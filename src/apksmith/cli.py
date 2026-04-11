"""Thin CLI wrapper so `apksmith ...` works from the shell.

The real orchestration lives in :mod:`apksmith.pipeline`; this module
is just argument parsing and error reporting.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from apksmith import __version__
from apksmith.config import InstrumentConfig
from apksmith.pipeline import instrument_apk


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="apksmith",
        description="Decompile, rewrite, repack, and re-sign an Android APK.",
    )
    parser.add_argument("--version", action="version", version=f"apksmith {__version__}")

    sub = parser.add_subparsers(dest="command", required=True)

    inst = sub.add_parser("instrument", help="Apply transform passes to an APK.")
    inst.add_argument("apk", type=Path, help="Input APK path.")
    inst.add_argument("-o", "--output-dir", type=Path, required=True)
    inst.add_argument("--keystore", type=Path, required=True)
    inst.add_argument("--keystore-pass", required=True)
    inst.add_argument("--key-alias", default=None)
    inst.add_argument("--key-pass", default=None)
    inst.add_argument("--log-tag", default="ApkSmith")
    inst.add_argument(
        "--pass",
        dest="passes",
        action="append",
        default=[],
        help="Transform pass to apply (repeatable). Currently only 'trace_logger'.",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "instrument":
        config = InstrumentConfig(
            keystore=args.keystore,
            keystore_pass=args.keystore_pass,
            key_alias=args.key_alias,
            key_pass=args.key_pass,
            log_tag=args.log_tag,
        )
        try:
            result = instrument_apk(args.apk, args.output_dir, config)
        except NotImplementedError as exc:
            print(f"apksmith: {exc}", file=sys.stderr)
            return 2
        print(f"OK: {result.repacked_apk}")
        return 0

    parser.error(f"unknown command: {args.command}")
    return 2  # unreachable, parser.error exits


if __name__ == "__main__":
    sys.exit(main())
