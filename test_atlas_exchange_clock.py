import pytest
from atlas_exchange_clock import validate_exchange_clock

@pytest.mark.parametrize("name,clock,received,day,expected", [
    ("NORMAL", "093015", "2026-10-20T00:30:17+00:00", "20261020", True),
    ("MIDNIGHT", "000001", "2026-10-20T15:00:03+00:00", "20261021", True),
    ("STALE", "093015", "2026-10-20T00:33:15+00:00", "20261020", False),
    ("FUTURE", "093015", "2026-10-20T00:30:05+00:00", "20261020", False),
    ("WRONG_DAY", "093015", "2026-10-20T00:30:17+00:00", "20261019", False),
    ("BAD_DATE", "093015", "2026-10-20T00:30:17+00:00", "20261320", False),
    ("BAD_TIME", "256099", "2026-10-20T00:30:17+00:00", "20261020", False),
    ("NO_TIMEZONE", "093015", "2026-10-20T00:30:17", "20261020", False),
    ("FUTURE_DATE", "093015", "2026-10-20T00:30:17+00:00", "20261021", False),
])
def test_exchange_clock_cases(name, clock, received, day, expected):
    result = validate_exchange_clock(clock, received, day)
    assert result["valid"] is expected, name
