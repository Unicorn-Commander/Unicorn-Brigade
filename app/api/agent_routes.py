"""
Agent management and chat routes.
Provides full CRUD for agents and real-time chat with function calling via Ops-Center LLM.
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Dict, List, Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession
import json
import logging
import time

from app.db.database import get_session
from app.db.repositories import AgentRepository, ToolExecutionRepository
from app.llm.ops_center_client import OpsCenterLLMClient, ToolCall, ToolResult
from app.llm.tool_resolver import get_tools_for_agent
from app.llm.mlx_provider import MLXLLMClient

logger = logging.getLogger(__name__)
router = APIRouter()

# Injected during startup via init_agent_routes()
llm_client: OpsCenterLLMClient = None


def init_agent_routes(client: OpsCenterLLMClient):
    global llm_client
    llm_client = client


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


class ChatCompletionRequest(BaseModel):
    messages: List[Dict[str, str]]
    agentId: Optional[str] = None
    model: Optional[str] = None
    temperature: Optional[float] = 0.7
    maxTokens: Optional[int] = 1000


# ---- Agent CRUD (DB-backed) ----

@router.get("/agents")
async def list_agents(session: AsyncSession = Depends(get_session)):
    """List all agents."""
    repo = AgentRepository(session)
    agents = await repo.list_all()
    for agent in agents:
        agent.setdefault("_count", {"messages": 0, "tasks": 0, "apiKeys": 0})
        agent.setdefault("agentTools", [])
    return {"agents": agents}


@router.get("/agents/domains")
async def list_domains(session: AsyncSession = Depends(get_session)):
    """Get domain summary with agent counts."""
    repo = AgentRepository(session)
    domains = await repo.get_domains()
    return {"domains": domains}


@router.get("/agents/{agent_id}")
async def get_agent(agent_id: str, session: AsyncSession = Depends(get_session)):
    """Get agent detail by ID."""
    repo = AgentRepository(session)
    agent = await repo.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")
    agent.setdefault("_count", {"messages": 0, "tasks": 0, "apiKeys": 0})
    agent.setdefault("agentTools", [])
    agent.setdefault("apiKeys", [])
    return agent


@router.post("/agents", status_code=201)
async def create_agent(request: AgentCreateRequest, session: AsyncSession = Depends(get_session)):
    """Create a new agent."""
    repo = AgentRepository(session)
    data = request.model_dump(exclude_none=True)
    agent = await repo.create(data)
    return agent


@router.put("/agents/{agent_id}")
async def update_agent(agent_id: str, request: AgentUpdateRequest, session: AsyncSession = Depends(get_session)):
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
async def delete_agent(agent_id: str, session: AsyncSession = Depends(get_session)):
    """Delete an agent."""
    repo = AgentRepository(session)
    success = await repo.delete(agent_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")
    return {"message": "Agent deleted", "id": agent_id}


# ---- Export / Import ----

@router.get("/agents/export/json")
async def export_agents(session: AsyncSession = Depends(get_session)):
    """Export all agents as JSON array (same format as seed_agents.json)."""
    repo = AgentRepository(session)
    agents = await repo.list_all()
    return {"agents": agents, "count": len(agents)}


@router.post("/agents/import/json")
async def import_agents(agents: List[Dict[str, Any]], session: AsyncSession = Depends(get_session)):
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
):
    """Chat with a specific agent. Supports function calling when agent has tools."""
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

    # Build messages
    messages = [{"role": "system", "content": system_content}]
    for msg in (request.history or []):
        messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
    messages.append({"role": "user", "content": request.message})

    # Resolve model and params
    model = request.model or agent.get("model", "openai/gpt-4o-mini")
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

        if agent_tools:
            # ---- Function calling path ----
            def on_tool_call(tc: ToolCall):
                tool_calls_log.append({
                    "id": tc.id,
                    "name": tc.name,
                    "arguments": tc.arguments,
                })
                logger.info(f"Tool call: {tc.name}({tc.arguments})")

            def on_tool_result(tr: ToolResult):
                # Attach result to the matching tool call entry
                for entry in tool_calls_log:
                    if entry["id"] == tr.tool_call_id:
                        entry["result"] = tr.result
                        entry["error"] = tr.error
                        break
                logger.info(f"Tool result: {tr.name} -> {'error: ' + tr.error if tr.error else 'ok'}")

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

        return result

    except Exception as e:
        logger.error(f"Chat error with agent {agent_id}: {e}")
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
async def get_agent_tools(agent_id: str, session: AsyncSession = Depends(get_session)):
    """Get tools attached to an agent."""
    repo = AgentRepository(session)
    agent = await repo.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")
    return {"tools": agent.get("agentTools", []), "toolNames": agent.get("tools", [])}


@router.post("/agents/{agent_id}/tools")
async def attach_tool(agent_id: str, request: AttachToolRequest, session: AsyncSession = Depends(get_session)):
    """Attach a tool to an agent."""
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
async def detach_tool(agent_id: str, tool_id: str, session: AsyncSession = Depends(get_session)):
    """Detach a tool from an agent."""
    repo = AgentRepository(session)
    agent = await repo.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")

    tools = [t for t in agent.get("tools", []) if t != tool_id]
    await repo.update(agent_id, {"tools": tools})

    return {"message": "Tool detached", "toolId": tool_id}


@router.patch("/agents/{agent_id}/tools/{tool_id}")
async def update_tool_config(agent_id: str, tool_id: str, request: UpdateToolConfigRequest, session: AsyncSession = Depends(get_session)):
    """Update tool configuration for an agent."""
    repo = AgentRepository(session)
    agent = await repo.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")

    return {"message": "Tool config updated", "toolId": tool_id, "config": request.config}


# ---- Direct Chat ----

@router.post("/chat/completions")
async def direct_chat_completion(request: ChatCompletionRequest, session: AsyncSession = Depends(get_session)):
    """Direct chat completion. Optionally loads agent persona if agentId provided."""
    messages = list(request.messages)

    if request.agentId:
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
):
    """
    Chat with agent using local MLX inference (Granite 3.3 2B/8B).

    Bypasses Ops-Center for testing and local development.
    Supports function calling with local models.
    """
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
async def list_local_models():
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
