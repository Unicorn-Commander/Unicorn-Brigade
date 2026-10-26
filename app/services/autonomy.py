"""Autonomy catalogue (P-00092) — the pure logic behind ``/api/v1/autonomy``.

One place listing every agent job that runs on its own: Brigade's own scheduled
runs AND loops that live outside Brigade (cron on bigboy, systemd on commander,
LaunchAgents on the Mac Studio, Claude Code routines, continuous watchers) that
register and report through the API. For each job the catalogue answers: which
agent, what it is responsible for, where and how it runs, when it runs next, how
its last run went and why it failed.

Everything here is a PURE function over plain values or duck-typed rows (any
object with the right attributes, so a ``SimpleNamespace`` works in tests). No
database, no request, no clock: callers pass ``now``. The routes in
``app/api/autonomy_routes.py`` only load rows, call these, and persist.

Cron schedules
--------------
Every schedule is parsed by ``app.services.cron.parse_cron`` using standard
five-field cron semantics: day-of-week 0 or 7 is Sunday, 1 is Monday, and when
both day-of-month and day-of-week are restricted the job fires when EITHER
matches. That shared parser translates the expression into APScheduler terms
and uses ``OrTrigger`` where APScheduler's native AND semantics differ.

Staleness
---------
A job is ``stale`` when the first fire time after its last run was missed by more
than half an interval plus 15 minutes, where interval is the gap between that
fire time and the one after it. For evenly spaced schedules this is the
contract's ``now - lastRunAt > 1.5 x interval + 15 min`` (anchored on the
schedule rather than on when the last run finished). For uneven schedules
(twice a day at uneven hours, weekdays only) it does not raise the false alarms
a gap measured from ``now`` would.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Iterable, Optional
from zoneinfo import ZoneInfo

from app.core.timezones import BUSINESS_TIMEZONE
from app.services.cron import parse_cron as _parse_standard_cron
from app.services.cron import (
    standard_dow_to_aps,  # noqa: F401  (re-exported: catalogue callers and tests import it from here)
)

logger = logging.getLogger(__name__)


# ── vocabulary ────────────────────────────────────────────────────

SOURCE_BRIGADE = "brigade"
SOURCE_EXTERNAL = "external"
BRIGADE_HOST = "brigade"
BRIGADE_RUNNER = "brigade-scheduler"
# Runners an OUTSIDE job may declare (``brigade-scheduler`` is Brigade's own).
EXTERNAL_RUNNERS = ("cron", "systemd", "launchd", "claude-routine", "continuous", "other")
RUN_STATUSES = ("running", "success", "error", "timeout", "skipped")
TERMINAL_STATUSES = ("success", "error", "timeout", "skipped")
# The run statuses that set a job's last_error (an outside job's report).
FAILING_STATUSES = ("error", "timeout")
# Health: every last status OTHER than these (and null) is failing — including
# words outside the run enum that Brigade's own rows carry in real data (the
# dogfood zpool-health row reports "degraded").
NON_FAILING_STATUSES = frozenset({"success", "skipped", "running"})

HEALTH_FAILING = "failing"
HEALTH_STALE = "stale"
HEALTH_NEVER = "never"
HEALTH_OK = "ok"
HEALTH_PAUSED = "paused"
# Catalogue sort order: what needs a human first.
HEALTH_ORDER = (HEALTH_FAILING, HEALTH_STALE, HEALTH_NEVER, HEALTH_OK, HEALTH_PAUSED)
_HEALTH_RANK = {h: i for i, h in enumerate(HEALTH_ORDER)}

STALE_GRACE = timedelta(minutes=15)
MAX_RUNS_PER_JOB = 200
SUMMARY_PREVIEW_CHARS = 280  # Brigade items: last_result_summary shown on a card
SUMMARY_MAX_CHARS = 2000
ERROR_MAX_CHARS = 4000
COMMAND_MAX_CHARS = 500
RUNBOOK_URL_MAX_CHARS = 500
NOTES_MAX_CHARS = 2000

KEY_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{1,118}[a-z0-9]$")
KEY_RULE = (
    "Job keys are 3-120 characters of lowercase letters, digits and hyphens, "
    "starting and ending with a letter or digit (for example build-log-refresh)."
)
SECRET_IN_COMMAND = "Don't store secrets in the command; reference them by name."
SECRET_IN_RUNBOOK_URL = "Don't store secrets in the runbook URL; reference them by name."
SECRET_IN_NOTES = "Don't store secrets in the notes; reference them by name."


# ── keys ─────────────────────────────────────────────────────────

def is_valid_key(key: Any) -> bool:
    """A job key is a lowercase slug: ``^[a-z0-9][a-z0-9-]{1,118}[a-z0-9]$``."""
    # fullmatch, not match: "$" alone also matches before a trailing newline.
    return isinstance(key, str) and bool(KEY_PATTERN.fullmatch(key))


def unknown_job_detail(key: str) -> str:
    """The 404 detail for a report against a job nobody registered."""
    return f"No job '{key}'. Register it with PUT /api/v1/autonomy/jobs/{key} first."


# ── secrets ──────────────────────────────────────────────────────

_SECRET_ASSIGNMENT = re.compile(r"(password|passwd|secret|token|api[_-]?key)\s*[=:]", re.IGNORECASE)
_SECRET_ASSIGNMENT_VALUE = re.compile(
    r"((?:password|passwd|secret|token|api[_-]?key)\s*[=:]\s*)(\"[^\"]*\"|'[^']*'|\S+)",
    re.IGNORECASE,
)
_URL_USERINFO = re.compile(r"://[^/\s:]+:[^@\s]+@")
_URL_USERINFO_PASSWORD = re.compile(r"(://[^/\s:]+:)[^@\s]+@")
# Common credential shapes, matched only at a word boundary AND with a minimum
# token length: the fleet inventory (204 real jobs) has legitimate commands with
# "sk-" inside words — /usr/local/bin/disk-guard.sh, kiosk-chromium-refresh, the
# leaddesk jobs — and a bare prefix match refused them. ``ubk-`` is Brigade's own
# key format and ``sbk-`` Stable's, the very keys a reporting script is handed.
# AKIA is case-sensitive (AWS access key ids are upper-case).
_KEY_SHAPES = re.compile(
    r"(?<![A-Za-z0-9])(?:"
    r"(?:sk|ubk|sbk)-[A-Za-z0-9_\-]{16,}"
    r"|ghp_[A-Za-z0-9]{20,}"
    r"|github_pat_[A-Za-z0-9_]{20,}"
    r"|xox[abposr]-[A-Za-z0-9\-]{10,}"
    r"|AKIA[0-9A-Z]{16}"
    r")"
)
REDACTED = "[redacted]"


def looks_like_secret(text: Optional[str]) -> bool:
    """True when ``text`` looks like it carries a credential: ``password=``-style
    assignments (password, passwd, secret, token, api key), URL userinfo
    (``scheme://user:pass@host``) or a common key prefix (sk-, ghp_, xoxb-, AKIA,
    plus Brigade's ubk- and Stable's sbk-)."""
    if not text:
        return False
    return bool(
        _SECRET_ASSIGNMENT.search(text)
        or _URL_USERINFO.search(text)
        or _KEY_SHAPES.search(text)
    )


def redact_secrets(text: Optional[str]) -> Optional[str]:
    """Mask credential-looking substrings in free text a script reports.

    A failing ``curl`` happily prints the URL it used, userinfo and all, and run
    summaries/errors are shown to every operator in the org — so they are masked
    before they are stored. Never raises; ``None`` stays ``None``.
    """
    if not text:
        return text
    out = _URL_USERINFO_PASSWORD.sub(r"\1***@", text)
    out = _SECRET_ASSIGNMENT_VALUE.sub(lambda m: m.group(1) + REDACTED, out)
    out = _KEY_SHAPES.sub(REDACTED, out)
    return out


def command_problem(command: Optional[str]) -> Optional[str]:
    """The 422 message for an unacceptable ``command`` (secret first, then length)."""
    if command is None:
        return None
    if looks_like_secret(command):
        return SECRET_IN_COMMAND
    if len(command) > COMMAND_MAX_CHARS:
        return f"command must be at most {COMMAND_MAX_CHARS} characters"
    return None


def runbook_url_problem(url: Optional[str]) -> Optional[str]:
    """The 422 message for an unacceptable ``runbookUrl`` (secret first, then length)."""
    if url is None:
        return None
    if looks_like_secret(url):
        return SECRET_IN_RUNBOOK_URL
    if len(url) > RUNBOOK_URL_MAX_CHARS:
        return f"runbookUrl must be at most {RUNBOOK_URL_MAX_CHARS} characters"
    return None


def notes_problem(notes: Optional[str]) -> Optional[str]:
    """The 422 message for unacceptable ``notes`` (secret first, then length)."""
    if notes is None:
        return None
    if looks_like_secret(notes):
        return SECRET_IN_NOTES
    if len(notes) > NOTES_MAX_CHARS:
        return f"notes must be at most {NOTES_MAX_CHARS} characters"
    return None


# ── text ─────────────────────────────────────────────────────────

def clip(text: Optional[str], limit: int) -> Optional[str]:
    """``text`` cut to at most ``limit`` characters, marked with an ellipsis."""
    if text is None or len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def sanitize_report_text(text: Optional[str], limit: int) -> Optional[str]:
    """Reported summary/error text as stored: trimmed, secrets masked, clipped.

    Over-long text is clipped rather than rejected: refusing a failure report
    because its error is long would lose the failure. Masking runs BEFORE
    clipping so a cut can never leave a partial key behind.
    """
    if text is None:
        return None
    trimmed = text.strip()
    if not trimmed:
        return None
    return clip(redact_secrets(trimmed), limit)


# ── time ─────────────────────────────────────────────────────────

def to_naive_utc(value: Optional[datetime]) -> Optional[datetime]:
    """Brigade stores naive UTC. Aware -> converted; naive -> taken as UTC."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)


def as_aware_utc(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def iso_z(value: Optional[datetime]) -> Optional[str]:
    """ISO 8601 in UTC with a trailing Z (the shape every Brigade to_dict uses)."""
    naive = to_naive_utc(value)
    return naive.isoformat() + "Z" if naive is not None else None


# ── timezones and cron ───────────────────────────────────────────

def validate_timezone(tz: str) -> str:
    """``tz`` if it is an IANA zone the scheduler also accepts; else ValueError."""
    name = (tz or "").strip()
    try:
        ZoneInfo(name)
        _parse_standard_cron("0 0 * * *", name)  # APScheduler resolves zones through pytz
    except Exception:  # noqa: BLE001 - every failure means "not a usable zone"
        raise ValueError(f"unknown timezone {tz!r}; use an IANA zone such as UTC or America/New_York") from None
    return name


@dataclass(frozen=True)
class CronSchedule:
    """A schedule that fires whenever ANY of its APScheduler triggers fires.

    One trigger normally; two when a standard cron restricts both day-of-month
    and day-of-week (cron then fires when either matches; APScheduler alone
    would require both)."""

    triggers: tuple

    def fire_at_or_after(self, moment: datetime) -> Optional[datetime]:
        """The first fire time at or after ``moment`` (UTC), or None if it never fires."""
        moment = as_aware_utc(moment)
        fires = [t.get_next_fire_time(None, moment) for t in self.triggers]
        fires = [f for f in fires if f is not None]
        return min(fires).astimezone(UTC) if fires else None


def parse_schedule(cron: str, tz: str, *, standard: bool = True) -> CronSchedule:
    """Parse a five-field cron through the shared standard parser.

    ``standard`` remains as a source-compatible keyword for callers from the
    pre-unification API; all schedules now use standard cron semantics.
    Raises ``ValueError`` on bad input.
    """
    return CronSchedule((_parse_standard_cron(cron, tz),))


def validate_schedule(cron: str, tz: str, *, now: Optional[datetime] = None) -> str:
    """A cleaned standard cron for an outside job, or ValueError with the reason.

    It must parse (through the shared cron parser) and fire at least once more:
    ``0 0 31 2 *`` is valid syntax that never runs."""
    cleaned = " ".join((cron or "").split())
    try:
        schedule = parse_schedule(cleaned, tz, standard=True)
    except Exception as e:  # noqa: BLE001 - APScheduler raises ValueError/TypeError
        raise ValueError(f"invalid schedule: {e}") from None
    if schedule.fire_at_or_after(now or datetime.now(UTC)) is None:
        raise ValueError(f"schedule {cleaned!r} never fires")
    return cleaned


def safe_schedule(cron: Optional[str], tz: Optional[str], *, standard: bool) -> Optional[CronSchedule]:
    """``parse_schedule`` that returns None instead of raising: a row edited by
    hand must not take the whole catalogue down."""
    if not cron or not str(cron).strip():
        return None
    try:
        return parse_schedule(str(cron), tz or "UTC", standard=standard)
    except Exception as e:  # noqa: BLE001
        logger.debug("autonomy: unparseable schedule %r (%s): %s", cron, tz, e)
        return None


def next_run_at(schedule: Optional[CronSchedule], now: datetime, *, enabled: bool = True) -> Optional[datetime]:
    """Next fire time (UTC) for an enabled scheduled job; None otherwise."""
    if not enabled or schedule is None:
        return None
    return schedule.fire_at_or_after(now)


def schedule_interval(schedule: Optional[CronSchedule], at: datetime) -> Optional[timedelta]:
    """The gap between the next two fire times at or after ``at``."""
    if schedule is None:
        return None
    first = schedule.fire_at_or_after(at)
    if first is None:
        return None
    second = schedule.fire_at_or_after(first + timedelta(microseconds=1))
    if second is None:
        return None
    return second - first


def stale_after(schedule: Optional[CronSchedule], last_run_at: Optional[datetime]) -> Optional[datetime]:
    """When a job that last ran at ``last_run_at`` becomes stale (UTC), or None
    if it cannot (no schedule, or no fire time after the last run)."""
    if schedule is None or last_run_at is None:
        return None
    expected = schedule.fire_at_or_after(as_aware_utc(last_run_at) + timedelta(microseconds=1))
    if expected is None:
        return None
    gap = schedule_interval(schedule, expected) or timedelta(0)
    return expected + gap / 2 + STALE_GRACE


def is_failing_status(status: Any) -> bool:
    """A last status that makes a job ``failing``: anything but success,
    skipped, running or nothing. Compared case-insensitively; shown as-is."""
    if status is None:
        return False
    word = str(status).strip().lower()
    return bool(word) and word not in NON_FAILING_STATUSES


def compute_health(
    *,
    enabled: bool,
    last_status: Optional[str],
    last_run_at: Optional[datetime],
    schedule: Optional[CronSchedule],
    now: datetime,
) -> str:
    """paused -> failing -> never -> stale -> ok, in that order of precedence.

    failing = any last status but success / skipped / running / null (so a
    Brigade row's "degraded" is failing). A job with no cron (``continuous``,
    "on every push") is never stale."""
    if not enabled:
        return HEALTH_PAUSED
    if is_failing_status(last_status):
        return HEALTH_FAILING
    if last_run_at is None:
        return HEALTH_NEVER
    deadline = stale_after(schedule, last_run_at)
    if deadline is not None and as_aware_utc(now) > deadline:
        return HEALTH_STALE
    return HEALTH_OK


# ── catalogue items ──────────────────────────────────────────────

def agent_summary(agent: Any) -> Optional[dict]:
    """The agent card a catalogue item carries (None when the id is unknown)."""
    if agent is None:
        return None
    return {
        "id": agent.id,
        "name": agent.name,
        "displayName": getattr(agent, "display_name", None),
        "title": getattr(agent, "title", None),
        "domain": getattr(agent, "domain", None),
        "avatarUrl": getattr(agent, "avatar_url", None),
    }


def build_brigade_item(
    run: Any,
    agent: Any,
    now: datetime,
    *,
    last_duration_ms: Optional[int] = None,
) -> dict:
    """A catalogue item for one of Brigade's own ``scheduled_runs`` rows.

    ``last_duration_ms`` comes from the row's latest finished history entry
    (scheduled_runs itself keeps no duration)."""
    tz = getattr(run, "timezone", None) or BUSINESS_TIMEZONE
    enabled = bool(run.enabled)
    schedule = safe_schedule(run.cron, tz, standard=True)
    summary = getattr(run, "last_result_summary", None)
    last_status = getattr(run, "last_status", None)
    return {
        "id": f"{SOURCE_BRIGADE}:{run.id}",
        "source": SOURCE_BRIGADE,
        "key": str(run.id),
        "name": run.name,
        "responsibility": getattr(run, "description", None) or None,
        "agentId": run.agent_id,
        "agent": agent_summary(agent),
        "host": BRIGADE_HOST,
        "runner": BRIGADE_RUNNER,
        "schedule": run.cron,
        "timezone": tz,
        "scheduleNote": None,
        "nextRunAt": iso_z(next_run_at(schedule, now, enabled=enabled)),
        "enabled": enabled,
        "lastRunAt": iso_z(getattr(run, "last_run_at", None)),
        "lastStatus": last_status,  # passed through as-is, even outside the enum
        "lastSummary": clip(summary, SUMMARY_PREVIEW_CHARS),
        "lastError": summary if is_failing_status(last_status) else None,
        "lastDurationMs": last_duration_ms,
        "health": compute_health(
            enabled=enabled,
            last_status=last_status,
            last_run_at=getattr(run, "last_run_at", None),
            schedule=schedule,
            now=now,
        ),
        "command": None,
        "runbookUrl": None,
        "owner": None,
        "notes": None,
        "scheduledRunId": str(run.id),
        "updatedAt": iso_z(getattr(run, "updated_at", None)),
    }


def build_external_item(job: Any, agent: Any, now: datetime) -> dict:
    """A catalogue item for an outside job (``autonomous_jobs`` row)."""
    tz = getattr(job, "timezone", None) or "UTC"
    enabled = bool(job.enabled)
    schedule = safe_schedule(getattr(job, "schedule", None), tz, standard=True)
    return {
        "id": f"{SOURCE_EXTERNAL}:{job.key}",
        "source": SOURCE_EXTERNAL,
        "key": job.key,
        "name": job.name,
        "responsibility": job.responsibility,
        "agentId": getattr(job, "agent_id", None),
        "agent": agent_summary(agent),
        "host": job.host,
        "runner": job.runner,
        "schedule": getattr(job, "schedule", None),
        "timezone": tz,
        "scheduleNote": getattr(job, "schedule_note", None),
        "nextRunAt": iso_z(next_run_at(schedule, now, enabled=enabled)),
        "enabled": enabled,
        "lastRunAt": iso_z(getattr(job, "last_run_at", None)),
        "lastStatus": getattr(job, "last_status", None),
        "lastSummary": getattr(job, "last_summary", None),
        "lastError": getattr(job, "last_error", None),
        "lastDurationMs": getattr(job, "last_duration_ms", None),
        "health": compute_health(
            enabled=enabled,
            last_status=getattr(job, "last_status", None),
            last_run_at=getattr(job, "last_run_at", None),
            schedule=schedule,
            now=now,
        ),
        "command": getattr(job, "command", None),
        "runbookUrl": getattr(job, "runbook_url", None),
        "owner": getattr(job, "owner", None),
        "notes": getattr(job, "notes", None),
        "scheduledRunId": None,
        "updatedAt": iso_z(getattr(job, "updated_at", None)),
    }


def _sort_key(item: dict) -> tuple:
    agent = item.get("agent") or {}
    label = agent.get("displayName") or agent.get("name") or item.get("agentId")
    return (
        _HEALTH_RANK.get(item.get("health"), len(HEALTH_ORDER)),
        label is None,  # unassigned jobs last within a health band
        (label or "").casefold(),
        (item.get("name") or "").casefold(),
        item.get("id") or "",
    )


def sort_catalogue(items: Iterable[dict]) -> list:
    """failing, stale, never, ok, paused; then agent display name; then name."""
    return sorted(items, key=_sort_key)


def catalogue_counts(items: Iterable[dict]) -> dict:
    counts = {
        "total": 0,
        SOURCE_BRIGADE: 0,
        SOURCE_EXTERNAL: 0,
        HEALTH_FAILING: 0,
        HEALTH_STALE: 0,
        HEALTH_PAUSED: 0,
        HEALTH_NEVER: 0,
    }
    for item in items:
        counts["total"] += 1
        if item.get("source") in (SOURCE_BRIGADE, SOURCE_EXTERNAL):
            counts[item["source"]] += 1
        if item.get("health") in (HEALTH_FAILING, HEALTH_STALE, HEALTH_PAUSED, HEALTH_NEVER):
            counts[item["health"]] += 1
    return counts


# ── registering an outside job ───────────────────────────────────

# camelCase body field -> autonomous_jobs column.
JOB_FIELD_COLUMNS = {
    "name": "name",
    "responsibility": "responsibility",
    "agentId": "agent_id",
    "host": "host",
    "runner": "runner",
    "schedule": "schedule",
    "timezone": "timezone",
    "scheduleNote": "schedule_note",
    "command": "command",
    "runbookUrl": "runbook_url",
    "owner": "owner",
    "notes": "notes",
    "enabled": "enabled",
}
REQUIRED_JOB_FIELDS = frozenset({"name", "responsibility", "host", "runner"})


def plan_job_upsert(body: dict, provided: Iterable[str], *, creating: bool) -> dict:
    """The ``autonomous_jobs`` column values a PUT writes.

    First registration: every column, absent optional fields taking their
    defaults. Re-registration: the required fields plus only the optional
    fields the caller actually sent (an explicit null clears one). So a script
    that re-registers on every run never undoes a human's pause, owner or
    runbook edit unless it sends that field itself."""
    sent = set(provided)
    return {
        column: body.get(field)
        for field, column in JOB_FIELD_COLUMNS.items()
        if creating or field in REQUIRED_JOB_FIELDS or field in sent
    }


# ── reporting a run ──────────────────────────────────────────────

@dataclass(frozen=True)
class RunReport:
    """One ``POST /autonomy/jobs/{key}/runs`` body, timestamps already parsed."""

    status: str
    run_id: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    summary: Optional[str] = None
    error: Optional[str] = None
    duration_ms: Optional[int] = None


@dataclass(frozen=True)
class RunOutcome:
    """What a run report changes.

    ``run_values``: the run row's columns after the report. ``matched``: write
    them onto the row the report's runId matched (else insert a new row with
    them). ``job_updates``: the job's ``last_*`` columns."""

    run_values: dict
    matched: bool
    job_updates: dict


_INT4_MAX = 2_147_483_647  # duration columns are Postgres integer


def _duration_ms(start: Optional[datetime], end: Optional[datetime]) -> Optional[int]:
    if start is None or end is None:
        return None
    return min(_INT4_MAX, max(0, int((end - start).total_seconds() * 1000)))


def apply_run_report(report: RunReport, matched_run: Any = None, *, now: datetime) -> RunOutcome:
    """Apply a run report to (the run its runId matched, if any).

    * ``running``: opens a run (started_at = startedAt or now). Repeating the
      same runId while it is still running updates that row instead of adding one.
    * terminal (success/error/timeout/skipped): closes the row the runId
      matched (finished_at = finishedAt or now; duration from the timestamps
      unless durationMs is given), else records a finished run on its own.
      Re-sending a terminal report with the same runId updates that row, so a
      retried curl does not duplicate history.
    * The job: last_run_at = finishedAt or startedAt or now; last_status,
      last_summary and last_duration_ms follow the run; last_error is cleared
      on success, set (error, else summary) on error/timeout, kept otherwise.
    """
    now_naive = to_naive_utc(now)
    started = to_naive_utc(report.started_at)
    finished = to_naive_utc(report.finished_at)
    summary = sanitize_report_text(report.summary, SUMMARY_MAX_CHARS)
    error = sanitize_report_text(report.error, ERROR_MAX_CHARS)
    prior = matched_run
    prior_open = prior is not None and getattr(prior, "status", None) == "running"

    if report.status == "running":
        base = prior if prior_open else None  # a finished row reused by runId starts fresh
        values = {
            "status": "running",
            "started_at": started or (base.started_at if base is not None else None) or now_naive,
            "finished_at": None,
            "duration_ms": None,
            "summary": summary if summary is not None else (base.summary if base is not None else None),
            "error": error if error is not None else (base.error if base is not None else None),
        }
    else:
        base = prior
        start = started or (base.started_at if base is not None else None)
        end = finished
        if end is None and base is not None and not prior_open:
            end = base.finished_at  # a retried terminal report keeps its finish time
        if end is None:
            end = now_naive
        if report.duration_ms is not None:
            duration = min(_INT4_MAX, max(0, int(report.duration_ms)))
            if start is None:
                start = end - timedelta(milliseconds=duration)
        else:
            duration = _duration_ms(start, end)
        values = {
            "status": report.status,
            "started_at": start or end,
            "finished_at": end,
            "duration_ms": duration,
            "summary": summary if summary is not None else (base.summary if base is not None else None),
            "error": error if error is not None else (base.error if base is not None else None),
        }
    if prior is None:
        values["run_id"] = report.run_id

    job_updates = {
        "last_run_at": finished or started or now_naive,
        "last_status": report.status,
        "last_summary": values["summary"],
        "last_duration_ms": values["duration_ms"],
    }
    if report.status == "success":
        job_updates["last_error"] = None
    elif report.status in FAILING_STATUSES:
        job_updates["last_error"] = values["error"] or values["summary"]
    return RunOutcome(run_values=values, matched=prior is not None, job_updates=job_updates)
