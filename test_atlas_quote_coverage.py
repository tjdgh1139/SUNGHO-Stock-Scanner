import tempfile
import unittest
from pathlib import Path
from atlas_market_quote_store import save_quote
from atlas_quote_coverage import coverage_report

class CoverageTests(unittest.TestCase):
    def test_missing_and_duplicates(self):
        with tempfile.TemporaryDirectory() as folder:
            db=str(Path(folder)/"market.sqlite")
            expected=["000660","005930","000660"]
            a=coverage_report(db,"KRX",expected,"2026-10-20T00:00:00Z","2026-10-21T00:00:00Z")
            self.assertEqual((a["expected"],a["observed"],a["coverage_pct"]),(2,0,0.0))
            save_quote(db,market="KRX",symbol="000660",source="KIS_REST",
                       received_at_utc="2026-10-20T01:00:00Z",price=100)
            b=coverage_report(db,"KRX",expected,"2026-10-20T00:00:00Z","2026-10-21T00:00:00Z")
            self.assertEqual(b["coverage_pct"],50)
            self.assertEqual(b["missing"],["005930"])
            self.assertEqual(b["observations"],1)

if __name__=="__main__":
    unittest.main()
