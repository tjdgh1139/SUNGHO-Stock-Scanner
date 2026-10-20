import unittest
from atlas_scan_readiness import assess_scan_readiness

class ScanReadinessTests(unittest.TestCase):
    def test_fresh_complete(self):
        q={"received_at_utc":"2026-10-20T09:00:00Z","price":100}
        r=assess_scan_readiness(coverage={"expected":1,"coverage_pct":100},
            latest_quotes={"000660":q},now_utc="2026-10-20T09:01:00Z")
        self.assertTrue(r["ready"])
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
