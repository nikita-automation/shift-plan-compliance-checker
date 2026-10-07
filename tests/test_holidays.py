import unittest
from datetime import date

from shiftcheck.holidays import easter_sunday, holidays


class EasterTests(unittest.TestCase):
    def test_known_easter_dates(self):
        self.assertEqual(easter_sunday(2024), date(2024, 3, 31))
        self.assertEqual(easter_sunday(2025), date(2025, 4, 20))
        self.assertEqual(easter_sunday(2026), date(2026, 4, 5))
        self.assertEqual(easter_sunday(2027), date(2027, 3, 28))


class HolidayTests(unittest.TestCase):
    def test_moveable_holidays_2026(self):
        table = holidays(2026, "NW")
        self.assertEqual(table[date(2026, 4, 3)], "Karfreitag")
        self.assertEqual(table[date(2026, 4, 6)], "Ostermontag")
        self.assertEqual(table[date(2026, 5, 14)], "Christi Himmelfahrt")
        self.assertEqual(table[date(2026, 5, 25)], "Pfingstmontag")
        self.assertEqual(table[date(2026, 6, 4)], "Fronleichnam")

    def test_region_specific_days(self):
        nw = holidays(2026, "NW")
        de = holidays(2026, "DE")
        self.assertIn(date(2026, 11, 1), nw)       # Allerheiligen
        self.assertNotIn(date(2026, 11, 1), de)
        self.assertEqual(len(nw) - len(de), 2)
        self.assertIn(date(2026, 10, 3), de)       # nationwide

    def test_unknown_region_is_rejected(self):
        with self.assertRaises(ValueError):
            holidays(2026, "XX")


if __name__ == "__main__":
    unittest.main()
