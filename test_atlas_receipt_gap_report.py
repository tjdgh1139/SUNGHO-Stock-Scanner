import sqlite3
import tempfile
import unittest
from pathlib import Path
from atlas_receipt_gap_report import receipt_gaps

class ReceiptGapTests(unittest.TestCase):
    def test_gap_counts_and_read_only(self):
        with tempfile.TemporaryDirectory() as folder:
            path=str(Path(folder)/"q.sqlite")
            with sqlite3.connect(path) as db:
                db.execute("CREATE TABLE market_quotes(id INTEGER PRIMARY KEY,market TEXT,symbol TEXT,received_at_utc TEXT)")
                db.executemany("INSERT INTO market_quotes VALUES (?,?,?,?)",[
                    (1,"KRX","000660","2026-10-20T01:00:00Z"),
                    (2,"KRX","000660","2026-10-20T01:05:00Z"),
                    (3,"KRX","000660","2026-10-20T01:20:00Z")])
            r=receipt_gaps(path)
            self.assertEqual(r[0]["records"],3)
            self.assertEqual(r[0]["max_gap_seconds"],900)
            self.assertEqual(r[0]["gaps_over_threshold"],1)
    def test_missing_db_does_not_create(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"missing.sqlite"
            with self.assertRaises(sqlite3.OperationalError):
                receipt_gaps(str(path))
            self.assertFalse(path.exists())
if __name__=="__main__":
    unittest.main()
