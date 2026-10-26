"""Autonomy catalogue (P-00092): pure logic, request validation and the auth gates.

Style follows tests/test_scheduler.py: pure functions and Pydantic models, no
live database. The route-level tests at the bottom mount the REAL autonomy
router behind the REAL ``get_current_user`` (only credential resolution and the
org bind are stubbed) over an in-memory store, because the bug those guard
against lives in the wiring: the global path/method gate would 403 a
viewer-level reporter key before the route's own dependency ever ran.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

import app.api.autonomy_routes as routes
import app.auth.middleware as middleware
from app.api.admin_keys_routes import CreateUserKeyRequest
from app.api.apikey_routes import GenerateKeyRequest
from app.api.scheduled_run_routes import ScheduledRunCreate, ScheduledRunUpdate
from app.api.user_routes import CreateApiKeyRequest
from app.auth.middleware import (
    REPORTER_KEY_CONFINED_DETAIL,
    AuthUser,
    require_api_key,
    require_autonomy_reporter,
    require_operator,
)
from app.auth.roles import (
    AUTONOMY_REPORT_PERMISSION,
    UserRole,
    get_minimum_role_for_method,
    has_autonomy_report_scope,
    is_autonomy_report_request,
    is_reporter_only_credential,
    mcp_scope_level,
    role_from_permissions,
)
from app.core.timezones import BUSINESS_TIMEZONE
from app.db.database import get_session
from app.db.migrations import MIGRATIONS
from app.db.models import AutonomousJob, AutonomousJobRun, ScheduledRun
from app.services import autonomy as svc

CATALOGUE_ITEM_KEYS = {
    "id", "source", "key", "name", "responsibility", "agentId", "agent", "host",
    "runner", "schedule", "timezone", "scheduleNote", "nextRunAt", "enabled",
    "lastRunAt", "lastStatus", "lastSummary", "lastError", "lastDurationMs",
    "health", "command", "runbookUrl", "owner", "notes", "scheduledRunId", "updatedAt",
}
RUN_KEYS = {"id", "runId", "status", "startedAt", "finishedAt", "durationMs", "summary", "error"}


def utc(*args) -> datetime:
    return datetime(*args, tzinfo=UTC)


def _agent(agent_id="cpl-colophon", display="Cpl. Colophon", name="colophon"):
    return SimpleNamespace(
        id=agent_id, name=name, display_name=display, title="Build Log writer",
        domain="content", avatar_url=None,
    )


def _brigade_run(**over):
    base = {
        "id": "ca78fd8b-e894-4d6b-a157-8c757ec3d47e", "name": "colophon-daily",
        "agent_id": "cpl-colophon", "cron": "15 8 * * *", "timezone": "UTC", "enabled": True,
        "last_run_at": datetime(2026, 10, 24, 8, 15, 3), "last_status": "success",
        "last_result_summary": "Wrote the day's story.", "description": "Writes the day's Build Log story from the commits.",
        "updated_at": datetime(2026, 10, 24, 8, 15, 4),
    }
    base.update(over)
    return SimpleNamespace(**base)


def _external_job(**over):
    base = {
        "key": "build-log-refresh", "name": "Build Log refresh", "agent_id": "cpl-colophon",
        "responsibility": "Refreshes the Build Log three times a day.", "host": "build-server",
        "runner": "cron", "schedule": "0 6,14,22 * * *", "timezone": "UTC", "schedule_note": None,
        "command": "/opt/jobs/build-log-refresh.sh",
        "runbook_url": None, "owner": "Ops team", "notes": AUDIT_NOTE, "enabled": True,
        "last_run_at": datetime(2026, 10, 24, 14, 0, 40), "last_status": "success",
        "last_summary": "3 new day stories", "last_error": None, "last_duration_ms": 40000,
        "updated_at": datetime(2026, 10, 24, 14, 0, 41),
    }
    base.update(over)
    return SimpleNamespace(**base)


AUDIT_NOTE = (
    "BROKEN: script missing since the 2026-04-30 git stash; recovered copy in "
    "scripts/recovered-20260825/. Found in: build-server crontab (ops) line 7."
)


def _sched(cron, tz="UTC", standard=True):
    return svc.parse_schedule(cron, tz, standard=standard)


# ── keys ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("key", [
    "build-log-refresh", "abc", "a1b", "0-9", "zpool-health", "a" + "-" * 118 + "b",
    "x" * 120,
])
def test_valid_job_keys(key):
    assert svc.is_valid_key(key)


@pytest.mark.parametrize("key", [
    "", "a", "ab", "-abc", "abc-", "Abc", "a_b", "a b", "a.b", "ab/c", "x" * 121,
    "build-log-refresh\n", None, 123,
])
def test_invalid_job_keys(key):
    assert not svc.is_valid_key(key)


def test_unknown_job_detail_names_the_registration_call():
    assert svc.unknown_job_detail("build-log-refresh") == (
        "No job 'build-log-refresh'. Register it with "
        "PUT /api/v1/autonomy/jobs/build-log-refresh first."
    )


# ── secrets ──────────────────────────────────────────────────────

SECRET_COMMANDS = [
    "run.sh --password=hunter2",
    "PASSWD: hunter2 run.sh",
    "export API_KEY=abc123 && run.sh",
    "curl -H 'X-API-Key: abc' https://brigade/api",
    "refresh.sh token=abc",
    "refresh.sh --secret:foo",
    "refresh.sh apikey=1",
    "pg_dump postgresql://brigade:REMOVED@db.internal/brigade",
    "curl https://bot:hunter2@api.example.com/x",
    "notify.sh sk-" + "a1B2c3D4e5F6g7H8i9J0",
    "OPENAI=sk-proj-" + "Ab12" * 8 + " run.sh",
    "gh.sh ghp_" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8",
    "slack.sh xoxb-" + "1234567890-0987654321-AbCdEfGhIjKl",  # split: CI's gitleaks scans source
    "aws.sh AKIA" + "ABCDEFGHIJKLMNOP",
    "report.sh ubk-" + "Zx9" * 10,
]


@pytest.mark.parametrize("command", SECRET_COMMANDS)
def test_command_that_carries_a_secret_is_refused(command):
    assert svc.looks_like_secret(command)
    assert svc.command_problem(command) == "Don't store secrets in the command; reference them by name."


SAFE_COMMANDS = [
    "/opt/jobs/build-log-refresh.sh",
    "systemctl start colophon-refresh.timer",
    "launchctl kickstart gui/501/com.magicunicorn.leadgen",
    "disk-check.sh --mode=nightly",
    "/opt/task-runner/run.sh",
    "risk-report.sh",
    "refresh.sh --token-file=/run/secrets/brigade",
    "git -C /srv/repo pull ssh://git@forgejo.internal/repo.git",
    "/opt/sk-tools/run.sh",
    "akiaboost.sh",
    # From the fleet inventory (204 real jobs): "sk-" inside ordinary words.
    "/usr/local/bin/disk-guard.sh",
    "kiosk-chromium-refresh",
    "/opt/jobs/lead-sweep.sh --since=yesterday",
]


def test_fleet_inventory_commands_pass_and_a_real_looking_key_fails():
    assert svc.command_problem("/usr/local/bin/disk-guard.sh") is None
    assert svc.command_problem("kiosk-chromium-refresh") is None
    real_looking = "notify.sh --via openai sk-proj-" + "Q9mZ2Lr7VwK4sNa8DyE1HcUx"
    assert svc.command_problem(real_looking) == svc.SECRET_IN_COMMAND
    # A key prefix inside a word is not a key; at a word boundary it is.
    assert not svc.looks_like_secret("kiosk-" + "a" * 30)
    assert svc.looks_like_secret("run.sh sk-" + "a" * 30)
    assert svc.looks_like_secret("run.sh\tghp_" + "B" * 36)
    assert not svc.looks_like_secret("xghp_" + "B" * 36)


@pytest.mark.parametrize("command", SAFE_COMMANDS)
def test_ordinary_commands_are_accepted(command):
    assert not svc.looks_like_secret(command)
    assert svc.command_problem(command) is None


def test_command_length_is_checked_after_the_secret_check():
    assert svc.command_problem(None) is None
    assert svc.command_problem("x" * 500) is None
    assert svc.command_problem("x" * 501) == "command must be at most 500 characters"
    # A long command that also carries a secret gets the secret message.
    assert svc.command_problem("password=1 " + "x" * 600) == svc.SECRET_IN_COMMAND


def test_runbook_url_with_userinfo_is_refused():
    assert svc.runbook_url_problem("https://wiki.internal/runbooks/colophon") is None
    assert svc.runbook_url_problem("https://ops:pw@wiki.internal/x") == svc.SECRET_IN_RUNBOOK_URL
    assert svc.runbook_url_problem("https://wiki/" + "x" * 500).startswith("runbookUrl must be at most")


def test_reported_text_is_masked_before_it_is_stored():
    assert svc.redact_secrets("curl: (22) https://bot:hunter2@api.example.com/x failed") == (
        "curl: (22) https://bot:***@api.example.com/x failed"
    )
    assert svc.redact_secrets("token=abc123 leaked") == "token=[redacted] leaked"
    assert svc.redact_secrets('API_KEY: "a b c" then') == "API_KEY: [redacted] then"
    key = "sk-" + "Q" * 24
    assert svc.redact_secrets(f"used {key} ok") == "used [redacted] ok"
    assert svc.redact_secrets("3 new day stories") == "3 new day stories"
    assert svc.redact_secrets(None) is None


def test_sanitize_masks_before_clipping_so_no_partial_key_survives():
    key = "ghp_" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8"
    text = "x" * 30 + " " + key  # clipping first would leave "ghp_000000000000000000000000000000000000" behind
    out = svc.sanitize_report_text(text, 40)
    assert "ghp_" not in out
    assert len(out) <= 40
    assert svc.sanitize_report_text("   ", 10) is None
    assert svc.sanitize_report_text(None, 10) is None
    assert svc.sanitize_report_text("  ok  ", 10) == "ok"


def test_clip_marks_truncation_and_respects_the_limit():
    assert svc.clip("short", 280) == "short"
    clipped = svc.clip("y" * 500, 280)
    assert len(clipped) == 280 and clipped.endswith("…")
    assert svc.clip(None, 280) is None


# ── time helpers ─────────────────────────────────────────────────

def test_iso_z_shapes():
    assert svc.iso_z(None) is None
    assert svc.iso_z(datetime(2026, 10, 24, 8, 15)) == "2026-10-24T08:15:00Z"
    aware = datetime(2026, 10, 24, 4, 15, tzinfo=timezone(timedelta(hours=-4)))
    assert svc.iso_z(aware) == "2026-10-24T08:15:00Z"
    assert svc.to_naive_utc(aware) == datetime(2026, 10, 24, 8, 15)


# ── schedules: next run, interval, timezones, DST ────────────────

def test_next_run_is_the_next_fire_time_in_utc():
    sched = _sched("15 8 * * *")
    nxt = svc.next_run_at(sched, utc(2026, 10, 24, 22, 0))
    assert svc.iso_z(nxt) == "2026-10-25T08:15:00Z"


def test_next_run_is_inclusive_of_an_exact_fire_time():
    sched = _sched("15 8 * * *")
    assert svc.next_run_at(sched, utc(2026, 10, 24, 8, 15)) == utc(2026, 10, 24, 8, 15)


def test_next_run_is_null_when_paused_or_unscheduled():
    sched = _sched("15 8 * * *")
    assert svc.next_run_at(sched, utc(2026, 10, 24), enabled=False) is None
    assert svc.next_run_at(None, utc(2026, 10, 24)) is None


def test_next_run_in_new_york_across_the_end_of_dst():
    sched = _sched("0 2 * * *", "America/New_York")
    # 02:00 EDT on Oct 31 is 06:00Z; DST ends Nov 1, so 02:00 EST is 07:00Z.
    assert svc.iso_z(svc.next_run_at(sched, utc(2026, 10, 31, 0, 0))) == "2026-10-31T06:00:00Z"
    assert svc.iso_z(svc.next_run_at(sched, utc(2026, 11, 1, 0, 0))) == "2026-11-01T07:00:00Z"
    # The day DST ends is 25 hours long; the day after is 24 again.
    assert svc.schedule_interval(sched, utc(2026, 10, 31, 0, 0)) == timedelta(hours=25)
    assert svc.schedule_interval(sched, utc(2026, 11, 2, 0, 0)) == timedelta(hours=24)


def test_interval_is_the_gap_between_the_next_two_fire_times():
    assert svc.schedule_interval(_sched("*/15 * * * *"), utc(2026, 10, 24, 10, 7)) == timedelta(minutes=15)
    assert svc.schedule_interval(_sched("0 6,14,22 * * *"), utc(2026, 10, 24, 15, 0)) == timedelta(hours=8)
    # Uneven: from 10:00 the next two are 14:00 and 06:00 (16h); from 15:00, 06:00 and 14:00 (8h).
    assert svc.schedule_interval(_sched("0 6,14 * * *"), utc(2026, 10, 24, 10, 0)) == timedelta(hours=16)
    assert svc.schedule_interval(_sched("0 6,14 * * *"), utc(2026, 10, 24, 15, 0)) == timedelta(hours=8)
    assert svc.schedule_interval(None, utc(2026, 10, 24)) is None


@pytest.mark.parametrize("field,expected", [
    ("*", "*"),
    ("1-5", "mon,tue,wed,thu,fri"),
    ("0", "sun"),
    ("7", "sun"),
    ("0,6", "sat,sun"),
    ("*/2", "tue,thu,sat,sun"),     # standard cron: Sun, Tue, Thu, Sat
    ("5-7", "fri,sat,sun"),
    ("fri-sun", "fri,sat,sun"),
    ("1-5/2", "mon,wed,fri"),
    ("MON-FRI", "mon,tue,wed,thu,fri"),
    ("0-7", "*"),
])
def test_standard_day_of_week_is_translated_for_apscheduler(field, expected):
    assert svc.standard_dow_to_aps(field) == expected


@pytest.mark.parametrize("field", ["8", "1-", "x", "5-1", "*/0", "L", "?", ""])
def test_bad_day_of_week_is_rejected(field):
    with pytest.raises(ValueError):
        svc.standard_dow_to_aps(field)


def test_all_catalogue_crons_use_standard_semantics():
    saturday_evening = utc(2026, 10, 24, 20, 0)  # Sat Oct 24, 16:00 in New York
    standard = _sched("40 8 * * 1-5", "America/New_York", standard=True)
    brigade = _sched("40 8 * * 1-5", "America/New_York", standard=False)
    # Every catalogue schedule now shares standard cron semantics with dispatch.
    assert svc.iso_z(standard.fire_at_or_after(saturday_evening)) == "2026-10-26T12:40:00Z"
    assert svc.iso_z(brigade.fire_at_or_after(saturday_evening)) == "2026-10-26T12:40:00Z"


def test_standard_cron_fires_when_day_of_month_or_day_of_week_matches():
    sched = _sched("0 9 1 * 1")  # the 1st of the month OR any Monday
    fires, cursor = [], utc(2026, 10, 24)
    for _ in range(4):
        cursor = sched.fire_at_or_after(cursor)
        fires.append(cursor.date().isoformat())
        cursor += timedelta(microseconds=1)
    assert fires == ["2026-10-26", "2026-11-01", "2026-11-02", "2026-11-09"]


def test_validate_schedule():
    assert svc.validate_schedule("  0   6,14,22 * * *  ", "UTC") == "0 6,14,22 * * *"
    for bad in ["* * * *", "60 * * * *", "a b c d e", "*/0 * * * *", "0 0 * * 8"]:
        with pytest.raises(ValueError, match="invalid schedule"):
            svc.validate_schedule(bad, "UTC")
    with pytest.raises(ValueError, match="never fires"):
        svc.validate_schedule("0 0 31 2 *", "UTC")


def test_validate_timezone():
    assert svc.validate_timezone("America/New_York") == "America/New_York"
    assert svc.validate_timezone(" UTC ") == "UTC"
    for bad in ["Not/AZone", "", "../etc/passwd"]:
        with pytest.raises(ValueError, match="unknown timezone"):
            svc.validate_timezone(bad)


def test_unparseable_stored_schedule_never_breaks_the_catalogue():
    assert svc.safe_schedule("not a cron", "UTC", standard=True) is None
    assert svc.safe_schedule(None, "UTC", standard=True) is None
    assert svc.safe_schedule("15 8 * * *", "Not/AZone", standard=False) is None


# ── health ───────────────────────────────────────────────────────

def _health(now, *, enabled=True, last_status="success", last_run_at=None, cron="15 8 * * *",
            tz="UTC", standard=True):
    schedule = svc.safe_schedule(cron, tz, standard=standard) if cron else None
    return svc.compute_health(enabled=enabled, last_status=last_status, last_run_at=last_run_at,
                              schedule=schedule, now=now)


def test_health_paused_beats_everything():
    assert _health(utc(2026, 10, 24), enabled=False, last_status="error",
                   last_run_at=datetime(2026, 1, 1)) == "paused"


@pytest.mark.parametrize("status", ["error", "timeout", "degraded", "ERROR", "partial"])
def test_health_failing(status):
    assert _health(utc(2026, 10, 24, 9), last_status=status, last_run_at=datetime(2026, 10, 24, 8, 15)) == "failing"


def test_health_never_when_it_has_not_run():
    assert _health(utc(2026, 10, 24), last_status=None, last_run_at=None) == "never"


def test_health_ok_and_stale_for_a_daily_job():
    ran = datetime(2026, 10, 24, 8, 15, 0)
    assert _health(utc(2026, 10, 24, 22, 0), last_run_at=ran) == "ok"
    assert _health(utc(2026, 10, 26, 9, 0), last_run_at=ran) == "stale"


def test_stale_threshold_equals_the_contract_formula_for_an_evenly_spaced_schedule():
    """now - lastRunAt > 1.5 x interval + 15 min, with the last run on a fire time."""
    ran = datetime(2026, 10, 24, 8, 15, 0)
    threshold = utc(2026, 10, 24, 8, 15) + 1.5 * timedelta(days=1) + timedelta(minutes=15)
    assert svc.stale_after(_sched("15 8 * * *"), ran) == threshold
    assert _health(threshold, last_run_at=ran) == "ok"
    assert _health(threshold + timedelta(seconds=1), last_run_at=ran) == "stale"
    quarter = svc.stale_after(_sched("*/15 * * * *"), datetime(2026, 10, 24, 10, 0))
    assert quarter == utc(2026, 10, 24, 10, 0) + 1.5 * timedelta(minutes=15) + timedelta(minutes=15)


def test_twice_daily_job_is_not_stale_overnight_but_is_when_it_misses_a_run():
    ran = datetime(2026, 10, 24, 14, 0, 30)  # the 14:00 run; next is 06:00, then 14:00
    kw = {"cron": "0 6,14 * * *", "last_run_at": ran}
    assert _health(utc(2026, 10, 25, 5, 59), **kw) == "ok"   # just before the 06:00 run
    assert _health(utc(2026, 10, 25, 10, 15), **kw) == "ok"  # 06:00 + 4h + 15m grace
    assert _health(utc(2026, 10, 25, 10, 16), **kw) == "stale"


def test_weekday_job_is_not_stale_over_the_weekend():
    ran = datetime(2026, 10, 23, 12, 40, 5)  # Friday's 08:40 EDT run
    kw = {"cron": "40 8 * * 1-5", "tz": "America/New_York", "last_run_at": ran}
    assert _health(utc(2026, 10, 25, 23, 0), **kw) == "ok"   # Sunday night
    assert _health(utc(2026, 10, 27, 0, 55), **kw) == "ok"   # Monday 08:40 + 12h15m
    assert _health(utc(2026, 10, 27, 0, 56), **kw) == "stale"


def test_continuous_job_without_a_cron_is_never_stale():
    assert _health(utc(2026, 10, 24), cron=None, last_run_at=datetime(2026, 9, 1)) == "ok"


def test_a_run_stuck_in_running_goes_stale():
    assert _health(utc(2026, 10, 26), last_status="running", last_run_at=datetime(2026, 10, 24, 8, 15)) == "stale"


def test_a_status_outside_the_enum_is_failing():
    # Brigade's own rows carry other words in real data (dogfood zpool-health: "degraded").
    assert _health(utc(2026, 10, 24, 9), last_status="degraded", last_run_at=datetime(2026, 10, 24, 8, 15)) == "failing"


@pytest.mark.parametrize("status", ["success", "skipped", "running", "Success", None, ""])
def test_only_success_skipped_running_or_nothing_are_not_failing(status):
    assert not svc.is_failing_status(status)
    ran = datetime(2026, 10, 24, 8, 15) if status is not None else None
    assert _health(utc(2026, 10, 24, 9), last_status=status, last_run_at=ran) in ("ok", "never")


def test_brigade_item_passes_an_off_enum_status_through_as_failing():
    run = _brigade_run(enabled=True, last_status="degraded",
                       last_result_summary="pool tank DEGRADED: 1 of 2 mirrors offline")
    item = svc.build_brigade_item(run, None, utc(2026, 10, 24, 9))
    assert item["lastStatus"] == "degraded"
    assert item["health"] == "failing"
    assert item["lastError"] == "pool tank DEGRADED: 1 of 2 mirrors offline"


# ── catalogue items ──────────────────────────────────────────────

def test_brigade_item_maps_a_scheduled_run():
    now = utc(2026, 10, 24, 22, 0)
    item = svc.build_brigade_item(_brigade_run(), _agent(), now, last_duration_ms=1234)
    assert set(item) == CATALOGUE_ITEM_KEYS
    assert item["id"] == "brigade:ca78fd8b-e894-4d6b-a157-8c757ec3d47e"
    assert item["source"] == "brigade"
    assert item["key"] == item["scheduledRunId"] == "ca78fd8b-e894-4d6b-a157-8c757ec3d47e"
    assert item["responsibility"] == "Writes the day's Build Log story from the commits."
    assert item["host"] == "brigade" and item["runner"] == "brigade-scheduler"
    assert item["schedule"] == "15 8 * * *" and item["timezone"] == "UTC"
    assert item["nextRunAt"] == "2026-10-25T08:15:00Z"
    assert item["lastRunAt"] == "2026-10-24T08:15:03Z"
    assert item["lastStatus"] == "success" and item["lastError"] is None
    assert item["lastDurationMs"] == 1234
    assert item["health"] == "ok"
    assert item["command"] is None and item["runbookUrl"] is None and item["owner"] is None
    assert item["notes"] is None
    assert item["scheduleNote"] is None
    assert item["agent"] == {
        "id": "cpl-colophon", "name": "colophon", "displayName": "Cpl. Colophon",
        "title": "Build Log writer", "domain": "content", "avatarUrl": None,
    }
    assert item["updatedAt"] == "2026-10-24T08:15:04Z"


def test_brigade_item_summary_preview_and_error():
    long = "z" * 900
    item = svc.build_brigade_item(
        _brigade_run(last_status="error", last_result_summary=long), None, utc(2026, 10, 24, 9)
    )
    assert len(item["lastSummary"]) == 280 and item["lastSummary"].endswith("…")
    assert item["lastError"] == long
    assert item["health"] == "failing"
    assert item["agent"] is None


def test_brigade_item_defaults_a_missing_timezone_to_the_scheduler_default():
    item = svc.build_brigade_item(_brigade_run(timezone=None, description=None), None, utc(2026, 10, 24, 9))
    assert item["timezone"] == BUSINESS_TIMEZONE
    assert item["responsibility"] is None


def test_paused_brigade_item_has_no_next_run():
    item = svc.build_brigade_item(_brigade_run(enabled=False), None, utc(2026, 10, 24, 9))
    assert item["health"] == "paused" and item["nextRunAt"] is None


def test_external_item_maps_an_outside_job():
    now = utc(2026, 10, 24, 15, 0)
    item = svc.build_external_item(_external_job(), _agent(), now)
    assert set(item) == CATALOGUE_ITEM_KEYS
    assert item["id"] == "external:build-log-refresh" and item["key"] == "build-log-refresh"
    assert item["source"] == "external" and item["scheduledRunId"] is None
    assert item["host"] == "build-server" and item["runner"] == "cron"
    assert item["nextRunAt"] == "2026-10-24T22:00:00Z"
    assert item["lastSummary"] == "3 new day stories" and item["lastDurationMs"] == 40000
    assert item["command"] == "/opt/jobs/build-log-refresh.sh"
    assert item["owner"] == "Ops team" and item["health"] == "ok"
    assert item["notes"] == AUDIT_NOTE


def test_external_item_with_an_unknown_agent_has_a_null_agent():
    item = svc.build_external_item(_external_job(agent_id="ghost"), None, utc(2026, 10, 24, 15))
    assert item["agentId"] == "ghost" and item["agent"] is None


# ── sorting and counts ───────────────────────────────────────────

def _item(name, health, source="external", agent=None, agent_id=None):
    return {"id": f"{source}:{name}", "source": source, "name": name, "health": health,
            "agent": agent, "agentId": agent_id}


def test_sort_order_is_health_then_agent_then_name():
    items = [
        _item("zeta", "ok", agent={"displayName": "Bravo"}),
        _item("paused-one", "paused", agent={"displayName": "Alpha"}),
        _item("alpha-ok", "ok", agent={"displayName": "bravo"}),
        _item("unassigned", "ok"),
        _item("first", "ok", agent={"displayName": "Alpha"}),
        _item("never-ran", "never", agent={"displayName": "Zulu"}),
        _item("late", "stale", agent={"name": "omega"}),
        _item("broken", "failing", source="brigade", agent={"displayName": "Zulu"}),
    ]
    order = [i["name"] for i in svc.sort_catalogue(items)]
    assert order == ["broken", "late", "never-ran", "first", "alpha-ok", "zeta", "unassigned", "paused-one"]


def test_counts():
    items = [
        _item("a", "failing", source="brigade"),
        _item("b", "stale"),
        _item("c", "never"),
        _item("d", "ok", source="brigade"),
        _item("e", "paused"),
        _item("f", "paused"),
    ]
    assert svc.catalogue_counts(items) == {
        "total": 6, "brigade": 2, "external": 4, "failing": 1, "stale": 1, "paused": 2, "never": 1,
    }
    assert svc.catalogue_counts([]) == {
        "total": 0, "brigade": 0, "external": 0, "failing": 0, "stale": 0, "paused": 0, "never": 0,
    }


# ── registering ──────────────────────────────────────────────────

def _upsert(**over):
    body = {"name": "Build Log refresh", "responsibility": "Refreshes the Build Log.",
                "host": "build-server", "runner": "cron"}
    body.update(over)
    return routes.AutonomousJobUpsert(**body)


def test_first_registration_writes_every_column_with_defaults():
    body = _upsert(schedule="0 6,14,22 * * *")
    values = svc.plan_job_upsert(body.model_dump(), body.model_fields_set, creating=True)
    assert values["enabled"] is True and values["timezone"] == "UTC"
    assert values["command"] is None and values["schedule"] == "0 6,14,22 * * *"
    assert values["notes"] is None
    assert set(values) == set(svc.JOB_FIELD_COLUMNS.values())


def test_re_registration_only_touches_what_was_sent():
    body = _upsert()  # a script re-registering on every run, without enabled/owner
    values = svc.plan_job_upsert(body.model_dump(), body.model_fields_set, creating=False)
    assert set(values) == {"name", "responsibility", "host", "runner"}
    assert "notes" not in values  # an audit's notes survive a script's re-registration
    cleared = _upsert(command=None, enabled=False, notes=AUDIT_NOTE)
    values = svc.plan_job_upsert(cleared.model_dump(), cleared.model_fields_set, creating=False)
    assert values["command"] is None and values["enabled"] is False
    assert values["notes"] == AUDIT_NOTE


# ── run reports ──────────────────────────────────────────────────

def _row(values, run_id=None):
    return SimpleNamespace(**{**values, "run_id": run_id})


def test_running_then_success_with_the_same_run_id_closes_one_row():
    t0 = utc(2026, 10, 24, 14, 0, 0)
    opened = svc.apply_run_report(svc.RunReport(status="running", run_id="r-1"), None, now=t0)
    assert not opened.matched
    assert opened.run_values["status"] == "running"
    assert opened.run_values["started_at"] == datetime(2026, 10, 24, 14, 0, 0)
    assert opened.run_values["run_id"] == "r-1"
    assert opened.job_updates["last_status"] == "running"
    assert opened.job_updates["last_run_at"] == datetime(2026, 10, 24, 14, 0, 0)
    assert "last_error" not in opened.job_updates  # a new run doesn't hide the old failure yet

    row = _row(opened.run_values, run_id="r-1")
    t1 = t0 + timedelta(seconds=42, milliseconds=500)
    closed = svc.apply_run_report(
        svc.RunReport(status="success", run_id="r-1", summary="3 new day stories"), row, now=t1
    )
    assert closed.matched
    assert "run_id" not in closed.run_values  # the matched row keeps its key
    assert closed.run_values["status"] == "success"
    assert closed.run_values["finished_at"] == datetime(2026, 10, 24, 14, 0, 42, 500000)
    assert closed.run_values["duration_ms"] == 42500
    assert closed.job_updates == {
        "last_run_at": datetime(2026, 10, 24, 14, 0, 42, 500000),
        "last_status": "success",
        "last_summary": "3 new day stories",
        "last_duration_ms": 42500,
        "last_error": None,
    }


def test_success_without_a_run_id_inserts_a_finished_row():
    now = utc(2026, 10, 24, 14, 1)
    out = svc.apply_run_report(svc.RunReport(status="success", summary="done"), None, now=now)
    assert not out.matched
    v = out.run_values
    assert v["status"] == "success" and v["run_id"] is None
    assert v["started_at"] == v["finished_at"] == datetime(2026, 10, 24, 14, 1)
    assert v["duration_ms"] is None


def test_finished_row_from_timestamps_and_from_duration():
    now = utc(2026, 10, 24, 15)
    out = svc.apply_run_report(
        svc.RunReport(status="success", started_at=utc(2026, 10, 24, 14, 0, 0),
                      finished_at=utc(2026, 10, 24, 14, 0, 30)),
        None, now=now,
    )
    assert out.run_values["duration_ms"] == 30000
    assert out.job_updates["last_run_at"] == datetime(2026, 10, 24, 14, 0, 30)
    out = svc.apply_run_report(svc.RunReport(status="error", duration_ms=5000), None, now=now)
    assert out.run_values["finished_at"] == datetime(2026, 10, 24, 15)
    assert out.run_values["started_at"] == datetime(2026, 10, 24, 14, 59, 55)
    assert out.run_values["duration_ms"] == 5000


def test_given_duration_wins_over_the_timestamps():
    out = svc.apply_run_report(
        svc.RunReport(status="success", started_at=utc(2026, 10, 24, 14), finished_at=utc(2026, 10, 24, 14, 1),
                      duration_ms=1234),
        None, now=utc(2026, 10, 24, 15),
    )
    assert out.run_values["duration_ms"] == 1234


def test_last_run_at_is_finished_then_started_then_now():
    now = utc(2026, 10, 24, 15)
    started_only = svc.apply_run_report(
        svc.RunReport(status="skipped", started_at=utc(2026, 10, 24, 14)), None, now=now
    )
    assert started_only.job_updates["last_run_at"] == datetime(2026, 10, 24, 14)
    neither = svc.apply_run_report(svc.RunReport(status="skipped"), None, now=now)
    assert neither.job_updates["last_run_at"] == datetime(2026, 10, 24, 15)


def test_success_clears_last_error_and_failures_set_it():
    now = utc(2026, 10, 24, 15)
    assert svc.apply_run_report(svc.RunReport(status="success"), None, now=now).job_updates["last_error"] is None
    err = svc.apply_run_report(svc.RunReport(status="error", error="exit 2", summary="x"), None, now=now)
    assert err.job_updates["last_error"] == "exit 2"
    timeout = svc.apply_run_report(svc.RunReport(status="timeout", summary="killed after 300s"), None, now=now)
    assert timeout.job_updates["last_error"] == "killed after 300s"
    skipped = svc.apply_run_report(svc.RunReport(status="skipped"), None, now=now)
    assert "last_error" not in skipped.job_updates


def test_repeated_running_report_keeps_the_original_start():
    t0 = utc(2026, 10, 24, 14)
    row = _row(svc.apply_run_report(svc.RunReport(status="running", run_id="r-1"), None, now=t0).run_values,
               run_id="r-1")
    again = svc.apply_run_report(svc.RunReport(status="running", run_id="r-1"), row, now=t0 + timedelta(minutes=1))
    assert again.matched and again.run_values["started_at"] == datetime(2026, 10, 24, 14)


def test_retried_terminal_report_updates_the_same_row():
    t0 = utc(2026, 10, 24, 14)
    first = svc.apply_run_report(
        svc.RunReport(status="success", run_id="r-9", summary="ok"), None, now=t0
    )
    row = _row(first.run_values, run_id="r-9")
    retry = svc.apply_run_report(svc.RunReport(status="success", run_id="r-9"), row, now=t0 + timedelta(seconds=5))
    assert retry.matched  # no duplicate history row
    assert retry.run_values["finished_at"] == datetime(2026, 10, 24, 14)  # keeps its finish time
    assert retry.run_values["summary"] == "ok"


def test_report_text_is_clipped_and_masked():
    out = svc.apply_run_report(
        svc.RunReport(status="error", summary="s" * 3000,
                      error="curl https://bot:hunter2@api.example.com failed " + "e" * 5000),
        None, now=utc(2026, 10, 24),
    )
    assert len(out.run_values["summary"]) == 2000
    assert len(out.run_values["error"]) == 4000
    assert "hunter2" not in out.run_values["error"]
    assert out.job_updates["last_error"] == out.run_values["error"]


def test_aware_timestamps_are_stored_as_naive_utc():
    eastern = timezone(timedelta(hours=-4))
    out = svc.apply_run_report(
        svc.RunReport(status="success", started_at=datetime(2026, 10, 24, 10, 0, tzinfo=eastern),
                      finished_at=datetime(2026, 10, 24, 10, 0, 1, tzinfo=eastern)),
        None, now=utc(2026, 10, 24, 15),
    )
    assert out.run_values["started_at"] == datetime(2026, 10, 24, 14, 0)
    assert out.run_values["started_at"].tzinfo is None
    assert out.run_values["duration_ms"] == 1000


def test_durations_fit_a_postgres_integer():
    out = svc.apply_run_report(
        svc.RunReport(status="success", started_at=utc(1990, 1, 1), finished_at=utc(2026, 1, 1)),
        None, now=utc(2026, 10, 24),
    )
    assert out.run_values["duration_ms"] == 2_147_483_647


def test_unknown_key_route_helper_is_a_404_with_the_contract_message():
    with pytest.raises(HTTPException) as exc:
        routes._require_job(None, "no-such-job")
    assert exc.value.status_code == 404
    assert exc.value.detail == svc.unknown_job_detail("no-such-job")
    job = SimpleNamespace(key="x")
    assert routes._require_job(job, "x") is job


# ── request validation ───────────────────────────────────────────

def test_upsert_body_defaults_and_normalisation():
    body = _upsert(schedule=" 0  6,14,22 * * * ", agentId="  ", scheduleNote="", name="  Build Log  ")
    assert body.timezone == "UTC" and body.enabled is True
    assert body.schedule == "0 6,14,22 * * *"
    assert body.agentId is None and body.scheduleNote is None
    assert body.name == "Build Log"


@pytest.mark.parametrize("over,field", [
    ({"schedule": "61 * * * *"}, "schedule"),
    ({"schedule": "* * * *"}, "schedule"),
    ({"schedule": "0 0 31 2 *"}, "schedule"),
    ({"timezone": "Mars/Olympus_Mons"}, "timezone"),
    ({"runner": "brigade-scheduler"}, "runner"),
    ({"runner": "cronjob"}, "runner"),
    ({"name": "n" * 256}, "name"),
    ({"name": "   "}, "name"),
    ({"responsibility": "r" * 2001}, "responsibility"),
    ({"host": "h" * 121}, "host"),
    ({"scheduleNote": "s" * 256}, "scheduleNote"),
    ({"owner": "o" * 256}, "owner"),
    ({"agentId": "a" * 256}, "agentId"),
])
def test_upsert_body_rejects(over, field):
    with pytest.raises(ValidationError) as exc:
        _upsert(**over)
    assert [e["loc"] for e in exc.value.errors()] == [(field,)]


@pytest.mark.parametrize("missing", ["name", "responsibility", "host", "runner"])
def test_upsert_body_requires(missing):
    body = {"name": "n", "responsibility": "r", "host": "h", "runner": "cron"}
    body.pop(missing)
    with pytest.raises(ValidationError):
        routes.AutonomousJobUpsert(**body)


def test_every_runner_but_brigades_own_is_accepted():
    for runner in svc.EXTERNAL_RUNNERS:
        assert _upsert(runner=runner).runner == runner


def test_secrets_are_judged_by_the_route_not_echoed_by_pydantic():
    # The body model takes the value as-is; the route answers with a message
    # that never repeats it (see test_put_with_a_secret_in_the_command_is_refused).
    assert _upsert(command="run.sh --password=hunter2").command == "run.sh --password=hunter2"
    assert _upsert(notes="token=abc").notes == "token=abc"


def test_notes_field():
    assert _upsert(notes=AUDIT_NOTE).notes == AUDIT_NOTE
    assert _upsert(notes="   ").notes is None
    assert _upsert().notes is None
    assert svc.notes_problem(AUDIT_NOTE) is None
    assert svc.notes_problem(None) is None
    assert svc.notes_problem("n" * 2000) is None
    assert svc.notes_problem("n" * 2001) == "notes must be at most 2000 characters"
    for leaky in ["rotated; new password=hunter2", "see https://bot:pw@wiki/x", "key sk-" + "Z" * 24]:
        assert svc.notes_problem(leaky) == "Don't store secrets in the notes; reference them by name."


def test_agent_ids_may_contain_dots():
    # Colophon's dogfood id is "cpl.-colophon": existence is checked, format is not.
    assert _upsert(agentId="cpl.-colophon").agentId == "cpl.-colophon"


def test_run_report_body():
    body = routes.RunReportBody(status="success", startedAt="2026-10-24T14:00:00Z", summary="x" * 5000)
    assert body.startedAt == utc(2026, 10, 24, 14)
    assert len(body.summary) == 5000  # clipped when applied, never rejected
    assert routes.RunReportBody(status="running", runId="  ").runId is None
    for bad in [{"status": "done"}, {"status": "success", "runId": "r" * 121},
                {"status": "success", "durationMs": -1}, {"status": "success", "durationMs": 2**31},
                {"status": "success", "startedAt": "yesterday"}]:
        with pytest.raises(ValidationError):
            routes.RunReportBody(**bad)


def test_scheduled_run_description_round_trip():
    create = ScheduledRunCreate(name="d", agentId="a", prompt="p", cron="0 2 * * *",
                                description="Writes the day's Build Log story.")
    assert create.description == "Writes the day's Build Log story."
    assert ScheduledRunCreate(name="d", agentId="a", prompt="p", cron="0 2 * * *").description is None
    assert ScheduledRunUpdate(description="").description == ""
    with pytest.raises(ValidationError):
        ScheduledRunUpdate(description="d" * 2001)
    run = ScheduledRun(id="r", name="d", agent_id="a", prompt="p", cron="0 2 * * *",
                       timezone="UTC", enabled=True, max_runtime_seconds=300, description="Owns X.")
    assert run.to_dict()["description"] == "Owns X."


def test_model_serializers():
    job = AutonomousJob(id="j", key="k-1", name="n", responsibility="r", host="h", runner="cron",
                        timezone="UTC", enabled=True, created_at=datetime(2026, 10, 24),
                        updated_at=datetime(2026, 10, 24, 1))
    assert job.to_dict()["key"] == "k-1" and job.to_dict()["updatedAt"] == "2026-10-24T01:00:00Z"
    assert job.to_dict()["notes"] is None
    run = AutonomousJobRun(id="r", job_id="j", run_id="x", status="success",
                           started_at=datetime(2026, 10, 24), finished_at=datetime(2026, 10, 24, 0, 0, 1),
                           duration_ms=1000, summary="s", error=None)
    assert set(run.to_dict()) == RUN_KEYS
    assert run.to_dict()["finishedAt"] == "2026-10-24T00:00:01Z"


# ── migration ────────────────────────────────────────────────────

def _autonomy_migration():
    versions = [m[0] for m in MIGRATIONS]
    assert versions.count("20261024_01_autonomy_catalogue") == 1
    return next(sql for version, _, sql in MIGRATIONS if version == "20261024_01_autonomy_catalogue")


def test_migration_is_idempotent_and_turns_rls_on_both_tables():
    statements = _autonomy_migration()
    sql = "\n".join(statements)
    assert "ALTER TABLE scheduled_runs ADD COLUMN IF NOT EXISTS description text" in sql
    for stmt in statements:
        head = stmt.strip().split("\n")[0]
        if head.startswith("CREATE TABLE") or head.startswith("CREATE INDEX"):
            assert "IF NOT EXISTS" in head, head
    for table in ("autonomous_jobs", "autonomous_job_runs"):
        assert f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY" in statements
        assert f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY" in statements
        drop = statements.index(f"DROP POLICY IF EXISTS {table}_org_isolation ON {table}")
        create = next(i for i, s in enumerate(statements)
                      if s.strip().startswith(f"CREATE POLICY {table}_org_isolation ON {table}"))
        assert drop < create
        assert f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO brigade_app" in sql
    assert "USING (org_id = current_org_id()) WITH CHECK (org_id = current_org_id())" in sql
    assert "WHERE j.id = autonomous_job_runs.job_id" in sql
    assert "UNIQUE (org_id, key)" in sql
    assert "(job_id, started_at DESC)" in sql


@pytest.mark.parametrize("model", [AutonomousJob, AutonomousJobRun])
def test_migration_ddl_matches_the_orm_columns(model):
    sql = "\n".join(_autonomy_migration())
    table = re.search(
        rf"CREATE TABLE IF NOT EXISTS {model.__tablename__} \((.*?)\n\s*\)\s*$", sql, re.S | re.M
    ).group(1)
    declared = {line.strip().split()[0] for line in table.splitlines()
                if line.strip() and not line.strip().startswith("CONSTRAINT")}
    assert declared == {c.name for c in model.__table__.columns}


# ── the autonomy:report permission ───────────────────────────────

def _reporter(**over):
    perms = [AUTONOMY_REPORT_PERMISSION]
    base = {"id": "reporter-key", "role": role_from_permissions(perms), "permissions": perms,
                "key_org_id": "org-a"}
    base.update(over)
    return AuthUser(**base)


def test_the_permission_keeps_a_key_at_the_lowest_role():
    assert role_from_permissions([AUTONOMY_REPORT_PERMISSION]) == UserRole.VIEWER
    assert role_from_permissions([AUTONOMY_REPORT_PERMISSION], base_role="viewer") == UserRole.VIEWER
    assert role_from_permissions([AUTONOMY_REPORT_PERMISSION, "read"]) == UserRole.VIEWER
    assert role_from_permissions(["AUTONOMY:REPORT"]) == UserRole.VIEWER


def test_a_reporter_key_cannot_pass_require_operator_but_passes_the_reporter_gate():
    user = _reporter()
    with pytest.raises(HTTPException) as exc:
        require_operator(user)
    assert exc.value.status_code == 403
    assert require_autonomy_reporter(user) is user


def test_reporter_gate_admits_operators_and_admins_and_refuses_plain_viewers():
    for role in (UserRole.OPERATOR, UserRole.ADMIN):
        user = AuthUser(id="u", role=role, permissions=[])
        assert require_autonomy_reporter(user) is user
    with pytest.raises(HTTPException) as exc:
        require_autonomy_reporter(AuthUser(id="v", role=UserRole.VIEWER, permissions=["read"]))
    assert exc.value.status_code == 403


def test_the_permission_gives_no_mcp_access():
    assert mcp_scope_level(UserRole.VIEWER, [AUTONOMY_REPORT_PERMISSION]) == 0
    assert mcp_scope_level(UserRole.VIEWER, []) == 1  # the role fallback is unchanged
    assert mcp_scope_level(UserRole.VIEWER, [AUTONOMY_REPORT_PERMISSION, "read"]) == 1


def test_scope_helpers():
    assert has_autonomy_report_scope([" Autonomy:Report "])
    assert not has_autonomy_report_scope(["read"])
    assert is_reporter_only_credential([AUTONOMY_REPORT_PERMISSION])
    assert not is_reporter_only_credential([AUTONOMY_REPORT_PERMISSION, "read"])
    assert not is_reporter_only_credential([])
    assert is_autonomy_report_request("/api/v1/autonomy/jobs/build-log-refresh", "PUT")
    assert is_autonomy_report_request("/api/v1/autonomy/jobs/build-log-refresh/runs", "post")
    assert not is_autonomy_report_request("/api/v1/autonomy/jobs/build-log-refresh/runs", "GET")
    assert not is_autonomy_report_request("/api/v1/autonomy/jobs/build-log-refresh", "DELETE")
    assert not is_autonomy_report_request("/api/v1/autonomy", "GET")
    assert not is_autonomy_report_request("/api/v1/autonomy/jobs/a/b/runs", "POST")


def test_global_gate_lets_reporting_through_and_ignores_agents_in_a_key():
    gate = get_minimum_role_for_method
    assert gate("/api/v1/autonomy/jobs/build-log-refresh", "PUT") == UserRole.VIEWER
    assert gate("/api/v1/autonomy/jobs/build-log-refresh/runs", "POST") == UserRole.VIEWER
    assert gate("/api/v1/autonomy", "GET") == UserRole.VIEWER
    assert gate("/api/v1/autonomy/jobs/build-log-refresh", "DELETE") == UserRole.OPERATOR
    # A key that happens to start with "agents" must not pull the /agents rules
    # (DELETE/PUT there require ADMIN).
    assert gate("/api/v1/autonomy/jobs/agents-sync", "DELETE") == UserRole.OPERATOR
    assert gate("/api/v1/autonomy/jobs/agents-sync", "PUT") == UserRole.VIEWER
    assert gate("/api/v1/autonomy/jobs/knowledge-refresh/runs", "POST") == UserRole.VIEWER
    # Everything else is unchanged.
    assert gate("/api/v1/agents/x", "PUT") == UserRole.ADMIN
    assert gate("/api/v1/scheduled-runs", "POST") == UserRole.OPERATOR
    assert gate("/api/v1/scheduled-runs", "GET") == UserRole.VIEWER


def test_the_key_minting_endpoints_accept_the_permission():
    perms = [AUTONOMY_REPORT_PERMISSION]
    assert GenerateKeyRequest(name="Autonomy reporter", permissions=perms).permissions == perms
    assert CreateApiKeyRequest(name="Autonomy reporter", permissions=perms).permissions == perms
    assert CreateUserKeyRequest(email="ops@example.com", name="Autonomy reporter",
                                permissions=perms).permissions == perms


async def test_an_agent_key_minted_with_the_permission_stores_it_as_given():
    from app.db.repositories import ApiKeyRepository

    class _Session:
        added = None

        def add(self, obj):
            self.added = obj

        async def commit(self):
            return None

        async def refresh(self, obj):
            return None

    session = _Session()
    result = await ApiKeyRepository(session).generate(
        "the-colonel", {"name": "Autonomy reporter", "permissions": [AUTONOMY_REPORT_PERMISSION],
                        "expiresInDays": 1},
        org_id="org-a",
    )
    assert session.added.permissions == [AUTONOMY_REPORT_PERMISSION]
    assert result["permissions"] == [AUTONOMY_REPORT_PERMISSION]
    assert role_from_permissions(session.added.permissions) == UserRole.VIEWER


# ── routes: real router + real global gate over an in-memory store ──

class _Store:
    def __init__(self):
        self.jobs: dict = {}
        self.runs: list = []
        self.agents = {"cpl-colophon": _agent(), "cpl.-colophon": _agent("cpl.-colophon")}
        self.scheduled_runs = [_brigade_run()]


class _FakeSession:
    def __init__(self, store):
        self.store = store

    def add(self, obj):
        if isinstance(obj, AutonomousJob):
            self.store.jobs[obj.key] = obj
        elif isinstance(obj, AutonomousJobRun):
            self.store.runs.append(obj)

    async def delete(self, obj):
        self.store.jobs.pop(obj.key, None)
        self.store.runs = [r for r in self.store.runs if r.job_id != obj.id]

    async def flush(self):
        return None

    async def commit(self):
        return None

    async def rollback(self):
        return None


CREDENTIALS = {
    "reporter-key": lambda: _reporter(),
    "read-key": lambda: AuthUser(id="read-key", role=UserRole.VIEWER, permissions=["read"]),
    "operator-key": lambda: AuthUser(id="op-key", role=UserRole.OPERATOR, permissions=["write", "chat", "read"]),
    "admin-key": lambda: AuthUser(id="admin", role=UserRole.ADMIN, permissions=[]),
}


@pytest.fixture
def api(monkeypatch):
    store = _Store()
    clock = {"now": utc(2026, 10, 24, 15, 0)}

    async def _resolve_user(request, api_key, creds, session):
        make = CREDENTIALS.get(api_key or "")
        return make() if make else None

    async def _bind(user, session, requested_org_id=None):
        user.org_id = "org-a"

    async def _noop(*_args, **_kwargs):
        return None

    monkeypatch.setattr(middleware, "AUTH_BYPASS_ENABLED", False)
    monkeypatch.delenv("BRIGADE_ALLOWED_EMAILS", raising=False)
    monkeypatch.setattr(middleware, "_resolve_user", _resolve_user)
    monkeypatch.setattr(middleware, "_bind_org_context", _bind)
    monkeypatch.setattr(middleware, "_clear_org_context_safe", _noop)
    monkeypatch.setattr(routes, "ensure_org_context", _noop)
    monkeypatch.setattr(routes, "_utcnow", lambda: clock["now"])

    async def _find_job(session, key):
        return store.jobs.get(key)

    async def _get_agent(session, agent_id):
        return store.agents.get(agent_id) if agent_id else None

    async def _load_agents(session, ids):
        return {i: store.agents[i] for i in ids if i in store.agents}

    async def _load_brigade_runs(session, user):
        return list(store.scheduled_runs)

    async def _load_last_durations(session, ids):
        return {}

    async def _load_external_jobs(session):
        return list(store.jobs.values())

    def _newest_first(runs):
        return sorted(runs, key=lambda r: (r.started_at, r.created_at), reverse=True)

    async def _find_run(session, job_id, run_id):
        hits = [r for r in store.runs if r.job_id == job_id and r.run_id == run_id]
        return _newest_first(hits)[0] if hits else None

    async def _list_runs(session, job_id, limit):
        return _newest_first([r for r in store.runs if r.job_id == job_id])[:limit]

    async def _prune_runs(session, job_id, keep_id):
        mine = sorted((r for r in store.runs if r.job_id == job_id),
                      key=lambda r: (r.created_at, r.id), reverse=True)
        keep = {r.id for r in mine[: svc.MAX_RUNS_PER_JOB]} | {keep_id}
        store.runs = [r for r in store.runs if r.job_id != job_id or r.id in keep]

    for name, fn in {
        "_find_job": _find_job, "_get_agent": _get_agent, "_load_agents": _load_agents,
        "_load_brigade_runs": _load_brigade_runs, "_load_last_durations": _load_last_durations,
        "_load_external_jobs": _load_external_jobs, "_find_run": _find_run,
        "_list_runs": _list_runs, "_prune_runs": _prune_runs,
    }.items():
        monkeypatch.setattr(routes, name, fn)

    app = FastAPI()
    app.include_router(routes.router, prefix="/api/v1")

    @app.get("/api/v1/agents")
    async def _roster(user=Depends(require_api_key)):
        return {"ok": True}

    async def _session():
        yield _FakeSession(store)

    app.dependency_overrides[get_session] = _session
    client = TestClient(app)
    client.store = store
    client.clock = clock
    return client


JOB_BODY = {
    "name": "Build Log refresh",
    "agentId": "cpl-colophon",
    "responsibility": "Refreshes the Build Log three times a day.",
    "host": "build-server",
    "runner": "cron",
    "schedule": "0 6,14,22 * * *",
    "timezone": "UTC",
}


def _as(key):
    return {"X-API-Key": key}


def test_reporter_key_registers_and_reports_end_to_end(api):
    r = api.put("/api/v1/autonomy/jobs/build-log-refresh", json=JOB_BODY, headers=_as("reporter-key"))
    assert r.status_code == 200, r.text
    assert r.json()["created"] is True
    item = r.json()["item"]
    assert set(item) == CATALOGUE_ITEM_KEYS
    assert item["health"] == "never" and item["nextRunAt"] == "2026-10-24T22:00:00Z"
    assert item["agent"]["displayName"] == "Cpl. Colophon"

    r = api.post("/api/v1/autonomy/jobs/build-log-refresh/runs",
                 json={"status": "running", "runId": "2026-10-24T22"}, headers=_as("reporter-key"))
    assert r.status_code == 201, r.text
    assert r.json()["run"]["status"] == "running"

    api.clock["now"] = utc(2026, 10, 24, 15, 0, 42)
    r = api.post("/api/v1/autonomy/jobs/build-log-refresh/runs",
                 json={"status": "success", "runId": "2026-10-24T22", "summary": "3 new day stories"},
                 headers=_as("reporter-key"))
    assert r.status_code == 201, r.text
    body = r.json()
    assert set(body["run"]) == RUN_KEYS
    assert body["run"]["durationMs"] == 42000 and body["run"]["finishedAt"] == "2026-10-24T15:00:42Z"
    assert body["item"]["lastStatus"] == "success" and body["item"]["health"] == "ok"
    assert len(api.store.runs) == 1  # one row: opened, then closed

    r = api.get("/api/v1/autonomy/jobs/build-log-refresh/runs", headers=_as("operator-key"))
    assert r.status_code == 200 and [x["status"] for x in r.json()["runs"]] == ["success"]


def test_re_registration_keeps_a_humans_pause(api):
    api.put("/api/v1/autonomy/jobs/build-log-refresh", json=JOB_BODY, headers=_as("reporter-key"))
    paused = dict(JOB_BODY, enabled=False, owner="Ops team")
    assert api.put("/api/v1/autonomy/jobs/build-log-refresh", json=paused,
                   headers=_as("operator-key")).json()["item"]["health"] == "paused"
    r = api.put("/api/v1/autonomy/jobs/build-log-refresh", json=JOB_BODY, headers=_as("reporter-key"))
    assert r.json()["created"] is False
    assert r.json()["item"]["enabled"] is False and r.json()["item"]["owner"] == "Ops team"


def test_report_for_an_unknown_job_is_a_404_naming_the_fix(api):
    r = api.post("/api/v1/autonomy/jobs/no-such-job/runs", json={"status": "success"},
                 headers=_as("reporter-key"))
    assert r.status_code == 404
    assert r.json()["detail"] == (
        "No job 'no-such-job'. Register it with PUT /api/v1/autonomy/jobs/no-such-job first."
    )


@pytest.mark.parametrize("method,path", [
    ("GET", "/api/v1/autonomy"),
    ("DELETE", "/api/v1/autonomy/jobs/build-log-refresh"),
    ("GET", "/api/v1/autonomy/jobs/build-log-refresh/runs"),
    ("GET", "/api/v1/agents"),
])
def test_a_reporter_key_can_do_nothing_else(api, method, path):
    r = api.request(method, path, headers=_as("reporter-key"))
    assert r.status_code == 403
    assert r.json()["detail"] == REPORTER_KEY_CONFINED_DETAIL


def test_a_plain_viewer_key_cannot_report(api):
    r = api.put("/api/v1/autonomy/jobs/build-log-refresh", json=JOB_BODY, headers=_as("read-key"))
    assert r.status_code == 403
    assert api.get("/api/v1/agents", headers=_as("read-key")).status_code == 200


def test_unauthenticated_requests_are_refused(api):
    assert api.get("/api/v1/autonomy").status_code == 401
    assert api.put("/api/v1/autonomy/jobs/build-log-refresh", json=JOB_BODY).status_code == 401


def test_operator_reads_the_catalogue_and_deletes_a_job(api):
    api.put("/api/v1/autonomy/jobs/build-log-refresh", json=JOB_BODY, headers=_as("reporter-key"))
    r = api.get("/api/v1/autonomy", headers=_as("operator-key"))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["generatedAt"] == "2026-10-24T15:00:00Z"
    assert [i["id"] for i in body["items"]] == [
        "external:build-log-refresh", "brigade:ca78fd8b-e894-4d6b-a157-8c757ec3d47e",
    ]  # never before ok
    assert body["counts"] == {"total": 2, "brigade": 1, "external": 1, "failing": 0,
                              "stale": 0, "paused": 0, "never": 1}
    r = api.delete("/api/v1/autonomy/jobs/build-log-refresh", headers=_as("operator-key"))
    assert r.status_code == 204 and r.content == b""
    assert api.delete("/api/v1/autonomy/jobs/build-log-refresh",
                      headers=_as("operator-key")).status_code == 404


def test_put_with_a_secret_in_the_command_is_refused_without_echoing_it(api):
    body = dict(JOB_BODY, command="refresh.sh --token=hunter2-super-secret")
    r = api.put("/api/v1/autonomy/jobs/build-log-refresh", json=body, headers=_as("reporter-key"))
    assert r.status_code == 422
    assert r.json()["detail"] == "Don't store secrets in the command; reference them by name."
    assert "hunter2" not in r.text
    assert api.store.jobs == {}


@pytest.mark.parametrize("key", ["Build_Log", "ab", "-x-"])
def test_put_with_a_bad_key_is_a_422(api, key):
    r = api.put(f"/api/v1/autonomy/jobs/{key}", json=JOB_BODY, headers=_as("reporter-key"))
    assert r.status_code == 422 and r.json()["detail"] == svc.KEY_RULE


def test_put_with_notes_and_a_dotted_agent_id(api):
    body = dict(JOB_BODY, agentId="cpl.-colophon", notes=AUDIT_NOTE)
    r = api.put("/api/v1/autonomy/jobs/build-log-refresh", json=body, headers=_as("reporter-key"))
    assert r.status_code == 200, r.text
    assert r.json()["item"]["notes"] == AUDIT_NOTE
    assert r.json()["item"]["agentId"] == "cpl.-colophon" and r.json()["item"]["agent"]["id"] == "cpl.-colophon"
    # The script re-registers without notes: the audit's notes stay.
    r = api.put("/api/v1/autonomy/jobs/build-log-refresh", json=JOB_BODY, headers=_as("reporter-key"))
    assert r.json()["item"]["notes"] == AUDIT_NOTE
    listed = api.get("/api/v1/autonomy", headers=_as("operator-key")).json()["items"]
    assert {i["id"]: i["notes"] for i in listed} == {
        "external:build-log-refresh": AUDIT_NOTE,
        "brigade:ca78fd8b-e894-4d6b-a157-8c757ec3d47e": None,
    }


def test_put_with_a_secret_in_the_notes_is_refused_without_echoing_it(api):
    body = dict(JOB_BODY, notes="rotated the key; new api_key=hunter2-super-secret")
    r = api.put("/api/v1/autonomy/jobs/build-log-refresh", json=body, headers=_as("reporter-key"))
    assert r.status_code == 422
    assert r.json()["detail"] == "Don't store secrets in the notes; reference them by name."
    assert "hunter2" not in r.text


def test_put_with_an_unknown_agent_is_a_422(api):
    r = api.put("/api/v1/autonomy/jobs/build-log-refresh", json=dict(JOB_BODY, agentId="ghost"),
                headers=_as("reporter-key"))
    assert r.status_code == 422 and "ghost" in r.json()["detail"]


def test_put_with_a_bad_cron_is_a_422(api):
    r = api.put("/api/v1/autonomy/jobs/build-log-refresh", json=dict(JOB_BODY, schedule="0 25 * * *"),
                headers=_as("reporter-key"))
    assert r.status_code == 422


def test_runs_are_pruned_to_two_hundred_per_job(api):
    api.put("/api/v1/autonomy/jobs/build-log-refresh", json=JOB_BODY, headers=_as("reporter-key"))
    for i in range(svc.MAX_RUNS_PER_JOB + 5):
        api.clock["now"] = utc(2026, 10, 24, 15) + timedelta(minutes=i)
        assert api.post("/api/v1/autonomy/jobs/build-log-refresh/runs", json={"status": "success"},
                        headers=_as("reporter-key")).status_code == 201
    assert len(api.store.runs) == svc.MAX_RUNS_PER_JOB
    r = api.get("/api/v1/autonomy/jobs/build-log-refresh/runs?limit=100", headers=_as("operator-key"))
    assert len(r.json()["runs"]) == 100
    assert api.get("/api/v1/autonomy/jobs/build-log-refresh/runs?limit=101",
                   headers=_as("operator-key")).status_code == 422
