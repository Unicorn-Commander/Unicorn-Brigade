"""
Agent management and chat routes.
Provides full CRUD for agents and real-time chat with function calling via Ops-Center LLM.
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Dict, List, Optional, Any, Annotated
from sqlalchemy.ext.asyncio import AsyncSession
import json
import logging
import time

from app.db.database import get_session
from app.db.repositories import AgentRepository, ToolExecutionRepository
from app.llm.ops_center_client import OpsCenterLLMClient, ToolCall, ToolResult
from app.llm.tool_resolver import get_tools_for_agent
from app.llm.mlx_provider import MLXLLMClient
from app.auth.middleware import require_api_key, require_operator, require_admin, AuthUser
from app.auth.roles import UserRole
from app.security.rate_limit import rate_limit
from app.security.request_limits import max_body_size
from app.orchestration import (
    emit_agent_started,
    emit_agent_thinking,
    emit_tool_call,
    emit_tool_result,
    emit_agent_completed,
)
from app.observability import get_tracer
from app.agents.deep_research import DeepResearchAgent, ResearchDepth
import asyncio

logger = logging.getLogger(__name__)
router = APIRouter()

# Injected during startup via init_agent_routes()
llm_client: OpsCenterLLMClient = None


def init_agent_routes(client: OpsCenterLLMClient):
    global llm_client
    llm_client = client


def _ensure_agent_access(user: AuthUser, agent_id: str) -> None:
    if not user.can_access_agent(agent_id):
        raise HTTPException(status_code=403, detail="Access to agent denied")


# ---- Pydantic Models ----

class AgentCreateRequest(BaseModel):
    name: str
    displayName: Optional[str] = None
    title: Optional[str] = None
    rank: Optional[str] = None
    avatar: Optional[str] = "🦄"
    bio: Optional[str] = None
    persona: Optional[str] = None
    systemPrompt: Optional[str] = None
    domain: Optional[str] = "general"
    subdomain: Optional[str] = None
    status: Optional[str] = "active"
    type: Optional[str] = "individual"
    agentType: Optional[str] = "analysis"
    capabilities: Optional[List[str]] = []
    model: Optional[str] = "openai/gpt-4o-mini"
    temperature: Optional[float] = 0.7
    maxTokens: Optional[int] = 2000
    tools: Optional[List[str]] = []


class AgentUpdateRequest(BaseModel):
    displayName: Optional[str] = None
    title: Optional[str] = None
    rank: Optional[str] = None
    avatar: Optional[str] = None
    bio: Optional[str] = None
    persona: Optional[str] = None
    systemPrompt: Optional[str] = None
    domain: Optional[str] = None
    subdomain: Optional[str] = None
    status: Optional[str] = None
    type: Optional[str] = None
    agentType: Optional[str] = None
    capabilities: Optional[List[str]] = None
    model: Optional[str] = None
    temperature: Optional[float] = None
    maxTokens: Optional[int] = None
    tools: Optional[List[str]] = None


class ChatRequest(BaseModel):
    message: str
    stream: Optional[bool] = False
    model: Optional[str] = None
    temperature: Optional[float] = None
    maxTokens: Optional[int] = None
    user_id: Optional[str] = "anonymous"
    history: Optional[List[Dict[str, str]]] = []
    speaker_name: Optional[str] = None


class ChatCompletionRequest(BaseModel):
    messages: List[Dict[str, str]]
    agentId: Optional[str] = None
    model: Optional[str] = None
    temperature: Optional[float] = 0.7
    maxTokens: Optional[int] = 1000


class DeepResearchRequest(BaseModel):
    """Request model for deep research"""
    topic: str
    depth: Optional[str] = "medium"  # quick, medium, thorough
    user_id: Optional[str] = "anonymous"


class DeepResearchResponse(BaseModel):
    """Response model for deep research"""
    session_id: str
    status: str
    topic: str
    depth: str
    report: Optional[str] = None
    sources: Optional[List[Dict[str, str]]] = None
    queries_executed: Optional[List[str]] = None
    result_count: Optional[int] = None
    error: Optional[str] = None


# ---- Agent CRUD (DB-backed) ----

@router.get("/agents")
async def list_agents(
    session: AsyncSession = Depends(get_session),
    user: Annotated[AuthUser, Depends(require_api_key)] = None,
):
    """List all agents."""
    repo = AgentRepository(session)
    if user and user.role != UserRole.ADMIN and user.agent_id:
        agent = await repo.get(user.agent_id)
        agents = [agent] if agent else []
    else:
        agents = await repo.list_all()
    for agent in agents:
        agent.setdefault("_count", {"messages": 0, "tasks": 0, "apiKeys": 0})
        agent.setdefault("agentTools", [])
    return {"agents": agents}


@router.get("/agents/domains")
async def list_domains(
    session: AsyncSession = Depends(get_session),
    user: Annotated[AuthUser, Depends(require_api_key)] = None,
):
    """Get domain summary with agent counts."""
    repo = AgentRepository(session)
    if user and user.role != UserRole.ADMIN and user.agent_id:
        agent = await repo.get(user.agent_id)
        if not agent:
            return {"domains": []}
        domains = [{"name": agent.get("domain", "general"), "count": 1}]
    else:
        domains = await repo.get_domains()
    return {"domains": domains}


@router.get("/agents/{agent_id}")
async def get_agent(
    agent_id: str,
    session: AsyncSession = Depends(get_session),
    user: Annotated[AuthUser, Depends(require_api_key)] = None,
):
    """Get agent detail by ID."""
    _ensure_agent_access(user, agent_id)
    repo = AgentRepository(session)
    agent = await repo.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")
    agent.setdefault("_count", {"messages": 0, "tasks": 0, "apiKeys": 0})
    agent.setdefault("agentTools", [])
    agent.setdefault("apiKeys", [])
    return agent


@router.post("/agents", status_code=201)
async def create_agent(
    request: AgentCreateRequest,
    session: AsyncSession = Depends(get_session),
    user: Annotated[AuthUser, Depends(require_operator)] = None,
):
    """Create a new agent."""
    repo = AgentRepository(session)
    data = request.model_dump(exclude_none=True)
    agent = await repo.create(data)
    return agent


@router.put("/agents/{agent_id}")
async def update_agent(
    agent_id: str,
    request: AgentUpdateRequest,
    session: AsyncSession = Depends(get_session),
    user: Annotated[AuthUser, Depends(require_admin)] = None,
):
    """Update an existing agent."""
    repo = AgentRepository(session)
    updates = request.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    agent = await repo.update(agent_id, updates)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")
    return agent


@router.delete("/agents/{agent_id}")
async def delete_agent(
    agent_id: str,
    session: AsyncSession = Depends(get_session),
    user: Annotated[AuthUser, Depends(require_admin)] = None,
):
    """Delete an agent."""
    repo = AgentRepository(session)
    success = await repo.delete(agent_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")
    return {"message": "Agent deleted", "id": agent_id}


# ---- Export / Import ----

@router.get("/agents/export/json")
async def export_agents(
    session: AsyncSession = Depends(get_session),
    user: Annotated[AuthUser, Depends(require_admin)] = None,
):
    """Export all agents as JSON array (same format as seed_agents.json)."""
    repo = AgentRepository(session)
    agents = await repo.list_all()
    return {"agents": agents, "count": len(agents)}


@router.post("/agents/import/json")
async def import_agents(
    agents: List[Dict[str, Any]],
    session: AsyncSession = Depends(get_session),
    user: Annotated[AuthUser, Depends(require_operator)] = None,
    _size: Annotated[None, max_body_size(5 * 1024 * 1024)] = None,
):
    """Import agents from JSON array. Upserts by ID."""
    repo = AgentRepository(session)
    created = 0
    updated = 0
    for agent_data in agents:
        agent_id = agent_data.get("id")
        if agent_id:
            existing = await repo.get(agent_id)
            if existing:
                await repo.update(agent_id, agent_data)
                updated += 1
                continue
        await repo.create(agent_data)
        created += 1
    return {"created": created, "updated": updated, "total": created + updated}


# ---- Chat with Function Calling ----

@router.post("/agents/{agent_id}/chat")
async def chat_with_agent(
    agent_id: str,
    request: ChatRequest,
    session: AsyncSession = Depends(get_session),
    user: Annotated[AuthUser, Depends(require_operator)] = None,
    _rl: Annotated[None, rate_limit("agent_chat", 60, 60)] = None,
    _size: Annotated[None, max_body_size(100 * 1024)] = None,
):
    """Chat with a specific agent. Supports function calling when agent has tools."""
    _ensure_agent_access(user, agent_id)
    repo = AgentRepository(session)
    agent = await repo.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")

    # Build system message from agent config
    system_parts = []
    if agent.get("persona"):
        system_parts.append(agent["persona"])
    if agent.get("systemPrompt"):
        system_parts.append(agent["systemPrompt"])
    system_content = "\n\n".join(system_parts) if system_parts else (
        f"You are {agent.get('displayName', agent['name'])}, a specialized AI agent."
    )

    # Inject speaker context when available (voice pipeline provides this)
    if request.speaker_name:
        system_content += f"\n\n[Speaker Context: You are currently speaking with {request.speaker_name}. Address them by name naturally.]"

    # Build messages
    messages = [{"role": "system", "content": system_content}]
    for msg in (request.history or []):
        messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
    messages.append({"role": "user", "content": request.message})

    # Resolve model and params
    model = request.model or agent.get("model", "claude-3.5-haiku")
    temperature = request.temperature if request.temperature is not None else agent.get("temperature", 0.7)
    max_tokens = request.maxTokens or agent.get("maxTokens", 2000)

    # Resolve agent tools
    agent_tools = get_tools_for_agent(agent)

    if request.stream:
        return StreamingResponse(
            _stream_chat(messages, model, temperature, max_tokens, agent, request.user_id, agent_tools, session),
            media_type="text/event-stream"
        )

    # Non-streaming
    try:
        tool_calls_log = []
        agent_name = agent.get("displayName", agent["name"])

        # Initialize Langfuse tracer for observability
        tracer = get_tracer(
            agent_id=agent["id"],
            session_id=None,  # Could be passed from request
            user_id=request.user_id,
        )
        tracer.start_trace(
            name=f"chat:{agent['id']}",
            input_data={"message": request.message, "model": model},
            metadata={"agent_name": agent_name, "tools": [t.name for t in agent_tools]},
            tags=["chat", agent.get("domain", "general")],
        )

        # Emit agent started event for real-time orchestration
        await emit_agent_started(
            agent_id=agent["id"],
            agent_name=agent_name,
            task=request.message[:100],
        )

        if agent_tools:
            # ---- Function calling path ----
            def on_tool_call(tc: ToolCall):
                tool_calls_log.append({
                    "id": tc.id,
                    "name": tc.name,
                    "arguments": tc.arguments,
                })
                logger.info(f"Tool call: {tc.name}({tc.arguments})")
                # Emit to orchestration event bus
                asyncio.create_task(emit_tool_call(
                    agent_id=agent["id"],
                    agent_name=agent_name,
                    tool_name=tc.name,
                    arguments=tc.arguments,
                ))

            def on_tool_result(tr: ToolResult):
                # Attach result to the matching tool call entry
                matched_entry = None
                for entry in tool_calls_log:
                    if entry["id"] == tr.tool_call_id:
                        entry["result"] = tr.result
                        entry["error"] = tr.error
                        matched_entry = entry
                        break
                logger.info(f"Tool result: {tr.name} -> {'error: ' + tr.error if tr.error else 'ok'}")
                # Log to Langfuse observability
                tracer.log_tool_call(
                    tool_name=tr.name,
                    tool_input=matched_entry.get("arguments", {}) if matched_entry else {},
                    tool_output=tr.result,
                    success=not tr.error,
                )
                # Emit to orchestration event bus
                asyncio.create_task(emit_tool_result(
                    agent_id=agent["id"],
                    agent_name=agent_name,
                    tool_name=tr.name,
                    result=tr.result if not tr.error else {"error": tr.error},
                ))

            response = await llm_client.execute_tool_loop(
                messages=messages,
                tools=agent_tools,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                user_id=request.user_id,
                on_tool_call=on_tool_call,
                on_tool_result=on_tool_result,
            )
        else:
            # ---- No tools, plain chat ----
            response = await llm_client.chat_completion(
                messages=messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                user_id=request.user_id,
            )

        content = llm_client.get_response_content(response)
        usage = response.get("usage", {})

        result = {
            "content": content,
            "model": response.get("model", model),
            "provider": response.get("provider", "ops-center"),
            "usage": {
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
            },
            "agent": {
                "id": agent["id"],
                "name": agent.get("displayName", agent["name"]),
                "avatar": agent.get("avatar", "🦄"),
            },
        }

        if tool_calls_log:
            result["toolCalls"] = tool_calls_log

            # Fire-and-forget: log tool executions to DB
            try:
                tool_repo = ToolExecutionRepository(session)
                for tc in tool_calls_log:
                    te = await tool_repo.create({
                        "agent_id": agent["id"],
                        "tool_name": tc["name"],
                        "input": tc.get("arguments"),
                    })
                    status = "failed" if tc.get("error") else "completed"
                    await tool_repo.complete(
                        str(te["id"]),
                        output=tc.get("result"),
                        duration_ms=0,
                        status=status,
                    )
            except Exception as log_err:
                logger.warning(f"Failed to log tool executions: {log_err}")

        # Log LLM generation to Langfuse
        tracer.log_generation(
            name="chat_completion",
            model=response.get("model", model),
            input_messages=messages,
            output=content,
            usage={
                "input": usage.get("prompt_tokens", 0),
                "output": usage.get("completion_tokens", 0),
            },
            metadata={"tool_calls": len(tool_calls_log)},
        )

        # Emit agent completed event
        await emit_agent_completed(
            agent_id=agent["id"],
            agent_name=agent_name,
            result=content[:200] if content else "",
        )

        # End Langfuse trace
        tracer.end_trace(
            output={"content": content[:500] if content else "", "tools_used": len(tool_calls_log)},
            status="success",
        )

        return result

    except Exception as e:
        logger.error(f"Chat error with agent {agent_id}: {e}")
        # End trace with error status
        try:
            tracer.end_trace(output={"error": str(e)}, status="error")
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=str(e))


async def _stream_chat(messages, model, temperature, max_tokens, agent, user_id, agent_tools, session):
    """SSE streaming chat generator with function calling support."""
    try:
        tool_names = [t.name for t in agent_tools] if agent_tools else []

        start_event = {
            "type": "start",
            "agent": agent.get("displayName", agent["name"]),
            "model": model,
            "tools": tool_names,
        }
        yield f"data: {json.dumps(start_event)}\n\n"

        tool_calls_log = []

        # If agent has tools, run the tool loop first (non-streaming),
        # emitting tool_call / tool_result events, then stream the final response.
        if agent_tools:
            def on_tool_call(tc: ToolCall):
                tool_calls_log.append({
                    "id": tc.id,
                    "name": tc.name,
                    "arguments": tc.arguments,
                })

            def on_tool_result(tr: ToolResult):
                for entry in tool_calls_log:
                    if entry["id"] == tr.tool_call_id:
                        entry["result"] = tr.result
                        entry["error"] = tr.error
                        break

            response = await llm_client.execute_tool_loop(
                messages=messages,
                tools=agent_tools,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                user_id=user_id,
                on_tool_call=on_tool_call,
                on_tool_result=on_tool_result,
            )

            # Emit tool events
            for tc in tool_calls_log:
                yield f"data: {json.dumps({'type': 'tool_call', 'name': tc['name'], 'arguments': tc['arguments']})}\n\n"
                result_event = {
                    "type": "tool_result",
                    "name": tc["name"],
                    "result": tc.get("result"),
                    "error": tc.get("error"),
                    "success": tc.get("error") is None,
                }
                yield f"data: {json.dumps(result_event)}\n\n"

            # Log tool executions to DB
            try:
                tool_repo = ToolExecutionRepository(session)
                for tc in tool_calls_log:
                    te = await tool_repo.create({
                        "agent_id": agent["id"],
                        "tool_name": tc["name"],
                        "input": tc.get("arguments"),
                    })
                    status = "failed" if tc.get("error") else "completed"
                    await tool_repo.complete(
                        str(te["id"]),
                        output=tc.get("result"),
                        duration_ms=0,
                        status=status,
                    )
            except Exception as log_err:
                logger.warning(f"Failed to log tool executions: {log_err}")

            # Emit final content as tokens (simulate streaming from the already-complete response)
            content = llm_client.get_response_content(response)
            # Send in chunks to keep SSE behavior consistent
            chunk_size = 20
            for i in range(0, len(content), chunk_size):
                chunk = content[i:i + chunk_size]
                yield f"data: {json.dumps({'type': 'token', 'content': chunk})}\n\n"

            yield f"data: {json.dumps({'type': 'complete', 'content': content, 'model': model, 'toolCalls': tool_calls_log})}\n\n"
            yield "data: [DONE]\n\n"

        else:
            # No tools — stream directly from LLM
            accumulated = ""
            async for chunk_data in llm_client.chat_completion_stream(
                messages=messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                user_id=user_id,
            ):
                try:
                    chunk = json.loads(chunk_data)
                    delta = chunk.get("choices", [{}])[0].get("delta", {})
                    token = delta.get("content", "")
                    if token:
                        accumulated += token
                        yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
                except (json.JSONDecodeError, IndexError, KeyError):
                    continue

            yield f"data: {json.dumps({'type': 'complete', 'content': accumulated, 'model': model})}\n\n"
            yield "data: [DONE]\n\n"

    except Exception as e:
        logger.error(f"Stream error: {e}")
        yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"


# ---- Agent Tools Management ----

class AttachToolRequest(BaseModel):
    toolId: str
    config: Optional[Dict] = {}


class UpdateToolConfigRequest(BaseModel):
    config: Dict


@router.get("/agents/{agent_id}/tools")
async def get_agent_tools(
    agent_id: str,
    session: AsyncSession = Depends(get_session),
    user: Annotated[AuthUser, Depends(require_api_key)] = None,
):
    """Get tools attached to an agent."""
    _ensure_agent_access(user, agent_id)
    repo = AgentRepository(session)
    agent = await repo.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")
    return {"tools": agent.get("agentTools", []), "toolNames": agent.get("tools", [])}


@router.post("/agents/{agent_id}/tools")
async def attach_tool(
    agent_id: str,
    request: AttachToolRequest,
    session: AsyncSession = Depends(get_session),
    user: Annotated[AuthUser, Depends(require_operator)] = None,
):
    """Attach a tool to an agent."""
    _ensure_agent_access(user, agent_id)
    repo = AgentRepository(session)
    agent = await repo.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")

    tool_entry = {
        "id": f"{agent_id}-{request.toolId}",
        "toolId": request.toolId,
        "config": request.config,
        "isEnabled": True,
    }

    tools = list(agent.get("tools", []))
    if request.toolId not in tools:
        tools.append(request.toolId)
    await repo.update(agent_id, {"tools": tools})

    return tool_entry


@router.delete("/agents/{agent_id}/tools/{tool_id}")
async def detach_tool(
    agent_id: str,
    tool_id: str,
    session: AsyncSession = Depends(get_session),
    user: Annotated[AuthUser, Depends(require_operator)] = None,
):
    """Detach a tool from an agent."""
    _ensure_agent_access(user, agent_id)
    repo = AgentRepository(session)
    agent = await repo.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")

    tools = [t for t in agent.get("tools", []) if t != tool_id]
    await repo.update(agent_id, {"tools": tools})

    return {"message": "Tool detached", "toolId": tool_id}


@router.patch("/agents/{agent_id}/tools/{tool_id}")
async def update_tool_config(
    agent_id: str,
    tool_id: str,
    request: UpdateToolConfigRequest,
    session: AsyncSession = Depends(get_session),
    user: Annotated[AuthUser, Depends(require_operator)] = None,
):
    """Update tool configuration for an agent."""
    _ensure_agent_access(user, agent_id)
    repo = AgentRepository(session)
    agent = await repo.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")

    return {"message": "Tool config updated", "toolId": tool_id, "config": request.config}


# ---- Direct Chat ----

@router.post("/chat/completions")
async def direct_chat_completion(
    request: ChatCompletionRequest,
    session: AsyncSession = Depends(get_session),
    user: Annotated[AuthUser, Depends(require_operator)] = None,
    _rl: Annotated[None, rate_limit("chat_completions", 60, 60)] = None,
    _size: Annotated[None, max_body_size(100 * 1024)] = None,
):
    """Direct chat completion. Optionally loads agent persona if agentId provided."""
    messages = list(request.messages)

    if request.agentId:
        _ensure_agent_access(user, request.agentId)
        repo = AgentRepository(session)
        agent = await repo.get(request.agentId)
        if agent:
            system_parts = []
            if agent.get("persona"):
                system_parts.append(agent["persona"])
            if agent.get("systemPrompt"):
                system_parts.append(agent["systemPrompt"])
            if system_parts:
                system_content = "\n\n".join(system_parts)
                if not messages or messages[0].get("role") != "system":
                    messages.insert(0, {"role": "system", "content": system_content})

    model = request.model or "openai/gpt-4o-mini"

    try:
        response = await llm_client.chat_completion(
            messages=messages,
            model=model,
            temperature=request.temperature,
            max_tokens=request.maxTokens,
        )

        content = llm_client.get_response_content(response)
        usage = response.get("usage", {})

        return {
            "content": content,
            "model": response.get("model", model),
            "provider": response.get("provider", "ops-center"),
            "usage": {
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
            }
        }
    except Exception as e:
        logger.error(f"Chat completion error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---- Local MLX Testing ----

class MLXChatRequest(BaseModel):
    message: str
    model: Optional[str] = "granite-3.3-2b"  # granite-3.3-2b, granite-3.3-8b
    temperature: Optional[float] = 0.7
    maxTokens: Optional[int] = 1000
    history: Optional[List[Dict[str, str]]] = []


@router.post("/agents/{agent_id}/chat/local")
async def chat_with_agent_local(
    agent_id: str,
    request: MLXChatRequest,
    session: AsyncSession = Depends(get_session),
    user: Annotated[AuthUser, Depends(require_operator)] = None,
):
    """
    Chat with agent using local MLX inference (Granite 3.3 2B/8B).

    Bypasses Ops-Center for testing and local development.
    Supports function calling with local models.
    """
    _ensure_agent_access(user, agent_id)
    repo = AgentRepository(session)
    agent = await repo.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")

    # Build system message
    system_parts = []
    if agent.get("persona"):
        system_parts.append(agent["persona"])
    if agent.get("systemPrompt"):
        system_parts.append(agent["systemPrompt"])
    system_content = "\n\n".join(system_parts) if system_parts else (
        f"You are {agent.get('displayName', agent['name'])}, a specialized AI agent."
    )

    # Build messages
    messages = [{"role": "system", "content": system_content}]
    for msg in (request.history or []):
        messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
    messages.append({"role": "user", "content": request.message})

    # Get agent tools
    agent_tools = get_tools_for_agent(agent)

    try:
        # Initialize MLX client
        mlx_client = MLXLLMClient(model_name=request.model)

        tool_calls_log = []

        if agent_tools:
            def on_tool_call(tc: ToolCall):
                tool_calls_log.append({
                    "id": tc.id,
                    "name": tc.name,
                    "arguments": tc.arguments,
                })
                logger.info(f"[MLX] Tool call: {tc.name}({tc.arguments})")

            def on_tool_result(tr: ToolResult):
                for entry in tool_calls_log:
                    if entry["id"] == tr.tool_call_id:
                        entry["result"] = tr.result
                        entry["error"] = tr.error
                        break
                logger.info(f"[MLX] Tool result: {tr.name} -> {'error: ' + tr.error if tr.error else 'ok'}")

            response = await mlx_client.execute_tool_loop(
                messages=messages,
                tools=agent_tools,
                model=request.model,
                temperature=request.temperature,
                max_tokens=request.maxTokens,
                on_tool_call=on_tool_call,
                on_tool_result=on_tool_result,
            )
        else:
            response = await mlx_client.chat_completion(
                messages=messages,
                model=request.model,
                temperature=request.temperature,
                max_tokens=request.maxTokens,
            )

        content = mlx_client.get_response_content(response)
        usage = response.get("usage", {})

        result = {
            "content": content,
            "model": response.get("model", request.model),
            "provider": "mlx-local",
            "usage": {
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
            },
            "agent": {
                "id": agent["id"],
                "name": agent.get("displayName", agent["name"]),
                "avatar": agent.get("avatar", "🦄"),
            },
        }

        if tool_calls_log:
            result["toolCalls"] = tool_calls_log

        return result

    except ImportError as e:
        raise HTTPException(
            status_code=503,
            detail=f"MLX not available on this system: {e}. Install with: pip install mlx-lm"
        )
    except Exception as e:
        logger.error(f"[MLX] Chat error with agent {agent_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/models/local")
async def list_local_models(
    user: Annotated[AuthUser, Depends(require_api_key)] = None,
):
    """List available local MLX models."""
    return {
        "models": [
            {
                "id": "granite-3.3-2b",
                "name": "IBM Granite 3.3 2B Instruct (4-bit)",
                "size": "~1.5GB",
                "description": "Fast, efficient model for quick tasks",
            },
            {
                "id": "granite-3.3-8b",
                "name": "IBM Granite 3.3 8B Instruct (4-bit)",
                "size": "~5GB",
                "description": "More capable model for complex reasoning",
            },
            {
                "id": "granite-4.0-micro",
                "name": "IBM Granite 4.0 Micro (4-bit)",
                "size": "~2GB",
                "description": "Latest Granite architecture, compact size",
            },
        ],
        "provider": "mlx",
        "platform": "Apple Silicon Mac",
    }


# ---- Text-to-SQL Agent ----

class TextToSQLRequest(BaseModel):
    """Request for natural language to SQL conversion."""
    question: str
    explain: Optional[bool] = True
    row_limit: Optional[int] = 100


class TextToSQLResponse(BaseModel):
    """Response from text-to-SQL agent."""
    question: str
    sql: str
    results: List[Dict[str, Any]]
    columns: List[str]
    row_count: int
    truncated: bool = False
    explanation: Optional[str] = None
    execution_time_ms: float = 0.0
    error: Optional[str] = None
    safety_level: str = "safe"


@router.post("/agents/sql", response_model=TextToSQLResponse)
async def text_to_sql(
    request: TextToSQLRequest,
    session: AsyncSession = Depends(get_session),
    user: Annotated[AuthUser, Depends(require_operator)] = None,
    _rl: Annotated[None, rate_limit("text_to_sql", 30, 60)] = None,
    _size: Annotated[None, max_body_size(10 * 1024)] = None,
):
    """
    Convert natural language question to SQL and execute.

    This endpoint:
    1. Analyzes the database schema
    2. Converts the question to a safe SELECT query
    3. Executes the query with timeout and row limits
    4. Returns results with optional natural language explanation

    Security:
    - Only SELECT queries allowed (no INSERT/UPDATE/DELETE)
    - SQL injection patterns blocked
    - Query timeout: 30 seconds
    - Row limit: configurable, max 10,000
    """
    from app.agents.text_to_sql import get_text_to_sql_agent

    logger.info(f"Text-to-SQL request: {request.question[:100]}...")

    try:
        # Get agent instance (uses global LLM client)
        agent = get_text_to_sql_agent(llm_client)

        # Execute the text-to-SQL pipeline
        result = await agent.execute({
            "question": request.question,
            "explain": request.explain,
            "row_limit": min(request.row_limit or 100, 10000),
            "user_id": user.user_id if user else "anonymous",
        })

        return TextToSQLResponse(
            question=result.get("question", request.question),
            sql=result.get("sql", ""),
            results=result.get("results", []),
            columns=result.get("columns", []),
            row_count=result.get("row_count", 0),
            truncated=result.get("truncated", False),
            explanation=result.get("explanation"),
            execution_time_ms=result.get("execution_time_ms", 0.0),
            error=result.get("error"),
            safety_level=result.get("safety_level", "safe"),
        )

    except Exception as e:
        logger.error(f"Text-to-SQL error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/agents/sql/schema")
async def get_database_schema(
    session: AsyncSession = Depends(get_session),
    user: Annotated[AuthUser, Depends(require_operator)] = None,
):
    """
    Get the database schema used for SQL generation.

    Returns table names, columns, types, and relationships.
    Useful for understanding what data can be queried.
    """
    from app.agents.text_to_sql import get_text_to_sql_agent

    try:
        agent = get_text_to_sql_agent(llm_client)
        schema = await agent.get_schema(force_refresh=True)
        return {"schema": schema}
    except Exception as e:
        logger.error(f"Error fetching schema: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---- Deep Research Agent ----

class DeepResearchRequest(BaseModel):
    """Request model for deep research"""
    topic: str
    depth: Optional[str] = "medium"  # quick, medium, thorough
    user_id: Optional[str] = "anonymous"


class DeepResearchResponse(BaseModel):
    """Response model for deep research"""
    session_id: str
    status: str
    topic: str
    depth: str
    report: Optional[str] = None
    sources: Optional[List[Dict[str, str]]] = None
    queries_executed: Optional[List[str]] = None
    result_count: Optional[int] = None
    error: Optional[str] = None


@router.post("/agents/research", response_model=DeepResearchResponse)
async def deep_research(
    request: DeepResearchRequest,
    session: AsyncSession = Depends(get_session),
    user: Annotated[AuthUser, Depends(require_operator)] = None,
    _rl: Annotated[None, rate_limit("deep_research", 10, 60)] = None,
    _size: Annotated[None, max_body_size(10 * 1024)] = None,
):
    """
    Execute deep research on a topic.

    Performs multi-step autonomous research:
    1. Plans multiple search queries to cover different angles
    2. Executes web searches using the web_search tool
    3. Synthesizes findings into a comprehensive report
    4. Includes proper source citations with URLs

    Depth options:
    - quick: 2-3 queries, fast synthesis (~30 seconds)
    - medium: 4-6 queries, balanced depth (~1 minute)
    - thorough: 8-12 queries, comprehensive analysis (~2-3 minutes)

    Returns:
        Research report with sources and executed queries
    """
    # Validate depth
    valid_depths = ["quick", "medium", "thorough"]
    depth = request.depth.lower() if request.depth else "medium"
    if depth not in valid_depths:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid depth. Must be one of: {', '.join(valid_depths)}"
        )

    logger.info(f"Deep research request: topic='{request.topic}', depth={depth}")

    # Emit research started event
    await emit_agent_started(
        agent_id="deep-researcher",
        agent_name="Deep Researcher",
        task=f"Researching: {request.topic[:100]}",
    )

    try:
        # Initialize the deep research agent with the shared LLM client
        research_agent = DeepResearchAgent(
            llm_client=llm_client,
            model="openai/gpt-4o",  # Use capable model for research
        )

        # Execute research
        result = await research_agent.research(
            topic=request.topic,
            depth=depth,
            user_id=request.user_id or "anonymous",
        )

        # Emit completion event
        await emit_agent_completed(
            agent_id="deep-researcher",
            agent_name="Deep Researcher",
            result=f"Research complete: {len(result.get('sources', []))} sources, {len(result.get('queries_executed', []))} queries",
        )

        return DeepResearchResponse(
            session_id=result.get("session_id", ""),
            status=result.get("status", "error"),
            topic=result.get("topic", request.topic),
            depth=result.get("depth", depth),
            report=result.get("report"),
            sources=result.get("sources"),
            queries_executed=result.get("queries_executed"),
            result_count=result.get("result_count"),
            error=result.get("error"),
        )

    except Exception as e:
        logger.error(f"Deep research error: {e}")
        await emit_agent_completed(
            agent_id="deep-researcher",
            agent_name="Deep Researcher",
            result=f"Error: {str(e)}",
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/agents/research/sessions")
async def list_research_sessions(
    user: Annotated[AuthUser, Depends(require_api_key)] = None,
):
    """List all research sessions in memory."""
    sessions = DeepResearchAgent.list_sessions()
    return {
        "sessions": sessions,
        "count": len(sessions),
    }


@router.get("/agents/research/sessions/{session_id}")
async def get_research_session(
    session_id: str,
    user: Annotated[AuthUser, Depends(require_api_key)] = None,
):
    """Get details of a specific research session."""
    session = DeepResearchAgent.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    return {
        "session_id": session.session_id,
        "topic": session.topic,
        "depth": session.depth.value,
        "status": session.status,
        "queries_planned": session.queries_planned,
        "queries_executed": session.queries_executed,
        "result_count": len(session.search_results),
        "synthesis": session.synthesis,
        "sources": session.sources,
        "created_at": session.created_at.isoformat(),
        "completed_at": session.completed_at.isoformat() if session.completed_at else None,
        "error": session.error,
    }
