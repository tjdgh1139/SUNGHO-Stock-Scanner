import unittest
from atlas_quote_quality import assess_quote

class QualityTests(unittest.TestCase):
    def test_fresh_and_stale(self):
        q={"received_at_utc":"2026-10-20T09:00:00Z","price":100}
        self.assertTrue(assess_quote(q,now_utc="2026-10-20T09:01:00Z")["usable"])
        self.assertEqual(assess_quote(q,now_utc="2026-10-20T09:04:00Z")["reason"],"STALE")
    def test_missing_and_future(self):
        self.assertEqual(assess_quote(None,now_utc="2026-10-20T09:00:00Z")["reason"],"MISSING")
        q={"received_at_utc":"2026-10-20T09:01:00Z","price":100}
        self.assertEqual(assess_quote(q,now_utc="2026-10-20T09:00:00Z")["reason"],"FUTURE_TIMESTAMP")

if __name__=="__main__":
    unittest.main()
