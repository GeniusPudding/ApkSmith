"""Smali syntax parsing utilities.

Ported from SADroid's ``smali_utils/smali_parser.py`` — stripped of dead
code, console debugging artefacts, and ``rich`` dependency.
"""

from __future__ import annotations

import hashlib

# ---------------------------------------------------------------------------
# Hashing
# ---------------------------------------------------------------------------

def hash_sign(sign: str) -> str:
    """Return the first 16 hex chars of the SHA-256 of *sign*."""
    return hashlib.sha256(sign.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Method-signature helpers
# ---------------------------------------------------------------------------

def param_registers_num(params_list: list[str]) -> int:
    """Number of Dalvik registers a parameter list occupies (J/D take 2)."""
    return len(params_list) + params_list.count("J") + params_list.count("D")


def get_dirlist(method_sign: str) -> list[str]:
    """Split ``Lfoo/bar/Baz;->qux(...)V`` into ``['foo','bar','Baz','qux']``."""
    class_part, method_part = method_sign[1:].split(";->")
    return class_part.split("/") + [method_part.split("(")[0]]


def get_params_list(line: str, class_sign: str | None = None) -> list[str]:
    """Parse parameter type descriptors from a ``.method`` or ``invoke`` line.

    For ``.method`` lines the caller must supply *class_sign* (the owning
    class descriptor, e.g. ``Lfoo/Bar;``); non-static methods implicitly
    prepend the class as the first parameter (``this``).
    """
    if line.startswith(".method"):
        is_static = "static" in line.split(" ")
        if not class_sign:
            raise ValueError(f"method line '{line}' has no class_sign")
    elif line.startswith("    invoke"):
        is_static = line.startswith("    invoke-static")
        class_sign = line.split("->")[0].split(" ")[-1]
    else:
        raise ValueError(f"line '{line}' has no param string")

    param_string = line[line.index("(") + 1 : line.index(")")]
    if param_string == "":
        return [] if is_static else [class_sign]

    params_list: list[str] = []
    partitions_id: list[int] = []
    in_class = False
    for i, ch in enumerate(param_string):
        if ch == "L":
            in_class = True
        if in_class:
            if ch == ";":
                in_class = False
                partitions_id.append(i)
        else:
            if ch != "[":
                partitions_id.append(i)

    last_p = 0
    for p in partitions_id:
        params_list.append(param_string[last_p : p + 1])
        last_p = p + 1

    if not is_static:
        params_list = [class_sign] + params_list
    return params_list


def is_non_common_instruction(smali_line: str) -> bool:
    """True for directives, labels, comments, blank lines.

    Anything that is NOT a regular Dalvik instruction.
    """
    return (
        any(smali_line.startswith(e) for e in ["    .", "    :", "    #", ".", "     "])
        or smali_line.strip() == ""
    )


def is_target_method(
    method_sign: str,
    smali_base_dir: str,  # noqa: ARG001 – kept for call-site compat
    target_api_graph: dict,
) -> bool:
    """Return True if *method_sign* matches the target-API trie."""
    try:
        dir_list = get_dirlist(method_sign)
    except Exception:
        return False
    current = target_api_graph
    for d in dir_list:
        if d not in current:
            return False
        current = current[d]
    return True
