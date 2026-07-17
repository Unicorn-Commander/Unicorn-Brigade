"""BR-4 durable-state proof — workflow/checkpoint/Ralph persistence + scheduler
leader election, driven against an EPHEMERAL throwaway Postgres.

Proves the two BR-4 durability gaps end-to-end:

  (a) A hierarchical WorkflowExecution — INCLUDING a pending human-approval
      checkpoint and per-step results — and a Ralph self-correction state survive
      a simulated process restart: the exact serialize→DB→deserialize path the
      engines use round-trips losslessly, and the in-flight (non-terminal) set is
      what a fresh process would rehydrate. Completing an execution drops it out
      of that set (so a finished run is not re-hydrated forever).

  (b) With two "scheduler instances" (two PgAdvisoryLeaderLock holders on one DB)
      only ONE becomes leader; the other is a follower whose acquire returns False
      (so, in the scheduler, its reload_all/upsert/remove no-op → it never fires).

  (c) On leader "death" the follower ACQUIRES: both a graceful release AND a hard
      crash (connection dropped without unlock) free the session-scoped advisory
      lock so a standby takes over.

Serialization is exercised with the REAL pydantic models (WorkflowExecution /
RalphWorkflowState) loaded STANDALONE via importlib — they have no top-level app
imports, so this avoids dragging in the heavy app.workflows package __init__ (the
engine + full tool stack) that a plain ``import`` would trigger.

Env (set by run_durable_state_proof.sh BEFORE import — engines build at import):
  MIGRATION_DATABASE_URL / DATABASE_URL  → the throwaway Postgres.
Exit 0 iff every assertion holds.
"""

import asyncio
import importlib.util
import json
import os
import sys
import uuid
from datetime import datetime

# Register ORM tables on Base.metadata + build the engines from env (light).
import app.db.models  # noqa: F401
from app.db import execution_store as store
from app.db.database import engine, init_db, migration_engine
from app.services.leader_election import PgAdvisoryLeaderLock, lock_key_from_name

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FAILURES = []
PASSES = []


def check(label, condition, detail=""):
    tag = "PASS" if condition else "FAIL"
    (PASSES if condition else FAILURES).append(label)
    print(f"  [{tag}] {label}" + (f"  — {detail}" if detail else ""))


def _load_standalone(mod_name, relpath):
    """Load a single .py file as a standalone module (bypasses the package
    __init__). Safe here because schema.py / ralph_engine.py have NO top-level
    app imports."""
    path = os.path.join(_ROOT, relpath)
    spec = importlib.util.spec_from_file_location(mod_name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


_schema = _load_standalone("brigade_wf_schema_standalone", "app/workflows/schema.py")
_ralph = _load_standalone("brigade_ralph_standalone", "app/workflows/ralph_engine.py")
WorkflowExecution = _schema.WorkflowExecution
WorkflowExecutionState = _schema.WorkflowExecutionState
StepExecution = _schema.StepExecution
StepExecutionState = _schema.StepExecutionState
RalphWorkflowState = _ralph.RalphWorkflowState


async def _persist_execution(ex):
    """Byte-for-byte mirror of WorkflowEngine._persist (the real write path)."""
    state = ex.state.value if hasattr(ex.state, "value") else str(ex.state)
    await store.save_workflow_execution(
        id=ex.id,
        workflow_id=ex.workflow_id,
        workflow_name=ex.workflow_name,
        state=state,
        data=json.loads(ex.model_dump_json()),
        current_step=ex.current_step,
        pending_checkpoint=ex.pending_checkpoint,
        mission_id=ex.mission_id,
        started_at=ex.started_at,
        completed_at=ex.completed_at,
    )


async def _persist_ralph(st):
    """Mirror of RalphWorkflowEngine.persist_db."""
    await store.save_ralph_execution(
        execution_id=st.execution_id,
        workflow_id=st.workflow_id,
        is_complete=bool(st.is_complete),
        is_paused=bool(st.is_paused),
        final_outcome=st.final_outcome,
        data=json.loads(st.model_dump_json()),
    )


async def part_a_workflow():
    print("\n" + "=" * 78)
    print("PART A(1) — Hierarchical workflow + HITL checkpoint survives a restart")
    print("=" * 78)

    ex = WorkflowExecution(
        workflow_id="investment_due_diligence",
        workflow_name="Investment Due Diligence",
        state=WorkflowExecutionState.WAITING_CHECKPOINT,
        started_at=datetime.utcnow(),
        current_step="step-3",
        pending_checkpoint="cp-approve-deal-memo",
    )
    ex.step_executions["step-1"] = StepExecution(
        step_id="step-1",
        state=StepExecutionState.COMPLETED,
        outputs={"risk_score": 87, "note": "clean"},
        tokens_used=1200,
    )
    ex.checkpoint_responses["cp-earlier"] = {"approved": True, "by": "alice"}
    ex.total_cost = 0.42
    ex.total_tokens = 1200
    await _persist_execution(ex)
    print(f"persisted execution {ex.id} in WAITING_CHECKPOINT (pending cp-approve-deal-memo)")

    # ---- simulate process restart: a brand-new process reads the durable row ----
    data = await store.load_workflow_execution_data(ex.id)
    check("workflow execution row persisted to Postgres", data is not None)
    ex2 = WorkflowExecution.model_validate(data)
    check("state WAITING_CHECKPOINT survived the restart",
          ex2.state == WorkflowExecutionState.WAITING_CHECKPOINT, str(ex2.state))
    check("pending_checkpoint survived the restart",
          ex2.pending_checkpoint == "cp-approve-deal-memo", str(ex2.pending_checkpoint))
    check("current_step survived", ex2.current_step == "step-3", str(ex2.current_step))
    check("completed step-1 result survived",
          ex2.step_executions.get("step-1") is not None
          and ex2.step_executions["step-1"].outputs == {"risk_score": 87, "note": "clean"},
          str(ex2.step_executions.get("step-1")))
    check("earlier checkpoint response survived",
          ex2.checkpoint_responses.get("cp-earlier") == {"approved": True, "by": "alice"})
    check("aggregated cost/tokens survived",
          ex2.total_cost == 0.42 and ex2.total_tokens == 1200,
          f"cost={ex2.total_cost} tokens={ex2.total_tokens}")

    # ---- the rehydrate set a fresh WorkflowEngine.rehydrate() would load ----
    inflight = await store.load_inflight_workflow_execution_data()
    check("in-flight execution is in the startup rehydrate set",
          any(d["id"] == ex.id for d in inflight), f"n_inflight={len(inflight)}")
    cache = {}
    for d in inflight:
        e = WorkflowExecution.model_validate(d)
        cache[e.id] = e
    check("rehydrate repopulates a fresh in-memory cache with the checkpoint intact",
          ex.id in cache and cache[ex.id].pending_checkpoint == "cp-approve-deal-memo")

    # ---- completing it removes it from the rehydrate set ----
    ex2.state = WorkflowExecutionState.COMPLETED
    ex2.completed_at = datetime.utcnow()
    await _persist_execution(ex2)
    inflight2 = await store.load_inflight_workflow_execution_data()
    check("a COMPLETED execution drops out of the in-flight rehydrate set",
          not any(d["id"] == ex.id for d in inflight2))

    print("\n" + "=" * 78)
    print("PART A(2) — Ralph self-correction state survives a restart")
    print("=" * 78)
    st = RalphWorkflowState(
        workflow_id="investment_due_diligence",
        execution_id="ralph_dd_" + uuid.uuid4().hex[:8],
    )
    st.tasks["task_1"] = {
        "id": "task_1", "description": "research background", "status": "completed",
        "assigned_to": "research", "dependencies": [], "attempts": 1, "max_attempts": 3,
        "error_history": [], "result": {"ok": True},
        "started_at": datetime.utcnow(), "completed_at": datetime.utcnow(),
    }
    st.tasks["task_2"] = {
        "id": "task_2", "description": "analyze financials", "status": "failed",
        "assigned_to": "finance", "dependencies": ["task_1"], "attempts": 2, "max_attempts": 3,
        "error_history": ["timeout", "rate-limited"], "result": None,
        "started_at": None, "completed_at": None,
    }
    st.current_iteration = 1
    st.is_paused = True
    st.pending_guidance = "focus on Q4 2025 only"
    await _persist_ralph(st)
    print(f"persisted ralph execution {st.execution_id} (paused, iteration 1, 1 failed task)")

    rdata = await store.load_ralph_execution_data(st.execution_id)
    check("ralph execution row persisted to Postgres", rdata is not None)
    st2 = RalphWorkflowState.model_validate(rdata)
    check("ralph current_iteration survived", st2.current_iteration == 1, str(st2.current_iteration))
    check("ralph is_paused survived", st2.is_paused is True, str(st2.is_paused))
    check("ralph pending_guidance survived",
          st2.pending_guidance == "focus on Q4 2025 only", str(st2.pending_guidance))
    check("ralph task_1 completed-result survived",
          st2.tasks["task_1"]["result"] == {"ok": True})
    check("ralph task_2 failure error_history survived",
          st2.tasks["task_2"]["error_history"] == ["timeout", "rate-limited"],
          str(st2.tasks["task_2"]["error_history"]))
    inflight_r = await store.load_inflight_ralph_execution_data()
    check("in-flight ralph execution is in the startup rehydrate set",
          any(d["execution_id"] == st.execution_id for d in inflight_r))

    st2.is_complete = True
    st2.is_paused = False
    st2.final_outcome = "success"
    await _persist_ralph(st2)
    inflight_r2 = await store.load_inflight_ralph_execution_data()
    check("a completed ralph execution drops out of the in-flight rehydrate set",
          not any(d["execution_id"] == st.execution_id for d in inflight_r2))


async def part_bc_leader_election():
    print("\n" + "=" * 78)
    print("PART B — two scheduler instances: only ONE becomes leader (follower no-ops)")
    print("=" * 78)
    dsn = os.environ["MIGRATION_DATABASE_URL"]
    key = lock_key_from_name("brigade_scheduler_proof")

    a = PgAdvisoryLeaderLock(dsn, key)
    b = PgAdvisoryLeaderLock(dsn, key)
    got_a = await a.try_acquire()
    got_b = await b.try_acquire()
    check("instance A acquires scheduler leadership", got_a is True, f"A={got_a}")
    check("instance B is a follower (lock already held) → its reload/upsert no-op",
          got_b is False, f"B={got_b}")
    check("EXACTLY ONE leader across two instances", (got_a, got_b) == (True, False),
          f"(A,B)=({got_a},{got_b})")
    check("A.held / B.held reflect leadership", a.held is True and b.held is False,
          f"A.held={a.held} B.held={b.held}")
    check("leader re-acquire is idempotent (stays True, no double-lock)",
          (await a.try_acquire()) is True)
    check("follower re-attempt still False while leader alive",
          (await b.try_acquire()) is False)

    print("\n" + "=" * 78)
    print("PART C — on leader death the follower ACQUIRES (graceful + crash)")
    print("=" * 78)
    # (c.i) graceful release → follower B takes over.
    await a.release()
    got_b2 = await b.try_acquire()
    check("after leader A releases, follower B ACQUIRES (takeover)", got_b2 is True, f"B={got_b2}")
    c = PgAdvisoryLeaderLock(dsn, key)
    check("a new instance C cannot acquire while B now leads",
          (await c.try_acquire()) is False)

    # (c.ii) HARD CRASH: drop B's connection WITHOUT unlocking (simulates the
    # process dying). NullPool means the physical session actually ends, so
    # Postgres frees the session-scoped lock and a standby can take over.
    await b._drop_conn()
    b._held = False
    d = PgAdvisoryLeaderLock(dsn, key)
    got_d = await d.try_acquire()
    check("after leader B 'crashes' (conn dropped, no unlock), instance D ACQUIRES",
          got_d is True, f"D={got_d}")
    check("C still cannot acquire while D leads", (await c.try_acquire()) is False)

    await d.release()
    await c.release()
    # after both release, a fresh acquire succeeds again.
    e = PgAdvisoryLeaderLock(dsn, key)
    check("after all release, a fresh instance can acquire again", (await e.try_acquire()) is True)
    await e.release()


async def main():
    print("=" * 78)
    print("BR-4 DURABLE STATE PROOF")
    print("=" * 78)
    print(f"DATABASE_URL           = {os.environ['DATABASE_URL']}")
    print(f"MIGRATION_DATABASE_URL = {os.environ['MIGRATION_DATABASE_URL']}")

    # Drive the REAL app schema bootstrap (create_all + additive migrations),
    # which creates workflow_executions + ralph_executions.
    await init_db()
    async with migration_engine.connect() as oc:
        from sqlalchemy import text
        tabs = (await oc.execute(text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_name IN ('workflow_executions','ralph_executions') ORDER BY table_name"
        ))).scalars().all()
    check("migration created workflow_executions + ralph_executions",
          set(tabs) == {"ralph_executions", "workflow_executions"}, str(tabs))

    await part_a_workflow()
    await part_bc_leader_election()

    print("\n" + "=" * 78)
    print(f"RESULT: {len(PASSES)} passed, {len(FAILURES)} failed")
    if FAILURES:
        print("FAILURES:")
        for f in FAILURES:
            print(f"   - {f}")
    print("=" * 78)
    await engine.dispose()
    if migration_engine is not engine:
        await migration_engine.dispose()
    sys.exit(1 if FAILURES else 0)


if __name__ == "__main__":
    asyncio.run(main())
