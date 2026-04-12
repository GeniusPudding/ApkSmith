"""ADB (Android Debug Bridge) helpers.

Handles device discovery, APK extraction, installation, and uninstallation.
Every function that talks to a device accepts an optional *serial* parameter;
when omitted, the single connected device is used. If multiple devices are
connected and no serial is given, an error is raised with the list of
available serials so the user can pick one.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from apksmith.toolchain.tools import ToolNotFoundError


# ---------------------------------------------------------------------------
# Locator
# ---------------------------------------------------------------------------

def find_adb(override: str | None = None) -> str:
    if override:
        return override
    found = shutil.which("adb")
    if found:
        return found
    raise ToolNotFoundError(
        "Could not find 'adb' on PATH. It ships with Android SDK platform-tools."
    )


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _adb(args: list[str], *, serial: str | None = None, adb: str | None = None) -> str:
    """Run an adb command and return stdout. Raises on failure."""
    adb_bin = find_adb(adb)
    cmd = [adb_bin]
    if serial:
        cmd += ["-s", serial]
    cmd += args
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
    except FileNotFoundError as exc:
        raise ToolNotFoundError(f"adb not found: {exc.filename}") from exc
    except subprocess.CalledProcessError as exc:
        msg = (exc.stderr or exc.stdout or "").strip()
        raise RuntimeError(f"adb {' '.join(args)} failed (exit {exc.returncode}): {msg}") from exc
    return proc.stdout


# ---------------------------------------------------------------------------
# Device discovery
# ---------------------------------------------------------------------------

def list_devices(*, adb: str | None = None) -> list[dict[str, str]]:
    """Return a list of connected devices as ``[{"serial": ..., "state": ...}, ...]``."""
    out = _adb(["devices"], adb=adb)
    devices = []
    for line in out.strip().splitlines()[1:]:  # skip header
        parts = line.split()
        if len(parts) >= 2:
            devices.append({"serial": parts[0], "state": parts[1]})
    return devices


def require_device(serial: str | None = None, *, adb: str | None = None) -> str:
    """Return a valid device serial, or raise with a helpful message.

    If *serial* is given, verifies it's connected. Otherwise, auto-selects
    the single connected device — errors clearly when zero or multiple
    devices are found.
    """
    devices = [d for d in list_devices(adb=adb) if d["state"] == "device"]

    if serial:
        serials = {d["serial"] for d in devices}
        if serial not in serials:
            raise RuntimeError(
                f"Device '{serial}' not found. Connected devices: "
                + (", ".join(serials) if serials else "(none)")
            )
        return serial

    if len(devices) == 0:
        raise RuntimeError(
            "No Android devices connected. Connect a device or start an emulator, "
            "then try again. (Tip: run 'adb devices' to check.)"
        )
    if len(devices) == 1:
        return devices[0]["serial"]

    serials = [d["serial"] for d in devices]
    raise RuntimeError(
        f"Multiple devices connected: {', '.join(serials)}\n"
        f"Use -d <serial> to pick one."
    )


# ---------------------------------------------------------------------------
# Package info
# ---------------------------------------------------------------------------

def get_package_apk_paths(package: str, *, serial: str | None = None, adb: str | None = None) -> list[str]:
    """Return the on-device paths to all APK files for *package*.

    Most apps have a single ``base.apk``. Apps installed via Play Store
    with app bundles may have additional ``split_config.*.apk`` files.
    """
    out = _adb(["shell", "pm", "path", package], serial=serial, adb=adb)
    paths = []
    for line in out.strip().splitlines():
        m = re.match(r"^package:(.+)$", line.strip())
        if m:
            paths.append(m.group(1))
    if not paths:
        raise RuntimeError(
            f"Package '{package}' not found on device. "
            f"Check the package name with: adb shell pm list packages | grep <keyword>"
        )
    return paths


# ---------------------------------------------------------------------------
# Pull
# ---------------------------------------------------------------------------

def pull_apk(
    package: str,
    output_dir: Path,
    *,
    serial: str | None = None,
    adb: str | None = None,
) -> list[Path]:
    """Pull all APK files for *package* from the device into *output_dir*.

    Returns a list of local paths. For single-APK apps this is one file;
    for split APKs it may be several.
    """
    serial = require_device(serial, adb=adb)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    device_paths = get_package_apk_paths(package, serial=serial, adb=adb)
    local_paths: list[Path] = []

    for dp in device_paths:
        # Name the local file after the APK filename on device
        fname = dp.rsplit("/", 1)[-1]  # e.g. "base.apk" or "split_config.arm64_v8a.apk"
        # Prefix with package name to avoid collisions
        local_name = f"{package}_{fname}"
        local_path = output_dir / local_name
        print(f"Pulling {dp} -> {local_path}")
        _adb(["pull", dp, str(local_path)], serial=serial, adb=adb)
        local_paths.append(local_path)

    return local_paths


# ---------------------------------------------------------------------------
# Install / Uninstall
# ---------------------------------------------------------------------------

def uninstall_package(
    package: str,
    *,
    serial: str | None = None,
    adb: str | None = None,
    keep_data: bool = False,
) -> None:
    """Uninstall a package from the device."""
    serial = require_device(serial, adb=adb)
    cmd = ["uninstall"]
    if keep_data:
        cmd.append("-k")
    cmd.append(package)
    try:
        _adb(cmd, serial=serial, adb=adb)
        print(f"Uninstalled {package}")
    except RuntimeError:
        # Package might not be installed — that's fine
        print(f"Note: {package} was not installed (or already removed)")


def install_apk(
    apk_paths: list[Path] | Path,
    *,
    serial: str | None = None,
    adb: str | None = None,
) -> None:
    """Install one or more APK files to the device.

    For a single APK, uses ``adb install -r``.
    For split APKs (multiple files), uses ``adb install-multiple -r``.
    """
    serial = require_device(serial, adb=adb)
    adb_bin = find_adb(adb)

    if isinstance(apk_paths, Path):
        apk_paths = [apk_paths]

    str_paths = [str(p) for p in apk_paths]

    if len(str_paths) == 1:
        cmd = [adb_bin, "-s", serial, "install", "-r", str_paths[0]]
    else:
        cmd = [adb_bin, "-s", serial, "install-multiple", "-r"] + str_paths

    print(f"Installing {', '.join(p.name for p in apk_paths)} to {serial}")
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("Install successful")
    except subprocess.CalledProcessError as exc:
        msg = (exc.stderr or exc.stdout or "").strip()
        raise RuntimeError(f"Install failed: {msg}") from exc


def get_package_name_from_apk(apk_path: Path, *, aapt: str | None = None) -> str | None:
    """Try to extract the package name from an APK using aapt or aapt2."""
    for tool in ([aapt] if aapt else ["aapt2", "aapt"]):
        found = shutil.which(tool)
        if not found:
            continue
        try:
            out = subprocess.run(
                [found, "dump", "badging", str(apk_path)],
                capture_output=True, text=True, check=True,
            ).stdout
            m = re.search(r"package:\s*name='([^']+)'", out)
            if m:
                return m.group(1)
        except (subprocess.CalledProcessError, FileNotFoundError):
            continue
    return None
