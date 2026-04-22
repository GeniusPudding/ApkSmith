"""ApkSmith command-line interface.

Usage::

    apksmith doctor                          # check prerequisites
    apksmith pull <package> -o <dir>         # pull APK from device
    apksmith instrument <apk> -o <dir> ...   # rewrite smali + repack + sign
    apksmith install <apk>                   # install APK to device

Every subcommand supports ``--help`` for full option docs.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from apksmith import __version__

# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="apksmith",
        description=(
            "Mod any Android app without its source code.\n\n"
            "ApkSmith decompiles an APK, rewrites its smali bytecode with\n"
            "one or more transform passes, then repacks, re-signs, and\n"
            "optionally reinstalls the result."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  apksmith doctor\n"
            "  apksmith pull com.example.app -o ./pulled\n"
            "  apksmith instrument app.apk -o out/"
            " --keystore dev.keystore --keystore-pass changeit\n"
            "  apksmith install out/repacked_app.apk\n"
            "\n"
            "Run 'apksmith <command> --help' for command-specific options."
        ),
    )
    parser.add_argument("--version", action="version", version=f"apksmith {__version__}")

    sub = parser.add_subparsers(dest="command", required=True, metavar="command")

    # --- doctor --------------------------------------------------------------
    sub.add_parser(
        "doctor",
        help="Check that all required tools are installed and reachable.",
        description=(
            "Scan PATH for every tool ApkSmith needs (apktool, adb, zipalign,\n"
            "apksigner, Java, etc.) and print a status table. No device\n"
            "connection is required, but if a device is connected its serial\n"
            "will be shown."
        ),
    )

    # --- pull ----------------------------------------------------------------
    p_pull = sub.add_parser(
        "pull",
        help="Pull an installed app's APK from a connected Android device.",
        description=(
            "Extract the APK file(s) for the given package name from a\n"
            "connected device using adb. For apps with split APKs (common\n"
            "for Play Store installs), all splits are pulled.\n\n"
            "Requires: adb on PATH, one device connected (or use -d)."
        ),
    )
    p_pull.add_argument("package", help="Android package name (e.g. com.example.app)")
    p_pull.add_argument("-o", "--output-dir", type=Path, default=Path("."),
                        help="Directory to save pulled APK(s). Default: current dir.")
    p_pull.add_argument("-d", "--device", default=None, metavar="SERIAL",
                        help="Device serial (from 'adb devices'). Auto-selects if only one device.")

    # --- instrument ----------------------------------------------------------
    p_inst = sub.add_parser(
        "instrument",
        help="Decompile an APK, apply transform passes, repack and re-sign.",
        description=(
            "The core pipeline: decompile the APK with apktool, walk every\n"
            "smali file, apply the requested transform pass(es), patch in\n"
            "the runtime helper class, rebuild with apktool, zipalign, and\n"
            "sign with your keystore.\n\n"
            "No device connection is needed — this operates on a local APK file.\n\n"
            "Requires: apktool, zipalign, apksigner on PATH (or via options)."
        ),
    )
    p_inst.add_argument("apk", type=Path, help="Input APK file.")
    p_inst.add_argument("-o", "--output-dir", type=Path, required=True,
                        help="Directory for output files (created if missing).")
    p_inst.add_argument("--keystore", type=Path, required=True,
                        help="Path to your Java keystore (.keystore / .jks).")
    p_inst.add_argument("--keystore-pass", required=True,
                        help="Keystore password.")
    p_inst.add_argument("--key-alias", default=None,
                        help="Key alias inside the keystore (optional if keystore has one key).")
    p_inst.add_argument("--key-pass", default=None,
                        help="Key password. Defaults to keystore password if omitted.")
    p_inst.add_argument("--log-tag", default="ApkSmith",
                        help="Logcat tag for injected Log.d calls. Default: ApkSmith")
    p_inst.add_argument("--target-api-graph", type=Path, default=None,
                        help="JSON file with the target API trie (optional).")
    p_inst.add_argument("--pass", dest="passes", action="append", default=[],
                        help="Transform pass to apply (repeatable). Default: trace_logger.")

    # --- install -------------------------------------------------------------
    p_install = sub.add_parser(
        "install",
        help="Install a (repacked) APK to a connected Android device.",
        description=(
            "Install an APK to a connected device using adb. If the app is\n"
            "already installed with a different signature (which is always\n"
            "the case for repacked APKs), the old version is automatically\n"
            "uninstalled first.\n\n"
            "WARNING: uninstalling removes the app's data (logins, settings,\n"
            "saved files). This is unavoidable because Android rejects\n"
            "signature-mismatched updates.\n\n"
            "Requires: adb on PATH, one device connected (or use -d)."
        ),
    )
    p_install.add_argument("apk", type=Path, nargs="+",
                           help="APK file(s) to install. Pass multiple files for split APKs.")
    p_install.add_argument("-d", "--device", default=None, metavar="SERIAL",
                           help="Device serial. Auto-selects if only one device.")
    p_install.add_argument("--no-uninstall", action="store_true",
                           help=(
                               "Skip automatic uninstall of the old version"
                               " (will fail if signatures differ)."
                           ))

    return parser


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

def _cmd_doctor() -> int:
    from apksmith.doctor import run_doctor
    return run_doctor()


def _cmd_pull(args: argparse.Namespace) -> int:
    from apksmith.toolchain.adb import pull_apk

    paths = pull_apk(
        args.package, args.output_dir, serial=args.device,
    )
    print(f"\nPulled {len(paths)} file(s):")
    for p in paths:
        print(f"  {p}")
    if len(paths) == 1:
        print(
            f"\nNext step:\n  apksmith instrument {paths[0]}"
            " -o out/ --keystore <your.keystore> --keystore-pass <pass>"
        )
    return 0


def _cmd_instrument(args: argparse.Namespace) -> int:
    from apksmith.config import InstrumentConfig
    from apksmith.pipeline import instrument_apk

    target_api_graph = {}
    if args.target_api_graph:
        with open(args.target_api_graph) as f:
            target_api_graph = json.load(f)

    config = InstrumentConfig(
        keystore=args.keystore,
        keystore_pass=args.keystore_pass,
        key_alias=args.key_alias,
        key_pass=args.key_pass,
        log_tag=args.log_tag,
        target_api_graph=target_api_graph,
    )

    result = instrument_apk(args.apk, args.output_dir, config)

    print(f"\nDone: {result.repacked_apk}")
    print(f"  app hash:        {result.app_hash}")
    print(f"  methods patched: {result.stats.methods_patched}")
    print(f"\nNext step:\n  apksmith install {result.repacked_apk}")
    return 0


def _cmd_install(args: argparse.Namespace) -> int:
    from apksmith.toolchain.adb import (
        get_package_name_from_apk,
        install_apk,
        require_device,
        uninstall_package,
    )

    serial = require_device(args.device)

    # Try to detect the package name so we can uninstall the old version
    if not args.no_uninstall:
        pkg = get_package_name_from_apk(args.apk[0])
        if pkg:
            print(f"Detected package: {pkg}")
            print("Uninstalling old version (app data will be lost)...")
            uninstall_package(pkg, serial=serial)
        else:
            print("Could not detect package name from APK (aapt/aapt2 not found).")
            print("Skipping auto-uninstall. Install may fail if signatures differ.")

    install_apk(args.apk, serial=serial)
    print("\nApp installed successfully.")
    return 0


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "doctor":
            return _cmd_doctor()
        elif args.command == "pull":
            return _cmd_pull(args)
        elif args.command == "instrument":
            return _cmd_instrument(args)
        elif args.command == "install":
            return _cmd_install(args)
    except Exception as exc:
        print(f"apksmith: error: {exc}", file=sys.stderr)
        return 1

    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
