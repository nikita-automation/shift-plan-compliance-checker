import json
import os
import tempfile
import unittest
from datetime import date, timedelta

from shiftcheck.rules import Rules, check
from helpers import make_shift, rules_of


def run(*shifts, **overrides):
    return check(list(shifts), Rules(**overrides)).findings


class DailyHoursTests(unittest.TestCase):
    def test_exactly_8_hours_is_clean(self):
        self.assertEqual(run(make_shift("A", "2026-10-06", "08:00", "16:30", 30)), [])

    def test_over_8_is_a_warning_not_a_violation(self):
        findings = run(make_shift("A", "2026-10-06", "08:00", "17:30", 45))   # 8 h 45 net
        self.assertEqual(rules_of(findings), ["DAILY_OVER_8"])
        self.assertEqual(findings[0].severity, "warning")

    def test_exactly_10_hours_is_not_a_violation(self):
        findings = run(make_shift("A", "2026-10-06", "08:00", "18:45", 45))   # 10 h net
        self.assertNotIn("DAILY_MAX", rules_of(findings))

    def test_10_hours_1_minute_is_a_violation(self):
        findings = run(make_shift("A", "2026-10-06", "08:00", "18:46", 45))
        self.assertIn("DAILY_MAX", rules_of(findings))

    def test_split_shifts_are_summed_per_day(self):
        findings = run(make_shift("A", "2026-10-06", "06:00", "12:00", 0),
                       make_shift("A", "2026-10-06", "14:00", "20:30", 30))   # 12 h net
        self.assertIn("DAILY_MAX", rules_of(findings))


class BreakTests(unittest.TestCase):
    def test_up_to_6_hours_needs_no_break(self):
        self.assertEqual(run(make_shift("A", "2026-10-06", "08:00", "14:00", 0)), [])

    def test_6_hours_1_minute_needs_30_minutes(self):
        findings = run(make_shift("A", "2026-10-06", "08:00", "14:01", 0))
        self.assertEqual(rules_of(findings), ["BREAK"])
        self.assertEqual(run(make_shift("A", "2026-10-06", "08:00", "14:31", 30)), [])

    def test_up_to_9_hours_needs_30_minutes(self):
        # 9 h 00 net with 30 min break: allowed, but over 8 h -> only the warning
        findings = run(make_shift("A", "2026-10-06", "08:00", "17:30", 30))
        self.assertEqual(rules_of(findings), ["DAILY_OVER_8"])

    def test_over_9_hours_needs_45_minutes(self):
        findings = run(make_shift("A", "2026-10-06", "08:00", "17:31", 30))   # 9 h 01 net
        self.assertIn("BREAK", rules_of(findings))
        findings = run(make_shift("A", "2026-10-06", "08:00", "17:46", 45))   # 9 h 01 net
        self.assertNotIn("BREAK", rules_of(findings))

    def test_gap_between_split_shifts_counts_as_break(self):
        findings = run(make_shift("A", "2026-10-06", "08:00", "12:00", 0),
                       make_shift("A", "2026-10-06", "15:00", "19:00", 0))   # 8 h net, 3 h gap
        self.assertEqual(findings, [])

    def test_gap_shorter_than_15_minutes_does_not_count(self):
        findings = run(make_shift("A", "2026-10-06", "08:00", "12:00", 0),
                       make_shift("A", "2026-10-06", "12:10", "18:10", 0))   # 10 h net, gap 10 min
        self.assertIn("BREAK", rules_of(findings))


class RestTests(unittest.TestCase):
    def test_exactly_11_hours_is_fine(self):
        findings = run(make_shift("A", "2026-10-06", "14:00", "22:00", 30),
                       make_shift("A", "2026-10-07", "09:00", "13:00", 0))
        self.assertEqual(findings, [])

    def test_10_hours_59_minutes_is_a_violation(self):
        findings = run(make_shift("A", "2026-10-06", "14:00", "22:00", 30),
                       make_shift("A", "2026-10-07", "08:59", "13:00", 0))
        self.assertEqual(rules_of(findings), ["REST"])

    def test_overnight_shift_rest_is_measured_from_its_real_end(self):
        findings = run(make_shift("A", "2026-10-06", "22:00", "06:00", 30),
                       make_shift("A", "2026-10-07", "14:00", "20:00", 0))   # 8 h rest
        self.assertEqual(rules_of(findings), ["REST"])
        self.assertIn("07.10. 06:00", findings[0].message)

    def test_split_shift_inside_one_day_needs_no_rest(self):
        findings = run(make_shift("A", "2026-10-06", "06:00", "10:00", 0),
                       make_shift("A", "2026-10-06", "14:00", "18:00", 0))
        self.assertNotIn("REST", rules_of(findings))

    def test_other_employees_do_not_interfere(self):
        findings = run(make_shift("A", "2026-10-06", "14:00", "22:00", 30),
                       make_shift("B", "2026-10-07", "06:00", "14:00", 30))
        self.assertEqual(findings, [])

    def test_sector_rule_can_shorten_rest(self):
        shifts = [make_shift("A", "2026-10-06", "14:00", "22:00", 30),
                  make_shift("A", "2026-10-07", "08:00", "12:00", 0)]   # 10 h rest
        self.assertEqual(rules_of(check(shifts, Rules()).findings), ["REST"])
        self.assertEqual(check(shifts, Rules(min_rest_hours=10)).findings, [])


class OverlapTests(unittest.TestCase):
    def test_double_booking_is_reported_with_both_rows(self):
        findings = run(make_shift("A", "2026-10-06", "08:00", "12:00", 0, row=2),
                       make_shift("A", "2026-10-06", "11:00", "15:00", 0, row=3))
        overlap = [f for f in findings if f.rule == "OVERLAP"]
        self.assertEqual(len(overlap), 1)
        self.assertIn("rows 2 and 3", overlap[0].message)


class WeeklyTests(unittest.TestCase):
    def test_48_hours_is_fine_49_is_a_warning(self):
        six_days = [make_shift("A", "2026-10-%02d" % d, "08:00", "16:30", 30) for d in range(5, 11)]
        self.assertNotIn("WEEKLY_OVER", rules_of(check(six_days, Rules()).findings))
        six_days[0] = make_shift("A", "2026-10-05", "08:00", "17:30", 30)   # +1 h
        findings = check(six_days, Rules()).findings
        self.assertIn("WEEKLY_OVER", rules_of(findings))

    def test_weeks_are_counted_separately(self):
        shifts = [make_shift("A", "2026-10-%02d" % d, "08:00", "17:30", 30) for d in (5, 6, 7, 8, 9)]
        shifts += [make_shift("A", "2026-10-%02d" % d, "08:00", "17:30", 30) for d in (12, 13, 14, 15, 16)]
        self.assertNotIn("WEEKLY_OVER", rules_of(check(shifts, Rules()).findings))   # 45 h each


class SundayHolidayTests(unittest.TestCase):
    def test_sunday_without_approval_is_a_violation(self):
        findings = run(make_shift("A", "2026-10-11", "10:00", "16:00", 0))
        self.assertEqual(rules_of(findings), ["SUNDAY_HOLIDAY"])

    def test_sunday_with_approval_is_only_a_note(self):
        findings = run(make_shift("A", "2026-10-11", "10:00", "16:00", 0, approved=True))
        self.assertEqual([(f.rule, f.severity) for f in findings], [("SUNDAY_HOLIDAY_OK", "info")])

    def test_saturday_night_shift_touching_sunday_is_flagged_on_sunday(self):
        findings = run(make_shift("A", "2026-10-10", "22:00", "06:00", 30))
        self.assertEqual([(f.rule, f.day) for f in findings], [("SUNDAY_HOLIDAY", "2026-10-11")])

    def test_regional_holiday_depends_on_region(self):
        shift = make_shift("A", "2026-06-04", "08:00", "12:00", 0)   # Fronleichnam, Thursday
        self.assertEqual(rules_of(run(shift, holiday_region="NW")), ["SUNDAY_HOLIDAY"])
        self.assertEqual(run(shift, holiday_region="DE"), [])

    def test_approval_requirement_can_be_switched_off(self):
        shift = make_shift("A", "2026-10-11", "10:00", "16:00", 0)
        self.assertEqual(run(shift, sunday_requires_approval=False), [])


class FreeSundaysTests(unittest.TestCase):
    @staticmethod
    def plan(total_sundays, worked_sundays):
        """Plan spanning exactly `total_sundays` Sundays; employee A works the first `worked_sundays`."""
        first_sunday = date(2026, 10, 11)
        last_sunday = first_sunday + timedelta(days=7 * (total_sundays - 1))
        shifts = [
            # filler for a second employee so the plan starts on Monday 5 Oct and ends the day after the last Sunday
            make_shift("Z", "2026-10-05", "08:00", "12:00", 0),
            make_shift("Z", (last_sunday + timedelta(days=1)).isoformat(), "08:00", "12:00", 0),
        ]
        for index in range(worked_sundays):
            day = (first_sunday + timedelta(days=7 * index)).isoformat()
            shifts.append(make_shift("A", day, "10:00", "14:00", 0, approved=True))
        return shifts

    @staticmethod
    def warned(shifts):
        return "FREE_SUNDAYS" in [f.rule for f in check(shifts, Rules()).findings if f.employee == "A"]

    def test_working_most_sundays_warns(self):
        self.assertTrue(self.warned(self.plan(10, 8)))

    def test_working_a_few_sundays_does_not(self):
        self.assertFalse(self.warned(self.plan(10, 7)))

    def test_threshold_is_exactly_15_free_sundays_per_52(self):
        self.assertFalse(self.warned(self.plan(52, 37)))   # 15 free: still fine
        self.assertTrue(self.warned(self.plan(52, 38)))    # 14 free: warn

    def test_projection_starts_at_8_sundays(self):
        self.assertTrue(self.warned(self.plan(8, 8)))
        self.assertFalse(self.warned(self.plan(7, 7)))


class BoundaryTests(unittest.TestCase):
    def test_break_block_of_exactly_15_minutes_counts(self):
        findings = run(make_shift("A", "2026-10-06", "08:00", "12:00", 0),
                       make_shift("A", "2026-10-06", "12:15", "18:30", 0))
        # 4 h + 6 h 15 = 10 h 15 net needs 45 min; the 15 min gap is too short, but it must be counted
        self.assertIn("BREAK", rules_of(findings))
        self.assertIn("plan has 15 min", [f for f in findings if f.rule == "BREAK"][0].message)

    def test_back_to_back_shifts_do_not_overlap(self):
        findings = run(make_shift("A", "2026-10-06", "08:00", "12:00", 0),
                       make_shift("A", "2026-10-06", "12:00", "14:00", 0))
        self.assertNotIn("OVERLAP", rules_of(findings))


class RulesConfigTests(unittest.TestCase):
    def test_load_and_reject_unknown_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            good = os.path.join(tmp, "good.json")
            with open(good, "w") as handle:
                json.dump({"min_rest_hours": 10, "break_thresholds": [[9, 45], [6, 30]]}, handle)
            self.assertEqual(Rules.from_file(good).min_rest_hours, 10)
            bad = os.path.join(tmp, "bad.json")
            with open(bad, "w") as handle:
                json.dump({"min_rest_hourz": 10}, handle)
            with self.assertRaises(ValueError):
                Rules.from_file(bad)

    def test_default_json_matches_dataclass_defaults(self):
        here = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(here, "..", "rules.default.json")
        loaded = Rules.from_file(path)
        self.assertEqual(loaded, Rules())


if __name__ == "__main__":
    unittest.main()
