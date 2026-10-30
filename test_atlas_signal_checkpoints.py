import tempfile
import unittest
from pathlib import Path
from atlas_market_quote_store import save_quote
from atlas_signal_followup import save_signal
from atlas_signal_checkpoints import checkpoint_returns

class CheckpointTests(unittest.TestCase):
    def test_no_future_or_missing_data_invention(self):
        with tempfile.TemporaryDirectory() as folder:
            db=str(Path(folder)/"test.db")
            save_signal(db,market="KRX",symbol="000660",
                        signal_at_utc="2026-10-20T09:00:00Z",
                        reference_price=100,strategy="paper")
            def quote(t,p):
                save_quote(db,market="KRX",symbol="000660",source="KIS_REST",
                           received_at_utc=t,price=p)
            quote("2026-10-20T09:04:00Z",110)
            quote("2026-10-20T09:05:00Z",102)
            quote("2026-10-20T09:15:00Z",97)
            result=checkpoint_returns(db,1,tolerance_minutes=1)
            self.assertEqual(result["5m"]["return_pct"],2)
            self.assertEqual(result["15m"]["return_pct"],-3)
            self.assertEqual(result["30m"]["status"],"MISSING")
            self.assertEqual(result["1440m"]["status"],"MISSING")

if __name__=="__main__":
    unittest.main()
