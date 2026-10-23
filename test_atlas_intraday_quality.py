import unittest
from atlas_intraday_quality import assess_intraday

class IntradayQualityTests(unittest.TestCase):
    def test_quality_cases(self):
        now = "2026-10-20T09:01:00+00:00"
        base = dict(
            received_at_utc="2026-10-20T09:00:30+00:00",
            price=100, volume=1000, turnover=100000,
            freshness="VERIFIED_EXCHANGE_TIME"
        )
        cases = [
            ("NORMAL", {}, True),
            ("ZERO_VOLUME", {"volume": 0}, False),
            ("ZERO_TURNOVER", {"turnover": 0}, False),
            ("MISSING_VOLUME", {"volume": None}, False),
            ("REST_ONLY", {"freshness": "REST_RECEIPT_ONLY"}, False),
            ("STALE", {"received_at_utc": "2026-10-20T08:50:00+00:00"}, False),
            ("NAN_VOLUME", {"volume": float("nan")}, False),
            ("INF_TURNOVER", {"turnover": float("inf")}, False),
            ("MISSING_FRESHNESS", {"freshness": None}, False),
            ("UNKNOWN_FRESHNESS", {"freshness": "UNKNOWN"}, False),
        ]
        for name, changes, expected in cases:
            with self.subTest(name=name):
                result = assess_intraday({**base, **changes}, now_utc=now)
                self.assertIs(result["eligible"], expected)
                self.assertEqual(
                    result["action"],
                    "EVALUATE" if expected else "WAIT"
                )

if __name__ == "__main__":
    unittest.main()
