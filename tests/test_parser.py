import unittest
from datetime import datetime

from shiftcheck.parser import parse_text


class ParserTests(unittest.TestCase):
    def test_english_comma_file(self):
        shifts, issues = parse_text(
            "employee,date,start,end,break_minutes,approved\n"
            "Ann,2026-10-05,08:00,16:30,30,\n")
        self.assertEqual(issues, [])
        self.assertEqual(len(shifts), 1)
        self.assertEqual(shifts[0].work_minutes, 8 * 60)
        self.assertFalse(shifts[0].approved)

    def test_german_semicolon_file_with_bom(self):
        shifts, issues = parse_text(
            "﻿Mitarbeiter;Datum;Beginn;Ende;Pause;Genehmigt\n"
            "Ann;05.10.2026;08:00;16:30;30;ja\n")
        self.assertEqual(issues, [])
        self.assertEqual(shifts[0].start, datetime(2026, 10, 5, 8, 0))
        self.assertTrue(shifts[0].approved)

    def test_overnight_shift_ends_next_day(self):
        shifts, _ = parse_text("employee,date,start,end,break_minutes\nAnn,2026-10-05,22:00,06:00,30\n")
        self.assertEqual(shifts[0].end, datetime(2026, 10, 6, 6, 0))
        self.assertEqual(shifts[0].work_minutes, 7 * 60 + 30)

    def test_bad_rows_become_issues_with_spreadsheet_row_numbers(self):
        shifts, issues = parse_text(
            "employee,date,start,end,break_minutes\n"
            "Ann,2026-10-05,08:00,16:30,30\n"
            "Ben,2026-10-05,25:00,16:30,30\n"
            "Cem,not-a-date,08:00,16:30,30\n"
            "Dee,2026-10-05,08:00,16:30,half an hour\n"
            ",2026-10-05,08:00,16:30,30\n")
        self.assertEqual(len(shifts), 1)
        self.assertEqual([i.row for i in issues], [3, 4, 5, 6])
        self.assertIn("out of range", issues[0].message)
        self.assertIn("unreadable date", issues[1].message)
        self.assertIn("whole minutes", issues[2].message)
        self.assertIn("missing", issues[3].message)

    def test_break_defaults_to_zero(self):
        shifts, issues = parse_text("employee,date,start,end\nAnn,2026-10-05,08:00,12:00\n")
        self.assertEqual(issues, [])
        self.assertEqual(shifts[0].break_minutes, 0)

    def test_empty_file(self):
        self.assertEqual(parse_text(""), ([], []))


if __name__ == "__main__":
    unittest.main()
