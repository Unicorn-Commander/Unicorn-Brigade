# Executed by Grok (headless lane)
"""
Async database connection manager using SQLAlchemy 2.0 + asyncpg.

Two-DSN tenancy split (BR-1.2 / BR-1.3)
---------------------------------------
Brigade enforces per-org isolation with Postgres Row-Level Security (see
app/db/migrations.py :: 20260626_01_org_tenancy_rls). RLS is only meaningful if
the RUNTIME actually connects as a role that is *subject* to it — a superuser or
a BYPASSRLS role silently defeats every policy. So we split the connection by
purpose:

  * ``DATABASE_URL``            — RUNTIME app-role DSN. Normal request traffic
                                  (``engine`` / ``async_session``). In production
                                  this MUST be a ``NOLOGIN``-parent-backed LOGIN
                                  role ``IN ROLE brigade_app`` that is
                                  ``NOBYPASSRLS`` + ``NOSUPERUSER``. RLS applies.
  * ``MIGRATION_DATABASE_URL``  — OWNER/ADMIN DSN for DDL, migrations, role
                                  provisioning, and trusted cross-tenant system
                                  work (``migration_engine`` / ``admin_session``).
                                  Defaults to ``DATABASE_URL`` for single-role dev.

In dev the two DSNs are equal, so ``migration_engine is engine`` and everything
runs as the one (usually superuser) role — RLS exists but is bypassed. That is
the pre-BR-1.2 behavior and is fine for local work; ``verify_app_role_not_bypassing``
logs loudly so it is never a silent surprise in a real deployment.
"""
import asyncio
import logging
import os
import re
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


# Default to local dev postgres; overridden by DATABASE_URL env var. In prod this
# is the RLS-subject app-role DSN (see module docstring).
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://leads_user:leads_password_dev@localhost:5434/unicorn_brigade"
)
# Owner/admin DSN for DDL + migrations + provisioning + cross-tenant system work.
# Falls back to DATABASE_URL so single-role dev keeps working unchanged.
MIGRATION_DATABASE_URL = os.getenv("MIGRATION_DATABASE_URL", DATABASE_URL)

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)
migration_engine = engine if MIGRATION_DATABASE_URL == DATABASE_URL else create_async_engine(
    MIGRATION_DATABASE_URL,
    echo=False,
    pool_size=2,
    max_overflow=2,
    pool_pre_ping=True,
)

# Request-scoped sessions bind to the RUNTIME (app-role) engine → subject to RLS.
async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
# Admin/owner-bound sessions for trusted CROSS-TENANT system work. The scheduler
# enumerates + dispatches jobs across every org, so it fundamentally cannot be
# constrained by the per-request ``app.current_org_id`` RLS filter (with an empty
# GUC, FORCE RLS would hide every row and it would load zero jobs). It still binds
# the GUC per job so each write is attributed to the correct org. In dev
# (MIGRATION_DATABASE_URL == DATABASE_URL) this is the same engine as async_session.
admin_session = async_sessionmaker(migration_engine, expire_on_commit=False, class_=AsyncSession)


class OrgContextLost(RuntimeError):
    """The request has a bound org but the connection's RLS GUC is empty and
    could not be restored. Raised instead of letting a write silently no-op."""


async def ensure_org_context(session: AsyncSession) -> None:
    """Re-assert this REQUEST's org into the CONNECTION's RLS GUC before a write.

    ``app.current_org_id`` is a *connection*-level setting, but a request is not
    pinned to one connection: every ``session.commit()`` inside a repository
    method releases the connection back to the pool, and the next statement
    checks out a DIFFERENT one — which never received this request's
    ``set_config`` (or, worse, has just been blanked by another request's
    ``_clear_org_context`` teardown). The write then lands with a NULL org_id and
    Postgres rejects it as "new row violates row-level security policy".

    That is not hypothetical: it silently dropped 751 assistant chat messages
    between 2026-07-17 (when the B1 teardown started positively blanking pooled
    connections) and 2026-08-11. Before B1, these writes only ever succeeded by
    ACCIDENT — they inherited a stale org left on a recycled connection, which is
    the very cross-tenant leak B1 closed. Closing the leak turned a silent
    correctness bug into silent data loss.

    Call this at the top of any repository write that targets a FORCE-RLS table.

    Fails SAFE: with no org bound for this request (public/unbound callers) it is
    a no-op and the pre-existing behaviour is unchanged — it can never invent an
    org, so it cannot re-open B1.
    """
    try:
        from app.orchestration.event_bus import current_org_id_var
        org_id = current_org_id_var.get()
    except Exception:  # noqa: BLE001 - context var must never break a write
        return
    if not org_id:
        # No bound org for this request. Nothing to restore; leave the GUC alone.
        return
    current = (await session.execute(
        text("SELECT current_setting('app.current_org_id', true)")
    )).scalar()
    if current == str(org_id):
        return  # connection already carries the right org — no round-trip needed
    await session.execute(
        text("SELECT set_config('app.current_org_id', :org_id, false)"),
        {"org_id": str(org_id)},
    )
    verify = (await session.execute(
        text("SELECT current_setting('app.current_org_id', true)")
    )).scalar()
    if verify != str(org_id):
        # Refuse to proceed into a write that RLS will silently reject.
        raise OrgContextLost(
            "could not restore app.current_org_id on this connection "
            f"(wanted {org_id}, got {verify!r})"
        )
    logger.debug("Re-asserted org RLS context on a recycled connection")


async def _clear_org_context(session: AsyncSession) -> None:
    """Positively clear the per-request org RLS GUC (``app.current_org_id``) at
    SESSION level and COMMIT so the clear PERSISTS on the pooled connection.

    Postgres REVERTS a session-level ``set_config(..., is_local=false)`` if the
    surrounding transaction later rolls back, so the clear must be committed to
    stick — that reversion is exactly the B1 cross-tenant leak. Order is
    load-bearing: rollback first (discard any handler transaction state), then
    clear, then commit.

    Callers that resolve NO bound user — public paths, ``get_current_user_optional``
    returning None, an SSE identity with no org — call this to GUARANTEE an empty
    GUC, so an unbound request can never inherit another tenant's org from a reused
    connection regardless of pool timing.
    """
    # Clear the request-scoped org FIRST so ``ensure_org_context`` can never
    # resurrect it on a later write: after a deliberate clear there is no bound
    # org, and the context var is the single source of truth for that.
    try:
        from app.orchestration.event_bus import current_org_id_var
        current_org_id_var.set(None)
    except Exception:  # noqa: BLE001 - never break the clear on a context-var error
        logger.debug("Could not reset current_org_id_var during clear", exc_info=True)
    await session.rollback()
    await session.execute(text("SELECT set_config('app.current_org_id', '', false)"))
    await session.commit()


async def _invalidate_pooled_session(session: AsyncSession) -> None:
    """Discard a connection whose org GUC cannot be proven cleared.

    ``asyncio.shield`` is used HERE and only here: a cancelled streaming
    generator's next ``await`` would otherwise raise ``CancelledError``
    before ``invalidate`` runs, returning a possibly org-tainted connection
    to the pool (the B1 leak). The GUC clear itself is not shielded — a hung
    rollback must not pin the cancelled generator; we fail safe by discarding
    the connection instead.
    """
    try:
        await asyncio.shield(session.invalidate())
    except Exception:
        logger.debug("Session invalidate failed", exc_info=True)


@asynccontextmanager
async def streaming_org_context(session: AsyncSession, org_id: str | None):
    """Re-bind the request's org for FORCE-RLS writes issued from a
    ``StreamingResponse`` generator body.

    FastAPI >= 0.106 (this repo pins 0.115) exits yield-dependencies BEFORE the
    response body is streamed. So by the time a ``StreamingResponse`` generator
    runs, ``get_session``'s teardown has already executed — clearing the
    connection's ``app.current_org_id`` GUC AND positively nulling
    ``current_org_id_var`` (see ``_clear_org_context``). A write issued from the
    generator then finds no bound org: ``ensure_org_context`` fails safe to a
    no-op, the row lands with ``org_id = current_org_id()`` → NULL, and Postgres
    rejects it as "new row violates row-level security policy". That is how every
    streaming agent chat with tool calls silently lost its ``tool_executions``
    audit rows while the SSE stream itself returned 200.

    Bind the org for the duration of the block so the repository methods'
    ``ensure_org_context`` can do its job, then POSITIVELY clear it on exit —
    the same B1 guarantee ``get_session`` gives ordinary requests: no connection
    may return to the pool carrying this org.

    Fail-safe: with no ``org_id`` (unbound/public caller) this is a no-op. It
    can never invent an org, so it cannot re-open B1; the write stays correctly
    refused by RLS.

    Cleanup is cancellation-safe. ``asyncio.CancelledError`` is a
    ``BaseException``, not ``Exception``: a disconnect that cancels during
    rollback/clear must still (1) reset the ContextVar and (2) clear the GUC
    or ``invalidate`` the connection when the clear cannot be confirmed, then
    re-raise so cancellation is not swallowed.
    """
    if not org_id:
        yield
        return
    from app.orchestration.event_bus import current_org_id_var
    token = current_org_id_var.set(str(org_id))
    try:
        yield
    finally:
        try:
            await _clear_org_context(session)
        except BaseException as exc:
            # Exception *and* CancelledError / GeneratorExit / KeyboardInterrupt.
            # A connection we failed to clear must NOT go back to the pool
            # carrying this request's org. Invalidate (shielded), then re-raise
            # anything that is not a regular Exception so cancellation
            # propagates. Client disconnects are CancelledError — log those
            # at debug so every SSE hangup is not a warning.
            if isinstance(exc, Exception):
                logger.warning(
                    "Failed to clear streaming org context; invalidating the session "
                    "so a possibly org-tainted connection is not pooled.",
                    exc_info=True,
                )
            else:
                logger.debug(
                    "Streaming org-context cleanup interrupted; invalidating the "
                    "session so a possibly org-tainted connection is not pooled.",
                    exc_info=True,
                )
            await _invalidate_pooled_session(session)
            if not isinstance(exc, Exception):
                raise
        finally:
            current_org_id_var.reset(token)


async def get_session() -> AsyncSession:
    """Get an async database session."""
    async with async_session() as session:
        try:
            yield session
        finally:
            # B1 (verified cross-tenant leak) fix — ORDER IS LOAD-BEARING. Discard
            # any handler transaction state FIRST (rollback), THEN clear the org
            # RLS GUC, THEN COMMIT so the clear persists at session level on the
            # connection returned to the pool. The previous order
            # (set_config-clear → rollback) was UNDONE by Postgres on that rollback
            # — a session-level set_config(..., false) issued inside a transaction
            # that then rolls back is reverted — so a pooled connection kept the
            # prior request's org and an unbound/anonymous reuse read another
            # tenant's rows (public /a2a/agents, get_agent_card, /stats, …).
            try:
                await _clear_org_context(session)
            except Exception:
                # Clearing failed (DB unreachable, etc.). Do NOT hand a possibly
                # org-tainted connection back to the pool — invalidate it so the
                # pool discards it and the next checkout gets a fresh, GUC-less one.
                logger.warning(
                    "Failed to clear tenant context on DB session; invalidating the "
                    "connection so it is not pooled with a stale org.",
                    exc_info=True,
                )
                try:
                    await session.invalidate()
                except Exception:
                    logger.debug("Session invalidate failed", exc_info=True)


# Postgres identifiers: letter/underscore start, then letters/digits/underscore.
# Anything else is rejected rather than quoted-through, so a hostile role name in
# a DSN can never become injectable DDL.
_PG_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,62}$")


async def provision_app_role() -> None:
    """BR-1.3: ensure the RUNTIME LOGIN role (the one ``DATABASE_URL`` authenticates
    as) exists as a NOBYPASSRLS/NOSUPERUSER member of the NOLOGIN ``brigade_app``
    parent, so it inherits brigade_app's grants but is fully subject to RLS.

    Runs on the OWNER engine (only the owner/admin can CREATE ROLE). Credentials
    come from ``DATABASE_URL`` itself — the password there IS the role password —
    so there is a single source of truth and no duplicate secret. Skipped when the
    runtime and migration roles are the same (single-role dev): there is no
    separate app role to create, and the shared role is intentionally privileged.

    Best-effort + loud: if the owner lacks CREATEROLE, or the role was already
    provisioned out-of-band by an operator, we log and continue rather than crash
    startup.
    """
    if migration_engine is engine:
        logger.info(
            "provision_app_role: MIGRATION_DATABASE_URL == DATABASE_URL — single-role "
            "dev, no separate RLS-subject app role to provision (RLS present but bypassed)."
        )
        return
    try:
        app_url = make_url(DATABASE_URL)
        owner_user = make_url(MIGRATION_DATABASE_URL).username
    except Exception as exc:  # noqa: BLE001
        logger.error("provision_app_role: could not parse DSNs: %s", exc)
        return

    app_user = app_url.username
    app_pw = app_url.password
    if not app_user:
        logger.warning("provision_app_role: DATABASE_URL has no username; skipping.")
        return
    if app_user == owner_user:
        logger.info(
            "provision_app_role: runtime role %r == owner role — nothing to provision.",
            app_user,
        )
        return
    if not _PG_IDENT_RE.match(app_user):
        logger.error(
            "provision_app_role: refusing to provision unsafe role identifier %r.",
            app_user,
        )
        return

    # Password literal: single-quoted, single-quotes doubled. The DO body is
    # dollar-quoted ($do$), and Postgres does not scan for dollar-quotes inside a
    # '...' string literal, so an embedded $do$ in the password cannot break out.
    if app_pw is None:
        pw_clause = ""
    else:
        pw_clause = "PASSWORD '" + str(app_pw).replace("'", "''") + "'"

    provision_sql = f"""
    DO $do$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{app_user}') THEN
            CREATE ROLE "{app_user}" LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB
                NOCREATEROLE {pw_clause} IN ROLE brigade_app;
        ELSE
            ALTER ROLE "{app_user}" LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB
                NOCREATEROLE {pw_clause};
            GRANT brigade_app TO "{app_user}";
        END IF;
    END
    $do$;
    """
    try:
        async with migration_engine.begin() as conn:
            await conn.execute(text(provision_sql))
        logger.info(
            "provision_app_role: ensured LOGIN role %r IN ROLE brigade_app "
            "(NOBYPASSRLS, NOSUPERUSER).",
            app_user,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "provision_app_role: FAILED to provision runtime app role %r (owner may "
            "lack CREATEROLE, or provision it manually): %s",
            app_user,
            exc,
        )


async def verify_app_role_not_bypassing() -> dict | None:
    """BR-1.3 self-check: confirm the RUNTIME connection is actually subject to RLS.

    Connecting as a superuser or a ``rolbypassrls=true`` role silently defeats
    every isolation policy, so we assert the opposite at startup and log loudly if
    the posture is wrong. Returns the observed posture (or None if it can't be
    read); never raises.
    """
    try:
        async with engine.connect() as conn:
            row = (
                await conn.execute(
                    text(
                        "SELECT current_user AS role, "
                        "(SELECT rolbypassrls FROM pg_roles WHERE rolname = current_user) AS bypassrls, "
                        "(SELECT rolsuper FROM pg_roles WHERE rolname = current_user) AS super"
                    )
                )
            ).mappings().first()
    except Exception as exc:  # noqa: BLE001
        logger.error("verify_app_role_not_bypassing: could not read runtime role posture: %s", exc)
        return None

    posture = dict(row) if row else None
    if posture is None:
        return None
    if posture.get("bypassrls") or posture.get("super"):
        logger.warning(
            "⚠️  RLS NOT ENFORCED at runtime: connected as %r (rolbypassrls=%s, "
            "rolsuper=%s). Point DATABASE_URL at a NOBYPASSRLS/NOSUPERUSER app role "
            "IN ROLE brigade_app so org isolation is real.",
            posture.get("role"), posture.get("bypassrls"), posture.get("super"),
        )
    else:
        logger.info(
            "✅ Runtime DB role %r is subject to RLS (rolbypassrls=false, rolsuper=false).",
            posture.get("role"),
        )
    return posture


async def verify_owner_role_bypasses_rls() -> dict | None:
    """M1 self-check: confirm the OWNER/``MIGRATION_DATABASE_URL`` role BYPASSES RLS.

    Symmetric to ``verify_app_role_not_bypassing`` (which asserts the APP role IS
    subject to RLS). Trusted CROSS-TENANT system work runs on the owner engine and
    MUST see rows across every org: the scheduler (``scheduler.reload_all``
    enumerating all orgs' enabled jobs) and the BR-1.1 identity remap
    (``run_identity_remap``). If that role is itself subject to RLS — neither
    ``rolsuper`` nor ``rolbypassrls`` — then with no ``app.current_org_id`` bound,
    FORCE ROW LEVEL SECURITY hides EVERY row and those subsystems SILENTLY process
    zero rows (no error, no jobs loaded, no rows remapped). So we assert the
    opposite at startup and log LOUDLY when the posture is wrong. Returns the
    observed posture (or None if it can't be read); never raises.

    In single-role dev (``migration_engine is engine``) this reads the same
    (usually superuser) role and passes — the mirror of the app-role check's
    "RLS present but bypassed" note.
    """
    try:
        async with migration_engine.connect() as conn:
            row = (
                await conn.execute(
                    text(
                        "SELECT current_user AS role, "
                        "(SELECT rolbypassrls FROM pg_roles WHERE rolname = current_user) AS bypassrls, "
                        "(SELECT rolsuper FROM pg_roles WHERE rolname = current_user) AS super"
                    )
                )
            ).mappings().first()
    except Exception as exc:  # noqa: BLE001
        logger.error("verify_owner_role_bypasses_rls: could not read owner role posture: %s", exc)
        return None

    posture = dict(row) if row else None
    if posture is None:
        return None
    if posture.get("super") or posture.get("bypassrls"):
        logger.info(
            "✅ Owner/migration DB role %r BYPASSES RLS (rolsuper=%s, rolbypassrls=%s) — "
            "scheduler + identity remap can enumerate across every org.",
            posture.get("role"), posture.get("super"), posture.get("bypassrls"),
        )
    else:
        logger.warning(
            "⚠️  OWNER ROLE IS SUBJECT TO RLS: MIGRATION_DATABASE_URL connects as %r "
            "(rolsuper=false, rolbypassrls=false). With no app.current_org_id bound, "
            "FORCE ROW LEVEL SECURITY will HIDE EVERY ROW from cross-tenant system work "
            "— the scheduler (scheduler.reload_all) will load ZERO jobs and the BR-1.1 "
            "identity remap (run_identity_remap) will relabel ZERO rows, both SILENTLY. "
            "Point MIGRATION_DATABASE_URL at a SUPERUSER or BYPASSRLS owner role.",
            posture.get("role"),
        )
    return posture


async def init_db():
    """Create all tables (skips existing ones), then apply additive migrations.

    ``create_all`` only creates missing TABLES; it never adds columns to an
    existing table. ``run_additive_migrations`` closes that gap idempotently for
    deployed DBs (and is a harmless no-op on a fresh install where create_all
    already built the full table)."""
    async with migration_engine.begin() as conn:
        await conn.execute(text(
            "CREATE OR REPLACE FUNCTION current_org_id() RETURNS uuid "
            "LANGUAGE sql STABLE AS $$ "
            "SELECT nullif(current_setting('app.current_org_id', true), '')::uuid "
            "$$"
        ))
        # checkfirst=True prevents errors when indexes/tables already exist
        await conn.run_sync(lambda sync_conn: Base.metadata.create_all(sync_conn, checkfirst=True))
    from app.db.migrations import run_additive_migrations, run_identity_remap
    # All DDL/migrations run on the OWNER/admin engine. The org-tenancy migration
    # (20260626_01) creates the brigade_app parent role, ENABLEs+FORCEs RLS, and
    # GRANTs the app role — none of which the RLS-subject runtime role could do.
    await run_additive_migrations(migration_engine)
    # BR-1.1: one-shot batch remap of rows written under a raw Keycloak sub to the
    # canonical local users.id (must run AFTER users.keycloak_id exists). It
    # relabels rows across every org, so it also runs on the owner engine — the
    # app role's RLS would otherwise scope it to a single org.
    await run_identity_remap(migration_engine)
    # BR-1.3: now that brigade_app + its grants exist, provision the LOGIN app
    # role that DATABASE_URL points at (owner engine), then confirm the runtime
    # engine is genuinely subject to RLS. Both are best-effort + loud.
    await provision_app_role()
    await verify_app_role_not_bypassing()
    # M1: symmetric assertion that the OWNER/migration role BYPASSES RLS, so the
    # scheduler + identity remap (which run RLS-exempt, GUC-unbound) don't silently
    # see zero rows. Best-effort + loud, mirroring the app-role verify above.
    await verify_owner_role_bypasses_rls()
    logger.info("Database tables created/verified")


async def close_db():
    """Close the database engine."""
    await engine.dispose()
    if migration_engine is not engine:
        await migration_engine.dispose()
    logger.info("Database engine closed")
