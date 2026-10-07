"""Command line interface: `python -m shiftcheck ...`"""

from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from . import __version__
from .holidays import holidays
from .parser import parse_file
from .report import RENDERERS
from .rules import Rules, check


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="shiftcheck", description=__doc__)
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)

    chk = sub.add_parser("check", help="check a shift plan CSV")
    chk.add_argument("plan", help="CSV with columns employee,date,start,end,break_minutes[,approved]")
    chk.add_argument("--rules", help="JSON file overriding the default limits (see rules.default.json)")
    chk.add_argument("--region", choices=("NW", "DE"), help="holiday calendar (default: from rules, NW)")
    chk.add_argument("--format", choices=sorted(RENDERERS), default="text")
    chk.add_argument("--fail-on", choices=("violation", "warning", "never"), default="violation",
                     help="exit with status 1 when findings of this severity (or worse) exist")

    hol = sub.add_parser("holidays", help="print the public holidays of a year")
    hol.add_argument("year", type=int)
    hol.add_argument("--region", choices=("NW", "DE"), default="NW")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.command == "holidays":
        for day, name in sorted(holidays(args.year, args.region).items()):
            print("%s  %s  %s" % (day.isoformat(), day.strftime("%a"), name))
        return 0

    rules = Rules.from_file(args.rules) if args.rules else Rules()
    if args.region:
        rules.holiday_region = args.region
    shifts, issues = parse_file(args.plan)
    report = check(shifts, rules, issues)
    sys.stdout.write(RENDERERS[args.format](report))

    if args.fail_on == "never":
        return 0
    if report.issues or report.count("violation"):
        return 1
    if args.fail_on == "warning" and report.count("warning"):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
