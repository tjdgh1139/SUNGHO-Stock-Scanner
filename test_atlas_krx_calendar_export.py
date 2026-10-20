import unittest
from datetime import datetime,timezone
from atlas_krx_calendar_export import build_calendar

class FakeCalendar:
    def sessions_in_range(self,start,end):
        from datetime import date
        return [type("Day",(),{"date":lambda self,d=d:d})() for d in
                (date(2026,10,20),date(2026,10,21))]

class ExportTests(unittest.TestCase):
    def test_short_horizon_and_dates(self):
        r=build_calendar(now_utc=datetime(2026,10,20,1,tzinfo=timezone.utc),
                         horizon_days=2,calendar=FakeCalendar())
        self.assertEqual(r["verified_open_dates"],["2026-10-20","2026-10-21"])
        self.assertEqual(r["market"],"KRX")
    def test_invalid_horizon(self):
        with self.assertRaises(ValueError):
            build_calendar(horizon_days=100,calendar=FakeCalendar())

if __name__=="__main__":
    unittest.main()
