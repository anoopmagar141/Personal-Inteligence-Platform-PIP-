from datetime import datetime, timedelta, timezone
from backend.stages import stage_00_gap_detector as gap_detector

def test_no_prior_session():
    """First-ever run case."""
    result = gap_detector.run(None)
    assert result == {"warm_start_level": "none", "context_depth_modifier": 0}

def test_under_1_hour():
    now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    last = now - timedelta(minutes=59, seconds=59)
    assert gap_detector.run(last, now) == {"warm_start_level": "none", "context_depth_modifier": 0}

def test_exactly_1_hour():
    """Exactly 1 hour boundary falls into 'brief' / 1."""
    now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    last = now - timedelta(hours=1)
    assert gap_detector.run(last, now) == {"warm_start_level": "brief", "context_depth_modifier": 1}

def test_under_24_hours():
    now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    last = now - timedelta(hours=23, minutes=59, seconds=59)
    assert gap_detector.run(last, now) == {"warm_start_level": "brief", "context_depth_modifier": 1}

def test_exactly_24_hours():
    """Exactly 24 hours boundary falls into 'summary' / 2."""
    now = datetime(2026, 1, 2, 12, 0, 0, tzinfo=timezone.utc)
    last = now - timedelta(hours=24)
    assert gap_detector.run(last, now) == {"warm_start_level": "summary", "context_depth_modifier": 2}

def test_under_7_days():
    now = datetime(2026, 1, 8, 12, 0, 0, tzinfo=timezone.utc)
    last = now - timedelta(days=6, hours=23, minutes=59, seconds=59)
    assert gap_detector.run(last, now) == {"warm_start_level": "summary", "context_depth_modifier": 2}

def test_exactly_7_days():
    """Exactly 7 days boundary falls into 'summary' / 2."""
    now = datetime(2026, 1, 8, 12, 0, 0, tzinfo=timezone.utc)
    last = now - timedelta(days=7)
    assert gap_detector.run(last, now) == {"warm_start_level": "summary", "context_depth_modifier": 2}

def test_over_7_days():
    """Strictly greater than 7 days falls into 'full' / 3."""
    now = datetime(2026, 1, 8, 12, 0, 0, tzinfo=timezone.utc)
    last = now - (timedelta(days=7) + timedelta(seconds=1))
    assert gap_detector.run(last, now) == {"warm_start_level": "full", "context_depth_modifier": 3}

def test_over_1_week():
    now = datetime(2026, 2, 1, 12, 0, 0, tzinfo=timezone.utc)
    last = now - timedelta(days=10)
    assert gap_detector.run(last, now) == {"warm_start_level": "full", "context_depth_modifier": 3}

def test_future_timestamp_fails_safe(caplog):
    """If the clock went backwards and gap is negative, fail safe to none/0."""
    now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    last = now + timedelta(hours=1)
    result = gap_detector.run(last, now)
    assert result == {"warm_start_level": "none", "context_depth_modifier": 0}
    assert "future" in caplog.text

def test_malformed_input_fails_safe(caplog):
    """Any unexpected error (e.g. TypeError from bad input) should be caught and fail safe."""
    now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    result = gap_detector.run("not a datetime", now) # type: ignore
    assert result == {"warm_start_level": "none", "context_depth_modifier": 0}
    assert "Error in gap detector" in caplog.text
