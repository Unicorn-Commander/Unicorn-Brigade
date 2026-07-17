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
# per DB. Postgres dialect (Brigade runs on Postgres/asyncpg). ``sql`` may be a
# string of semicolon-separated simple statements, or an explicit list when a
# statement contains internal semicolons (functions/policies).
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
    (
        "20260624_02_agent_affiliation",
        "Agent affiliation classification (employee/contractor/third_party/frontier)",
        # Nullable so an unset value is honest; backfill derives a best-guess from
        # the agent's model (local/uc -> we own it = employee; frontier APIs ->
        # frontier). The backfill only fills NULLs, so an operator's later manual
        # reclassification (contractor/third_party, or flipping a specific agent)
        # is never clobbered on re-deploy.
        """
        ALTER TABLE agents ADD COLUMN IF NOT EXISTS affiliation varchar(32);
        UPDATE agents SET affiliation = CASE
            WHEN model LIKE 'anthropic/%' OR model LIKE 'claude%'
              OR model LIKE 'openai/%' OR model LIKE 'gpt%'
              OR model LIKE 'google/%' OR model LIKE 'gemini%' THEN 'frontier'
            ELSE 'employee'
        END WHERE affiliation IS NULL;
        """,
    ),
    (
        "20260624_03_tool_catalog",
        "Tool cost/permission catalog + best-guess seed (operator corrects in place)",
        # cost_tier: free | paid | subscription. permission_level: 1 (basic util/
        # read) .. 5 (privileged: shell, delegate). external: calls outside our
        # infra. Seed is a BEST-GUESS starting point -- ON CONFLICT DO NOTHING so
        # operator edits to the table survive every re-deploy.
        """
        CREATE TABLE IF NOT EXISTS tool_catalog (
            name varchar(100) PRIMARY KEY,
            display_name varchar(150),
            description text,
            cost_tier varchar(20) NOT NULL DEFAULT 'free',
            permission_level integer NOT NULL DEFAULT 1,
            provider varchar(50),
            external boolean NOT NULL DEFAULT false,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now()
        );
        INSERT INTO tool_catalog (name, cost_tier, permission_level, provider, external) VALUES
            ('add_task_comment','free',2,'project_ops',false),
            ('agentic_rag','free',1,'knowledge',false),
            ('analytics_sql','free',4,'internal',false),
            ('calculator','free',1,'internal',false),
            ('canvas_create','free',2,'canvas',false),
            ('canvas_edit','free',2,'canvas',false),
            ('canvas_rewrite','free',2,'canvas',false),
            ('cdr_deep_research','paid',4,'center_deep',false),
            ('cdr_quick_answer','paid',1,'center_deep',false),
            ('cdr_search','paid',1,'center_deep',false),
            ('create_project','free',3,'project_ops',false),
            ('create_task','free',2,'project_ops',false),
            ('database','free',4,'internal',false),
            ('datetime','free',1,'internal',false),
            ('delegate_to_agent','free',5,'orchestration',false),
            ('doc_generate','free',2,'internal',false),
            ('email','subscription',3,'mail',true),
            ('file','free',2,'internal',false),
            ('find_connections','free',1,'knowledge',false),
            ('find_evidence_gaps','free',2,'legal',false),
            ('generate_pdf','free',2,'internal',false),
            ('get_case_summary','free',1,'legal',false),
            ('get_document_content','free',1,'docs',false),
            ('get_entity','free',1,'knowledge',false),
            ('get_project','free',1,'project_ops',false),
            ('get_recent_activity','free',1,'project_ops',false),
            ('get_relationships','free',1,'knowledge',false),
            ('get_strategy','free',1,'legal',false),
            ('get_timeline','free',1,'knowledge',false),
            ('glitter_add_allergy','free',4,'glitter',false),
            ('glitter_add_appointment','free',4,'glitter',false),
            ('glitter_add_care_plan_item','free',4,'glitter',false),
            ('glitter_add_condition','free',4,'glitter',false),
            ('glitter_add_medication','free',4,'glitter',false),
            ('glitter_add_vital','free',4,'glitter',false),
            ('glitter_ask','free',3,'glitter',false),
            ('glitter_get_health_summary','free',3,'glitter',false),
            ('glitter_get_timeline','free',3,'glitter',false),
            ('glitter_get_visit_summary','free',3,'glitter',false),
            ('glitter_ingest_text','free',4,'glitter',false),
            ('glitter_list_allergies','free',3,'glitter',false),
            ('glitter_list_conditions','free',3,'glitter',false),
            ('glitter_list_labs','free',3,'glitter',false),
            ('glitter_list_medications','free',3,'glitter',false),
            ('glitter_list_models','free',1,'glitter',false),
            ('glitter_list_vitals','free',3,'glitter',false),
            ('http_request','free',4,'internal',true),
            ('json','free',1,'internal',false),
            ('kg_query','free',1,'knowledge',false),
            ('knowledge_graph','free',1,'knowledge',false),
            ('knowledge_query','free',1,'knowledge',false),
            ('knowledge_store','free',3,'knowledge',false),
            ('list_entities','free',1,'knowledge',false),
            ('list_my_projects','free',1,'project_ops',false),
            ('list_my_tasks','free',1,'project_ops',false),
            ('list_project_documents','free',1,'docs',false),
            ('memory','free',1,'internal',false),
            ('notify','free',2,'internal',false),
            ('pdf_extract','free',2,'internal',false),
            ('search_entities','free',1,'knowledge',false),
            ('search_evidence','free',1,'legal',false),
            ('search_knowledge','free',1,'knowledge',false),
            ('search_projects','free',1,'project_ops',false),
            ('shell','free',5,'system',false),
            ('update_billing_fields','free',4,'project_ops',false),
            ('update_project_status','free',3,'project_ops',false),
            ('update_task_status','free',2,'project_ops',false),
            ('upload_document','free',2,'docs',false),
            ('web_search','paid',1,'web',true)
        ON CONFLICT (name) DO NOTHING;
        """,
    ),
    (
        "20260705_01_agent_avatar_url",
        "agents.avatar_url for image avatars (emoji `avatar` stays the fallback)",
        """
        ALTER TABLE agents ADD COLUMN IF NOT EXISTS avatar_url TEXT;
        """,
    ),
    (
        "20260716_01_user_keycloak_id",
        "BR-1.1: users.keycloak_id — canonical Keycloak sub binding (unique-nullable + index)",
        # Additive + idempotent. Nullable so legacy/native rows stay valid until
        # they learn their sub on first SSO login; UNIQUE so two rows can never
        # claim the same sub (Postgres allows many NULLs under a unique index).
        # The DATA remap (relabeling rows written under a raw sub to the local
        # users.id) is NOT here — it is procedural and lives in
        # remap_forked_keycloak_rows / run_identity_remap below, plus the lazy
        # per-login remap in app/auth/middleware.resolve_canonical_user_id.
        """
        ALTER TABLE users ADD COLUMN IF NOT EXISTS keycloak_id varchar(255);
        CREATE UNIQUE INDEX IF NOT EXISTS ix_users_keycloak_id ON users (keycloak_id);
        """,
    ),
    (
        "20260626_01_org_tenancy_rls",
        "Organization tenancy substrate, org_id backfill, and RLS policies",
        [
            """
            CREATE OR REPLACE FUNCTION current_org_id() RETURNS uuid
            LANGUAGE sql STABLE
            AS $$ SELECT nullif(current_setting('app.current_org_id', true), '')::uuid $$
            """,
            """
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'brigade_app') THEN
                    CREATE ROLE brigade_app NOLOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
                ELSE
                    ALTER ROLE brigade_app NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
                END IF;
            END $$;
            """,
            """
            CREATE TABLE IF NOT EXISTS organizations (
                id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
                name varchar(255) NOT NULL,
                slug varchar(255) NOT NULL UNIQUE,
                plan_tier varchar(50) NOT NULL DEFAULT 'free',
                api_calls_limit integer NOT NULL DEFAULT 0,
                metadata json DEFAULT '{}'::json,
                created_at timestamptz NOT NULL DEFAULT now(),
                updated_at timestamptz NOT NULL DEFAULT now()
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS org_memberships (
                id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
                org_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
                user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                role varchar(50) NOT NULL DEFAULT 'owner',
                created_at timestamptz NOT NULL DEFAULT now(),
                CONSTRAINT uq_org_memberships_org_user UNIQUE (org_id, user_id)
            )
            """,
            "CREATE INDEX IF NOT EXISTS ix_org_memberships_user_id ON org_memberships(user_id)",
            "CREATE INDEX IF NOT EXISTS ix_org_memberships_org_id ON org_memberships(org_id)",
            """
            INSERT INTO organizations (id, name, slug, plan_tier, api_calls_limit, metadata)
            VALUES (gen_random_uuid(), 'Early Access', 'early-access', 'free', 0, '{"bootstrap": true}'::json)
            ON CONFLICT (slug) DO NOTHING
            """,
            """
            INSERT INTO org_memberships (id, org_id, user_id, role)
            SELECT gen_random_uuid(), o.id, u.id, 'owner'
            FROM organizations o
            CROSS JOIN users u
            WHERE o.slug = 'early-access'
            ON CONFLICT (org_id, user_id) DO NOTHING
            """,
            "ALTER TABLE agents ADD COLUMN IF NOT EXISTS org_id uuid",
            "ALTER TABLE conversations ADD COLUMN IF NOT EXISTS org_id uuid",
            "ALTER TABLE messages ADD COLUMN IF NOT EXISTS org_id uuid",
            "ALTER TABLE builder_sessions ADD COLUMN IF NOT EXISTS org_id uuid",
            "ALTER TABLE tool_executions ADD COLUMN IF NOT EXISTS org_id uuid",
            "ALTER TABLE speaker_profiles ADD COLUMN IF NOT EXISTS org_id uuid",
            "ALTER TABLE code_attributions ADD COLUMN IF NOT EXISTS org_id uuid",
            "ALTER TABLE scheduled_runs ADD COLUMN IF NOT EXISTS org_id uuid",
            "ALTER TABLE scheduled_run_history ADD COLUMN IF NOT EXISTS org_id uuid",
            """
            UPDATE conversations
            SET org_id = (SELECT id FROM organizations WHERE slug = 'early-access')
            WHERE org_id IS NULL
            """,
            """
            UPDATE messages m
            SET org_id = c.org_id
            FROM conversations c
            WHERE m.conversation_id = c.id AND m.org_id IS NULL
            """,
            """
            UPDATE builder_sessions
            SET org_id = (SELECT id FROM organizations WHERE slug = 'early-access')
            WHERE org_id IS NULL
            """,
            """
            UPDATE tool_executions te
            SET org_id = COALESCE(
                (SELECT c.org_id FROM conversations c WHERE c.id = te.conversation_id),
                (SELECT id FROM organizations WHERE slug = 'early-access')
            )
            WHERE te.org_id IS NULL
            """,
            """
            UPDATE speaker_profiles sp
            SET org_id = COALESCE(
                (SELECT om.org_id FROM org_memberships om WHERE om.user_id = sp.user_id LIMIT 1),
                (SELECT id FROM organizations WHERE slug = 'early-access')
            )
            WHERE sp.org_id IS NULL
            """,
            """
            UPDATE code_attributions
            SET org_id = (SELECT id FROM organizations WHERE slug = 'early-access')
            WHERE org_id IS NULL
            """,
            """
            UPDATE scheduled_runs sr
            SET org_id = COALESCE(
                (SELECT om.org_id FROM org_memberships om WHERE om.user_id = sr.owner_user_id LIMIT 1),
                (SELECT id FROM organizations WHERE slug = 'early-access')
            )
            WHERE sr.org_id IS NULL
            """,
            """
            UPDATE scheduled_run_history h
            SET org_id = COALESCE(
                (SELECT sr.org_id FROM scheduled_runs sr WHERE sr.id = h.scheduled_run_id),
                (SELECT id FROM organizations WHERE slug = 'early-access')
            )
            WHERE h.org_id IS NULL
            """,
            "ALTER TABLE conversations ALTER COLUMN org_id SET DEFAULT current_org_id()",
            "ALTER TABLE messages ALTER COLUMN org_id SET DEFAULT current_org_id()",
            "ALTER TABLE builder_sessions ALTER COLUMN org_id SET DEFAULT current_org_id()",
            "ALTER TABLE tool_executions ALTER COLUMN org_id SET DEFAULT current_org_id()",
            "ALTER TABLE speaker_profiles ALTER COLUMN org_id SET DEFAULT current_org_id()",
            "ALTER TABLE code_attributions ALTER COLUMN org_id SET DEFAULT current_org_id()",
            "ALTER TABLE scheduled_runs ALTER COLUMN org_id SET DEFAULT current_org_id()",
            "ALTER TABLE scheduled_run_history ALTER COLUMN org_id SET DEFAULT current_org_id()",
            "ALTER TABLE conversations ALTER COLUMN org_id SET NOT NULL",
            "ALTER TABLE messages ALTER COLUMN org_id SET NOT NULL",
            "ALTER TABLE builder_sessions ALTER COLUMN org_id SET NOT NULL",
            "ALTER TABLE tool_executions ALTER COLUMN org_id SET NOT NULL",
            "ALTER TABLE speaker_profiles ALTER COLUMN org_id SET NOT NULL",
            "ALTER TABLE code_attributions ALTER COLUMN org_id SET NOT NULL",
            "ALTER TABLE scheduled_runs ALTER COLUMN org_id SET NOT NULL",
            "ALTER TABLE scheduled_run_history ALTER COLUMN org_id SET NOT NULL",
            "CREATE INDEX IF NOT EXISTS ix_agents_org_id ON agents(org_id)",
            "CREATE INDEX IF NOT EXISTS ix_conversations_org_id ON conversations(org_id)",
            "CREATE INDEX IF NOT EXISTS ix_messages_org_id ON messages(org_id)",
            "CREATE INDEX IF NOT EXISTS ix_builder_sessions_org_id ON builder_sessions(org_id)",
            "CREATE INDEX IF NOT EXISTS ix_tool_executions_org_id ON tool_executions(org_id)",
            "CREATE INDEX IF NOT EXISTS ix_speaker_profiles_org_id ON speaker_profiles(org_id)",
            "CREATE INDEX IF NOT EXISTS ix_code_attributions_org_id ON code_attributions(org_id)",
            "CREATE INDEX IF NOT EXISTS ix_scheduled_runs_org_id ON scheduled_runs(org_id)",
            "CREATE INDEX IF NOT EXISTS ix_scheduled_run_history_org_id ON scheduled_run_history(org_id)",
            """
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_conversations_org_id_organizations') THEN
                    ALTER TABLE conversations ADD CONSTRAINT fk_conversations_org_id_organizations FOREIGN KEY (org_id) REFERENCES organizations(id) ON DELETE CASCADE;
                END IF;
                IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_messages_org_id_organizations') THEN
                    ALTER TABLE messages ADD CONSTRAINT fk_messages_org_id_organizations FOREIGN KEY (org_id) REFERENCES organizations(id) ON DELETE CASCADE;
                END IF;
                IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_builder_sessions_org_id_organizations') THEN
                    ALTER TABLE builder_sessions ADD CONSTRAINT fk_builder_sessions_org_id_organizations FOREIGN KEY (org_id) REFERENCES organizations(id) ON DELETE CASCADE;
                END IF;
                IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_tool_executions_org_id_organizations') THEN
                    ALTER TABLE tool_executions ADD CONSTRAINT fk_tool_executions_org_id_organizations FOREIGN KEY (org_id) REFERENCES organizations(id) ON DELETE CASCADE;
                END IF;
                IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_speaker_profiles_org_id_organizations') THEN
                    ALTER TABLE speaker_profiles ADD CONSTRAINT fk_speaker_profiles_org_id_organizations FOREIGN KEY (org_id) REFERENCES organizations(id) ON DELETE CASCADE;
                END IF;
                IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_code_attributions_org_id_organizations') THEN
                    ALTER TABLE code_attributions ADD CONSTRAINT fk_code_attributions_org_id_organizations FOREIGN KEY (org_id) REFERENCES organizations(id) ON DELETE CASCADE;
                END IF;
                IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_scheduled_runs_org_id_organizations') THEN
                    ALTER TABLE scheduled_runs ADD CONSTRAINT fk_scheduled_runs_org_id_organizations FOREIGN KEY (org_id) REFERENCES organizations(id) ON DELETE CASCADE;
                END IF;
                IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_scheduled_run_history_org_id_organizations') THEN
                    ALTER TABLE scheduled_run_history ADD CONSTRAINT fk_scheduled_run_history_org_id_organizations FOREIGN KEY (org_id) REFERENCES organizations(id) ON DELETE CASCADE;
                END IF;
                IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_agents_org_id_organizations') THEN
                    ALTER TABLE agents ADD CONSTRAINT fk_agents_org_id_organizations FOREIGN KEY (org_id) REFERENCES organizations(id) ON DELETE CASCADE;
                END IF;
            END $$;
            """,
            "ALTER TABLE conversations ENABLE ROW LEVEL SECURITY",
            "ALTER TABLE messages ENABLE ROW LEVEL SECURITY",
            "ALTER TABLE builder_sessions ENABLE ROW LEVEL SECURITY",
            "ALTER TABLE tool_executions ENABLE ROW LEVEL SECURITY",
            "ALTER TABLE speaker_profiles ENABLE ROW LEVEL SECURITY",
            "ALTER TABLE code_attributions ENABLE ROW LEVEL SECURITY",
            "ALTER TABLE scheduled_runs ENABLE ROW LEVEL SECURITY",
            "ALTER TABLE scheduled_run_history ENABLE ROW LEVEL SECURITY",
            "ALTER TABLE conversations FORCE ROW LEVEL SECURITY",
            "ALTER TABLE messages FORCE ROW LEVEL SECURITY",
            "ALTER TABLE builder_sessions FORCE ROW LEVEL SECURITY",
            "ALTER TABLE tool_executions FORCE ROW LEVEL SECURITY",
            "ALTER TABLE speaker_profiles FORCE ROW LEVEL SECURITY",
            "ALTER TABLE code_attributions FORCE ROW LEVEL SECURITY",
            "ALTER TABLE scheduled_runs FORCE ROW LEVEL SECURITY",
            "ALTER TABLE scheduled_run_history FORCE ROW LEVEL SECURITY",
            "DROP POLICY IF EXISTS conversations_org_isolation ON conversations",
            "CREATE POLICY conversations_org_isolation ON conversations USING (org_id = current_org_id()) WITH CHECK (org_id = current_org_id())",
            "DROP POLICY IF EXISTS messages_org_isolation ON messages",
            """
            CREATE POLICY messages_org_isolation ON messages
            USING (org_id = current_org_id())
            WITH CHECK (
                org_id = current_org_id()
                AND EXISTS (
                    SELECT 1 FROM conversations c
                    WHERE c.id = messages.conversation_id
                    AND c.org_id = current_org_id()
                )
            )
            """,
            "DROP POLICY IF EXISTS builder_sessions_org_isolation ON builder_sessions",
            "CREATE POLICY builder_sessions_org_isolation ON builder_sessions USING (org_id = current_org_id()) WITH CHECK (org_id = current_org_id())",
            "DROP POLICY IF EXISTS tool_executions_org_isolation ON tool_executions",
            """
            CREATE POLICY tool_executions_org_isolation ON tool_executions
            USING (org_id = current_org_id())
            WITH CHECK (
                org_id = current_org_id()
                AND (
                    conversation_id IS NULL
                    OR EXISTS (
                        SELECT 1 FROM conversations c
                        WHERE c.id = tool_executions.conversation_id
                        AND c.org_id = current_org_id()
                    )
                )
            )
            """,
            "DROP POLICY IF EXISTS speaker_profiles_org_isolation ON speaker_profiles",
            "CREATE POLICY speaker_profiles_org_isolation ON speaker_profiles USING (org_id = current_org_id()) WITH CHECK (org_id = current_org_id())",
            "DROP POLICY IF EXISTS code_attributions_org_isolation ON code_attributions",
            "CREATE POLICY code_attributions_org_isolation ON code_attributions USING (org_id = current_org_id()) WITH CHECK (org_id = current_org_id())",
            "DROP POLICY IF EXISTS scheduled_runs_org_isolation ON scheduled_runs",
            "CREATE POLICY scheduled_runs_org_isolation ON scheduled_runs USING (org_id = current_org_id()) WITH CHECK (org_id = current_org_id())",
            "DROP POLICY IF EXISTS scheduled_run_history_org_isolation ON scheduled_run_history",
            """
            CREATE POLICY scheduled_run_history_org_isolation ON scheduled_run_history
            USING (org_id = current_org_id())
            WITH CHECK (
                org_id = current_org_id()
                AND EXISTS (
                    SELECT 1 FROM scheduled_runs sr
                    WHERE sr.id = scheduled_run_history.scheduled_run_id
                    AND sr.org_id = current_org_id()
                )
            )
            """,
            "GRANT USAGE ON SCHEMA public TO brigade_app",
            "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO brigade_app",
            "GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO brigade_app",
            "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO brigade_app",
            "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO brigade_app",
        ],
    ),
]

# Recorded in schema_migrations so the one-shot identity remap runs once per DB.
_IDENTITY_REMAP_VERSION = "20260716_02_identity_remap_backfill"

# BR-1.1 identity remap. Portable SQL (correlated subquery form) so it runs
# unchanged on Postgres (prod) and SQLite (the throwaway test DB). Each statement
# relabels rows whose ``user_id`` equals a *populated* ``keycloak_id`` to that
# user's canonical local ``users.id``.
#
# What this CAN remap right now: only rows whose user_id matches a keycloak_id
# that is already populated on some users row. Because we have NO stored
# sub->email map, a legacy email-keyed row does not know its own sub until a
# human logs in via Keycloak (which stamps keycloak_id and lazily remaps that
# user's rows in the middleware). So at first deploy — before anyone has logged
# in post-migration — this one-shot matches ~nothing; it is a belt-and-suspenders
# batch pass that catches any keycloak_ids populated out-of-band (e.g. an
# operator backfill). The durable, per-human remap happens lazily on next login.
#
# OUT OF SCOPE for this (or any) SQL remap: per-user Graphiti/FalkorDB agent
# memory is keyed by a group_id of ``{user_id}__{agent}`` (the raw sub, pre-
# cutover) -- a graph namespace, not a relational row this migration can UPDATE.
# Rather than move graph nodes, the memory RETRIEVAL path dual-reads the legacy
# ``{sub}__{agent}`` namespace via AuthUser.keycloak_id while writes stay
# canonical (app/memory/graphiti_manager._read_group_ids). No data movement, no
# FalkorDB surgery, so a cutover user keeps old memory without a backfill.
#
# Edge cases handled by the WHERE clause:
#   * user_id NULL / 'anonymous'      -> never equals a uuid keycloak_id, skipped
#   * downstream pass-through ids     -> not a keycloak_id, skipped
#   * sub already == users.id         -> excluded by ``keycloak_id <> CAST(id AS text)``
#                                        (portable: varchar<>uuid has NO operator on
#                                        Postgres — this cast was a BR-1.1 bug caught
#                                        by the BR-1.2 real-Postgres RLS proof; CAST
#                                        keeps SQLite green too), no churn
#   * already-canonical rows          -> user_id not in the keycloak_id set, skipped
_REMAP_STATEMENTS = [
    """
    UPDATE conversations
       SET user_id = (SELECT u.id FROM users u WHERE u.keycloak_id = conversations.user_id)
     WHERE user_id IN (
        SELECT keycloak_id FROM users
         WHERE keycloak_id IS NOT NULL AND keycloak_id <> CAST(id AS text)
     )
    """,
    """
    UPDATE builder_sessions
       SET user_id = (SELECT u.id FROM users u WHERE u.keycloak_id = builder_sessions.user_id)
     WHERE user_id IN (
        SELECT keycloak_id FROM users
         WHERE keycloak_id IS NOT NULL AND keycloak_id <> CAST(id AS text)
     )
    """,
]


async def remap_forked_keycloak_rows(conn) -> None:
    """Run the BR-1.1 batch identity remap on the given async connection/session.

    Portable + idempotent (a second run matches zero rows). Extracted as a
    standalone helper so the throwaway-DB test drives the exact SQL prod runs.
    Keep the table list in sync with
    app/auth/middleware._KEYCLOAK_REMAP_TABLES.
    """
    for stmt in _REMAP_STATEMENTS:
        await conn.execute(text(stmt))


async def run_identity_remap(engine) -> None:
    """One-shot BR-1.1 identity remap, recorded in schema_migrations so it runs
    once per DB. Best-effort + loud, like run_additive_migrations. Idempotent, so
    a re-run (were the guard row missing) is harmless."""
    try:
        async with engine.begin() as conn:
            await conn.execute(text(
                "CREATE TABLE IF NOT EXISTS schema_migrations ("
                "version varchar(255) PRIMARY KEY, "
                "applied_at timestamptz NOT NULL DEFAULT now())"
            ))
            rows = await conn.execute(text("SELECT version FROM schema_migrations"))
            applied = {r[0] for r in rows}
        if _IDENTITY_REMAP_VERSION in applied:
            return
        async with engine.begin() as conn:
            await remap_forked_keycloak_rows(conn)
            await conn.execute(
                text("INSERT INTO schema_migrations (version) VALUES (:v) "
                     "ON CONFLICT (version) DO NOTHING"),
                {"v": _IDENTITY_REMAP_VERSION},
            )
        logger.info(f"Applied identity remap {_IDENTITY_REMAP_VERSION}")
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Identity remap {_IDENTITY_REMAP_VERSION} FAILED: {exc}")


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
        if isinstance(sql, str):
            statements = [s.strip() for s in sql.split(";") if s.strip()]
        else:
            statements = [s.strip() for s in sql if s.strip()]
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
