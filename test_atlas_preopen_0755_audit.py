"""Offline regression tests for 07:55 KST publication audit."""
import unittest
from datetime import datetime, timezone
from scripts.audit_preopen_0755 import audit_0755

VALID = {
    "generated_at_utc": "2026-10-22T22:56:00Z",
    "market": "KR",
    "phase": "recheck",
    "session_date": "20261023",
    "coverage": {"attempted": 5, "validated": 3},
    "candidates": [{"source": "HISTORICAL EOD NOT LIVE", "symbol": "000660"}],
}
VERIFIED = "2026-10-22T22:58:00Z"


class Audit0755Tests(unittest.TestCase):
    def check(self, snapshot=None, **kwargs):
        return audit_0755(VALID if snapshot is None else snapshot,
                          verified_at=kwargs.pop("verified_at", VERIFIED),
                          built_this_run=kwargs.pop("built_this_run", True),
                          **kwargs)[0]

    def test_valid_fresh_eod_recheck(self):
        self.assertEqual(self.check(), "ON_TIME")

    def test_missing_fresh_build_is_missed(self):
        self.assertEqual(self.check(built_this_run=False), "MISSED")

    def test_late_verification_is_missed(self):
        self.assertEqual(self.check(verified_at="2026-10-22T23:00:00Z"), "MISSED")

    def test_late_workflow_completion_is_missed(self):
        self.assertEqual(self.check(run_completed_at="2026-10-22T23:00:01Z"), "MISSED")

    def test_stale_snapshot_is_missed(self):
        self.assertEqual(self.check({**VALID, "generated_at_utc":"2026-10-21T22:56:00Z"}), "MISSED")

    def test_wrong_session_or_phase_is_missed(self):
        self.assertEqual(self.check({**VALID, "phase":"preopen"}), "MISSED")
        self.assertEqual(self.check({**VALID, "session_date":"20261022"}), "MISSED")

    def test_missing_coverage_or_candidates_is_missed(self):
        self.assertEqual(self.check({**VALID, "coverage":{"attempted":5,"validated":0}}), "MISSED")
        self.assertEqual(self.check({**VALID, "candidates":[]}), "MISSED")

    def test_live_claim_is_rejected(self):
        self.assertEqual(self.check({**VALID, "candidates":[{"source":"KIS LIVE"}]}), "MISSED")

    def test_naive_timestamp_rejected(self):
        self.assertEqual(self.check({**VALID, "generated_at_utc":"2026-10-23T07:56:00"}), "MISSED")


if __name__ == "__main__":
    unittest.main()
