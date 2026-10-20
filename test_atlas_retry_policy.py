import unittest
from atlas_retry_policy import retry_policy

class RetryPolicyTests(unittest.TestCase):
    def test_403_never_auto_retry(self):
        self.assertFalse(retry_policy(consecutive_failures=1,status_code=403).retry)
    def test_bounded_backoff_and_circuit(self):
        a=retry_policy(consecutive_failures=2,status_code=429)
        self.assertTrue(a.retry)
        self.assertEqual(a.delay_seconds,4)
        b=retry_policy(consecutive_failures=5,status_code=500)
        self.assertEqual(b.reason,"CIRCUIT_OPEN")
    def test_bad_request_stops(self):
        self.assertFalse(retry_policy(consecutive_failures=1,status_code=400).retry)

if __name__=="__main__":
    unittest.main()
