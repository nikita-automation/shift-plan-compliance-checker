"""End-to-end: the committed sample plan must produce exactly the findings we planted in it."""

import contextlib
import io
import json
import os
import unittest

from shiftcheck.cli import main
from shiftcheck.parser import parse_file
from shiftcheck.rules import Rules, check

SAMPLE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "sample", "shift_plan.csv")

EXPECTED = {
    ("violation", "BREAK", "Anna Beispiel", "2026-10-06"),
    ("violation", "DAILY_MAX", "Anna Beispiel", "2026-10-06"),
    ("violation", "REST", "Ben Muster", "2026-10-08"),
    ("violation", "SUNDAY_HOLIDAY", "Ben Muster", "2026-11-01"),
    ("violation", "SUNDAY_HOLIDAY", "Clara Probe", "2026-10-11"),
    ("violation", "OVERLAP", "Felix Fiktiv", "2026-10-12"),
    ("violation", "REST", "Felix Fiktiv", "2026-10-22"),
    ("warning", "DAILY_OVER_8", "Elif Testfrau", "2026-10-09"),
    ("warning", "DAILY_OVER_8", "Elif Testfrau", "2026-10-12"),
    ("warning", "DAILY_OVER_8", "Elif Testfrau", "2026-10-13"),
    ("warning", "DAILY_OVER_8", "Elif Testfrau", "2026-10-14"),
    ("warning", "DAILY_OVER_8", "Elif Testfrau", "2026-10-15"),
    ("warning", "DAILY_OVER_8", "Elif Testfrau", "2026-10-16"),
    ("warning", "WEEKLY_OVER", "Elif Testfrau", "2026-10-12"),
    ("warning", "DAILY_OVER_8", "Felix Fiktiv", "2026-10-12"),
    ("info", "SUNDAY_HOLIDAY_OK", "Anna Beispiel", "2026-11-01"),
    ("info", "SUNDAY_HOLIDAY_OK", "Clara Probe", "2026-10-25"),
    ("info", "SUNDAY_HOLIDAY_OK", "David Demo", "2026-10-18"),
}


def run_cli(*args):
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        code = main(list(args))
    return code, buffer.getvalue()


class SampleTests(unittest.TestCase):
    def test_sample_findings_are_exactly_the_planted_ones(self):
        shifts, issues = parse_file(SAMPLE)
        report = check(shifts, Rules(), issues)
        found = {(f.severity, f.rule, f.employee, f.day) for f in report.findings}
        self.assertEqual(found, EXPECTED)
        self.assertEqual(len(report.findings), len(EXPECTED))   # no duplicates
        self.assertEqual([(i.row, "out of range" in i.message) for i in report.issues], [(38, True)])

    def test_clean_shifts_produce_no_findings(self):
        shifts, _ = parse_file(SAMPLE)
        flagged = {(f.employee, f.day) for f in check(shifts, Rules()).findings}
        # Felix's split shift on 5 Oct and David's regular late shifts are fine
        self.assertNotIn(("Felix Fiktiv", "2026-10-05"), flagged)
        self.assertFalse([k for k in flagged if k[0] == "David Demo" and k[1] != "2026-10-18"])


class CliTests(unittest.TestCase):
    def test_text_report_and_exit_code(self):
        code, out = run_cli("check", SAMPLE)
        self.assertEqual(code, 1)
        self.assertIn("7 violation(s), 8 warning(s), 3 note(s), 1 unreadable row(s)", out)

    def test_json_report_is_machine_readable(self):
        code, out = run_cli("check", SAMPLE, "--format", "json", "--fail-on", "never")
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertEqual(data["summary"]["violations"], 7)
        self.assertEqual(len(data["findings"]), len(EXPECTED))
        self.assertEqual(data["unreadable_rows"][0]["row"], 38)

    def test_markdown_report_has_tables(self):
        _, out = run_cli("check", SAMPLE, "--format", "md", "--fail-on", "never")
        self.assertIn("## Violations", out)
        self.assertIn("| Anna Beispiel | 2026-10-06 | DAILY_MAX |", out)

    def test_region_option_changes_the_holiday_finding(self):
        _, out = run_cli("check", SAMPLE, "--region", "DE", "--format", "json", "--fail-on", "never")
        messages = [f["message"] for f in json.loads(out)["findings"] if f["employee"] == "Ben Muster"
                    and f["rule"] == "SUNDAY_HOLIDAY"]
        self.assertEqual(len(messages), 1)
        self.assertIn("Sunday", messages[0])
        self.assertNotIn("Allerheiligen", messages[0])

    def test_holidays_command(self):
        code, out = run_cli("holidays", "2026")
        self.assertEqual(code, 0)
        self.assertIn("2026-04-03  Fri  Karfreitag", out)


if __name__ == "__main__":
    unittest.main()
