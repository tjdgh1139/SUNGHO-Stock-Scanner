import tempfile
import unittest
from pathlib import Path
from atlas_kis_quote_bridge import collect_one
from atlas_market_quote_store import latest_quote

class BridgeTests(unittest.TestCase):
    def test_injected_provider_and_deduplication(self):
        calls=[]
        def fake(symbol):
            calls.append(symbol)
            return {"price": 1000, "volume": 200, "turnover": 300000, "change_pct": -1}
        with tempfile.TemporaryDirectory() as d:
            path=str(Path(d)/"market.sqlite")
            stamp="2026-10-19T09:50:46+00:00"
            self.assertTrue(collect_one(path,"000660",fake,received_at_utc=stamp))
            self.assertFalse(collect_one(path,"000660",fake,received_at_utc=stamp))
            self.assertEqual(calls,["000660","000660"])
            self.assertEqual(latest_quote(path,"KRX","000660")["volume"],200)

    def test_invalid_response_never_stored(self):
        with tempfile.TemporaryDirectory() as d:
            path=str(Path(d)/"market.sqlite")
            with self.assertRaises(ValueError):
                collect_one(path,"000660",lambda _: {},received_at_utc="2026-10-19T09:50:46Z")
            self.assertIsNone(latest_quote(path,"KRX","000660"))
            with self.assertRaises(ValueError):
                collect_one(path,"MU",lambda _: {"price": 10})

if __name__=="__main__":
    unittest.main()
