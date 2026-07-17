"""Audit-2 F1 — import/update org_id field-injection proof.

Sibling to prove_shared_agent_mutation.py. Drives the REAL app code against an
EPHEMERAL throwaway Postgres:
  * app.db.database.init_db  → create_all + all migrations (agents RLS with the
    shared-catalog policy) + provision the NOBYPASSRLS app role + verify posture.
  * app.db.repositories.AgentRepository.update — the SAME code the import route
    calls to mutate an agent, now hardened to strip org_id/orgId/id.
  * app.db.database.async_session (app-role, RLS-subject) / admin_session (owner,
    RLS-exempt) — the two sessionmakers `_agent_writer` routes between (shared →
    owner/RLS-exempt; per-org → request/RLS-subject).

What it proves (finding F1): under ENFORCED RLS (app role NOBYPASSRLS), an
operator ``POST /agents/import/json`` cannot use a raw ``org_id``/``orgId`` (or
``id``) in the payload to reassign/claim a SHARED (NULL-org) seed agent — even
though that write runs on the RLS-EXEMPT owner session (which has NO ``WITH
CHECK`` to stop it). The pre-fix regression: the C1 admin_session routing removed
the request-session ``WITH CHECK`` cap, so ``AgentRepository.update`` would
``setattr(agent, "org_id", <any uuid>)`` and relocate the agent fleet-wide. The
fix strips the tenancy keys inside ``update`` (real code, exercised here) AND at
the route via the ``_IMPORT_WRITABLE_FIELDS`` whitelist (the real constant is
loaded from source below via ``ast`` — the route module itself pulls heavy
runtime deps, langgraph/LLM clients, that aren't importable in this harness).

The counterfactual (PHASE 3) shows the owner session CAN still write org_id at
raw SQL (proving the RLS-exempt path genuinely lacks the WITH CHECK backstop, so
the danger is real) — only the code-level strip neutralizes the import vector.

Env (set by the caller BEFORE import — engines are built at import time):
  MIGRATION_DATABASE_URL  owner/admin DSN (superuser)       — DDL + migrations
  DATABASE_URL            app-role DSN (brigade_app_login)   — RLS-subject runtime

Exit code 0 only if every assertion holds.
"""
import ast
import asyncio
import os
import sys
import uuid

from sqlalchemy import text

# Import order matters: env is already set by the shell. Importing the module
# builds `engine` (app-role) + `migration_engine` (owner) from those env vars.
import app.db.models  # noqa: F401  — registers all ORM tables on Base.metadata
from app.db.database import (
    engine,            # runtime app-role engine (DATABASE_URL) — subject to RLS
    migration_engine,  # owner/admin engine (MIGRATION_DATABASE_URL)
    async_session,     # app-role sessionmaker (a "request" session, RLS-subject)
    admin_session,     # owner sessionmaker (RLS-exempt) — the shared-agent path
    init_db,
    provision_app_role,
    verify_app_role_not_bypassing,
    verify_owner_role_bypasses_rls,
)
from app.db.models import Agent
from app.db.repositories import AgentRepository

ORG_A = str(uuid.uuid4())
ORG_B = str(uuid.uuid4())
FAILURES = []
PASSES = []


def check(label, condition, detail=""):
    tag = "PASS" if condition else "FAIL"
    (PASSES if condition else FAILURES).append(label)
    print(f"  [{tag}] {label}" + (f"  — {detail}" if detail else ""))


async def scalar(conn, statement, **params):
    return (await conn.execute(text(statement), params)).scalar()


async def bind(session, org_id):
    """Exactly what middleware._bind_org_context runs to bind the RLS GUC."""
    await session.execute(
        text("SELECT set_config('app.current_org_id', :o, false)"), {"o": org_id}
    )


async def app_session_bound(org_id):
    """A fresh app-role (RLS-subject) session with the org GUC bound — i.e. a real
    request session acting as ``org_id``."""
    s = async_session()
    await bind(s, org_id)
    return s


async def owner_field(agent_id, column):
    async with migration_engine.connect() as oc:
        return await scalar(oc, f"SELECT {column} FROM agents WHERE id=:id", id=agent_id)


def load_real_whitelist():
    """Load the REAL ``_IMPORT_WRITABLE_FIELDS`` frozenset from the route source
    WITHOUT importing the module (it pulls langgraph). Parse the assignment and
    literal-eval the set elements — so the proof tracks the actual constant with
    zero drift."""
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src_path = os.path.join(here, "app", "api", "agent_routes.py")
    tree = ast.parse(open(src_path).read())
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "_IMPORT_WRITABLE_FIELDS"
            for t in node.targets
        ):
            call = node.value  # frozenset({...})
            setnode = call.args[0]
            return {ast.literal_eval(e) for e in setnode.elts}
    raise RuntimeError("_IMPORT_WRITABLE_FIELDS not found in agent_routes.py")


async def main():
    print("=" * 78)
    print("PHASE 0 — init_db as owner; provision + verify NOBYPASSRLS app role")
    print("=" * 78)
    print(f"MIGRATION_DATABASE_URL (owner)   = {os.environ['MIGRATION_DATABASE_URL']}")
    print(f"DATABASE_URL           (app-role)= {os.environ['DATABASE_URL']}")
    print(f"migration_engine is engine? {migration_engine is engine} (expect False)")

    await init_db()
    await provision_app_role()
    posture = await verify_app_role_not_bypassing()
    check("runtime role is NOBYPASSRLS brigade_app_login",
          bool(posture) and posture["role"] == "brigade_app_login"
          and posture["bypassrls"] is False and posture["super"] is False, str(posture))
    owner_posture = await verify_owner_role_bypasses_rls()
    check("owner/migration role BYPASSES RLS (the shared-agent write path)",
          bool(owner_posture) and (owner_posture["super"] or owner_posture["bypassrls"]),
          str(owner_posture))

    async with migration_engine.connect() as oc:
        ag = (await oc.execute(text(
            "SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname='agents'"
        ))).first()
        check("agents has RLS ENABLED + FORCED (shared-catalog policy live)",
              bool(ag) and ag[0] is True and ag[1] is True,
              f"rowsecurity={ag[0] if ag else None} force={ag[1] if ag else None}")

    print("\n" + "=" * 78)
    print("PHASE 1 — Seed org A + org B; agent-global(NULL/shared), agent-a(orgA)")
    print("=" * 78)
    async with migration_engine.begin() as oc:
        for oid, slug in ((ORG_A, "org-a"), (ORG_B, "org-b")):
            await oc.execute(text(
                "INSERT INTO organizations (id,name,slug,plan_tier,api_calls_limit,metadata) "
                "VALUES (:id,:n,:s,'free',0,'{}'::json)"
            ), {"id": oid, "n": slug, "s": slug})
        await oc.execute(text(
            "INSERT INTO agents (id,name,org_id,tools) VALUES ('agent-global','Gunny',NULL,'[]'::json)"
        ))
        await oc.execute(text(
            "INSERT INTO agents (id,name,org_id,tools) VALUES ('agent-a','Agent A',:o,'[]'::json)"
        ), {"o": ORG_A})
    print(f"orgs: A={ORG_A}  B={ORG_B}")
    print("seeded (owner): agent-global=NULL(shared), agent-a=orgA")

    print("\n" + "=" * 78)
    print("PHASE 2 — THE ATTACK: import-update the shared agent via admin_session with org_id")
    print("=" * 78)
    # This is EXACTLY what _agent_writer does for a shared (orgId is None) agent:
    # route the write through the RLS-EXEMPT owner session. The malicious import
    # payload carries org_id/orgId (claim it to org A) + id (re-map PK) alongside a
    # benign field. The FIXED AgentRepository.update must strip the tenancy keys.
    malicious = {
        "id": "hijacked-pk",              # attempt PK re-map
        "org_id": ORG_A,                  # attempt to CLAIM the shared agent to org A
        "orgId": ORG_A,                   # camelCase alias, same intent
        "name": "Gunny",
        "displayName": "claimed by org A",  # benign field — MUST still apply
    }
    check("org_id IS a real Agent column (the injection targets a genuine column)",
          hasattr(Agent, "org_id"), "hasattr(Agent,'org_id')")
    async with admin_session() as owner_sess:
        updated = await AgentRepository(owner_sess).update("agent-global", dict(malicious))
    check("update on the RLS-exempt owner session returns the agent (no error)",
          bool(updated), f"updated={bool(updated)}")
    check("benign field APPLIED — displayName updated (update semantics intact)",
          bool(updated) and updated.get("displayName") == "claimed by org A",
          f"displayName={updated.get('displayName') if updated else None}")
    org_after = await owner_field("agent-global", "org_id")
    check("F1 FIX: shared agent's org_id STAYS NULL — operator could NOT claim it",
          org_after is None, f"org_id={org_after}")
    check("F1 FIX: shared agent still resolves by its original id (PK not re-mapped)",
          (await owner_field("agent-global", "name")) == "Gunny",
          f"agent-global still present, name={await owner_field('agent-global','name')!r}")
    check("F1 FIX: no row was relocated to the re-mapped PK 'hijacked-pk'",
          (await owner_field("hijacked-pk", "id")) is None,
          "SELECT id WHERE id='hijacked-pk' is empty")

    print("\n" + "=" * 78)
    print("PHASE 3 — Counterfactual: the owner session CAN write org_id at raw SQL")
    print("=" * 78)
    # Proves the danger is real: the admin/owner session has NO WITH CHECK, so a
    # raw column write DOES relocate the shared agent. Only the code-level strip in
    # AgentRepository.update stops the import vector. Restore NULL afterwards.
    async with migration_engine.begin() as oc:
        await oc.execute(text("UPDATE agents SET org_id=:o WHERE id='agent-global'"), {"o": ORG_A})
    raw = await owner_field("agent-global", "org_id")
    check("raw owner-session UPDATE ... SET org_id DID change it (no WITH CHECK on this path)",
          str(raw) == ORG_A, f"org_id={raw} (== ORG_A)")
    async with migration_engine.begin() as oc:
        await oc.execute(text("UPDATE agents SET org_id=NULL WHERE id='agent-global'"))
    check("restored shared agent to NULL-org for the remaining assertions",
          (await owner_field("agent-global", "org_id")) is None)

    print("\n" + "=" * 78)
    print("PHASE 4 — Route-level whitelist: the REAL _IMPORT_WRITABLE_FIELDS strips tenancy keys")
    print("=" * 78)
    whitelist = load_real_whitelist()
    print(f"loaded {len(whitelist)} whitelisted fields from agent_routes.py source")
    for k in ("org_id", "orgId", "id", "createdAt", "updatedAt"):
        check(f"whitelist EXCLUDES {k!r} (not client-settable via import)",
              k not in whitelist)
    for k in ("name", "displayName", "systemPrompt", "model", "tools", "domain", "accessPolicy"):
        check(f"whitelist INCLUDES content field {k!r} (import semantics intact)",
              k in whitelist)
    # Apply the whitelist filter (what _sanitize_agent_import_updates does) to the
    # malicious payload and confirm only benign fields survive.
    sanitized = {k: v for k, v in malicious.items() if k in whitelist}
    check("sanitized malicious payload drops org_id/orgId/id",
          not ({"org_id", "orgId", "id"} & set(sanitized)),
          f"sanitized keys={sorted(sanitized)}")
    check("sanitized malicious payload keeps name + displayName",
          sanitized.get("displayName") == "claimed by org A" and sanitized.get("name") == "Gunny",
          f"sanitized={sanitized}")

    print("\n" + "=" * 78)
    print("PHASE 5 — Per-org agent: import cannot relocate agent-a across orgs either")
    print("=" * 78)
    # A per-org agent's import-update runs on the REQUEST session (org A). Attacker
    # tries to shove it to org B via org_id in the payload. The fixed update strips
    # org_id, so agent-a stays in org A (and even a raw attempt would fail WITH CHECK).
    s = await app_session_bound(ORG_A)
    try:
        ua = await AgentRepository(s).update(
            "agent-a", {"org_id": ORG_B, "orgId": ORG_B, "displayName": "A edits its own"}
        )
        check("org A import-update of its OWN agent-a succeeds (benign field applies)",
              bool(ua) and ua.get("displayName") == "A edits its own",
              f"displayName={ua.get('displayName') if ua else None}")
    finally:
        await s.close()
    check("F1 FIX: agent-a STAYS in org A (org_id not relocated to org B)",
          str(await owner_field("agent-a", "org_id")) == ORG_A,
          f"org_id={await owner_field('agent-a','org_id')}")

    # org B cannot even see agent-a (RLS) → its import-update is a no-op.
    s = await app_session_bound(ORG_B)
    try:
        res = await AgentRepository(s).update("agent-a", {"displayName": "org B tampering", "org_id": ORG_B})
        check("org B import-update of org A's agent-a is a no-op (invisible under RLS)",
              res is None, f"update result={res is not None}")
    finally:
        await s.close()
    check("agent-a UNCHANGED after org B's attempt (isolation held)",
          (await owner_field("agent-a", "display_name")) == "A edits its own",
          f"display_name={await owner_field('agent-a','display_name')!r}")

    print("\n" + "=" * 78)
    print("PHASE 6 — Shared agent still global + visible to both orgs after all attempts")
    print("=" * 78)
    check("agent-global is STILL NULL-org (shared) at the end",
          (await owner_field("agent-global", "org_id")) is None)
    for org, oid in (("A", ORG_A), ("B", ORG_B)):
        s = await app_session_bound(oid)
        try:
            g = await AgentRepository(s).get("agent-global")
            check(f"org {org} still SEES the shared agent-global (RLS USING allows NULL)",
                  bool(g) and g.get("orgId") is None,
                  f"orgId={g.get('orgId') if g else 'not-visible'}")
        finally:
            await s.close()

    print("\n" + "=" * 78)
    print(f"RESULT: {len(PASSES)} passed, {len(FAILURES)} failed")
    if FAILURES:
        print("FAILURES:")
        for f in FAILURES:
            print(f"   - {f}")
    print("=" * 78)
    await engine.dispose()
    await migration_engine.dispose()
    sys.exit(1 if FAILURES else 0)


if __name__ == "__main__":
    asyncio.run(main())
