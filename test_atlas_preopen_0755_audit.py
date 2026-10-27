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
    "candidates": [{"source": "HISTORICAL EOD NOT LIVE", "symbol": "000660",
                    "status": "WATCH · pre-open technical screen", "last_trading_date": "2026-10-22"}],
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

    def test_missing_snapshot_fails_closed(self):
        status, _ = audit_0755(None, verified_at=VERIFIED, built_this_run=True)
        self.assertEqual(status, "MISSED")

    def test_completion_on_different_day_fails_closed(self):
        self.assertEqual(self.check(run_completed_at="2026-10-21T22:58:00Z"), "MISSED")

    def test_completion_before_verification_fails_closed(self):
        self.assertEqual(self.check(run_completed_at="2026-10-22T22:57:00Z"), "MISSED")

    def test_invalid_coverage_type_fails_closed(self):
        self.assertEqual(self.check({**VALID, "coverage":{"attempted":"invalid","validated":3}}), "MISSED")

    def test_future_snapshot_fails_closed(self):
        self.assertEqual(self.check({**VALID, "generated_at_utc":"2026-10-22T22:59:00Z"}), "MISSED")

    def test_naive_timestamp_rejected(self):
        self.assertEqual(self.check({**VALID, "generated_at_utc":"2026-10-23T07:56:00"}), "MISSED")


    def test_symbol_must_be_unique_six_digit_ascii_code(self):
        for symbol in (None, 660, "00066", "０００６６０", "00ABC0"):
            with self.subTest(symbol=symbol):
                row = {**VALID["candidates"][0], "symbol": symbol}
                self.assertEqual(self.check({**VALID, "candidates": [row]}), "MISSED")
        duplicate = [VALID["candidates"][0], dict(VALID["candidates"][0])]
        self.assertEqual(self.check({**VALID, "candidates": duplicate}), "MISSED")

    def test_oct_27_green_workflow_with_no_0755_snapshot_is_missed(self):
        # Oct 27 KST: 07:00 phase published at 07:23; nominal 07:55 run
        # completed at 08:13, printed 'no publication', and left it unchanged.
        first = {**VALID, "phase": "first", "session_date": "20261027",
                 "generated_at_utc": "2026-10-26T22:23:01Z",
                 "candidates": [{**VALID["candidates"][0],
                                 "last_trading_date": "2026-10-26"}]}
        self.assertEqual(self.check(first,
            verified_at="2026-10-26T23:13:31Z", built_this_run=False,
            run_completed_at="2026-10-26T23:13:34Z"), "MISSED")
        # Even a hypothetical valid-looking recheck is invalid when completion
        # is after 08:00 KST; GitHub's success conclusion is irrelevant.
        recheck = {**first, "phase": "recheck",
                   "generated_at_utc": "2026-10-26T22:56:00Z"}
        self.assertEqual(self.check(recheck,
            verified_at="2026-10-26T22:59:58Z", built_this_run=True,
            run_completed_at="2026-10-26T23:13:34Z"), "MISSED")

    def test_historical_candidate_cannot_claim_buy_or_sell(self):
        for status in ("BUY", "SELL", "WATCH · BUY now", "WATCH · SELL now", "HOLD"):
            with self.subTest(status=status):
                row = {**VALID["candidates"][0], "status": status}
                self.assertEqual(self.check({**VALID, "candidates": [row]}), "MISSED")

    def test_historical_reference_date_must_precede_session_and_be_recent(self):
        for value in ("2026-10-23", "2026-10-24", "2026-10-01", "garbage", None):
            with self.subTest(value=value):
                row = {**VALID["candidates"][0], "last_trading_date": value}
                self.assertEqual(self.check({**VALID, "candidates": [row]}), "MISSED")

    def test_marked_not_live_but_not_eod_is_rejected(self):
        row = {**VALID["candidates"][0], "source": "KIS WS · NOT LIVE"}
        self.assertEqual(self.check({**VALID, "candidates": [row]}), "MISSED")

    def test_historical_weekend_gap_accepts_monday_session(self):
        row = {**VALID["candidates"][0], "last_trading_date": "2026-10-23"}
        monday = {**VALID, "generated_at_utc": "2026-10-25T22:56:00Z",
                  "session_date": "20261026", "candidates": [row]}
        self.assertEqual(self.check(monday, verified_at="2026-10-25T22:58:00Z"), "ON_TIME")

    def test_oct_26_late_0755_workflow_is_missed_even_if_green(self):
        previous_first = {
            **VALID, "phase": "first", "session_date": "20261026",
            "generated_at_utc": "2026-10-25T22:13:39Z",
            "candidates": [
                {**VALID["candidates"][0], "last_trading_date": "2026-10-23"}
            ],
        }
        status = self.check(previous_first,
                            verified_at="2026-10-25T23:06:13Z",
                            built_this_run=False)
        self.assertEqual(status, "MISSED")

    def test_scheduled_0755_workflow_must_audit_both_before_and_after_push(self):
        from pathlib import Path
        workflow = (Path(__file__).resolve().parent / ".github" / "workflows"
                    / "atlas-scheduled-preopen.yml").read_text(encoding="utf-8")
        self.assertIn("- cron: '55 22 * * 0-4'", workflow)
        self.assertIn("github.event.schedule == '55 22 * * 0-4'", workflow)
        self.assertIn("ATLAS_PUBLISHED_RECHECK: ${{ steps.build.outputs.snapshot_changed }}", workflow)
        self.assertLess(workflow.index("Preflight 07:55 KST recheck evidence"),
                        workflow.index("Commit only if a verified snapshot exists"))
        self.assertLess(workflow.index("Commit only if a verified snapshot exists"),
                        workflow.index("Verify 07:55 KST publication before 08:00"))


if __name__ == "__main__":
    unittest.main()
