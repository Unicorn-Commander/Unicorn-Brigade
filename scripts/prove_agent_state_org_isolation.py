"""Audit-2 F2 — AgentState shared-singleton cross-tenant task-leak proof.

A PURE async/unit exercise of the REAL OrchestrationEventBus (no Postgres). It
drives the actual ``app.orchestration.event_bus`` singleton + its emit helpers +
its public getters, exactly as the orchestration routes do.

What it proves (finding F2): a SHARED agent (one ``agent_id`` — e.g. gunny —
across every tenant) that is driven by two orgs no longer leaks one org's task
text to the other. Pre-fix, ``_agent_states`` was keyed by ``agent_id`` alone, so
the shared agent was ONE ``AgentState`` object: the first writer stamped its
org, later writers (other orgs) overwrote ``current_task``/``current_mission``,
and the first org then read the second org's task via ``/state`` +
``/agents/active`` (both pass its ``event_visible_to_org`` filter because the
singleton kept the first org's stamp). The fix keys state by ``(org_id,
agent_id)``, so each tenant gets its own segregated ``AgentState`` for the same
shared agent and the ``.values()`` readers still filter cleanly by ``s.org_id``.

Exit code 0 only if every assertion holds.
"""
import asyncio
import json
import sys
import uuid

from app.orchestration.event_bus import (
    event_bus,
    emit_agent_started,
    emit_tool_call,
    current_org_id_var,
    event_visible_to_org,
    AgentState,
)

ORG_A = str(uuid.uuid4())
ORG_B = str(uuid.uuid4())
SHARED = "gunny"           # one shared agent_id, driven by BOTH orgs
TASK_A = "org-A-SECRET: reconcile org A payroll"
TASK_B = "org-B-SECRET: draft org B acquisition memo"

FAILURES = []
PASSES = []


def check(label, condition, detail=""):
    tag = "PASS" if condition else "FAIL"
    (PASSES if condition else FAILURES).append(label)
    print(f"  [{tag}] {label}" + (f"  — {detail}" if detail else ""))


async def emit_as(org_id, coro):
    """Publish an event with ``org_id`` bound in the per-task context — exactly
    how middleware._bind_org_context / the scheduler bind current_org_id_var
    before the emitting work runs. publish() reads it to stamp the event."""
    token = current_org_id_var.set(org_id)
    try:
        await coro
    finally:
        current_org_id_var.reset(token)


def active_visible_to(org_id):
    """The /agents/active route body: get_active_agents() filtered by org."""
    return [
        s for s in event_bus.get_active_agents()
        if event_visible_to_org(s.org_id, org_id)
    ]


async def main():
    print("=" * 78)
    print("PHASE 1 — two orgs drive the SAME shared agent_id 'gunny'")
    print("=" * 78)
    # Org A starts gunny on its secret task; then org B starts the SAME gunny on
    # ITS secret task. Pre-fix, the second emit clobbers the one shared object.
    await emit_as(ORG_A, emit_agent_started(SHARED, "Gunny", task=TASK_A, mission_id="mission-A"))
    await emit_as(ORG_B, emit_agent_started(SHARED, "Gunny", task=TASK_B, mission_id="mission-B"))

    state_a = event_bus.get_agent_state(SHARED, ORG_A)
    state_b = event_bus.get_agent_state(SHARED, ORG_B)

    check("org A has its OWN gunny state", state_a is not None)
    check("org B has its OWN gunny state", state_b is not None)
    check("the two shared-agent states are DISTINCT objects (not one singleton)",
          state_a is not None and state_b is not None and state_a is not state_b)
    check("F2 FIX: org A's gunny.current_task is org A's task (NOT clobbered by org B)",
          bool(state_a) and state_a.current_task == TASK_A,
          f"current_task={state_a.current_task if state_a else None!r}")
    check("F2 FIX: org B's gunny.current_task is org B's task",
          bool(state_b) and state_b.current_task == TASK_B,
          f"current_task={state_b.current_task if state_b else None!r}")
    check("org A's gunny state is stamped org A", bool(state_a) and state_a.org_id == ORG_A,
          f"org_id={state_a.org_id if state_a else None}")
    check("org B's gunny state is stamped org B", bool(state_b) and state_b.org_id == ORG_B,
          f"org_id={state_b.org_id if state_b else None}")
    check("org A's gunny mission is mission-A (per-org mission not crossed)",
          bool(state_a) and state_a.current_mission == "mission-A",
          f"mission={state_a.current_mission if state_a else None}")
    check("org B's gunny mission is mission-B",
          bool(state_b) and state_b.current_mission == "mission-B",
          f"mission={state_b.current_mission if state_b else None}")
    # Two segregated keys exist for the one shared agent_id.
    gunny_keys = [k for k in event_bus._agent_states if k[1] == SHARED]
    check("_agent_states holds TWO (org_id, 'gunny') keys — one per tenant",
          len(gunny_keys) == 2 and (ORG_A, SHARED) in gunny_keys and (ORG_B, SHARED) in gunny_keys,
          f"keys={gunny_keys}")

    print("\n" + "=" * 78)
    print("PHASE 2 — /agents/active is org-scoped: neither org sees the other's task")
    print("=" * 78)
    a_view = active_visible_to(ORG_A)
    b_view = active_visible_to(ORG_B)
    a_tasks = [s.current_task for s in a_view if s.agent_id == SHARED]
    b_tasks = [s.current_task for s in b_view if s.agent_id == SHARED]
    check("org A /agents/active shows gunny with org A's task", TASK_A in a_tasks, f"a_tasks={a_tasks}")
    check("F2 FIX: org A /agents/active does NOT expose org B's task", TASK_B not in a_tasks)
    check("org B /agents/active shows gunny with org B's task", TASK_B in b_tasks, f"b_tasks={b_tasks}")
    check("F2 FIX: org B /agents/active does NOT expose org A's task", TASK_A not in b_tasks)
    check("org A sees exactly ONE gunny in active (its own, not doubled)",
          len([s for s in a_view if s.agent_id == SHARED]) == 1)

    print("\n" + "=" * 78)
    print("PHASE 3 — /state snapshot is org-scoped (same event_visible_to_org rule)")
    print("=" * 78)
    snap_a = event_bus.get_state_snapshot(viewer_org_id=ORG_A)
    snap_b = event_bus.get_state_snapshot(viewer_org_id=ORG_B)
    a_json = json.dumps(snap_a)
    b_json = json.dumps(snap_b)
    a_snap_gunny = [s for s in snap_a["agentStates"] if s["agentId"] == SHARED]
    check("org A /state shows gunny with org A's task",
          any(s.get("currentTask") == TASK_A for s in a_snap_gunny), f"gunny={a_snap_gunny}")
    check("F2 FIX: org A /state snapshot NEVER contains org B's secret task text",
          TASK_B not in a_json, "TASK_B absent from serialized org-A snapshot")
    check("F2 FIX: org B /state snapshot NEVER contains org A's secret task text",
          TASK_A not in b_json, "TASK_A absent from serialized org-B snapshot")
    check("org A /state gunny carries org A's mission only",
          any(s.get("currentMission") == "mission-A" for s in a_snap_gunny)
          and all(s.get("currentMission") != "mission-B" for s in a_snap_gunny))

    print("\n" + "=" * 78)
    print("PHASE 4 — unattributed + per-org control (no over/under-sharing)")
    print("=" * 78)
    # Unattributed (system) work — no org bound — is withheld from both tenants.
    await emit_as(None, emit_agent_started("the-general", "The General", task="system sweep", mission_id=None))
    check("unattributed agent state is NOT visible to org A",
          all(s.agent_id != "the-general" for s in active_visible_to(ORG_A)))
    check("unattributed agent state is NOT visible to org B",
          all(s.agent_id != "the-general" for s in active_visible_to(ORG_B)))
    # A genuinely per-org agent (distinct id) stays scoped to its own org.
    await emit_as(ORG_A, emit_agent_started("col-a-only", "Col A", task="org A only", mission_id="mA2"))
    check("per-org agent col-a-only visible to org A",
          any(s.agent_id == "col-a-only" for s in active_visible_to(ORG_A)))
    check("per-org agent col-a-only NOT visible to org B",
          all(s.agent_id != "col-a-only" for s in active_visible_to(ORG_B)))

    print("\n" + "=" * 78)
    print("PHASE 5 — later same-org events UPDATE (don't fork) the org's own state")
    print("=" * 78)
    # A follow-up tool_call from org A must update org A's existing gunny state
    # (still one per-org object), never create a second or touch org B's.
    await emit_as(ORG_A, emit_tool_call(SHARED, "Gunny", tool_name="calculator", arguments={}, mission_id="mission-A"))
    state_a2 = event_bus.get_agent_state(SHARED, ORG_A)
    check("org A's gunny state is still a SINGLE object after a follow-up event",
          len([k for k in event_bus._agent_states if k[1] == SHARED]) == 2)
    check("org A's gunny moved to 'executing' on tool_call (state advanced in place)",
          bool(state_a2) and state_a2.status == "executing", f"status={state_a2.status if state_a2 else None}")
    check("org B's gunny task STILL intact after org A's follow-up (no cross-write)",
          bool(event_bus.get_agent_state(SHARED, ORG_B))
          and event_bus.get_agent_state(SHARED, ORG_B).current_task == TASK_B)

    print("\n" + "=" * 78)
    print("PHASE 6 — counterfactual: agent_id-only keying WOULD have leaked (the bug)")
    print("=" * 78)
    # Illustrative: reproduce the PRE-FIX single-key store to show the collapse the
    # fix prevents (this touches a throwaway local dict, NOT the real bus).
    legacy = {}
    for org, task in ((ORG_A, TASK_A), (ORG_B, TASK_B)):
        st = legacy.get(SHARED)
        if st is None:
            st = legacy[SHARED] = AgentState(agent_id=SHARED, agent_name="Gunny", org_id=org)
        st.current_task = task  # later writer clobbers
    leaked = legacy[SHARED]
    check("pre-fix single-key store collapses gunny to ONE object",
          len([k for k in legacy if k == SHARED]) == 1)
    check("pre-fix object keeps the FIRST org's stamp but the SECOND org's task (the leak)",
          leaked.org_id == ORG_A and leaked.current_task == TASK_B,
          f"org_id={leaked.org_id} current_task={leaked.current_task!r}")
    check("→ under the old code org A's filter (org_id==A) would have shown org B's task",
          event_visible_to_org(leaked.org_id, ORG_A) and leaked.current_task == TASK_B)

    print("\n" + "=" * 78)
    print(f"RESULT: {len(PASSES)} passed, {len(FAILURES)} failed")
    if FAILURES:
        print("FAILURES:")
        for f in FAILURES:
            print(f"   - {f}")
    print("=" * 78)
    sys.exit(1 if FAILURES else 0)


if __name__ == "__main__":
    asyncio.run(main())
