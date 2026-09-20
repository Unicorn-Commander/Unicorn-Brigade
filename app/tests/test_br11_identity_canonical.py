# Executed by Grok (headless lane)
"""BR-1.1 (P-00129) — canonical user_id unification tests.

Unmarked tests use a throwaway SQLite DB under a temp dir. Tests marked
``postgres`` use ``TEST_DATABASE_URL`` (the existing test DSN convention in
``tests/test_integration.py``) and skip before opening any engine when that
env is unset — they never fall back to SQLite. Postgres schema is built the
way production does (``app.db.migrations.run_additive_migrations``, same
order as ``app.db.database.init_db``), not bare ``create_all``. Exercises
the two halves of BR-1.1:

  * ``remap_forked_keycloak_rows`` — the batch migration SQL (portable form that
    prod runs on Postgres), proving forked rows unify with no data loss and that
    a re-run is a no-op (idempotent).
  * ``resolve_canonical_user_id`` — the middleware resolver, proving a Keycloak
    principal and a personal API key resolve to the SAME local ``users.id`` for
    one human, that the legacy email-keyed row is claimed by its sub, and that
    the collision / brand-new-user edges behave.
  * ``GraphitiMemoryManager._read_group_ids`` — the memory dual-read alias,
    proving a cutover SSO user's pre-BR-1.1 agent memory (keyed by the raw sub)
    stays reachable: retrieval reads BOTH the canonical ``{local_id}__{agent}``
    and legacy ``{sub}__{agent}`` namespaces while writes stay canonical-only.
    Pure string logic — needs no Graphiti/FalkorDB, so it runs in this env.

Run directly:  python -m app.tests.test_br11_identity_canonical
Or via pytest: pytest app/tests/test_br11_identity_canonical.py
"""

import asyncio
import inspect
import os
import sqlite3
import tempfile
import uuid

import pytest
from sqlalchemy import event, select, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.exc import CompileError, OperationalError, UnsupportedCompilationError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles

from app.auth.middleware import resolve_canonical_user_id
from app.db.database import Base
from app.db.migrations import (
    MIGRATIONS,
    remap_forked_keycloak_rows,
    run_additive_migrations,
)
from app.db.models import BuilderSession, Conversation, User

# BR-1.2 added ``org_id NOT NULL DEFAULT current_org_id()`` to conversations /
# builder_sessions (and friends). ``current_org_id()`` is a Postgres function
# (reads the app.current_org_id RLS GUC); SQLite has no such function, so building
# this test's throwaway schema from the real models and inserting a row would fail
# with "unknown function: current_org_id()". Register a stub on every SQLite
# connection that returns a fixed uuid — enough to satisfy the server-default +
# NOT NULL. This test is about user_id remapping, not org isolation, so the actual
# org_id value is irrelevant.
_STUB_ORG_ID = "00000000-0000-0000-0000-000000000000"


@compiles(UUID, "sqlite")
def _sqlite_uuid(type_, compiler, **kw):
    """Postgres UUID columns are CHAR(36) on the throwaway SQLite harness."""
    return "CHAR(36)"


_POSTGRES_UUID_DDL_TOKENS = ("uuid", "gen_random_uuid")
_SQLITE_PG_UUID_DDL_ERRORS = (
    CompileError,
    UnsupportedCompilationError,
    OperationalError,
)


def _compiler_or_dbapi_diagnostic(exc: BaseException) -> str:
    """Compiler / DBAPI message only — never the SQLAlchemy-rendered statement.

    ``str(StatementError)`` appends ``[SQL: ...]``. Matching on that text
    treats every wrapped error whose statement mentions ``gen_random_uuid()``
    as a UUID-DDL skip (locked DB, disk I/O, duplicate column). Classify:

    * ``CompileError`` / ``UnsupportedCompilationError``: ``err.args[0]``
      (compiler message, before any statement is attached).
    * ``OperationalError``: ``err.orig`` (the ``sqlite3.OperationalError``)
      via ``orig.args[0]`` / ``str(orig)`` — SQLAlchemy's
      ``StatementError.orig`` / ``.statement`` split. Never ``str(err)``.
    """
    if isinstance(exc, CompileError):
        return str(exc.args[0]).lower() if exc.args else ""
    orig = getattr(exc, "orig", None)
    if not isinstance(orig, sqlite3.OperationalError):
        return ""
    if orig.args:
        return str(orig.args[0]).lower()
    return str(orig).lower()


def _sqlite_cannot_compile_postgres_uuid_ddl(dialect_name: str, exc: BaseException) -> bool:
    """True only when SQLite fails specifically on Postgres UUID DDL.

    Schema-creation errors that are not this limitation (JSONB, a bad
    constraint, a locked database, disk I/O, a duplicate column) stay
    failures — even when the submitted SQL mentions gen_random_uuid().
    """
    if dialect_name != "sqlite":
        return False
    if not isinstance(exc, _SQLITE_PG_UUID_DDL_ERRORS):
        return False
    blob = _compiler_or_dbapi_diagnostic(exc)
    return any(token in blob for token in _POSTGRES_UUID_DDL_TOKENS)


# Existing test DSN convention (tests/test_integration.py::test_database_url).
_TEST_PG_DSN_ENV = "TEST_DATABASE_URL"


def _postgres_requested(request) -> bool:
    """True when the requesting test is marked ``postgres``."""
    return request.node.get_closest_marker("postgres") is not None


def _identity_db_url(*, postgres: bool):
    """Return ``(engine_url, sqlite_path_or_None)``.

    Postgres-marked runs read ``TEST_DATABASE_URL`` and skip *before* any
    engine is opened when it is unset. Unmarked runs keep on-disk SQLite.
    """
    if postgres:
        dsn = os.environ.get(_TEST_PG_DSN_ENV)
        if not dsn:
            pytest.skip(f"requires PostgreSQL: set {_TEST_PG_DSN_ENV}")
        return dsn, None
    fd, path = tempfile.mkstemp(prefix="br11_scratch_", suffix=".sqlite")
    os.close(fd)
    return f"sqlite+aiosqlite:///{path}", path


def _official_current_org_id_sql() -> str:
    """Production ``current_org_id()`` body from ``app.db.migrations.MIGRATIONS``.

    The identity harness must not invent a private copy of this function;
    create_all does not create it. init_db() applies this SQL before create_all
    then calls run_additive_migrations — same order as here, on this engine.
    """
    needle = "CREATE OR REPLACE FUNCTION current_org_id()"
    for _version, _desc, sql in MIGRATIONS:
        statements = [sql] if isinstance(sql, str) else sql
        for stmt in statements:
            if needle in stmt:
                return stmt.strip()
    raise RuntimeError(
        "app.db.migrations.MIGRATIONS does not define current_org_id(); "
        "the identity postgres harness cannot invent one"
    )


def _org_bound_sessionmaker(engine, org_id: str):
    """Session factory that binds ``app.current_org_id`` the way middleware does.

    ``conversations.org_id`` is ``NOT NULL DEFAULT current_org_id()``. Without
    the GUC the default is NULL and inserts fail. ``org_id`` is the
    migration-seeded ``early-access`` row, not a test-invented tenant.
    """
    factory = async_sessionmaker(engine, expire_on_commit=False)

    class _BoundSession:
        def __init__(self):
            self._raw = factory()

        async def __aenter__(self):
            session = await self._raw.__aenter__()
            await session.execute(
                text("SELECT set_config('app.current_org_id', :o, false)"),
                {"o": org_id},
            )
            return session

        async def __aexit__(self, *exc):
            return await self._raw.__aexit__(*exc)

    return _BoundSession


async def _bootstrap_postgres_identity_schema(engine) -> str:
    """Production schema path on this throwaway engine, not bare create_all.

    Mirrors ``app.db.database.init_db``: official ``current_org_id()`` SQL,
    then ``create_all``, then ``run_additive_migrations`` (RLS, FORCE RLS,
    early-access org). Does not call ``init_db()`` (process-global engine +
    LOGIN role provisioning). Returns the seeded early-access org id.
    """
    fn_sql = _official_current_org_id_sql()
    async with engine.begin() as conn:
        await conn.execute(text(fn_sql))
        await conn.run_sync(
            lambda sync_conn: Base.metadata.create_all(sync_conn, checkfirst=True)
        )
    await run_additive_migrations(engine)
    async with engine.begin() as conn:
        org_id = (
            await conn.execute(
                text("SELECT id FROM organizations WHERE slug = 'early-access'")
            )
        ).scalar()
        force = (
            await conn.execute(
                text(
                    "SELECT c.relforcerowsecurity FROM pg_class c "
                    "JOIN pg_namespace n ON n.oid = c.relnamespace "
                    "WHERE c.relname = 'conversations' "
                    "AND n.nspname = current_schema()"
                )
            )
        ).scalar()
    if not force:
        raise RuntimeError(
            "run_additive_migrations did not FORCE RLS on conversations; "
            "postgres identity harness is not the production schema"
        )
    if org_id is None:
        raise RuntimeError(
            "run_additive_migrations did not seed organizations.slug='early-access'"
        )
    return str(org_id)


async def _open_fresh_db(*, postgres: bool = False):
    """Create a throwaway identity DB. Returns (engine, sessionmaker, path).

    ``postgres=True`` uses ``TEST_DATABASE_URL`` (skip if unset) and never
    opens SQLite. Schema is built the way production does (migrations), not
    bare create_all. ``postgres=False`` is the unmarked SQLite harness.
    Caller (or the ``_fresh_db`` fixture) disposes + unlinks.
    """
    url, sqlite_path = _identity_db_url(postgres=postgres)
    engine = None
    try:
        engine = create_async_engine(url)
        if sqlite_path is not None:

            @event.listens_for(engine.sync_engine, "connect")
            def _register_pg_compat(dbapi_connection, _record):
                dbapi_connection.create_function("current_org_id", 0, lambda: _STUB_ORG_ID)
                dbapi_connection.create_function(
                    "gen_random_uuid", 0, lambda: str(uuid.uuid4())
                )

            dialect_name = engine.dialect.name
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            return engine, async_sessionmaker(engine, expire_on_commit=False), sqlite_path

        org_id = await _bootstrap_postgres_identity_schema(engine)
        return engine, _org_bound_sessionmaker(engine, org_id), None
    except Exception as exc:
        dialect_name = engine.dialect.name if engine is not None else None
        if engine is not None:
            await engine.dispose()
        if sqlite_path is not None:
            try:
                os.unlink(sqlite_path)
            except OSError:
                pass
        if dialect_name and _sqlite_cannot_compile_postgres_uuid_ddl(dialect_name, exc):
            pytest.skip(
                "SQLite cannot compile Postgres-only UUID / gen_random_uuid() DDL "
                f"({type(exc).__name__}); these identity scenarios require PostgreSQL"
            )
        raise


@pytest.fixture
async def _fresh_db(request):
    """Identity harness DB: PostgreSQL when marked ``postgres`` and a DSN is
    set, otherwise SQLite. A marked test with no ``TEST_DATABASE_URL`` skips
    before any engine is created.
    """
    engine, Session, path = await _open_fresh_db(postgres=_postgres_requested(request))
    try:
        yield engine, Session, path
    finally:
        await engine.dispose()
        if path is not None:
            try:
                os.unlink(path)
            except OSError:
                pass


async def _count(session, table):
    r = await session.execute(text(f"SELECT COUNT(*) FROM {table}"))
    return r.scalar_one()


def _norm(v):
    """Canonicalize an id for comparison. The throwaway SQLite renders the
    postgresql.UUID type asymmetrically (ORM -> dashed, raw SQL -> no dashes);
    on prod Postgres both forms are the identical canonical dashed string. Fold
    UUID formatting so we compare identity, not text. Non-UUIDs
    ('anonymous', downstream pass-through ids) pass through untouched."""
    try:
        return str(uuid.UUID(str(v)))
    except (ValueError, TypeError):
        return v


async def _scenario_batch_remap(log, engine, Session, path):
    """Two synthetic identities that fork today unify via the batch migration."""
    try:
        kc_sub = str(uuid.uuid4())          # the Keycloak sub (distinct from local id)
        downstream = "projops-passthrough-42"  # opaque downstream id, must survive

        async with Session() as s:
            # Legacy email-keyed row (auto-provisioned pre-BR-1.1: no keycloak_id).
            u = User(email="alice@x.com", name="alice",
                     password_hash="NOLOGIN-SSO-ONLY", role="operator",
                     apps=[], is_active=True)
            s.add(u)
            await s.commit()
        async with Session() as s:
            # The canonical id is whatever the DB stores — the value the API-key
            # path (a fresh SELECT then str(user.id)) and the remap (SELECT u.id)
            # both key on. Read it fresh, exactly like the real auth paths do.
            local_id = str((await s.execute(select(User))).scalar_one().id)

        async with Session() as s:
            # Forked ownership: one conv written by the KC-bearer path (user_id =
            # sub), one by the API-key path (user_id = local id) — SAME human.
            s.add(Conversation(id=str(uuid.uuid4()), user_id=kc_sub, title="via-sso"))
            s.add(Conversation(id=str(uuid.uuid4()), user_id=local_id, title="via-apikey"))
            s.add(Conversation(id=str(uuid.uuid4()), user_id="anonymous", title="anon"))
            s.add(Conversation(id=str(uuid.uuid4()), user_id=downstream, title="downstream"))
            s.add(BuilderSession(id=str(uuid.uuid4()), user_id=kc_sub))
            await s.commit()

        total_before = None
        async with Session() as s:
            total_before = (await _count(s, "conversations"),
                            await _count(s, "builder_sessions"))
            # Prove the API-key path (str(user.id)) agrees with the remap's
            # SELECT-id source — the invariant BR-1.1 relies on.
            raw_id = (await s.execute(text("SELECT id FROM users"))).scalar_one()
            assert _norm(raw_id) == _norm(local_id), "str(user.id) must equal the stored users.id"
            # A login (or operator backfill) has stamped keycloak_id = sub.
            u = (await s.execute(select(User).where(User.id == local_id))).scalar_one()
            u.keycloak_id = kc_sub
            await s.commit()

        # Run the batch migration exactly as prod would.
        async with Session() as s:
            await remap_forked_keycloak_rows(s)
            await s.commit()

        async with Session() as s:
            rows = (await s.execute(select(Conversation.title, Conversation.user_id))).all()
            by_title = dict(rows)
            bsub = (await s.execute(select(BuilderSession.user_id))).scalars().all()
            total_after = (await _count(s, "conversations"),
                           await _count(s, "builder_sessions"))

        assert _norm(by_title["via-sso"]) == _norm(local_id), "sub-keyed conv must remap to local id"
        assert _norm(by_title["via-apikey"]) == _norm(local_id), "already-canonical conv unchanged"
        assert by_title["anon"] == "anonymous", "'anonymous' must be untouched"
        assert by_title["downstream"] == downstream, "downstream pass-through must survive"
        assert [_norm(x) for x in bsub] == [_norm(local_id)], "builder session sub-keyed row must remap"
        assert total_before == total_after, "no rows created or lost"
        assert _norm(by_title["via-sso"]) == _norm(by_title["via-apikey"]), "the fork is unified"

        # Idempotency: a second pass changes nothing.
        async with Session() as s:
            await remap_forked_keycloak_rows(s)
            await s.commit()
        async with Session() as s:
            rows2 = (await s.execute(select(Conversation.title, Conversation.user_id))).all()
        assert dict(rows2) == by_title, "remap must be idempotent"

        log.append(f"[batch] local_id={local_id[:8]} sub={kc_sub[:8]} -> unified; "
                   f"downstream+anon preserved; idempotent OK")
    finally:
        await engine.dispose()
        if path is not None:
            os.unlink(path)


async def _scenario_resolver(log, engine, Session, path):
    """KC-bearer and API-key resolve to the SAME local id; claim + edges."""
    try:
        kc_sub = str(uuid.uuid4())

        async with Session() as s:
            u = User(email="bob@x.com", name="bob",
                     password_hash="NOLOGIN-SSO-ONLY", role="viewer",
                     apps=["librechat"], is_active=True)  # keycloak_id NULL
            s.add(u)
            await s.commit()
        async with Session() as s:
            local_id = str((await s.execute(select(User))).scalar_one().id)
        async with Session() as s:
            s.add(Conversation(id=str(uuid.uuid4()), user_id=kc_sub, title="bob-sso"))
            await s.commit()

        # KC-bearer path resolves the canonical id.
        async with Session() as s:
            kc_resolved = await resolve_canonical_user_id(
                s, kc_sub=kc_sub, email="Bob@x.com",   # mixed case → normalized
                derived_apps=["projectops"], realm_role="operator")

        # API-key path id is simply str(users.id).
        async with Session() as s:
            u = (await s.execute(select(User).where(User.email == "bob@x.com"))).scalar_one()
            apikey_id = str(u.id)
            claimed_sub = u.keycloak_id
            merged_apps = u.apps
            synced_role = u.role
            conv_owner = (await s.execute(
                select(Conversation.user_id).where(Conversation.title == "bob-sso"))
            ).scalar_one()

        assert _norm(kc_resolved) == _norm(local_id), "resolver must return the local users.id, not the sub"
        assert _norm(kc_resolved) == _norm(apikey_id), "KC-bearer and API-key MUST yield the same id"
        assert kc_resolved != kc_sub, "resolver must NOT return the raw Keycloak sub"
        assert claimed_sub == kc_sub, "legacy email row must be claimed by the sub"
        assert _norm(conv_owner) == _norm(local_id), "lazy remap must relabel the sub-keyed conv"
        assert set(merged_apps) == {"librechat", "projectops"}, "apps merge additively"
        assert synced_role == "operator", "role syncs from Keycloak"

        # Edge: brand-new user (no keycloak_id match, no email row) → provisioned.
        new_sub = str(uuid.uuid4())
        async with Session() as s:
            new_id = await resolve_canonical_user_id(
                s, kc_sub=new_sub, email="carol@x.com",
                derived_apps=[], realm_role="viewer")
        async with Session() as s:
            carol = (await s.execute(select(User).where(User.email == "carol@x.com"))).scalar_one()
        # Compare as UUIDs: on the throwaway SQLite the just-created object holds
        # the dashed python default while a fresh SELECT returns the normalized
        # form — the SAME identity (on prod Postgres both are the canonical
        # dashed string, so this equality is exact there).
        assert uuid.UUID(new_id) == uuid.UUID(str(carol.id)), "new user provisioned to a stable id"
        assert carol.keycloak_id == new_sub, "new user bound to its sub"

        # Edge: collision — same email presents a DIFFERENT sub. Keep original binding.
        async with Session() as s:
            collide_id = await resolve_canonical_user_id(
                s, kc_sub=str(uuid.uuid4()), email="bob@x.com",
                derived_apps=[], realm_role="operator")
        async with Session() as s:
            u2 = (await s.execute(select(User).where(User.email == "bob@x.com"))).scalar_one()
        assert _norm(collide_id) == _norm(local_id), "collision still resolves the same human's row"
        assert u2.keycloak_id == kc_sub, "collision must NOT overwrite the existing sub binding"

        # Edge: emailless token with no prior binding → degraded (None), caller keeps sub.
        async with Session() as s:
            degraded = await resolve_canonical_user_id(
                s, kc_sub=str(uuid.uuid4()), email=None,
                derived_apps=[], realm_role="viewer")
        assert degraded is None, "emailless + unknown sub cannot mint a row"

        log.append(f"[resolver] KC id == API-key id == {local_id[:8]}; claim+merge+role OK; "
                   f"new-user/collision/emailless edges OK")
    finally:
        await engine.dispose()
        if path is not None:
            os.unlink(path)


def _scenario_memory_alias(log):
    """BR-1.1 memory dual-read: a cutover SSO user's pre-BR-1.1 agent memory —
    stored in Graphiti under a group_id keyed by the raw Keycloak sub — stays
    reachable AFTER the id cutover with no data movement. Retrieval reads both
    the canonical and legacy namespaces; writes stay canonical-only, so the sub
    namespace only drains via reads and never accretes new memory.

    Pure ``_group_id`` / ``_read_group_ids`` string logic — Graphiti/FalkorDB are
    not importable in this env, but the manager degrades to ``graphiti=None`` and
    these methods stay callable, which is exactly the alias surface under test."""
    from app.memory.graphiti_manager import GraphitiMemoryManager

    m = GraphitiMemoryManager()  # graphiti absent -> self.graphiti None; pure methods still work
    local_id = "11111111-2222-3333-4444-555555555555"  # canonical local users.id
    sub = "kc|abcd-legacy-sub"                          # pre-BR-1.1 Keycloak sub
    agent = "col-finance"

    write_group = m._group_id(local_id, agent)

    # 1. Dual-read covers BOTH namespaces, canonical first.
    read_groups = m._read_group_ids(local_id, agent, legacy_user_id=sub)
    assert write_group in read_groups, "reads must cover the canonical write namespace"
    assert m._group_id(sub, agent) in read_groups, "reads must ALSO cover the legacy sub namespace"
    assert len(read_groups) == 2, "exactly canonical + legacy"
    assert read_groups[0] == write_group, "canonical namespace is read first"

    # 2. Writes are canonical-only: the write namespace is the local-id group and
    #    is never the legacy group — new memory can only land under the local id.
    assert write_group == m._group_id(local_id, agent)
    assert write_group != m._group_id(sub, agent), "write namespace must differ from the legacy one"

    # 3. Nothing to alias -> a single (canonical) namespace, identical to pre-alias.
    assert m._read_group_ids(local_id, agent, legacy_user_id=None) == [write_group], \
        "None sub -> single namespace"
    assert m._read_group_ids(local_id, agent, legacy_user_id=local_id) == [write_group], \
        "sub == canonical id -> single namespace"

    # 4. Case scoping is preserved on BOTH namespaces (memory can't bleed cases).
    cg = m._read_group_ids(local_id, agent, case_id="case-9", legacy_user_id=sub)
    assert cg == [m._group_id(local_id, agent, "case-9"), m._group_id(sub, agent, "case-9")], \
        "case segment applied to both canonical + legacy groups"

    # 5. A legacy id that slugs to the SAME group is deduped to a single read.
    assert m._read_group_ids("a.b", agent, legacy_user_id="a/b") == [m._group_id("a.b", agent)], \
        "slug collision must not double-read the same namespace"

    log.append(f"[memory] read={read_groups}; write-only={write_group}; "
               f"None/equal->single; case+dedupe OK")


async def _run_all():
    log = []
    db = await _open_fresh_db(postgres=False)
    await _scenario_batch_remap(log, *db)
    db = await _open_fresh_db(postgres=False)
    await _scenario_resolver(log, *db)
    _scenario_memory_alias(log)
    return log


# ---- pytest entrypoints ----

_UUID_BEARING_SQL = (
    "CREATE TABLE organizations (id CHAR(36) DEFAULT gen_random_uuid() NOT NULL)"
)


def test_schema_skip_only_matches_sqlite_uuid_or_gen_random_uuid():
    """The BR-1.1 fixture must not turn an unrelated schema error into a skip."""
    uuid_compile = CompileError("Compiler can't render element of type UUID")
    assert _sqlite_cannot_compile_postgres_uuid_ddl("sqlite", uuid_compile) is True
    assert _sqlite_cannot_compile_postgres_uuid_ddl("postgresql", uuid_compile) is False

    gen_compile = UnsupportedCompilationError(None, "DEFAULT gen_random_uuid()")
    assert _sqlite_cannot_compile_postgres_uuid_ddl("sqlite", gen_compile) is True

    for diagnostic in (
        'near "gen_random_uuid": syntax error',
        'unrecognized token: "gen_random_uuid"',
        "no such function: gen_random_uuid",
    ):
        true_uuid_ddl = OperationalError(
            _UUID_BEARING_SQL, {}, sqlite3.OperationalError(diagnostic)
        )
        assert _sqlite_cannot_compile_postgres_uuid_ddl("sqlite", true_uuid_ddl) is True
        assert _sqlite_cannot_compile_postgres_uuid_ddl("postgresql", true_uuid_ddl) is False

    jsonb_compile = CompileError("Compiler can't render element of type JSONB")
    assert _sqlite_cannot_compile_postgres_uuid_ddl("sqlite", jsonb_compile) is False

    generic_op = OperationalError("CREATE TABLE t (id INTEGER)", {}, Exception("syntax error"))
    assert _sqlite_cannot_compile_postgres_uuid_ddl("sqlite", generic_op) is False

    assert _sqlite_cannot_compile_postgres_uuid_ddl(
        "sqlite", RuntimeError("gen_random_uuid() exploded")
    ) is False


def test_schema_skip_ignores_statement_text_for_unrelated_operational_errors():
    """Unrelated DBAPI diagnostics must not skip just because SQL names UUID DDL.

    ``str(OperationalError)`` includes the statement. A locked database, disk
    I/O error, or duplicate column wrapped with ``gen_random_uuid()`` SQL
    must still fail the test, not skip.
    """
    for diagnostic in (
        "database is locked",
        "disk I/O error",
        "duplicate column name: x",
    ):
        sqlite_orig = OperationalError(
            _UUID_BEARING_SQL, {}, sqlite3.OperationalError(diagnostic)
        )
        assert (
            _sqlite_cannot_compile_postgres_uuid_ddl("sqlite", sqlite_orig) is False
        ), diagnostic
        # Astra r3 reproduction: orig is a bare Exception; statement still
        # contains gen_random_uuid() so str(err) would have matched.
        wrapped = OperationalError(_UUID_BEARING_SQL, {}, Exception(diagnostic))
        assert (
            _sqlite_cannot_compile_postgres_uuid_ddl("sqlite", wrapped) is False
        ), diagnostic


@pytest.mark.asyncio
async def test_postgres_marked_without_dsn_skips_before_opening_sqlite(monkeypatch):
    """Marked postgres path with no TEST_DATABASE_URL must skip before any engine."""
    monkeypatch.delenv(_TEST_PG_DSN_ENV, raising=False)
    opened = []

    def fake_create(url, *args, **kwargs):
        opened.append(url)
        raise AssertionError(f"create_async_engine must not run, got {url!r}")

    monkeypatch.setattr(
        "app.tests.test_br11_identity_canonical.create_async_engine", fake_create
    )
    with pytest.raises(
        pytest.skip.Exception, match="requires PostgreSQL: set TEST_DATABASE_URL"
    ):
        await _open_fresh_db(postgres=True)
    assert opened == []


@pytest.mark.asyncio
async def test_postgres_marked_with_dsn_opens_postgres_not_sqlite(monkeypatch):
    """Marked postgres path with TEST_DATABASE_URL must open that DSN, not SQLite."""
    dsn = "postgresql+asyncpg://ci:ci@127.0.0.1:1/identity_ci"
    monkeypatch.setenv(_TEST_PG_DSN_ENV, dsn)
    opened = []

    def fake_create(url, *args, **kwargs):
        opened.append(url)
        raise RuntimeError("stop-before-connect")

    monkeypatch.setattr(
        "app.tests.test_br11_identity_canonical.create_async_engine", fake_create
    )
    with pytest.raises(RuntimeError, match="stop-before-connect"):
        await _open_fresh_db(postgres=True)
    assert opened == [dsn]
    assert all("sqlite" not in str(url) for url in opened)


@pytest.mark.asyncio
async def test_unmarked_path_opens_sqlite_without_dsn(monkeypatch):
    """Unmarked tests keep SQLite even when TEST_DATABASE_URL is absent."""
    monkeypatch.delenv(_TEST_PG_DSN_ENV, raising=False)
    opened = []

    def fake_create(url, *args, **kwargs):
        opened.append(url)
        raise RuntimeError("stop-before-connect")

    monkeypatch.setattr(
        "app.tests.test_br11_identity_canonical.create_async_engine", fake_create
    )
    with pytest.raises(RuntimeError, match="stop-before-connect"):
        await _open_fresh_db(postgres=False)
    assert len(opened) == 1
    assert str(opened[0]).startswith("sqlite+aiosqlite:///")


def test_identity_postgres_schema_uses_migration_current_org_id_not_a_private_copy():
    """Postgres bootstrap must use the repo migrations, not a private function."""
    sql = _official_current_org_id_sql()
    assert "CREATE OR REPLACE FUNCTION current_org_id()" in sql
    assert "current_setting('app.current_org_id'" in sql
    src = inspect.getsource(_bootstrap_postgres_identity_schema)
    assert "run_additive_migrations" in src
    assert "nullif(current_setting" not in src
    assert "AS $$" not in src


def test_fresh_db_fixture_follows_postgres_marker():
    """The ``_fresh_db`` fixture selects Postgres only for marked tests."""

    class _Node:
        def __init__(self, marked):
            self._marked = marked

        def get_closest_marker(self, name):
            return object() if self._marked and name == "postgres" else None

    class _Request:
        def __init__(self, marked):
            self.node = _Node(marked)

    assert _postgres_requested(_Request(True)) is True
    assert _postgres_requested(_Request(False)) is False


@pytest.mark.integration
@pytest.mark.postgres
@pytest.mark.asyncio
async def test_postgres_schema_applies_migrations_not_bare_create_all(_fresh_db):
    """create_all does not create current_org_id(), FORCE RLS, or policies."""
    _engine, Session, _path = _fresh_db
    async with Session() as s:
        fn = (
            await s.execute(
                text(
                    "SELECT EXISTS ("
                    "SELECT 1 FROM pg_proc p "
                    "JOIN pg_namespace n ON n.oid = p.pronamespace "
                    "WHERE p.proname = 'current_org_id' "
                    "AND n.nspname = current_schema())"
                )
            )
        ).scalar()
        force = (
            await s.execute(
                text(
                    "SELECT c.relforcerowsecurity FROM pg_class c "
                    "JOIN pg_namespace n ON n.oid = c.relnamespace "
                    "WHERE c.relname = 'conversations' "
                    "AND n.nspname = current_schema()"
                )
            )
        ).scalar()
        policy = (
            await s.execute(
                text(
                    "SELECT EXISTS ("
                    "SELECT 1 FROM pg_policies "
                    "WHERE tablename = 'conversations' "
                    "AND policyname = 'conversations_org_isolation' "
                    "AND schemaname = current_schema())"
                )
            )
        ).scalar()
    assert fn is True, "current_org_id() missing — migrations did not run"
    assert force is True, "conversations FORCE RLS missing — bare create_all"
    assert policy is True, "conversations_org_isolation policy missing"


@pytest.mark.integration
@pytest.mark.postgres
@pytest.mark.asyncio
async def test_batch_remap_unifies_forked_rows(_fresh_db):
    await _scenario_batch_remap([], *_fresh_db)


@pytest.mark.integration
@pytest.mark.postgres
@pytest.mark.asyncio
async def test_resolver_unifies_kc_and_apikey(_fresh_db):
    await _scenario_resolver([], *_fresh_db)


def test_memory_dual_read_alias():
    """Sync — the alias is pure string logic, no DB/event-loop needed."""
    _scenario_memory_alias([])


def test_authuser_carries_keycloak_id():
    """The dual-read plumbing hinges on AuthUser exposing the legacy sub."""
    from app.auth.middleware import AuthUser
    from app.auth.roles import UserRole
    # Default None: master-admin / agent keys have no bound sub -> no alias.
    assert AuthUser(id="x", role=UserRole.VIEWER).keycloak_id is None
    # Threaded by the KC-bearer and user-API-key paths.
    au = AuthUser(id="local-1", role=UserRole.VIEWER, user_id="local-1", keycloak_id="kc-sub-9")
    assert au.keycloak_id == "kc-sub-9"


if __name__ == "__main__":
    out = asyncio.run(_run_all())
    print("BR-1.1 identity-canonical test — PASS")
    for line in out:
        print("  " + line)
