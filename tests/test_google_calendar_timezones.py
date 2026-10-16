"""Regression tests for explicit Google Calendar timezone parsing."""

from datetime import datetime
import os
import time
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest

from app.integrations.google_calendar import GoogleCalendarClient


@pytest.fixture(autouse=True)
def host_timezone_is_utc(monkeypatch):
    """Make the pre-fix naive ``astimezone`` behavior deterministic."""
    original_tz = os.environ.get("TZ")
    monkeypatch.setenv("TZ", "UTC")
    time.tzset()
    yield
    if original_tz is None:
        monkeypatch.delenv("TZ", raising=False)
    else:
        monkeypatch.setenv("TZ", original_tz)
    time.tzset()


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (
            "2026-10-16T09:30",
            datetime(2026, 10, 16, 9, 30, tzinfo=ZoneInfo("America/New_York")),
        ),
        (
            "2026-12-16T09:30",
            datetime(2026, 12, 16, 9, 30, tzinfo=ZoneInfo("America/New_York")),
        ),
    ],
)
def test_naive_iso_datetime_is_wall_time_in_requested_timezone(value, expected):
    client = GoogleCalendarClient()

    parsed = client._parse_datetime(value, "America/New_York")

    assert parsed == expected


def test_naive_common_format_and_date_only_use_requested_timezone():
    client = GoogleCalendarClient()
    timezone = "America/New_York"

    assert client._parse_datetime("2026-10-16 09:30", timezone).hour == 9
    assert client._parse_datetime("2026-10-16", timezone) == datetime(
        2026, 10, 16, tzinfo=ZoneInfo(timezone)
    )


@pytest.mark.asyncio
async def test_create_event_uses_requested_wall_time_without_calling_google():
    client = GoogleCalendarClient()
    service = MagicMock()
    service.events.return_value.insert.return_value.execute.return_value = {
        "id": "event-1"
    }
    client._service = service

    result = await client.create_event(
        title="Planning",
        start_time="2026-10-16T09:30",
        end_time="2026-10-16T10:00",
        timezone="America/New_York",
    )

    body = service.events.return_value.insert.call_args.kwargs["body"]
    assert result["success"] is True
    assert body["start"] == {
        "dateTime": "2026-10-16T09:30:00-04:00",
        "timeZone": "America/New_York",
    }
