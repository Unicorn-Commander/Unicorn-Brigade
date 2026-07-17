"""BR-1.2 / BR-1.3 two-org RLS isolation proof.

Drives the REAL app code (app.db.database.init_db → create_all + the
20260626_01_org_tenancy_rls migration + provision_app_role +
verify_app_role_not_bypassing) against an EPHEMERAL throwaway Postgres, then
proves org isolation by connecting as the provisioned NOBYPASSRLS app role.

Env (set by the caller BEFORE import — the engines are built at import time):
  MIGRATION_DATABASE_URL  owner/admin DSN (superuser)   — DDL + migrations
  DATABASE_URL            app-role DSN (brigade_app_login) — RLS-subject runtime

Exit code 0 only if every isolation assertion holds.
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
    init_db,
    provision_app_role,
    verify_app_role_not_bypassing,
    verify_owner_role_bypasses_rls,
)

ORG_A = str(uuid.uuid4())
ORG_B = str(uuid.uuid4())
FAILURES = []
PASSES = []


def check(label, condition, detail=""):
    tag = "PASS" if condition else "FAIL"
    (PASSES if condition else FAILURES).append(label)
    print(f"  [{tag}] {label}" + (f"  — {detail}" if detail else ""))


def sql(label, statement):
    print(f"\n>>> {label}\nSQL: {' '.join(statement.split())}")


async def scalar(conn, statement, **params):
    return (await conn.execute(text(statement), params)).scalar()


async def set_org(conn, org_id):
    """Exactly what scheduler._bind_org and middleware._bind_org_context run."""
    await conn.execute(
        text("SELECT set_config('app.current_org_id', :org, false)"), {"org": org_id}
    )


async def main():
    print("=" * 78)
    print("PHASE 0 — Drive real init_db() as owner; provision + verify app role")
    print("=" * 78)
    print(f"MIGRATION_DATABASE_URL (owner)   = {os.environ['MIGRATION_DATABASE_URL']}")
    print(f"DATABASE_URL           (app-role)= {os.environ['DATABASE_URL']}")
    print(f"migration_engine is engine? {migration_engine is engine} (expect False)")

    await init_db()  # create_all + migration + identity remap + provision + verify

    # Re-run provisioning + verification standalone so their results are captured.
    await provision_app_role()
    posture = await verify_app_role_not_bypassing()
    print(f"\nRuntime role posture: {posture}")
    check("runtime connects as brigade_app_login",
          posture and posture["role"] == "brigade_app_login", str(posture))
    check("runtime role rolbypassrls = false",
          posture and posture["bypassrls"] is False, str(posture))
    check("runtime role rolsuper = false",
          posture and posture["super"] is False, str(posture))

    # M1: symmetric owner-role check — the OWNER/MIGRATION_DATABASE_URL role MUST
    # bypass RLS, or the scheduler + identity remap would silently see zero rows.
    owner_posture = await verify_owner_role_bypasses_rls()
    print(f"Owner role posture: {owner_posture}")
    check("M1: owner/migration role BYPASSES RLS (rolsuper OR rolbypassrls)",
          bool(owner_posture) and (owner_posture["super"] or owner_posture["bypassrls"]),
          str(owner_posture))

    # Confirm role catalog + FORCE RLS posture directly, via owner.
    async with migration_engine.connect() as oc:
        parent = (await oc.execute(text(
            "SELECT rolcanlogin, rolbypassrls, rolsuper FROM pg_roles WHERE rolname='brigade_app'"
        ))).first()
        print(f"\nbrigade_app parent (canlogin,bypassrls,super) = {tuple(parent) if parent else None}")
        check("brigade_app parent is NOLOGIN", parent and parent[0] is False)
        check("brigade_app parent is NOBYPASSRLS", parent and parent[1] is False)

        member = (await oc.execute(text(
            "SELECT r.rolname FROM pg_auth_members m "
            "JOIN pg_roles r ON r.oid=m.roleid "
            "JOIN pg_roles a ON a.oid=m.member "
            "WHERE a.rolname='brigade_app_login'"
        ))).scalars().all()
        print(f"brigade_app_login is a member of: {member}")
        check("app-login IS IN ROLE brigade_app", "brigade_app" in member)

        rls = (await oc.execute(text(
            "SELECT relname, relrowsecurity, relforcerowsecurity FROM pg_class "
            "WHERE relname IN ('conversations','messages','scheduled_runs',"
            "'scheduled_run_history','tool_executions','builder_sessions',"
            "'speaker_profiles','code_attributions') ORDER BY relname"
        ))).all()
        print("\nRLS posture (relname, rowsecurity, forcerowsecurity):")
        for r in rls:
            print(f"    {r[0]:<24} enabled={r[1]!s:<5} force={r[2]}")
        check("all 8 data tables ENABLE+FORCE RLS",
              len(rls) == 8 and all(r[1] and r[2] for r in rls))
        # BR-1.4: agents now carries RLS + FORCE (shared-catalog policy). The
        # BR-1.2 proof asserted the opposite ("deferred to BR-1.4"); this is the
        # flip that migration 20260716_02_tenancy_extend delivers.
        ag = (await oc.execute(text(
            "SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname='agents'"
        ))).first()
        check("BR-1.4: agents has RLS ENABLED", bool(ag) and ag[0] is True,
              f"agents.relrowsecurity={ag[0] if ag else None}")
        check("BR-1.4: agents has RLS FORCED", bool(ag) and ag[1] is True,
              f"agents.relforcerowsecurity={ag[1] if ag else None}")

    print("\n" + "=" * 78)
    print("PHASE 1 — Seed org A + org B; write org A data AS THE APP ROLE")
    print("=" * 78)

    # Orgs created by owner (organizations has no RLS).
    async with migration_engine.begin() as oc:
        for oid, slug in ((ORG_A, "org-a"), (ORG_B, "org-b")):
            await oc.execute(text(
                "INSERT INTO organizations (id,name,slug,plan_tier,api_calls_limit,metadata) "
                "VALUES (:id,:n,:s,'free',0,'{}'::json)"
            ), {"id": oid, "n": slug, "s": slug})
        # an agent per org (agents has no RLS but does carry org_id)
        await oc.execute(text(
            "INSERT INTO agents (id,name,org_id) VALUES ('agent-a','Agent A',:o)"
        ), {"o": ORG_A})
    print(f"orgs: A={ORG_A}  B={ORG_B}")

    # As the APP ROLE, bind org A and insert conversation+message+scheduled_run+history.
    async with engine.connect() as ac:
        await set_org(ac, ORG_A)
        cur = await scalar(ac, "SELECT current_user")
        check("app-role connection current_user=brigade_app_login", cur == "brigade_app_login", cur)

        sql("INSERT conversation into org A (WITH CHECK org_id=current_org_id())",
            "INSERT INTO conversations (id,user_id,org_id,title) VALUES (...A...)")
        conv_a = str(uuid.uuid4())
        await ac.execute(text(
            "INSERT INTO conversations (id,user_id,org_id,title) "
            "VALUES (:id,'user-a',:o,'A conversation')"
        ), {"id": conv_a, "o": ORG_A})

        msg_a = str(uuid.uuid4())
        await ac.execute(text(
            "INSERT INTO messages (id,conversation_id,org_id,role,content) "
            "VALUES (:id,:c,:o,'user','hello from A')"
        ), {"id": msg_a, "c": conv_a, "o": ORG_A})

        sr_a = str(uuid.uuid4())
        await ac.execute(text(
            "INSERT INTO scheduled_runs (id,name,org_id,agent_id,prompt,cron,timezone,enabled,max_runtime_seconds) "
            "VALUES (:id,'run-a',:o,'agent-a','do a','* * * * *','UTC',true,300)"
        ), {"id": sr_a, "o": ORG_A})

        srh_a = str(uuid.uuid4())
        await ac.execute(text(
            "INSERT INTO scheduled_run_history (id,scheduled_run_id,org_id,status,started_at,tool_calls_count) "
            "VALUES (:id,:sr,:o,'running',now(),0)"
        ), {"id": srh_a, "sr": sr_a, "o": ORG_A})
        await ac.commit()
        print("Inserted org A: conversation, message, scheduled_run, scheduled_run_history "
              "(all passed WITH CHECK).")

    print("\n" + "=" * 78)
    print("PHASE 2(a) — App role bound to ORG A sees A's rows")
    print("=" * 78)
    async with engine.connect() as ac:
        await set_org(ac, ORG_A)
        for tbl in ("conversations", "messages", "scheduled_runs", "scheduled_run_history"):
            n = await scalar(ac, f"SELECT count(*) FROM {tbl}")
            check(f"org A sees its {tbl} (n=1)", n == 1, f"count={n}")

    print("\n" + "=" * 78)
    print("PHASE 2(b) — App role bound to ORG B sees ZERO of A's rows; cannot write A")
    print("=" * 78)
    async with engine.connect() as ac:
        await set_org(ac, ORG_B)
        for tbl in ("conversations", "messages", "scheduled_runs", "scheduled_run_history"):
            n = await scalar(ac, f"SELECT count(*) FROM {tbl}")
            check(f"org B sees ZERO {tbl}", n == 0, f"count={n}")

        ids = (await ac.execute(text("SELECT id FROM conversations"))).scalars().all()
        check("org B SELECT id FROM conversations is empty", ids == [], f"ids={ids}")

        # (b.i) WITH CHECK: inserting a row tagged org A while bound to B must fail.
        sql("INSERT conversation tagged ORG A while bound to ORG B (expect WITH CHECK violation)",
            "INSERT INTO conversations (...,org_id=ORG_A,...) -- under GUC=ORG_B")
        try:
            await ac.execute(text(
                "INSERT INTO conversations (id,user_id,org_id,title) "
                "VALUES (:id,'evil',:o,'cross-org write')"
            ), {"id": str(uuid.uuid4()), "o": ORG_A})
            await ac.commit()
            check("cross-org INSERT (org A row under org B) rejected", False, "INSERT SUCCEEDED (LEAK!)")
        except Exception as e:
            await ac.rollback()
            check("cross-org INSERT (org A row under org B) rejected by WITH CHECK",
                  "row-level security" in str(e).lower() or "violates" in str(e).lower(),
                  type(e).__name__ + ": " + str(e).splitlines()[0][:120])

        # (b.ii) cross-org UPDATE cannot touch A's row (invisible under B).
        await set_org(ac, ORG_B)
        upd = (await ac.execute(text(
            "UPDATE conversations SET title='hacked' WHERE id=:id"
        ), {"id": conv_a})).rowcount
        await ac.commit()
        check("cross-org UPDATE of org A row affects 0 rows under org B", upd == 0, f"rowcount={upd}")

        # (b.iii) cross-org DELETE cannot touch A's row.
        await set_org(ac, ORG_B)
        dl = (await ac.execute(text(
            "DELETE FROM conversations WHERE id=:id"
        ), {"id": conv_a})).rowcount
        await ac.commit()
        check("cross-org DELETE of org A row affects 0 rows under org B", dl == 0, f"rowcount={dl}")

    # Control: org B CAN write + read its own data (isolation, not a broken app).
    async with engine.connect() as ac:
        await set_org(ac, ORG_B)
        conv_b = str(uuid.uuid4())
        await ac.execute(text(
            "INSERT INTO conversations (id,user_id,org_id,title) VALUES (:id,'user-b',:o,'B conversation')"
        ), {"id": conv_b, "o": ORG_B})
        await ac.commit()
        nb = await scalar(ac, "SELECT count(*) FROM conversations")
        check("org B can create + see its OWN conversation (n=1)", nb == 1, f"count={nb}")
    async with engine.connect() as ac:
        await set_org(ac, ORG_A)
        na = await scalar(ac, "SELECT count(*) FROM conversations")
        check("org A still sees only its own conversation, not B's (n=1)", na == 1, f"count={na}")

    print("\n" + "=" * 78)
    print("PHASE 2(c) — Scheduler org-binding path")
    print("=" * 78)
    # (c.i) The exact set_config path scheduler._bind_org runs: bind A, write history for A's run.
    async with engine.connect() as ac:
        await set_org(ac, ORG_A)
        h2 = str(uuid.uuid4())
        await ac.execute(text(
            "INSERT INTO scheduled_run_history (id,scheduled_run_id,org_id,status,started_at,tool_calls_count) "
            "VALUES (:id,:sr,:o,'success',now(),0)"
        ), {"id": h2, "sr": sr_a, "o": ORG_A})
        await ac.commit()
        n = await scalar(ac, "SELECT count(*) FROM scheduled_run_history")
        check("scheduler-bound org A can append history for its run (n=2)", n == 2, f"count={n}")

    # (c.ii) Under org B, writing history for A's run fails the child WITH CHECK subquery.
    async with engine.connect() as ac:
        await set_org(ac, ORG_B)
        sql("INSERT scheduled_run_history for A's run while bound to ORG B (expect WITH CHECK violation)",
            "child policy verifies parent scheduled_runs.org_id = current_org_id()")
        try:
            await ac.execute(text(
                "INSERT INTO scheduled_run_history (id,scheduled_run_id,org_id,status,started_at,tool_calls_count) "
                "VALUES (:id,:sr,:o,'running',now(),0)"
            ), {"id": str(uuid.uuid4()), "sr": sr_a, "o": ORG_B})
            await ac.commit()
            check("cross-org history INSERT (A's run under B) rejected", False, "INSERT SUCCEEDED (LEAK!)")
        except Exception as e:
            await ac.rollback()
            check("cross-org history INSERT (A's run under B) rejected",
                  "row-level security" in str(e).lower() or "violates" in str(e).lower(),
                  type(e).__name__ + ": " + str(e).splitlines()[0][:120])

    # (c.iii) Why the scheduler MUST use admin_session: app-role with EMPTY GUC sees 0 runs,
    #         but the owner/admin connection enumerates across BOTH orgs.
    async with engine.connect() as ac:
        await ac.execute(text("SELECT set_config('app.current_org_id','',false)"))
        n_empty = await scalar(ac, "SELECT count(*) FROM scheduled_runs")
    async with migration_engine.connect() as oc:
        n_admin = await scalar(oc, "SELECT count(*) FROM scheduled_runs")
    # seed a scheduled_run for org B so cross-tenant enumeration is non-trivial
    async with engine.connect() as ac:
        await set_org(ac, ORG_B)
        await ac.execute(text(
            "INSERT INTO scheduled_runs (id,name,org_id,agent_id,prompt,cron,timezone,enabled,max_runtime_seconds) "
            "VALUES (:id,'run-b',:o,'agent-a','do b','* * * * *','UTC',true,300)"
        ), {"id": str(uuid.uuid4()), "o": ORG_B})
        await ac.commit()
    async with migration_engine.connect() as oc:
        n_admin2 = await scalar(oc, "SELECT count(*) FROM scheduled_runs")
    print(f"app-role EMPTY GUC sees {n_empty} scheduled_runs; admin/owner sees {n_admin}→{n_admin2} across orgs")
    check("app-role with empty GUC sees 0 scheduled_runs (would break a naive scheduler)", n_empty == 0, f"n={n_empty}")
    check("admin/owner session enumerates scheduled_runs across BOTH orgs (n>=2)", n_admin2 >= 2, f"n={n_admin2}")

    print("\n" + "=" * 78)
    print("PHASE 3 — BR-1.4 agents SHARED-CATALOG isolation")
    print("=" * 78)
    # Seed via the OWNER (agents is FORCE-RLS; the owner is not subject to it, and
    # it is the ONLY sanctioned path for a NULL-org shared agent). agent-a (org A)
    # was already inserted in Phase 1; add agent-b (org B) and a global one.
    async with migration_engine.begin() as oc:
        await oc.execute(text(
            "INSERT INTO agents (id,name,org_id) VALUES ('agent-b','Agent B',:o)"
        ), {"o": ORG_B})
        await oc.execute(text(
            "INSERT INTO agents (id,name,org_id) VALUES ('agent-global','Shared Agent',NULL)"
        ))
    print("seeded (owner): agent-a=orgA, agent-b=orgB, agent-global=NULL(shared)")

    # (a) org A sees its own private agent + the shared one, but NOT org B's.
    async with engine.connect() as ac:
        await set_org(ac, ORG_A)
        ids = set((await ac.execute(text("SELECT id FROM agents ORDER BY id"))).scalars().all())
        check("org A sees its private agent-a", "agent-a" in ids, str(ids))
        check("org A sees the shared agent-global", "agent-global" in ids, str(ids))
        check("org A does NOT see org B's private agent-b", "agent-b" not in ids, str(ids))

    # (b) org B sees its own + shared, not A's. Shared agent visible to BOTH orgs.
    async with engine.connect() as ac:
        await set_org(ac, ORG_B)
        ids = set((await ac.execute(text("SELECT id FROM agents ORDER BY id"))).scalars().all())
        check("org B sees its private agent-b", "agent-b" in ids, str(ids))
        check("org B sees the shared agent-global (visible to BOTH)", "agent-global" in ids, str(ids))
        check("org B does NOT see org A's private agent-a", "agent-a" not in ids, str(ids))

    # (c) An UNBOUND session (empty GUC — e.g. public A2A discovery) sees ONLY the
    #     shared/global roster, never any tenant's private agents. This is what
    #     keeps the intentionally-public federation endpoints safe by construction.
    async with engine.connect() as ac:
        await ac.execute(text("SELECT set_config('app.current_org_id','',false)"))
        ids = set((await ac.execute(text("SELECT id FROM agents"))).scalars().all())
        check("unbound app role sees ONLY shared agents (global catalog)",
              ids == {"agent-global"}, str(ids))

    # (d) WITH CHECK: org B cannot write an agent tagged org A.
    async with engine.connect() as ac:
        await set_org(ac, ORG_B)
        sql("INSERT agent tagged ORG A while bound to ORG B (expect WITH CHECK violation)",
            "INSERT INTO agents (id,name,org_id) VALUES ('evil-a','Evil',ORG_A) -- under GUC=ORG_B")
        try:
            await ac.execute(text(
                "INSERT INTO agents (id,name,org_id) VALUES ('evil-a','Evil',:o)"
            ), {"o": ORG_A})
            await ac.commit()
            check("cross-org agent INSERT (org A row under org B) rejected", False, "INSERT SUCCEEDED (LEAK!)")
        except Exception as e:
            await ac.rollback()
            check("cross-org agent INSERT (org A row under org B) rejected by WITH CHECK",
                  "row-level security" in str(e).lower() or "violates" in str(e).lower(),
                  type(e).__name__ + ": " + str(e).splitlines()[0][:120])

    # (e) WITH CHECK: a tenant cannot create a NULL-org SHARED agent (admin-only).
    async with engine.connect() as ac:
        await set_org(ac, ORG_A)
        sql("INSERT NULL-org shared agent as a tenant (expect WITH CHECK violation — admin-only)",
            "INSERT INTO agents (id,name,org_id) VALUES ('sneaky-global','X',NULL) -- under GUC=ORG_A")
        try:
            await ac.execute(text(
                "INSERT INTO agents (id,name,org_id) VALUES ('sneaky-global','X',NULL)"
            ))
            await ac.commit()
            check("tenant creating a NULL-org shared agent rejected", False, "INSERT SUCCEEDED (LEAK!)")
        except Exception as e:
            await ac.rollback()
            check("tenant creating a NULL-org shared agent rejected by WITH CHECK",
                  "row-level security" in str(e).lower() or "violates" in str(e).lower(),
                  type(e).__name__ + ": " + str(e).splitlines()[0][:120])

    # (f) The org_id DEFAULT path: a tenant INSERT that omits org_id is auto-tagged
    #     with the caller's org (server_default current_org_id()) and passes WITH
    #     CHECK — this is why create_agent/import/dynamic paths need no per-site edit.
    async with engine.connect() as ac:
        await set_org(ac, ORG_A)
        await ac.execute(text(
            "INSERT INTO agents (id,name) VALUES ('agent-a-default','A default')"
        ))
        await ac.commit()
        row_org = await scalar(ac, "SELECT org_id FROM agents WHERE id='agent-a-default'")
        check("tenant INSERT without org_id defaults to caller's org", str(row_org) == ORG_A,
              f"org_id={row_org} expected {ORG_A}")
    async with engine.connect() as ac:
        await set_org(ac, ORG_B)
        seen = await scalar(ac, "SELECT count(*) FROM agents WHERE id='agent-a-default'")
        check("org B cannot see org A's defaulted agent", seen == 0, f"count={seen}")

    print("\n" + "=" * 78)
    print("PHASE 4 — B1: get_session teardown must NOT leak org across a POOLED reuse")
    print("=" * 78)
    # The reviewer-verified cross-tenant leak. A pooled connection that carried a
    # bound org into request 1 must return to the pool with the org RLS GUC
    # CLEARED — otherwise an UNBOUND/anonymous request 2 that reuses that same
    # physical connection (public /a2a/agents, get_agent_card, /stats, builder/
    # speaker/voice) inherits the previous tenant's org and reads its rows.
    #
    # This drives the REAL app.db.database.get_session dependency (its ``finally``
    # is the code under test) over a pool_size=1 / max_overflow=0 app-role engine,
    # so request 2 PROVABLY reuses request 1's backend connection (asserted via
    # pg_backend_pid equality). It FAILS on the pre-fix teardown order
    # (set_config-clear THEN rollback — Postgres REVERTS the session-level clear on
    # that rollback, restoring the previous org) and PASSES once teardown is
    # rollback → clear → COMMIT so the clear persists on the pooled connection.
    import app.db.database as _dbmod
    from sqlalchemy.ext.asyncio import (
        AsyncSession,
        create_async_engine as _cae,
        async_sessionmaker as _asm,
    )

    pool1_engine = _cae(
        os.environ["DATABASE_URL"], pool_size=1, max_overflow=0, pool_pre_ping=False
    )
    pool1_sessions = _asm(pool1_engine, expire_on_commit=False, class_=AsyncSession)
    _orig_async_session = _dbmod.async_session
    # get_session() looks up the module-global ``async_session`` at CALL time, so
    # this swap routes the real dependency onto the single-connection pool.
    _dbmod.async_session = pool1_sessions
    leak_conv = str(uuid.uuid4())
    try:
        # Request 1: bind ORG A, write a conversation, commit, then END the request
        # (aclose drives get_session's finally — exactly as when a handler returns).
        gen1 = _dbmod.get_session()
        s1 = await gen1.__anext__()
        await s1.execute(
            text("SELECT set_config('app.current_org_id', :o, false)"), {"o": ORG_A}
        )
        pid1 = (await s1.execute(text("SELECT pg_backend_pid()"))).scalar()
        await s1.execute(
            text(
                "INSERT INTO conversations (id,user_id,org_id,title) "
                "VALUES (:id,'reuse-user',:o,'reuse-A conversation')"
            ),
            {"id": leak_conv, "o": ORG_A},
        )
        await s1.commit()
        await gen1.aclose()  # ← runs get_session's teardown (the code under test)

        # Request 2: UNBOUND read on the REUSED connection. No org is bound — this
        # is the anonymous/public path. Under the B1 fix it must see ZERO rows.
        gen2 = _dbmod.get_session()
        s2 = await gen2.__anext__()
        pid2 = (await s2.execute(text("SELECT pg_backend_pid()"))).scalar()
        guc2 = (
            await s2.execute(text("SELECT current_setting('app.current_org_id', true)"))
        ).scalar()
        n_leak = (await s2.execute(text("SELECT count(*) FROM conversations"))).scalar()
        vis_leak = (
            await s2.execute(
                text("SELECT count(*) FROM conversations WHERE id=:id"), {"id": leak_conv}
            )
        ).scalar()
        await gen2.aclose()

        check(
            "B1: request 2 PROVABLY reuses request 1's backend connection (pool_size=1)",
            pid1 is not None and pid1 == pid2,
            f"pid1={pid1} pid2={pid2}",
        )
        check(
            "B1: reused connection's org GUC is EMPTY for the unbound request",
            (guc2 or "") == "",
            f"guc={guc2!r}",
        )
        check(
            "B1: unbound get_session reuse sees ZERO conversations (no cross-tenant leak)",
            n_leak == 0,
            f"count={n_leak}",
        )
        check(
            "B1: unbound get_session reuse CANNOT see request 1's org-A row",
            vis_leak == 0,
            f"visible={vis_leak}",
        )
    finally:
        _dbmod.async_session = _orig_async_session
        await pool1_engine.dispose()

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
