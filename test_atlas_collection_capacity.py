import unittest
from atlas_collection_capacity import estimate_cycle
class CapacityTests(unittest.TestCase):
    def test_ten_fast_responses(self):
        r=estimate_cycle(10,minimum_interval_seconds=0.5,response_seconds=0.1)
        self.assertAlmostEqual(r["estimated_seconds"],4.6)
        self.assertFalse(r["safe_to_expand"])
    def test_ten_slow_responses(self):
        r=estimate_cycle(10,minimum_interval_seconds=0.5,response_seconds=1)
        self.assertEqual(r["estimated_seconds"],10)
    def test_timeouts(self):
        self.assertEqual(estimate_cycle(10)["timeout_bound_seconds"],80)
    def test_invalid_inputs(self):
        for count in (0,-1,True,101):
            with self.assertRaises(ValueError):
                estimate_cycle(count)
if __name__=="__main__":
    unittest.main()
