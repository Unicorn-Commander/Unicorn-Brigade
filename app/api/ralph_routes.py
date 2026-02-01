"""
Ralph Self-Correction API Routes

Endpoints for managing self-correcting workflows with iterative improvement.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

from app.workflows.ralph_engine import (
    RalphWorkflowEngine,
    RalphWorkflowState,
    TaskStatus,
    IterationOutcome,
)
from app.workflows import get_workflow

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/ralph", tags=["ralph"])

# In-memory registry of active Ralph executions
_active_executions: Dict[str, RalphWorkflowEngine] = {}


# ===================================================================
# Request/Response Models
# ===================================================================

class RalphExecutionRequest(BaseModel):
    """Request to execute a workflow with Ralph self-correction"""
    workflow_id: str = Field(..., description="ID of workflow template to execute")
    inputs: Dict[str, Any] = Field(default_factory=dict, description="Workflow inputs")
    max_iterations: int = Field(default=5, ge=1, le=10, description="Maximum retry iterations")
    async_execution: bool = Field(default=False, description="Run in background")


class RalphGuidanceRequest(BaseModel):
    """Request to inject guidance mid-execution"""
    guidance: str = Field(..., description="Guidance text to inject", min_length=1)


class RalphExecutionResponse(BaseModel):
    """Response with execution details"""
    execution_id: str
    workflow_id: str
    status: str  # running, paused, completed, failed
    message: str


class RalphProgressResponse(BaseModel):
    """Response with current progress"""
    execution_id: str
    workflow_id: str
    iteration: int
    max_iterations: int
    is_complete: bool
    is_paused: bool
    tasks: Dict[str, int]  # total, completed, failed, in_progress, pending
    progress_percent: int


class RalphResultResponse(BaseModel):
    """Response with final result and history"""
    execution_id: str
    workflow_id: str
    outcome: str  # success, failed
    iterations: int
    tasks: Dict[str, Any]
    iteration_history: list
    guidance_history: list
    created_at: str
    updated_at: str


# ===================================================================
# Endpoints
# ===================================================================

@router.post("/execute", response_model=RalphExecutionResponse)
async def execute_workflow_with_ralph(
    request: RalphExecutionRequest,
    background_tasks: BackgroundTasks
) -> RalphExecutionResponse:
    """
    Execute a workflow with Ralph self-correction.

    Ralph automatically retries failed tasks with improved context from
    previous errors, enabling workflows to self-correct and complete
    successfully even when individual tasks fail.

    Example:
    ```json
    {
      "workflow_id": "investment_due_diligence",
      "inputs": {
        "company_name": "Acme Corp",
        "investment_amount": 5000000
      },
      "max_iterations": 5,
      "async_execution": true
    }
    ```
    """
    try:
        # Get workflow template
        workflow_def = get_workflow(request.workflow_id)
        if not workflow_def:
            raise HTTPException(status_code=404, detail=f"Workflow '{request.workflow_id}' not found")

        # Create Ralph engine
        ralph_engine = RalphWorkflowEngine(
            workflow_id=request.workflow_id,
            workflow_definition=workflow_def.model_dump() if hasattr(workflow_def, 'model_dump') else workflow_def.dict(),
            state_dir=Path(".ralph"),
        )

        # Override max iterations if specified
        if request.max_iterations != 5:
            ralph_engine.state.max_iterations = request.max_iterations

        # Register execution
        execution_id = ralph_engine._generate_execution_id()
        _active_executions[execution_id] = ralph_engine

        if request.async_execution:
            # Run in background
            background_tasks.add_task(_execute_ralph_workflow, ralph_engine, request.inputs, execution_id)
            return RalphExecutionResponse(
                execution_id=execution_id,
                workflow_id=request.workflow_id,
                status="running",
                message=f"Workflow execution started in background. Use GET /ralph/executions/{execution_id} to monitor progress."
            )
        else:
            # Run synchronously
            result = await ralph_engine.execute(request.inputs, execution_id=execution_id)

            return RalphExecutionResponse(
                execution_id=execution_id,
                workflow_id=request.workflow_id,
                status=result.get("outcome", "unknown"),
                message=f"Workflow completed with outcome: {result.get('outcome')}"
            )

    except Exception as e:
        logger.error(f"Error executing Ralph workflow: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/executions/{execution_id}", response_model=RalphProgressResponse)
async def get_execution_progress(execution_id: str) -> RalphProgressResponse:
    """
    Get current progress of a Ralph workflow execution.

    Returns task breakdown with completion status, current iteration,
    and overall progress percentage.
    """
    ralph_engine = _active_executions.get(execution_id)
    if not ralph_engine:
        raise HTTPException(status_code=404, detail=f"Execution '{execution_id}' not found")

    progress = ralph_engine.get_progress()

    return RalphProgressResponse(
        execution_id=execution_id,
        workflow_id=progress["workflow_id"],
        iteration=progress["iteration"],
        max_iterations=progress["max_iterations"],
        is_complete=progress["is_complete"],
        is_paused=progress["is_paused"],
        tasks=progress["tasks"],
        progress_percent=progress["progress_percent"]
    )


@router.get("/executions/{execution_id}/result", response_model=RalphResultResponse)
async def get_execution_result(execution_id: str) -> RalphResultResponse:
    """
    Get final result and complete history of a Ralph workflow execution.

    Includes:
    - All task results
    - Iteration history with error summaries
    - Guidance injection history
    - Overall outcome
    """
    ralph_engine = _active_executions.get(execution_id)
    if not ralph_engine:
        raise HTTPException(status_code=404, detail=f"Execution '{execution_id}' not found")

    if not ralph_engine.state or not ralph_engine.state.is_complete:
        raise HTTPException(status_code=400, detail="Execution not yet complete")

    result = ralph_engine._build_result()

    return RalphResultResponse(
        execution_id=result["execution_id"],
        workflow_id=result["workflow_id"],
        outcome=result["outcome"],
        iterations=result["iterations"],
        tasks=result["tasks"],
        iteration_history=result["iteration_history"],
        guidance_history=result["guidance_history"],
        created_at=result["created_at"],
        updated_at=result["updated_at"]
    )


@router.post("/executions/{execution_id}/guidance", response_model=RalphExecutionResponse)
async def inject_guidance(execution_id: str, request: RalphGuidanceRequest) -> RalphExecutionResponse:
    """
    Inject guidance mid-execution (without restart).

    This allows human-in-the-loop or supervisor agents to provide
    additional context when a workflow is paused or stuck.

    The guidance will be included in the next task execution attempt.

    Example:
    ```json
    {
      "guidance": "Focus on financial metrics from Q4 2025 specifically, ignore earlier data."
    }
    ```
    """
    ralph_engine = _active_executions.get(execution_id)
    if not ralph_engine:
        raise HTTPException(status_code=404, detail=f"Execution '{execution_id}' not found")

    ralph_engine.inject_guidance(request.guidance)

    return RalphExecutionResponse(
        execution_id=execution_id,
        workflow_id=ralph_engine.workflow_id,
        status="running" if not ralph_engine.state.is_paused else "paused",
        message=f"Guidance injected successfully. Execution will resume with new context."
    )


@router.get("/executions", response_model=list)
async def list_executions() -> list:
    """
    List all active Ralph workflow executions.

    Returns summary of each execution with current status.
    """
    executions = []
    for execution_id, ralph_engine in _active_executions.items():
        progress = ralph_engine.get_progress()
        executions.append({
            "execution_id": execution_id,
            "workflow_id": progress["workflow_id"],
            "iteration": progress["iteration"],
            "max_iterations": progress["max_iterations"],
            "is_complete": progress["is_complete"],
            "is_paused": progress["is_paused"],
            "progress_percent": progress["progress_percent"],
            "status": ralph_engine.state.final_outcome if ralph_engine.state.is_complete else "running"
        })

    return executions


@router.delete("/executions/{execution_id}")
async def cancel_execution(execution_id: str) -> Dict[str, str]:
    """
    Cancel a running Ralph workflow execution.

    Note: This removes the execution from the active registry.
    State files are preserved in .ralph/ directory.
    """
    if execution_id not in _active_executions:
        raise HTTPException(status_code=404, detail=f"Execution '{execution_id}' not found")

    ralph_engine = _active_executions[execution_id]

    # Mark as cancelled if still running
    if ralph_engine.state and not ralph_engine.state.is_complete:
        ralph_engine.state.is_complete = True
        ralph_engine.state.final_outcome = "cancelled"
        ralph_engine._save_state()

    # Remove from active executions
    del _active_executions[execution_id]

    return {
        "status": "success",
        "message": f"Execution '{execution_id}' cancelled and removed from active executions"
    }


@router.get("/health")
async def health_check() -> Dict[str, Any]:
    """Ralph subsystem health check"""
    return {
        "status": "healthy",
        "active_executions": len(_active_executions),
        "executions": [
            {
                "id": exec_id,
                "workflow_id": engine.workflow_id,
                "is_complete": engine.state.is_complete if engine.state else False
            }
            for exec_id, engine in _active_executions.items()
        ]
    }


# ===================================================================
# Background Task
# ===================================================================

async def _execute_ralph_workflow(
    ralph_engine: RalphWorkflowEngine,
    inputs: Dict[str, Any],
    execution_id: str
):
    """Background task for async workflow execution"""
    try:
        await ralph_engine.execute(inputs, execution_id=execution_id)
        logger.info(f"Ralph workflow {execution_id} completed successfully")
    except Exception as e:
        logger.error(f"Ralph workflow {execution_id} failed: {e}", exc_info=True)
        if ralph_engine.state:
            ralph_engine.state.is_complete = True
            ralph_engine.state.final_outcome = "failed"
            ralph_engine._save_state()
