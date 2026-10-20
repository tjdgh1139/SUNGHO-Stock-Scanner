import tempfile
import unittest
from pathlib import Path
from atlas_collector_heartbeat import save_heartbeat,latest_heartbeat

class HeartbeatTests(unittest.TestCase):
    def test_persist_and_reopen(self):
        with tempfile.TemporaryDirectory() as folder:
            db=str(Path(folder)/"health.db")
            save_heartbeat(db,market="KRX",observed_at_utc="2026-10-20T09:00:00Z",
                           state="HEALTHY",reason="OK",attempted=2,stored=2,failed=0)
            self.assertEqual(latest_heartbeat(db,"KRX")["state"],"HEALTHY")
            self.assertIsNone(latest_heartbeat(db,"NASDAQ"))
    def test_invalid_state_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError):
                save_heartbeat(str(Path(folder)/"health.db"),market="KRX",
                    observed_at_utc="2026-10-20T09:00:00Z",state="UNKNOWN",
                    reason="OK",attempted=1,stored=1,failed=0)

if __name__=="__main__":
    unittest.main()
