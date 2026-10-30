import unittest
from atlas_collector_smoke import run_smoke

class SmokeTests(unittest.TestCase):
    def test_synthetic_end_to_end(self):
        result=run_smoke()
        self.assertEqual(result["result"],"PASS")
        self.assertEqual(result["stored"],2)

if __name__=="__main__":
    unittest.main()
