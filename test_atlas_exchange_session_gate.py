import unittest
from datetime import datetime, timezone
from atlas_exchange_session_gate import market_gate

class SessionGateTests(unittest.TestCase):
    def test_missing_calendar_fails_closed(self):
        now=datetime(2026,10,20,1,0,tzinfo=timezone.utc)
        self.assertFalse(market_gate("KRX",now,verified_open_dates=None)["open"])
    def test_krx_verified_session(self):
        now=datetime(2026,10,20,1,0,tzinfo=timezone.utc)
        self.assertTrue(market_gate("KRX",now,verified_open_dates={"2026-10-20"})["open"])
        self.assertFalse(market_gate("KRX",now,verified_open_dates=set())["open"])
    def test_us_early_close_and_dst(self):
        now=datetime(2026,11,27,19,0,tzinfo=timezone.utc)
        self.assertFalse(market_gate("NYSE",now,verified_open_dates={"2026-11-27"},
            verified_early_closes={"2026-11-27":"13:00"})["open"])
        self.assertTrue(market_gate("NASDAQ",datetime(2026,11,27,17,0,tzinfo=timezone.utc),
            verified_open_dates={"2026-11-27"},verified_early_closes={"2026-11-27":"13:00"})["open"])

if __name__=="__main__":
    unittest.main()
