"""
Hierarchical Workflow API Routes - 3-Tier Agent Orchestration

This module provides endpoints for the 3-tier agent hierarchy:
- Orchestrator (The General) → Team Leads → Workers

Endpoints:
- Workflow execution and management
- Team Lead direct invocation
- Worker direct invocation (testing)
- Domain and model information
"""

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Annotated
import logging

from app.auth.middleware import require_api_key, require_operator, require_admin, AuthUser
from app.integrations.metering import meter_usage
from app.workflows import (
    WorkflowEngine,
    WorkflowExecutionState,
    get_workflow_engine,
    init_workflow_engine,
    get_team_lead,
    get_worker,
    get_workers_for_domain,
    get_model_summary,
    ALL_TEAM_LEADS,
    ALL_WORKERS,
    # Model configuration
    ModelConfig,
    ModelRegistry,
    CONFIG_PRESETS,
    create_config_from_request,
    list_available_presets,
    estimate_workflow_cost,
)
from app.workflows.templates import (
    ALL_WORKFLOWS,
    get_workflow,
    list_workflows as list_workflow_templates,
    get_workflows_by_tag,
)
from app.llm.ops_center_client import OpsCenterLLMClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/hierarchical", tags=["hierarchical-workflows"])

# Global engine reference
hierarchical_engine: Optional[WorkflowEngine] = None


def init_hierarchical_routes(llm_client: OpsCenterLLMClient, enable_local_models: bool = True):
    """Initialize hierarchical workflow routes with LLM client"""
    global hierarchical_engine
    hierarchical_engine = init_workflow_engine(
        llm_client=llm_client,
        orchestrator_model="anthropic/claude-opus-4-5-20251101",
        enable_local_models=enable_local_models,
    )
    logger.info("Hierarchical workflow routes initialized")


def get_engine() -> WorkflowEngine:
    """Dependency to get workflow engine"""
    if hierarchical_engine is None:
        raise HTTPException(status_code=503, detail="Hierarchical engine not initialized")
    return hierarchical_engine


# =============================================================================
# Request/Response Models
# =============================================================================

class ModelConfigInput(BaseModel):
    """Model configuration input for API requests"""
    preset: Optional[str] = Field(None, description="Preset name: cost_optimized, quality_optimized, full_api, full_local, finance_specialized, legal_specialized")
    orchestrator_model: Optional[str] = Field(None, description="Override orchestrator model")
    team_lead_models: Optional[Dict[str, str]] = Field(None, description="Override team lead models by domain")
    worker_models: Optional[Dict[str, str]] = Field(None, description="Override worker models by worker_id")
    enable_local_models: Optional[bool] = Field(None, description="Enable/disable local models")


class ExecuteWorkflowRequest(BaseModel):
    """Request to execute a workflow with optional model configuration."""
    model_config = {"protected_namespaces": ()}  # Allow field names starting with "model_"

    workflow_id: str = Field(..., description="ID of the workflow template to execute")
    inputs: Dict[str, Any] = Field(..., description="Input values for the workflow")
    async_execution: bool = Field(False, description="Run in background and return immediately")
    model_configuration: Optional[ModelConfigInput] = Field(None, description="Optional model configuration override", alias="model_config")


class ExecuteWorkflowResponse(BaseModel):
    """Response from workflow execution."""
    model_config = {"protected_namespaces": ()}  # Allow field names starting with "model_"

    execution_id: str
    workflow_id: str
    workflow_name: str
    state: str
    message: str
    outputs: Optional[Dict[str, Any]] = None
    total_cost: Optional[float] = None
    total_tokens: Optional[int] = None
    model_config_used: Optional[Dict[str, Any]] = None


class TeamLeadTaskRequest(BaseModel):
    """Request to execute a task with a team lead."""
    model_config = {"protected_namespaces": ()}  # Allow field names starting with "model_"

    task: str = Field(..., description="Task description")
    inputs: Dict[str, Any] = Field(default_factory=dict, description="Task inputs")
    model_configuration: Optional[ModelConfigInput] = Field(None, description="Optional model configuration override", alias="model_config")


class WorkerTaskRequest(BaseModel):
    """Request to execute a task with a worker."""
    model_config = {"protected_namespaces": ()}  # Allow field names starting with "model_"

    inputs: Dict[str, Any] = Field(..., description="Inputs matching worker's input schema")
    model_configuration: Optional[ModelConfigInput] = Field(None, description="Optional model configuration override", alias="model_config")


class CheckpointResponse(BaseModel):
    execution_id: str = Field(..., description="Execution ID")
    checkpoint_id: str = Field(..., description="Checkpoint ID")
    response: Dict[str, Any] = Field(..., description="Checkpoint response (e.g., approved: true)")


# =============================================================================
# Workflow Templates
# =============================================================================

@router.get("/templates")
async def list_templates(
    tag: Optional[str] = Query(None, description="Filter by tag"),
    user: Annotated[AuthUser, Depends(require_api_key)] = None,
):
    """
    List all available 3-tier workflow templates.

    Templates define multi-step workflows that coordinate:
    - Orchestrator (The General)
    - Team Leads (domain experts)
    - Workers (narrow-scope executors)
    """
    if tag:
        workflows = get_workflows_by_tag(tag)
        return {
            "workflows": [
                {
                    "id": w.id,
                    "name": w.name,
                    "description": w.description,
                    "tags": w.tags,
                    "requiredInputs": w.required_inputs,
                    "stepCount": len(w.steps),
                    "checkpointCount": len(w.checkpoints),
                }
                for w in workflows
            ],
            "count": len(workflows),
            "filter": {"tag": tag},
        }
    else:
        return {
            "workflows": list_workflow_templates(),
            "count": len(ALL_WORKFLOWS),
        }


@router.get("/templates/{workflow_id}")
async def get_template(
    workflow_id: str,
    user: Annotated[AuthUser, Depends(require_api_key)] = None,
):
    """Get detailed workflow template including steps and checkpoints"""
    workflow = get_workflow(workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail=f"Workflow not found: {workflow_id}")

    return {
        "workflow": workflow.to_dict(),
    }


# =============================================================================
# Workflow Execution
# =============================================================================

@router.post("/execute", response_model=ExecuteWorkflowResponse)
async def execute_workflow(
    request: ExecuteWorkflowRequest,
    background_tasks: BackgroundTasks,
    engine: WorkflowEngine = Depends(get_engine),
    user: Annotated[AuthUser, Depends(require_operator)] = None,
):
    """
    Execute a 3-tier hierarchical workflow.

    The workflow is executed by The General (orchestrator) who coordinates
    Team Leads (domain experts), who in turn delegate to specialized Workers
    (narrow-scope executors optimized for local models).

    Cost Optimization:
    - Orchestrator: API model (GPT-4o-mini) for complex reasoning
    - Team Leads: 7B-14B local models for domain understanding
    - Workers: 1B-3B local models for narrow tasks (essentially free)

    Model Configuration:
    - Use `model_config.preset` for a preset configuration
    - Override specific models with `model_config.orchestrator_model`, etc.
    - Available presets: cost_optimized, quality_optimized, full_api, full_local
    """
    workflow = get_workflow(request.workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail=f"Workflow not found: {request.workflow_id}")

    # Validate required inputs
    missing_inputs = [inp for inp in workflow.required_inputs if inp not in request.inputs]
    if missing_inputs:
        raise HTTPException(
            status_code=400,
            detail=f"Missing required inputs: {missing_inputs}"
        )

    # Build model configuration from request
    model_config = None
    if request.model_configuration:
        try:
            overrides = {}
            if request.model_configuration.orchestrator_model:
                overrides["orchestrator_model"] = request.model_configuration.orchestrator_model
            if request.model_configuration.team_lead_models:
                overrides["team_lead_models"] = request.model_configuration.team_lead_models
            if request.model_configuration.worker_models:
                overrides["worker_models"] = request.model_configuration.worker_models
            if request.model_configuration.enable_local_models is not None:
                overrides["enable_local_models"] = request.model_configuration.enable_local_models

            model_config = create_config_from_request(
                preset=request.model_configuration.preset,
                overrides=overrides if overrides else None,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    # BR-3.4: capture the caller's org/user so a background (async) workflow can
    # still be metered against the right tenant once it finishes.
    _wf_org_id = getattr(user, "org_id", None)
    _wf_user = (getattr(user, "email", "") or "").lower() or None

    async def _meter_workflow(execution):
        """Meter a finished hierarchical workflow against the caller's org. Records
        the engine's own token/cost tally to the durable ledger (org attribution +
        per-org cap visibility); no Lago COGS emit — the per-tier model calls are
        tallied by the engine and cloud tiers meter themselves upstream, so this
        avoids double-charging. Best-effort."""
        try:
            _mcfg = getattr(execution, "model_config_used", None)
            await meter_usage(
                org_id=_wf_org_id,
                user=_wf_user,
                source="hierarchical",
                event_type="workflow",
                model=(_mcfg or {}).get("orchestrator_model") if isinstance(_mcfg, dict) else None,
                tokens=int(getattr(execution, "total_tokens", 0) or 0),
                cost=float(getattr(execution, "total_cost", 0.0) or 0.0),
                is_local=False,
                emit_value=False,
                meta={
                    "workflow_id": workflow.id,
                    "execution_id": getattr(execution, "id", None),
                    "state": getattr(getattr(execution, "state", None), "value", None),
                },
            )
        except Exception as _me:
            logger.debug(f"workflow meter skipped: {_me}")

    if request.async_execution:
        # Run in background
        async def run_workflow():
            try:
                _exec = await engine.execute_workflow(workflow, request.inputs, model_config=model_config)
                await _meter_workflow(_exec)
            except Exception as e:
                logger.error(f"Background workflow execution failed: {e}")

        background_tasks.add_task(run_workflow)

        return ExecuteWorkflowResponse(
            execution_id="pending",
            workflow_id=workflow.id,
            workflow_name=workflow.name,
            state="queued",
            message="Workflow queued for execution",
            model_config_used=model_config.model_dump() if model_config else None,
        )
    else:
        # Synchronous execution
        execution = await engine.execute_workflow(workflow, request.inputs, model_config=model_config)
        await _meter_workflow(execution)  # BR-3.4

        return ExecuteWorkflowResponse(
            execution_id=execution.id,
            workflow_id=workflow.id,
            workflow_name=workflow.name,
            state=execution.state.value,
            message=f"Workflow {execution.state.value}",
            outputs=execution.outputs if execution.state == WorkflowExecutionState.COMPLETED else None,
            total_cost=execution.total_cost,
            total_tokens=execution.total_tokens,
            model_config_used=execution.model_config_used,
        )


@router.get("/executions")
async def list_executions(
    workflow_id: Optional[str] = Query(None, description="Filter by workflow ID"),
    state: Optional[str] = Query(None, description="Filter by state"),
    engine: WorkflowEngine = Depends(get_engine),
    user: Annotated[AuthUser, Depends(require_api_key)] = None,
):
    """List workflow executions"""
    state_filter = None
    if state:
        try:
            state_filter = WorkflowExecutionState(state)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid state: {state}")

    executions = engine.list_executions(workflow_id=workflow_id, state=state_filter)

    return {
        "executions": [e.to_dict() for e in executions],
        "count": len(executions),
    }


@router.get("/executions/{execution_id}")
async def get_execution(
    execution_id: str,
    engine: WorkflowEngine = Depends(get_engine),
    user: Annotated[AuthUser, Depends(require_api_key)] = None,
):
    """Get execution details including step-by-step results"""
    execution = engine.get_execution(execution_id)
    if not execution:
        raise HTTPException(status_code=404, detail=f"Execution not found: {execution_id}")

    return {
        "execution": execution.to_dict(),
    }


@router.post("/executions/{execution_id}/cancel")
async def cancel_execution(
    execution_id: str,
    engine: WorkflowEngine = Depends(get_engine),
    user: Annotated[AuthUser, Depends(require_operator)] = None,
):
    """Cancel a running execution"""
    success = await engine.cancel_execution(execution_id)
    if not success:
        raise HTTPException(
            status_code=400,
            detail="Could not cancel execution (may not be running)"
        )

    return {"message": "Execution cancelled", "execution_id": execution_id}


@router.post("/executions/{execution_id}/checkpoint")
async def respond_to_checkpoint(
    execution_id: str,
    request: CheckpointResponse,
    engine: WorkflowEngine = Depends(get_engine),
    user: Annotated[AuthUser, Depends(require_operator)] = None,
):
    """Respond to a workflow checkpoint (human-in-the-loop)"""
    execution = await engine.resume_execution(execution_id, request.response)
    if not execution:
        raise HTTPException(
            status_code=400,
            detail="Could not resume execution (may not be waiting at checkpoint)"
        )

    return {
        "message": "Checkpoint response processed",
        "execution": execution.to_dict(),
    }


# =============================================================================
# Team Leads (Domain Experts)
# =============================================================================

@router.get("/domains")
async def list_domains(
    user: Annotated[AuthUser, Depends(require_api_key)] = None,
):
    """
    List all available domains and their team leads.

    Domains:
    - research: Deep research, OSINT, fact verification
    - finance: Financial analysis, calculations, projections
    - content: Writing, editing, SEO, social media
    - sales: Lead research, outreach, CRM operations
    - devops: Monitoring, incident response, deployments
    - legal: Case analysis, document drafting, FOIA
    - medical: Clinical analysis, compliance, documentation
    - investigation: Evidence collection, timeline, patterns
    """
    domains = []
    for lead in ALL_TEAM_LEADS.values():
        domains.append({
            "domain": lead.domain,
            "teamLead": {
                "id": lead.id,
                "name": lead.name,
                "description": lead.description,
                "model": lead.model,
            },
            "workers": [
                {
                    "id": w.id,
                    "name": w.name,
                    "description": w.description,
                    "model": w.model,
                }
                for w in lead.workers
            ],
            "workerCount": len(lead.workers),
        })

    return {
        "domains": domains,
        "count": len(domains),
    }


@router.get("/domains/{domain}")
async def get_domain_details(
    domain: str,
    user: Annotated[AuthUser, Depends(require_api_key)] = None,
):
    """Get detailed information about a domain including team lead and all workers"""
    team_lead = get_team_lead(domain)
    if not team_lead:
        raise HTTPException(status_code=404, detail=f"Domain not found: {domain}")

    return {
        "domain": domain,
        "teamLead": team_lead.to_dict(),
    }


@router.post("/domains/{domain}/execute")
async def execute_domain_task(
    domain: str,
    request: TeamLeadTaskRequest,
    engine: WorkflowEngine = Depends(get_engine),
    user: Annotated[AuthUser, Depends(require_operator)] = None,
):
    """
    Execute a task with a specific domain's Team Lead.

    The Team Lead will:
    1. Analyze the task
    2. Delegate to appropriate workers
    3. Aggregate results
    4. Return the combined output

    This is useful for:
    - Testing domain capabilities
    - Single-domain tasks
    - Bypassing the orchestrator for simple tasks

    Model Configuration:
    - Use `model_config.preset` for a preset configuration
    - Override the team lead model with `model_config.team_lead_models`
    """
    team_lead = get_team_lead(domain)
    if not team_lead:
        raise HTTPException(status_code=404, detail=f"Domain not found: {domain}")

    # Build model configuration from request
    model_config = None
    if request.model_configuration:
        try:
            overrides = {}
            if request.model_configuration.orchestrator_model:
                overrides["orchestrator_model"] = request.model_configuration.orchestrator_model
            if request.model_configuration.team_lead_models:
                overrides["team_lead_models"] = request.model_configuration.team_lead_models
            if request.model_configuration.worker_models:
                overrides["worker_models"] = request.model_configuration.worker_models
            if request.model_configuration.enable_local_models is not None:
                overrides["enable_local_models"] = request.model_configuration.enable_local_models

            model_config = create_config_from_request(
                preset=request.model_configuration.preset,
                overrides=overrides if overrides else None,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    result = await engine.execute_team_lead_task(
        domain=domain,
        task=request.task,
        inputs=request.inputs,
        model_config=model_config,
    )

    return {
        "domain": domain,
        "teamLead": team_lead.name,
        "modelUsed": result.get("model_used"),
        "result": result,
    }


# =============================================================================
# Workers (Narrow-Scope Executors)
# =============================================================================

@router.get("/workers")
async def list_workers(
    domain: Optional[str] = Query(None, description="Filter by domain"),
    user: Annotated[AuthUser, Depends(require_api_key)] = None,
):
    """
    List all workers, optionally filtered by domain.

    Workers are narrow-scope executors optimized for small local models (1B-3B).
    They have well-defined input/output schemas and focus on single tasks.
    """
    if domain:
        workers = get_workers_for_domain(domain)
        if not workers:
            raise HTTPException(status_code=404, detail=f"Domain not found: {domain}")
    else:
        workers = list(ALL_WORKERS.values())

    return {
        "workers": [
            {
                "id": w.id,
                "name": w.name,
                "description": w.description,
                "model": w.model,
                "tool": w.tool,
                "inputSchema": w.input_schema,
                "outputSchema": w.output_schema,
            }
            for w in workers
        ],
        "count": len(workers),
        "filter": {"domain": domain} if domain else None,
    }


@router.get("/workers/{worker_id}")
async def get_worker_details(
    worker_id: str,
    user: Annotated[AuthUser, Depends(require_api_key)] = None,
):
    """Get detailed worker information including prompt and examples"""
    worker = get_worker(worker_id)
    if not worker:
        raise HTTPException(status_code=404, detail=f"Worker not found: {worker_id}")

    return {
        "worker": worker.to_dict(),
    }


@router.post("/workers/{worker_id}/execute")
async def execute_worker_task(
    worker_id: str,
    request: WorkerTaskRequest,
    engine: WorkflowEngine = Depends(get_engine),
    user: Annotated[AuthUser, Depends(require_operator)] = None,
):
    """
    Execute a task directly with a worker (for testing).

    Workers are designed for small local models and have:
    - Single, well-defined purpose
    - Strict input/output schema
    - Optimized prompts with few-shot examples

    Useful for testing worker behavior before using in workflows.

    Model Configuration:
    - Use `model_config.preset` for a preset configuration
    - Override the worker model with `model_config.worker_models`
    """
    worker = get_worker(worker_id)
    if not worker:
        raise HTTPException(status_code=404, detail=f"Worker not found: {worker_id}")

    # Build model configuration from request
    model_config = None
    if request.model_configuration:
        try:
            overrides = {}
            if request.model_configuration.orchestrator_model:
                overrides["orchestrator_model"] = request.model_configuration.orchestrator_model
            if request.model_configuration.team_lead_models:
                overrides["team_lead_models"] = request.model_configuration.team_lead_models
            if request.model_configuration.worker_models:
                overrides["worker_models"] = request.model_configuration.worker_models
            if request.model_configuration.enable_local_models is not None:
                overrides["enable_local_models"] = request.model_configuration.enable_local_models

            model_config = create_config_from_request(
                preset=request.model_configuration.preset,
                overrides=overrides if overrides else None,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    result = await engine.execute_worker_task(
        worker_id=worker_id,
        inputs=request.inputs,
        model_config=model_config,
    )

    return {
        "workerId": worker_id,
        "workerName": worker.name,
        "modelUsed": result.get("model_used"),
        "result": result,
    }


# =============================================================================
# Model Information & Configuration
# =============================================================================

@router.get("/models")
async def get_models_summary(
    user: Annotated[AuthUser, Depends(require_api_key)] = None,
):
    """
    Get summary of models used across the 3-tier hierarchy.

    Model Tiers:
    - Orchestrator: GPT-4o-mini (API) - complex reasoning
    - Team Leads: 7B-14B local - domain understanding
    - Workers: 1B-3B local - narrow tasks (essentially free)
    """
    summary = get_model_summary()

    summary["costEstimates"] = {
        "orchestrator": "~$0.00015/1K input, $0.0006/1K output",
        "teamLeads": "Free (local Ollama models)",
        "workers": "Free (local Ollama models)",
        "note": "Local models require Ollama with specified models pulled",
    }

    summary["requiredModels"] = {
        "teamLeads": [
            "ollama/llama3.1:8b",
            "ollama/gemma2:9b",
        ],
        "workers": [
            "ollama/llama3.2:3b",
            "ollama/phi3:3.8b",
            "ollama/qwen2.5-math:1.5b",
            "ollama/tinyllama:1.1b",
            "ollama/mistral:7b",
        ],
    }

    return summary


@router.get("/config/presets")
async def list_config_presets(
    user: Annotated[AuthUser, Depends(require_api_key)] = None,
):
    """
    List all available model configuration presets.

    Presets:
    - cost_optimized: Local models everywhere, API only for orchestrator
    - quality_optimized: API team leads, local workers
    - full_api: API models everywhere (highest quality, highest cost)
    - full_local: Local models everywhere (requires good GPU)
    - finance_specialized: Optimized for financial analysis
    - legal_specialized: Optimized for legal analysis
    """
    return {
        "presets": list_available_presets(),
        "count": len(CONFIG_PRESETS),
    }


@router.get("/config/presets/{preset_name}")
async def get_config_preset(
    preset_name: str,
    user: Annotated[AuthUser, Depends(require_api_key)] = None,
):
    """Get detailed configuration for a specific preset"""
    if preset_name not in CONFIG_PRESETS:
        raise HTTPException(
            status_code=404,
            detail=f"Preset not found: {preset_name}. Available: {', '.join(CONFIG_PRESETS.keys())}"
        )

    config = CONFIG_PRESETS[preset_name]
    return {
        "presetName": preset_name,
        "configuration": config.model_dump(),
    }


class CostEstimateRequest(BaseModel):
    """Request to estimate workflow execution cost."""
    model_config = {"protected_namespaces": ()}  # Allow field names starting with "model_"

    workflow_id: str = Field(..., description="ID of the workflow to estimate")
    model_configuration: Optional[ModelConfigInput] = Field(None, description="Optional model configuration", alias="model_config")
    avg_tokens_per_step: int = Field(2000, description="Average tokens per workflow step")
    avg_worker_tokens: int = Field(500, description="Average tokens per worker call")


@router.post("/config/estimate-cost")
async def estimate_workflow_cost_endpoint(
    request: CostEstimateRequest,
    user: Annotated[AuthUser, Depends(require_api_key)] = None,
):
    """
    Estimate the cost of running a workflow with a given model configuration.

    Helps with cost planning before executing workflows.
    Compare different presets to find the right cost/quality balance.
    """
    workflow = get_workflow(request.workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail=f"Workflow not found: {request.workflow_id}")

    # Build model configuration
    model_config = None
    if request.model_configuration:
        try:
            overrides = {}
            if request.model_configuration.orchestrator_model:
                overrides["orchestrator_model"] = request.model_configuration.orchestrator_model
            if request.model_configuration.team_lead_models:
                overrides["team_lead_models"] = request.model_configuration.team_lead_models
            if request.model_configuration.worker_models:
                overrides["worker_models"] = request.model_configuration.worker_models
            if request.model_configuration.enable_local_models is not None:
                overrides["enable_local_models"] = request.model_configuration.enable_local_models

            model_config = create_config_from_request(
                preset=request.model_configuration.preset,
                overrides=overrides if overrides else None,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    else:
        model_config = ModelConfig()

    estimate = estimate_workflow_cost(
        workflow=workflow,
        config=model_config,
        avg_tokens_per_step=request.avg_tokens_per_step,
        avg_worker_tokens=request.avg_worker_tokens,
    )

    return {
        "workflowId": workflow.id,
        "workflowName": workflow.name,
        "modelConfig": model_config.model_dump(),
        "costEstimate": estimate,
    }


# =============================================================================
# Health Check
# =============================================================================

@router.get("/health")
async def hierarchical_health(
    user: Annotated[AuthUser, Depends(require_api_key)] = None,
):
    """Check hierarchical workflow subsystem health"""
    engine = hierarchical_engine

    return {
        "status": "healthy" if engine else "unavailable",
        "engine_initialized": engine is not None,
        "template_count": len(ALL_WORKFLOWS),
        "domain_count": len(ALL_TEAM_LEADS),
        "worker_count": len(ALL_WORKERS),
        "active_executions": len(engine.list_executions(state=WorkflowExecutionState.RUNNING)) if engine else 0,
        "architecture": {
            "orchestrator": "The General (GPT-4o-mini)",
            "teamLeads": f"{len(ALL_TEAM_LEADS)} domains",
            "workers": f"{len(ALL_WORKERS)} narrow-scope executors",
        },
    }
