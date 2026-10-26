"""Shared standard-cron parsing for Brigade schedules.

APScheduler 3 numbers weekdays from Monday, while the five-field cron syntax
Brigade stores numbers them from Sunday (0 and 7).  APScheduler also combines
day-of-month and day-of-week with AND; standard cron combines restricted fields
with OR.  Keep those translations here so dispatch, validation and next-run
displays cannot disagree.
"""

from __future__ import annotations

from typing import Union

from apscheduler.triggers.combining import OrTrigger
from apscheduler.triggers.cron import CronTrigger

from app.core.timezones import BUSINESS_TIMEZONE

CronTriggerLike = Union[CronTrigger, OrTrigger]

# Standard cron names are Sunday-first.  APScheduler's names are Monday-first,
# but the names themselves have the same meaning once the standard numeric field
# has been expanded into a set of named weekdays.
_STD_DOW_NAMES = ("sun", "mon", "tue", "wed", "thu", "fri", "sat")
_APS_DOW_ORDER = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


def _std_dow_number(token: str) -> int:
    value = token.strip().lower()
    if value.isdigit():
        number = int(value)
        if 0 <= number <= 7:
            return number
        raise ValueError(f"day-of-week {token!r} is out of range (0-7)")
    if value in _STD_DOW_NAMES:
        return _STD_DOW_NAMES.index(value)
    raise ValueError(f"invalid day-of-week {token!r}")


def _std_dow_days(field: str) -> set[int]:
    """Expand a standard-cron weekday field into Sunday-based day numbers."""
    days: set[int] = set()
    for part in field.split(","):
        part = part.strip()
        if not part:
            raise ValueError(f"invalid day-of-week field {field!r}")
        base, slash, step_text = part.partition("/")
        step = 1
        if slash:
            if not step_text.isdigit() or int(step_text) < 1:
                raise ValueError(f"invalid day-of-week step in {part!r}")
            step = int(step_text)
        if base == "*":
            low, high = 0, 7
        elif "-" in base:
            first, last = base.split("-", 1)
            low, high = _std_dow_number(first), _std_dow_number(last)
            if high < low and high == 0:
                high = 7  # e.g. fri-sun
            if high < low:
                raise ValueError(f"day-of-week range {base!r} runs backwards")
        else:
            low = _std_dow_number(base)
            high = 7 if slash else low
        days.update(number % 7 for number in range(low, high + 1, step))
    return days


def standard_dow_to_aps(field: str) -> str:
    """Translate a standard-cron weekday field to APScheduler's terms."""
    if field.strip() == "*":
        return "*"
    days = _std_dow_days(field)
    if days == set(range(7)):
        return "*"
    return ",".join(
        name for name in _APS_DOW_ORDER if _STD_DOW_NAMES.index(name) in days
    )


def parse_cron(expr: str, tz: str = BUSINESS_TIMEZONE) -> CronTriggerLike:
    """Parse one standard five-field cron expression.

    The returned object is a ``CronTrigger`` for ordinary expressions and an
    ``OrTrigger`` when both day-of-month and day-of-week are restricted.
    Raises ``ValueError`` with a useful message for malformed expressions.
    """
    if not isinstance(expr, str):
        raise ValueError(f"cron must be a string, got: {expr!r}")
    parts = expr.strip().split()
    if len(parts) != 5:
        raise ValueError(
            f"cron must be 5 fields (minute hour day month day_of_week), got: {expr!r}"
        )

    minute, hour, day, month, dow = parts
    try:
        aps_dow = standard_dow_to_aps(dow)
        # In standard cron, a restricted day-of-month and restricted weekday
        # are an OR.  Split the expression into two AND triggers and combine
        # them so APScheduler's trigger semantics do not change the schedule.
        if day.strip() != "*" and dow.strip() != "*":
            return OrTrigger(
                [
                    CronTrigger(
                        minute=minute,
                        hour=hour,
                        day=day,
                        month=month,
                        day_of_week="*",
                        timezone=tz,
                    ),
                    CronTrigger(
                        minute=minute,
                        hour=hour,
                        day="*",
                        month=month,
                        day_of_week=aps_dow,
                        timezone=tz,
                    ),
                ]
            )
        return CronTrigger(
            minute=minute,
            hour=hour,
            day=day,
            month=month,
            day_of_week=aps_dow,
            timezone=tz,
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid cron expression {expr!r}: {exc}") from None
