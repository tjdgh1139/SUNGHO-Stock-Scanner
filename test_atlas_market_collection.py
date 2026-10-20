import tempfile
import unittest
from pathlib import Path
from atlas_market_collection import collect_cycle
from atlas_market_quote_store import latest_quote

class CollectionTests(unittest.TestCase):
    def test_collect_and_isolate_failed_symbols(self):
        with tempfile.TemporaryDirectory() as folder:
            db=str(Path(folder)/"quotes.db")
            def provider(symbol):
                if symbol == "005930":
                    raise TimeoutError("mock")
                return {"price": 1000, "volume": 10}
            t="2026-10-20T08:00:00+00:00"
            first=collect_cycle(db,["000660","005930","000660"],provider,received_at_utc=t)
            self.assertEqual((first.attempted,first.stored,first.duplicates),(2,1,0))
            self.assertEqual(first.failed,{"005930":"TimeoutError"})
            self.assertIsNotNone(latest_quote(db,"KRX","000660"))
            self.assertIsNone(latest_quote(db,"KRX","005930"))
            second=collect_cycle(db,["000660"],provider,received_at_utc=t)
            self.assertEqual(second.duplicates,1)

if __name__=="__main__":
    unittest.main()
