"""Regression tests for the org-RLS / connection-pool message-loss bug.

WHAT BROKE (2026-07-17 .. 2026-08-11): ``app.current_org_id`` is a *connection*
level Postgres setting, but a request is not pinned to one connection. Every
``session.commit()`` inside a repository method releases the connection back to
the pool, and the next statement checks out a DIFFERENT one — which never
received this request's ``set_config``, or which another request's
``_clear_org_context`` teardown has just blanked. The write then lands with a
NULL ``org_id`` and Postgres rejects it as "new row violates row-level security
policy". The failure was swallowed into a ``logger.warning`` while the API still
returned 200, so it dropped 751 assistant chat messages before anyone noticed.

WHY THESE TESTS LOOK LIKE THIS — read before "simplifying" them:

  * They need a REAL Postgres. The bug lives in the interaction between a
    session-scoped GUC, FORCE row-level security, and a connection pool. No
    amount of mocking reproduces it; the pre-existing hermetic suite covered
    this code and saw nothing.

  * They must break the one-connection assumption. The FIRST attempt to
    reproduce this by hand PASSED, because an idle pool hands the same physical
    connection back every time and the GUC is still sitting on it. A
    single-threaded happy-path test cannot see this bug at all. So one test
    deterministically blanks every pooled connection between the writes, and one
    runs concurrent requests against a deliberately small pool.

  * They assert ROW COUNTS, not status codes. The broken version returned 200
    and reported success while writing nothing. "It returned 200" is exactly the
    assertion that let this ship.

Isolation: every test runs under its own throwaway organization. RLS itself keeps these rows invisible to the rest of the database, and
the org is deleted at teardown (``organizations`` cascades to agents,
conversations and messages), so no production row is touched.

Skips cleanly when no database is reachable.
"""

import asyncio
import os
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.repositories import ConversationRepository

APP_DSN = os.getenv("DATABASE_URL", "")          # RLS-SUBJECT app role
ADMIN_DSN = os.getenv("MIGRATION_DATABASE_URL", APP_DSN)  # owner, for fixture DDL/DML

pytestmark = pytest.mark.skipif(
    not APP_DSN.startswith("postgresql"),
    reason="needs a real Postgres (DATABASE_URL); the bug is a pool+RLS interaction "
           "that cannot be reproduced with mocks",
)

# Small on purpose: a big pool makes connection reuse rarer and the concurrency
# test flakier. With 3 connections and 8 concurrent requests, checkouts churn.
POOL_SIZE = 3
CONCURRENCY = 8


def _org_var():
    from app.orchestration.event_bus import current_org_id_var
    return current_org_id_var


@pytest.fixture
async def admin_engine():
    eng = create_async_engine(ADMIN_DSN, pool_size=2, max_overflow=0)
    yield eng
    await eng.dispose()


@pytest.fixture
async def test_org(admin_engine):
    """A throwaway organization. Deleting it cascades every row these tests wrote."""
    org_id = str(uuid.uuid4())
    slug = f"rlstest-{org_id[:8]}"
    async with admin_engine.begin() as c:
        await c.execute(
            text("INSERT INTO organizations (id, name, slug, plan_tier, api_calls_limit) "
                 "VALUES (:i, :n, :s, 'free', 0)"),
            {"i": org_id, "n": "RLS regression test org", "s": slug},
        )
    yield org_id
    async with admin_engine.begin() as c:
        await c.execute(text("DELETE FROM organizations WHERE id = :i"), {"i": org_id})


@pytest.fixture
async def test_agent(admin_engine, test_org):
    agent_id = f"rlstest-agent-{test_org[:8]}"
    async with admin_engine.begin() as c:
        await c.execute(
            text("INSERT INTO agents (id, name, display_name, model, status, "
                 "billing_tier, rate_multiplier, org_id) "
                 "VALUES (:i, :i, 'RLS Test Agent', 'uc/chat-local-p40', 'inactive', "
                 "'standard', 1.0, :o)"),
            {"i": agent_id, "o": test_org},
        )
    return agent_id


@pytest.fixture
async def app_sessionmaker(test_org):
    """Sessions on the RLS-SUBJECT role with a deliberately small pool."""
    eng = create_async_engine(APP_DSN, pool_size=POOL_SIZE, max_overflow=0)
    maker = async_sessionmaker(eng, expire_on_commit=False)
    token = _org_var().set(test_org)
    try:
        yield maker
    finally:
        _org_var().reset(token)
        await eng.dispose()


async def _bind_org(session, org_id):
    """What auth/middleware._bind_org_context does to the connection it holds."""
    await session.execute(
        text("SELECT set_config('app.current_org_id', :o, false)"), {"o": org_id}
    )


async def _blank_every_pooled_connection(maker):
    """Deterministically recreate the production condition.

    Hold all POOL_SIZE connections at once and blank the org GUC on each, exactly
    as ``database._clear_org_context`` does when another request tears down. When
    these are released, EVERY connection in the pool carries an empty org — so
    the next checkout is guaranteed to get one, instead of us hoping the race
    lands the right way.
    """
    sessions = [maker() for _ in range(POOL_SIZE)]
    try:
        for s in sessions:
            await s.execute(text("SELECT set_config('app.current_org_id', '', false)"))
        for s in sessions:
            await s.commit()   # commit makes the blank stick at session level
    finally:
        for s in sessions:
            await s.close()


async def _count_messages(maker, conv_id):
    """Row counts by role. Read with the GUC bound so RLS lets us see our own rows."""
    async with maker() as s:
        await _bind_org(s, _org_var().get())
        rows = (await s.execute(
            text("SELECT role, count(*) FROM messages WHERE conversation_id = :c "
                 "GROUP BY role"),
            {"c": conv_id},
        )).all()
    return {r[0]: r[1] for r in rows}


@pytest.mark.asyncio
async def test_messages_persist_when_the_pooled_connection_lost_its_org(
    app_sessionmaker, test_agent, test_org
):
    """THE regression test. Deterministic, no race.

    Pre-fix this fails with zero assistant rows: the conversation INSERT lands on
    the connection that still holds the org, then the commit releases it, and the
    message INSERT lands on a blanked connection and is rejected by RLS.
    """
    maker = app_sessionmaker
    async with maker() as s:
        await _bind_org(s, test_org)
        repo = ConversationRepository(s)

        conv = await repo.create({
            "agent_id": test_agent, "user_id": "rls-regression",
            "title": "pool regression", "model": "uc/chat-local-p40",
        })
        conv_id = str(conv["id"])

        # create() committed, so our connection went back to the pool. Poison the
        # whole pool the way a concurrent request's teardown does.
        await _blank_every_pooled_connection(maker)

        await repo.add_message(conv_id, {"role": "user", "content": "does this survive"})
        await repo.add_message(conv_id, {
            "role": "assistant", "content": "it must",
            "model": "uc/chat-local-p40", "tokens_used": 7,
        })

    counts = await _count_messages(maker, conv_id)
    assert counts.get("user") == 1, (
        f"user message did not persist (counts={counts}) — the write was silently "
        f"rejected by RLS on a connection with no org bound"
    )
    assert counts.get("assistant") == 1, (
        f"assistant message did not persist (counts={counts}) — this is the exact "
        f"shape of the 2026-07-17..08-11 data loss: user half saved, reply dropped"
    )


@pytest.mark.asyncio
async def test_messages_persist_under_concurrent_requests_sharing_a_pool(
    app_sessionmaker, test_agent, test_org
):
    """The property a single-threaded test cannot check.

    CONCURRENCY requests contend for POOL_SIZE connections while teardown tasks
    blank connections underneath them — so a request's statements genuinely land
    on different physical connections. Asserts exact totals, not "no exception".
    """
    maker = app_sessionmaker
    conv_ids = []
    lock = asyncio.Lock()

    async def one_request(n):
        async with maker() as s:
            await _bind_org(s, test_org)
            repo = ConversationRepository(s)
            conv = await repo.create({
                "agent_id": test_agent, "user_id": f"rls-conc-{n}",
                "title": f"concurrent {n}", "model": "uc/chat-local-p40",
            })
            cid = str(conv["id"])
            await repo.add_message(cid, {"role": "user", "content": f"q{n}"})
            await asyncio.sleep(0)  # yield: let another task take our connection
            await repo.add_message(cid, {
                "role": "assistant", "content": f"a{n}",
                "model": "uc/chat-local-p40", "tokens_used": 3,
            })
            async with lock:
                conv_ids.append(cid)

    async def teardown_noise():
        for _ in range(4):
            await _blank_every_pooled_connection(maker)
            await asyncio.sleep(0)

    await asyncio.gather(
        *(one_request(i) for i in range(CONCURRENCY)),
        teardown_noise(),
    )

    assert len(conv_ids) == CONCURRENCY
    async with maker() as s:
        await _bind_org(s, test_org)
        rows = (await s.execute(
            text("SELECT role, count(*) FROM messages WHERE conversation_id = ANY(:ids) "
                 "GROUP BY role"),
            {"ids": [uuid.UUID(c) for c in conv_ids]},
        )).all()
    counts = {r[0]: r[1] for r in rows}
    assert counts.get("user") == CONCURRENCY, f"lost user messages: {counts}"
    assert counts.get("assistant") == CONCURRENCY, (
        f"lost assistant messages: {counts} — expected {CONCURRENCY} of each; "
        f"a shortfall here is the pool/RLS regression"
    )


@pytest.mark.asyncio
async def test_org_context_lost_raises_instead_of_silently_no_opping():
    """The loud half of the fix.

    If the org context genuinely cannot be restored, ``ensure_org_context`` must
    RAISE, so the caller reports a persistence failure. Returning quietly would
    hand the write straight to RLS to reject and swallow — the original bug.
    """
    from app.db.database import OrgContextLost, ensure_org_context

    token = _org_var().set("11111111-1111-1111-1111-111111111111")

    class StuckSession:
        """set_config never takes effect — e.g. a connection reset mid-request."""
        async def execute(self, *_a, **_kw):
            class R:
                @staticmethod
                def scalar():
                    return None
            return R()

    try:
        with pytest.raises(OrgContextLost):
            await ensure_org_context(StuckSession())
    finally:
        _org_var().reset(token)


@pytest.mark.asyncio
async def test_no_org_bound_is_a_no_op_and_cannot_invent_an_org():
    """Fail-safe direction: with no org bound the guard must do NOTHING.

    If it ever wrote a value here it would re-open the B1 cross-tenant leak that
    ``_clear_org_context`` exists to close.
    """
    from app.db.database import ensure_org_context

    token = _org_var().set(None)
    statements = []

    class RecordingSession:
        async def execute(self, stmt, *_a, **_kw):
            statements.append(str(stmt))
            class R:
                @staticmethod
                def scalar():
                    return None
            return R()

    try:
        await ensure_org_context(RecordingSession())
    finally:
        _org_var().reset(token)
    assert statements == [], f"guard touched the connection with no org bound: {statements}"


def test_every_forced_rls_write_method_still_calls_the_guard():
    """Canary against silent removal.

    The guard is only effective if it is actually invoked. If someone deletes an
    ``ensure_org_context`` call from one of these write paths, that table starts
    silently dropping rows again — name it here so the suite says so.
    """
    import inspect
    from app.db import repositories as R

    required = {
        "AgentRepository": ["create", "update", "delete"],
        "ConversationRepository": ["create", "update", "delete", "add_message"],
        "BuilderSessionRepository": ["get_or_create", "add_messages", "set_agent_config"],
        "ToolExecutionRepository": ["create", "complete"],
        "CodeAttributionRepository": ["create"],
        "SpeakerProfileRepository": ["create", "update", "delete"],
    }
    missing = []
    for cls_name, methods in required.items():
        cls = getattr(R, cls_name)
        for m in methods:
            src = inspect.getsource(getattr(cls, m))
            if "ensure_org_context" not in src:
                missing.append(f"{cls_name}.{m}")
    assert not missing, (
        "these FORCE-RLS write paths no longer re-assert the org context and will "
        f"silently drop rows on a recycled connection: {missing}"
    )


def test_persist_failure_is_loud_and_surfaced_on_the_response():
    """The persist handler must not swallow a failure into a 200.

    Structural check on the real route: the original bug was a ``logger.warning``
    plus an unchanged 200 body. Verified behaviourally in production by revoking
    INSERT on ``messages`` (the response came back ``persisted: false`` with an
    ERROR log); this guards the contract in CI.
    """
    import inspect
    from app.api import agent_routes

    src = inspect.getsource(agent_routes.chat_with_agent)
    _, _, after = src.partition("except Exception as persist_err:")
    assert after, "persist error handler not found in chat_with_agent"
    handler = after[:2000]

    assert "logger.error" in handler, "persistence failure must log at ERROR, not warning"
    assert '"persisted"' in handler or "'persisted'" in handler, (
        "response must carry persisted=False so a caller can tell 'answered and saved' "
        "from 'answered and thrown away'"
    )
    assert "persistence_error" in handler, "response must carry persistence_error"
    assert 'result["persisted"] = True' in src, (
        "the success path must mark persisted=True, otherwise the flag is unreadable"
    )
