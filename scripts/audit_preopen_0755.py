"""Fail-closed read-only verification for a scheduled 07:55 KST EOD snapshot.

A green GitHub Actions run alone is not evidence of an on-time recheck.
No broker integration, trading orders, or live BUY judgments occur here.
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")


def _instant(value):
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    return parsed.astimezone(timezone.utc) if parsed.tzinfo is not None else None


def audit_0755(snapshot, *, verified_at, built_this_run, run_completed_at=None):
    """Return (ON_TIME|MISSED, reason); status ignores GitHub's success flag.

    verified_at is when the *final* publication check executes. A later
    completed Actions run can be checked again using run_completed_at.
    """
    now = _instant(verified_at)
    finished = _instant(run_completed_at) if run_completed_at is not None else now
    if now is None or finished is None:
        return "MISSED", "unverified audit or run-completion timestamp"
    now_kst = now.astimezone(KST)
    done_kst = finished.astimezone(KST)
    if not (now_kst.hour == 7 and 55 <= now_kst.minute <= 59):
        return "MISSED", "verification did not finish before 08:00 KST"
    if finished < now or done_kst.date() != now_kst.date() or not (done_kst.hour == 7 and 55 <= done_kst.minute <= 59):
        return "MISSED", "workflow completion did not occur before 08:00 KST"
    if built_this_run is not True:
        return "MISSED", "07:55 run did not generate a fresh recheck snapshot"
    if not isinstance(snapshot, dict):
        return "MISSED", "published snapshot absent or unreadable"
    generated = _instant(snapshot.get("generated_at_utc"))
    if generated is None or generated > now:
        return "MISSED", "missing, future, or naive snapshot timestamp"
    pub_kst = generated.astimezone(KST)
    if pub_kst.date() != now_kst.date() or not (pub_kst.hour == 7 and 55 <= pub_kst.minute <= 59):
        return "MISSED", "snapshot is not from the 07:55-07:59 KST window"
    if (snapshot.get("market") != "KR" or snapshot.get("phase") != "recheck"
            or snapshot.get("session_date") != now_kst.strftime("%Y%m%d")):
        return "MISSED", "recheck phase, market, or current session not verified"
    coverage = snapshot.get("coverage")
    rows = snapshot.get("candidates")
    if not isinstance(coverage, dict) or not isinstance(rows, list):
        return "MISSED", "coverage or candidate evidence missing"
    try:
        attempted = int(coverage["attempted"])
        validated = int(coverage["validated"])
    except (KeyError, TypeError, ValueError, OverflowError):
        return "MISSED", "invalid validated coverage"
    if not (0 < validated <= attempted and 1 <= len(rows) <= min(5, validated)):
        return "MISSED", "no validated candidate publication"
    # EOD WATCH must never be certified as the session's authenticated LIVE BUY.
    seen_symbols = set()
    for row in rows:
        if not isinstance(row, dict):
            return "MISSED", "candidate evidence missing"
        symbol = row.get("symbol")
        if (not isinstance(symbol, str) or len(symbol) != 6 or
                not symbol.isascii() or not symbol.isdigit() or symbol in seen_symbols):
            return "MISSED", "candidate symbol missing, invalid, or duplicated"
        seen_symbols.add(symbol)
        source, status = row.get("source"), row.get("status")
        if not isinstance(source, str) or "EOD" not in source or "NOT LIVE" not in source:
            return "MISSED", "candidate source is not historical EOD"
        if not isinstance(status, str) or not status.startswith("WATCH") or any(
                claim in status.upper() for claim in ("BUY", "SELL")):
            return "MISSED", "historical EOD candidate claims trading signal"
        try:
            last_date = datetime.strptime(row["last_trading_date"], "%Y-%m-%d").date()
        except (KeyError, TypeError, ValueError):
            return "MISSED", "historical EOD reference date invalid"
        if not 1 <= (pub_kst.date() - last_date).days <= 5:
            return "MISSED", "historical EOD reference date missing or stale"
    return "ON_TIME", "fresh EOD WATCH recheck published before 08:00 KST"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path)
    args = parser.parse_args(argv)
    try:
        snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, UnicodeError, json.JSONDecodeError):
        snapshot = None
    import os
    status, reason = audit_0755(snapshot, verified_at=datetime.now(timezone.utc),
                                built_this_run=os.environ.get("ATLAS_PUBLISHED_RECHECK") == "true")
    print(f"07:55 KST {status}: {reason}")
    return 0 if status == "ON_TIME" else 2


if __name__ == "__main__":
    raise SystemExit(main())
