"""Fail-closed official-style exchange session check for scheduled KRX preopen.

Uses the maintained XKRX exchange calendar, including market holidays.
A missing calendar never means the market is open.
"""
from datetime import date


def krx_session(day,*,calendar=None):
    if not isinstance(day,date):
        return False
    try:
        if calendar is None:
            import exchange_calendars
            calendar=exchange_calendars.get_calendar("XKRX")
        return bool(calendar.is_session(day.isoformat()))
    except (ImportError,ValueError,TypeError,KeyError,OverflowError):
        return False
