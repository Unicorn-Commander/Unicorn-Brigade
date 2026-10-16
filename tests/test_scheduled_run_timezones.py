"""Regression tests for scheduled-run business timezone defaults and DST."""

from datetime import datetime, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from app.api.scheduled_run_routes import ScheduledRunCreate
from app.core.timezones import BUSINESS_TIMEZONE
from app.db.models import ScheduledRun
from app.services.scheduler import BrigadeScheduler, _parse_cron


def _new_run_body():
    return ScheduledRunCreate(
        name="Daily report",
        agentId="report-agent",
        prompt="prepare the daily report",
        cron="0 2 * * *",
    )


def test_omitted_timezone_schedules_two_am_in_new_york_across_dst():
    body = _new_run_body()
    assert body.timezone == BUSINESS_TIMEZONE

    trigger = _parse_cron(body.cron, body.timezone)
    # 2026-10-31 00:00Z is Oct 30 20:00 EDT, so the next 02:00 ET is Oct 31 (EDT), then Nov 1 (EST).
    cursor = datetime(2026, 10, 31, tzinfo=timezone.utc)
    fires = []
    for _ in range(3):
        cursor = trigger.get_next_fire_time(cursor, cursor)
        fires.append(cursor)

    local_fires = [fire.astimezone(ZoneInfo(BUSINESS_TIMEZONE)) for fire in fires]
    assert [(fire.date().isoformat(), fire.hour) for fire in local_fires] == [
        ("2026-10-31", 2),
        ("2026-11-01", 2),
        ("2026-11-02", 2),
    ]
    assert local_fires[0].utcoffset().total_seconds() == -4 * 60 * 60
    assert local_fires[1].utcoffset().total_seconds() == -5 * 60 * 60


def test_scheduler_registration_defaults_omitted_row_timezone_to_business_zone():
    jobs = []
    scheduler = BrigadeScheduler(object())
    scheduler.scheduler = SimpleNamespace(add_job=lambda *args, **kwargs: jobs.append(kwargs))

    scheduler._register(
        SimpleNamespace(id="run-1", cron="0 2 * * *", timezone=None)
    )

    assert str(jobs[0]["trigger"].timezone) == BUSINESS_TIMEZONE
    assert ScheduledRun.__table__.c.timezone.default.arg == BUSINESS_TIMEZONE
