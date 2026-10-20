import io
import json
import tempfile
import unittest
from pathlib import Path
from datetime import datetime,timezone
from contextlib import redirect_stdout
from atlas_staging_scheduler_gate import main

class StagingSchedulerTests(unittest.TestCase):
    def test_fail_closed_without_calendar(self):
        with tempfile.TemporaryDirectory() as d:
            args=["--calendar",str(Path(d)/"missing.json"),"--lock-file",str(Path(d)/"lock"),
                  "--db",str(Path(d)/"q"),"--health-db",str(Path(d)/"h"),"--symbols","000660"]
            self.assertEqual(main(args),3)
    def test_stale_calendar_blocks_collector(self):
        with tempfile.TemporaryDirectory() as d:
            cal=Path(d)/"cal.json"
            cal.write_text(json.dumps({"market":"KRX","verified_open_dates":["2026-10-20"],
                "generated_at_utc":"2026-10-01T00:00:00Z","valid_through_local_date":"2026-10-27"}))
            args=["--calendar",str(cal),"--lock-file",str(Path(d)/"lock"),
                  "--db",str(Path(d)/"q"),"--health-db",str(Path(d)/"h"),"--symbols","000660"]
            calls=[]
            self.assertEqual(main(args,now_utc=datetime(2026,10,20,1,tzinfo=timezone.utc),collector=lambda a:calls.append(a)),3)
            self.assertEqual(calls,[])

    def test_verified_market_calls_collector_once(self):
        with tempfile.TemporaryDirectory() as d:
            cal=Path(d)/"cal.json"
            cal.write_text(json.dumps({"market":"KRX","verified_open_dates":["2026-10-20"],"generated_at_utc":"2026-10-20T00:00:00Z","valid_through_local_date":"2026-10-27"}))
            args=["--calendar",str(cal),"--lock-file",str(Path(d)/"lock"),
                  "--db",str(Path(d)/"q"),"--health-db",str(Path(d)/"h"),"--symbols","000660"]
            calls=[]
            def fake(a):
                calls.append(a)
                return 0
            now=datetime(2026,10,20,1,0,tzinfo=timezone.utc)
            self.assertEqual(main(args,now_utc=now,collector=fake),0)
            self.assertEqual(len(calls),1)
            self.assertEqual(main(args,now_utc=now.replace(hour=23),collector=fake),0)
            self.assertEqual(len(calls),1)

if __name__=="__main__":
    unittest.main()
