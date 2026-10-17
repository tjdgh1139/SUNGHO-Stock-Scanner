from atlas_preopen_published import should_use_automatic

def test_manual_same_day_preserved():
    a={"session_date":"20261019","frozen_at_utc":"2026-10-18T22:00:00+00:00"}
    newer={"session_date":"20261019","frozen_at_utc":"2026-10-18T22:55:00+00:00"}
    assert not should_use_automatic(a,"manual",newer)

def test_new_day_replaces_old_manual():
    old={"session_date":"20261019","frozen_at_utc":"2026-10-18T22:55:00+00:00"}
    today={"session_date":"20261020","frozen_at_utc":"2026-10-19T22:00:00+00:00"}
    assert should_use_automatic(old,"manual",today)

def test_second_preopen_replaces_first_automatic():
    first={"session_date":"20261019","frozen_at_utc":"2026-10-18T22:00:00+00:00"}
    second={"session_date":"20261019","frozen_at_utc":"2026-10-18T22:55:00+00:00"}
    assert should_use_automatic(first,"automatic",second)

def test_older_or_missing_auto_does_not_replace():
    today={"session_date":"20261019","frozen_at_utc":"2026-10-18T22:55:00+00:00"}
    older={"session_date":"20261019","frozen_at_utc":"2026-10-18T22:00:00+00:00"}
    assert not should_use_automatic(today,"automatic",older)
    assert not should_use_automatic(today,"automatic",None)
