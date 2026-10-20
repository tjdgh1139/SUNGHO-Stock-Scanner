import unittest
from atlas_scan_readiness import assess_scan_readiness

class ScanReadinessTests(unittest.TestCase):
    def test_fresh_complete(self):
        q={"received_at_utc":"2026-10-20T09:00:00Z","price":100}
        r=assess_scan_readiness(coverage={"expected":1,"coverage_pct":100},
            latest_quotes={"000660":q},now_utc="2026-10-20T09:01:00Z")
        self.assertTrue(r["ready"])
    def test_universe_identity_not_just_count(self):
        q={"received_at_utc":"2026-10-20T09:00:00Z","price":100}
        a=assess_scan_readiness(coverage={"expected":2,"coverage_pct":100},
            latest_quotes={"000660":q,"999999":q},expected_symbols=["000660","005930"],
            now_utc="2026-10-20T09:01:00Z")
        self.assertEqual(a["reason"],"INCOMPLETE_QUOTE_SET")
        self.assertEqual(a["missing"],["005930"])
        b=assess_scan_readiness(coverage={"expected":1,"coverage_pct":100},
            latest_quotes={"000660":q,"005930":q},expected_symbols=["000660"],
            now_utc="2026-10-20T09:01:00Z")
        self.assertEqual(b["reason"],"UNEXPECTED_SYMBOLS")

    def test_stale_and_coverage(self):
        q={"received_at_utc":"2026-10-20T08:00:00Z","price":100}
        a=assess_scan_readiness(coverage={"expected":1,"coverage_pct":100},
            latest_quotes={"000660":q},now_utc="2026-10-20T09:01:00Z")
        self.assertEqual(a["reason"],"UNUSABLE_QUOTES")
        b=assess_scan_readiness(coverage={"expected":2,"coverage_pct":50},
            latest_quotes={"000660":q},now_utc="2026-10-20T09:01:00Z")
        self.assertEqual(b["reason"],"INSUFFICIENT_COVERAGE")

if __name__=="__main__":
    unittest.main()
