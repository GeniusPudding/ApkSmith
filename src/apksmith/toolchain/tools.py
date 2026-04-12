"""Locate and run external tools (apktool / zipalign / apksigner).

Each tool has a ``find_*`` function that resolves its path and a
``run_*`` function that wraps ``subprocess.run`` with proper error
reporting.
"""

from __future__ import annotations

import shutil
import subprocess


class ToolNotFoundError(RuntimeError):
    """Raised when a required external tool cannot be located."""


# ---------------------------------------------------------------------------
# Locators
# ---------------------------------------------------------------------------

def _find(names: list[str], label: str, override: str | None = None) -> str:
    if override:
        return override
    for name in names:
        found = shutil.which(name)
        if found:
            return found
    raise ToolNotFoundError(
        f"Could not find {' or '.join(repr(n) for n in names)} on PATH. "
        f"({label})"
    )


def find_apktool(override: str | None = None) -> str:
    return _find(
        ["apktool", "apktool.bat"], "Install from https://apktool.org", override,
    )


def find_zipalign(override: str | None = None) -> str:
    return _find(
        ["zipalign"], "Ships with Android SDK build-tools", override,
    )


def find_apksigner(override: str | None = None) -> str:
    return _find(
        ["apksigner", "apksigner.bat"], "Ships with Android SDK build-tools", override,
    )


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_tool(cmd: list[str], *, label: str = "") -> subprocess.CompletedProcess[str]:
    """Run *cmd* via ``subprocess.run``, raising on failure with a clear message."""
    display = label or cmd[0]
    print(f"[{display}] $ {' '.join(cmd)}")
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
    except FileNotFoundError as exc:
        raise ToolNotFoundError(
            f"{display}: executable not found ({exc.filename})"
        ) from exc
    except subprocess.CalledProcessError as exc:
        tail_out = (exc.stdout or "").strip()[-2000:]
        tail_err = (exc.stderr or "").strip()[-2000:]
        raise RuntimeError(
            f"{display} failed (exit {exc.returncode})\n"
            f"--- stdout ---\n{tail_out}\n--- stderr ---\n{tail_err}"
        ) from exc
    if proc.stdout:
        print(proc.stdout.rstrip())
    return proc


# ---------------------------------------------------------------------------
# High-level convenience wrappers
# ---------------------------------------------------------------------------

def decompile(
    apktool: str, apk_path: str, output_dir: str,
) -> None:
    """``apktool d`` an APK into *output_dir*."""
    run_tool(
        [apktool, "-rf", "d", "--only-main-classes", apk_path, "-o", output_dir],
        label="apktool d",
    )


def build(apktool: str, apktool_dir: str) -> None:
    """``apktool b`` the unpacked directory back into an APK."""
    run_tool([apktool, "b", apktool_dir], label="apktool b")


def zipalign(zipalign_bin: str, in_apk: str, out_apk: str) -> None:
    run_tool(
        [zipalign_bin, "-f", "-v", "4", in_apk, out_apk], label="zipalign",
    )


def sign(
    apksigner: str,
    in_apk: str,
    out_apk: str,
    *,
    keystore: str,
    ks_pass: str,
    key_pass: str,
    key_alias: str | None = None,
) -> None:
    cmd = [
        apksigner, "sign",
        "--ks", keystore,
        "--ks-pass", "pass:" + ks_pass,
        "--key-pass", "pass:" + key_pass,
        "--out", out_apk,
    ]
    if key_alias:
        cmd += ["--ks-key-alias", key_alias]
    cmd.append(in_apk)
    run_tool(cmd, label="apksigner")
