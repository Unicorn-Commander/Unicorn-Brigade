"""Contract tests for Brigade's shared standard-cron parser."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from apscheduler.triggers.combining import OrTrigger

from app.services.cron import parse_cron

NEW_YORK = ZoneInfo("America/New_York")


def _local(year, month, day, hour, minute=0):
    return datetime(year, month, day, hour, minute, tzinfo=NEW_YORK)


def test_numeric_weekdays_use_standard_cron_numbers():
    trigger = parse_cron("40 8 * * 1-5", "America/New_York")
    fire = trigger.get_next_fire_time(None, _local(2026, 10, 24, 16))
    assert fire == _local(2026, 10, 26, 8, 40)


@pytest.mark.parametrize("weekday", ["0", "7"])
def test_both_standard_sunday_numbers_fire_on_sunday(weekday):
    trigger = parse_cron(f"0 9 * * {weekday}", "America/New_York")
    fire = trigger.get_next_fire_time(None, _local(2026, 10, 24, 16))
    assert fire == _local(2026, 10, 25, 9)


def test_restricted_day_of_month_and_weekday_are_or_semantics():
    trigger = parse_cron("0 9 1 * 1", "America/New_York")
    assert isinstance(trigger, OrTrigger)
    cursor = _local(2026, 10, 24, 0)
    previous = None
    fires = []
    for _ in range(4):
        fire = trigger.get_next_fire_time(previous, cursor)
        fires.append(fire.date().isoformat())
        previous = fire
        cursor = fire + timedelta(microseconds=1)
    assert fires == ["2026-10-26", "2026-11-01", "2026-11-02", "2026-11-09"]


def test_named_weekdays_keep_working():
    trigger = parse_cron("0 9 * * mon-fri", "America/New_York")
    fire = trigger.get_next_fire_time(None, _local(2026, 10, 24, 16))
    assert fire == _local(2026, 10, 26, 9)

    sunday = parse_cron("0 9 * * sun", "America/New_York")
    assert sunday.get_next_fire_time(None, _local(2026, 10, 24, 16)) == _local(2026, 10, 25, 9)


def test_invalid_weekday_is_rejected_with_a_clear_error():
    with pytest.raises(ValueError, match=r"day-of-week.*8.*out of range"):
        parse_cron("* * * * 8", "UTC")
