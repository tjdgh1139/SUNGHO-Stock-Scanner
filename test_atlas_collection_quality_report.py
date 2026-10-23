import sqlite3
import tempfile
import unittest
from pathlib import Path
from atlas_collection_quality_report import summarize

class ReportTests(unittest.TestCase):
    def test_aggregates_without_mutation(self):
        with tempfile.TemporaryDirectory() as d:
            q,h,a=[str(Path(d)/n) for n in ("q.db","h.db","a.db")]
            with sqlite3.connect(q) as c:
                c.execute("CREATE TABLE market_quotes(market TEXT,symbol TEXT,received_at_utc TEXT)")
                c.execute("INSERT INTO market_quotes VALUES('KRX','000660','2026-10-22T01:00:00Z')")
            with sqlite3.connect(h) as c:
                c.execute("CREATE TABLE collector_heartbeat(market TEXT,state TEXT,attempted INTEGER,stored INTEGER,failed INTEGER)")
                c.execute("INSERT INTO collector_heartbeat VALUES('KRX','HEALTHY',2,2,0)")
            with sqlite3.connect(a) as c:
                c.execute("CREATE TABLE quote_quality_audit(market TEXT,symbol TEXT,status TEXT,reason TEXT)")
                c.execute("INSERT INTO quote_quality_audit VALUES('KRX','000660','BLOCKED','STALE')")
            result=summarize(q,h,a)
            self.assertEqual(result["quotes"][0]["records"],1)
            self.assertEqual(result["cycles"][0]["failed"],0)
            self.assertEqual(result["quality"][0]["reason"],"STALE")
    def test_missing_database_not_created(self):
        with tempfile.TemporaryDirectory() as d:
            q=Path(d)/"missing.db"
            with self.assertRaises(sqlite3.OperationalError):
                summarize(str(q),str(q),str(q))
            self.assertFalse(q.exists())
if __name__=="__main__":
    unittest.main()
