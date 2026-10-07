"""Read a shift plan from CSV (comma or semicolon separated, German or English headers)."""

from __future__ import annotations

import csv
import io
from datetime import datetime, timedelta
from typing import Dict, Iterable, List, Optional, Tuple

from .models import ParseIssue, Shift

_ALIASES = {
    "employee": "employee", "mitarbeiter": "employee", "name": "employee",
    "date": "date", "datum": "date", "day": "date",
    "start": "start", "beginn": "start", "von": "start",
    "end": "end", "ende": "end", "bis": "end",
    "break_minutes": "break_minutes", "break": "break_minutes", "pause": "break_minutes",
    "pause_min": "break_minutes",
    "approved": "approved", "genehmigt": "approved", "sunday_approved": "approved",
}
_TRUE = {"1", "true", "yes", "ja", "y", "j", "x"}
_DATE_FORMATS = ("%Y-%m-%d", "%d.%m.%Y")


def _parse_date(text: str):
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ValueError("unreadable date %r (use YYYY-MM-DD or DD.MM.YYYY)" % text)


def _parse_time(text: str) -> Tuple[int, int]:
    try:
        hh, mm = text.strip().split(":")
        hh, mm = int(hh), int(mm)
    except ValueError:
        raise ValueError("unreadable time %r (use HH:MM)" % text)
    if not (0 <= hh <= 23 and 0 <= mm <= 59):
        raise ValueError("time out of range: %r" % text)
    return hh, mm


def parse_rows(rows: Iterable[Dict[str, str]]) -> Tuple[List[Shift], List[ParseIssue]]:
    """Turn raw CSV rows into shifts. Bad rows become ParseIssues instead of exceptions,
    so one typo does not hide the other 200 rows from the check."""
    shifts: List[Shift] = []
    issues: List[ParseIssue] = []
    for number, raw in enumerate(rows, start=2):  # row 1 is the header, like in a spreadsheet
        row = {}
        for key, value in raw.items():
            if key is None:
                continue
            canonical = _ALIASES.get(key.strip().lower())
            if canonical:
                row[canonical] = (value or "").strip()
        missing = [c for c in ("employee", "date", "start", "end") if not row.get(c)]
        if missing:
            issues.append(ParseIssue(number, "missing value(s): " + ", ".join(missing)))
            continue
        try:
            day = _parse_date(row["date"])
            sh, sm = _parse_time(row["start"])
            eh, em = _parse_time(row["end"])
            start = datetime(day.year, day.month, day.day, sh, sm)
            end = datetime(day.year, day.month, day.day, eh, em)
            if end <= start:  # runs past midnight
                end += timedelta(days=1)
            raw_break = row.get("break_minutes", "") or "0"
            if not raw_break.isdigit():
                raise ValueError("break must be whole minutes, got %r" % raw_break)
            shifts.append(Shift(
                employee=row["employee"], start=start, end=end,
                break_minutes=int(raw_break),
                approved=row.get("approved", "").lower() in _TRUE,
                row=number,
            ))
        except ValueError as exc:
            issues.append(ParseIssue(number, str(exc)))
    return shifts, issues


def parse_text(text: str) -> Tuple[List[Shift], List[ParseIssue]]:
    first_line = text.lstrip("﻿").splitlines()[0] if text.strip() else ""
    delimiter = ";" if first_line.count(";") > first_line.count(",") else ","
    reader = csv.DictReader(io.StringIO(text.lstrip("﻿")), delimiter=delimiter)
    return parse_rows(reader)


def parse_file(path: str) -> Tuple[List[Shift], List[ParseIssue]]:
    with open(path, encoding="utf-8") as handle:
        return parse_text(handle.read())
