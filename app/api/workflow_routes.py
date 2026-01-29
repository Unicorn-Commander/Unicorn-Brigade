"""
Workflow Engine API Routes

New Lobster-style workflow execution with:
- Task routing and planning
- Step-by-step execution with approval gates
- Resume tokens for HITL
- Verification and confidence scoring
"""

from fastapi import APIRouter, HTTPException, status, Header, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
import uuid
import json
import asyncio
import logging

from app.engine.models import Task, TaskResult, WorkflowPlan, ResumeToken, RiskLevel
from app.engine.workflow import WorkflowEngine, WorkflowLoader

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/workflow", tags=["workflow"])

# Global workflow engine instance
workflow_engine: Optional[WorkflowEngine] = None


def init_workflow_engine(llm_client=None):
    """Initialize the workflow engine"""
    global workflow_engine
    workflow_engine = WorkflowEngine(llm_client=llm_client)
    logger.info("Workflow engine initialized")


# Request/Response Models

class WorkflowRequest(BaseModel):
    """Request to execute a workflow"""
    task: str = Field(..., description="Task description")
    context: Dict[str, Any] = Field(default_factory=dict, description="Additional context")
    workflow_id: Optional[str] = Field(None, description="Specific workflow definition to use")
    model: str = Field("default", description="LLM model to use")
    stream: bool = Field(False, description="Stream execution events")


class WorkflowResponse(BaseModel):
    """Response from workflow execution"""
    task_id: str
    status: str
    output: Optional[str] = None
    artifacts: List[Dict[str, Any]] = []
    steps_completed: int = 0
    steps_total: int = 0
    requires_approval: bool = False
    approval_token: Optional[str] = None
    confidence: Optional[float] = None
    tokens_used: Dict[str, int] = Field(default_factory=dict)
    duration_seconds: float = 0.0
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ApprovalRequest(BaseModel):
    """Request to approve/reject a pending step"""
    token_id: str = Field(..., description="Resume token ID")
    approved: bool = Field(..., description="Whether to approve")
    feedback: Optional[str] = Field(None, description="Optional feedback")


class ApprovalResponse(BaseModel):
    """Response after approval decision"""
    token_id: str
    approved: bool
    resumed: bool
    task_id: Optional[str] = None
    message: str


class WorkflowListItem(BaseModel):
    """Workflow definition summary"""
    id: str
    name: str
    description: str
    steps_count: int
    requires_approval: bool


# Routes

@router.post("/execute", response_model=WorkflowResponse)
async def execute_workflow(
    request: WorkflowRequest,
    user_id: str = Header("anonymous", alias="X-User-ID"),
    background_tasks: BackgroundTasks = None,
):
    """
    Execute a workflow task.

    The workflow engine will:
    1. Route the task (classify intent, risk, worker)
    2. Plan execution steps
    3. Execute steps with approval gates for risky operations
    4. Verify results and score confidence

    If approval is required, returns with `requires_approval=True` and an approval token.
    """
    if not workflow_engine:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Workflow engine not initialized"
        )

    try:
        # Create task
        task = Task(
            task=request.task,
            user_id=user_id,
            context=request.context,
        )

        # Callbacks for events
        steps_completed = 0
        total_steps = 0
        approval_token = None

        async def on_step_complete(step_id: str, result: Any):
            nonlocal steps_completed
            steps_completed += 1
            logger.info(f"Step {step_id} completed")

        async def on_approval_required(token: ResumeToken):
            nonlocal approval_token
            approval_token = token.id
            logger.info(f"Approval required: {token.id}")

        # Execute workflow
        result = await workflow_engine.execute(
            task=task,
            on_step_complete=on_step_complete,
            on_approval_required=on_approval_required,
            model=request.model,
        )

        # Check if blocked on approval
        if result.status == "pending_approval":
            return WorkflowResponse(
                task_id=result.task_id,
                status="pending_approval",
                output="Workflow paused for approval",
                requires_approval=True,
                approval_token=approval_token,
                steps_completed=steps_completed,
                steps_total=len(result.execution.steps) if result.execution else 0,
            )

        # Build response
        artifacts = []
        if result.execution:
            for step_result in result.execution.results:
                for artifact in step_result.artifacts:
                    artifacts.append({
                        "name": artifact.get("name", "unknown"),
                        "type": artifact.get("type", "text"),
                        "content": artifact.get("content"),
                    })

        return WorkflowResponse(
            task_id=result.task_id,
            status=result.status,
            output=result.output,
            artifacts=artifacts,
            steps_completed=steps_completed,
            steps_total=len(result.execution.steps) if result.execution else 0,
            confidence=result.verification.confidence if result.verification else None,
            tokens_used=result.tokens_used,
            duration_seconds=result.duration_seconds,
        )

    except Exception as e:
        logger.error(f"Workflow execution failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/execute/stream")
async def execute_workflow_stream(
    request: WorkflowRequest,
    user_id: str = Header("anonymous", alias="X-User-ID"),
):
    """
    Execute a workflow with Server-Sent Events streaming.

    Events:
    - start: Workflow started
    - routing: Task routing complete
    - planning: Execution plan ready
    - step_start: Step execution starting
    - step_complete: Step execution complete
    - approval_required: Human approval needed
    - verification: Results verified
    - complete: Workflow finished
    - error: Error occurred
    """
    if not workflow_engine:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Workflow engine not initialized"
        )

    async def generate():
        try:
            task = Task(
                task=request.task,
                user_id=user_id,
                context=request.context,
            )

            # Send start event
            yield f"data: {json.dumps({'type': 'start', 'task_id': task.id})}\n\n"

            async def on_step_complete(step_id: str, result: Any):
                pass  # Handled in streaming

            async def on_approval_required(token: ResumeToken):
                pass  # Handled in streaming

            # Route task
            routing = await workflow_engine.router.route(task)
            yield f"data: {json.dumps({'type': 'routing', 'intent': routing.intent.value, 'risk': routing.risk.value, 'worker': routing.worker.value})}\n\n"
            await asyncio.sleep(0.1)

            # Plan execution
            plan = await workflow_engine.planner.plan(task, routing)
            yield f"data: {json.dumps({'type': 'planning', 'steps_count': len(plan.steps), 'steps': [{'id': s.id, 'name': s.name} for s in plan.steps]})}\n\n"
            await asyncio.sleep(0.1)

            # Execute steps
            for step in plan.steps:
                yield f"data: {json.dumps({'type': 'step_start', 'step_id': step.id, 'step_name': step.name})}\n\n"

                # Check if approval needed
                if step.requires_approval:
                    token = workflow_engine.approval_gate.create_checkpoint(
                        workflow_id=task.id,
                        step=step,
                        context=task.context,
                    )
                    yield f"data: {json.dumps({'type': 'approval_required', 'token_id': token.id, 'step': step.name, 'risk': step.tool.value})}\n\n"
                    # Stop here - workflow will be resumed via /approve endpoint
                    return

                # Execute step
                step_result = await workflow_engine.executor.execute_step(
                    step=step,
                    context=task.context,
                    user_id=user_id,
                    model=request.model,
                )

                yield f"data: {json.dumps({'type': 'step_complete', 'step_id': step.id, 'status': step_result.status.value})}\n\n"
                await asyncio.sleep(0.1)

            # Execute and get full result
            result = await workflow_engine.execute(
                task=task,
                on_step_complete=on_step_complete,
                on_approval_required=on_approval_required,
                model=request.model,
            )

            # Send verification
            if result.verification:
                yield f"data: {json.dumps({'type': 'verification', 'verified': result.verification.verified, 'confidence': result.verification.confidence})}\n\n"

            # Send completion
            yield f"data: {json.dumps({'type': 'complete', 'task_id': result.task_id, 'status': result.status, 'output': result.output[:500] if result.output else None, 'duration': result.duration_seconds})}\n\n"

        except Exception as e:
            logger.error(f"Streaming error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.post("/approve", response_model=ApprovalResponse)
async def approve_step(
    request: ApprovalRequest,
    user_id: str = Header("anonymous", alias="X-User-ID"),
):
    """
    Approve or reject a pending workflow step.

    Use the token_id from a previous workflow execution that returned `requires_approval=True`.
    """
    if not workflow_engine:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Workflow engine not initialized"
        )

    try:
        # Process approval
        if request.approved:
            success = workflow_engine.approval_gate.approve(
                token_id=request.token_id,
                approved_by=user_id,
            )
        else:
            success = workflow_engine.approval_gate.reject(
                token_id=request.token_id,
                rejected_by=user_id,
                reason=request.feedback or "Rejected by user",
            )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Token not found or already processed: {request.token_id}"
            )

        # Get the token to find task ID
        token = workflow_engine.approval_gate.get_pending(request.token_id)

        return ApprovalResponse(
            token_id=request.token_id,
            approved=request.approved,
            resumed=request.approved,
            task_id=token.workflow_id if token else None,
            message="Step approved, workflow will resume" if request.approved else "Step rejected, workflow cancelled"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Approval failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/resume/{token_id}", response_model=WorkflowResponse)
async def resume_workflow(
    token_id: str,
    user_id: str = Header("anonymous", alias="X-User-ID"),
):
    """
    Resume a workflow after approval.

    This continues execution from where it was paused.
    """
    if not workflow_engine:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Workflow engine not initialized"
        )

    try:
        result = await workflow_engine.resume_workflow(
            token_id=token_id,
            approved=True,
        )

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Cannot resume workflow with token: {token_id}"
            )

        return WorkflowResponse(
            task_id=result.task_id,
            status=result.status,
            output=result.output,
            duration_seconds=result.duration_seconds,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Resume failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/pending")
async def list_pending_approvals(
    user_id: str = Header("anonymous", alias="X-User-ID"),
):
    """List all pending approval requests"""
    if not workflow_engine:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Workflow engine not initialized"
        )

    pending = workflow_engine.approval_gate.list_pending()

    return {
        "pending": [
            {
                "token_id": token.id,
                "workflow_id": token.workflow_id,
                "step_id": token.step_id,
                "step_name": token.step_name,
                "created_at": token.created_at.isoformat(),
                "expires_at": token.expires_at.isoformat() if token.expires_at else None,
            }
            for token in pending
        ],
        "count": len(pending),
    }


@router.get("/definitions")
async def list_workflow_definitions():
    """List available workflow definitions"""
    loader = WorkflowLoader()
    workflows = loader.list_workflows()

    return {
        "workflows": [
            WorkflowListItem(
                id=w["id"],
                name=w["name"],
                description=w["description"],
                steps_count=w["steps_count"],
                requires_approval=w.get("requires_approval", False),
            ).model_dump()
            for w in workflows
        ],
        "count": len(workflows),
    }


@router.get("/definitions/{workflow_id}")
async def get_workflow_definition(workflow_id: str):
    """Get a specific workflow definition"""
    loader = WorkflowLoader()

    try:
        workflow = loader.load_workflow(workflow_id)
        return {
            "id": workflow_id,
            "workflow": workflow,
        }
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow not found: {workflow_id}"
        )


@router.get("/workers")
async def list_workers():
    """List available workers"""
    from app.workers import list_workers as get_workers

    workers = get_workers()

    return {
        "workers": workers,
        "count": len(workers),
    }


@router.get("/status")
async def workflow_status():
    """Get workflow engine status"""
    if not workflow_engine:
        return {
            "status": "unavailable",
            "message": "Workflow engine not initialized",
        }

    pending = workflow_engine.approval_gate.list_pending()

    return {
        "status": "operational",
        "pending_approvals": len(pending),
        "components": {
            "router": "ready",
            "planner": "ready",
            "executor": "ready",
            "verifier": "ready",
            "approval_gate": "ready",
        },
    }
