import sqlite3
import tempfile
import unittest
from pathlib import Path
from atlas_quote_quality_audit import audit_latest

class AuditTests(unittest.TestCase):
    def test_unverified_timestamp_is_blocked(self):
        with tempfile.TemporaryDirectory() as folder:
            src=str(Path(folder)/"quotes.sqlite")
            dest=str(Path(folder)/"audit.sqlite")
            with sqlite3.connect(src) as db:
                db.execute("CREATE TABLE market_quotes(id INTEGER PRIMARY KEY,market TEXT,symbol TEXT,received_at_utc TEXT,price REAL,volume REAL,turnover REAL)")
                db.execute("INSERT INTO market_quotes VALUES (1,'KRX','000660','2026-10-21T01:00:00+00:00',1200000,100,100000)")
            self.assertEqual(audit_latest(src,dest,now_utc="2026-10-21T01:00:01+00:00")["blocked"],1)
            with sqlite3.connect(dest) as db:
                self.assertEqual(db.execute("SELECT reason FROM quote_quality_audit").fetchone()[0],"UNVERIFIED_EXCHANGE_TIME")
    def test_missing_source_does_not_create_quote_db(self):
        with tempfile.TemporaryDirectory() as folder:
            src=Path(folder)/"missing.sqlite"
            with self.assertRaises(sqlite3.OperationalError):
                audit_latest(str(src),str(Path(folder)/"audit.sqlite"))
            self.assertFalse(src.exists())
if __name__=="__main__":
    unittest.main()
