import tempfile
import unittest
from pathlib import Path
from atlas_cycle_coordinator import run_cycle
from atlas_collector_heartbeat import latest_heartbeat

class CoordinatorTests(unittest.TestCase):
    def test_healthy_cycle(self):
        with tempfile.TemporaryDirectory() as folder:
            result=run_cycle(str(Path(folder)/"db.sqlite"),["000660"],
                lambda _: {"price":100},received_at_utc="2026-10-20T09:00:00Z")
            self.assertEqual(result.health.state,"HEALTHY")
            self.assertIsNone(result.retry)
    def test_heartbeat_is_persisted(self):
        with tempfile.TemporaryDirectory() as folder:
            db=str(Path(folder)/'quotes.db')
            health_db=str(Path(folder)/'health.db')
            run_cycle(db,['000660'],lambda _: {'price':100},
                      received_at_utc='2026-10-20T09:00:00Z',
                      heartbeat_db_path=health_db,market='KRX',
                      heartbeat_at_utc='2026-10-20T09:00:01Z')
            heartbeat=latest_heartbeat(health_db,'KRX')
            self.assertEqual(heartbeat['state'],'HEALTHY')
            self.assertEqual(heartbeat['stored'],1)

    def test_failed_provider_no_infinite_retry(self):
        with tempfile.TemporaryDirectory() as folder:
            def fail(_):
                raise RuntimeError("mock failure")
            result=run_cycle(str(Path(folder)/"db.sqlite"),["000660"],fail,
                consecutive_failures=1,last_status_code=403)
            self.assertEqual(result.health.state,"DEGRADED")
            self.assertFalse(result.retry.retry)

if __name__=="__main__":
    unittest.main()
