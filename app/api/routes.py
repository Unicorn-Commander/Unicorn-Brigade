"""API routes"""

from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.responses import StreamingResponse
from typing import Dict, Any, Annotated
import uuid
import logging
import json
import asyncio
from datetime import datetime
import time

from app.api.models import TaskRequest, TaskResponse, SystemStatus, AgentStatus, MemoryQuery, MemoryResponse
from app.auth.middleware import require_operator, AuthUser
from app.graph.workflow import WorkflowManager
from app.memory.manager import MemoryManager
from app.graph.state import AgentState

logger = logging.getLogger(__name__)
router = APIRouter()

# Initialize managers (will be set by main.py)
memory_manager = None
workflow_manager = None
start_time = time.time()

def init_managers(mem_mgr: MemoryManager, wf_mgr: WorkflowManager):
    """Initialize managers"""
    global memory_manager, workflow_manager
    memory_manager = mem_mgr
    workflow_manager = wf_mgr

@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "memory_available": memory_manager is not None,
        "workflow_available": workflow_manager is not None
    }

@router.get("/system/status", response_model=SystemStatus)
async def system_status():
    """Get system status"""
    try:
        # Get workflow stats
        workflow_stats = workflow_manager.get_workflow_stats() if workflow_manager else {}

        # Get memory stats
        memory_stats = memory_manager.get_stats() if memory_manager else {"status": "unavailable"}

        # Build agent status
        agent_statuses = {}
        if workflow_manager:
            for name, agent_status in workflow_stats.get("agents_status", {}).items():
                agent_statuses[name] = AgentStatus(**agent_status)

        return SystemStatus(
            status="operational",
            version="1.0.0",
            memory=memory_stats,
            agents=agent_statuses,
            uptime=time.time() - start_time,
            timestamp=datetime.utcnow()
        )
    except Exception as e:
        logger.error(f"Error getting system status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/agents/execute", response_model=TaskResponse)
async def execute_task(
    request: TaskRequest,
    user: Annotated[AuthUser, Depends(require_operator)],
):
    """Execute agent task immediately (requires operator auth)"""
    try:
        if not workflow_manager:
            raise HTTPException(status_code=503, detail="Workflow manager not initialized")

        # Generate task ID
        task_id = str(uuid.uuid4())

        logger.info(f"Executing task {task_id} with agent {request.agent_type}")

        # Create initial state
        initial_state = AgentState(
            task_id=task_id,
            agent_type=request.agent_type,
            task=request.task,
            user_id=request.user_id or "anonymous",
            current_agent="",
            status="pending",
            context=request.context or {},
            results=[],
            messages=[{"role": "user", "content": request.task}],
            input_tokens=0,
            output_tokens=0,
            tools_used=[],
            llm_route="openai:gpt-4o-mini",
            memory_keys=[],
            next=""
        )

        # Execute workflow
        final_state = await workflow_manager.execute_workflow(initial_state)

        # Calculate total tokens
        total_tokens = {
            "input": final_state["input_tokens"],
            "output": final_state["output_tokens"],
            "total": final_state["input_tokens"] + final_state["output_tokens"]
        }

        return TaskResponse(
            task_id=task_id,
            status=final_state["status"],
            message="Task completed successfully",
            result=final_state.get("results", []),
            tokens=total_tokens
        )

    except Exception as e:
        logger.error(f"Error executing task: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/agents/execute/stream")
async def execute_task_stream(
    request: TaskRequest,
    user: Annotated[AuthUser, Depends(require_operator)],
):
    """Execute task with streaming response (requires operator auth)"""

    async def generate():
        try:
            task_id = str(uuid.uuid4())

            # Send start event
            yield f"data: {json.dumps({'type': 'start', 'task_id': task_id, 'agent': request.agent_type})}\n\n"
            await asyncio.sleep(0.1)

            # Send processing event
            yield f"data: {json.dumps({'type': 'processing', 'task_id': task_id, 'message': 'Initializing agent...'})}\n\n"
            await asyncio.sleep(0.1)

            # Create initial state
            initial_state = AgentState(
                task_id=task_id,
                agent_type=request.agent_type,
                task=request.task,
                user_id=request.user_id or "anonymous",
                current_agent="",
                status="pending",
                context=request.context or {},
                results=[],
                messages=[{"role": "user", "content": request.task}],
                input_tokens=0,
                output_tokens=0,
                tools_used=[],
                llm_route="openai:gpt-4o-mini",
                memory_keys=[],
                next=""
            )

            # Execute workflow
            yield f"data: {json.dumps({'type': 'executing', 'task_id': task_id, 'message': 'Executing workflow...'})}\n\n"

            final_state = await workflow_manager.execute_workflow(initial_state)

            # Send results incrementally
            for i, result in enumerate(final_state.get("results", [])):
                yield f"data: {json.dumps({'type': 'result', 'task_id': task_id, 'index': i, 'result': result})}\n\n"
                await asyncio.sleep(0.1)

            # Send completion event
            total_tokens = {
                "input": final_state["input_tokens"],
                "output": final_state["output_tokens"],
                "total": final_state["input_tokens"] + final_state["output_tokens"]
            }

            yield f"data: {json.dumps({'type': 'complete', 'task_id': task_id, 'status': final_state['status'], 'tokens': total_tokens})}\n\n"

        except Exception as e:
            logger.error(f"Streaming error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")

@router.post("/memory/query", response_model=MemoryResponse)
async def query_memory(
    query: MemoryQuery,
    user: Annotated[AuthUser, Depends(require_operator)],
):
    """Query memory (requires operator auth - reads cross-user memory)"""
    try:
        if not memory_manager:
            raise HTTPException(status_code=503, detail="Memory manager not initialized")

        memories = await memory_manager.retrieve(
            user_id=query.user_id,
            query=query.query,
            agent_id=query.agent_id,
            limit=query.limit
        )

        return MemoryResponse(
            memories=memories,
            count=len(memories)
        )

    except Exception as e:
        logger.error(f"Error querying memory: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/memory/user/{user_id}")
async def get_user_memories(
    user_id: str,
    user: Annotated[AuthUser, Depends(require_operator)],
    agent_id: str = None,
):
    """Get all memories for user (requires operator auth - reads cross-user memory)"""
    try:
        if not memory_manager:
            raise HTTPException(status_code=503, detail="Memory manager not initialized")

        memories = await memory_manager.get_all(
            user_id=user_id,
            agent_id=agent_id
        )

        return {
            "user_id": user_id,
            "agent_id": agent_id,
            "memories": memories,
            "count": len(memories)
        }

    except Exception as e:
        logger.error(f"Error getting user memories: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/memory/{memory_id}")
async def delete_memory(
    memory_id: str,
    user: Annotated[AuthUser, Depends(require_operator)],
):
    """Delete specific memory (requires operator auth - destructive)"""
    try:
        if not memory_manager:
            raise HTTPException(status_code=503, detail="Memory manager not initialized")

        success = await memory_manager.delete(memory_id)

        if not success:
            raise HTTPException(status_code=404, detail="Memory not found")

        return {"message": "Memory deleted successfully", "memory_id": memory_id}

    except Exception as e:
        logger.error(f"Error deleting memory: {e}")
        raise HTTPException(status_code=500, detail=str(e))
