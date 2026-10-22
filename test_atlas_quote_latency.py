import tempfile
import unittest
import sqlite3
from pathlib import Path
from atlas_quote_latency import timed_quote,save_latency
class LatencyTests(unittest.TestCase):
    def test_success(self):
        ticks=iter([1.0,1.4])
        result,event=timed_quote("000660",lambda s:{"price":1},clock=lambda:next(ticks))
        self.assertEqual(result,{"price":1})
        self.assertAlmostEqual(event["duration_seconds"],0.4)
    def test_failure_does_not_store_secret(self):
        ticks=iter([1.0,1.5])
        def fail(_): raise RuntimeError("secret")
        result,event=timed_quote("000660",fail,clock=lambda:next(ticks))
        self.assertIsNone(result)
        self.assertEqual(event["status"],"FAILED")
        self.assertNotIn("secret",str(event))
    def test_persist_event(self):
        with tempfile.TemporaryDirectory() as d:
            db=str(Path(d)/"latency.sqlite")
            save_latency(db,{"symbol":"000660","duration_seconds":0.3,"status":"OK"})
            with sqlite3.connect(db) as c:
                self.assertEqual(c.execute("SELECT COUNT(*) FROM quote_latency").fetchone()[0],1)
if __name__=="__main__":
    unittest.main()
