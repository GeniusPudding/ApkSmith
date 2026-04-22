"""pytest fixtures for ApkSmith E2E tests.

The E2E tests talk to a real Android emulator or device via adb and
run the full decompile -> instrument -> install -> launch -> verify
pipeline. They are automatically skipped when prerequisites are not
met (no device, missing tools, fixture not built), so a plain
``pytest`` run on a machine without Android tooling still succeeds.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

FIXTURE_DIR = Path(__file__).parent / "fixtures"
HELLO_APK = FIXTURE_DIR / "hello_app.apk"
DEBUG_KEYSTORE = FIXTURE_DIR / "debug.keystore"


def _have(*names: str) -> bool:
    return all(shutil.which(n) is not None for n in names)


def _have_any(*names: str) -> bool:
    return any(shutil.which(n) is not None for n in names)


def _online_devices() -> list[str]:
    try:
        out = subprocess.run(
            ["adb", "devices"], capture_output=True, text=True, check=True,
        ).stdout
    except (FileNotFoundError, subprocess.CalledProcessError):
        return []
    serials: list[str] = []
    for line in out.strip().splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "device":
            serials.append(parts[0])
    return serials


@pytest.fixture(scope="session")
def require_tools():
    """Skip test if apktool / zipalign / apksigner are not on PATH."""
    missing: list[str] = []
    if not _have_any("apktool", "apktool.bat"):
        missing.append("apktool")
    if not _have("zipalign"):
        missing.append("zipalign")
    if not _have_any("apksigner", "apksigner.bat"):
        missing.append("apksigner")
    if missing:
        pytest.skip(
            f"Missing required tools on PATH: {', '.join(missing)}. "
            f"Run 'apksmith doctor' for a full report."
        )


@pytest.fixture(scope="session")
def require_device():
    """Skip test if no Android device / emulator is connected."""
    if not _have("adb"):
        pytest.skip("adb not on PATH")
    devices = _online_devices()
    if not devices:
        pytest.skip(
            "No Android device or emulator online. "
            "Start an emulator or connect a device, then re-run."
        )
    # Use the first online device; multi-device runs can override.
    return devices[0]


@pytest.fixture(scope="session")
def require_fixture_apk():
    """Skip test if hello_app.apk has not been built yet."""
    if not HELLO_APK.exists():
        pytest.skip(
            f"Fixture APK not built: {HELLO_APK}\n"
            f"Build it once with: tests/e2e/fixtures/hello_app/build.sh\n"
            f"(requires ANDROID_HOME + JDK)"
        )
    return HELLO_APK


@pytest.fixture(scope="session")
def require_keystore():
    """Skip test if the debug keystore is missing."""
    if not DEBUG_KEYSTORE.exists():
        pytest.skip(
            f"Debug keystore missing: {DEBUG_KEYSTORE}\n"
            f"It is generated automatically the first time build.sh runs."
        )
    return DEBUG_KEYSTORE
