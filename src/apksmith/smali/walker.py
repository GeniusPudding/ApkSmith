"""Walk a decompiled APK's smali tree, applying a rewrite function to each file.

Ported from SADroid's ``core_SADroid_logger.walk_smali_dir`` — parameterised
so that the skip-lists come from :class:`~apksmith.config.InstrumentConfig`
rather than module-level constants.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterable
from typing import Any

from apksmith.config import DEFAULT_SKIP_COM_CHILDREN, DEFAULT_SKIP_PACKAGES


def walk_smali_dir(
    smali_base_dir: str,
    target_api_graph: dict[str, Any],
    app_hash: str,
    rewrite_fn: Callable[[list[str], str, dict, str], str],
    *,
    on_method: Callable[[str, str], None] | None = None,
    skip_packages: Iterable[str] = DEFAULT_SKIP_PACKAGES,
    skip_com_children: Iterable[str] = DEFAULT_SKIP_COM_CHILDREN,
) -> None:
    """Walk one ``smali*/`` root and rewrite every non-framework ``.smali`` in place.

    Parameters
    ----------
    smali_base_dir:
        e.g. ``<apktool_dir>/smali`` or ``<apktool_dir>/smali_classes2``.
    target_api_graph:
        Nested-dict trie of "interesting" API calls.
    app_hash:
        Short hash identifying the current app.
    rewrite_fn:
        ``(smali_lines, smali_base_dir, target_api_graph, app_hash) -> new_content``
        The actual rewriting pass to apply per file.
    on_method:
        Optional ``(method_hash, method_sign) -> None`` forwarded to *rewrite_fn*.
    skip_packages:
        Top-level package names to ignore (e.g. ``android``, ``kotlin``).
    skip_com_children:
        Children of ``com/`` to ignore (e.g. ``google``, ``facebook``).
    """
    skip_set = set(skip_packages)
    com_skip = set(skip_com_children)

    walking_list: list[tuple[str, list[str], list[str]]] = []

    for d in os.listdir(smali_base_dir):
        if d in skip_set:
            continue
        if d == "com":
            com_dir = os.path.join(smali_base_dir, "com")
            for dd in os.listdir(com_dir):
                if dd in com_skip:
                    continue
                w = list(os.walk(os.path.join(com_dir, dd)))
                if w:
                    walking_list.extend(w)
        else:
            w = list(os.walk(os.path.join(smali_base_dir, d)))
            if w:
                walking_list.extend(w)

    for dirpath, _dirnames, filenames in walking_list:
        for fname in filenames:
            if not fname.endswith(".smali"):
                continue

            full_path = os.path.join(os.path.abspath(dirpath), fname)
            with open(full_path, encoding="utf-8") as f:
                smali_lines = list(f)

            new_content = rewrite_fn(
                smali_lines,
                smali_base_dir,
                target_api_graph,
                app_hash,
                on_method,
            )

            with open(full_path, "w", encoding="utf-8") as f:
                f.write(new_content)
