"""Command-line interface: osp-gdb-validate <gdb> --schema <yaml>."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .schema import load_schema
from .validator import validate


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="osp-gdb-validate",
        description="Validate a file geodatabase against a YAML schema "
                    "definition (fields, types, domains, uniqueness, typos).")
    p.add_argument("gdb", help="path to the .gdb directory")
    p.add_argument("--schema", "-s", required=True,
                   help="path to the schema YAML")
    p.add_argument("--json", metavar="PATH",
                   help="also write the full report as JSON to PATH")
    p.add_argument("--quiet", "-q", action="store_true",
                   help="suppress the text report; exit code only")
    args = p.parse_args(argv)

    if not Path(args.gdb).exists():
        print(f"error: GDB not found: {args.gdb}", file=sys.stderr)
        return 2

    schema = load_schema(args.schema)
    report = validate(args.gdb, schema)

    if not args.quiet:
        print(report.to_text())
    if args.json:
        Path(args.json).write_text(report.to_json(), encoding="utf-8")
        if not args.quiet:
            print(f"JSON report written to {args.json}")

    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
