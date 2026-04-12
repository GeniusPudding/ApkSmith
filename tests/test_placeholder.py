"""Tests for ApkSmith core modules."""

from pathlib import Path

import pytest

import apksmith
from apksmith import InstrumentConfig, InstrumentResult, InstrumentStats
from apksmith.smali.parser import (
    get_dirlist,
    get_params_list,
    hash_sign,
    is_non_common_instruction,
    is_target_method,
    param_registers_num,
)
from apksmith.passes.trace_logger import (
    _check_common_instruction_replace,
    _emit_log,
    _gen_method_start_log,
    _replace_p_to_v_in_line,
    method_logger,
)
from apksmith.toolchain.tools import find_apktool, ToolNotFoundError


# ---------------------------------------------------------------------------
# Public API surface
# ---------------------------------------------------------------------------

class TestPublicAPI:
    def test_version_exists(self):
        assert hasattr(apksmith, "__version__")

    def test_instrument_apk_callable(self):
        assert callable(apksmith.instrument_apk)

    def test_config_defaults(self):
        cfg = InstrumentConfig(keystore=Path("/tmp/x.keystore"), keystore_pass="pw")
        assert cfg.log_tag == "ApkSmith"
        assert cfg.extra_local_regs == 2
        assert cfg.redecompile is True
        assert cfg.resolved_key_pass() == "pw"
        assert "android" in cfg.skip_package_prefixes

    def test_config_key_pass_override(self):
        cfg = InstrumentConfig(keystore=Path("/k"), keystore_pass="s", key_pass="k")
        assert cfg.resolved_key_pass() == "k"

    def test_result_defaults(self):
        r = InstrumentResult(repacked_apk=Path("/x.apk"), app_hash="a" * 16)
        assert r.methods == {}
        assert isinstance(r.stats, InstrumentStats)
        assert r.stats.methods_patched == 0


# ---------------------------------------------------------------------------
# Smali parser
# ---------------------------------------------------------------------------

class TestParser:
    def test_hash_sign_deterministic(self):
        assert hash_sign("Lfoo/Bar;->baz()V") == hash_sign("Lfoo/Bar;->baz()V")
        assert len(hash_sign("x")) == 16

    def test_get_dirlist(self):
        assert get_dirlist("Lfoo/bar/Baz;->qux(I)V") == ["foo", "bar", "Baz", "qux"]

    def test_param_registers_num_basic(self):
        assert param_registers_num(["I", "Z"]) == 2

    def test_param_registers_num_wide(self):
        assert param_registers_num(["J", "I"]) == 3  # J takes 2

    def test_get_params_list_static(self):
        line = ".method public static foo(ILjava/lang/String;)V"
        result = get_params_list(line, "Lcom/example/A;")
        assert result == ["I", "Ljava/lang/String;"]

    def test_get_params_list_non_static(self):
        line = ".method public foo(I)V"
        result = get_params_list(line, "Lcom/example/A;")
        assert result == ["Lcom/example/A;", "I"]

    def test_is_non_common_instruction(self):
        assert is_non_common_instruction("    .locals 3")
        assert is_non_common_instruction("    :cond_0")
        assert is_non_common_instruction("")
        assert not is_non_common_instruction("    invoke-virtual {v0}, Lfoo;->bar()V")

    def test_is_target_method_hit(self):
        graph = {"foo": {"bar": {"Baz": {"qux": {}}}}}
        assert is_target_method("Lfoo/bar/Baz;->qux(I)V", "/dummy", graph)

    def test_is_target_method_miss(self):
        graph = {"foo": {"bar": {}}}
        assert not is_target_method("Lfoo/bar/Baz;->qux(I)V", "/dummy", graph)


# ---------------------------------------------------------------------------
# Trace logger pass
# ---------------------------------------------------------------------------

class TestTraceLogger:
    def test_replace_p_to_v(self):
        line = "    iput-object p1, p0, Lfoo;->bar:I"
        result = _replace_p_to_v_in_line(line, 3)
        assert "v4" in result  # p1 -> v4 (1+3)
        assert "v3" in result  # p0 -> v3 (0+3)

    def test_check_common_instruction_replace_skips_directives(self):
        line = "    .locals 3"
        assert _check_common_instruction_replace(line, 5) == line

    def test_gen_method_start_log_contains_marker(self):
        out = _gen_method_start_log("abc123", "v10", "v11", "apphash")
        assert "[Method START]" in out
        assert "[abc123]" in out
        assert "LApkSmith/InlineLogs;" in out

    def test_emit_log_pattern(self):
        out = _emit_log("v5", "v6", "test message")
        assert 'const-string v5, "test message"' in out
        assert "monitorLog" in out

    def test_method_logger_skips_interface(self):
        lines = [".class public interface abstract Lfoo/Bar;\n", ".end class\n"]
        result = method_logger(lines, "/dummy", {}, "hash")
        assert result == ".class public interface abstract Lfoo/Bar;\n.end class\n"

    def test_method_logger_basic_method(self):
        lines = [
            ".class public Lcom/example/A;\n",
            ".super Ljava/lang/Object;\n",
            "\n",
            ".method public foo()V\n",
            "    .locals 1\n",
            "    return-void\n",
            ".end method\n",
        ]
        collected: list[tuple[str, str]] = []
        result = method_logger(lines, "/dummy", {}, "testhash", on_method=lambda h, s: collected.append((h, s)))
        assert "[Method START]" in result
        assert "[Method END]" in result
        assert len(collected) == 1
        assert collected[0][1] == "Lcom/example/A;->foo()V"

    def test_method_logger_skips_clinit(self):
        lines = [
            ".class public Lcom/example/A;\n",
            "\n",
            ".method static constructor <clinit>()V\n",
            "    .locals 0\n",
            "    return-void\n",
            ".end method\n",
        ]
        result = method_logger(lines, "/dummy", {}, "testhash")
        assert "[Method START]" not in result

    def test_method_logger_branch(self):
        lines = [
            ".class public Lcom/example/A;\n",
            "\n",
            ".method public foo(I)V\n",
            "    .locals 1\n",
            "    if-eqz p1, :cond_0\n",
            "    return-void\n",
            "    :cond_0\n",
            "    return-void\n",
            ".end method\n",
        ]
        result = method_logger(lines, "/dummy", {}, "testhash")
        assert "[Branch:" in result
        assert "[TAG:" in result

    def test_method_logger_locals_gt_255_bails(self):
        lines = [
            ".class public Lcom/example/A;\n",
            "\n",
            ".method public foo()V\n",
            "    .locals 256\n",
            "    return-void\n",
            ".end method\n",
        ]
        result = method_logger(lines, "/dummy", {}, "testhash")
        # Should NOT instrument — the .locals 256 line stays as-is
        assert "[Method START]" not in result


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

class TestTools:
    def test_find_apktool_raises_when_missing(self, monkeypatch):
        monkeypatch.setattr("shutil.which", lambda _: None)
        with pytest.raises(ToolNotFoundError):
            find_apktool()
