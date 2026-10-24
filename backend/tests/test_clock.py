from datetime import UTC, datetime, timedelta, timezone

import pytest
from app.clock import FakeClock, SystemClock


def test_fake_clock_set_and_advance(clock):
    assert clock.now() == datetime(2026, 1, 15, 9, 0, tzinfo=UTC)
    clock.advance(minutes=15)
    assert clock.now() == datetime(2026, 1, 15, 9, 15, tzinfo=UTC)
    clock.advance(timedelta(days=1))
    assert clock.now() == datetime(2026, 1, 16, 9, 15, tzinfo=UTC)
    clock.set(datetime(2026, 3, 29, 1, 59, tzinfo=UTC))
    assert clock.now().hour == 1


def test_fake_clock_normalizes_to_utc():
    berlin_summer = timezone(timedelta(hours=2))
    clock = FakeClock(datetime(2026, 7, 1, 12, 0, tzinfo=berlin_summer))
    assert clock.now() == datetime(2026, 7, 1, 10, 0, tzinfo=UTC)
    assert clock.now().tzinfo is UTC


def test_fake_clock_rejects_naive_and_backwards(clock):
    with pytest.raises(ValueError):
        FakeClock(datetime(2026, 1, 1))
    with pytest.raises(ValueError):
        clock.set(datetime(2026, 1, 1))
    with pytest.raises(ValueError):
        clock.advance(minutes=-1)


def test_system_clock_is_aware_utc():
    now = SystemClock().now()
    assert now.tzinfo is UTC
