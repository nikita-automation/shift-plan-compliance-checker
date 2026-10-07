"""Shared test helpers."""

from datetime import datetime, timedelta

from shiftcheck.models import Shift


def make_shift(employee, day, start, end, break_minutes=0, approved=False, row=0):
    """make_shift('Ann', '2026-10-05', '08:00', '16:30', 30) - end <= start means next day."""
    start_dt = datetime.strptime("%s %s" % (day, start), "%Y-%m-%d %H:%M")
    end_dt = datetime.strptime("%s %s" % (day, end), "%Y-%m-%d %H:%M")
    if end_dt <= start_dt:
        end_dt += timedelta(days=1)
    return Shift(employee, start_dt, end_dt, break_minutes, approved, row)


def rules_of(findings):
    return sorted(f.rule for f in findings)
