"""
Google Calendar Integration

Provides calendar functionality via Google Calendar API.
Supports both OAuth2 (user credentials) and Service Account authentication.

Environment Variables:
    OAuth2 Flow (shared with Gmail):
        - GOOGLE_CLIENT_ID: OAuth2 client ID
        - GOOGLE_CLIENT_SECRET: OAuth2 client secret
        - GOOGLE_REFRESH_TOKEN: OAuth2 refresh token
        - GOOGLE_USER_EMAIL: Email address of the user

    Service Account Flow:
        - GOOGLE_SERVICE_ACCOUNT_FILE: Path to service account JSON file
        - GOOGLE_DELEGATED_USER: User email to impersonate (domain-wide delegation)

    Calendar-specific:
        - GOOGLE_CALENDAR_ENABLED: Enable/disable calendar integration
        - GOOGLE_CALENDAR_CREDENTIALS_FILE: Path to credentials file (optional)
"""

import logging
import os
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

from app.core.timezones import BUSINESS_TIMEZONE

load_dotenv()

logger = logging.getLogger(__name__)

# Google API scopes for Calendar
CALENDAR_SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/calendar.readonly",
]

# Environment variables (shared with google_email.py)
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REFRESH_TOKEN = os.getenv("GOOGLE_REFRESH_TOKEN", "")
GOOGLE_USER_EMAIL = os.getenv("GOOGLE_USER_EMAIL", "")

# Service account configuration
GOOGLE_SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "")
GOOGLE_DELEGATED_USER = os.getenv("GOOGLE_DELEGATED_USER", "")

# Calendar-specific configuration
GOOGLE_CALENDAR_ENABLED = os.getenv("GOOGLE_CALENDAR_ENABLED", "false").lower() == "true"
GOOGLE_CALENDAR_CREDENTIALS_FILE = os.getenv(
    "GOOGLE_CALENDAR_CREDENTIALS_FILE", "config/google_calendar_credentials.json"
)

# Token cache for OAuth2 flow
_calendar_token_cache: Dict[str, Any] = {"access_token": None, "expires_at": 0}


class GoogleCalendarClient:
    """
    Google Calendar client supporting OAuth2 and Service Account authentication.

    Provides methods for:
    - Creating calendar events
    - Listing events with filtering
    - Checking availability (free/busy)
    - Updating and deleting events
    - Getting attendee availability
    """

    def __init__(self):
        """Initialize the Google Calendar client."""
        self._credentials = None
        self._service = None
        self._user_email = GOOGLE_USER_EMAIL or GOOGLE_DELEGATED_USER
        self._default_timezone = BUSINESS_TIMEZONE

    def _get_oauth2_credentials(self):
        """
        Get OAuth2 credentials using refresh token.

        Uses client credentials and refresh token to obtain access tokens.
        Tokens are cached and refreshed automatically when expired.
        """
        global _calendar_token_cache

        # Return cached token if still valid (with 60s buffer)
        if (
            _calendar_token_cache["access_token"]
            and _calendar_token_cache["expires_at"] > time.time() + 60
        ):
            from google.oauth2.credentials import Credentials

            return Credentials(
                token=_calendar_token_cache["access_token"],
                refresh_token=GOOGLE_REFRESH_TOKEN,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=GOOGLE_CLIENT_ID,
                client_secret=GOOGLE_CLIENT_SECRET,
                scopes=CALENDAR_SCOPES,
            )

        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials

        creds = Credentials(
            token=None,
            refresh_token=GOOGLE_REFRESH_TOKEN,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=GOOGLE_CLIENT_ID,
            client_secret=GOOGLE_CLIENT_SECRET,
            scopes=CALENDAR_SCOPES,
        )

        # Refresh the token
        creds.refresh(Request())

        # Cache the new token
        _calendar_token_cache["access_token"] = creds.token
        _calendar_token_cache["expires_at"] = time.time() + 3500  # ~1 hour

        logger.info("Google Calendar OAuth2 token refreshed successfully")
        return creds

    def _get_service_account_credentials(self):
        """
        Get credentials using service account with domain-wide delegation.

        Requires a service account JSON file and the user email to impersonate.
        The service account must have domain-wide delegation enabled in Google Admin.
        """
        from google.oauth2 import service_account

        credentials = service_account.Credentials.from_service_account_file(
            GOOGLE_SERVICE_ACCOUNT_FILE,
            scopes=CALENDAR_SCOPES,
        )

        # Delegate to the specified user
        if GOOGLE_DELEGATED_USER:
            credentials = credentials.with_subject(GOOGLE_DELEGATED_USER)

        logger.info(
            f"Calendar service account credentials loaded, delegating to: {GOOGLE_DELEGATED_USER}"
        )
        return credentials

    def _get_credentials(self):
        """Get the appropriate credentials based on configuration."""
        if self._credentials:
            return self._credentials

        # Prefer service account if configured
        if GOOGLE_SERVICE_ACCOUNT_FILE and os.path.exists(GOOGLE_SERVICE_ACCOUNT_FILE):
            self._credentials = self._get_service_account_credentials()
        elif GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET and GOOGLE_REFRESH_TOKEN:
            self._credentials = self._get_oauth2_credentials()
        else:
            raise ValueError(
                "Google credentials not configured. "
                "Set either GOOGLE_SERVICE_ACCOUNT_FILE or "
                "GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, and GOOGLE_REFRESH_TOKEN"
            )

        return self._credentials

    def _get_service(self):
        """Get or create the Google Calendar API service."""
        if self._service:
            return self._service

        from googleapiclient.discovery import build

        credentials = self._get_credentials()
        self._service = build("calendar", "v3", credentials=credentials)

        return self._service

    def _parse_datetime(
        self, dt_str: str, timezone: str = None
    ) -> datetime:
        """
        Parse a datetime string into a datetime object.

        Supports ISO format and common date/time formats.
        """
        tz = ZoneInfo(timezone or self._default_timezone)

        # Try ISO format first
        try:
            if "T" in dt_str:
                if dt_str.endswith("Z"):
                    dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
                else:
                    dt = datetime.fromisoformat(dt_str)
                return self._localize_or_convert(dt, tz)
            else:
                # Date only
                dt = datetime.strptime(dt_str, "%Y-%m-%d")
                return self._localize_or_convert(dt, tz)
        except ValueError:
            pass

        # Try other formats
        formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%m/%d/%Y %H:%M",
            "%m/%d/%Y",
        ]
        for fmt in formats:
            try:
                dt = datetime.strptime(dt_str, fmt)
                return self._localize_or_convert(dt, tz)
            except ValueError:
                continue

        raise ValueError(f"Unable to parse datetime: {dt_str}")

    @staticmethod
    def _localize_or_convert(dt: datetime, tz: ZoneInfo) -> datetime:
        """Attach the requested zone to naive wall time, or convert aware time."""
        if dt.tzinfo is None:
            return dt.replace(tzinfo=tz)
        return dt.astimezone(tz)

    def _format_datetime(self, dt: datetime, timezone: str = None) -> Dict[str, str]:
        """Format datetime for Google Calendar API."""
        tz = timezone or self._default_timezone
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=ZoneInfo(tz))
        return {
            "dateTime": dt.isoformat(),
            "timeZone": tz,
        }

    async def create_event(
        self,
        title: str,
        start_time: str,
        end_time: str,
        attendees: Optional[List[str]] = None,
        description: Optional[str] = None,
        location: Optional[str] = None,
        timezone: str = None,
        send_notifications: bool = True,
        conference_data: bool = False,
        reminders: Optional[Dict[str, Any]] = None,
        calendar_id: str = "primary",
    ) -> Dict[str, Any]:
        """
        Create a calendar event.

        Args:
            title: Event title/summary
            start_time: Start time (ISO format or common formats)
            end_time: End time (ISO format or common formats)
            attendees: List of attendee email addresses
            description: Event description
            location: Event location
            timezone: Timezone for the event (default: America/New_York)
            send_notifications: Send email notifications to attendees
            conference_data: Add Google Meet video conferencing
            reminders: Custom reminders configuration
            calendar_id: Calendar ID (default: 'primary')

        Returns:
            Dict with event details or error
        """
        try:
            service = self._get_service()
            tz = timezone or self._default_timezone

            # Parse times
            start_dt = self._parse_datetime(start_time, tz)
            end_dt = self._parse_datetime(end_time, tz)

            # Build event body
            event = {
                "summary": title,
                "start": self._format_datetime(start_dt, tz),
                "end": self._format_datetime(end_dt, tz),
            }

            if description:
                event["description"] = description

            if location:
                event["location"] = location

            if attendees:
                event["attendees"] = [{"email": email} for email in attendees]

            if reminders:
                event["reminders"] = reminders
            else:
                event["reminders"] = {
                    "useDefault": False,
                    "overrides": [
                        {"method": "email", "minutes": 24 * 60},
                        {"method": "popup", "minutes": 30},
                    ],
                }

            # Conference settings
            conference_version = 0
            if conference_data:
                event["conferenceData"] = {
                    "createRequest": {
                        "requestId": f"meet-{int(time.time())}",
                        "conferenceSolutionKey": {"type": "hangoutsMeet"},
                    }
                }
                conference_version = 1

            # Create the event
            result = (
                service.events()
                .insert(
                    calendarId=calendar_id,
                    body=event,
                    sendNotifications=send_notifications,
                    conferenceDataVersion=conference_version,
                )
                .execute()
            )

            logger.info(f"Calendar event created: {result.get('id')}")

            return {
                "success": True,
                "event_id": result.get("id"),
                "html_link": result.get("htmlLink"),
                "ical_uid": result.get("iCalUID"),
                "hangout_link": result.get("hangoutLink"),
                "conference_data": result.get("conferenceData"),
                "organizer": result.get("organizer", {}).get("email"),
                "status": result.get("status"),
                "start": result.get("start"),
                "end": result.get("end"),
            }

        except Exception as e:
            logger.error(f"Failed to create calendar event: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    async def get_event(
        self, event_id: str, calendar_id: str = "primary"
    ) -> Dict[str, Any]:
        """
        Get a specific calendar event by ID.

        Args:
            event_id: The event ID
            calendar_id: Calendar ID (default: 'primary')

        Returns:
            Dict containing the event data or error
        """
        try:
            service = self._get_service()
            event = (
                service.events()
                .get(calendarId=calendar_id, eventId=event_id)
                .execute()
            )

            return {
                "success": True,
                "event": self._parse_event(event),
                "raw": event,
            }
        except Exception as e:
            logger.error(f"Failed to get event {event_id}: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    async def list_events(
        self,
        time_min: Optional[str] = None,
        time_max: Optional[str] = None,
        max_results: int = 10,
        calendar_id: str = "primary",
        query: Optional[str] = None,
        single_events: bool = True,
        order_by: str = "startTime",
    ) -> Dict[str, Any]:
        """
        List calendar events with optional filtering.

        Args:
            time_min: Lower bound for start time (ISO format)
            time_max: Upper bound for start time (ISO format)
            max_results: Maximum number of events to return
            calendar_id: Calendar ID (default: 'primary')
            query: Free text search query
            single_events: Expand recurring events into instances
            order_by: Order by 'startTime' or 'updated'

        Returns:
            Dict containing list of events or error
        """
        try:
            service = self._get_service()

            # Default to today if no time_min specified
            if not time_min:
                time_min = datetime.now(ZoneInfo(self._default_timezone)).isoformat()

            params = {
                "calendarId": calendar_id,
                "timeMin": time_min,
                "maxResults": max_results,
                "singleEvents": single_events,
                "orderBy": order_by,
            }

            if time_max:
                params["timeMax"] = time_max

            if query:
                params["q"] = query

            results = service.events().list(**params).execute()

            events = [self._parse_event(e) for e in results.get("items", [])]

            return {
                "success": True,
                "events": events,
                "count": len(events),
                "next_page_token": results.get("nextPageToken"),
            }
        except Exception as e:
            logger.error(f"Failed to list events: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    async def update_event(
        self,
        event_id: str,
        title: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        attendees: Optional[List[str]] = None,
        description: Optional[str] = None,
        location: Optional[str] = None,
        timezone: str = None,
        send_notifications: bool = True,
        calendar_id: str = "primary",
    ) -> Dict[str, Any]:
        """
        Update an existing calendar event.

        Args:
            event_id: The event ID to update
            title: New title (optional)
            start_time: New start time (optional)
            end_time: New end time (optional)
            attendees: New list of attendees (optional, replaces existing)
            description: New description (optional)
            location: New location (optional)
            timezone: Timezone for the event
            send_notifications: Send notifications about the update
            calendar_id: Calendar ID (default: 'primary')

        Returns:
            Dict with updated event details or error
        """
        try:
            service = self._get_service()
            tz = timezone or self._default_timezone

            # Get existing event
            event = (
                service.events()
                .get(calendarId=calendar_id, eventId=event_id)
                .execute()
            )

            # Update fields
            if title:
                event["summary"] = title

            if description is not None:
                event["description"] = description

            if location is not None:
                event["location"] = location

            if start_time:
                start_dt = self._parse_datetime(start_time, tz)
                event["start"] = self._format_datetime(start_dt, tz)

            if end_time:
                end_dt = self._parse_datetime(end_time, tz)
                event["end"] = self._format_datetime(end_dt, tz)

            if attendees is not None:
                event["attendees"] = [{"email": email} for email in attendees]

            # Update the event
            result = (
                service.events()
                .update(
                    calendarId=calendar_id,
                    eventId=event_id,
                    body=event,
                    sendNotifications=send_notifications,
                )
                .execute()
            )

            logger.info(f"Calendar event updated: {event_id}")

            return {
                "success": True,
                "event_id": result.get("id"),
                "html_link": result.get("htmlLink"),
                "updated": result.get("updated"),
            }

        except Exception as e:
            logger.error(f"Failed to update event {event_id}: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    async def delete_event(
        self,
        event_id: str,
        send_notifications: bool = True,
        calendar_id: str = "primary",
    ) -> Dict[str, Any]:
        """
        Delete a calendar event.

        Args:
            event_id: The event ID to delete
            send_notifications: Send cancellation notifications
            calendar_id: Calendar ID (default: 'primary')

        Returns:
            Dict with success status
        """
        try:
            service = self._get_service()

            service.events().delete(
                calendarId=calendar_id,
                eventId=event_id,
                sendNotifications=send_notifications,
            ).execute()

            logger.info(f"Calendar event deleted: {event_id}")

            return {
                "success": True,
                "event_id": event_id,
                "message": "Event deleted successfully",
            }

        except Exception as e:
            logger.error(f"Failed to delete event {event_id}: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    async def get_free_busy(
        self,
        attendees: List[str],
        time_min: str,
        time_max: str,
        timezone: str = None,
    ) -> Dict[str, Any]:
        """
        Get free/busy information for a list of attendees.

        Args:
            attendees: List of email addresses to check
            time_min: Start of time range (ISO format)
            time_max: End of time range (ISO format)
            timezone: Timezone for the query

        Returns:
            Dict containing free/busy data per attendee
        """
        try:
            service = self._get_service()
            tz = timezone or self._default_timezone

            body = {
                "timeMin": time_min,
                "timeMax": time_max,
                "timeZone": tz,
                "items": [{"id": email} for email in attendees],
            }

            result = service.freebusy().query(body=body).execute()

            # Parse the results
            calendars = result.get("calendars", {})
            availability = {}

            for email, data in calendars.items():
                busy_periods = data.get("busy", [])
                errors = data.get("errors", [])

                availability[email] = {
                    "busy": busy_periods,
                    "errors": errors,
                    "available": len(busy_periods) == 0 and len(errors) == 0,
                }

            return {
                "success": True,
                "time_min": time_min,
                "time_max": time_max,
                "timezone": tz,
                "calendars": availability,
            }

        except Exception as e:
            logger.error(f"Failed to get free/busy info: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    async def find_available_slots(
        self,
        attendees: List[str],
        duration_minutes: int,
        date_range_start: str,
        date_range_end: str,
        timezone: str = None,
        working_hours_start: int = 9,
        working_hours_end: int = 17,
        exclude_weekends: bool = True,
        buffer_minutes: int = 15,
        max_slots: int = 10,
    ) -> Dict[str, Any]:
        """
        Find available time slots for a meeting across all attendees.

        Args:
            attendees: List of attendee email addresses
            duration_minutes: Required meeting duration in minutes
            date_range_start: Start of date range to search (ISO format)
            date_range_end: End of date range to search (ISO format)
            timezone: Timezone for availability check
            working_hours_start: Start of working hours (0-23)
            working_hours_end: End of working hours (0-23)
            exclude_weekends: Skip Saturday and Sunday
            buffer_minutes: Buffer time between meetings
            max_slots: Maximum number of slots to return

        Returns:
            Dict containing available time slots
        """
        try:
            tz = ZoneInfo(timezone or self._default_timezone)

            # Parse date range
            start_dt = self._parse_datetime(date_range_start, str(tz))
            end_dt = self._parse_datetime(date_range_end, str(tz))

            # Get free/busy info
            freebusy_result = await self.get_free_busy(
                attendees=attendees,
                time_min=start_dt.isoformat(),
                time_max=end_dt.isoformat(),
                timezone=str(tz),
            )

            if not freebusy_result.get("success"):
                return freebusy_result

            # Collect all busy periods
            all_busy = []
            for email, data in freebusy_result.get("calendars", {}).items():
                for busy in data.get("busy", []):
                    busy_start = datetime.fromisoformat(
                        busy["start"].replace("Z", "+00:00")
                    )
                    busy_end = datetime.fromisoformat(
                        busy["end"].replace("Z", "+00:00")
                    )
                    all_busy.append((busy_start, busy_end))

            # Sort busy periods
            all_busy.sort(key=lambda x: x[0])

            # Find available slots
            available_slots = []
            current = start_dt
            duration = timedelta(minutes=duration_minutes)
            buffer = timedelta(minutes=buffer_minutes)

            while current + duration <= end_dt and len(available_slots) < max_slots:
                # Skip weekends if configured
                if exclude_weekends and current.weekday() >= 5:
                    current = current.replace(
                        hour=working_hours_start, minute=0, second=0
                    ) + timedelta(days=1)
                    continue

                # Skip non-working hours
                if current.hour < working_hours_start:
                    current = current.replace(
                        hour=working_hours_start, minute=0, second=0
                    )
                    continue

                if current.hour >= working_hours_end:
                    current = current.replace(
                        hour=working_hours_start, minute=0, second=0
                    ) + timedelta(days=1)
                    continue

                # Check if slot end is within working hours
                slot_end = current + duration
                if slot_end.hour > working_hours_end or (
                    slot_end.hour == working_hours_end and slot_end.minute > 0
                ):
                    current = current.replace(
                        hour=working_hours_start, minute=0, second=0
                    ) + timedelta(days=1)
                    continue

                # Check against busy periods
                slot_available = True
                for busy_start, busy_end in all_busy:
                    # Check if slot overlaps with busy period
                    if not (slot_end <= busy_start or current >= busy_end):
                        slot_available = False
                        # Move to end of busy period plus buffer
                        current = busy_end + buffer
                        break

                if slot_available:
                    available_slots.append(
                        {
                            "start": current.isoformat(),
                            "end": slot_end.isoformat(),
                            "duration_minutes": duration_minutes,
                        }
                    )
                    current = slot_end + buffer
                    continue

            return {
                "success": True,
                "slots": available_slots,
                "count": len(available_slots),
                "attendees": attendees,
                "duration_minutes": duration_minutes,
                "timezone": str(tz),
            }

        except Exception as e:
            logger.error(f"Failed to find available slots: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    def _parse_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse a Calendar event into a more usable format.

        Args:
            event: Raw Calendar API event response

        Returns:
            Parsed event dict with common fields extracted
        """
        # Get start/end times
        start = event.get("start", {})
        end = event.get("end", {})

        # Handle all-day events vs timed events
        start_time = start.get("dateTime") or start.get("date")
        end_time = end.get("dateTime") or end.get("date")
        is_all_day = "date" in start and "dateTime" not in start

        # Get attendees
        attendees = []
        for attendee in event.get("attendees", []):
            attendees.append(
                {
                    "email": attendee.get("email"),
                    "display_name": attendee.get("displayName"),
                    "response_status": attendee.get("responseStatus"),
                    "organizer": attendee.get("organizer", False),
                    "optional": attendee.get("optional", False),
                }
            )

        return {
            "id": event.get("id"),
            "ical_uid": event.get("iCalUID"),
            "title": event.get("summary", ""),
            "description": event.get("description", ""),
            "location": event.get("location", ""),
            "start": start_time,
            "end": end_time,
            "timezone": start.get("timeZone"),
            "is_all_day": is_all_day,
            "status": event.get("status"),
            "html_link": event.get("htmlLink"),
            "hangout_link": event.get("hangoutLink"),
            "organizer": event.get("organizer", {}).get("email"),
            "creator": event.get("creator", {}).get("email"),
            "attendees": attendees,
            "recurrence": event.get("recurrence"),
            "recurring_event_id": event.get("recurringEventId"),
            "created": event.get("created"),
            "updated": event.get("updated"),
        }


# Module-level singleton instance
_client: Optional[GoogleCalendarClient] = None


def get_client() -> GoogleCalendarClient:
    """Get or create the singleton GoogleCalendarClient instance."""
    global _client
    if _client is None:
        _client = GoogleCalendarClient()
    return _client


def is_enabled() -> bool:
    """Check if Google Calendar integration is enabled."""
    return GOOGLE_CALENDAR_ENABLED


# Convenience functions for direct use
async def create_event(
    title: str,
    start_time: str,
    end_time: str,
    attendees: Optional[List[str]] = None,
    description: Optional[str] = None,
    location: Optional[str] = None,
    timezone: str = None,
    send_notifications: bool = True,
    conference_data: bool = False,
) -> Dict[str, Any]:
    """Create a calendar event."""
    return await get_client().create_event(
        title=title,
        start_time=start_time,
        end_time=end_time,
        attendees=attendees,
        description=description,
        location=location,
        timezone=timezone,
        send_notifications=send_notifications,
        conference_data=conference_data,
    )


async def get_event(event_id: str, calendar_id: str = "primary") -> Dict[str, Any]:
    """Get a specific event by ID."""
    return await get_client().get_event(event_id, calendar_id)


async def list_events(
    time_min: Optional[str] = None,
    time_max: Optional[str] = None,
    max_results: int = 10,
    calendar_id: str = "primary",
    query: Optional[str] = None,
) -> Dict[str, Any]:
    """List calendar events."""
    return await get_client().list_events(
        time_min=time_min,
        time_max=time_max,
        max_results=max_results,
        calendar_id=calendar_id,
        query=query,
    )


async def update_event(
    event_id: str,
    title: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    attendees: Optional[List[str]] = None,
    description: Optional[str] = None,
    location: Optional[str] = None,
    send_notifications: bool = True,
) -> Dict[str, Any]:
    """Update a calendar event."""
    return await get_client().update_event(
        event_id=event_id,
        title=title,
        start_time=start_time,
        end_time=end_time,
        attendees=attendees,
        description=description,
        location=location,
        send_notifications=send_notifications,
    )


async def delete_event(
    event_id: str, send_notifications: bool = True
) -> Dict[str, Any]:
    """Delete a calendar event."""
    return await get_client().delete_event(
        event_id=event_id, send_notifications=send_notifications
    )


async def get_free_busy(
    attendees: List[str],
    time_min: str,
    time_max: str,
    timezone: str = None,
) -> Dict[str, Any]:
    """Get free/busy information for attendees."""
    return await get_client().get_free_busy(
        attendees=attendees,
        time_min=time_min,
        time_max=time_max,
        timezone=timezone,
    )


async def find_available_slots(
    attendees: List[str],
    duration_minutes: int,
    date_range_start: str,
    date_range_end: str,
    timezone: str = None,
    working_hours_start: int = 9,
    working_hours_end: int = 17,
    exclude_weekends: bool = True,
    buffer_minutes: int = 15,
    max_slots: int = 10,
) -> Dict[str, Any]:
    """Find available time slots for a meeting."""
    return await get_client().find_available_slots(
        attendees=attendees,
        duration_minutes=duration_minutes,
        date_range_start=date_range_start,
        date_range_end=date_range_end,
        timezone=timezone,
        working_hours_start=working_hours_start,
        working_hours_end=working_hours_end,
        exclude_weekends=exclude_weekends,
        buffer_minutes=buffer_minutes,
        max_slots=max_slots,
    )
