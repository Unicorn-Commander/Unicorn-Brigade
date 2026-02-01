"""
Meeting Scheduler Agent

A specialized agent for parsing meeting requests from natural language,
checking calendar availability, finding optimal meeting times, and
creating/managing calendar events.

Features:
- Natural language parsing of meeting requests
- Calendar availability checking via Google Calendar API
- Optimal time slot finding across multiple participants
- Meeting creation with invites and Google Meet links
- Rescheduling and cancellation support
- Timezone handling
- Configurable preferences (working hours, buffers, etc.)
"""

import logging
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from app.agents.base import BaseAgent
from app.integrations import google_calendar

logger = logging.getLogger(__name__)


# Default meeting preferences
DEFAULT_PREFERENCES = {
    "preferred_times": ["morning", "afternoon"],  # morning, afternoon, evening
    "working_hours_start": 9,
    "working_hours_end": 17,
    "no_meetings_after": 18,  # No meetings scheduled after this hour
    "buffer_minutes": 15,  # Buffer between meetings
    "default_duration": 30,  # Default meeting duration in minutes
    "timezone": "America/Los_Angeles",
    "exclude_weekends": True,
    "prefer_earlier": True,  # Prefer earlier slots when finding times
    "max_slots_to_show": 5,  # Maximum number of time slots to suggest
}

# Time preference mappings (hour ranges)
TIME_PREFERENCES = {
    "morning": (9, 12),
    "afternoon": (12, 17),
    "evening": (17, 20),
    "early_morning": (7, 9),
    "late_afternoon": (15, 17),
}

# Duration keywords mapping
DURATION_KEYWORDS = {
    "quick": 15,
    "brief": 15,
    "short": 15,
    "half hour": 30,
    "30 min": 30,
    "30 minutes": 30,
    "hour": 60,
    "1 hour": 60,
    "one hour": 60,
    "90 min": 90,
    "90 minutes": 90,
    "1.5 hours": 90,
    "2 hours": 120,
    "two hours": 120,
}


class MeetingRequest:
    """Parsed meeting request from natural language."""

    def __init__(
        self,
        title: Optional[str] = None,
        attendees: Optional[List[str]] = None,
        duration_minutes: int = 30,
        preferred_date: Optional[str] = None,
        preferred_time: Optional[str] = None,
        preferred_time_of_day: Optional[str] = None,
        location: Optional[str] = None,
        description: Optional[str] = None,
        add_video: bool = False,
        timezone: str = "America/Los_Angeles",
        urgency: str = "normal",  # normal, urgent, flexible
        raw_text: str = "",
    ):
        self.title = title
        self.attendees = attendees or []
        self.duration_minutes = duration_minutes
        self.preferred_date = preferred_date
        self.preferred_time = preferred_time
        self.preferred_time_of_day = preferred_time_of_day
        self.location = location
        self.description = description
        self.add_video = add_video
        self.timezone = timezone
        self.urgency = urgency
        self.raw_text = raw_text

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "attendees": self.attendees,
            "duration_minutes": self.duration_minutes,
            "preferred_date": self.preferred_date,
            "preferred_time": self.preferred_time,
            "preferred_time_of_day": self.preferred_time_of_day,
            "location": self.location,
            "description": self.description,
            "add_video": self.add_video,
            "timezone": self.timezone,
            "urgency": self.urgency,
        }


class MeetingScheduler(BaseAgent):
    """
    Meeting Scheduler Agent

    Parses natural language meeting requests, checks calendar availability,
    finds optimal meeting times, and creates calendar events.
    """

    def __init__(
        self,
        name: str = "meeting-scheduler",
        memory_manager=None,
        preferences: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(name=name, memory_manager=memory_manager)
        self.preferences = {**DEFAULT_PREFERENCES, **(preferences or {})}
        self._calendar_client = None

    @property
    def calendar_client(self) -> google_calendar.GoogleCalendarClient:
        """Get or create the calendar client."""
        if self._calendar_client is None:
            self._calendar_client = google_calendar.get_client()
        return self._calendar_client

    async def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a scheduling task.

        The task dict should contain:
        - action: 'schedule', 'reschedule', 'cancel', 'check_availability', 'find_slots'
        - message: Natural language input (for schedule action)
        - event_id: Event ID (for reschedule/cancel)
        - Other action-specific parameters
        """
        action = task.get("action", "schedule")

        try:
            if action == "schedule":
                return await self._handle_schedule(task)
            elif action == "reschedule":
                return await self._handle_reschedule(task)
            elif action == "cancel":
                return await self._handle_cancel(task)
            elif action == "check_availability":
                return await self._handle_check_availability(task)
            elif action == "find_slots":
                return await self._handle_find_slots(task)
            elif action == "parse":
                return await self._handle_parse(task)
            else:
                return {
                    "success": False,
                    "error": f"Unknown action: {action}",
                }

        except Exception as e:
            logger.error(f"Meeting scheduler error: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    def parse_request(self, message: str) -> MeetingRequest:
        """
        Parse a natural language meeting request.

        Extracts:
        - Meeting title/purpose
        - Attendees (email addresses)
        - Duration
        - Preferred date/time
        - Location
        - Video conference request

        Args:
            message: Natural language meeting request

        Returns:
            MeetingRequest object with parsed details
        """
        request = MeetingRequest(raw_text=message)
        message_lower = message.lower()

        # Extract email addresses (attendees)
        email_pattern = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
        emails = re.findall(email_pattern, message)
        request.attendees = list(set(emails))

        # Extract duration
        request.duration_minutes = self._extract_duration(message_lower)

        # Extract date
        request.preferred_date = self._extract_date(message_lower)

        # Extract time
        time_info = self._extract_time(message_lower)
        request.preferred_time = time_info.get("specific_time")
        request.preferred_time_of_day = time_info.get("time_of_day")

        # Check for video conference keywords
        video_keywords = [
            "video",
            "zoom",
            "meet",
            "google meet",
            "video call",
            "virtual",
            "online",
            "remote",
        ]
        request.add_video = any(kw in message_lower for kw in video_keywords)

        # Extract location (if not video)
        if not request.add_video:
            request.location = self._extract_location(message)

        # Extract meeting title/purpose
        request.title = self._extract_title(message, request.attendees)

        # Check urgency
        urgent_keywords = ["urgent", "asap", "immediately", "emergency", "critical"]
        flexible_keywords = ["flexible", "whenever", "anytime", "no rush"]

        if any(kw in message_lower for kw in urgent_keywords):
            request.urgency = "urgent"
        elif any(kw in message_lower for kw in flexible_keywords):
            request.urgency = "flexible"

        # Set timezone from preferences
        request.timezone = self.preferences.get("timezone", "America/Los_Angeles")

        return request

    def _extract_duration(self, message: str) -> int:
        """Extract meeting duration from message."""
        # Check for known duration keywords
        for keyword, duration in DURATION_KEYWORDS.items():
            if keyword in message:
                return duration

        # Try to find numeric durations
        patterns = [
            r"(\d+)\s*(?:min(?:ute)?s?)",  # "30 min", "30 minutes"
            r"(\d+)\s*(?:hour|hr)s?",  # "1 hour", "2 hours"
        ]

        for pattern in patterns:
            match = re.search(pattern, message)
            if match:
                value = int(match.group(1))
                if "hour" in pattern or "hr" in pattern:
                    return value * 60
                return value

        # Default duration
        return self.preferences.get("default_duration", 30)

    def _extract_date(self, message: str) -> Optional[str]:
        """Extract preferred date from message."""
        tz = ZoneInfo(self.preferences.get("timezone", "America/Los_Angeles"))
        now = datetime.now(tz)

        # Relative date keywords
        if "today" in message:
            return now.strftime("%Y-%m-%d")
        elif "tomorrow" in message:
            return (now + timedelta(days=1)).strftime("%Y-%m-%d")
        elif "next week" in message:
            # Start of next week (Monday)
            days_until_monday = (7 - now.weekday()) % 7
            if days_until_monday == 0:
                days_until_monday = 7
            return (now + timedelta(days=days_until_monday)).strftime("%Y-%m-%d")
        elif "this week" in message:
            return now.strftime("%Y-%m-%d")

        # Day of week
        days = [
            "monday",
            "tuesday",
            "wednesday",
            "thursday",
            "friday",
            "saturday",
            "sunday",
        ]
        for i, day in enumerate(days):
            if day in message:
                current_day = now.weekday()
                days_ahead = i - current_day
                if days_ahead <= 0:  # Target day already passed this week
                    days_ahead += 7
                return (now + timedelta(days=days_ahead)).strftime("%Y-%m-%d")

        # Try to find specific dates
        date_patterns = [
            r"(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?",  # MM/DD or MM/DD/YYYY
            r"(\d{4})-(\d{2})-(\d{2})",  # YYYY-MM-DD
            r"(\w+)\s+(\d{1,2})(?:st|nd|rd|th)?(?:,?\s*(\d{4}))?",  # January 15, 2024
        ]

        # Month names for pattern matching
        months = {
            "january": 1,
            "february": 2,
            "march": 3,
            "april": 4,
            "may": 5,
            "june": 6,
            "july": 7,
            "august": 8,
            "september": 9,
            "october": 10,
            "november": 11,
            "december": 12,
            "jan": 1,
            "feb": 2,
            "mar": 3,
            "apr": 4,
            "jun": 6,
            "jul": 7,
            "aug": 8,
            "sep": 9,
            "oct": 10,
            "nov": 11,
            "dec": 12,
        }

        # Check for month day format
        for month_name, month_num in months.items():
            pattern = rf"{month_name}\s+(\d{{1,2}})(?:st|nd|rd|th)?(?:,?\s*(\d{{4}}))?"
            match = re.search(pattern, message)
            if match:
                day = int(match.group(1))
                year = int(match.group(2)) if match.group(2) else now.year
                return f"{year}-{month_num:02d}-{day:02d}"

        # Default to None (will search within a reasonable range)
        return None

    def _extract_time(self, message: str) -> Dict[str, Optional[str]]:
        """Extract preferred time from message."""
        result = {"specific_time": None, "time_of_day": None}

        # Time of day preferences
        for time_pref in TIME_PREFERENCES.keys():
            if time_pref.replace("_", " ") in message:
                result["time_of_day"] = time_pref
                break

        # Specific time patterns
        time_patterns = [
            r"(\d{1,2}):(\d{2})\s*(am|pm)?",  # 10:30am, 2:00 pm
            r"(\d{1,2})\s*(am|pm)",  # 10am, 2pm
            r"at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?",  # at 10, at 2:30pm
        ]

        for pattern in time_patterns:
            match = re.search(pattern, message)
            if match:
                hour = int(match.group(1))
                minute = int(match.group(2)) if match.group(2) and match.group(2).isdigit() else 0

                # Handle AM/PM
                if len(match.groups()) >= 3:
                    period = match.group(3) if match.group(3) else match.group(2)
                    if isinstance(period, str):
                        period = period.lower()
                        if period == "pm" and hour < 12:
                            hour += 12
                        elif period == "am" and hour == 12:
                            hour = 0

                result["specific_time"] = f"{hour:02d}:{minute:02d}"
                break

        return result

    def _extract_location(self, message: str) -> Optional[str]:
        """Extract meeting location from message."""
        # Look for location indicators
        location_patterns = [
            r"(?:at|in|location:?)\s+([A-Z][a-zA-Z\s]+(?:Room|Conference|Office|Building)?(?:\s+\d+)?)",
            r"(?:meet at|meeting at)\s+(.+?)(?:\s+(?:at|on|for)|$)",
        ]

        for pattern in location_patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                location = match.group(1).strip()
                # Don't return if it looks like a time
                if not any(
                    kw in location.lower()
                    for kw in ["am", "pm", "morning", "afternoon", "evening"]
                ):
                    return location

        return None

    def _extract_title(self, message: str, attendees: List[str]) -> str:
        """Extract meeting title/purpose from message."""
        # Common meeting purpose keywords
        purpose_patterns = [
            r"(?:schedule|set up|book|create)\s+(?:a\s+)?(.+?)(?:\s+with|\s+for|\s+meeting)?",
            r"(?:meeting|call)\s+(?:about|regarding|for|to discuss)\s+(.+?)(?:\s+with|$)",
            r"discuss(?:ion)?\s+(?:about|on)?\s*(.+?)(?:\s+with|$)",
        ]

        for pattern in purpose_patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                title = match.group(1).strip()
                # Clean up the title
                title = re.sub(r"\s+", " ", title)
                # Remove email addresses from title
                for email in attendees:
                    title = title.replace(email, "").strip()
                if title and len(title) > 3:
                    return title

        # Default title
        if attendees:
            return f"Meeting with {', '.join(attendees[:2])}"
        return "Meeting"

    async def check_availability(
        self,
        attendees: List[str],
        duration_minutes: int,
        date_range: Optional[Tuple[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Check calendar availability for a list of attendees.

        Args:
            attendees: List of attendee email addresses
            duration_minutes: Required meeting duration
            date_range: Optional (start, end) date range tuple

        Returns:
            Dict with availability information
        """
        tz = ZoneInfo(self.preferences.get("timezone", "America/Los_Angeles"))
        now = datetime.now(tz)

        # Default date range: next 7 days
        if date_range:
            time_min, time_max = date_range
        else:
            time_min = now.isoformat()
            time_max = (now + timedelta(days=7)).isoformat()

        return await self.calendar_client.get_free_busy(
            attendees=attendees,
            time_min=time_min,
            time_max=time_max,
            timezone=str(tz),
        )

    async def find_optimal_time(
        self,
        attendees: List[str],
        duration_minutes: int,
        date_range: Optional[Tuple[str, str]] = None,
        preferences: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Find optimal meeting times based on availability and preferences.

        Args:
            attendees: List of attendee email addresses
            duration_minutes: Required meeting duration
            date_range: Optional (start, end) date range tuple
            preferences: Optional preferences override

        Returns:
            Dict with ranked time slots
        """
        prefs = {**self.preferences, **(preferences or {})}
        tz = ZoneInfo(prefs.get("timezone", "America/Los_Angeles"))
        now = datetime.now(tz)

        # Set date range
        if date_range:
            time_min, time_max = date_range
        else:
            time_min = now.isoformat()
            time_max = (now + timedelta(days=14)).isoformat()

        # Find available slots
        result = await self.calendar_client.find_available_slots(
            attendees=attendees,
            duration_minutes=duration_minutes,
            date_range_start=time_min,
            date_range_end=time_max,
            timezone=str(tz),
            working_hours_start=prefs.get("working_hours_start", 9),
            working_hours_end=prefs.get("working_hours_end", 17),
            exclude_weekends=prefs.get("exclude_weekends", True),
            buffer_minutes=prefs.get("buffer_minutes", 15),
            max_slots=prefs.get("max_slots_to_show", 5) * 2,  # Get more to rank
        )

        if not result.get("success"):
            return result

        slots = result.get("slots", [])

        # Rank slots based on preferences
        ranked_slots = self._rank_slots(slots, prefs)

        return {
            "success": True,
            "slots": ranked_slots[: prefs.get("max_slots_to_show", 5)],
            "count": len(ranked_slots),
            "attendees": attendees,
            "duration_minutes": duration_minutes,
            "preferences_applied": {
                "preferred_times": prefs.get("preferred_times"),
                "prefer_earlier": prefs.get("prefer_earlier"),
            },
        }

    def _rank_slots(
        self, slots: List[Dict[str, Any]], preferences: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Rank time slots based on preferences."""
        preferred_times = preferences.get("preferred_times", ["morning", "afternoon"])
        prefer_earlier = preferences.get("prefer_earlier", True)
        no_meetings_after = preferences.get("no_meetings_after", 18)

        scored_slots = []

        for slot in slots:
            start = datetime.fromisoformat(slot["start"])
            hour = start.hour
            score = 100  # Base score

            # Filter out slots after no_meetings_after
            if hour >= no_meetings_after:
                score -= 50

            # Boost preferred times
            for time_pref in preferred_times:
                if time_pref in TIME_PREFERENCES:
                    start_hour, end_hour = TIME_PREFERENCES[time_pref]
                    if start_hour <= hour < end_hour:
                        score += 20
                        break

            # Earlier preference
            if prefer_earlier:
                score -= hour  # Lower hour = higher score

            # Prefer weekdays strongly
            if start.weekday() < 5:  # Monday = 0, Friday = 4
                score += 10

            scored_slots.append({**slot, "score": score})

        # Sort by score (higher is better)
        scored_slots.sort(key=lambda x: x["score"], reverse=True)

        # Remove score from output
        for slot in scored_slots:
            del slot["score"]

        return scored_slots

    async def create_meeting(
        self,
        title: str,
        attendees: List[str],
        start_time: str,
        duration_minutes: int,
        description: Optional[str] = None,
        location: Optional[str] = None,
        add_video: bool = False,
        timezone: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a calendar meeting event.

        Args:
            title: Meeting title
            attendees: List of attendee email addresses
            start_time: Start time (ISO format)
            duration_minutes: Meeting duration in minutes
            description: Optional meeting description
            location: Optional physical location
            add_video: Add Google Meet video conferencing
            timezone: Timezone for the meeting

        Returns:
            Dict with created event details
        """
        tz = timezone or self.preferences.get("timezone", "America/Los_Angeles")

        # Calculate end time
        start = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        end = start + timedelta(minutes=duration_minutes)

        return await self.calendar_client.create_event(
            title=title,
            start_time=start.isoformat(),
            end_time=end.isoformat(),
            attendees=attendees,
            description=description,
            location=location,
            timezone=tz,
            send_notifications=True,
            conference_data=add_video,
        )

    async def send_invites(self, meeting_id: str) -> Dict[str, Any]:
        """
        Send or resend meeting invitations.

        Note: Google Calendar automatically sends invites when creating events
        with send_notifications=True. This method can be used to resend or
        update invitations.

        Args:
            meeting_id: The calendar event ID

        Returns:
            Dict with invite status
        """
        # Get the event
        event_result = await self.calendar_client.get_event(meeting_id)
        if not event_result.get("success"):
            return event_result

        event = event_result.get("event", {})
        attendees = event.get("attendees", [])

        # Re-update the event to trigger notification resend
        result = await self.calendar_client.update_event(
            event_id=meeting_id,
            send_notifications=True,
        )

        if result.get("success"):
            return {
                "success": True,
                "message": f"Invitations sent to {len(attendees)} attendee(s)",
                "attendees": [a.get("email") for a in attendees],
                "event_id": meeting_id,
            }

        return result

    # Private handler methods for execute()

    async def _handle_schedule(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Handle schedule action."""
        message = task.get("message", "")
        if not message:
            return {
                "success": False,
                "error": "No message provided for scheduling",
            }

        # Parse the request
        request = self.parse_request(message)

        if not request.attendees:
            return {
                "success": False,
                "error": "No attendees found in the request. Please include email addresses.",
                "parsed_request": request.to_dict(),
            }

        # Determine date range based on parsed request
        tz = ZoneInfo(request.timezone)
        now = datetime.now(tz)

        if request.preferred_date:
            date_start = request.preferred_date
            date_end = (
                datetime.strptime(date_start, "%Y-%m-%d") + timedelta(days=1)
            ).strftime("%Y-%m-%d")
        else:
            date_start = now.strftime("%Y-%m-%d")
            date_end = (now + timedelta(days=7)).strftime("%Y-%m-%d")

        # Find optimal times
        slots_result = await self.find_optimal_time(
            attendees=request.attendees,
            duration_minutes=request.duration_minutes,
            date_range=(f"{date_start}T00:00:00", f"{date_end}T23:59:59"),
        )

        if not slots_result.get("success"):
            return slots_result

        slots = slots_result.get("slots", [])
        if not slots:
            return {
                "success": False,
                "error": "No available time slots found for the requested period",
                "parsed_request": request.to_dict(),
            }

        # If a specific time was requested, try to use it
        chosen_slot = None
        if request.preferred_time:
            for slot in slots:
                slot_time = datetime.fromisoformat(slot["start"]).strftime("%H:%M")
                if slot_time == request.preferred_time:
                    chosen_slot = slot
                    break

        # Use the first (best ranked) slot if no specific time matched
        if not chosen_slot:
            chosen_slot = slots[0]

        # Create the meeting
        result = await self.create_meeting(
            title=request.title or "Meeting",
            attendees=request.attendees,
            start_time=chosen_slot["start"],
            duration_minutes=request.duration_minutes,
            description=request.description,
            location=request.location,
            add_video=request.add_video,
            timezone=request.timezone,
        )

        if result.get("success"):
            result["parsed_request"] = request.to_dict()
            result["chosen_slot"] = chosen_slot
            result["alternative_slots"] = slots[1:4] if len(slots) > 1 else []

        return result

    async def _handle_reschedule(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Handle reschedule action."""
        event_id = task.get("event_id")
        if not event_id:
            return {
                "success": False,
                "error": "No event_id provided for rescheduling",
            }

        new_start_time = task.get("new_start_time")
        new_end_time = task.get("new_end_time")

        return await self.calendar_client.update_event(
            event_id=event_id,
            start_time=new_start_time,
            end_time=new_end_time,
            send_notifications=True,
        )

    async def _handle_cancel(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Handle cancel action."""
        event_id = task.get("event_id")
        if not event_id:
            return {
                "success": False,
                "error": "No event_id provided for cancellation",
            }

        send_notifications = task.get("send_notifications", True)

        return await self.calendar_client.delete_event(
            event_id=event_id,
            send_notifications=send_notifications,
        )

    async def _handle_check_availability(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Handle check_availability action."""
        attendees = task.get("attendees", [])
        if not attendees:
            return {
                "success": False,
                "error": "No attendees provided for availability check",
            }

        duration = task.get("duration_minutes", self.preferences.get("default_duration", 30))
        date_range = task.get("date_range")

        return await self.check_availability(
            attendees=attendees,
            duration_minutes=duration,
            date_range=date_range,
        )

    async def _handle_find_slots(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Handle find_slots action."""
        attendees = task.get("attendees", [])
        if not attendees:
            return {
                "success": False,
                "error": "No attendees provided for finding slots",
            }

        duration = task.get("duration_minutes", self.preferences.get("default_duration", 30))
        date_range = task.get("date_range")
        preferences = task.get("preferences")

        return await self.find_optimal_time(
            attendees=attendees,
            duration_minutes=duration,
            date_range=date_range,
            preferences=preferences,
        )

    async def _handle_parse(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Handle parse action (parse request without creating meeting)."""
        message = task.get("message", "")
        if not message:
            return {
                "success": False,
                "error": "No message provided for parsing",
            }

        request = self.parse_request(message)
        return {
            "success": True,
            "parsed_request": request.to_dict(),
        }


# Module-level singleton
_scheduler: Optional[MeetingScheduler] = None


def get_scheduler(
    memory_manager=None, preferences: Optional[Dict[str, Any]] = None
) -> MeetingScheduler:
    """Get or create the singleton MeetingScheduler instance."""
    global _scheduler
    if _scheduler is None:
        _scheduler = MeetingScheduler(
            memory_manager=memory_manager, preferences=preferences
        )
    return _scheduler


# Convenience functions
async def schedule_meeting(message: str) -> Dict[str, Any]:
    """Schedule a meeting from natural language."""
    scheduler = get_scheduler()
    return await scheduler.execute({"action": "schedule", "message": message})


async def parse_meeting_request(message: str) -> Dict[str, Any]:
    """Parse a meeting request without creating it."""
    scheduler = get_scheduler()
    return await scheduler.execute({"action": "parse", "message": message})


async def check_availability(
    attendees: List[str],
    duration_minutes: int = 30,
    date_range: Optional[Tuple[str, str]] = None,
) -> Dict[str, Any]:
    """Check calendar availability for attendees."""
    scheduler = get_scheduler()
    return await scheduler.execute(
        {
            "action": "check_availability",
            "attendees": attendees,
            "duration_minutes": duration_minutes,
            "date_range": date_range,
        }
    )


async def find_meeting_slots(
    attendees: List[str],
    duration_minutes: int = 30,
    date_range: Optional[Tuple[str, str]] = None,
    preferences: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Find available meeting time slots."""
    scheduler = get_scheduler()
    return await scheduler.execute(
        {
            "action": "find_slots",
            "attendees": attendees,
            "duration_minutes": duration_minutes,
            "date_range": date_range,
            "preferences": preferences,
        }
    )


async def cancel_meeting(event_id: str, send_notifications: bool = True) -> Dict[str, Any]:
    """Cancel a scheduled meeting."""
    scheduler = get_scheduler()
    return await scheduler.execute(
        {
            "action": "cancel",
            "event_id": event_id,
            "send_notifications": send_notifications,
        }
    )


async def reschedule_meeting(
    event_id: str,
    new_start_time: str,
    new_end_time: Optional[str] = None,
) -> Dict[str, Any]:
    """Reschedule an existing meeting."""
    scheduler = get_scheduler()
    return await scheduler.execute(
        {
            "action": "reschedule",
            "event_id": event_id,
            "new_start_time": new_start_time,
            "new_end_time": new_end_time,
        }
    )
