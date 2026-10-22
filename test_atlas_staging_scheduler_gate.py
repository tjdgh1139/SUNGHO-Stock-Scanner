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


    def test_successful_collection_runs_optional_audit(self):
        import sqlite3
        with tempfile.TemporaryDirectory() as d:
            cal=Path(d)/"cal.json"
            cal.write_text(json.dumps({"market":"KRX","verified_open_dates":["2026-10-20"],
                "generated_at_utc":"2026-10-20T00:00:00Z",
                "valid_through_local_date":"2026-10-27"}))
            db=str(Path(d)/"quotes.sqlite")
            audit=str(Path(d)/"audit.sqlite")
            args=["--calendar",str(cal),"--lock-file",str(Path(d)/"lock"),
                  "--db",db,"--health-db",str(Path(d)/"health"),
                  "--audit-db",audit,"--symbols","000660"]
            def collector(_):
                with sqlite3.connect(db) as c:
                    c.execute("CREATE TABLE market_quotes(id INTEGER PRIMARY KEY,market TEXT,symbol TEXT,received_at_utc TEXT,price REAL,volume REAL,turnover REAL)")
                    c.execute("INSERT INTO market_quotes VALUES(1,'KRX','000660','2026-10-20T01:00:00+00:00',1200000,100,100000)")
                return 0
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(args,now_utc=datetime(2026,10,20,1,tzinfo=timezone.utc),collector=collector),0)
            with sqlite3.connect(audit) as c:
                self.assertEqual(c.execute("SELECT COUNT(*) FROM quote_quality_audit").fetchone()[0],1)

    def test_failed_collector_skips_audit(self):
        with tempfile.TemporaryDirectory() as d:
            cal=Path(d)/"cal.json"
            cal.write_text(json.dumps({"market":"KRX","verified_open_dates":["2026-10-20"],
                "generated_at_utc":"2026-10-20T00:00:00Z",
                "valid_through_local_date":"2026-10-27"}))
            audit=Path(d)/"audit.sqlite"
            args=["--calendar",str(cal),"--lock-file",str(Path(d)/"lock"),
                  "--db",str(Path(d)/"quotes"),"--health-db",str(Path(d)/"health"),
                  "--audit-db",str(audit),"--symbols","000660"]
            self.assertEqual(main(args,now_utc=datetime(2026,10,20,1,tzinfo=timezone.utc),collector=lambda _:2),2)
            self.assertFalse(audit.exists())

if __name__=="__main__":
    unittest.main()
