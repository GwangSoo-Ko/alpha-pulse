from alphapulse.briefing.scheduler import parse_time, should_run_now


def test_parse_time():
    h, m = parse_time("08:30")
    assert h == 8
    assert m == 30


def test_parse_time_invalid():
    h, m = parse_time("invalid")
    assert h == 8
    assert m == 30  # default


def test_parse_time_none():
    h, m = parse_time(None)
    assert h == 8
    assert m == 30


def test_should_run_now():
    from datetime import time
    target = time(8, 30)
    assert should_run_now(time(8, 30), target, tolerance_minutes=1)
    assert should_run_now(time(8, 31), target, tolerance_minutes=1)
    assert not should_run_now(time(9, 0), target, tolerance_minutes=1)
    assert not should_run_now(time(7, 0), target, tolerance_minutes=1)
