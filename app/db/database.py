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
import os
import re
import logging
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text
from sqlalchemy.engine import make_url

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


async def get_session() -> AsyncSession:
    """Get an async database session."""
    async with async_session() as session:
        try:
            yield session
        finally:
            try:
                await session.execute(text("SELECT set_config('app.current_org_id', '', false)"))
                await session.rollback()
            except Exception:
                logger.debug("Failed to clear tenant context on DB session", exc_info=True)


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
    logger.info("Database tables created/verified")


async def close_db():
    """Close the database engine."""
    await engine.dispose()
    if migration_engine is not engine:
        await migration_engine.dispose()
    logger.info("Database engine closed")
