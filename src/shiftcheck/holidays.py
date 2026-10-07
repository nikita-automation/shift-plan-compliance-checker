"""Public holidays computed from the Easter date - no external data, no network."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Dict

# Nationwide holidays plus the ones that only apply in North Rhine-Westphalia.
_NATIONWIDE = ("new_year", "good_friday", "easter_monday", "labour_day", "ascension",
               "whit_monday", "unity_day", "christmas_1", "christmas_2")
_BY_REGION = {
    "DE": (),
    "NW": ("corpus_christi", "all_saints"),
}


def easter_sunday(year: int) -> date:
    """Gregorian Easter (anonymous algorithm / Meeus-Jones-Butcher)."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month, day = divmod(h + l - 7 * m + 114, 31)
    return date(year, month, day + 1)


def holidays(year: int, region: str = "NW") -> Dict[date, str]:
    """Return {date: name} for the given year. Region is 'DE' (nationwide only) or 'NW'."""
    if region not in _BY_REGION:
        raise ValueError("unknown region %r (supported: %s)" % (region, ", ".join(sorted(_BY_REGION))))
    easter = easter_sunday(year)
    table = {
        "new_year": (date(year, 1, 1), "Neujahr"),
        "good_friday": (easter - timedelta(days=2), "Karfreitag"),
        "easter_monday": (easter + timedelta(days=1), "Ostermontag"),
        "labour_day": (date(year, 5, 1), "Tag der Arbeit"),
        "ascension": (easter + timedelta(days=39), "Christi Himmelfahrt"),
        "whit_monday": (easter + timedelta(days=50), "Pfingstmontag"),
        "corpus_christi": (easter + timedelta(days=60), "Fronleichnam"),
        "unity_day": (date(year, 10, 3), "Tag der Deutschen Einheit"),
        "all_saints": (date(year, 11, 1), "Allerheiligen"),
        "christmas_1": (date(year, 12, 25), "1. Weihnachtstag"),
        "christmas_2": (date(year, 12, 26), "2. Weihnachtstag"),
    }
    keys = _NATIONWIDE + _BY_REGION[region]
    return {table[k][0]: table[k][1] for k in keys}
