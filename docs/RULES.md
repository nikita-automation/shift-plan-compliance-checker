# Rules in detail

The checks follow the structure of the German *Arbeitszeitgesetz* (ArbZG). This document says exactly what is
modelled so nobody mistakes the tool for more than it is. **It is not legal advice**; for a binding answer ask
your works council, employment lawyer or the competent labour inspectorate.

## Modelled

| ArbZG | Content | How the tool applies it |
|---|---|---|
| § 3 | Working time may not exceed 8 h a day; up to 10 h if the average over 6 months / 24 weeks stays at 8 h | `> 10 h` → `DAILY_MAX` (violation). `> 8 h` → `DAILY_OVER_8` (warning: the tool cannot see the time account). Weekly: `> 48 h` → `WEEKLY_OVER` (warning) |
| § 4 | Breaks of 30 min (> 6 h up to 9 h) and 45 min (> 9 h); a break counts in blocks of at least 15 min | `BREAK`. Working time = shift length minus the planned break. Gaps of ≥ 15 min between split shifts of one day count as break |
| § 5 | 11 h uninterrupted rest after the end of daily work | `REST`, measured from the real end of the previous working day (overnight shifts included). Configurable (`min_rest_hours`) because some sectors may shorten it with compensation |
| § 9 | Sunday and public-holiday rest (0–24 h) | `SUNDAY_HOLIDAY` unless the shift is marked `approved`. Every calendar day a shift touches counts, so Saturday-night shifts are flagged on the Sunday |
| § 10 | Sector exceptions (hospitals, hotels and restaurants, …) | Not decided by the tool — it asks for a documented approval per shift instead |
| § 11 | At least 15 Sundays a year free; compensatory day off (2 weeks for Sundays, 8 weeks for holidays) | `FREE_SUNDAYS` projects the share of worked Sundays in the plan (needs at least 8 Sundays). Approved work yields a reminder note |

Additional data-quality check: `OVERLAP` (the same person booked twice at the same time).

## Conventions

- A shift belongs to the day it **starts**.
- Shifts of one person that start on the same day form one **working day**; hours and breaks are evaluated per
  working day, rest only *between* working days.
- All times are naive local times; daylight-saving changes are not modelled.
- Public holidays: Easter-based calculation for the nationwide days; `NW` additionally has Corpus Christi
  (*Fronleichnam*) and All Saints' Day (*Allerheiligen*).

## Deliberately not modelled

- Collective agreements and works agreements that deviate from the statute.
- Averaging periods (needs time-account data, not a plan).
- Night-work limits (§ 6), young workers (JArbSchG), maternity protection (MuSchG), part-time contracts.
- *When* in the shift the break is taken (only its length is known).
- Regional holiday calendars beyond `NW` and `DE`.

## Adding a rule

A rule is a function `(workdays | shifts, Rules) -> list[Finding]` in `src/shiftcheck/rules.py`, registered in
`check()`. Give it a stable `rule` id, a severity, a human message and a `reference`, then add boundary tests
(`tests/test_rules.py`) — and flip each comparison once to prove the tests notice.
