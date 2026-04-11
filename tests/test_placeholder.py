"""Smoke tests for the v0.0.1 scaffold.

These exist so CI has something to run while the real code is being
ported over from SADroid. They are intentionally trivial.
"""

from pathlib import Path

import pytest

import apksmith
from apksmith import InstrumentConfig, InstrumentResult, InstrumentStats


def test_public_api_surface():
    assert hasattr(apksmith, "__version__")
    assert hasattr(apksmith, "instrument_apk")
    assert hasattr(apksmith, "InstrumentConfig")
    assert hasattr(apksmith, "InstrumentResult")


def test_config_defaults():
    cfg = InstrumentConfig(keystore=Path("/tmp/x.keystore"), keystore_pass="pw")
    assert cfg.log_tag == "ApkSmith"
    assert cfg.extra_local_regs == 2
    assert cfg.redecompile is True
    assert cfg.resolved_key_pass() == "pw"
    assert "android" in cfg.skip_package_prefixes


def test_config_key_pass_override():
    cfg = InstrumentConfig(
        keystore=Path("/tmp/x.keystore"),
        keystore_pass="store",
        key_pass="key",
    )
    assert cfg.resolved_key_pass() == "key"


def test_result_defaults():
    r = InstrumentResult(repacked_apk=Path("/tmp/out.apk"), app_hash="deadbeef" * 2)
    assert r.methods == {}
    assert isinstance(r.stats, InstrumentStats)
    assert r.stats.methods_patched == 0


def test_instrument_apk_not_implemented():
    """Placeholder pipeline raises a clear error until Track B lands."""
    cfg = InstrumentConfig(keystore=Path("/tmp/x.keystore"), keystore_pass="pw")
    with pytest.raises(NotImplementedError, match="not wired yet"):
        apksmith.instrument_apk(Path("/tmp/x.apk"), Path("/tmp/out"), cfg)
