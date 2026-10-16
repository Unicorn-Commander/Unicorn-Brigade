"""
Calendar API Routes

REST API endpoints for meeting scheduling operations.

Endpoints:
- POST /api/v1/calendar/schedule - Schedule a meeting from natural language
- GET /api/v1/calendar/availability - Check availability for attendees
- POST /api/v1/calendar/reschedule - Reschedule an existing meeting
- DELETE /api/v1/calendar/meeting/{id} - Cancel a meeting
- GET /api/v1/calendar/events - List calendar events
- GET /api/v1/calendar/meeting/{id} - Get meeting details
- POST /api/v1/calendar/find-slots - Find available time slots
- GET /api/v1/calendar/health - Calendar service health check
"""

import logging
from datetime import datetime, timedelta
from typing import Annotated, Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field, field_validator

from app.agents.meeting_scheduler import (
    MeetingScheduler,
    get_scheduler,
    schedule_meeting,
    parse_meeting_request,
    check_availability,
    find_meeting_slots,
    cancel_meeting,
    reschedule_meeting,
)
from app.integrations import google_calendar
from app.auth.middleware import require_api_key, require_operator, AuthUser
from app.core.timezones import BUSINESS_TIMEZONE

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/calendar", tags=["calendar"])

# Pydantic models for request/response validation


class ScheduleMeetingRequest(BaseModel):
    """Request model for scheduling a meeting from natural language."""

    message: str = Field(
        ...,
        description="Natural language meeting request",
        examples=[
            "Schedule a 30-minute meeting with john@example.com tomorrow at 2pm to discuss project updates"
        ],
    )
    preferences: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional scheduling preferences override",
        examples=[
            {
                "preferred_times": ["morning"],
                "working_hours_start": 9,
                "working_hours_end": 17,
                "buffer_minutes": 15,
            }
        ],
    )


class ScheduleMeetingResponse(BaseModel):
    """Response model for scheduled meeting."""

    success: bool
    event_id: Optional[str] = None
    html_link: Optional[str] = None
    hangout_link: Optional[str] = None
    start: Optional[Dict[str, str]] = None
    end: Optional[Dict[str, str]] = None
    parsed_request: Optional[Dict[str, Any]] = None
    chosen_slot: Optional[Dict[str, Any]] = None
    alternative_slots: Optional[List[Dict[str, Any]]] = None
    error: Optional[str] = None


class AvailabilityRequest(BaseModel):
    """Request model for checking availability."""

    attendees: List[str] = Field(
        ...,
        description="List of attendee email addresses",
        examples=[["john@example.com", "jane@example.com"]],
    )
    duration_minutes: int = Field(
        default=30,
        description="Meeting duration in minutes",
        ge=15,
        le=480,
    )
    date_start: Optional[str] = Field(
        default=None,
        description="Start of date range (ISO format or YYYY-MM-DD)",
    )
    date_end: Optional[str] = Field(
        default=None,
        description="End of date range (ISO format or YYYY-MM-DD)",
    )
    timezone: str = Field(
        default=BUSINESS_TIMEZONE,
        description="Timezone for the availability check",
    )


class AvailabilityResponse(BaseModel):
    """Response model for availability check."""

    success: bool
    calendars: Optional[Dict[str, Any]] = None
    time_min: Optional[str] = None
    time_max: Optional[str] = None
    timezone: Optional[str] = None
    error: Optional[str] = None


class FindSlotsRequest(BaseModel):
    """Request model for finding available time slots."""

    attendees: List[str] = Field(
        ...,
        description="List of attendee email addresses",
    )
    duration_minutes: int = Field(
        default=30,
        description="Meeting duration in minutes",
        ge=15,
        le=480,
    )
    date_start: Optional[str] = Field(
        default=None,
        description="Start of date range to search",
    )
    date_end: Optional[str] = Field(
        default=None,
        description="End of date range to search",
    )
    timezone: str = Field(
        default=BUSINESS_TIMEZONE,
        description="Timezone for the search",
    )
    preferences: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Scheduling preferences",
    )


class FindSlotsResponse(BaseModel):
    """Response model for available time slots."""

    success: bool
    slots: Optional[List[Dict[str, Any]]] = None
    count: Optional[int] = None
    attendees: Optional[List[str]] = None
    duration_minutes: Optional[int] = None
    preferences_applied: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class RescheduleRequest(BaseModel):
    """Request model for rescheduling a meeting."""

    event_id: str = Field(
        ...,
        description="The calendar event ID to reschedule",
    )
    new_start_time: str = Field(
        ...,
        description="New start time (ISO format)",
    )
    new_end_time: Optional[str] = Field(
        default=None,
        description="New end time (ISO format). If not provided, duration is preserved.",
    )
    send_notifications: bool = Field(
        default=True,
        description="Send update notifications to attendees",
    )


class RescheduleResponse(BaseModel):
    """Response model for reschedule operation."""

    success: bool
    event_id: Optional[str] = None
    html_link: Optional[str] = None
    updated: Optional[str] = None
    error: Optional[str] = None


class CancelResponse(BaseModel):
    """Response model for cancel operation."""

    success: bool
    event_id: Optional[str] = None
    message: Optional[str] = None
    error: Optional[str] = None


class EventResponse(BaseModel):
    """Response model for a single event."""

    success: bool
    event: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class EventListResponse(BaseModel):
    """Response model for event list."""

    success: bool
    events: Optional[List[Dict[str, Any]]] = None
    count: Optional[int] = None
    next_page_token: Optional[str] = None
    error: Optional[str] = None


class ParseRequest(BaseModel):
    """Request model for parsing a meeting request."""

    message: str = Field(
        ...,
        description="Natural language meeting request to parse",
    )


class ParseResponse(BaseModel):
    """Response model for parsed meeting request."""

    success: bool
    parsed_request: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class HealthResponse(BaseModel):
    """Response model for health check."""

    status: str
    enabled: bool
    message: str


class CreateEventRequest(BaseModel):
    """Request model for creating a calendar event directly."""

    title: str = Field(..., description="Event title")
    start_time: str = Field(..., description="Start time (ISO format)")
    end_time: str = Field(..., description="End time (ISO format)")
    attendees: Optional[List[str]] = Field(
        default=None, description="List of attendee emails"
    )
    description: Optional[str] = Field(default=None, description="Event description")
    location: Optional[str] = Field(default=None, description="Event location")
    timezone: str = Field(default=BUSINESS_TIMEZONE, description="Timezone")
    add_video: bool = Field(
        default=False, description="Add Google Meet video conferencing"
    )
    send_notifications: bool = Field(
        default=True, description="Send notifications to attendees"
    )


# Routes


@router.get("/health", response_model=HealthResponse)
async def calendar_health():
    """
    Check calendar service health.

    Returns the status of the Google Calendar integration.
    """
    enabled = google_calendar.is_enabled()

    if not enabled:
        return HealthResponse(
            status="disabled",
            enabled=False,
            message="Google Calendar integration is disabled. Set GOOGLE_CALENDAR_ENABLED=true",
        )

    # Try to get credentials
    try:
        client = google_calendar.get_client()
        client._get_credentials()
        return HealthResponse(
            status="healthy",
            enabled=True,
            message="Google Calendar integration is configured and ready",
        )
    except Exception as e:
        return HealthResponse(
            status="unhealthy",
            enabled=True,
            message=f"Calendar credentials error: {str(e)}",
        )


@router.post("/schedule", response_model=ScheduleMeetingResponse)
async def api_schedule_meeting(
    request: ScheduleMeetingRequest,
    user: Annotated[AuthUser, Depends(require_operator)] = None,
):
    """
    Schedule a meeting from natural language.

    Parses the natural language request, finds available time slots,
    and creates a calendar event with invitations.

    Example requests:
    - "Schedule a 30-minute meeting with john@example.com tomorrow at 2pm"
    - "Set up a video call with team@company.com next Monday morning"
    - "Book a 1-hour meeting with alice@example.com and bob@example.com this week"
    """
    try:
        scheduler = get_scheduler()

        # Apply preferences if provided
        if request.preferences:
            scheduler.preferences.update(request.preferences)

        result = await scheduler.execute(
            {"action": "schedule", "message": request.message}
        )

        return ScheduleMeetingResponse(**result)

    except Exception as e:
        logger.error(f"Error scheduling meeting: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/parse", response_model=ParseResponse)
async def api_parse_request(
    request: ParseRequest,
    user: Annotated[AuthUser, Depends(require_operator)] = None,
):
    """
    Parse a meeting request without creating it.

    Extracts meeting details from natural language for preview/validation.
    """
    try:
        result = await parse_meeting_request(request.message)
        return ParseResponse(**result)
    except Exception as e:
        logger.error(f"Error parsing meeting request: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/availability", response_model=AvailabilityResponse)
async def api_check_availability(
    attendees: str = Query(
        ...,
        description="Comma-separated list of attendee email addresses",
    ),
    duration_minutes: int = Query(default=30, ge=15, le=480),
    date_start: Optional[str] = Query(default=None),
    date_end: Optional[str] = Query(default=None),
    timezone: str = Query(default=BUSINESS_TIMEZONE),
    user: Annotated[AuthUser, Depends(require_api_key)] = None,
):
    """
    Check availability for a list of attendees.

    Returns free/busy information for the specified time range.
    """
    try:
        attendee_list = [e.strip() for e in attendees.split(",") if e.strip()]

        if not attendee_list:
            raise HTTPException(status_code=400, detail="No valid attendees provided")

        # Set default date range if not provided
        tz = ZoneInfo(timezone)
        now = datetime.now(tz)

        if not date_start:
            date_start = now.isoformat()
        if not date_end:
            date_end = (now + timedelta(days=7)).isoformat()

        date_range = (date_start, date_end) if date_start and date_end else None

        result = await check_availability(
            attendees=attendee_list,
            duration_minutes=duration_minutes,
            date_range=date_range,
        )

        return AvailabilityResponse(**result)

    except Exception as e:
        logger.error(f"Error checking availability: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/availability", response_model=AvailabilityResponse)
async def api_check_availability_post(
    request: AvailabilityRequest,
    user: Annotated[AuthUser, Depends(require_operator)] = None,
):
    """
    Check availability for a list of attendees (POST version).

    Returns free/busy information for the specified time range.
    """
    try:
        # Set default date range if not provided
        tz = ZoneInfo(request.timezone)
        now = datetime.now(tz)

        date_start = request.date_start or now.isoformat()
        date_end = request.date_end or (now + timedelta(days=7)).isoformat()

        date_range = (date_start, date_end)

        result = await check_availability(
            attendees=request.attendees,
            duration_minutes=request.duration_minutes,
            date_range=date_range,
        )

        return AvailabilityResponse(**result)

    except Exception as e:
        logger.error(f"Error checking availability: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/find-slots", response_model=FindSlotsResponse)
async def api_find_slots(
    request: FindSlotsRequest,
    user: Annotated[AuthUser, Depends(require_operator)] = None,
):
    """
    Find available time slots for a meeting.

    Searches for mutually available times across all attendees,
    ranked by scheduling preferences.
    """
    try:
        # Set default date range if not provided
        tz = ZoneInfo(request.timezone)
        now = datetime.now(tz)

        date_start = request.date_start or now.isoformat()
        date_end = request.date_end or (now + timedelta(days=14)).isoformat()

        date_range = (date_start, date_end)

        result = await find_meeting_slots(
            attendees=request.attendees,
            duration_minutes=request.duration_minutes,
            date_range=date_range,
            preferences=request.preferences,
        )

        return FindSlotsResponse(**result)

    except Exception as e:
        logger.error(f"Error finding slots: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reschedule", response_model=RescheduleResponse)
async def api_reschedule_meeting(
    request: RescheduleRequest,
    user: Annotated[AuthUser, Depends(require_operator)] = None,
):
    """
    Reschedule an existing meeting.

    Updates the meeting time and sends notifications to attendees.
    """
    try:
        result = await reschedule_meeting(
            event_id=request.event_id,
            new_start_time=request.new_start_time,
            new_end_time=request.new_end_time,
        )

        return RescheduleResponse(**result)

    except Exception as e:
        logger.error(f"Error rescheduling meeting: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/meeting/{event_id}", response_model=CancelResponse)
async def api_cancel_meeting(
    event_id: str,
    send_notifications: bool = Query(default=True),
    user: Annotated[AuthUser, Depends(require_operator)] = None,
):
    """
    Cancel a scheduled meeting.

    Deletes the calendar event and optionally sends cancellation
    notifications to attendees.
    """
    try:
        result = await cancel_meeting(
            event_id=event_id,
            send_notifications=send_notifications,
        )

        return CancelResponse(**result)

    except Exception as e:
        logger.error(f"Error canceling meeting: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/meeting/{event_id}", response_model=EventResponse)
async def api_get_meeting(
    event_id: str,
    calendar_id: str = Query(default="primary"),
    user: Annotated[AuthUser, Depends(require_api_key)] = None,
):
    """
    Get details of a specific meeting.
    """
    try:
        result = await google_calendar.get_event(
            event_id=event_id,
            calendar_id=calendar_id,
        )

        return EventResponse(**result)

    except Exception as e:
        logger.error(f"Error getting meeting: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/events", response_model=EventListResponse)
async def api_list_events(
    time_min: Optional[str] = Query(default=None),
    time_max: Optional[str] = Query(default=None),
    max_results: int = Query(default=10, ge=1, le=100),
    calendar_id: str = Query(default="primary"),
    query: Optional[str] = Query(default=None),
    user: Annotated[AuthUser, Depends(require_api_key)] = None,
):
    """
    List calendar events.

    Returns events within the specified time range.
    """
    try:
        result = await google_calendar.list_events(
            time_min=time_min,
            time_max=time_max,
            max_results=max_results,
            calendar_id=calendar_id,
            query=query,
        )

        return EventListResponse(**result)

    except Exception as e:
        logger.error(f"Error listing events: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/events", response_model=ScheduleMeetingResponse)
async def api_create_event(
    request: CreateEventRequest,
    user: Annotated[AuthUser, Depends(require_operator)] = None,
):
    """
    Create a calendar event directly.

    Creates an event with the specified details without
    natural language parsing.
    """
    try:
        result = await google_calendar.create_event(
            title=request.title,
            start_time=request.start_time,
            end_time=request.end_time,
            attendees=request.attendees,
            description=request.description,
            location=request.location,
            timezone=request.timezone,
            send_notifications=request.send_notifications,
            conference_data=request.add_video,
        )

        return ScheduleMeetingResponse(**result)

    except Exception as e:
        logger.error(f"Error creating event: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Initialize routes (called from main.py)
def init_calendar_routes():
    """Initialize calendar routes."""
    logger.info("Calendar routes initialized")
