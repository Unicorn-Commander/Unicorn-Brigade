"""C1 shared/seed (NULL-org) agent MUTATION proof.

Sibling to prove_org_rls_isolation.py. Drives the REAL app code against an
EPHEMERAL throwaway Postgres:
  * app.db.database.init_db  → create_all + all migrations (incl.
    20260716_02_tenancy_extend: agents RLS with the shared-catalog policy) +
    provision the NOBYPASSRLS app role + verify posture.
  * app.db.repositories.AgentRepository — the SAME create/update/delete code the
    agent routes call to touch the DB.
  * app.db.database.async_session (app-role, RLS-subject) / admin_session (owner,
    RLS-exempt) — the two sessionmakers the fixed route routes between.

What it proves (finding C1): under ENFORCED RLS (app role NOBYPASSRLS), a shared
(NULL-org) agent — the 17-agent seed roster — CANNOT be updated/tool-attached on
the RLS-subject request session (its ``WITH CHECK (org_id = current_org_id())``
rejects the NULL row → 500), but CAN be mutated via the OWNER/admin session, while
a per-org agent stays org-isolated. This is exactly the routing the fixed
``app/api/agent_routes._agent_writer`` performs: it READS the target on the
request session (RLS lets it see only a shared agent or one in the caller's own
org), then routes a shared (orgId is None) agent's write through admin_session and
a per-org agent's write through the request session. The proof replicates that
one-line routing decision here because app.api.agent_routes pulls heavy runtime
deps (langgraph, LLM clients) that aren't importable in this harness; the DB
writes it exercises are the real AgentRepository the route uses.

Env (set by the caller BEFORE import — engines are built at import time):
  MIGRATION_DATABASE_URL  owner/admin DSN (superuser)       — DDL + migrations
  DATABASE_URL            app-role DSN (brigade_app_login)   — RLS-subject runtime

Exit code 0 only if every assertion holds.
"""
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


async def owner_org_of(agent_id):
    """Read an agent's org_id AS THE OWNER (RLS-exempt) — ground truth."""
    async with migration_engine.connect() as oc:
        return await scalar(oc, "SELECT org_id FROM agents WHERE id=:id", id=agent_id)


async def owner_field(agent_id, column):
    async with migration_engine.connect() as oc:
        return await scalar(oc, f"SELECT {column} FROM agents WHERE id=:id", id=agent_id)


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
    check("owner/migration role BYPASSES RLS (shared-agent write path)",
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
    print("PHASE 1 — Seed org A + org B; agent-a(orgA), agent-b(orgB), agent-global(NULL)")
    print("=" * 78)
    # Orgs + agents seeded by the OWNER: agents is FORCE-RLS, and the owner is the
    # ONLY sanctioned path for a NULL-org shared agent (mirrors create_agent's
    # shared branch + the seed loader).
    async with migration_engine.begin() as oc:
        for oid, slug in ((ORG_A, "org-a"), (ORG_B, "org-b")):
            await oc.execute(text(
                "INSERT INTO organizations (id,name,slug,plan_tier,api_calls_limit,metadata) "
                "VALUES (:id,:n,:s,'free',0,'{}'::json)"
            ), {"id": oid, "n": slug, "s": slug})
        await oc.execute(text(
            "INSERT INTO agents (id,name,org_id,tools) VALUES ('agent-a','Agent A',:o,'[]'::json)"
        ), {"o": ORG_A})
        await oc.execute(text(
            "INSERT INTO agents (id,name,org_id,tools) VALUES ('agent-b','Agent B',:o,'[]'::json)"
        ), {"o": ORG_B})
        await oc.execute(text(
            "INSERT INTO agents (id,name,org_id,tools) VALUES ('agent-global','Shared Agent',NULL,'[]'::json)"
        ))
    print(f"orgs: A={ORG_A}  B={ORG_B}")
    print("seeded (owner): agent-a=orgA, agent-b=orgB, agent-global=NULL(shared)")

    print("\n" + "=" * 78)
    print("PHASE 2 — _agent_writer's routing KEY: the shared agent reads as orgId=None")
    print("=" * 78)
    # The fixed route READS the target on the RLS-subject request session and keys
    # its routing on agent['orgId'] (None → owner session; else → request session).
    s = await app_session_bound(ORG_A)
    try:
        repo = AgentRepository(s)
        g = await repo.get("agent-global")
        a = await repo.get("agent-a")
        b = await repo.get("agent-b")
        check("request session (org A) can READ the shared agent (RLS USING allows NULL)",
              g is not None, f"get(agent-global)={g is not None}")
        check("shared agent reads as orgId=None → _agent_writer routes it to admin_session",
              bool(g) and g.get("orgId") is None, f"orgId={g.get('orgId') if g else None}")
        check("per-org agent-a reads as orgId=ORG_A → _agent_writer keeps it on the request session",
              bool(a) and a.get("orgId") == ORG_A, f"orgId={a.get('orgId') if a else None}")
        check("org A CANNOT see org B's private agent-b (RLS isolation on read)",
              b is None, f"get(agent-b)={b is not None}")
    finally:
        await s.close()

    print("\n" + "=" * 78)
    print("PHASE 3 — THE BUG: updating the shared agent on the REQUEST session 500s (WITH CHECK)")
    print("=" * 78)
    # This is the pre-fix path (request session for a NULL-org agent). The commit
    # inside AgentRepository.update fails the agents WITH CHECK (org_id=NULL is not
    # current_org_id()). The fix exists precisely to avoid this.
    s = await app_session_bound(ORG_A)
    try:
        try:
            await AgentRepository(s).update("agent-global", {"displayName": "hijacked via request session"})
            check("shared-agent UPDATE on the request session is rejected", False,
                  "UPDATE SUCCEEDED (would only happen if RLS were bypassed)")
        except Exception as e:  # noqa: BLE001
            await s.rollback()
            check("shared-agent UPDATE on the request session rejected by WITH CHECK (the C1 bug)",
                  "row-level security" in str(e).lower() or "violates" in str(e).lower()
                  or "check" in str(e).lower(),
                  type(e).__name__ + ": " + str(e).splitlines()[0][:120])
    finally:
        await s.close()
    # Confirm the failed write did NOT persist.
    dn = await owner_field("agent-global", "display_name")
    check("failed request-session update did NOT mutate the shared agent",
          dn != "hijacked via request session", f"display_name={dn!r}")

    print("\n" + "=" * 78)
    print("PHASE 4 — THE FIX: updating the shared agent via admin_session SUCCEEDS + persists")
    print("=" * 78)
    async with admin_session() as owner_sess:
        updated = await AgentRepository(owner_sess).update(
            "agent-global", {"displayName": "shared roster edited by operator"}
        )
    check("shared-agent UPDATE via admin_session returns the updated agent (no WITH CHECK error)",
          bool(updated) and updated.get("displayName") == "shared roster edited by operator",
          f"displayName={updated.get('displayName') if updated else None}")
    dn2 = await owner_field("agent-global", "display_name")
    check("shared-agent UPDATE via admin_session PERSISTED",
          dn2 == "shared roster edited by operator", f"display_name={dn2!r}")
    # And it is STILL a shared (NULL-org) agent afterwards — the fix does not leak
    # it into an org.
    org_after = await owner_org_of("agent-global")
    check("shared agent stays NULL-org after the admin_session edit (still global)",
          org_after is None, f"org_id={org_after}")

    print("\n" + "=" * 78)
    print("PHASE 5 — Tool ATTACH on the shared agent: admin_session OK, request session 500s")
    print("=" * 78)
    # attach_tool routes through _agent_writer too — a shared agent's tool list is
    # edited on admin_session.
    async with admin_session() as owner_sess:
        ta = await AgentRepository(owner_sess).update("agent-global", {"tools": ["calculator", "web_search"]})
    check("tool-attach on the shared agent via admin_session returns updated tools",
          bool(ta) and set(ta.get("tools") or []) == {"calculator", "web_search"},
          f"tools={ta.get('tools') if ta else None}")
    tools_p = await owner_field("agent-global", "tools")
    check("tool-attach via admin_session PERSISTED to the shared agent",
          set(tools_p or []) == {"calculator", "web_search"}, f"tools={tools_p}")
    # Same attach attempted on the request session → rejected (WITH CHECK).
    s = await app_session_bound(ORG_A)
    try:
        try:
            await AgentRepository(s).update("agent-global", {"tools": ["shell"]})
            check("tool-attach on the shared agent via the request session is rejected", False,
                  "UPDATE SUCCEEDED (RLS not enforced?)")
        except Exception as e:  # noqa: BLE001
            await s.rollback()
            check("tool-attach on the shared agent via the request session rejected by WITH CHECK",
                  "row-level security" in str(e).lower() or "violates" in str(e).lower()
                  or "check" in str(e).lower(),
                  type(e).__name__)
    finally:
        await s.close()
    tools_after = await owner_field("agent-global", "tools")
    check("rejected request-session tool-attach did NOT mutate the shared agent",
          set(tools_after or []) == {"calculator", "web_search"}, f"tools={tools_after}")

    print("\n" + "=" * 78)
    print("PHASE 6 — Per-org agent stays ORG-ISOLATED (the other half of C1)")
    print("=" * 78)
    # (a) org A edits its OWN agent-a on the request session — WITH CHECK passes.
    s = await app_session_bound(ORG_A)
    try:
        ua = await AgentRepository(s).update("agent-a", {"displayName": "A owns this"})
        check("org A updates its OWN per-org agent-a on the request session (WITH CHECK passes)",
              bool(ua) and ua.get("displayName") == "A owns this",
              f"displayName={ua.get('displayName') if ua else None}")
    finally:
        await s.close()
    check("per-org agent-a update PERSISTED",
          (await owner_field("agent-a", "display_name")) == "A owns this")

    # (b) org B cannot see or update org A's private agent-a — repo.get returns
    #     None (invisible under RLS), and update() no-ops (0 rows) → stays isolated.
    s = await app_session_bound(ORG_B)
    try:
        repo = AgentRepository(s)
        seen = await repo.get("agent-a")
        check("org B CANNOT see org A's private agent-a", seen is None, f"get={seen is not None}")
        res = await repo.update("agent-a", {"displayName": "org B tampering"})
        check("org B UPDATE of org A's agent-a is a no-op (invisible row → not found)",
              res is None, f"update result={res is not None}")
    finally:
        await s.close()
    check("org A's agent-a is UNCHANGED after org B's attempt (isolation held)",
          (await owner_field("agent-a", "display_name")) == "A owns this",
          f"display_name={await owner_field('agent-a', 'display_name')!r}")

    # (c) Control: org B CAN edit its OWN agent-b (isolation, not a broken app).
    s = await app_session_bound(ORG_B)
    try:
        ub = await AgentRepository(s).update("agent-b", {"displayName": "B owns this"})
        check("org B updates its OWN per-org agent-b (control: app works within an org)",
              bool(ub) and ub.get("displayName") == "B owns this",
              f"displayName={ub.get('displayName') if ub else None}")
    finally:
        await s.close()

    # (d) The shared agent remains visible to BOTH orgs after all the edits.
    for org, oid in (("A", ORG_A), ("B", ORG_B)):
        s = await app_session_bound(oid)
        try:
            g = await AgentRepository(s).get("agent-global")
            check(f"org {org} still sees the (edited) shared agent-global",
                  bool(g) and g.get("displayName") == "shared roster edited by operator",
                  f"displayName={g.get('displayName') if g else None}")
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
