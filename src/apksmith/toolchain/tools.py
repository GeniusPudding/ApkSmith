"""Locate external tools (apktool / zipalign / apksigner) on PATH.

These helpers are intentionally tiny: Track B will grow them into full
``subprocess.run`` wrappers with proper error reporting.
"""

from __future__ import annotations

import shutil


class ToolNotFoundError(RuntimeError):
    """Raised when a required external tool cannot be located."""


def find_apktool(override: str | None = None) -> str:
    """Return a runnable path for apktool.

    On Windows the binary is typically ``apktool.bat``; elsewhere it is
    ``apktool``. Both are accepted.
    """
    if override:
        return override
    for candidate in ("apktool", "apktool.bat"):
        found = shutil.which(candidate)
        if found:
            return found
    raise ToolNotFoundError(
        "Could not find 'apktool' or 'apktool.bat' on PATH. "
        "Install it from https://apktool.org and try again."
    )


def find_zipalign(override: str | None = None) -> str:
    if override:
        return override
    found = shutil.which("zipalign")
    if found:
        return found
    raise ToolNotFoundError(
        "Could not find 'zipalign' on PATH. It ships with the Android SDK build-tools."
    )


def find_apksigner(override: str | None = None) -> str:
    if override:
        return override
    for candidate in ("apksigner", "apksigner.bat"):
        found = shutil.which(candidate)
        if found:
            return found
    raise ToolNotFoundError(
        "Could not find 'apksigner' on PATH. It ships with the Android SDK build-tools."
    )
