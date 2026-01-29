"""
Workflow Engine - Main Orchestrator

The WorkflowEngine ties together:
- Router: Task classification
- Planner: Step sequence generation
- Executor: Step execution
- Verifier: Confidence scoring
- ApprovalGate: Human-in-the-loop

This is the main entry point for executing tasks.
"""

import yaml
import json
import logging
from typing import Dict, Any, Optional, List, Callable
from pathlib import Path
from datetime import datetime

from app.engine.models import (
    Task,
    TaskResult,
    WorkflowPlan,
    WorkflowStep,
    ExecutionResult,
    VerificationResult,
    RoutingResult,
    ExecutionStatus,
    RiskLevel,
    ToolType,
    WorkerType,
    StepResult,
    ResumeToken,
    ApprovalState,
)
from app.engine.router import TaskRouter
from app.engine.planner import TaskPlanner
from app.engine.executor import StepExecutor
from app.engine.verifier import ResultVerifier
from app.engine.approval import ApprovalGate
from app.llm.ops_center_client import OpsCenterLLMClient

logger = logging.getLogger(__name__)


class WorkflowLoader:
    """Loads workflow definitions from YAML files"""

    def __init__(self, workflows_dir: Optional[Path] = None):
        self.workflows_dir = workflows_dir or Path(__file__).parent.parent.parent / "workflows"
        self.workflows_dir.mkdir(parents=True, exist_ok=True)
        self._cache: Dict[str, WorkflowPlan] = {}

    def load(self, name: str) -> Optional[WorkflowPlan]:
        """Load a workflow by name"""
        if name in self._cache:
            return self._cache[name]

        # Try YAML first, then JSON
        yaml_path = self.workflows_dir / f"{name}.yaml"
        json_path = self.workflows_dir / f"{name}.json"

        if yaml_path.exists():
            return self._load_yaml(yaml_path)
        elif json_path.exists():
            return self._load_json(json_path)

        logger.warning(f"Workflow not found: {name}")
        return None

    def _load_yaml(self, path: Path) -> Optional[WorkflowPlan]:
        """Load workflow from YAML file"""
        try:
            with open(path) as f:
                data = yaml.safe_load(f)
            return self._parse_workflow(data, path.stem)
        except Exception as e:
            logger.error(f"Error loading YAML workflow {path}: {e}")
            return None

    def _load_json(self, path: Path) -> Optional[WorkflowPlan]:
        """Load workflow from JSON file"""
        try:
            with open(path) as f:
                data = json.load(f)
            return self._parse_workflow(data, path.stem)
        except Exception as e:
            logger.error(f"Error loading JSON workflow {path}: {e}")
            return None

    def _parse_workflow(self, data: dict, name: str) -> WorkflowPlan:
        """Parse workflow data into WorkflowPlan"""
        steps = []
        for i, step_data in enumerate(data.get("steps", []), 1):
            # Parse tool type
            tool_str = step_data.get("tool", step_data.get("command", "llm")).split()[0].lower()
            tool_map = {
                "shell": ToolType.SHELL,
                "bash": ToolType.SHELL,
                "python": ToolType.PYTHON,
                "browser": ToolType.BROWSER,
                "filesystem": ToolType.FILESYSTEM,
                "file": ToolType.FILESYSTEM,
                "llm": ToolType.LLM,
                "api": ToolType.API,
                "database": ToolType.DATABASE,
                "db": ToolType.DATABASE,
            }
            tool = tool_map.get(tool_str, ToolType.LLM)

            # Parse worker type
            worker_str = step_data.get("worker", "")
            worker = None
            if worker_str:
                try:
                    worker = WorkerType(worker_str)
                except ValueError:
                    pass

            # Parse risk level
            risk_str = step_data.get("risk", "low").lower()
            try:
                risk = RiskLevel(risk_str)
            except ValueError:
                risk = RiskLevel.LOW

            step = WorkflowStep(
                id=step_data.get("id", i),
                action=step_data.get("action", step_data.get("command", "")),
                tool=tool,
                worker=worker,
                inputs=step_data.get("inputs", []),
                outputs=step_data.get("outputs", []),
                success_criteria=step_data.get("success_criteria", []),
                risk=risk,
                approval_required=step_data.get("approval", False) or step_data.get("approval_required", False),
                timeout_seconds=step_data.get("timeout", 60),
                stdin_from=step_data.get("stdin", step_data.get("stdin_from")),
            )
            steps.append(step)

        # Calculate total risk
        max_risk = RiskLevel.LOW
        requires_approval = False
        for step in steps:
            if step.risk == RiskLevel.HIGH:
                max_risk = RiskLevel.HIGH
            elif step.risk == RiskLevel.MEDIUM and max_risk != RiskLevel.HIGH:
                max_risk = RiskLevel.MEDIUM
            if step.approval_required:
                requires_approval = True

        plan = WorkflowPlan(
            name=data.get("name", name),
            objective=data.get("objective", data.get("description", "")),
            assumptions=data.get("assumptions", []),
            steps=steps,
            stop_conditions=data.get("stop_conditions", []),
            total_risk=max_risk,
            requires_approval=requires_approval,
        )

        self._cache[name] = plan
        return plan

    def list_workflows(self) -> List[str]:
        """List all available workflows"""
        workflows = []
        for path in self.workflows_dir.glob("*.yaml"):
            workflows.append(path.stem)
        for path in self.workflows_dir.glob("*.json"):
            if path.stem not in workflows:
                workflows.append(path.stem)
        return sorted(workflows)

    def reload(self):
        """Clear cache and reload all workflows"""
        self._cache.clear()


class WorkflowEngine:
    """
    Main workflow orchestration engine.

    This is the primary entry point for executing tasks.
    It coordinates Router → Planner → Executor → Verifier.
    """

    def __init__(
        self,
        llm_client: Optional[OpsCenterLLMClient] = None,
        workflows_dir: Optional[Path] = None,
        prompts_dir: Optional[Path] = None,
        state_dir: Optional[Path] = None,
        artifacts_dir: Optional[Path] = None,
        confidence_threshold: float = 0.7,
        max_retries: int = 2,
    ):
        self.llm_client = llm_client or OpsCenterLLMClient()
        self.confidence_threshold = confidence_threshold
        self.max_retries = max_retries

        # Initialize components
        self.workflow_loader = WorkflowLoader(workflows_dir)
        self.router = TaskRouter(
            llm_client=self.llm_client,
            confidence_threshold=confidence_threshold,
        )
        self.planner = TaskPlanner(llm_client=self.llm_client)
        self.executor = StepExecutor(
            llm_client=self.llm_client,
            artifacts_dir=artifacts_dir,
        )
        self.verifier = ResultVerifier(
            llm_client=self.llm_client,
            confidence_threshold=confidence_threshold,
        )
        self.approval_gate = ApprovalGate(state_dir=state_dir)

        # Worker registry
        self.workers: Dict[WorkerType, Any] = {}

        logger.info("WorkflowEngine initialized")

    def register_worker(self, worker_type: WorkerType, worker: Any):
        """Register a worker for a specific type"""
        self.workers[worker_type] = worker
        self.executor.workers[worker_type] = worker
        logger.info(f"Registered worker: {worker_type.value}")

    async def execute(
        self,
        task: Task,
        on_step_complete: Optional[Callable] = None,
        on_approval_required: Optional[Callable] = None,
    ) -> TaskResult:
        """
        Execute a task through the full pipeline.

        Pipeline:
        1. Route task (classify intent, risk, worker)
        2. Check for known workflow OR plan new workflow
        3. Execute workflow steps
        4. Verify results
        5. Handle retries/escalation if needed

        Args:
            task: The task to execute
            on_step_complete: Callback after each step
            on_approval_required: Callback when approval is needed

        Returns:
            TaskResult with full execution details
        """
        start_time = datetime.utcnow()
        logger.info(f"Executing task {task.id}: {task.content[:100]}...")

        try:
            # Step 1: Route the task
            routing = await self.router.route(task)
            logger.info(
                f"Task {task.id} routed: intent={routing.intent}, "
                f"risk={routing.risk}, worker={routing.suggested_worker}"
            )

            # Step 2: Get or create workflow plan
            plan = await self._get_or_create_plan(task, routing)
            logger.info(f"Task {task.id} planned: {len(plan.steps)} steps")

            # Step 3: Execute workflow
            model = self._determine_model(routing)
            execution = await self._execute_with_retries(
                task,
                plan,
                routing,
                model,
                on_step_complete,
                on_approval_required,
            )

            # Step 4: Verify results
            expected_outputs = []
            for step in plan.steps:
                expected_outputs.extend(step.outputs)
            verification = await self.verifier.verify(execution, expected_outputs, task.user_id)

            # Step 5: Handle escalation if needed
            if verification.next_action == "escalate_to_strong_model" and not routing.escalate_to_cloud:
                logger.info(f"Task {task.id}: Escalating to cloud model")
                return await self._escalate_and_retry(task, routing, plan, verification)

            # Build result
            duration = (datetime.utcnow() - start_time).total_seconds()
            return TaskResult(
                task_id=task.id,
                status=execution.status,
                routing=routing,
                plan=plan,
                execution=execution,
                verification=verification,
                output=execution.final_output,
                artifacts=execution.artifacts,
                total_duration_seconds=duration,
                total_tokens=execution.total_tokens,
                model_used=model,
                escalated=routing.escalate_to_cloud,
                resume_token=execution.resume_token,
            )

        except Exception as e:
            logger.error(f"Task {task.id} failed: {e}")
            duration = (datetime.utcnow() - start_time).total_seconds()
            return TaskResult(
                task_id=task.id,
                status=ExecutionStatus.FAILED,
                output=str(e),
                total_duration_seconds=duration,
            )

    async def _get_or_create_plan(self, task: Task, routing: RoutingResult) -> WorkflowPlan:
        """Get existing workflow or create a new plan"""
        # Check for suggested workflow
        if task.suggested_workflow:
            plan = self.workflow_loader.load(task.suggested_workflow)
            if plan:
                return plan

        # Check for intent-based workflow
        intent_workflow = self.workflow_loader.load(routing.intent.value)
        if intent_workflow:
            return intent_workflow

        # Generate new plan
        return await self.planner.plan(task, routing)

    def _determine_model(self, routing: RoutingResult) -> str:
        """Determine which model to use based on routing"""
        if routing.escalate_to_cloud:
            return routing.suggested_model
        if routing.risk == RiskLevel.HIGH:
            return "ops-center"  # Use better model for high-risk
        return "local"

    async def _execute_with_retries(
        self,
        task: Task,
        plan: WorkflowPlan,
        routing: RoutingResult,
        model: str,
        on_step_complete: Optional[Callable],
        on_approval_required: Optional[Callable],
    ) -> ExecutionResult:
        """Execute workflow with retry logic and checkpoint support"""

        # Track execution context for checkpointing
        execution_context: Dict[str, Any] = {"steps": {}}
        completed_step_results: List[StepResult] = []

        async def approval_callback(step: WorkflowStep, context: Dict[str, Any]) -> bool:
            """Handle approval requests with full checkpoint creation"""
            if on_approval_required:
                return await on_approval_required(step, context)

            # Create a comprehensive checkpoint with all resume context
            checkpoint_context = {
                **context,
                "task_id": task.id,
                "task_content": task.content,
                "user_id": task.user_id,
                "model": model,
                "workflow_plan": plan.model_dump_json(),
                "routing": routing.model_dump_json(),
                "completed_steps": [r.model_dump() for r in completed_step_results],
            }

            token = await self.approval_gate.request_approval(step, checkpoint_context, plan.id)

            # Enhance token with extended context
            token.task_id = task.id
            token.task_content = task.content
            token.user_id = task.user_id
            token.model = model
            token.workflow_plan_json = plan.model_dump_json()
            token.routing_json = routing.model_dump_json()
            token.step_results_json = json.dumps([r.model_dump() for r in completed_step_results], default=str)
            token.execution_context = context
            self.approval_gate._save_token(token)

            logger.info(f"Created checkpoint for task {task.id} at step {step.id}: {token.token_id}")

            # In async mode, return False to pause execution
            return False

        async def step_complete_callback(step: WorkflowStep, result: StepResult):
            """Track completed steps for checkpoint"""
            completed_step_results.append(result)
            execution_context["steps"][f"step{step.id}"] = {
                "stdout": result.output,
                "output": result.output,
                "artifacts": result.artifacts,
                "status": result.status.value,
            }
            if on_step_complete:
                await on_step_complete(step, result)

        for attempt in range(self.max_retries + 1):
            execution = await self.executor.execute_workflow(
                plan=plan,
                user_id=task.user_id,
                model=model,
                on_step_complete=step_complete_callback,
                on_approval_required=approval_callback if plan.requires_approval else None,
            )

            # If completed or blocked for approval, return
            if execution.status in [ExecutionStatus.COMPLETED, ExecutionStatus.APPROVAL_REQUIRED]:
                return execution

            # If failed, check if we should retry
            if attempt < self.max_retries:
                logger.info(f"Task {task.id}: Retry {attempt + 1}/{self.max_retries}")
                # Escalate model on retry
                if model == "local":
                    model = "ops-center"
            else:
                logger.warning(f"Task {task.id}: Max retries exceeded")

        return execution

    async def _escalate_and_retry(
        self,
        task: Task,
        routing: RoutingResult,
        plan: WorkflowPlan,
        verification: VerificationResult,
    ) -> TaskResult:
        """Escalate to cloud model and retry execution"""
        logger.info(f"Escalating task {task.id} to cloud model")

        # Update routing for escalation
        routing.escalate_to_cloud = True
        routing.suggested_model = "claude-burst"
        routing.escalation_reason = verification.escalation_reason or "Low confidence"

        # Re-execute with cloud model
        execution = await self.executor.execute_workflow(
            plan=plan,
            user_id=task.user_id,
            model="claude-burst",
        )

        # Verify again
        expected_outputs = []
        for step in plan.steps:
            expected_outputs.extend(step.outputs)
        new_verification = await self.verifier.verify(execution, expected_outputs, task.user_id)

        return TaskResult(
            task_id=task.id,
            status=execution.status,
            routing=routing,
            plan=plan,
            execution=execution,
            verification=new_verification,
            output=execution.final_output,
            artifacts=execution.artifacts,
            total_tokens=execution.total_tokens,
            model_used="claude-burst",
            escalated=True,
        )

    async def resume_workflow(
        self,
        token_id: str,
        approved: bool = True,
        approved_by: str = "user",
        rejection_reason: str = "",
        on_step_complete: Optional[Callable] = None,
        on_approval_required: Optional[Callable] = None,
    ) -> TaskResult:
        """
        Resume a paused workflow after approval.

        This implements full checkpoint/resume capability:
        1. Load the checkpoint with all execution context
        2. Restore the workflow plan and routing
        3. Continue execution from the approved step
        4. Handle any subsequent approval gates

        Args:
            token_id: The resume token ID
            approved: Whether the step was approved
            approved_by: Who approved/rejected
            rejection_reason: Reason if rejected
            on_step_complete: Callback after each step
            on_approval_required: Callback for future approval requests

        Returns:
            TaskResult with continued execution
        """
        start_time = datetime.utcnow()
        logger.info(f"Resuming workflow with token {token_id}")

        # Process approval/rejection
        if approved:
            success = self.approval_gate.approve(token_id, approved_by)
        else:
            success = self.approval_gate.reject(token_id, approved_by, rejection_reason)

        if not success:
            return TaskResult(
                task_id="unknown",
                status=ExecutionStatus.FAILED,
                output=f"Failed to {'approve' if approved else 'reject'} token",
            )

        if not approved:
            token = self.approval_gate.get_token(token_id)
            return TaskResult(
                task_id=token.task_id if token else "unknown",
                status=ExecutionStatus.BLOCKED,
                output=f"Workflow rejected: {rejection_reason}",
            )

        # Load the checkpoint token with full context
        token = self.approval_gate.get_token(token_id)
        if not token:
            return TaskResult(
                task_id="unknown",
                status=ExecutionStatus.FAILED,
                output="Could not load checkpoint token",
            )

        try:
            # Restore workflow plan
            if not token.workflow_plan_json:
                return TaskResult(
                    task_id=token.task_id or "unknown",
                    status=ExecutionStatus.FAILED,
                    output="Checkpoint missing workflow plan",
                )

            plan_data = json.loads(token.workflow_plan_json)
            plan = WorkflowPlan(**plan_data)

            # Restore routing result
            routing = None
            if token.routing_json:
                routing_data = json.loads(token.routing_json)
                routing = RoutingResult(**routing_data)

            # Restore completed step results
            completed_results: List[StepResult] = []
            if token.step_results_json:
                results_data = json.loads(token.step_results_json)
                completed_results = [StepResult(**r) for r in results_data]

            # Restore execution context
            context = token.execution_context or token.state.get("steps", {})
            if isinstance(context, dict) and "steps" not in context:
                context = {"steps": context}

            # Find the step to resume from (the approved step)
            resume_step_index = None
            for i, step in enumerate(plan.steps):
                if step.id == token.step_id:
                    resume_step_index = i
                    break

            if resume_step_index is None:
                return TaskResult(
                    task_id=token.task_id or "unknown",
                    status=ExecutionStatus.FAILED,
                    output=f"Could not find step {token.step_id} in workflow",
                )

            logger.info(
                f"Resuming workflow {plan.name} from step {resume_step_index + 1}/{len(plan.steps)} "
                f"(step_id={token.step_id})"
            )

            # Execute remaining steps starting from the approved step
            model = token.model or "local"
            user_id = token.user_id or "anonymous"
            total_tokens = {"input": 0, "output": 0}
            all_artifacts = []

            # Collect artifacts from completed steps
            for result in completed_results:
                all_artifacts.extend(result.artifacts)
                total_tokens["input"] += result.tokens_used.get("input", 0)
                total_tokens["output"] += result.tokens_used.get("output", 0)

            # Execute from the resume point
            for i, step in enumerate(plan.steps[resume_step_index:], start=resume_step_index):
                # Check for approval requirement (skip for the just-approved step)
                if step.approval_required and i > resume_step_index:
                    if on_approval_required:
                        approved_now = await on_approval_required(step, context)
                        if not approved_now:
                            # Create new checkpoint
                            new_token = await self._create_checkpoint(
                                task_id=token.task_id,
                                task_content=token.task_content,
                                user_id=user_id,
                                model=model,
                                plan=plan,
                                routing=routing,
                                step=step,
                                context=context,
                                completed_results=completed_results,
                            )
                            return TaskResult(
                                task_id=token.task_id or "unknown",
                                status=ExecutionStatus.APPROVAL_REQUIRED,
                                output=f"Approval required for step {step.id}: {step.action}",
                                resume_token=new_token.token_id,
                            )
                    else:
                        # Default: create checkpoint and pause
                        new_token = await self._create_checkpoint(
                            task_id=token.task_id,
                            task_content=token.task_content,
                            user_id=user_id,
                            model=model,
                            plan=plan,
                            routing=routing,
                            step=step,
                            context=context,
                            completed_results=completed_results,
                        )
                        return TaskResult(
                            task_id=token.task_id or "unknown",
                            status=ExecutionStatus.APPROVAL_REQUIRED,
                            output=f"Approval required for step {step.id}: {step.action}",
                            resume_token=new_token.token_id,
                        )

                # Execute the step
                result = await self.executor.execute_step(step, context, user_id, model)
                completed_results.append(result)

                # Update context
                context["steps"][f"step{step.id}"] = {
                    "stdout": result.output,
                    "output": result.output,
                    "artifacts": result.artifacts,
                    "status": result.status.value,
                }

                # Update totals
                total_tokens["input"] += result.tokens_used.get("input", 0)
                total_tokens["output"] += result.tokens_used.get("output", 0)
                all_artifacts.extend(result.artifacts)

                # Callback
                if on_step_complete:
                    await on_step_complete(step, result)

                # Check for failure
                if result.status in [ExecutionStatus.FAILED, ExecutionStatus.BLOCKED]:
                    duration = (datetime.utcnow() - start_time).total_seconds()
                    return TaskResult(
                        task_id=token.task_id or "unknown",
                        status=result.status,
                        output=result.error or result.blocker,
                        total_duration_seconds=duration,
                        total_tokens=total_tokens,
                        artifacts=all_artifacts,
                        resume_token=token_id,
                    )

            # All steps completed successfully
            duration = (datetime.utcnow() - start_time).total_seconds()
            final_output = completed_results[-1].output if completed_results else None

            logger.info(f"Workflow {plan.name} completed after resume")

            return TaskResult(
                task_id=token.task_id or "unknown",
                status=ExecutionStatus.COMPLETED,
                routing=routing,
                plan=plan,
                output=final_output,
                artifacts=all_artifacts,
                total_duration_seconds=duration,
                total_tokens=total_tokens,
                model_used=model,
                resume_token=token_id,
            )

        except Exception as e:
            logger.error(f"Error resuming workflow: {e}")
            duration = (datetime.utcnow() - start_time).total_seconds()
            return TaskResult(
                task_id=token.task_id if token else "unknown",
                status=ExecutionStatus.FAILED,
                output=f"Resume failed: {str(e)}",
                total_duration_seconds=duration,
            )

    async def _create_checkpoint(
        self,
        task_id: str,
        task_content: str,
        user_id: str,
        model: str,
        plan: WorkflowPlan,
        routing: Optional[RoutingResult],
        step: WorkflowStep,
        context: Dict[str, Any],
        completed_results: List[StepResult],
    ) -> ResumeToken:
        """Create a checkpoint for workflow pause/resume"""
        checkpoint_context = {
            **context,
            "task_id": task_id,
            "task_content": task_content,
            "user_id": user_id,
            "model": model,
        }

        token = await self.approval_gate.request_approval(step, checkpoint_context, plan.id)

        # Enhance with extended context
        token.task_id = task_id
        token.task_content = task_content
        token.user_id = user_id
        token.model = model
        token.workflow_plan_json = plan.model_dump_json()
        token.routing_json = routing.model_dump_json() if routing else None
        token.step_results_json = json.dumps([r.model_dump() for r in completed_results], default=str)
        token.execution_context = context

        self.approval_gate._save_token(token)
        return token

    def get_pending_approvals(self) -> list:
        """Get all pending approval requests"""
        tokens = self.approval_gate.get_pending_approvals()
        return [self.approval_gate.format_approval_request(t) for t in tokens]

    def list_workflows(self) -> List[str]:
        """List available workflows"""
        return self.workflow_loader.list_workflows()

    def get_workflow(self, name: str) -> Optional[WorkflowPlan]:
        """Get a specific workflow by name"""
        return self.workflow_loader.load(name)

    def get_stats(self) -> Dict[str, Any]:
        """Get engine statistics"""
        return {
            "available_workflows": self.list_workflows(),
            "registered_workers": [w.value for w in self.workers.keys()],
            "pending_approvals": len(self.approval_gate.get_pending_approvals()),
            "confidence_threshold": self.confidence_threshold,
            "max_retries": self.max_retries,
        }
