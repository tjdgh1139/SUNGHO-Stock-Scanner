import tempfile
import unittest
from pathlib import Path
from atlas_market_quote_store import save_quote
from atlas_signal_followup import save_signal,snapshot_performance

class FollowupTests(unittest.TestCase):
    def test_only_post_signal_prices(self):
        with tempfile.TemporaryDirectory() as folder:
            db=str(Path(folder)/"test.db")
            def quote(t,p):
                save_quote(db,market="KRX",symbol="000660",source="KIS_REST",
                           received_at_utc=t,price=p)
            quote("2026-10-20T08:59:00Z",150)
            self.assertTrue(save_signal(db,market="KRX",symbol="000660",
                signal_at_utc="2026-10-20T09:00:00Z",reference_price=100,strategy="paper"))
            self.assertFalse(save_signal(db,market="KRX",symbol="000660",
                signal_at_utc="2026-10-20T09:00:00Z",reference_price=100,strategy="paper"))
            self.assertEqual(snapshot_performance(db,1)["status"],"NO_POST_SIGNAL_DATA")
            quote("2026-10-20T09:01:00Z",103)
            quote("2026-10-20T09:02:00Z",97)
            perf=snapshot_performance(db,1)
            self.assertEqual((perf["mfe_pct"],perf["mae_pct"]),(3,-3))
            self.assertEqual(perf["observations"],2)

if __name__=="__main__":
    unittest.main()
