"""BR-4 durable state — Postgres persistence for workflow + Ralph executions.

Before BR-4 the 3-tier ``WorkflowEngine`` kept every ``WorkflowExecution`` (incl.
HITL checkpoint state) in an in-memory dict, and the Ralph engine wrote its
``RalphWorkflowState`` to a per-process ``.ralph/*.json`` file. Both were LOST on
restart and WRONG with two replicas. This module is the write-through durable
mirror: the engines upsert the full pydantic object (serialised to a JSON dict)
on each state transition and rehydrate the in-flight set on startup.

Deliberately DEPENDENCY-LIGHT + MODEL-AGNOSTIC, and it lives in ``app.db`` (not
``app.workflows``) ON PURPOSE: it imports only ``app.db`` and operates purely on
plain dicts + scalar columns, so importing it never triggers the heavy
``app.workflows`` package ``__init__`` (which eagerly imports the engine + the
whole tool stack) and there is no engine ↔ store import cycle. The CALLERS do the
pydantic (de)serialisation: they pass ``data = json.loads(obj.model_dump_json())``
in, and reconstruct with ``Model.model_validate(data)`` on the way out. That also
makes this layer trivially unit-testable against an ephemeral Postgres.

Tenancy (mirrors the scheduler): all reads/writes use ``admin_session`` — the
RLS-exempt owner/admin factory — because these engines are trusted SYSTEM
components that enumerate + rehydrate across every org (exactly like
``scheduler.reload_all``). The two tables carry NO RLS (see the 20260719_01
migration); ``org_id`` is a best-effort attribution pointer supplied by the
caller, never an isolation boundary. Every function is best-effort + LOUD: a
transient DB error is logged, never raised, so a hiccup can't crash a running
workflow or startup.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import select

from app.db.database import admin_session
from app.db.models import RalphExecutionRecord, WorkflowExecutionRecord

logger = logging.getLogger(__name__)

# Non-terminal workflow states rehydrated on startup so an in-flight execution
# (and any pending human-approval checkpoint) survives a restart.
_INFLIGHT_WORKFLOW_STATES = ("pending", "running", "waiting_checkpoint", "paused")


# ── Hierarchical WorkflowExecution ─────────────────────────────────────────

async def save_workflow_execution(
    *,
    id: str,
    workflow_id: str,
    workflow_name: Optional[str],
    state: str,
    data: Dict[str, Any],
    current_step: Optional[str] = None,
    pending_checkpoint: Optional[str] = None,
    mission_id: Optional[str] = None,
    started_at: Optional[datetime] = None,
    completed_at: Optional[datetime] = None,
    org_id: Optional[str] = None,
) -> None:
    """Upsert a WorkflowExecution snapshot (``data`` = its model_dump). Loud + safe."""
    try:
        async with admin_session() as session:
            row = await session.get(WorkflowExecutionRecord, id)
            if row is None:
                session.add(
                    WorkflowExecutionRecord(
                        id=id,
                        workflow_id=workflow_id,
                        workflow_name=workflow_name,
                        org_id=org_id,
                        state=state,
                        current_step=current_step,
                        pending_checkpoint=pending_checkpoint,
                        mission_id=mission_id,
                        data=data,
                        started_at=started_at,
                        completed_at=completed_at,
                    )
                )
            else:
                row.workflow_id = workflow_id
                row.workflow_name = workflow_name
                # Never blank a known org with a NULL from a later context-less write.
                if org_id is not None:
                    row.org_id = org_id
                row.state = state
                row.current_step = current_step
                row.pending_checkpoint = pending_checkpoint
                row.mission_id = mission_id
                row.data = data
                row.started_at = started_at
                row.completed_at = completed_at
            await session.commit()
    except Exception as exc:  # noqa: BLE001
        logger.error("BR-4 save_workflow_execution(%s) failed: %s", id, exc)


async def load_workflow_execution_data(execution_id: str) -> Optional[Dict[str, Any]]:
    """Return the persisted ``data`` blob for one execution (caller reconstructs)."""
    try:
        async with admin_session() as session:
            row = await session.get(WorkflowExecutionRecord, execution_id)
            return dict(row.data) if row is not None else None
    except Exception as exc:  # noqa: BLE001
        logger.error("BR-4 load_workflow_execution_data(%s) failed: %s", execution_id, exc)
        return None


async def load_inflight_workflow_execution_data() -> List[Dict[str, Any]]:
    """Return the ``data`` blob of every non-terminal execution (startup rehydrate)."""
    try:
        async with admin_session() as session:
            rows = (
                await session.execute(
                    select(WorkflowExecutionRecord).where(
                        WorkflowExecutionRecord.state.in_(_INFLIGHT_WORKFLOW_STATES)
                    )
                )
            ).scalars().all()
        return [dict(r.data) for r in rows]
    except Exception as exc:  # noqa: BLE001
        logger.error("BR-4 load_inflight_workflow_execution_data failed: %s", exc)
        return []


# ── Ralph self-correction state ────────────────────────────────────────────

async def save_ralph_execution(
    *,
    execution_id: str,
    workflow_id: str,
    is_complete: bool,
    is_paused: bool,
    final_outcome: Optional[str],
    data: Dict[str, Any],
    org_id: Optional[str] = None,
) -> None:
    """Upsert a RalphWorkflowState snapshot (``data`` = its model_dump). Loud + safe."""
    try:
        async with admin_session() as session:
            row = await session.get(RalphExecutionRecord, execution_id)
            if row is None:
                session.add(
                    RalphExecutionRecord(
                        execution_id=execution_id,
                        workflow_id=workflow_id,
                        org_id=org_id,
                        is_complete=bool(is_complete),
                        is_paused=bool(is_paused),
                        final_outcome=final_outcome,
                        data=data,
                    )
                )
            else:
                row.workflow_id = workflow_id
                if org_id is not None:
                    row.org_id = org_id
                row.is_complete = bool(is_complete)
                row.is_paused = bool(is_paused)
                row.final_outcome = final_outcome
                row.data = data
            await session.commit()
    except Exception as exc:  # noqa: BLE001
        logger.error("BR-4 save_ralph_execution(%s) failed: %s", execution_id, exc)


async def load_ralph_execution_data(execution_id: str) -> Optional[Dict[str, Any]]:
    """Return the persisted ``data`` blob for one Ralph execution."""
    try:
        async with admin_session() as session:
            row = await session.get(RalphExecutionRecord, execution_id)
            return dict(row.data) if row is not None else None
    except Exception as exc:  # noqa: BLE001
        logger.error("BR-4 load_ralph_execution_data(%s) failed: %s", execution_id, exc)
        return None


async def load_inflight_ralph_execution_data() -> List[Dict[str, Any]]:
    """Return the ``data`` blob of every non-complete Ralph execution (rehydrate)."""
    try:
        async with admin_session() as session:
            rows = (
                await session.execute(
                    select(RalphExecutionRecord).where(
                        RalphExecutionRecord.is_complete.is_(False)
                    )
                )
            ).scalars().all()
        return [dict(r.data) for r in rows]
    except Exception as exc:  # noqa: BLE001
        logger.error("BR-4 load_inflight_ralph_execution_data failed: %s", exc)
        return []
