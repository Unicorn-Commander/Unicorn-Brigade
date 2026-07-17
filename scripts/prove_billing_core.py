"""BR-3 billing-core proof (BR-3.1 / 3.4 / 3.5 / 3.6 / 3.8).

Drives the REAL app code (app.db.database.init_db → create_all + the additive
migrations incl. 20260720_01_billing_usage_ledger + provision_app_role) against
an EPHEMERAL throwaway Postgres, then proves the per-org billing core using the
REAL billing modules — the same ones every metered execution path calls:

    app.db.usage_ledger    record_usage / org_period_usage / get_org_cap /
                           org_over_cap / set_org_cap   (durable per-org ledger)
    app.integrations.metering  meter_usage / enforce_org_cap_or_402
    app.integrations.lago      emit_ai_api_call (BR-3.1 org = external_customer_id)

Asserted (the task's required proofs):
  * a metered call records usage against the RIGHT org (and NOT another);        [BR-3.1/3.4]
  * the durable cost-control ledger lives in Postgres, keyed on org;             [BR-3.8]
  * an over-cap org gets 402 (and under-cap / admin / soft-cap do NOT);          [BR-3.6]
  * usage for org A is INVISIBLE to org B — the usage_events table respects       [BR-3.4/3.5]
    the RLS tenancy exactly like conversations/messages;
  * the streaming shim now routes through the preflight + RBAC + metering gates   [BR-3.5]
    it previously BYPASSED (AST assertion over _enhanced_stream_chat + the live
    402 function it calls).

These modules import cleanly under a minimal interpreter (httpx + app.db only),
mirroring how the RLS proof imports app.db — so this runs wherever that one does.

Env (set by the caller BEFORE import — engines are built at import time):
  MIGRATION_DATABASE_URL  owner/admin DSN (superuser)      — DDL + migrations + writes
  DATABASE_URL            app-role DSN (brigade_app_login)  — RLS-subject reads

Exit code 0 only if every assertion holds; 1 otherwise.
"""
import ast
import asyncio
import inspect
import os
import sys
import uuid

from sqlalchemy import text

# Importing app.db.database builds `engine` (app-role) + `migration_engine`
# (owner) from the env DSNs already set by the shell.
import app.db.models  # noqa: F401 — registers all ORM tables on Base.metadata
from app.db.database import (
    engine,            # runtime app-role engine (DATABASE_URL) — subject to RLS
    migration_engine,  # owner/admin engine (MIGRATION_DATABASE_URL)
    init_db,
    provision_app_role,
    verify_app_role_not_bypassing,
)
from app.db import usage_ledger as UL
from app.integrations import metering as METER
from app.integrations import lago as LAGO

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


async def set_org(conn, org_id):
    """Exactly what middleware._bind_org_context / scheduler._bind_org run."""
    await conn.execute(
        text("SELECT set_config('app.current_org_id', :org, false)"), {"org": org_id}
    )


class _FakeUser:
    """Minimal AuthUser stand-in for the preflight (role + org_id are all it reads)."""
    def __init__(self, role, org_id):
        self.role = role
        self.org_id = org_id


async def main():
    print("=" * 78)
    print("PHASE 0 — Drive real init_db(); provision app role; verify billing schema")
    print("=" * 78)
    print(f"MIGRATION_DATABASE_URL (owner)    = {os.environ['MIGRATION_DATABASE_URL']}")
    print(f"DATABASE_URL           (app-role) = {os.environ['DATABASE_URL']}")

    await init_db()  # create_all + additive migrations (+ provision + verify)
    await provision_app_role()
    posture = await verify_app_role_not_bypassing()
    check("runtime connects as NOBYPASSRLS app role",
          bool(posture) and posture.get("bypassrls") is False, str(posture))

    async with migration_engine.connect() as oc:
        # BR-3.8/3.5: usage_events is a durable, RLS-isolated tenant table.
        ue = (await oc.execute(text(
            "SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname='usage_events'"
        ))).first()
        check("usage_events table exists", bool(ue), str(ue))
        check("BR-3.5: usage_events has RLS ENABLED", bool(ue) and ue[0] is True)
        check("BR-3.5: usage_events has RLS FORCED", bool(ue) and ue[1] is True)
        pol = (await oc.execute(text(
            "SELECT polname FROM pg_policy p JOIN pg_class c ON c.oid=p.polrelid "
            "WHERE c.relname='usage_events'"
        ))).scalars().all()
        check("usage_events has an org-isolation policy",
              any("org" in (n or "") for n in pol), str(pol))
        # BR-3.6: org_billing_config exists (caps), no RLS (config/pointer table).
        cfg = (await oc.execute(text(
            "SELECT relrowsecurity FROM pg_class WHERE relname='org_billing_config'"
        ))).first()
        check("BR-3.6: org_billing_config table exists", bool(cfg), str(cfg))
        check("org_billing_config carries NO RLS (config table)",
              bool(cfg) and cfg[0] is False)

    # Orgs (organizations has no RLS — created by owner).
    async with migration_engine.begin() as oc:
        for oid, slug in ((ORG_A, "org-a"), (ORG_B, "org-b")):
            await oc.execute(text(
                "INSERT INTO organizations (id,name,slug,plan_tier,api_calls_limit,metadata) "
                "VALUES (:id,:n,:s,'free',0,'{}'::json)"
            ), {"id": oid, "n": slug, "s": slug})
    print(f"orgs: A={ORG_A}  B={ORG_B}")

    print("\n" + "=" * 78)
    print("PHASE 1 — BR-3.1/3.4: meter_usage records against the RIGHT org")
    print("=" * 78)
    # These are the EXACT calls the metered execution paths make (agent chat,
    # A2A, MCP tool, scheduled run, ...), through the shared meter_usage primitive.
    r1 = await METER.meter_usage(org_id=ORG_A, user="alice@a.test", source="agent_chat",
                                 model="local/x", tokens=100, provider="local", agent_id="ag-a")
    r2 = await METER.meter_usage(org_id=ORG_A, user=None, source="scheduled_run",
                                 model="local/x", tokens=50, provider="local", agent_id="ag-a")
    rb1 = await METER.meter_usage(org_id=ORG_B, user="bob@b.test", source="mcp_tool",
                                  event_type="tool_call", tokens=0, tools_used=["calculator"])
    rb2 = await METER.meter_usage(org_id=ORG_B, user="bob@b.test", source="agent_chat",
                                  model="local/y", tokens=30, provider="local", agent_id="ag-b")
    check("meter_usage returns a durable ledger row id (org A)", bool(r1) and bool(r2),
          f"{r1}, {r2}")
    # No-org metering is a no-op (never bill a shared/global identity).
    r_noorg = await METER.meter_usage(org_id=None, user="nobody@x", source="agent_chat", tokens=999)
    check("BR-3.1: metering with NO org is a no-op (returns None)", r_noorg is None)

    usage_a = await UL.org_period_usage(ORG_A)
    usage_b = await UL.org_period_usage(ORG_B)
    print(f"org A usage: {usage_a}")
    print(f"org B usage: {usage_b}")
    check("org A ledger tokens == 150 (100+50, ONLY A's)", usage_a["tokens"] == 150,
          f"tokens={usage_a['tokens']}")
    check("org A ledger events == 2", usage_a["events"] == 2, f"events={usage_a['events']}")
    check("org B ledger tokens == 30 (ONLY B's; the 999 no-org call excluded)",
          usage_b["tokens"] == 30, f"tokens={usage_b['tokens']}")
    check("org B ledger events == 2", usage_b["events"] == 2, f"events={usage_b['events']}")

    # BR-3.1: the durable row's external_customer_id IS the org (billing subject).
    async with migration_engine.connect() as oc:
        ext = (await oc.execute(text(
            "SELECT DISTINCT external_customer_id FROM usage_events WHERE org_id=:o"
        ), {"o": ORG_A})).scalars().all()
    check("BR-3.1: usage_events.external_customer_id == org_id (billing subject)",
          ext == [ORG_A], str(ext))

    print("\n" + "=" * 78)
    print("PHASE 2 — BR-3.1: Lago event keys on the ORG as external_customer_id")
    print("=" * 78)
    captured = {}

    async def _capture(envelope, mirror):
        captured["env"] = envelope
        return True

    _orig = LAGO._post_event
    LAGO._post_event = _capture
    try:
        await LAGO.emit_ai_api_call(user="alice@a.test", model="local/x", tokens=100,
                                    cost=0.01, org_id=ORG_A)
    finally:
        LAGO._post_event = _orig
    ev = (captured.get("env") or {}).get("event", {})
    check("BR-3.1: Lago external_customer_id == org_id", ev.get("external_customer_id") == ORG_A,
          str(ev.get("external_customer_id")))
    check("BR-3.1: Lago properties still carry the user (per-user attribution)",
          (ev.get("properties") or {}).get("user") == "alice@a.test")
    check("BR-3.1: Lago properties carry org_id",
          (ev.get("properties") or {}).get("org_id") == ORG_A)

    print("\n" + "=" * 78)
    print("PHASE 3 — BR-3.6: over-cap org gets 402 (under-cap / admin / soft do NOT)")
    print("=" * 78)
    await UL.set_org_cap(ORG_A, monthly_token_cap=100, hard_stop=True)  # A has 150 > 100
    dec_a = await UL.org_over_cap(ORG_A)
    dec_b = await UL.org_over_cap(ORG_B)
    check("org A is OVER its 100-token cap (150 used)", dec_a["over"] is True, dec_a.get("reason"))
    check("org B is UNDER cap (no cap configured)", dec_b["over"] is False)

    from fastapi import HTTPException
    # over-cap non-admin → 402
    raised = None
    try:
        await METER.enforce_org_cap_or_402(_FakeUser(role="operator", org_id=ORG_A))
    except HTTPException as e:
        raised = e
    check("BR-3.6: over-cap org → HTTPException 402", raised is not None and raised.status_code == 402,
          f"status={getattr(raised,'status_code',None)}")
    check("BR-3.6: 402 detail identifies org_cap_reached",
          bool(raised) and isinstance(raised.detail, dict) and raised.detail.get("error") == "org_cap_reached",
          str(getattr(raised, "detail", None))[:120])
    # under-cap non-admin → no raise
    ok_b = True
    try:
        await METER.enforce_org_cap_or_402(_FakeUser(role="operator", org_id=ORG_B))
    except HTTPException:
        ok_b = False
    check("BR-3.6: under-cap org is NOT blocked", ok_b)
    # admin over-cap → no raise (admin short-circuit)
    ok_admin = True
    try:
        await METER.enforce_org_cap_or_402(_FakeUser(role="admin", org_id=ORG_A))
    except HTTPException:
        ok_admin = False
    check("BR-3.6: admin is never capped (even over-cap org)", ok_admin)
    # soft cap (hard_stop=False) → never trips
    await UL.set_org_cap(ORG_A, monthly_token_cap=100, hard_stop=False)
    dec_soft = await UL.org_over_cap(ORG_A)
    check("BR-3.6: hard_stop=False never trips (soft/observe-only)", dec_soft["over"] is False)
    await UL.set_org_cap(ORG_A, monthly_token_cap=100, hard_stop=True)  # restore

    print("\n" + "=" * 78)
    print("PHASE 4 — BR-3.4/3.5: usage_events RLS — org A usage INVISIBLE to org B")
    print("=" * 78)
    async with engine.connect() as ac:  # the NOBYPASSRLS app role
        await set_org(ac, ORG_A)
        na = await scalar(ac, "SELECT count(*) FROM usage_events")
        check("app-role bound to A sees A's 2 usage rows", na == 2, f"count={na}")
        await set_org(ac, ORG_B)
        nb = await scalar(ac, "SELECT count(*) FROM usage_events")
        n_a_from_b = await scalar(ac, "SELECT count(*) FROM usage_events WHERE org_id=:o", o=ORG_A)
        check("app-role bound to B sees B's 2 usage rows", nb == 2, f"count={nb}")
        check("BR-3.4: org A usage is INVISIBLE to org B (RLS)", n_a_from_b == 0,
              f"A-rows-seen-by-B={n_a_from_b}")
        # WITH CHECK: B cannot forge a usage row for A.
        wrote_a_as_b = None
        try:
            await ac.execute(text(
                "INSERT INTO usage_events (id,org_id,external_customer_id,event_type,source,tokens,cost) "
                "VALUES (gen_random_uuid(),:o,:o,'ai_api_call','agent_chat',5,0.0)"
            ), {"o": ORG_A})
            wrote_a_as_b = True
        except Exception:
            wrote_a_as_b = False
        check("BR-3.4: org B cannot INSERT a usage row for org A (WITH CHECK)",
              wrote_a_as_b is False)
        await ac.rollback()

    print("\n" + "=" * 78)
    print("PHASE 5 — BR-3.5: the streaming shim now GATES + METERS (was bypassed)")
    print("=" * 78)
    # Static/AST assertion over the REAL _enhanced_stream_chat body: prove the
    # previously-bypassed gates + metering are wired INTO that function (not merely
    # elsewhere in the file). Read the source without importing the heavy module.
    src_path = os.path.join(os.path.dirname(__file__), "..", "app", "api", "openai_compat_routes.py")
    with open(os.path.abspath(src_path), "r") as fh:
        tree = ast.parse(fh.read())
    fn = next((n for n in ast.walk(tree)
               if isinstance(n, ast.AsyncFunctionDef) and n.name == "_enhanced_stream_chat"), None)
    check("_enhanced_stream_chat exists", fn is not None)
    # ast.dump includes every Name/Attribute id, so substring checks are precise
    # (they match a real call node inside the function, not a comment elsewhere).
    body = ast.dump(fn) if fn else ""
    for needed, why in [
        ("_enforce_billing_or_402", "credits preflight (402)"),
        ("enforce_org_cap_or_402", "per-org cap preflight (402)"),
        ("evaluate_agent_access", "per-agent RBAC (403)"),
        ("_meter_chat_to_lago", "metering after the stream"),
    ]:
        check(f"BR-3.5: streaming shim now calls {needed} ({why})", needed in body)

    print("\n" + "=" * 78)
    print(f"RESULT: {len(PASSES)} passed, {len(FAILURES)} failed")
    print("=" * 78)
    if FAILURES:
        print("FAILURES:")
        for f in FAILURES:
            print(f"  - {f}")
    sys.exit(1 if FAILURES else 0)


if __name__ == "__main__":
    asyncio.run(main())
