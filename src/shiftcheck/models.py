"""Data model: shifts, workdays, findings."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import List

SEVERITIES = ("violation", "warning", "info")


@dataclass(frozen=True)
class Shift:
    employee: str
    start: datetime
    end: datetime
    break_minutes: int = 0
    approved: bool = False  # Sunday / holiday work has a documented approval
    row: int = 0  # spreadsheet row in the source file, header = row 1 (for messages)

    @property
    def day(self) -> date:
        """The day the shift starts - the day it is attributed to."""
        return self.start.date()

    @property
    def span_minutes(self) -> int:
        return int((self.end - self.start).total_seconds() // 60)

    @property
    def work_minutes(self) -> int:
        """Working time = span minus unpaid break."""
        return self.span_minutes - self.break_minutes


@dataclass
class Workday:
    """All shifts of one employee that start on the same calendar day.

    Split shifts (e.g. 10:00-14:00 and 18:00-22:00) are treated as one working day:
    the gap between them counts as a break if it is long enough, and no daily rest
    period is required inside the day.
    """

    employee: str
    day: date
    shifts: List[Shift] = field(default_factory=list)

    @property
    def start(self) -> datetime:
        return min(s.start for s in self.shifts)

    @property
    def end(self) -> datetime:
        return max(s.end for s in self.shifts)

    @property
    def work_minutes(self) -> int:
        return sum(s.work_minutes for s in self.shifts)


@dataclass(frozen=True)
class Finding:
    rule: str
    severity: str  # one of SEVERITIES
    employee: str
    day: str  # ISO date, or "" for findings that span the whole plan
    message: str
    reference: str = ""  # e.g. "ArbZG § 3"

    def as_dict(self) -> dict:
        return {
            "rule": self.rule,
            "severity": self.severity,
            "employee": self.employee,
            "day": self.day,
            "message": self.message,
            "reference": self.reference,
        }


@dataclass(frozen=True)
class ParseIssue:
    row: int
    message: str
