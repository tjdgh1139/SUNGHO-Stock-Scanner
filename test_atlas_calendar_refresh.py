import json
import tempfile
import unittest
from datetime import datetime,timezone,date
from pathlib import Path
from atlas_calendar_refresh import refresh_calendar

class FakeCalendar:
    def sessions_in_range(self,start,end):
        return [type("Day",(),{"date":lambda self:date(2026,10,20)})()]

class BadCalendar:
    def sessions_in_range(self,start,end):
        raise RuntimeError("calendar unavailable")

class CalendarRefreshTests(unittest.TestCase):
    def test_refresh_replaces_existing_file(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"calendar.json"
            p.write_text('{"old":true}')
            result=refresh_calendar(str(p),now_utc=datetime(2026,10,20,1,tzinfo=timezone.utc),calendar=FakeCalendar())
            self.assertEqual(result["status"],"REFRESHED")
            self.assertEqual(json.loads(p.read_text())["market"],"KRX")
    def test_failed_refresh_preserves_old_file(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"calendar.json"
            p.write_text('{"old":true}')
            with self.assertRaises(RuntimeError):
                refresh_calendar(str(p),calendar=BadCalendar())
            self.assertEqual(p.read_text(),'{"old":true}')

if __name__=="__main__":
    unittest.main()
