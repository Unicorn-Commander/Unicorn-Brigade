"""
Workflow Engine - Executes 3-Tier Hierarchical Agent Workflows

Architecture:
Orchestrator (The General) → Team Leads → Workers

The engine handles:
- Workflow execution and state management
- Team Lead delegation to Workers
- Result aggregation
- Human-in-the-loop checkpoints
- Cost tracking and optimization
- Runtime model configuration and overrides
"""

import asyncio
import json
import logging
import re
from typing import Dict, Any, List, Optional, Callable, AsyncGenerator
from datetime import datetime
import uuid

from app.workflows.schema import (
    WorkflowDefinition,
    WorkflowExecution,
    WorkflowExecutionState,
    StepExecution,
    StepExecutionState,
    WorkflowStep,
    Checkpoint,
    CheckpointType,
    TeamLeadSpec,
    WorkerSpec,
    ModelTier,
)
from app.workflows.team_leads import (
    ALL_TEAM_LEADS,
    ALL_WORKERS,
    get_team_lead,
    get_worker,
)
from app.workflows.model_config import (
    ModelConfig,
    ModelRegistry,
    COST_OPTIMIZED_CONFIG,
)
# BR-4 durable state: write-through persistence of WorkflowExecution (incl. HITL
# checkpoint state) so an in-flight execution survives a restart / is rehydratable.
# execution_store is model-agnostic (dict in/out) + dependency-light (app.db
# only); this engine owns the pydantic (de)serialisation via model_dump_json /
# model_validate.
from app.db.execution_store import (
    save_workflow_execution,
    load_inflight_workflow_execution_data,
)


def _current_org_id() -> Optional[str]:
    """Best-effort read of the bound org for BR-4 execution attribution."""
    try:
        from app.orchestration.event_bus import current_org_id_var
        return current_org_id_var.get() or None
    except Exception:
        return None
from app.llm.ops_center_client import OpsCenterLLMClient, ModelUnavailableError
from app.llm.tool_resolver import get_tools_by_names
from app.orchestration import (
    event_bus,
    emit_agent_started,
    emit_agent_completed,
    emit_agent_thinking,
    emit_tool_call,
    emit_tool_result,
    emit_agent_message,
    emit_agent_invocation,
    EventType,
    OrchestrationEvent,
)

logger = logging.getLogger(__name__)


class WorkflowEngine:
    """
    Executes 3-tier hierarchical workflows.

    Flow:
    1. Orchestrator (The General) receives task and selects Team Leads
    2. Team Leads decompose tasks and delegate to Workers
    3. Workers execute narrow tasks and return results
    4. Results flow back up through aggregation

    Model Configuration:
    - Supports runtime model configuration via ModelConfig
    - Can override orchestrator, team lead, and worker models
    - Uses preset configurations (cost_optimized, quality_optimized, etc.)
    - Per-execution model overrides supported
    """

    def __init__(
        self,
        llm_client: Optional[OpsCenterLLMClient] = None,
        orchestrator_model: str = "openai/gpt-4o-mini",
        enable_local_models: bool = True,
        model_config: Optional[ModelConfig] = None,
    ):
        self.llm_client = llm_client or OpsCenterLLMClient()

        # Use provided model_config or create default from parameters
        if model_config:
            self._default_config = model_config
        else:
            self._default_config = ModelConfig(
                orchestrator_model=orchestrator_model,
                enable_local_models=enable_local_models,
            )

        # For backward compatibility
        self.orchestrator_model = self._default_config.orchestrator_model
        self.enable_local_models = self._default_config.enable_local_models

        # Active executions
        self._executions: Dict[str, WorkflowExecution] = {}

        # Checkpoint callbacks
        self._checkpoint_handlers: Dict[str, Callable] = {}

        logger.info(
            f"WorkflowEngine initialized with orchestrator model: {self.orchestrator_model}, "
            f"local models: {self.enable_local_models}"
        )

    def get_model_config(self) -> ModelConfig:
        """Get the current default model configuration"""
        return self._default_config

    def update_model_config(self, config: ModelConfig) -> None:
        """Update the default model configuration"""
        self._default_config = config
        self.orchestrator_model = config.orchestrator_model
        self.enable_local_models = config.enable_local_models
        logger.info(f"Model configuration updated: orchestrator={config.orchestrator_model}")

    # =========================================================================
    # BR-4 Durable State
    # =========================================================================

    async def _persist(self, execution: WorkflowExecution) -> None:
        """Write-through the execution snapshot to Postgres (best-effort + loud).

        Called on every meaningful state transition so an in-flight execution
        (and any pending human-approval checkpoint) is durable across a process
        restart. ``save_workflow_execution`` never raises."""
        state = execution.state.value if hasattr(execution.state, "value") else str(execution.state)
        await save_workflow_execution(
            id=execution.id,
            workflow_id=execution.workflow_id,
            workflow_name=execution.workflow_name,
            state=state,
            data=json.loads(execution.model_dump_json()),
            current_step=execution.current_step,
            pending_checkpoint=execution.pending_checkpoint,
            mission_id=execution.mission_id,
            started_at=execution.started_at,
            completed_at=execution.completed_at,
            org_id=_current_org_id(),
        )

    async def rehydrate(self) -> int:
        """Reload in-flight executions from Postgres into the in-memory cache.

        Run once at startup (app.main lifespan). After a restart or on a fresh
        replica this repopulates ``_executions`` so ``get_execution`` /
        ``list_executions`` (kept SYNC, cache-backed, so the API contract and the
        unit tests are unchanged) see executions that were running before the
        restart — including any WAITING_CHECKPOINT execution a human still has to
        approve. Never clobbers a live in-memory execution on this replica.
        Returns the number of executions rehydrated."""
        count = 0
        for data in await load_inflight_workflow_execution_data():
            try:
                ex = WorkflowExecution.model_validate(data)
            except Exception as e:  # pragma: no cover - defensive
                logger.error("BR-4 rehydrate: skipping unreadable workflow row: %s", e)
                continue
            if ex.id not in self._executions:
                self._executions[ex.id] = ex
                count += 1
        if count:
            logger.info("WorkflowEngine rehydrated %d in-flight execution(s) from DB", count)
        return count

    # =========================================================================
    # Main Execution
    # =========================================================================

    async def execute_workflow(
        self,
        workflow: WorkflowDefinition,
        inputs: Dict[str, Any],
        user_id: Optional[str] = None,
        on_step_complete: Optional[Callable] = None,
        on_checkpoint: Optional[Callable] = None,
        model_config: Optional[ModelConfig] = None,
    ) -> WorkflowExecution:
        """
        Execute a complete workflow.

        Args:
            workflow: The workflow definition to execute
            inputs: Input values for the workflow
            user_id: Optional user ID for tracking
            on_step_complete: Callback when each step completes
            on_checkpoint: Callback when a checkpoint is reached
            model_config: Optional model configuration override for this execution

        Returns:
            WorkflowExecution with results
        """
        # Use provided config or fall back to default
        config = model_config or self._default_config

        # Create execution record
        execution = WorkflowExecution(
            workflow_id=workflow.id,
            workflow_name=workflow.name,
            inputs=inputs,
            state=WorkflowExecutionState.RUNNING,
            started_at=datetime.utcnow(),
        )
        # Store the model config used for this execution
        execution.model_config_used = config.model_dump()
        self._executions[execution.id] = execution

        # Create mission in orchestration system
        mission = event_bus.create_mission(
            name=workflow.name,
            description=f"Executing workflow: {workflow.description}",
            lead_agent="the-general",
        )
        execution.mission_id = mission.id
        # BR-4: persist the initial RUNNING snapshot so the execution is durable
        # from the very first moment (survives a restart mid-run).
        await self._persist(execution)

        try:
            # Emit workflow start
            await emit_agent_started(
                agent_id="the-general",
                agent_name="The General",
                task=f"Orchestrating workflow: {workflow.name}",
                mission_id=mission.id,
            )

            # Execute steps in order
            step_outputs: Dict[str, Dict[str, Any]] = {"inputs": inputs}

            for step in workflow.steps:
                # Check for checkpoint before this step
                checkpoint = self._get_checkpoint_before_step(workflow, step.id)
                if checkpoint and checkpoint.type == CheckpointType.HUMAN_APPROVAL:
                    execution.state = WorkflowExecutionState.WAITING_CHECKPOINT
                    execution.pending_checkpoint = checkpoint.id
                    # BR-4: persist the WAITING_CHECKPOINT state so a pending
                    # human-approval gate survives a restart and is resumable.
                    await self._persist(execution)
                    if on_checkpoint:
                        response = await on_checkpoint(checkpoint, step_outputs)
                        execution.checkpoint_responses[checkpoint.id] = response
                        if not response.get("approved", False):
                            execution.state = WorkflowExecutionState.CANCELLED
                            execution.error = "Checkpoint not approved"
                            break
                    execution.state = WorkflowExecutionState.RUNNING

                # Check condition
                if step.condition and not self._evaluate_condition(step.condition, step_outputs):
                    # Skip this step
                    step_exec = StepExecution(step_id=step.id, state=StepExecutionState.SKIPPED)
                    execution.step_executions[step.id] = step_exec
                    continue

                # Resolve inputs for this step
                step_inputs = self._resolve_inputs(step.inputs, step_outputs)

                # Execute the step
                execution.current_step = step.id
                step_exec = await self._execute_step(
                    step=step,
                    inputs=step_inputs,
                    workflow=workflow,
                    mission_id=mission.id,
                    model_config=config,
                )
                execution.step_executions[step.id] = step_exec

                # Update totals
                execution.total_tokens += step_exec.tokens_used
                execution.total_cost += step_exec.estimated_cost

                # Store outputs
                step_outputs[step.id] = step_exec.outputs

                # BR-4: persist after each completed step so a restart mid-run
                # keeps everything done so far (state, per-step results, cost).
                await self._persist(execution)

                # Callback
                if on_step_complete:
                    await on_step_complete(step, step_exec)

                # Check for failure
                if step_exec.state == StepExecutionState.FAILED:
                    if step.max_retries > step_exec.retries:
                        # Retry
                        step_exec.retries += 1
                        await asyncio.sleep(step.retry_delay_seconds)
                        # Re-execute...
                    else:
                        execution.state = WorkflowExecutionState.FAILED
                        execution.error = step_exec.error
                        break

            # Workflow complete
            if execution.state == WorkflowExecutionState.RUNNING:
                # End-of-workflow checkpoints: any HUMAN_APPROVAL whose
                # `after_step` is empty fires AFTER the final step. The
                # mid-workflow loop above only fires checkpoints whose
                # `after_step` matches a specific step id, so end-of-flow
                # approvals (used by ~18 professional workflows for
                # "review the final deal memo / report" gates) need this
                # explicit pass — without it they were silently dead code.
                for checkpoint in workflow.checkpoints:
                    if checkpoint.after_step:
                        continue  # already handled in the per-step loop
                    if checkpoint.type != CheckpointType.HUMAN_APPROVAL:
                        continue
                    execution.state = WorkflowExecutionState.WAITING_CHECKPOINT
                    execution.pending_checkpoint = checkpoint.id
                    # BR-4: durably record the end-of-flow approval gate too.
                    await self._persist(execution)
                    if on_checkpoint:
                        response = await on_checkpoint(checkpoint, step_outputs)
                        execution.checkpoint_responses[checkpoint.id] = response
                        if not response.get("approved", False):
                            execution.state = WorkflowExecutionState.CANCELLED
                            execution.error = "End-of-workflow checkpoint not approved"
                            break
                    execution.state = WorkflowExecutionState.RUNNING

            if execution.state == WorkflowExecutionState.RUNNING:
                execution.state = WorkflowExecutionState.COMPLETED
                # Gather final outputs
                for output_key in workflow.final_outputs:
                    for step_id, outputs in step_outputs.items():
                        if output_key in outputs:
                            execution.outputs[output_key] = outputs[output_key]

            execution.completed_at = datetime.utcnow()

            # BR-4: persist the terminal snapshot (completed / cancelled).
            await self._persist(execution)

            # Emit completion
            await emit_agent_completed(
                agent_id="the-general",
                agent_name="The General",
                result=f"Workflow {execution.state.value}: {len(execution.outputs)} outputs",
                mission_id=mission.id,
            )

            return execution

        except Exception as e:
            logger.error(f"Workflow execution failed: {e}")
            execution.state = WorkflowExecutionState.FAILED
            execution.error = str(e)
            execution.completed_at = datetime.utcnow()
            # BR-4: persist the failed terminal snapshot too.
            await self._persist(execution)
            return execution

    async def _execute_step(
        self,
        step: WorkflowStep,
        inputs: Dict[str, Any],
        workflow: WorkflowDefinition,
        mission_id: str,
        model_config: Optional[ModelConfig] = None,
    ) -> StepExecution:
        """Execute a single workflow step by delegating to appropriate Team Lead"""

        config = model_config or self._default_config

        step_exec = StepExecution(
            step_id=step.id,
            state=StepExecutionState.RUNNING,
            started_at=datetime.utcnow(),
            inputs_received=inputs,
        )

        try:
            # Determine executor
            if step.executor == "orchestrator":
                # Orchestrator handles directly
                result = await self._orchestrator_execute(step, inputs, mission_id, config)
            else:
                # Delegate to Team Lead
                team_lead = get_team_lead(step.executor.replace("-lead", ""))
                if not team_lead:
                    team_lead = ALL_TEAM_LEADS.get(step.executor)

                if not team_lead:
                    raise ValueError(f"Unknown executor: {step.executor}")

                # Emit delegation event: Orchestrator → Team Lead
                await emit_agent_message(
                    agent_id="the-general",
                    agent_name="The General",
                    message=f"Delegating to {team_lead.name}: {step.description}",
                    to_agent=team_lead.id,
                    mission_id=mission_id,
                )
                # Emit invocation event for 3D visualization
                await emit_agent_invocation(
                    agent_id="the-general",
                    agent_name="The General",
                    target_agent_id=team_lead.id,
                    target_agent_name=team_lead.name,
                    purpose=f"Hierarchical delegation: {step.description[:50]}",
                    protocol="internal",  # Purple connection for hierarchical
                    metadata={"step_id": step.id, "workflow_type": "hierarchical"},
                    mission_id=mission_id,
                )

                result = await self._team_lead_execute(
                    team_lead=team_lead,
                    task=step.description,
                    inputs=inputs,
                    mission_id=mission_id,
                    step_exec=step_exec,
                    model_config=config,
                )

            step_exec.outputs = result.get("outputs", result)
            step_exec.state = StepExecutionState.COMPLETED
            step_exec.completed_at = datetime.utcnow()

            # Extract token usage if available
            step_exec.tokens_used = result.get("tokens_used", 0)
            step_exec.estimated_cost = result.get("estimated_cost", 0.0)

        except asyncio.TimeoutError:
            step_exec.state = StepExecutionState.FAILED
            step_exec.error = f"Step timed out after {step.timeout_seconds}s"
        except Exception as e:
            step_exec.state = StepExecutionState.FAILED
            step_exec.error = str(e)
            logger.error(f"Step {step.id} failed: {e}")

        return step_exec

    # =========================================================================
    # Orchestrator Execution
    # =========================================================================

    async def _orchestrator_execute(
        self,
        step: WorkflowStep,
        inputs: Dict[str, Any],
        mission_id: str,
        model_config: Optional[ModelConfig] = None,
    ) -> Dict[str, Any]:
        """Orchestrator (The General) executes a step directly"""

        config = model_config or self._default_config
        model = ModelRegistry.get_model_for_orchestrator(config)

        await emit_agent_thinking(
            agent_id="the-general",
            agent_name="The General",
            thought=f"Executing step: {step.name}",
            mission_id=mission_id,
        )

        # Build prompt for orchestrator
        prompt = f"""You are The General, orchestrating a workflow step.

Step: {step.name}
Description: {step.description}

Inputs:
{json.dumps(inputs, indent=2)}

Execute this step and provide the outputs as JSON.
Expected outputs: {step.outputs}

Respond with a JSON object containing the outputs."""

        try:
            response = await self.llm_client.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                model=model,
                temperature=0.3,
            )
        except ModelUnavailableError as e:
            # Orchestrator should always use API models, but handle edge case
            logger.warning(f"Model {model} unavailable for orchestrator, falling back to default: {e}")
            fallback_model = "openai/gpt-4o-mini"
            logger.info(f"Using fallback model: {fallback_model}")
            response = await self.llm_client.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                model=fallback_model,
                temperature=0.3,
            )
            model = fallback_model

        content = self._extract_content(response)
        outputs = self._parse_json_from_response(content)

        return {
            "outputs": outputs,
            "tokens_used": response.get("usage", {}).get("total_tokens", 0),
            "estimated_cost": ModelRegistry.get_model_cost(
                model,
                response.get("usage", {}).get("prompt_tokens", 0),
                response.get("usage", {}).get("completion_tokens", 0),
            ),
            "model_used": model,
        }

    # =========================================================================
    # Team Lead Execution
    # =========================================================================

    async def _team_lead_execute(
        self,
        team_lead: TeamLeadSpec,
        task: str,
        inputs: Dict[str, Any],
        mission_id: str,
        step_exec: StepExecution,
        model_config: Optional[ModelConfig] = None,
    ) -> Dict[str, Any]:
        """Team Lead receives task, delegates to workers, and aggregates results"""

        config = model_config or self._default_config

        # Get model for this team lead using config
        domain = team_lead.domain
        model = ModelRegistry.get_model_for_team_lead(domain, config)

        step_exec.executor_id = team_lead.id
        step_exec.model_used = model
        step_exec.state = StepExecutionState.DELEGATING

        await emit_agent_started(
            agent_id=team_lead.id,
            agent_name=team_lead.name,
            task=task,
            mission_id=mission_id,
        )

        # Step 1: Team Lead analyzes task and decides on delegations
        delegation_plan = await self._get_delegation_plan(
            team_lead, task, inputs, mission_id, config
        )

        step_exec.state = StepExecutionState.WAITING_WORKERS

        # Step 2: Execute worker tasks
        worker_results: Dict[str, Any] = {}
        total_tokens = 0
        total_cost = 0.0

        for delegation in delegation_plan.get("delegations", []):
            worker_id = delegation.get("worker_id")
            worker_task = delegation.get("task")
            depends_on = delegation.get("depends_on", [])

            # Wait for dependencies
            for dep in depends_on:
                while dep not in worker_results:
                    await asyncio.sleep(0.1)

            # Get dependency outputs for this worker
            dep_inputs = {dep: worker_results[dep] for dep in depends_on if dep in worker_results}
            worker_inputs = {**inputs, **dep_inputs}

            # Emit delegation event: Team Lead → Worker
            await emit_agent_message(
                agent_id=team_lead.id,
                agent_name=team_lead.name,
                message=f"Delegating to worker: {worker_task}",
                to_agent=worker_id,
                mission_id=mission_id,
            )
            # Emit invocation event for 3D visualization
            await emit_agent_invocation(
                agent_id=team_lead.id,
                agent_name=team_lead.name,
                target_agent_id=worker_id,
                target_agent_name=worker_id,  # Worker ID is also the name
                purpose=f"Worker delegation: {worker_task[:50]}",
                protocol="internal",  # Purple connection for hierarchical
                metadata={"worker_task": worker_task, "workflow_type": "hierarchical"},
                mission_id=mission_id,
            )

            # Execute worker
            worker_result = await self._worker_execute(
                worker_id=worker_id,
                task=worker_task,
                inputs=worker_inputs,
                mission_id=mission_id,
                model_config=config,
            )

            worker_results[worker_id] = worker_result.get("outputs", {})
            total_tokens += worker_result.get("tokens_used", 0)
            total_cost += worker_result.get("estimated_cost", 0.0)

            # Track worker call
            step_exec.worker_calls.append({
                "worker_id": worker_id,
                "task": worker_task,
                "result": worker_results[worker_id],
                "model_used": worker_result.get("model_used"),
            })

        step_exec.state = StepExecutionState.AGGREGATING

        # Step 3: Team Lead aggregates results
        aggregated = await self._aggregate_worker_results(
            team_lead=team_lead,
            task=task,
            worker_results=worker_results,
            mission_id=mission_id,
            model_config=config,
        )

        total_tokens += aggregated.get("tokens_used", 0)
        total_cost += aggregated.get("estimated_cost", 0.0)

        await emit_agent_completed(
            agent_id=team_lead.id,
            agent_name=team_lead.name,
            result=f"Completed with {len(worker_results)} worker tasks",
            mission_id=mission_id,
        )

        return {
            "outputs": aggregated.get("outputs", {}),
            "worker_results": worker_results,
            "tokens_used": total_tokens,
            "estimated_cost": total_cost,
            "model_used": model,
        }

    async def _get_delegation_plan(
        self,
        team_lead: TeamLeadSpec,
        task: str,
        inputs: Dict[str, Any],
        mission_id: str,
        model_config: Optional[ModelConfig] = None,
    ) -> Dict[str, Any]:
        """Team Lead decides how to delegate to workers"""

        config = model_config or self._default_config

        await emit_agent_thinking(
            agent_id=team_lead.id,
            agent_name=team_lead.name,
            thought="Planning task delegation...",
            mission_id=mission_id,
        )

        # Build worker descriptions
        worker_descriptions = "\n".join([
            f"- {w.id}: {w.description}"
            for w in team_lead.workers
        ])

        prompt = f"""{team_lead.system_prompt}

TASK: {task}

INPUTS:
{json.dumps(inputs, indent=2)}

AVAILABLE WORKERS:
{worker_descriptions}

{team_lead.delegation_prompt}

Return a JSON delegation plan."""

        # Use model from config for team lead
        model = ModelRegistry.get_model_for_team_lead(team_lead.domain, config)

        try:
            response = await self.llm_client.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                model=model,
                temperature=team_lead.temperature,
                max_tokens=team_lead.max_tokens,
            )
        except ModelUnavailableError as e:
            # Local model unavailable, fall back to API model
            logger.warning(f"Model {model} unavailable for team lead {team_lead.id}, falling back to API model: {e}")
            fallback_model = config.api_fallback_team_lead
            logger.info(f"Using fallback model: {fallback_model}")
            response = await self.llm_client.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                model=fallback_model,
                temperature=team_lead.temperature,
                max_tokens=team_lead.max_tokens,
            )
            model = fallback_model

        content = self._extract_content(response)
        plan = self._parse_json_from_response(content)

        # Validate worker IDs
        valid_worker_ids = {w.id for w in team_lead.workers}
        plan["delegations"] = [
            d for d in plan.get("delegations", [])
            if d.get("worker_id") in valid_worker_ids
        ]

        return plan

    async def _aggregate_worker_results(
        self,
        team_lead: TeamLeadSpec,
        task: str,
        worker_results: Dict[str, Any],
        mission_id: str,
        model_config: Optional[ModelConfig] = None,
    ) -> Dict[str, Any]:
        """Team Lead aggregates worker results into final output"""

        config = model_config or self._default_config

        await emit_agent_thinking(
            agent_id=team_lead.id,
            agent_name=team_lead.name,
            thought="Aggregating worker results...",
            mission_id=mission_id,
        )

        prompt = f"""{team_lead.system_prompt}

ORIGINAL TASK: {task}

WORKER RESULTS:
{json.dumps(worker_results, indent=2)}

Synthesize these worker results into a coherent final output.
Return JSON with the aggregated outputs."""

        model = ModelRegistry.get_model_for_team_lead(team_lead.domain, config)

        try:
            response = await self.llm_client.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                model=model,
                temperature=team_lead.temperature,
                max_tokens=team_lead.max_tokens,
            )
        except ModelUnavailableError as e:
            # Local model unavailable, fall back to API model
            logger.warning(f"Model {model} unavailable for team lead aggregation {team_lead.id}, falling back to API model: {e}")
            fallback_model = config.api_fallback_team_lead
            logger.info(f"Using fallback model: {fallback_model}")
            response = await self.llm_client.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                model=fallback_model,
                temperature=team_lead.temperature,
                max_tokens=team_lead.max_tokens,
            )
            model = fallback_model

        content = self._extract_content(response)
        outputs = self._parse_json_from_response(content)

        return {
            "outputs": outputs,
            "tokens_used": response.get("usage", {}).get("total_tokens", 0),
            "estimated_cost": ModelRegistry.get_model_cost(
                model,
                response.get("usage", {}).get("prompt_tokens", 0),
                response.get("usage", {}).get("completion_tokens", 0),
            ),
            "model_used": model,
        }

    # =========================================================================
    # Worker Execution
    # =========================================================================

    async def _worker_execute(
        self,
        worker_id: str,
        task: str,
        inputs: Dict[str, Any],
        mission_id: str,
        model_config: Optional[ModelConfig] = None,
    ) -> Dict[str, Any]:
        """Execute a narrow-scope worker task"""

        config = model_config or self._default_config

        worker = get_worker(worker_id)
        if not worker:
            raise ValueError(f"Unknown worker: {worker_id}")

        await emit_agent_started(
            agent_id=worker_id,
            agent_name=worker.name,
            task=task,
            mission_id=mission_id,
        )

        # Build worker prompt with examples
        examples_text = ""
        if worker.examples:
            examples_text = "\nEXAMPLES:\n"
            for ex in worker.examples:
                examples_text += f"Input: {json.dumps(ex['input'])}\n"
                examples_text += f"Output: {json.dumps(ex['output'])}\n\n"

        prompt = f"""{worker.task_prompt}
{examples_text}
INPUT:
{json.dumps(inputs, indent=2)}

Respond with valid JSON matching the output schema."""

        # Use worker model from config (with worker's default as fallback)
        model = ModelRegistry.get_model_for_worker(worker_id, config, worker.model)

        # Execute with automatic fallback on model unavailability
        try:
            # Execute with optional tool
            if worker.tool:
                # Get tool and execute with tool loop
                tools = get_tools_by_names([worker.tool])
                if tools:
                    await emit_tool_call(
                        agent_id=worker_id,
                        agent_name=worker.name,
                        tool_name=worker.tool,
                        arguments=inputs,
                        mission_id=mission_id,
                    )

                    response = await self.llm_client.execute_tool_loop(
                        messages=[{"role": "user", "content": prompt}],
                        tools=tools,
                        model=model,
                        temperature=worker.temperature,
                        max_tokens=worker.max_tokens,
                        max_iterations=3,
                    )

                    await emit_tool_result(
                        agent_id=worker_id,
                        agent_name=worker.name,
                        tool_name=worker.tool,
                        result=response.get("content", "")[:200],
                        mission_id=mission_id,
                    )
                else:
                    response = await self.llm_client.chat_completion(
                        messages=[{"role": "user", "content": prompt}],
                        model=model,
                        temperature=worker.temperature,
                        max_tokens=worker.max_tokens,
                    )
            else:
                response = await self.llm_client.chat_completion(
                    messages=[{"role": "user", "content": prompt}],
                    model=model,
                    temperature=worker.temperature,
                    max_tokens=worker.max_tokens,
                )
        except ModelUnavailableError as e:
            # Local model unavailable, fall back to API model
            logger.warning(f"Model {model} unavailable for worker {worker_id}, falling back to API model: {e}")
            fallback_model = config.api_fallback_worker
            logger.info(f"Using fallback model: {fallback_model}")

            # Retry with fallback model
            if worker.tool:
                tools = get_tools_by_names([worker.tool])
                if tools:
                    response = await self.llm_client.execute_tool_loop(
                        messages=[{"role": "user", "content": prompt}],
                        tools=tools,
                        model=fallback_model,
                        temperature=worker.temperature,
                        max_tokens=worker.max_tokens,
                        max_iterations=3,
                    )
                else:
                    response = await self.llm_client.chat_completion(
                        messages=[{"role": "user", "content": prompt}],
                        model=fallback_model,
                        temperature=worker.temperature,
                        max_tokens=worker.max_tokens,
                    )
            else:
                response = await self.llm_client.chat_completion(
                    messages=[{"role": "user", "content": prompt}],
                    model=fallback_model,
                    temperature=worker.temperature,
                    max_tokens=worker.max_tokens,
                )

            # Update model used to reflect fallback
            model = fallback_model

        content = self._extract_content(response)
        outputs = self._parse_json_from_response(content)

        await emit_agent_completed(
            agent_id=worker_id,
            agent_name=worker.name,
            result=str(outputs)[:200],
            mission_id=mission_id,
        )

        return {
            "outputs": outputs,
            "tokens_used": response.get("usage", {}).get("total_tokens", 0),
            "estimated_cost": ModelRegistry.get_model_cost(
                model,
                response.get("usage", {}).get("prompt_tokens", 0),
                response.get("usage", {}).get("completion_tokens", 0),
            ),
            "model_used": model,
        }

    # =========================================================================
    # Direct Execution (for testing)
    # =========================================================================

    async def execute_team_lead_task(
        self,
        domain: str,
        task: str,
        inputs: Dict[str, Any],
        model_config: Optional[ModelConfig] = None,
    ) -> Dict[str, Any]:
        """
        Directly execute a task with a Team Lead (for testing).

        Args:
            domain: Domain name (research, finance, legal, etc.)
            task: Task description
            inputs: Task inputs
            model_config: Optional model configuration override

        Returns:
            Execution results including worker outputs
        """
        config = model_config or self._default_config

        team_lead = get_team_lead(domain)
        if not team_lead:
            raise ValueError(f"Unknown domain: {domain}")

        # Create a temporary mission
        mission = event_bus.create_mission(
            name=f"{domain} task",
            description=task,
            lead_agent=team_lead.id,
        )

        step_exec = StepExecution(
            step_id="direct",
            state=StepExecutionState.RUNNING,
            started_at=datetime.utcnow(),
        )

        result = await self._team_lead_execute(
            team_lead=team_lead,
            task=task,
            inputs=inputs,
            mission_id=mission.id,
            step_exec=step_exec,
            model_config=config,
        )

        return {
            "domain": domain,
            "team_lead": team_lead.name,
            "model_used": result.get("model_used"),
            "outputs": result.get("outputs", {}),
            "worker_results": result.get("worker_results", {}),
            "tokens_used": result.get("tokens_used", 0),
            "estimated_cost": result.get("estimated_cost", 0.0),
            "execution_time": (datetime.utcnow() - step_exec.started_at).total_seconds(),
        }

    async def execute_worker_task(
        self,
        worker_id: str,
        inputs: Dict[str, Any],
        model_config: Optional[ModelConfig] = None,
    ) -> Dict[str, Any]:
        """
        Directly execute a worker task (for testing).

        Args:
            worker_id: Worker ID
            inputs: Task inputs matching worker's input schema
            model_config: Optional model configuration override

        Returns:
            Worker outputs
        """
        config = model_config or self._default_config

        worker = get_worker(worker_id)
        if not worker:
            raise ValueError(f"Unknown worker: {worker_id}")

        # Create temporary mission
        mission = event_bus.create_mission(
            name=f"Worker: {worker.name}",
            description=worker.description,
            lead_agent=worker_id,
        )

        result = await self._worker_execute(
            worker_id=worker_id,
            task=worker.description,
            inputs=inputs,
            mission_id=mission.id,
            model_config=config,
        )

        return {
            "worker": worker.name,
            "model_used": result.get("model_used"),
            "outputs": result.get("outputs", {}),
            "tokens_used": result.get("tokens_used", 0),
            "estimated_cost": result.get("estimated_cost", 0.0),
        }

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def _extract_content(self, response: Dict[str, Any]) -> str:
        """Extract content from LLM response"""
        if "choices" in response and len(response["choices"]) > 0:
            choice = response["choices"][0]
            if "message" in choice and "content" in choice["message"]:
                return choice["message"]["content"] or ""
        if "content" in response:
            return response["content"] or ""
        return ""

    def _parse_json_from_response(self, text: str) -> Dict[str, Any]:
        """Parse JSON from LLM response, handling markdown code blocks"""
        # Try to find JSON in code block
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # Try to find raw JSON object
        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        # Return as-is wrapped in result
        return {"result": text}

    def _resolve_inputs(
        self,
        input_mapping: Dict[str, str],
        step_outputs: Dict[str, Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Resolve step inputs from previous step outputs"""
        resolved = {}
        for local_name, source_path in input_mapping.items():
            parts = source_path.split(".")
            value = step_outputs
            for part in parts:
                if isinstance(value, dict) and part in value:
                    value = value[part]
                else:
                    value = None
                    break
            resolved[local_name] = value
        return resolved

    def _evaluate_condition(
        self,
        condition: str,
        step_outputs: Dict[str, Dict[str, Any]],
    ) -> bool:
        """Evaluate a step condition"""
        # Simple evaluation - expand as needed
        try:
            # Replace step references with actual values
            for step_id, outputs in step_outputs.items():
                for key, value in outputs.items() if isinstance(outputs, dict) else []:
                    condition = condition.replace(f"{step_id}.{key}", repr(value))
            return eval(condition)
        except Exception:
            return True  # Default to executing if condition can't be evaluated

    def _get_checkpoint_before_step(
        self,
        workflow: WorkflowDefinition,
        step_id: str,
    ) -> Optional[Checkpoint]:
        """Get checkpoint that should occur before a step"""
        for checkpoint in workflow.checkpoints:
            if checkpoint.after_step == step_id:
                return checkpoint
        return None

    def _estimate_cost(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        """Estimate cost for model usage (deprecated - use ModelRegistry.get_model_cost)"""
        return ModelRegistry.get_model_cost(model, input_tokens, output_tokens)

    # =========================================================================
    # Execution Management
    # =========================================================================

    def get_execution(self, execution_id: str) -> Optional[WorkflowExecution]:
        """Get execution by ID"""
        return self._executions.get(execution_id)

    def list_executions(
        self,
        workflow_id: Optional[str] = None,
        state: Optional[WorkflowExecutionState] = None,
    ) -> List[WorkflowExecution]:
        """List executions with optional filters"""
        executions = list(self._executions.values())
        if workflow_id:
            executions = [e for e in executions if e.workflow_id == workflow_id]
        if state:
            executions = [e for e in executions if e.state == state]
        return executions

    async def cancel_execution(self, execution_id: str) -> bool:
        """Cancel a running execution"""
        execution = self._executions.get(execution_id)
        if execution and execution.state == WorkflowExecutionState.RUNNING:
            execution.state = WorkflowExecutionState.CANCELLED
            execution.completed_at = datetime.utcnow()
            await self._persist(execution)  # BR-4: durable cancel
            return True
        return False

    async def resume_execution(
        self,
        execution_id: str,
        checkpoint_response: Dict[str, Any],
    ) -> Optional[WorkflowExecution]:
        """Resume an execution waiting at a checkpoint"""
        execution = self._executions.get(execution_id)
        if not execution or execution.state != WorkflowExecutionState.WAITING_CHECKPOINT:
            return None

        if execution.pending_checkpoint:
            execution.checkpoint_responses[execution.pending_checkpoint] = checkpoint_response
            execution.pending_checkpoint = None
            execution.state = WorkflowExecutionState.RUNNING
            # Continue execution...
            await self._persist(execution)  # BR-4: durable checkpoint response

        return execution


# Global engine instance
workflow_engine: Optional[WorkflowEngine] = None


def get_workflow_engine() -> WorkflowEngine:
    """Get or create the global workflow engine"""
    global workflow_engine
    if workflow_engine is None:
        workflow_engine = WorkflowEngine()
    return workflow_engine


def init_workflow_engine(
    llm_client: OpsCenterLLMClient,
    orchestrator_model: str = "openai/gpt-4o-mini",
    enable_local_models: bool = True,
    model_config: Optional[ModelConfig] = None,
) -> WorkflowEngine:
    """
    Initialize the global workflow engine.

    Args:
        llm_client: LLM client for API calls
        orchestrator_model: Default orchestrator model (if model_config not provided)
        enable_local_models: Enable local models (if model_config not provided)
        model_config: Full model configuration (overrides orchestrator_model and enable_local_models)

    Returns:
        Initialized WorkflowEngine
    """
    global workflow_engine
    workflow_engine = WorkflowEngine(
        llm_client=llm_client,
        orchestrator_model=orchestrator_model,
        enable_local_models=enable_local_models,
        model_config=model_config,
    )
    return workflow_engine
