"""Minimal additive-only schema migrations for Brigade.

Brigade builds its schema with SQLAlchemy ``create_all`` (which only ever creates
MISSING tables) and has no Alembic. ``create_all`` never ALTERs an existing
table, so adding a column to a table that already exists in a deployed DB (the
classic prod gap) silently does nothing — and the next ``SELECT`` that
enumerates the new column 500s. This runner closes that gap: after
``create_all`` it applies a versioned list of **additive, idempotent** DDL
statements and records what ran in ``schema_migrations`` so each applies once per
database.

RULES for entries (enforced by convention, not code):
  * Append-only. Never edit or delete a shipped entry — add a new one.
  * Every statement must be additive + idempotent: ``ADD COLUMN IF NOT EXISTS``,
    ``CREATE INDEX IF NOT EXISTS``, ``CREATE TABLE IF NOT EXISTS``. Never
    destructive, never a table rewrite. (Idempotent so re-running — e.g. after a
    DB that already got the column via ``create_all`` on a fresh install, or a
    manual ALTER — is a safe no-op.)
"""

import logging

from sqlalchemy import text

logger = logging.getLogger(__name__)

# (version, description, sql). Append-only. Statements run in order, each once
# per DB. Postgres dialect (Brigade runs on Postgres/asyncpg).
MIGRATIONS = [
    (
        "20260624_01_agent_value_billing",
        "Per-agent value-billing columns on agents",
        """
        ALTER TABLE agents ADD COLUMN IF NOT EXISTS billing_tier varchar(50) NOT NULL DEFAULT 'standard';
        ALTER TABLE agents ADD COLUMN IF NOT EXISTS rate_multiplier double precision NOT NULL DEFAULT 1.0;
        ALTER TABLE agents ADD COLUMN IF NOT EXISTS base_price_per_call double precision;
        """,
    ),
]


async def run_additive_migrations(engine) -> None:
    """Apply any unapplied additive migrations. Best-effort + loud: a failure is
    logged (so it's visible) but does not crash startup — and because every
    statement is ``IF NOT EXISTS``, a partial/again run is harmless."""
    try:
        async with engine.begin() as conn:
            await conn.execute(text(
                "CREATE TABLE IF NOT EXISTS schema_migrations ("
                "version varchar(255) PRIMARY KEY, "
                "applied_at timestamptz NOT NULL DEFAULT now())"
            ))
            rows = await conn.execute(text("SELECT version FROM schema_migrations"))
            applied = {r[0] for r in rows}
    except Exception as exc:  # noqa: BLE001
        logger.error(f"schema_migrations bootstrap failed (skipping migrations): {exc}")
        return

    for version, desc, sql in MIGRATIONS:
        if version in applied:
            continue
        statements = [s.strip() for s in sql.split(";") if s.strip()]
        try:
            # One transaction per migration so a failure can't half-apply others.
            async with engine.begin() as conn:
                for stmt in statements:
                    await conn.execute(text(stmt))
                await conn.execute(
                    text("INSERT INTO schema_migrations (version) VALUES (:v) "
                         "ON CONFLICT (version) DO NOTHING"),
                    {"v": version},
                )
            logger.info(f"Applied schema migration {version}: {desc}")
        except Exception as exc:  # noqa: BLE001
            logger.error(f"Schema migration {version} FAILED ({desc}): {exc}")
