import tempfile
import unittest
from pathlib import Path
from atlas_market_quote_store import save_quote, latest_quote

class MarketQuoteStoreTests(unittest.TestCase):
    def test_append_dedupe_and_latest(self):
        with tempfile.TemporaryDirectory() as folder:
            db = str(Path(folder) / "quotes.sqlite")
            base = dict(market="KRX", symbol="000660", source="KIS_REST",
                        received_at_utc="2026-10-19T09:50:46+00:00",
                        price=1292000, volume=3678841)
            self.assertTrue(save_quote(db, **base))
            self.assertFalse(save_quote(db, **base))
            self.assertEqual(latest_quote(db, "KRX", "000660")["price"], 1292000)
            self.assertTrue(save_quote(db, market="KRX", symbol="000660",
                source="KIS_REST", received_at_utc="2026-10-19T09:51:46+00:00",
                price=1293000))
            self.assertEqual(latest_quote(db, "KRX", "000660")["price"], 1293000)
            self.assertIsNone(latest_quote(db, "NASDAQ", "000660"))

    def test_reject_invalid_data(self):
        with tempfile.TemporaryDirectory() as folder:
            db = str(Path(folder) / "quotes.sqlite")
            base = dict(market="KRX",symbol="000660",source="KIS_REST",
                        received_at_utc="2026-10-19T09:50:46+00:00",price=1)
            for bad in (dict(price=0), dict(volume=-1), dict(change_pct=float("nan")),
                        dict(received_at_utc="2026-10-19T09:50:46")):
                with self.assertRaises(ValueError):
                    save_quote(db, **(base | bad))

    def test_received_at_utc_normalizes_equivalent_formats_and_dedupes(self):
        with tempfile.TemporaryDirectory() as folder:
            db = str(Path(folder) / "quotes.sqlite")
            row = dict(market="KRX", symbol="000660", source="KIS_REST", price=1)
            self.assertTrue(save_quote(db, **row, received_at_utc="2026-10-28T00:00:00Z"))
            self.assertFalse(save_quote(db, **row, received_at_utc="2026-10-28T00:00:00.000000+00:00"))
            self.assertEqual(latest_quote(db, "KRX", "000660")["received_at_utc"],
                             "2026-10-28T00:00:00.000000+00:00")

    def test_latest_quote_uses_true_instant_order_across_fractional_seconds(self):
        with tempfile.TemporaryDirectory() as folder:
            db = str(Path(folder) / "quotes.sqlite")
            row = dict(market="KRX", symbol="000660", source="KIS_REST")
            self.assertTrue(save_quote(db, **row, received_at_utc="2026-10-28T00:00:00Z", price=1))
            self.assertTrue(save_quote(db, **row, received_at_utc="2026-10-28T00:00:00.500000+00:00", price=2))
            self.assertEqual(latest_quote(db, "KRX", "000660")["price"], 2)

if __name__ == "__main__":
    unittest.main()
