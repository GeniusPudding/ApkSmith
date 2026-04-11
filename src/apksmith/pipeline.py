"""End-to-end `instrument_apk` orchestration.

This is the top-level entry point: decompile → walk smali → apply
transform passes → patch runtime helpers → repack → zipalign → sign.

Until the core is ported over from SADroid, this module intentionally
raises ``NotImplementedError`` so that importers see a clear message
rather than running against a half-baked pipeline.
"""

from __future__ import annotations

from pathlib import Path

from apksmith.config import InstrumentConfig
from apksmith.result import InstrumentResult


def instrument_apk(
    apk_path: Path,
    output_dir: Path,
    config: InstrumentConfig,
) -> InstrumentResult:
    """Run the full ApkSmith pipeline on ``apk_path``.

    Parameters
    ----------
    apk_path:
        The input APK. Must exist.
    output_dir:
        Directory in which to write working files and the final repacked
        APK. Will be created if missing.
    config:
        Everything else — tool paths, keystore, passes, callbacks.

    Returns
    -------
    InstrumentResult
        Includes the path to the repacked APK, the app hash, the map of
        method hashes to signatures, and per-run stats.
    """
    raise NotImplementedError(
        "instrument_apk is not wired yet. Track B (SADroid in-place refactor) "
        "will populate this module via `git subtree split`. See README roadmap."
    )
