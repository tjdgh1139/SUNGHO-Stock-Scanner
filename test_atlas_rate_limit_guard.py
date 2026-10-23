import unittest
from atlas_rate_limit_guard import decide_rate_limit

class RateLimitGuardTests(unittest.TestCase):
    def test_http_429_stops_without_retry(self):
        r=decide_rate_limit(http_status=429)
        self.assertTrue(r.stop_cycle)
        self.assertFalse(r.retry_now)
    def test_auth_failure_stops(self):
        self.assertTrue(decide_rate_limit(http_status=401).stop_cycle)
    def test_unknown_error_does_not_claim_rate_limit(self):
        self.assertFalse(decide_rate_limit(http_status=503).stop_cycle)
    def test_invalid_status_fails_closed(self):
        self.assertTrue(decide_rate_limit(http_status=True).stop_cycle)

if __name__=="__main__":
    unittest.main()
