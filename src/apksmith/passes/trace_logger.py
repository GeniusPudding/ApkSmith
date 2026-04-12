"""trace_logger pass — instrument every method with logcat tracing.

Ported from SADroid's ``core_SADroid_logger.py``. This is the first
(and so far only) concrete transform pass in ApkSmith.

For every non-``<clinit>`` method in a ``.smali`` file it:

* Reserves two extra local registers for scratch space.
* Emits a ``[Method START]`` log at entry (with a random-ID correlation tag).
* Emits a ``[Method END]`` log before every ``return*`` instruction.
* Emits a ``[TARGET API CALL]`` log before calls that match the target-API trie.
* Emits ``[Branch]`` / ``[TAG]`` logs around ``if-*`` and label instructions.

All log output goes through the helper class ``LApkSmith/InlineLogs;``
which is patched into the decompiled tree by
:func:`apksmith.pipeline.patch_helper_class`.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from apksmith.smali.parser import (
    get_dirlist,
    get_params_list,
    hash_sign,
    is_non_common_instruction,
    is_target_method,
    param_registers_num,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

HELPER_CLASS = "LApkSmith/InlineLogs;"
"""Smali class reference for the injected runtime helper."""

ADDITIONAL_LOCAL_COUNT = 2
"""How many extra v-registers to reserve per method for logging scratch."""


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

_get_invoke_sign = lambda line: line.strip().split(", ")[-1].strip()

_p2v_reg = lambda reg, locals_num: (
    "v" + str(int(reg[1:]) + locals_num) if reg[0] == "p" else reg
)

_tag_sign = lambda line: (
    line.strip().lstrip(":") if ":cond_" not in line else "True" + line.strip()
)


def _check_common_instruction_replace(line: str, locals_num: int) -> str:
    if not is_non_common_instruction(line):
        try:
            return _replace_p_to_v_in_line(line, locals_num)
        except Exception:
            return line
    return line


def _replace_p_to_v_in_line(line: str, locals_num: int) -> str:
    # invoke-xxx/range {pX .. pY} format
    range_matches = re.findall(r"\{p(\d+) \.\. p(\d+)\}", line)
    for start, end in range_matches:
        v_start = _p2v_reg("p" + start, locals_num)
        v_end = _p2v_reg("p" + end, locals_num)
        line = line.replace(f"{{p{start} .. p{end}}}", f"{{{v_start} .. {v_end}}}")
    # plain pX registers
    for reg in re.findall(r"\bp\d+\b", line):
        v_reg = _p2v_reg(reg, locals_num)
        line = re.sub(r"\b" + reg + r"\b", v_reg, line)
    return line


# ---------------------------------------------------------------------------
# Smali code generators
# ---------------------------------------------------------------------------

def _gen_method_start_log(
    method_hash: str, v_last: str, v_last2: str, app_hash: str,
) -> str:
    H = HELPER_CLASS
    s = f'    invoke-static {{}}, {H}->genRandom()Ljava/lang/String;\n\n'
    s += f"    move-result-object {v_last2}\n\n"
    s += f'    const-string {v_last}, "[{app_hash}], [Method START], [{method_hash}] "\n\n'
    s += f"    invoke-static/range {{{v_last} .. {v_last2}}}, {H}->stringCancate(Ljava/lang/String;Ljava/lang/String;)Ljava/lang/String;\n\n"
    s += f"    move-result-object {v_last}\n\n"
    s += f"    invoke-static/range {{{v_last}}}, {H}->monitorLog(Ljava/lang/String;)V\n\n"
    return s


def _gen_method_params_log(locals_num: int, params_list: list[str]) -> str:
    if not params_list:
        return ""
    s = ""
    p_count = 0
    for param in params_list:
        p_reg = f"p{p_count}"
        v_reg = _p2v_reg(p_reg, locals_num)
        if param in ("J", "D"):
            s += f"    move-wide/16 {v_reg}, {p_reg}\n\n"
            p_count += 1
        elif len(param) == 1:
            s += f"    move/16 {v_reg}, {p_reg}\n\n"
        else:
            s += f"    move-object/16 {v_reg}, {p_reg}\n\n"
        p_count += 1
    return s


def _emit_log(v_last: str, v_last2: str, msg: str) -> str:
    """Emit the 4-instruction log pattern used everywhere."""
    H = HELPER_CLASS
    s = f'    const-string {v_last}, "{msg}"\n\n'
    s += f"    invoke-static/range {{{v_last} .. {v_last2}}}, {H}->stringCancate(Ljava/lang/String;Ljava/lang/String;)Ljava/lang/String;\n\n"
    s += f"    move-result-object {v_last}\n\n"
    s += f"    invoke-static/range {{{v_last}}}, {H}->monitorLog(Ljava/lang/String;)V\n\n"
    return s


# ---------------------------------------------------------------------------
# The main rewriting function — one .smali file at a time
# ---------------------------------------------------------------------------

def method_logger(
    smali_lines: list[str],
    smali_base_dir: str,
    target_api_graph: dict[str, Any],
    app_hash: str,
    on_method: Callable[[str, str], None] | None = None,
) -> str:
    """Rewrite one ``.smali`` file, returning the instrumented text.

    *on_method* is an optional ``(method_hash, method_sign) -> None``
    callback fired once per patched method.
    """
    class_name = smali_lines[0].split(" ")[-1].strip("\n")
    if smali_lines[0].startswith(".class public interface abstract"):
        return "".join(smali_lines)

    in_method = False
    output_flag = 1
    current_method_signature = ""
    method_hash = ""
    new_content = ""
    locals_num = 0
    params_num = 0
    v_last = ""
    v_last2 = ""
    params_list: list[str] = []
    extra = ADDITIONAL_LOCAL_COUNT

    for i, line in enumerate(smali_lines):
        tmp_line = line

        if line.startswith(".method ") and "<clinit>(" not in line:
            in_method = True
            tokens = line.strip("\n").split(" ")
            current_method_signature = f"{class_name}->{tokens[-1]}"
            method_hash = hash_sign(current_method_signature)
            if on_method is not None:
                on_method(method_hash, current_method_signature)
            locals_num = 0
            params_list = get_params_list(line, class_name)
            params_num = param_registers_num(params_list)

        elif in_method:
            line = line.strip("\n")
            line = _check_common_instruction_replace(line, locals_num - extra)

            if line.startswith("    .locals "):
                locals_num = int(line.split(" ")[-1])
                if locals_num > 255:
                    new_content += "".join(smali_lines[i:])
                    return new_content
                num = locals_num + params_num
                v_last = "v" + str(num)
                v_last2 = "v" + str(num + 1)
                line = line.replace(str(locals_num), str(locals_num + extra))
                new_content += line + "\n"
                new_content += _gen_method_params_log(locals_num, params_list)
                new_content += _gen_method_start_log(method_hash, v_last, v_last2, app_hash)
                locals_num += extra
                output_flag = 0

            elif line.startswith(".end method"):
                in_method = False

            elif line.startswith("    return"):
                new_content += _emit_log(
                    v_last, v_last2,
                    f"[{app_hash}], [Method END], [{method_hash}] ",
                )

            elif line.startswith("    invoke"):
                invoke_sign = _get_invoke_sign(line)
                if is_target_method(invoke_sign, smali_base_dir, target_api_graph):
                    new_content += _emit_log(
                        v_last, v_last2,
                        f"[{app_hash}], [TARGET API CALL: {invoke_sign} - (line {i})], [{method_hash}] ",
                    )

            elif line.startswith("    if-"):
                output_flag = 0
                new_content += _emit_log(
                    v_last, v_last2,
                    f"[{app_hash}], [Branch: {tmp_line.strip()} - (line {i})], [{method_hash}] ",
                )
                new_content += line + "\n\n"
                false_tag = "False" + line.strip().split(" ")[-1]
                new_content += _emit_log(
                    v_last, v_last2,
                    f"[{app_hash}], [TAG: {false_tag} - (line {i})], [{method_hash}] ",
                )

            elif line.startswith("    move-exception"):
                output_flag = 0

            elif line.startswith("    :"):
                output_flag = 0
                last_line = smali_lines[i - 1]
                if not last_line.startswith("    :"):
                    next_line = _check_common_instruction_replace(
                        smali_lines[i + 1], locals_num - extra,
                    )
                    next2_line = _check_common_instruction_replace(
                        smali_lines[i + 2], locals_num - extra,
                    )
                    tag_str = f"[{app_hash}], [TAG: "

                    if line.startswith("    :try_end"):
                        catch_list = next_line.strip().split(" ")
                        end, catch = catch_list[-2][1:-1], catch_list[-1][1:]
                        tag_str += f"{end}->:{catch} - (line {i})], [{method_hash}] "
                        new_content += _emit_log(v_last, v_last2, tag_str)
                        new_content += line + "\n"

                    elif line.startswith("    :sswitch_data") or line.startswith("    :pswitch_data"):
                        new_content += line + "\n"

                    elif line.startswith("    :array"):
                        new_content += line + "\n"

                    elif line.startswith("    :catch"):
                        new_content += line + "\n"
                        new_content += next_line
                        if next_line.startswith("    :"):
                            new_content += next2_line
                        tag_str += f"{_tag_sign(line)} - (line {i})], [{method_hash}] "
                        new_content += "\n" + _emit_log(v_last, v_last2, tag_str)

                    else:  # common tag
                        new_content += line + "\n"
                        tag_str += _tag_sign(line)
                        if next_line.startswith("    :"):
                            new_content += next_line
                            tag_str += "," + _tag_sign(next_line)
                            if next2_line.startswith("    :"):
                                new_content += next2_line
                                tag_str += "," + _tag_sign(next2_line)
                        tag_str += f" - (line {i})], [{method_hash}] "
                        new_content += _emit_log(v_last, v_last2, tag_str)

            line += "\n"

        if output_flag:
            new_content += line
        else:
            output_flag = 1

    return new_content
