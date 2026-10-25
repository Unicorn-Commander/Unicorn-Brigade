"""Regression: PUT/POST /scheduled-runs refreshed the row after commit on a pooled
connection that had lost the request's org GUC, and FORCE RLS hid it
("Could not refresh instance", HTTP 500). Seen live on dogfood 2026-10-24 when six
descriptions were written concurrently: 5 of 6 returned 500 although the commit
had landed. The handlers must re-assert the org context between commit and refresh.
"""
import asyncio
from types import SimpleNamespace

import app.api.scheduled_run_routes as routes
from app.auth.roles import UserRole
from app.db.models import ScheduledRun


class _RecordingSession:
    def __init__(self, calls, run=None):
        self.calls = calls
        self._run = run

    async def get(self, model, key):
        self.calls.append("get")
        return self._run

    def add(self, obj):
        self.calls.append("add")
        self._run = obj

    async def commit(self):
        self.calls.append("commit")

    async def refresh(self, obj):
        self.calls.append("refresh")

    async def execute(self, *args, **kwargs):  # pragma: no cover - not reached
        self.calls.append("execute")


def _admin():
    return SimpleNamespace(role=UserRole.ADMIN, id="u1", user_id="u1", permissions=["admin"])


def _patch(monkeypatch, calls):
    async def fake_ensure(session):
        calls.append("ensure_org_context")

    async def fake_agent_exists(session, agent_id):
        calls.append("agent_exists")

    monkeypatch.setattr(routes, "ensure_org_context", fake_ensure)
    monkeypatch.setattr(routes, "_ensure_agent_exists", fake_agent_exists)
    monkeypatch.setattr(routes, "get_scheduler", lambda: None)


def _existing_run():
    return ScheduledRun(
        id="11111111-1111-1111-1111-111111111111",
        name="deadlines-sentinel",
        agent_id="deadline-sentinel",
        prompt="scan deadlines",
        cron="17 14 * * *",
        timezone="UTC",
        enabled=True,
        max_runtime_seconds=300,
    )


def test_update_reasserts_org_context_between_commit_and_refresh(monkeypatch):
    calls = []
    _patch(monkeypatch, calls)
    session = _RecordingSession(calls, run=_existing_run())
    body = routes.ScheduledRunUpdate(description="Scans Project-Ops deadlines every afternoon.")
    out = asyncio.run(routes.update_scheduled_run("11111111-1111-1111-1111-111111111111", body, session=session, user=_admin()))
    assert calls.index("commit") < calls.index("ensure_org_context") < calls.index("refresh")
    assert out["description"] == "Scans Project-Ops deadlines every afternoon."


def test_create_reasserts_org_context_between_commit_and_refresh(monkeypatch):
    calls = []
    _patch(monkeypatch, calls)
    session = _RecordingSession(calls)
    body = routes.ScheduledRunCreate(
        name="nightly", agentId="deadline-sentinel", prompt="do it", cron="0 2 * * *",
        description="Runs the nightly check.",
    )
    asyncio.run(routes.create_scheduled_run(body, session=session, user=_admin()))
    assert calls.index("commit") < calls.index("ensure_org_context") < calls.index("refresh")
