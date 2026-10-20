import unittest
from atlas_collector_watchdog_policy import decide_watchdog

class WatchdogTests(unittest.TestCase):
    def test_halt_and_alert(self):
        self.assertEqual(decide_watchdog(consecutive_failures=5,last_success_age_seconds=10,market_open=True).action,"HALT")
        self.assertEqual(decide_watchdog(consecutive_failures=0,last_success_age_seconds=400,market_open=True).reason,"STALE_COLLECTION")
        self.assertEqual(decide_watchdog(consecutive_failures=0,last_success_age_seconds=10,market_open=False).action,"WAIT")
        self.assertEqual(decide_watchdog(consecutive_failures=0,last_success_age_seconds=-1,market_open=True).action,"HALT")
    def test_healthy(self):
        self.assertEqual(decide_watchdog(consecutive_failures=0,last_success_age_seconds=30,market_open=True).action,"CONTINUE")

if __name__=="__main__":
    unittest.main()
