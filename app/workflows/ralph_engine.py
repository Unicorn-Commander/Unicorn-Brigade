# Executed by Grok (headless lane)
"""
Ralph Workflow Engine - Self-Correcting Agent Loops

Inspired by open-ralph-wiggum, this engine adds iterative self-correction
to Brigade workflows. Agents can automatically retry failed tasks with
improved context, track progress, and accept mid-execution guidance.

Key Features:
- Task breakdown with progress tracking
- Automatic retry with error feedback
- Mid-execution guidance injection
- Iteration history and learning
- Integration with hierarchical workflows
"""

import json
import asyncio
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    """Task completion status"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class IterationOutcome(str, Enum):
    """Iteration result"""
    SUCCESS = "success"
    RETRY = "retry"
    FAILED = "failed"
    NEEDS_GUIDANCE = "needs_guidance"


@dataclass
class RalphTask:
    """Individual task in the workflow breakdown"""
    id: str
    description: str
    status: TaskStatus
    assigned_to: Optional[str] = None  # agent_id
    dependencies: List[str] = None  # task_ids that must complete first
    attempts: int = 0
    max_attempts: int = 3
    error_history: List[str] = None
    result: Optional[Any] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []
        if self.error_history is None:
            self.error_history = []

    def can_execute(self, completed_task_ids: set) -> bool:
        """Check if all dependencies are satisfied"""
        return all(dep_id in completed_task_ids for dep_id in self.dependencies)

    def record_attempt(self, error: Optional[str] = None):
        """Record an execution attempt"""
        self.attempts += 1
        if error:
            self.error_history.append(error)

    def should_retry(self) -> bool:
        """Check if task should be retried"""
        return (
            self.status == TaskStatus.FAILED and
            self.attempts < self.max_attempts
        )


@dataclass
class Iteration:
    """Single iteration of workflow execution"""
    number: int
    started_at: datetime
    completed_at: Optional[datetime] = None
    outcome: Optional[IterationOutcome] = None
    tasks_completed: int = 0
    tasks_failed: int = 0
    error_summary: Optional[str] = None
    guidance_received: Optional[str] = None  # Mid-execution guidance


class RalphWorkflowState(BaseModel):
    """Complete state of a Ralph workflow execution"""
    workflow_id: str
    execution_id: str
    # Owning organization (tenancy). Stamped at state init from the launching
    # request's bound org so the in-memory registry can be tenant-scoped: a
    # non-admin caller only reaches Ralph executions whose org_id equals their
    # own. None for runs launched with no bound org (visible to admins only).
    org_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    # Task breakdown
    tasks: Dict[str, Dict] = Field(default_factory=dict)  # task_id -> RalphTask dict

    # Iteration history
    iterations: List[Dict] = Field(default_factory=list)  # Iteration dicts
    current_iteration: int = 0
    max_iterations: int = 5

    # Guidance system
    pending_guidance: Optional[str] = None
    guidance_history: List[Dict] = Field(default_factory=list)

    # Overall status
    is_complete: bool = False
    is_paused: bool = False
    final_outcome: Optional[str] = None

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class RalphWorkflowEngine:
    """
    Self-correcting workflow engine with iterative improvement.

    Wraps the standard WorkflowEngine to add:
    - Automatic task breakdown
    - Self-correction loops
    - Progress persistence
    - Mid-execution guidance
    """

    def __init__(
        self,
        workflow_id: str,
        workflow_definition: Dict,
        state_dir: Optional[Path] = None,
        on_task_complete: Optional[Callable] = None,
        on_iteration_complete: Optional[Callable] = None,
        org_id: Optional[str] = None,
    ):
        self.workflow_id = workflow_id
        self.workflow_definition = workflow_definition
        self.state_dir = state_dir or Path(".ralph")
        self.state_dir.mkdir(exist_ok=True)
        # Owning org for tenancy scoping — captured at launch by the route (from
        # the authenticated caller's bound org) and stamped onto the state so the
        # read endpoints can confine a tenant to their own executions.
        self.org_id = org_id

        # Callbacks
        self.on_task_complete = on_task_complete
        self.on_iteration_complete = on_iteration_complete

        # State
        self.state: Optional[RalphWorkflowState] = None
        self.execution_id: Optional[str] = None

    async def execute(
        self,
        inputs: Dict[str, Any],
        execution_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute workflow with self-correction.

        Returns:
            Final workflow result with iteration history
        """
        # Initialize or resume
        self.execution_id = execution_id or self._generate_execution_id()

        # Resume order: local disk cache first (fast, unchanged), then the BR-4
        # durable Postgres mirror (survives a restart / a fresh replica with no
        # local .ralph file), else start fresh.
        if not self._load_state():
            if not await self.load_db():
                self._initialize_state(inputs)

        # BR-4: persist the starting snapshot so the run is durable + visible to
        # other replicas from its first moment.
        await self.persist_db()

        # Main self-correction loop
        while not self.state.is_complete and self.state.current_iteration < self.state.max_iterations:
            iteration_result = await self._run_iteration()
            # BR-4: durably mirror the state at every iteration boundary (covers
            # RETRY / NEEDS_GUIDANCE / SUCCESS / FAILED before we act on it).
            await self.persist_db()

            if iteration_result.outcome == IterationOutcome.SUCCESS:
                self.state.is_complete = True
                self.state.final_outcome = "success"
                break

            elif iteration_result.outcome == IterationOutcome.NEEDS_GUIDANCE:
                self.state.is_paused = True
                await self._notify_needs_guidance(iteration_result)
                # Wait for guidance injection
                while self.state.is_paused:
                    await asyncio.sleep(1)
                continue

            elif iteration_result.outcome == IterationOutcome.RETRY:
                # Prepare for next iteration with error context
                self.state.current_iteration += 1
                continue

            else:  # FAILED
                self.state.is_complete = True
                self.state.final_outcome = "failed"
                break

        # Save final state (local disk + BR-4 durable Postgres mirror).
        self._save_state()
        await self.persist_db()

        # Build result
        return self._build_result()

    def _initialize_state(self, inputs: Dict[str, Any]):
        """Initialize workflow state with task breakdown"""
        # Resolve the owning org: the org captured at construction (from the
        # authenticated request), falling back to the currently-bound request
        # context if available. Stamped on the state so tenant scoping survives
        # persistence + rehydration.
        org_id = getattr(self, "org_id", None)
        if org_id is None:
            try:
                from app.orchestration.event_bus import current_org_id_var
                org_id = current_org_id_var.get() or None
            except Exception:
                org_id = None
        self.state = RalphWorkflowState(
            workflow_id=self.workflow_id,
            execution_id=self.execution_id,
            org_id=org_id,
        )

        # Break down workflow into tasks
        tasks = self._breakdown_workflow(self.workflow_definition, inputs)
        for task in tasks:
            self.state.tasks[task.id] = asdict(task)

        self._save_state()

    def _breakdown_workflow(
        self,
        workflow_def: Dict,
        inputs: Dict[str, Any]
    ) -> List[RalphTask]:
        """
        Convert workflow definition into Ralph tasks.

        For hierarchical workflows:
        - Each step becomes a task
        - Checkpoints become decision tasks
        - Dependencies follow step order
        """
        tasks = []
        steps = workflow_def.get("steps", [])

        for idx, step in enumerate(steps):
            task_id = f"task_{idx + 1}"

            # Determine dependencies (previous non-checkpoint step)
            dependencies = []
            if idx > 0:
                dependencies.append(f"task_{idx}")

            task = RalphTask(
                id=task_id,
                description=step.get("description", f"Step {idx + 1}"),
                status=TaskStatus.PENDING,
                assigned_to=step.get("team_lead") or step.get("worker"),
                dependencies=dependencies,
                max_attempts=step.get("max_retries", 3)
            )
            tasks.append(task)

        return tasks

    async def _run_iteration(self) -> Iteration:
        """Execute one iteration of the workflow"""
        iteration = Iteration(
            number=self.state.current_iteration + 1,
            started_at=datetime.now()
        )

        completed_task_ids = set(
            task_id for task_id, task_data in self.state.tasks.items()
            if task_data["status"] == TaskStatus.COMPLETED.value
        )

        tasks_completed = 0
        tasks_failed = 0
        errors = []

        # Execute tasks in dependency order
        for task_id, task_data in self.state.tasks.items():
            task = RalphTask(**task_data)

            if task.status == TaskStatus.COMPLETED:
                continue

            if not task.can_execute(completed_task_ids):
                continue

            # Execute task
            task.status = TaskStatus.IN_PROGRESS
            task.started_at = datetime.now()
            self.state.tasks[task_id] = asdict(task)
            self._save_state()

            try:
                result = await self._execute_task(task, iteration.number)
                # Executed by Grok (headless lane)
                # Count every try, including success. record_attempt(error=None)
                # is the 2df9e88 contract (docs: first-try success attempts=1,
                # fail-then-succeed attempts=2). Only the except path used to
                # increment, so a retried task that then succeeded stayed at 1.
                task.record_attempt()
                task.status = TaskStatus.COMPLETED
                task.result = result
                task.completed_at = datetime.now()
                completed_task_ids.add(task_id)
                tasks_completed += 1

                # Callback
                if self.on_task_complete:
                    await self.on_task_complete(task, result)

            except Exception as e:
                error_msg = str(e)
                task.record_attempt(error_msg)
                errors.append(f"{task.description}: {error_msg}")

                if task.should_retry():
                    task.status = TaskStatus.PENDING  # Will retry
                else:
                    task.status = TaskStatus.FAILED
                    tasks_failed += 1

            self.state.tasks[task_id] = asdict(task)
            self._save_state()

        # Evaluate iteration
        iteration.completed_at = datetime.now()
        iteration.tasks_completed = tasks_completed
        iteration.tasks_failed = tasks_failed

        if tasks_failed > 0 and iteration.number >= self.state.max_iterations:
            iteration.outcome = IterationOutcome.FAILED
            iteration.error_summary = "\n".join(errors)
        elif tasks_failed > 0:
            iteration.outcome = IterationOutcome.RETRY
            iteration.error_summary = "\n".join(errors)
        elif all(
            task_data["status"] == TaskStatus.COMPLETED.value
            for task_data in self.state.tasks.values()
        ):
            iteration.outcome = IterationOutcome.SUCCESS
        else:
            # Some tasks still pending (need guidance or more iterations)
            iteration.outcome = IterationOutcome.NEEDS_GUIDANCE

        # Record iteration
        self.state.iterations.append(asdict(iteration))
        self.state.updated_at = datetime.now()
        self._save_state()

        # Callback
        if self.on_iteration_complete:
            await self.on_iteration_complete(iteration)

        return iteration

    async def _execute_task(self, task: RalphTask, iteration_num: int) -> Any:
        """
        Execute a single task.

        This is where you integrate with the actual workflow executor
        (hierarchical workflow engine, team leads, workers, etc.)
        """
        # Build execution context with error history
        context = {
            "task_description": task.description,
            "iteration": iteration_num,
            "previous_errors": task.error_history,
            "guidance": self.state.pending_guidance
        }

        # TODO: Integrate with actual execution (WorkflowEngine, team leads, etc.)
        # For now, placeholder that simulates work
        await asyncio.sleep(0.1)

        # Clear used guidance
        if self.state.pending_guidance:
            self.state.guidance_history.append({
                "task_id": task.id,
                "iteration": iteration_num,
                "guidance": self.state.pending_guidance,
                "timestamp": datetime.now().isoformat()
            })
            self.state.pending_guidance = None

        return {"status": "completed", "context": context}

    def inject_guidance(self, guidance: str):
        """
        Inject guidance mid-execution (without restart).

        This allows human-in-the-loop or supervisor agents to provide
        additional context when the workflow is stuck.
        """
        self.state.pending_guidance = guidance
        self.state.is_paused = False
        self.state.updated_at = datetime.now()
        self._save_state()

    def _build_result(self) -> Dict[str, Any]:
        """Build final result with full history"""
        return {
            "workflow_id": self.workflow_id,
            "execution_id": self.execution_id,
            "outcome": self.state.final_outcome,
            "iterations": len(self.state.iterations),
            "tasks": {
                task_id: {
                    "description": task_data["description"],
                    "status": task_data["status"],
                    "attempts": task_data["attempts"],
                    "result": task_data.get("result")
                }
                for task_id, task_data in self.state.tasks.items()
            },
            "iteration_history": self.state.iterations,
            "guidance_history": self.state.guidance_history,
            "created_at": self.state.created_at.isoformat(),
            "updated_at": self.state.updated_at.isoformat()
        }

    def _save_state(self):
        """Persist state to disk"""
        state_file = self.state_dir / f"{self.execution_id}.json"
        with open(state_file, "w") as f:
            json.dump(self.state.dict(), f, indent=2, default=str)

    def _load_state(self) -> bool:
        """Load state from disk if exists"""
        state_file = self.state_dir / f"{self.execution_id}.json"
        if not state_file.exists():
            return False

        with open(state_file) as f:
            state_data = json.load(f)
            self.state = RalphWorkflowState(**state_data)

        return True

    # ── BR-4 durable state (Postgres) ──────────────────────────────────────
    # The disk _save_state/_load_state above stay AS-IS (a fast local cache and
    # what the unit tests exercise). These async methods add the shared, durable,
    # replica-safe Postgres mirror. Imports are LAZY to avoid the
    # persistence → ralph_engine import cycle (persistence imports
    # RalphWorkflowState from this module). Both are best-effort + never raise.

    async def persist_db(self) -> None:
        """Write-through this execution's RalphWorkflowState to Postgres."""
        if self.state is None:
            return
        from app.db.execution_store import save_ralph_execution

        org_id = None
        try:
            from app.orchestration.event_bus import current_org_id_var
            org_id = current_org_id_var.get() or None
        except Exception:
            org_id = None

        await save_ralph_execution(
            execution_id=self.state.execution_id,
            workflow_id=self.state.workflow_id,
            is_complete=bool(self.state.is_complete),
            is_paused=bool(self.state.is_paused),
            final_outcome=self.state.final_outcome,
            data=json.loads(self.state.model_dump_json()),
            org_id=org_id,
        )

    async def load_db(self) -> bool:
        """Load this execution's state from the Postgres durable mirror.

        Returns True if a snapshot for ``self.execution_id`` was found + loaded
        (used as the restart/other-replica resume fallback in ``execute`` and by
        the routes' rehydration path)."""
        if not self.execution_id:
            return False
        from app.db.execution_store import load_ralph_execution_data
        data = await load_ralph_execution_data(self.execution_id)
        if data is None:
            return False
        self.state = RalphWorkflowState.model_validate(data)
        return True

    def _generate_execution_id(self) -> str:
        """Generate unique execution ID"""
        from uuid import uuid4
        return f"ralph_{self.workflow_id}_{uuid4().hex[:8]}"

    async def _notify_needs_guidance(self, iteration: Iteration):
        """Notify that workflow needs guidance (placeholder)"""
        # This could trigger notifications, webhooks, etc.
        pass

    def get_progress(self) -> Dict[str, Any]:
        """Get current progress summary"""
        if not self.state:
            return {"status": "not_started"}

        total_tasks = len(self.state.tasks)
        completed = sum(
            1 for t in self.state.tasks.values()
            if t["status"] == TaskStatus.COMPLETED.value
        )
        failed = sum(
            1 for t in self.state.tasks.values()
            if t["status"] == TaskStatus.FAILED.value
        )
        in_progress = sum(
            1 for t in self.state.tasks.values()
            if t["status"] == TaskStatus.IN_PROGRESS.value
        )

        return {
            "execution_id": self.execution_id,
            "workflow_id": self.workflow_id,
            "iteration": self.state.current_iteration + 1,
            "max_iterations": self.state.max_iterations,
            "is_complete": self.state.is_complete,
            "is_paused": self.state.is_paused,
            "tasks": {
                "total": total_tasks,
                "completed": completed,
                "failed": failed,
                "in_progress": in_progress,
                "pending": total_tasks - completed - failed - in_progress
            },
            "progress_percent": int((completed / total_tasks) * 100) if total_tasks > 0 else 0
        }
