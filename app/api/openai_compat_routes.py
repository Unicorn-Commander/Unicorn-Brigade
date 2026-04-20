# Brigade OpenAI-compatible adapter for opencode / any OpenAI SDK client.
#
# Usage: point the client at  https://brigade.magicunicorn.dev/api/v1/openai/v1
# and set `model` to an agent ID (e.g. "gunny", "judge-advocate").
#
# Each agent's persona + systemPrompt + tools are applied automatically.

import json
import logging
import time
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Header, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_session
from app.db.repositories import AgentRepository

logger = logging.getLogger(__name__)
router = APIRouter()


class OpenAIChatMessage(BaseModel):
    role: str
    content: str


class OpenAIChatRequest(BaseModel):
    model: str
    messages: List[OpenAIChatMessage]
    stream: Optional[bool] = False
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    user: Optional[str] = None
    # Passthrough-mode inputs (OpenCode / any OpenAI SDK that does client-side
    # tool execution). When present, the adapter runs in passthrough mode:
    # Brigade's persona + memory are injected into the system prompt, but the
    # LLM sees ONLY the client's tools. Client executes tool calls locally and
    # sends follow-up messages (role=tool) back. See /api/v1/openai/v1 docs.
    tools: Optional[List[Dict[str, Any]]] = None
    tool_choice: Optional[Any] = None
    response_format: Optional[Dict[str, Any]] = None


def _verify_admin_key(x_api_key: Optional[str], authorization: Optional[str]) -> None:
    import os
    admin_key = os.getenv("BRIGADE_ADMIN_KEY", "")
    if not admin_key:
        return  # auth disabled
    provided = x_api_key
    if not provided and authorization and authorization.startswith("Bearer "):
        provided = authorization[len("Bearer "):]
    if provided != admin_key:
        raise HTTPException(status_code=401, detail="Invalid API key")


@router.get("/models")
async def list_models(
    session: AsyncSession = Depends(get_session),
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
):
    """OpenAI-compatible model listing. Each Brigade agent appears as a model."""
    # Accept admin key OR user API key (Bearer or X-API-Key).
    from app.auth.middleware import validate_api_key
    provided = x_api_key
    if not provided and authorization and authorization.startswith("Bearer "):
        provided = authorization[len("Bearer "):]
    if not provided or not await validate_api_key(provided, session):
        raise HTTPException(status_code=401, detail="Invalid API key")
    repo = AgentRepository(session)
    agents = await repo.list_all()
    now = int(time.time())
    data = []
    for a in agents:
        data.append({
            "id": a["id"],
            "object": "model",
            "created": now,
            "owned_by": "unicorn-brigade",
            "name": a.get("displayName") or a.get("name"),
            "description": a.get("bio") or "",
        })
    return {"object": "list", "data": data}


@router.post("/chat/completions")
async def openai_chat_completions(
    request: OpenAIChatRequest,
    session: AsyncSession = Depends(get_session),
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
):
    """OpenAI-compatible chat completions. `model` = Brigade agent ID.

    Routes to the existing agent chat implementation (persona, tools, memory,
    persistence all active). Supports streaming via SSE like OpenAI.
    """
    # Resolve the actual authenticated user (admin key OR user API key).
    # Import validation lazily to avoid circular imports.
    from app.auth.middleware import validate_api_key
    import os
    provided = x_api_key
    if not provided and authorization and authorization.startswith("Bearer "):
        provided = authorization[len("Bearer "):]
    auth_user = None
    if provided:
        auth_user = await validate_api_key(provided, session)
    if auth_user is None:
        raise HTTPException(status_code=401, detail="Invalid API key")
    # ---- Passthrough-mode branch ----
    # When the client (OpenCode, custom SDK) sends its own tool definitions,
    # we keep Brigade's persona + memory layer but let the client own the tool
    # loop. LLM sees ONLY the client's tools; client executes them and sends
    # role="tool" follow-up messages in subsequent requests.
    if request.tools:
        return await _passthrough_chat(
            request=request,
            session=session,
            auth_user=auth_user,
        )
    # ---- End passthrough branch ----



    # Import lazily so we don't create circular imports at module load
    from app.api.agent_routes import (
        chat_with_agent,
        ChatRequest,
        # history is plain dict
    )
    

    agent_id = request.model
    if not agent_id:
        raise HTTPException(status_code=400, detail="`model` must be a Brigade agent ID")

    # Pull the latest user message; everything else becomes history
    if not request.messages:
        raise HTTPException(status_code=400, detail="`messages` is required")
    user_msgs = [m for m in request.messages if m.role in ("user", "assistant")]
    if not user_msgs or user_msgs[-1].role != "user":
        raise HTTPException(status_code=400, detail="last message must be role=user")

    latest = user_msgs[-1].content
    history = [{"role": m.role, "content": m.content} for m in user_msgs[:-1]]

    # user_id on the chat request is a hint only; chat_with_agent will override it
    # with auth_user's identity for non-admins (memory isolation).
    from app.auth.roles import UserRole as _UserRole
    requested_user_id = request.user or auth_user.user_id or auth_user.id or "opencode"
    brigade_req = ChatRequest(
        message=latest,
        user_id=requested_user_id,
        stream=bool(request.stream),
        temperature=request.temperature,
        maxTokens=request.max_tokens,
        history=history,
        model=None,  # let the agent's configured model win
    )

    try:
        brigade_resp = await chat_with_agent(
            agent_id=agent_id,
            request=brigade_req,
            session=session,
            user=auth_user,
            _rl=None,
            _size=None,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"OpenAI-compat call failed for agent={agent_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    if request.stream:
        # brigade returns a StreamingResponse already; just pass through
        return brigade_resp

    # Wrap Brigade's response in OpenAI format
    content = brigade_resp.get("content", "") if isinstance(brigade_resp, dict) else ""
    usage = brigade_resp.get("usage", {}) if isinstance(brigade_resp, dict) else {}
    model_used = brigade_resp.get("model", agent_id) if isinstance(brigade_resp, dict) else agent_id

    return {
        "id": f"chatcmpl-brigade-{uuid.uuid4().hex[:12]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": agent_id,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
        },
        "system_fingerprint": f"brigade-{model_used}",
    }


async def _passthrough_chat(
    request: "OpenAIChatRequest",
    session: AsyncSession,
    auth_user: Any,
):
    """Passthrough mode: persona + memory from Brigade, tools from the client.

    Flow:
      1. Load agent (for persona / systemPrompt).
      2. Retrieve relevant memories for authenticated user + this agent.
      3. Build system message = persona + systemPrompt + memories.
      4. Forward the full OpenAI chat request (with client's tools) to the
         agent's configured LLM, via ops_center_client's chat path.
      5. Return the LLM's response as-is, including any tool_calls the client
         will execute locally.
      6. If the response is a terminal text reply (no tool_calls), kick off
         an async memory store of (latest user msg -> reply).
    """
    import time
    import uuid as _uuid
    import asyncio as _asyncio

    from app.db.repositories import AgentRepository
    from app.auth.roles import UserRole as _UserRole

    agent_id = request.model
    if not agent_id:
        raise HTTPException(status_code=400, detail="`model` must be a Brigade agent ID")

    repo = AgentRepository(session)
    agent = await repo.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")

    # --- Enforce memory isolation ---
    effective_user_id = request.user
    if auth_user and auth_user.role != _UserRole.ADMIN:
        effective_user_id = auth_user.user_id or auth_user.id
    if not effective_user_id or effective_user_id in ("admin", "dev-bypass", "anonymous"):
        effective_user_id = auth_user.user_id or auth_user.id or "anonymous"

    # --- Build system prompt (persona + memories) ---
    system_parts = []
    if agent.get("persona"):
        system_parts.append(agent["persona"])
    if agent.get("systemPrompt"):
        system_parts.append(agent["systemPrompt"])

    # Memory retrieval
    try:
        from app.main import memory_manager as _mm
    except Exception:
        _mm = None
    if _mm and effective_user_id and effective_user_id != "anonymous":
        try:
            recalled = await _mm.retrieve(
                user_id=effective_user_id,
                query=request.messages[-1].content if request.messages else "",
                agent_id=agent["id"],
                limit=5,
            )
            if recalled:
                lines = []
                for m in recalled:
                    txt = m.get("memory") or m.get("text") or m.get("content") or ""
                    if txt:
                        lines.append(f"- {txt}")
                if lines:
                    system_parts.append(
                        "## Relevant context from prior conversations with this user:\n"
                        + "\n".join(lines)
                    )
        except Exception as e:
            logger.warning(f"passthrough memory retrieve failed: {e}")

    system_content = "\n\n".join(system_parts) if system_parts else (
        f"You are {agent.get('displayName', agent['name'])}, a specialized AI agent."
    )

    # --- Build the OpenAI-format messages list for the LLM ---
    llm_messages = [{"role": "system", "content": system_content}]
    # Preserve ALL client messages — including role="tool" follow-ups that
    # continue an interleaved tool loop. Also drop any client-sent system
    # message (we override with agent persona).
    for m in request.messages:
        if m.role == "system":
            continue
        llm_messages.append({"role": m.role, "content": m.content})

    # --- Forward to the LLM ---
    # Pull global llm_client from agent_routes (it is the injected OpsCenter client)
    from app.api.agent_routes import llm_client as _llm_client
    if _llm_client is None:
        raise HTTPException(status_code=503, detail="LLM client not initialized")

    model = agent.get("model") or "default"
    temperature = request.temperature if request.temperature is not None else agent.get("temperature", 0.7)
    max_tokens = request.max_tokens or agent.get("maxTokens", 2000)

    # Use the raw httpx client from ops_center to make a direct call with the
    # client-supplied tools. We bypass execute_tool_loop so the client owns
    # tool execution.
    target_url, resolved_model, route_type = _llm_client._resolve_local_model(model)
    payload = {
        "model": resolved_model,
        "messages": llm_messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "tools": request.tools,
    }
    if request.tool_choice is not None:
        payload["tool_choice"] = request.tool_choice
    if request.response_format is not None:
        payload["response_format"] = request.response_format

    # Pick endpoint + headers per route type (mirrors ops_center_client logic)
    if route_type == "local":
        endpoint = f"{target_url}/v1/chat/completions"
        headers = {"Content-Type": "application/json"}
    elif route_type == "direct":
        endpoint = target_url
        headers = {"Content-Type": "application/json"}
    elif route_type == "openrouter":
        import os as _os
        endpoint = f"{target_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {_os.getenv('OPENROUTER_API_KEY', '')}",
            "Content-Type": "application/json",
        }
    else:  # ops-center
        endpoint = f"{target_url}/api/v1/llm/chat/completions"
        headers = {
            "Authorization": f"Bearer {_llm_client.service_key}",
            "Content-Type": "application/json",
        }
        if effective_user_id and effective_user_id not in ("anonymous", "dev-bypass", ""):
            headers["X-User-ID"] = effective_user_id

    logger.info(
        f"[passthrough] agent={agent_id} model={resolved_model} route={route_type} "
        f"client_tools={len(request.tools or [])}"
    )

    try:
        resp = await _llm_client.client.post(endpoint, json=payload, headers=headers)
        resp.raise_for_status()
        raw = resp.json()
    except Exception as e:
        logger.error(f"passthrough LLM call failed: {e}")
        raise HTTPException(status_code=500, detail=f"LLM call failed: {e}")

    # --- Store memory of this exchange if terminal (no tool_calls in response) ---
    # We only store on terminal turns to avoid fragmented memory of incomplete tool loops.
    try:
        choices = raw.get("choices") or []
        first_msg = (choices[0].get("message") if choices else {}) or {}
        has_tool_calls = bool(first_msg.get("tool_calls"))
        if not has_tool_calls and _mm and effective_user_id and effective_user_id != "anonymous":
            latest_user = next(
                (m.content for m in reversed(request.messages) if m.role == "user"),
                None,
            )
            reply = first_msg.get("content") or ""
            if latest_user and reply:
                _asyncio.create_task(
                    _mm.store(
                        user_id=effective_user_id,
                        agent_id=agent["id"],
                        messages=[
                            {"role": "user", "content": latest_user},
                            {"role": "assistant", "content": reply},
                        ],
                        metadata={"model": model, "mode": "passthrough"},
                    )
                )
    except Exception as e:
        logger.warning(f"passthrough memory store dispatch failed: {e}")

    # Re-stamp model id in the response with the agent id so the client sees
    # "the-general" not "gpu1-gemma-4-26B-...".
    if "model" in raw:
        raw["model"] = agent_id
    return raw

