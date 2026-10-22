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


    def test_ten_symbols_partial_failure_isolated(self):
        with tempfile.TemporaryDirectory() as folder:
            db=str(Path(folder)/"quotes.db")
            symbols=[f"{i:06d}" for i in range(1,11)]
            calls=[]
            def provider(symbol):
                calls.append(symbol)
                if symbol in (symbols[2],symbols[7]):
                    raise TimeoutError("secret-token-must-not-leak")
                return {"price":1000,"volume":10,"turnover":10000}
            result=collect_cycle(db,symbols,provider,
                received_at_utc="2026-10-20T01:00:00+00:00")
            self.assertEqual(result.attempted,10)
            self.assertEqual(result.stored,8)
            self.assertEqual(result.failed,{symbols[2]:"TimeoutError",symbols[7]:"TimeoutError"})
            self.assertEqual(calls,symbols)
            self.assertNotIn("secret-token",str(result.failed))
            self.assertIsNone(latest_quote(db,"KRX",symbols[2]))
            self.assertIsNotNone(latest_quote(db,"KRX",symbols[9]))

    def test_all_failed_symbols_never_write_fake_quotes(self):
        with tempfile.TemporaryDirectory() as folder:
            db=str(Path(folder)/"quotes.db")
            def provider(symbol):
                raise ConnectionError("private-credential")
            result=collect_cycle(db,["000660","005930"],provider,
                received_at_utc="2026-10-20T01:00:00+00:00")
            self.assertEqual((result.attempted,result.stored),(2,0))
            self.assertEqual(len(result.failed),2)
            self.assertNotIn("private-credential",str(result.failed))
            self.assertIsNone(latest_quote(db,"KRX","000660"))

if __name__=="__main__":
    unittest.main()
