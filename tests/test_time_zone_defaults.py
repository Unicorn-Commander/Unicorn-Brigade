"""Regression tests for the application's business timezone defaults."""

import inspect

from app.agents.meeting_scheduler import DEFAULT_PREFERENCES, MeetingRequest
from app.api import calendar_routes
from app.api.calendar_routes import AvailabilityRequest, CreateEventRequest, FindSlotsRequest
from app.integrations.google_calendar import GoogleCalendarClient


BUSINESS_TIMEZONE = "America/New_York"


def test_calendar_defaults_use_business_timezone():
    assert AvailabilityRequest(attendees=["person@example.com"]).timezone == BUSINESS_TIMEZONE
    assert FindSlotsRequest(attendees=["person@example.com"]).timezone == BUSINESS_TIMEZONE
    assert CreateEventRequest(
        title="Planning",
        start_time="2026-10-16T09:30",
        end_time="2026-10-16T10:00",
    ).timezone == BUSINESS_TIMEZONE
    assert GoogleCalendarClient()._default_timezone == BUSINESS_TIMEZONE

    query_default = inspect.signature(calendar_routes.api_check_availability).parameters[
        "timezone"
    ].default.default
    assert query_default == BUSINESS_TIMEZONE


def test_meeting_scheduler_preference_defaults_use_business_timezone():
    assert DEFAULT_PREFERENCES["timezone"] == BUSINESS_TIMEZONE
    assert MeetingRequest().timezone == BUSINESS_TIMEZONE
