"""The checks. Each rule is a small function: (workdays/shifts, config) -> findings.

The limits are modelled on the German Arbeitszeitgesetz (ArbZG). They are a starting point
for *plausibility checks*, not legal advice: collective agreements, sector exceptions
(ArbZG § 10) and averaging periods are deliberately out of scope - see docs/RULES.md.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Sequence, Tuple

from .holidays import holidays
from .models import Finding, ParseIssue, Shift, Workday


@dataclass
class Rules:
    max_daily_hours_hard: float = 10.0      # ArbZG § 3: never more than 10 h
    max_daily_hours_soft: float = 8.0       # ArbZG § 3: > 8 h only with averaging
    # (hours worked "over", minimum break in minutes) - checked from the top down
    break_thresholds: List[Tuple[float, int]] = field(default_factory=lambda: [(9.0, 45), (6.0, 30)])
    min_break_block_minutes: int = 15       # ArbZG § 4: only blocks of >= 15 min count as break
    min_rest_hours: float = 11.0            # ArbZG § 5
    max_weekly_hours: float = 48.0          # 6 x 8 h; averaging allowed -> warning only
    sunday_requires_approval: bool = True   # ArbZG § 9
    holiday_requires_approval: bool = True
    holiday_region: str = "NW"
    min_free_sundays_per_year: int = 15     # ArbZG § 11
    min_sundays_for_projection: int = 8     # need at least this many Sundays in the plan

    @classmethod
    def from_file(cls, path: str) -> "Rules":
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        if "break_thresholds" in data:
            data["break_thresholds"] = [tuple(item) for item in data["break_thresholds"]]
        unknown = set(data) - set(cls.__dataclass_fields__)
        if unknown:
            raise ValueError("unknown rule setting(s): " + ", ".join(sorted(unknown)))
        return cls(**data)


def group_workdays(shifts: Sequence[Shift]) -> List[Workday]:
    grouped: Dict[Tuple[str, date], Workday] = {}
    for shift in sorted(shifts, key=lambda s: (s.employee, s.start)):
        key = (shift.employee, shift.day)
        grouped.setdefault(key, Workday(shift.employee, shift.day)).shifts.append(shift)
    return sorted(grouped.values(), key=lambda w: (w.employee, w.day))


def _hours(minutes: float) -> str:
    """Format minutes as '9 h 15 min' (or '8 h')."""
    hours, rest = divmod(int(round(minutes)), 60)
    return "%d h %d min" % (hours, rest) if rest else "%d h" % hours


# --- individual rules ---------------------------------------------------------------

def check_daily_hours(workdays: Sequence[Workday], rules: Rules) -> List[Finding]:
    out = []
    for wd in workdays:
        hours = wd.work_minutes / 60.0
        if hours > rules.max_daily_hours_hard:
            out.append(Finding(
                "DAILY_MAX", "violation", wd.employee, wd.day.isoformat(),
                "%s worked - above the absolute limit of %s per day"
                % (_hours(wd.work_minutes), _hours(rules.max_daily_hours_hard * 60)),
                "ArbZG § 3"))
        elif hours > rules.max_daily_hours_soft:
            out.append(Finding(
                "DAILY_OVER_8", "warning", wd.employee, wd.day.isoformat(),
                "%s worked - allowed only if the average stays at %s per working day "
                "within 6 months / 24 weeks (check the time account)"
                % (_hours(wd.work_minutes), _hours(rules.max_daily_hours_soft * 60)),
                "ArbZG § 3"))
    return out


def _required_break(work_minutes: int, rules: Rules) -> int:
    for over_hours, minutes in sorted(rules.break_thresholds, reverse=True):
        if work_minutes > over_hours * 60:
            return minutes
    return 0


def _available_break(wd: Workday, rules: Rules) -> int:
    """Planned breaks plus long-enough gaps between split shifts."""
    total = sum(s.break_minutes for s in wd.shifts)
    ordered = sorted(wd.shifts, key=lambda s: s.start)
    for earlier, later in zip(ordered, ordered[1:]):
        gap = int((later.start - earlier.end).total_seconds() // 60)
        if gap >= rules.min_break_block_minutes:
            total += gap
    return total


def check_breaks(workdays: Sequence[Workday], rules: Rules) -> List[Finding]:
    out = []
    for wd in workdays:
        needed = _required_break(wd.work_minutes, rules)
        have = _available_break(wd, rules)
        if needed and have < needed:
            out.append(Finding(
                "BREAK", "violation", wd.employee, wd.day.isoformat(),
                "%s worked needs a break of at least %d min, plan has %d min"
                % (_hours(wd.work_minutes), needed, have),
                "ArbZG § 4"))
    return out


def check_rest(workdays: Sequence[Workday], rules: Rules) -> List[Finding]:
    out = []
    by_employee: Dict[str, List[Workday]] = defaultdict(list)
    for wd in workdays:
        by_employee[wd.employee].append(wd)
    for employee, days in by_employee.items():
        days.sort(key=lambda w: w.start)
        for earlier, later in zip(days, days[1:]):
            gap = later.start - earlier.end
            if gap < timedelta(0):
                continue  # overlapping shifts are reported by check_overlaps
            if gap < timedelta(hours=rules.min_rest_hours):
                out.append(Finding(
                    "REST", "violation", employee, later.day.isoformat(),
                    "only %s of rest between shift end (%s) and next shift start (%s) - "
                    "%s uninterrupted rest required"
                    % (_hours(gap.total_seconds() / 60), earlier.end.strftime("%d.%m. %H:%M"),
                       later.start.strftime("%d.%m. %H:%M"), _hours(rules.min_rest_hours * 60)),
                    "ArbZG § 5"))
    return out


def check_overlaps(shifts: Sequence[Shift]) -> List[Finding]:
    out = []
    by_employee: Dict[str, List[Shift]] = defaultdict(list)
    for shift in shifts:
        by_employee[shift.employee].append(shift)
    for employee, items in by_employee.items():
        items.sort(key=lambda s: s.start)
        for earlier, later in zip(items, items[1:]):
            if later.start < earlier.end:
                out.append(Finding(
                    "OVERLAP", "violation", employee, later.day.isoformat(),
                    "shift %s-%s overlaps the shift starting %s (rows %d and %d)"
                    % (later.start.strftime("%H:%M"), later.end.strftime("%H:%M"),
                       earlier.start.strftime("%d.%m. %H:%M"), earlier.row, later.row),
                    "data quality"))
    return out


def check_weekly_hours(workdays: Sequence[Workday], rules: Rules) -> List[Finding]:
    totals: Dict[Tuple[str, Tuple[int, int]], int] = defaultdict(int)
    first_day: Dict[Tuple[str, Tuple[int, int]], date] = {}
    for wd in workdays:
        iso = wd.day.isocalendar()
        key = (wd.employee, (iso[0], iso[1]))
        totals[key] += wd.work_minutes
        first_day.setdefault(key, wd.day)
    out = []
    for (employee, (year, week)), minutes in sorted(totals.items()):
        if minutes > rules.max_weekly_hours * 60:
            out.append(Finding(
                "WEEKLY_OVER", "warning", employee, first_day[(employee, (year, week))].isoformat(),
                "%s in calendar week %d/%d - above %s (6 x 8 h); fine only with averaging"
                % (_hours(minutes), week, year, _hours(rules.max_weekly_hours * 60)),
                "ArbZG § 3"))
    return out


def _days_touched(shift: Shift):
    """Yield every calendar date a shift touches, with the minutes worked on that date."""
    cursor = shift.start
    while cursor < shift.end:
        midnight = datetime(cursor.year, cursor.month, cursor.day) + timedelta(days=1)
        stop = min(midnight, shift.end)
        yield cursor.date(), int((stop - cursor).total_seconds() // 60)
        cursor = stop


def check_sunday_holiday(shifts: Sequence[Shift], rules: Rules) -> List[Finding]:
    out = []
    holiday_cache: Dict[int, Dict[date, str]] = {}

    def holiday_name(day: date) -> Optional[str]:
        if day.year not in holiday_cache:
            holiday_cache[day.year] = holidays(day.year, rules.holiday_region)
        return holiday_cache[day.year].get(day)

    for shift in shifts:
        for day, _minutes in _days_touched(shift):
            kind = None
            if day.weekday() == 6:
                kind = "Sunday"
            name = holiday_name(day)
            if name:
                kind = "public holiday (%s)" % name
            if not kind:
                continue
            needs_approval = rules.holiday_requires_approval if name else rules.sunday_requires_approval
            if not needs_approval:
                continue
            if shift.approved:
                out.append(Finding(
                    "SUNDAY_HOLIDAY_OK", "info", shift.employee, day.isoformat(),
                    "works on %s with documented approval - compensatory rest day required "
                    "within 2 weeks (Sunday) / 8 weeks (holiday)" % kind,
                    "ArbZG § 11"))
            else:
                out.append(Finding(
                    "SUNDAY_HOLIDAY", "violation", shift.employee, day.isoformat(),
                    "works on %s without a documented exception (sector rule or approval)" % kind,
                    "ArbZG § 9, § 10"))
    return out


def check_free_sundays(shifts: Sequence[Shift], rules: Rules) -> List[Finding]:
    if not shifts:
        return []
    first = min(s.start.date() for s in shifts)
    last = max(s.end.date() for s in shifts)
    sundays = []
    cursor = first + timedelta(days=(6 - first.weekday()) % 7)
    while cursor <= last:
        sundays.append(cursor)
        cursor += timedelta(days=7)
    if len(sundays) < rules.min_sundays_for_projection:
        return []
    worked: Dict[str, set] = defaultdict(set)
    for shift in shifts:
        for day, _ in _days_touched(shift):
            if day.weekday() == 6:
                worked[shift.employee].add(day)
    allowed_share = (52 - rules.min_free_sundays_per_year) / 52.0
    out = []
    for employee, days in sorted(worked.items()):
        share = len(days) / float(len(sundays))
        if share > allowed_share:
            out.append(Finding(
                "FREE_SUNDAYS", "warning", employee, "",
                "works %d of %d Sundays in the plan - projected to fall below %d free Sundays per year"
                % (len(days), len(sundays), rules.min_free_sundays_per_year),
                "ArbZG § 11"))
    return out


# --- orchestration ------------------------------------------------------------------

@dataclass
class Report:
    findings: List[Finding]
    issues: List[ParseIssue]
    shifts: int
    employees: int

    def count(self, severity: str) -> int:
        return sum(1 for f in self.findings if f.severity == severity)


def check(shifts: Sequence[Shift], rules: Optional[Rules] = None,
          issues: Optional[Sequence[ParseIssue]] = None) -> Report:
    rules = rules or Rules()
    workdays = group_workdays(shifts)
    findings: List[Finding] = []
    findings += check_daily_hours(workdays, rules)
    findings += check_breaks(workdays, rules)
    findings += check_rest(workdays, rules)
    findings += check_overlaps(shifts)
    findings += check_weekly_hours(workdays, rules)
    findings += check_sunday_holiday(shifts, rules)
    findings += check_free_sundays(shifts, rules)
    order = {"violation": 0, "warning": 1, "info": 2}
    findings.sort(key=lambda f: (order[f.severity], f.employee, f.day, f.rule))
    return Report(findings, list(issues or []), len(shifts), len({s.employee for s in shifts}))
