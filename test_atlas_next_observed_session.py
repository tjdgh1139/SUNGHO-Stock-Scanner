import tempfile
import unittest
from pathlib import Path
from atlas_market_quote_store import save_quote
from atlas_signal_followup import save_signal
from atlas_next_observed_session import next_observed_session

class NextObservedTests(unittest.TestCase):
    def test_local_date_and_missing_coverage(self):
        with tempfile.TemporaryDirectory() as folder:
            db=str(Path(folder)/"test.sqlite")
            save_signal(db,market="KRX",symbol="000660",
                        signal_at_utc="2026-10-20T05:00:00Z",reference_price=100,strategy="paper")
            self.assertEqual(next_observed_session(db,1)["status"],"NO_NEXT_OBSERVED_SESSION")
            for t,p in [("2026-10-20T06:00:00Z",120),
                        ("2026-10-21T00:00:00Z",103),
                        ("2026-10-21T01:00:00Z",101)]:
                save_quote(db,market="KRX",symbol="000660",source="KIS_REST",
                           received_at_utc=t,price=p)
            result=next_observed_session(db,1)
            self.assertEqual(result["local_session_date"],"2026-10-21")
            self.assertEqual(result["first_observed_return_pct"],3)
            self.assertEqual(result["last_observed_return_pct"],1)
            self.assertEqual(result["observations"],2)

if __name__=="__main__":
    unittest.main()
