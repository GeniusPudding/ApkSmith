"""``apksmith doctor`` — check that all prerequisites are in place.

Each check reports its version (or an error message) and whether it's
required or optional. The overall exit code is 0 if all required tools
are found, 1 otherwise.
"""

from __future__ import annotations

import shutil
import subprocess
import sys


def _ver(cmd: list[str]) -> str | None:
    """Run *cmd* and return the first version-like string, or None."""
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        text = (proc.stdout + proc.stderr).strip()
        # Grab first token that looks like a version number
        for token in text.replace(",", " ").split():
            if any(c.isdigit() for c in token) and "." in token:
                return token.strip("()")
        return text[:60] if text else None
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None


def _which(names: list[str]) -> str | None:
    for n in names:
        found = shutil.which(n)
        if found:
            return found
    return None


def run_doctor() -> int:
    """Print a diagnostic table and return 0 (all OK) or 1 (something missing)."""

    checks: list[tuple[str, list[str], list[str], bool]] = [
        # (label, binary_names, version_cmd_suffix, required)
        ("Python", [sys.executable], ["--version"], True),
        ("Java", ["java"], ["-version"], True),
        ("apktool", ["apktool", "apktool.bat"], ["--version"], True),
        ("zipalign", ["zipalign"], ["-h"], True),  # zipalign has no --version; -h exits 1 but prints info
        ("apksigner", ["apksigner", "apksigner.bat"], ["version"], True),
        ("adb", ["adb"], ["version"], True),
        ("keytool", ["keytool"], ["-help"], False),
        ("emulator", ["emulator"], ["-version"], False),
        ("aapt2", ["aapt2", "aapt"], ["version"], False),
    ]

    ok = "\u2713"
    fail = "\u2717"
    all_required_ok = True

    print()
    print(f"  {'Tool':<14} {'Version':<24} {'Status':<10} {'Note'}")
    print(f"  {'----':<14} {'-------':<24} {'------':<10} {'----'}")

    for label, names, ver_suffix, required in checks:
        path = _which(names)
        if path:
            ver = _ver([path] + ver_suffix)
            tag = "required" if required else "optional"
            print(f"  {label:<14} {(ver or '?'):<24} {ok:<10} {tag}")
        else:
            tag = "REQUIRED" if required else "optional"
            status = fail if required else "-"
            print(f"  {label:<14} {'(not found)':<24} {status:<10} {tag}")
            if required:
                all_required_ok = False

    # Device check
    adb_path = _which(["adb"])
    if adb_path:
        try:
            from apksmith.toolchain.adb import list_devices
            devices = list_devices(adb=adb_path)
            online = [d for d in devices if d["state"] == "device"]
            if online:
                serials = ", ".join(d["serial"] for d in online)
                print(f"\n  Devices      {len(online)} connected: {serials}")
            else:
                print(f"\n  Devices      0 connected (connect a device or start an emulator)")
        except Exception:
            print(f"\n  Devices      (could not query)")

    print()
    if all_required_ok:
        print("  All required tools found. You're ready to go.")
    else:
        print("  Some required tools are missing. Install them and try again.")
    print()

    return 0 if all_required_ok else 1
