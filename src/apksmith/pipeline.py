"""End-to-end ``instrument_apk`` orchestration.

Decompile -> walk smali -> apply trace_logger pass -> patch runtime
helpers -> repack -> zipalign -> sign.
"""

from __future__ import annotations

import importlib.resources
import os
from pathlib import Path

from apksmith.config import InstrumentConfig
from apksmith.passes.trace_logger import method_logger
from apksmith.result import InstrumentResult, InstrumentStats
from apksmith.smali.parser import hash_sign
from apksmith.smali.walker import walk_smali_dir
from apksmith.toolchain.tools import (
    build,
    decompile,
    find_apksigner,
    find_apktool,
    find_zipalign,
    sign,
    zipalign,
)


def _patch_helper_class(smali_base_dir: str, log_tag: str) -> None:
    """Copy ``InlineLogs.smali`` into the decompiled tree.

    The helper class lives under ``ApkSmith/InlineLogs.smali`` inside the
    primary smali root. The logcat tag constant inside the file is
    rewritten to match ``log_tag``.
    """
    inject_dir = os.path.join(smali_base_dir, "ApkSmith")
    os.makedirs(inject_dir, exist_ok=True)

    # Read the template from the package resources.
    ref = importlib.resources.files("apksmith.resources").joinpath("InlineLogs.smali")
    template = ref.read_text(encoding="utf-8")

    # Replace the default logcat tag with the caller's choice.
    patched = template.replace(
        'const-string v0, "ApkSmith"',
        f'const-string v0, "{log_tag}"',
    )

    dest = os.path.join(inject_dir, "InlineLogs.smali")
    with open(dest, "w", encoding="utf-8") as f:
        f.write(patched)


def instrument_apk(
    apk_path: Path,
    output_dir: Path,
    config: InstrumentConfig,
) -> InstrumentResult:
    """Run the full ApkSmith pipeline on *apk_path*.

    Parameters
    ----------
    apk_path:
        The input APK. Must exist.
    output_dir:
        Directory for working files. Created if missing. The final
        repacked APK is written here as ``repacked_<stem>.apk``.
    config:
        All knobs: tool paths, keystore, tag, callbacks, etc.

    Returns
    -------
    InstrumentResult
    """
    apk_path = Path(apk_path)
    output_dir = Path(output_dir)
    if not apk_path.exists():
        raise FileNotFoundError(apk_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    # --- resolve tools -------------------------------------------------------
    apktool = find_apktool(config.apktool)
    zipalign_bin = find_zipalign(config.zipalign)
    apksigner = find_apksigner(config.apksigner)

    # --- names and hashes ----------------------------------------------------
    app_name = apk_path.stem
    app_hash = hash_sign(app_name)

    apktool_dir = str(output_dir / app_name)

    # --- method tracking -----------------------------------------------------
    methods: dict[str, str] = {}
    stats = InstrumentStats()

    user_cb = config.on_method

    def on_method(method_hash: str, method_sign: str) -> None:
        methods[method_hash] = method_sign
        stats.methods_patched += 1
        if user_cb is not None:
            user_cb(method_hash, method_sign)

    # --- 1. decompile --------------------------------------------------------
    if config.redecompile:
        decompile(apktool, str(apk_path), apktool_dir)

    # --- 2. instrument -------------------------------------------------------
    print("bytecode instrumentation")
    smali_dirs = [
        d for d in os.listdir(apktool_dir) if d.startswith("smali")
    ]
    for subdir in smali_dirs:
        smali_base = os.path.join(apktool_dir, subdir)
        walk_smali_dir(
            smali_base,
            config.target_api_graph,
            app_hash,
            rewrite_fn=method_logger,
            on_method=on_method,
            skip_packages=config.skip_package_prefixes,
            skip_com_children=config.skip_com_children,
        )
    # Patch runtime helper into the primary smali root.
    _patch_helper_class(
        os.path.join(apktool_dir, "smali"), config.log_tag,
    )

    # --- 3. repack -> zipalign -> sign ---------------------------------------
    print("repackage")
    build(apktool, apktool_dir)

    build_apk = os.path.join(apktool_dir, "dist", app_name + ".apk")
    aligned_apk = os.path.join(apktool_dir, "dist", app_name + "_aligned.apk")
    repacked_apk = str(output_dir / ("repacked_" + app_name + ".apk"))

    zipalign(zipalign_bin, build_apk, aligned_apk)
    sign(
        apksigner,
        aligned_apk,
        repacked_apk,
        keystore=str(config.keystore),
        ks_pass=config.keystore_pass,
        key_pass=config.resolved_key_pass(),
        key_alias=config.key_alias,
    )

    print(f"instrument_apk: {repacked_apk}")
    return InstrumentResult(
        repacked_apk=Path(repacked_apk),
        app_hash=app_hash,
        methods=methods,
        stats=stats,
    )
