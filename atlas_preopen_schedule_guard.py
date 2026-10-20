"""Fail-closed timing gate for scheduled *historical* KR preopen snapshots.

GitHub Actions may start a cron run late and mark a no-op job successful.
Only a job still within its own intended KST time slot can publish.
No trading, price, or data-provider operations are performed here.
"""
from datetime import datetime
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")
CRON_SLOT = {
    "0 22 * * 0-4": ("first", 7 * 60, 7 * 60 + 50),
    "50 22 * * 0-4": ("recheck", 7 * 60 + 50, 8 * 60),
    "55 22 * * 0-4": ("recheck", 7 * 60 + 55, 8 * 60),
}


def check_schedule_window(cron, when):
    """Return (allowed, expected_phase). Unknown schedules always fail.

    cron is github.event.schedule, which must be split into distinct entries
    in workflow YAML so the 07:55 run is distinguishable from 07:50.
    Empty cron means an unscheduled manual run and is not a mandatory publish.
    """
    if not cron:
        return True, None
    slot = CRON_SLOT.get(cron)
    if slot is None or not isinstance(when, datetime) or when.tzinfo is None:
        return False, None
    local = when.astimezone(KST)
    expected, minute_min, minute_max = slot
    minute = local.hour * 60 + local.minute
    return (local.weekday() < 5 and minute_min <= minute < minute_max), expected
