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
        "20260729_01_core_agent_avatar_urls",
        "Populate verified Brigade and Brand-Ops primary agent portraits",
        # Brand-Ops owns the artwork masters below; Brigade owns their runtime
        # aliases and serves portable same-origin copies.  Keep this explanation
        # outside the SQL string: asyncpg can return a null statement status for
        # a semicolon-split statement beginning with a line comment.
        """
        UPDATE agents
        SET avatar_url = '/avatars/' || id || '.webp'
        WHERE id IN (
            'the-general',
            'gunny',
            'sgt-cipher',
            'cpt-fullstack',
            'maj-devops',
            'col-finance',
            'lt-taxstrat',
            'judge-advocate',
            'doc-medresearch',
            'detective-holmes',
            'prof-datasci',
            'support-agent',
            'code-reviewer',
            'sql-analyst',
            'sgt-scribe',
            'maj-leadgen',
            'lt-docanalyst',
            'iris'
        )
          AND (avatar_url IS NULL OR btrim(avatar_url) = '');

        UPDATE agents
        SET avatar_url = '/avatars/' || id || '.webp'
        WHERE (
            id = 'perry'
            AND (
                avatar_url IS NULL
                OR btrim(avatar_url) = ''
                OR avatar_url = '/api/brands/magic-unicorn/agents/perrywinkle-spector/avatar'
                OR avatar_url = 'https://brand-ops.magicunicorn.dev/api/brands/magic-unicorn/agents/perrywinkle-spector/avatar'
            )
        ) OR (
            id = 'prudence'
            AND (
                avatar_url IS NULL
                OR btrim(avatar_url) = ''
                OR avatar_url = '/api/brands/magic-unicorn/agents/prudence-finch/avatar'
                OR avatar_url = 'https://brand-ops.magicunicorn.dev/api/brands/magic-unicorn/agents/prudence-finch/avatar'
            )
        ) OR (
            id = 'cpl.-colophon'
            AND (
                avatar_url IS NULL
                OR btrim(avatar_url) = ''
                OR avatar_url = '/api/brands/magic-unicorn/agents/cpl-colophon/avatar'
                OR avatar_url = 'https://brand-ops.magicunicorn.dev/api/brands/magic-unicorn/agents/cpl-colophon/avatar'
            )
        );
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
            # H1 / BR-2.4 note: 'early-access' is the shared bootstrap org. Existing
            # users are backfilled into it (CROSS JOIN below) and, at the time this
            # migration shipped, every keyless identity (service/agent/admin keys)
            # also collapsed onto it at request time (middleware._default_org_id).
            # UPDATE (BR-2.4, migration 20260718_01_api_key_org_binding): H1 is now
            # CLOSED — api_keys.org_id gives each service/agent key its own org
            # binding, so multi-customer key issuance is isolated and safe. This org
            # is now only the FALLBACK for the master-admin key and legacy NULL-org
            # keys (which are backfilled here).
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
    (
        "20260716_02_tenancy_extend",
        "BR-1.4: agents RLS with a SHARED-CATALOG policy (NULL org_id = global roster)",
        # BR-1.2 (20260626_01) deferred agents: it added agents.org_id (nullable),
        # ix_agents_org_id, and fk_agents_org_id_organizations, but left agents
        # WITHOUT RLS so the seed/global roster kept working during the rollout.
        # BR-1.4 turns RLS on for agents with a twist the 8 data tables don't have:
        # a NULL org_id is a GLOBAL/shared agent readable by EVERY org (the seed
        # roster, Gunny, The General, ...), while an org-tagged agent is visible
        # only to its own org.
        #
        #   USING (org_id IS NULL OR org_id = current_org_id())
        #     -> reads: everyone sees shared agents + their own org's agents.
        #        An UNBOUND session (empty GUC, e.g. public A2A discovery) sees
        #        ONLY shared agents — never a tenant's private roster. That makes
        #        the intentionally-public federation surfaces safe by construction.
        #   WITH CHECK (org_id = current_org_id())
        #     -> writes: a tenant may only create/modify agents tagged with its
        #        OWN org. It can never write a NULL (shared) row nor another org's
        #        row, because current_org_id() is its own non-null org.
        #
        # Consequence: the RLS-subject app role CANNOT create a shared (NULL-org)
        # agent at all. Shared-agent creation is therefore admin-only and runs on
        # the OWNER/admin session which is not subject to RLS — gated at the app
        # layer (see app/api/agent_routes.create_agent) and used by the global
        # seed loader (app/db/init_db.seed_agents). Per-org creation is handled
        # purely by RLS + the org_id default below.
        [
            # Default org_id to the bound org — exactly like conversations/messages
            # and friends — so EVERY existing agent-creation path (create_agent,
            # import_agents, dynamic builder) lands the agent in the caller's org
            # without editing each call site. An explicit NULL (the admin shared
            # path, inserted via the owner session) overrides this default.
            "ALTER TABLE agents ALTER COLUMN org_id SET DEFAULT current_org_id()",
            "ALTER TABLE agents ENABLE ROW LEVEL SECURITY",
            "ALTER TABLE agents FORCE ROW LEVEL SECURITY",
            "DROP POLICY IF EXISTS agents_org_isolation ON agents",
            """
            CREATE POLICY agents_org_isolation ON agents
            USING (org_id IS NULL OR org_id = current_org_id())
            WITH CHECK (org_id = current_org_id())
            """,
        ],
    ),
    (
        "20260717_01_org_invitations",
        "BR-2.1: invitations table (invite-by-email) with org-isolation RLS",
        # Invite-by-email substrate for multi-user orgs. Same tenancy shape as the
        # data tables: org_id defaults to current_org_id(), ENABLE + FORCE RLS, and
        # a plain org-isolation policy so create/list/revoke on the RLS-subject
        # request session only ever see the caller's active org. ACCEPT is the one
        # cross-tenant step (the invitee is not yet a member) and runs on the
        # RLS-exempt admin_session — the scheduler's documented precedent.
        #
        # create_all builds this table on a FRESH install (from the ORM model)
        # BEFORE this migration runs; every statement here is IF NOT EXISTS /
        # idempotent so it is a safe no-op there and the real DDL on a deployed DB.
        [
            """
            CREATE TABLE IF NOT EXISTS invitations (
                id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
                org_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
                email varchar(255) NOT NULL,
                role varchar(50) NOT NULL DEFAULT 'member',
                token varchar(255) NOT NULL UNIQUE,
                status varchar(50) NOT NULL DEFAULT 'pending',
                invited_by uuid REFERENCES users(id) ON DELETE SET NULL,
                accepted_by uuid REFERENCES users(id) ON DELETE SET NULL,
                expires_at timestamptz,
                accepted_at timestamptz,
                created_at timestamptz NOT NULL DEFAULT now(),
                updated_at timestamptz NOT NULL DEFAULT now()
            )
            """,
            "CREATE INDEX IF NOT EXISTS ix_invitations_org_id ON invitations(org_id)",
            "CREATE INDEX IF NOT EXISTS ix_invitations_email ON invitations(email)",
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_invitations_token ON invitations(token)",
            # Auto-tag org_id with the caller's active org on a request-session
            # INSERT that omits it (mirrors conversations/messages/agents).
            "ALTER TABLE invitations ALTER COLUMN org_id SET DEFAULT current_org_id()",
            "ALTER TABLE invitations ENABLE ROW LEVEL SECURITY",
            "ALTER TABLE invitations FORCE ROW LEVEL SECURITY",
            "DROP POLICY IF EXISTS invitations_org_isolation ON invitations",
            "CREATE POLICY invitations_org_isolation ON invitations USING (org_id = current_org_id()) WITH CHECK (org_id = current_org_id())",
            # New table created after 20260626_01's blanket GRANT — grant explicitly
            # (guarded on the role existing; ALTER DEFAULT PRIVILEGES also covers it
            # for owner-created objects, but this is belt-and-suspenders + idempotent).
            """
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'brigade_app') THEN
                    GRANT SELECT, INSERT, UPDATE, DELETE ON invitations TO brigade_app;
                END IF;
            END $$;
            """,
        ],
    ),
    (
        "20260718_01_api_key_org_binding",
        "BR-2.4 / H1: per-key org binding — api_keys.org_id (+ backfill to early-access)",
        # Closes finding H1. Before this, EVERY service/agent key collapsed onto the
        # shared 'early-access' org (no per-key org_id), so two customers' keys read
        # each other's data — which gated multi-customer key issuance. This adds
        # api_keys.org_id; the auth middleware (_bind_org_context) now binds the
        # request's RLS org to it (see AuthUser.key_org_id).
        #
        # api_keys deliberately gets NO RLS: the key lookup in validate_api_key runs
        # BEFORE any org is bound (empty GUC), so FORCE RLS there would hide every
        # key and break all auth. org_id here is a binding POINTER used to CHOOSE the
        # org, not an RLS-isolated column (mirrors users / organizations /
        # org_memberships, which also carry no RLS).
        #
        # Additive + idempotent: create_all already builds the column from the ORM
        # model on a fresh install (this is the deployed-DB path). Existing keys are
        # backfilled to 'early-access' (their pre-BR-2.4 home) so behavior is
        # unchanged on cutover; new keys are stamped with the creator's active org
        # (server_default current_org_id() + explicit stamp in apikey_routes).
        # Left NULLABLE (unlike the RLS data tables' NOT NULL) — api_keys has no RLS
        # and a NULL org_id gracefully falls back to early-access at bind time.
        [
            "ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS org_id uuid",
            """
            UPDATE api_keys
            SET org_id = (SELECT id FROM organizations WHERE slug = 'early-access')
            WHERE org_id IS NULL
            """,
            "ALTER TABLE api_keys ALTER COLUMN org_id SET DEFAULT current_org_id()",
            "CREATE INDEX IF NOT EXISTS ix_api_keys_org_id ON api_keys(org_id)",
            """
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_api_keys_org_id_organizations') THEN
                    ALTER TABLE api_keys ADD CONSTRAINT fk_api_keys_org_id_organizations FOREIGN KEY (org_id) REFERENCES organizations(id) ON DELETE CASCADE;
                END IF;
            END $$;
            """,
        ],
    ),
    (
        "20260719_01_durable_workflow_state",
        "BR-4 durability: workflow_executions + ralph_executions (persist in-flight state)",
        # Closes the BR-4 durability gap: hierarchical WorkflowExecutions (incl.
        # HITL checkpoint state) and Ralph self-correction state were in-memory /
        # per-process-disk only — LOST on restart, WRONG with 2 replicas. These two
        # tables are the write-through durable mirror the engines upsert into and
        # rehydrate from on startup (see app/db/execution_store.py).
        #
        # create_all already builds these tables from the ORM models
        # (WorkflowExecutionRecord / RalphExecutionRecord) on a FRESH install BEFORE
        # this migration runs; every statement here is CREATE ... IF NOT EXISTS /
        # idempotent so it is a safe no-op there and the real DDL on a deployed DB.
        #
        # NO RLS — deliberately, and unlike the 8 tenant data tables. The workflow /
        # Ralph engines are trusted cross-org SYSTEM components (the scheduler's
        # documented precedent): they read via the RLS-exempt admin_session and
        # intentionally return executions globally (the routes never filtered by
        # org, so adding RLS would silently hide rows from the admin path with an
        # empty GUC and CHANGE behaviour). org_id is a best-effort attribution
        # POINTER here, exactly like api_keys / users / organizations, which also
        # carry no RLS. Because there is no RLS, this migration does NOT touch the
        # 8-table RLS proof (still 44/0).
        [
            """
            CREATE TABLE IF NOT EXISTS workflow_executions (
                id varchar(64) PRIMARY KEY,
                workflow_id varchar(255) NOT NULL,
                workflow_name varchar(500),
                org_id uuid REFERENCES organizations(id) ON DELETE CASCADE,
                state varchar(50) NOT NULL DEFAULT 'pending',
                current_step varchar(255),
                pending_checkpoint varchar(255),
                mission_id varchar(255),
                data json NOT NULL,
                started_at timestamptz,
                completed_at timestamptz,
                created_at timestamptz NOT NULL DEFAULT now(),
                updated_at timestamptz NOT NULL DEFAULT now()
            )
            """,
            "ALTER TABLE workflow_executions ALTER COLUMN org_id SET DEFAULT current_org_id()",
            "CREATE INDEX IF NOT EXISTS ix_workflow_executions_state ON workflow_executions(state)",
            "CREATE INDEX IF NOT EXISTS ix_workflow_executions_workflow_id ON workflow_executions(workflow_id)",
            "CREATE INDEX IF NOT EXISTS ix_workflow_executions_org_id ON workflow_executions(org_id)",
            """
            CREATE TABLE IF NOT EXISTS ralph_executions (
                execution_id varchar(255) PRIMARY KEY,
                workflow_id varchar(255) NOT NULL,
                org_id uuid REFERENCES organizations(id) ON DELETE CASCADE,
                is_complete boolean NOT NULL DEFAULT false,
                is_paused boolean NOT NULL DEFAULT false,
                final_outcome varchar(50),
                data json NOT NULL,
                created_at timestamptz NOT NULL DEFAULT now(),
                updated_at timestamptz NOT NULL DEFAULT now()
            )
            """,
            "ALTER TABLE ralph_executions ALTER COLUMN org_id SET DEFAULT current_org_id()",
            "CREATE INDEX IF NOT EXISTS ix_ralph_executions_is_complete ON ralph_executions(is_complete)",
            "CREATE INDEX IF NOT EXISTS ix_ralph_executions_workflow_id ON ralph_executions(workflow_id)",
            "CREATE INDEX IF NOT EXISTS ix_ralph_executions_org_id ON ralph_executions(org_id)",
            # New tables created after 20260626_01's blanket GRANT — grant the app
            # role explicitly (guarded on the role existing; belt-and-suspenders +
            # idempotent, mirrors the invitations migration). The engines use the
            # owner admin_session, so this grant is not strictly required, but keeps
            # the app role consistent with every other table.
            """
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'brigade_app') THEN
                    GRANT SELECT, INSERT, UPDATE, DELETE ON workflow_executions TO brigade_app;
                    GRANT SELECT, INSERT, UPDATE, DELETE ON ralph_executions TO brigade_app;
                END IF;
            END $$;
            """,
        ],
    ),
    (
        "20260720_01_billing_usage_ledger",
        "BR-3.1/3.4/3.6/3.8: usage_events (per-org RLS ledger) + org_billing_config (per-org caps)",
        # BR-3 billing core. Two additive tables:
        #
        #  * usage_events — the durable, write-through per-ORG usage ledger every
        #    metered execution path appends to (see app/db/usage_ledger.py). This
        #    is what moves the cost-control ledger OFF the best-effort in-memory /
        #    fire-and-forget Lago-only path and INTO Postgres (BR-3.8), mirroring
        #    the BR-4 execution_store durable-state pattern. It is the source of
        #    truth for per-org usage AND the substrate the per-org cap preflight
        #    (BR-3.6) sums. org_id is the billing subject (BR-3.1).
        #
        #    Unlike the BR-4 system-bookkeeping tables, this IS tenant data (org A's
        #    spend must be invisible to org B), so it carries FULL RLS exactly like
        #    conversations / messages / tool_executions: ENABLE + FORCE + an
        #    org-isolation policy (org_id = current_org_id() both ways). Writes come
        #    from the RLS-exempt admin_session with an explicit org_id (metering can
        #    run in a background task with no bound request org), while the policy
        #    guarantees a request-session reader only ever sees its own org — this
        #    is the isolation the BR-3 billing proof asserts. Because it is a NEW,
        #    separate table, it does NOT touch the existing 8-table RLS proof (still
        #    44/0).
        #
        #  * org_billing_config — per-org caps the preflight enforces (BR-3.6). NO
        #    RLS (a config/pointer table keyed BY org, read by admin_session in the
        #    preflight by arbitrary id), like organizations / api_keys.
        #
        # create_all already builds both tables from the ORM models on a FRESH
        # install BEFORE this migration runs; every statement here is CREATE ... IF
        # NOT EXISTS / idempotent so it is a safe no-op there and the real DDL on a
        # deployed DB.
        [
            """
            CREATE TABLE IF NOT EXISTS usage_events (
                id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
                org_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
                external_customer_id varchar(255),
                user_id varchar(255),
                event_type varchar(50) NOT NULL DEFAULT 'ai_api_call',
                source varchar(50) NOT NULL DEFAULT 'unknown',
                agent_id varchar(255),
                model varchar(255),
                tokens integer NOT NULL DEFAULT 0,
                cost double precision NOT NULL DEFAULT 0.0,
                rate_tier varchar(50),
                rate_multiplier double precision NOT NULL DEFAULT 1.0,
                outcome varchar(32),
                transaction_id varchar(255),
                meta json,
                created_at timestamptz NOT NULL DEFAULT now()
            )
            """,
            "ALTER TABLE usage_events ALTER COLUMN org_id SET DEFAULT current_org_id()",
            "CREATE INDEX IF NOT EXISTS ix_usage_events_org_id ON usage_events(org_id)",
            "CREATE INDEX IF NOT EXISTS ix_usage_events_org_created ON usage_events(org_id, created_at)",
            "CREATE INDEX IF NOT EXISTS ix_usage_events_event_type ON usage_events(event_type)",
            "CREATE INDEX IF NOT EXISTS ix_usage_events_created_at ON usage_events(created_at)",
            # Tenant data → same RLS shape as conversations/messages/tool_executions.
            "ALTER TABLE usage_events ENABLE ROW LEVEL SECURITY",
            "ALTER TABLE usage_events FORCE ROW LEVEL SECURITY",
            "DROP POLICY IF EXISTS usage_events_org_isolation ON usage_events",
            "CREATE POLICY usage_events_org_isolation ON usage_events USING (org_id = current_org_id()) WITH CHECK (org_id = current_org_id())",
            # Per-org caps (BR-3.6). No RLS — config keyed by org, read by admin_session.
            """
            CREATE TABLE IF NOT EXISTS org_billing_config (
                org_id uuid PRIMARY KEY REFERENCES organizations(id) ON DELETE CASCADE,
                monthly_token_cap bigint,
                monthly_cost_cap double precision,
                hard_stop boolean NOT NULL DEFAULT true,
                notes text,
                created_at timestamptz NOT NULL DEFAULT now(),
                updated_at timestamptz NOT NULL DEFAULT now()
            )
            """,
            # New tables created after 20260626_01's blanket GRANT — grant the app
            # role explicitly (guarded on the role existing; idempotent, mirrors the
            # invitations / durable-state migrations). usage_events is written via
            # the owner admin_session, but a request-session reader (usage UI) needs
            # SELECT, and the BR-3 proof drives the app role to assert RLS isolation.
            """
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'brigade_app') THEN
                    GRANT SELECT, INSERT, UPDATE, DELETE ON usage_events TO brigade_app;
                    GRANT SELECT, INSERT, UPDATE, DELETE ON org_billing_config TO brigade_app;
                END IF;
            END $$;
            """,
        ],
    ),
    (
        "20260729_02_rating_raider_avatar_url",
        "Preserve the verified production rating-raider portrait binding",
        # The exact 512x512 WebP already served from Brigade and was explicitly
        # bound to the rating-raider row in production. It is now tracked in the
        # Brigade asset catalog. Null-only assignment preserves every operator
        # custom URL and makes this migration safe to repeat.
        """
        UPDATE agents
        SET avatar_url = '/avatars/rating-raider.webp'
        WHERE id = 'rating-raider'
          AND (avatar_url IS NULL OR btrim(avatar_url) = '');
        """,
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
