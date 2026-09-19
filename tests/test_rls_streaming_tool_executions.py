"""Regression tests for the streaming tool-execution audit-log RLS rejection.

WHAT BREAKS (2026-07-17 .. fixed here): every streaming agent chat that used
tools logged

    Failed to log tool executions: (sqlalchemy.dialects.postgresql.asyncpg
    .ProgrammingError) InsufficientPrivilegeError: new row violates
    row-level security policy for table "tool_executions"

while the chat itself returned 200 — the audit rows were silently dropped.

WHY (root cause, verified against the pinned fastapi==0.115.0):
``tool_executions`` is FORCE-RLS with
``WITH CHECK (org_id = current_org_id() AND ...)`` and
``org_id NOT NULL DEFAULT current_org_id()`` (app/db/migrations.py,
20260626_01). ``ToolExecutionRepository.create`` re-asserts the org GUC via
``ensure_org_context``, which reads the request-scoped ``current_org_id_var``.
But FastAPI >= 0.106 exits yield-dependencies BEFORE the response body is
streamed: ``get_session``'s teardown (``_clear_org_context``) has already
cleared the connection GUC AND positively nulled ``current_org_id_var`` by the
time the ``StreamingResponse`` generator body runs. ``ensure_org_context``
then fails safe to a no-op, the INSERT lands with ``org_id = NULL`` and RLS
rejects it (``NULL = NULL`` is not true). The non-streaming branch is
unaffected — its tool log runs inside the endpoint body, where the var is
still bound.

WHY THESE TESTS LOOK LIKE THIS:

  * ``test_streaming_tool_log_runs_with_org_bound`` is the hermetic
    reproduction. It drives the REAL ``_stream_chat`` generator with the REAL
    ``ToolExecutionRepository`` against a fake session that emulates the
    session-level ``app.current_org_id`` GUC and the FORCE-RLS WITH CHECK at
    INSERT time — the exact rejection, no Postgres required. It starts from
    the post-teardown state the dependency exit leaves behind (var = None),
    exactly like production. Pre-fix it fails with zero rows written (the
    fake raises the RLS error and the route swallows it into a warning);
    post-fix the row lands with the request's org.

  * ``test_streaming_tool_executions_persist_against_real_rls`` is the
    end-to-end proof against a real Postgres with the real policy. It skips
    cleanly when no Postgres is reachable (same guard as
    test_rls_message_persistence.py). Run it with:

        DATABASE_URL=postgresql+asyncpg://<app_role>:<pw>@<host>:<port>/<db> \
        MIGRATION_DATABASE_URL=postgresql+asyncpg://<owner>:<pw>@<host>:<port>/<db> \
        pytest tests/test_rls_streaming_tool_executions.py -v

    where ``DATABASE_URL`` is the RLS-SUBJECT app role (NOBYPASSRLS,
    NOSUPERUSER, IN ROLE brigade_app) and ``MIGRATION_DATABASE_URL`` the
    owner, against a database already migrated by app.db.migrations.

  * The source canary always runs, so a DB-less CI still catches the guard
    being removed from the streaming path.
"""

import os
import uuid
from dataclasses import dataclass
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api import agent_routes

APP_DSN = os.getenv("DATABASE_URL", "")          # RLS-SUBJECT app role
ADMIN_DSN = os.getenv("MIGRATION_DATABASE_URL", APP_DSN)  # owner, for fixture DDL/DML

needs_postgres = pytest.mark.skipif(
    not APP_DSN.startswith("postgresql"),
    reason="needs a real Postgres with the tool_executions RLS policy applied "
           "(DATABASE_URL); the hermetic test above covers the same rejection",
)


def _org_var():
    from app.orchestration.event_bus import current_org_id_var
    return current_org_id_var


# ─────────────────────────────────────────────────────────────────────────────
# Hermetic reproduction: real _stream_chat + real ToolExecutionRepository +
# real ensure_org_context, against a fake session that emulates the Postgres
# GUC and the FORCE-RLS WITH CHECK at INSERT time.
# ─────────────────────────────────────────────────────────────────────────────

class RLSViolation(Exception):
    """Mirrors asyncpg.exceptions.InsufficientPrivilegeError's message."""


@dataclass
class FakeTool:
    name: str
    description: str = ""
    parameters: dict[str, Any] | None = None


@dataclass
class FakeToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class FakeToolResult:
    tool_call_id: str
    name: str
    result: Any
    error: str | None = None


class FakeRLSSession:
    """Emulates the narrow AsyncSession surface ToolExecutionRepository uses,
    with a session-level ``app.current_org_id`` GUC and the FORCE-RLS
    ``WITH CHECK (org_id = current_org_id() AND (conversation_id IS NULL OR
    ...))`` evaluated at flush (INSERT) time.

    One connection, GUC semantics faithful to Postgres: ``set_config(...,
    false)`` sticks, ``current_setting(..., true)`` returns NULL ('') when
    unbound, and an INSERT whose org_id default resolves to NULL violates the
    policy (``NULL = NULL`` is not true) — the exact production rejection.
    """

    def __init__(self):
        self.guc = ""            # '' == unbound (nullif(...,'') → NULL)
        self.rows = []           # rows that passed WITH CHECK
        self._pending = None
        self._last = None
        self.insert_attempts = 0

    async def execute(self, stmt, params=None, *_a, **_kw):
        s = str(stmt)
        outer = self

        class _R:
            @staticmethod
            def scalar():
                return outer.guc or None

            @staticmethod
            def scalar_one_or_none():
                return outer._last

        if "current_setting" in s:
            return _R()
        if "set_config" in s:
            outer.guc = (params or {}).get("org_id", "")
            return _R()
        # ToolExecutionRepository.complete's select-by-id.
        return _R()

    def add(self, obj):
        self._pending = obj

    async def flush(self):
        if self._pending is None:
            return
        self.insert_attempts += 1
        org = self.guc or None
        if org is None:
            # org_id DEFAULT current_org_id() → NULL → WITH CHECK NULL=NULL →
            # policy violation, exactly like the real policy.
            raise RLSViolation(
                'new row violates row-level security policy for table "tool_executions"'
            )
        if self._pending.id is None:
            self._pending.id = uuid.uuid4()
        if getattr(self._pending, "org_id", None) is None:
            self._pending.org_id = org
        if self._pending not in self.rows:
            self.rows.append(self._pending)
        self._last = self._pending
        self._pending = None

    async def commit(self):
        pass

    async def rollback(self):
        self._pending = None

    async def invalidate(self):
        pass


class FakeToolLoopClient:
    """Minimal stand-in for OpsCenterLLMClient on the tools branch of
    _stream_chat: drives the real on_tool_call / on_tool_result callbacks."""

    async def execute_tool_loop(self, *, on_tool_call, on_tool_result, **_kw):
        call = FakeToolCall(id="call-1", name="fake_tool", arguments={"q": "x"})
        on_tool_call(call)
        on_tool_result(FakeToolResult(tool_call_id="call-1", name="fake_tool",
                                      result={"ok": True}, error=None))
        return {"model": "fake-model", "provider": "fake", "usage": {}}

    def get_response_content(self, response):
        return "done"


async def _noop(*_a, **_kw):
    return None


@pytest.mark.asyncio
async def test_streaming_tool_log_runs_with_org_bound(monkeypatch):
    """THE hermetic regression test.

    Reproduces the production precondition exactly: the StreamingResponse
    generator body runs AFTER the dependency teardown, i.e. with
    ``current_org_id_var`` positively nulled. Pre-fix the tool_executions
    INSERT is rejected by the emulated FORCE-RLS WITH CHECK and zero rows are
    written (the route swallows the error into a warning and the stream still
    completes — the silent audit loss). Post-fix the streaming path re-binds
    the request's org around the writes and the row lands with the right org.
    """
    org_id = str(uuid.uuid4())
    monkeypatch.setattr(agent_routes, "llm_client", FakeToolLoopClient())
    monkeypatch.setattr(agent_routes, "emit_agent_started", _noop)
    monkeypatch.setattr(agent_routes, "emit_agent_completed", _noop)
    monkeypatch.setattr(agent_routes, "_meter_chat_to_lago", _noop)

    # The state the get_session teardown leaves behind for the generator body.
    token = _org_var().set(None)
    session = FakeRLSSession()
    try:
        frames = [
            frame
            async for frame in agent_routes._stream_chat(
                messages=[{"role": "user", "content": "use a tool"}],
                model="fake-model",
                temperature=0.2,
                max_tokens=64,
                agent={"id": "dr-glitter-mane", "name": "dr-glitter-mane"},
                user_id="user-1",
                agent_tools=[FakeTool(name="fake_tool")],
                session=session,
                user_email="user@example.com",
                org_id=org_id,
            )
        ]
    finally:
        _org_var().reset(token)

    assert not any('"type": "error"' in f for f in frames)
    assert session.insert_attempts == 1, (
        "the streaming tool log never attempted the tool_executions INSERT"
    )
    assert len(session.rows) == 1, (
        "tool_executions audit row was REJECTED by the emulated FORCE-RLS WITH "
        "CHECK — this is the production bug: the streaming generator runs after "
        "get_session's teardown nulled current_org_id_var, so ensure_org_context "
        "no-ops and the INSERT lands with a NULL org_id"
    )
    assert str(session.rows[0].org_id) == org_id
    assert session.rows[0].status == "completed"


@pytest.mark.asyncio
async def test_streaming_org_context_clears_after_writes(monkeypatch):
    """B1 posture: the re-bound org must NOT outlive the block.

    ``streaming_org_context`` must positively clear the GUC (and the context
    var) on exit so no connection returns to the pool carrying this request's
    org — the same guarantee ``get_session``'s teardown gives ordinary
    requests. A leak here re-opens the cross-tenant B1 finding.
    """
    from app.db.database import streaming_org_context

    org_id = str(uuid.uuid4())
    session = FakeRLSSession()
    token = _org_var().set(None)
    try:
        async with streaming_org_context(session, org_id):
            assert _org_var().get() == org_id
            assert session.guc == ""  # binding the var does not touch the GUC
            await session.execute(text("SELECT 1"))  # no-op; keeps shape honest
        assert _org_var().get() is None, "org var outlived the streaming block"
        assert session.guc == "", "org GUC outlived the streaming block"
    finally:
        _org_var().reset(token)


@pytest.mark.asyncio
async def test_streaming_org_context_without_org_cannot_invent_one():
    """Fail-safe direction: an unbound caller (no org) must see a pure no-op —
    the write stays correctly refused by RLS rather than being attributed to a
    guessed org. Mirrors test_no_org_bound_is_a_no_op_and_cannot_invent_an_org."""
    from app.db.database import streaming_org_context

    session = FakeRLSSession()
    token = _org_var().set(None)
    try:
        async with streaming_org_context(session, None):
            assert _org_var().get() is None
        assert session.guc == ""
    finally:
        _org_var().reset(token)


def test_streaming_tool_log_still_wraps_the_rls_guard():
    """Canary against silent removal (same doctrine as
    test_every_forced_rls_write_method_still_calls_the_guard): if the streaming
    tool log stops re-binding the org, the audit rows start silently vanishing
    again — say so in CI even without a database."""
    import inspect

    src = inspect.getsource(agent_routes._stream_chat)
    guard_at = src.find("streaming_org_context")
    log_at = src.find("Failed to log tool executions")
    assert guard_at != -1, (
        "_stream_chat no longer re-binds the org around the tool_executions "
        "writes — streaming chats will silently drop their audit rows to the "
        "FORCE-RLS policy (FastAPI >=0.106 runs the generator after the "
        "get_session teardown has cleared the org context)"
    )
    assert log_at != -1 and guard_at < log_at, (
        "the org re-bind must wrap the tool-execution logging block"
    )


# ─────────────────────────────────────────────────────────────────────────────
# End-to-end proof against the real FORCE-RLS policy (skips without Postgres).
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
async def admin_engine():
    eng = create_async_engine(ADMIN_DSN, pool_size=2, max_overflow=0)
    yield eng
    await eng.dispose()


@pytest.fixture
async def test_org(admin_engine):
    org_id = str(uuid.uuid4())
    slug = f"rlsstream-{org_id[:8]}"
    async with admin_engine.begin() as c:
        await c.execute(
            text("INSERT INTO organizations (id, name, slug, plan_tier, api_calls_limit) "
                 "VALUES (:i, :n, :s, 'free', 0)"),
            {"i": org_id, "n": "RLS streaming test org", "s": slug},
        )
    yield org_id
    async with admin_engine.begin() as c:
        await c.execute(text("DELETE FROM organizations WHERE id = :i"), {"i": org_id})


@pytest.fixture
async def test_agent(admin_engine, test_org):
    agent_id = f"rlsstream-agent-{test_org[:8]}"
    async with admin_engine.begin() as c:
        await c.execute(
            text("INSERT INTO agents (id, name, display_name, model, status, "
                 "billing_tier, rate_multiplier, org_id) "
                 "VALUES (:i, :i, 'RLS Streaming Test Agent', 'uc/chat-local-p40', "
                 "'inactive', 'standard', 1.0, :o)"),
            {"i": agent_id, "o": test_org},
        )
    return agent_id


@needs_postgres
@pytest.mark.asyncio
async def test_streaming_tool_executions_persist_against_real_rls(
    monkeypatch, test_org, test_agent, admin_engine
):
    """The real-policy proof. Drives the real _stream_chat generator on a real
    app-role session, starting from the post-teardown state (org var nulled,
    GUC blanked) that FastAPI's dependency exit produces.

    Pre-fix: the INSERT is rejected by tool_executions_org_isolation
    (InsufficientPrivilegeError swallowed into a warning) and the count stays
    zero. Post-fix: exactly one row, attributed to the request's org.
    """
    from app.db.database import _clear_org_context

    monkeypatch.setattr(agent_routes, "llm_client", FakeToolLoopClient())
    monkeypatch.setattr(agent_routes, "emit_agent_started", _noop)
    monkeypatch.setattr(agent_routes, "emit_agent_completed", _noop)
    monkeypatch.setattr(agent_routes, "_meter_chat_to_lago", _noop)

    eng = create_async_engine(APP_DSN, pool_size=2, max_overflow=0)
    maker = async_sessionmaker(eng, expire_on_commit=False)
    try:
        async with maker() as session:
            # What _bind_org_context did for this request...
            await session.execute(
                text("SELECT set_config('app.current_org_id', :o, false)"),
                {"o": test_org},
            )
            await session.commit()
            token = _org_var().set(test_org)
            # ...and what get_session's teardown then UNDID before the
            # StreamingResponse generator body runs (var nulled + GUC blanked).
            await _clear_org_context(session)
            assert _org_var().get() is None

            try:
                frames = [
                    frame
                    async for frame in agent_routes._stream_chat(
                        messages=[{"role": "user", "content": "use a tool"}],
                        model="uc/chat-local-p40",
                        temperature=0.2,
                        max_tokens=64,
                        agent={"id": test_agent, "name": test_agent},
                        user_id="rls-stream-test",
                        agent_tools=[FakeTool(name="fake_tool")],
                        session=session,
                        user_email="user@example.com",
                        org_id=test_org,
                    )
                ]
            finally:
                _org_var().reset(token)

        assert not any('"type": "error"' in f for f in frames)

        # Row counts, not status codes — the broken version completed the
        # stream and logged only a warning. Read on the owner (RLS-exempt)
        # engine with an explicit org filter.
        async with admin_engine.connect() as c:
            count = (await c.execute(
                text("SELECT count(*) FROM tool_executions "
                     "WHERE org_id = :o AND agent_id = :a"),
                {"o": test_org, "a": test_agent},
            )).scalar()
        assert count == 1, (
            f"tool_executions audit row missing (count={count}) — the streaming "
            "tool log ran with no org bound and the FORCE-RLS policy rejected "
            "the INSERT (the production bug)"
        )
    finally:
        await eng.dispose()
