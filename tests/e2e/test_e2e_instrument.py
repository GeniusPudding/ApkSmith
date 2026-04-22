"""End-to-end test: instrument an APK, install it on a real device, launch it, verify logs.

Run with::

    pytest tests/e2e/ -v

The test is automatically skipped when any prerequisite is missing
(fixture APK, keystore, adb, device, or build tools), so it is safe
to include in the default pytest run on machines without Android
tooling.
"""

from __future__ import annotations

import re
import subprocess
import time
from pathlib import Path

import pytest

from apksmith import InstrumentConfig, instrument_apk
from apksmith.toolchain.adb import get_package_name_from_apk

PACKAGE = "com.apksmith.test"
MAIN_ACTIVITY = f"{PACKAGE}/.MainActivity"
LOG_TAG = "ApkSmithE2E"
ORIGINAL_LOG_TAG = "HelloApp"

# How long to wait after `am start` before capturing logs. The app is
# small so a couple of seconds is plenty.
LAUNCH_WAIT_SECONDS = 3


def _adb(serial: str, *args: str) -> str:
    cmd = ["adb", "-s", serial, *args]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return proc.stdout


def _adb_maybe(serial: str, *args: str) -> tuple[int, str, str]:
    """Run adb without raising; return (returncode, stdout, stderr)."""
    cmd = ["adb", "-s", serial, *args]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return proc.returncode, proc.stdout, proc.stderr


@pytest.mark.e2e
def test_instrument_install_launch_verify_logs(
    tmp_path: Path,
    require_tools,
    require_device: str,
    require_fixture_apk: Path,
    require_keystore: Path,
):
    """Full pipeline: build modded APK, install, launch, verify logcat."""
    serial = require_device
    output_dir = tmp_path / "out"
    output_dir.mkdir()

    # ----- 1. Instrument ----------------------------------------------------
    config = InstrumentConfig(
        keystore=require_keystore,
        keystore_pass="changeit",
        key_alias="hellokey",
        log_tag=LOG_TAG,
    )
    result = instrument_apk(require_fixture_apk, output_dir, config)

    assert result.repacked_apk.exists(), "Repacked APK was not produced"
    assert result.stats.methods_patched > 0, "No methods were patched"

    # Sanity-check that our three methods are in the method map.
    signatures = set(result.methods.values())
    assert any("->onCreate(" in s for s in signatures), \
        f"MainActivity.onCreate not in patched methods: {signatures}"
    assert any("->compute(" in s for s in signatures), \
        f"MainActivity.compute not in patched methods: {signatures}"
    assert any("->handleResult(" in s for s in signatures), \
        f"MainActivity.handleResult not in patched methods: {signatures}"

    # ----- 2. Verify package name inside the rebuilt APK --------------------
    pkg = get_package_name_from_apk(result.repacked_apk)
    # aapt may not be on PATH — skip the assertion if so, but warn.
    if pkg is not None:
        assert pkg == PACKAGE, f"Unexpected package: {pkg}"

    # ----- 3. Uninstall any previous version --------------------------------
    _adb_maybe(serial, "uninstall", PACKAGE)

    # ----- 4. Install the instrumented APK ----------------------------------
    rc, stdout, stderr = _adb_maybe(
        serial, "install", "-r", str(result.repacked_apk),
    )
    assert rc == 0, f"adb install failed:\n{stdout}\n{stderr}"

    # ----- 5. Force-stop, clear logcat, and launch fresh --------------------
    # force-stop ensures onCreate runs again even if the app was already
    # in foreground from a previous test run.
    _adb_maybe(serial, "shell", "am", "force-stop", PACKAGE)
    time.sleep(1)
    # Enlarge logcat buffer and clear it so our window is clean.
    _adb_maybe(serial, "logcat", "-G", "4M")
    _adb(serial, "logcat", "-c")
    time.sleep(1)
    _adb(serial, "shell", "am", "start", "-n", MAIN_ACTIVITY)

    time.sleep(LAUNCH_WAIT_SECONDS)

    # ----- 6. Capture logcat -----------------------------------------------
    # Drain the entire logcat buffer, then filter locally. Using
    # `logcat -d TAG:D *:S` is unreliable on some emulator images (it
    # can return empty output even when matching lines exist), so we
    # grab everything and grep in Python.
    raw_logs = _adb(serial, "logcat", "-d")
    all_logs = "\n".join(
        line for line in raw_logs.splitlines()
        if any(tag in line for tag in [LOG_TAG, ORIGINAL_LOG_TAG, "FATAL EXCEPTION"])
    )

    # ----- 7. Verify the original app still works --------------------------
    # If instrumentation broke the app, ORIGINAL logs will NOT appear.
    assert f"D/{ORIGINAL_LOG_TAG}" in all_logs or ORIGINAL_LOG_TAG in all_logs, (
        f"Original Log.d calls did not appear — instrumentation may have broken "
        f"the app. Full log:\n{all_logs}"
    )
    assert "onCreate_begin" in all_logs, \
        f"onCreate did not execute. Logs:\n{all_logs}"
    assert "onCreate_end" in all_logs, \
        f"onCreate did not complete. Logs:\n{all_logs}"
    assert "compute_positive_branch" in all_logs, \
        f"if-branch in compute() did not execute. Logs:\n{all_logs}"

    # ----- 8. Verify the app did not crash ---------------------------------
    assert "FATAL EXCEPTION" not in all_logs, (
        f"App crashed after instrumentation.\n{all_logs}"
    )

    # ----- 9. Verify the instrumented logs appear --------------------------
    assert f"D/{LOG_TAG}" in all_logs or LOG_TAG in all_logs, (
        f"No instrumented logs with tag '{LOG_TAG}' appeared. "
        f"The injected Log.d calls are not firing.\n{all_logs}"
    )

    # We should see [Method START] and [Method END] at least once for
    # each instrumented method that ran (onCreate + compute + handleResult).
    method_start_count = all_logs.count("[Method START]")
    method_end_count = all_logs.count("[Method END]")
    assert method_start_count >= 3, (
        f"Expected at least 3 [Method START] entries (onCreate, compute, "
        f"handleResult), got {method_start_count}.\n{all_logs}"
    )
    assert method_end_count >= 3, (
        f"Expected at least 3 [Method END] entries, got {method_end_count}.\n"
        f"{all_logs}"
    )

    # Branches: compute() has one if/else, handleResult() has one.
    branch_count = all_logs.count("[Branch:")
    assert branch_count >= 2, (
        f"Expected at least 2 [Branch:] entries, got {branch_count}.\n"
        f"{all_logs}"
    )

    # TAG entries for the cond_ labels
    tag_count = all_logs.count("[TAG:")
    assert tag_count >= 2, (
        f"Expected at least 2 [TAG:] entries, got {tag_count}.\n{all_logs}"
    )

    # ----- 10. Verify method_hash <-> signature correlation ----------------
    # Each log line has [<method_hash>], which we should be able to
    # resolve back to a signature from result.methods.
    hash_pattern = re.compile(r"\[([0-9a-f]{16})\]")
    seen_hashes = set(hash_pattern.findall(all_logs))
    resolved = seen_hashes & set(result.methods.keys())
    assert len(resolved) >= 3, (
        f"Expected at least 3 method hashes in logs to resolve back to the "
        f"method map, got {len(resolved)}. Hashes in logs: {seen_hashes}\n"
        f"Logs:\n{all_logs}"
    )

    # ----- 11. Clean up ----------------------------------------------------
    _adb_maybe(serial, "uninstall", PACKAGE)
