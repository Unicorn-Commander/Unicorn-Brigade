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
from app.llm.gemma_sanitize import strip_channel_artifacts

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
    # Per-call model override: if set, replaces the agent's configured model.
    # Lets a UI surface (Crisis Ops Drafts wizard) pick best/cheap/local per call
    # without forking an agent definition per quality tier.
    model_override: Optional[str] = None
    # Per-call correlation id. Forwarded to chat_with_agent's mission_id so a
    # downstream subscriber to /api/v1/orchestration/events?mission_id=X
    # receives only events from THIS chat call (and any nested delegations).
    mission_id: Optional[str] = None
    # Per-case scope. When set, memory groups become {user}__{case}__{agent}
    # so memories don't bleed across cases. Forwarded through ChatRequest +
    # delegate_to_agent's downstream calls.
    case_id: Optional[str] = None


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




# ---- Introspection helpers (Option B: dual-layer tool handling) ----
def _server_tool_names():
    """Canonical set of Brigade-owned tool names (from the tool registry)."""
    try:
        from app.llm.tool_resolver import TOOL_REGISTRY
        return set(TOOL_REGISTRY.keys())
    except Exception:
        return set()

def _agent_server_tools_for(agent: Dict[str, Any]):
    """The subset of server tools THIS agent has configured to use."""
    from app.llm.tool_resolver import get_tools_for_agent
    return get_tools_for_agent(agent) or []


@router.get("/models")
async def list_models(
    session: AsyncSession = Depends(get_session),
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
):
    """OpenAI-compatible model listing. Each Brigade agent appears as a model."""
    # Accept admin key OR user API key (Bearer or X-API-Key).
    from app.auth.middleware import validate_api_key
    from app.auth.roles import can_user_access_agent, derive_user_tier, UserRole as _UserRole
    provided = x_api_key
    if not provided and authorization and authorization.startswith("Bearer "):
        provided = authorization[len("Bearer "):]
    if not provided:
        raise HTTPException(status_code=401, detail="Invalid API key")
    auth_user = await validate_api_key(provided, session)
    if not auth_user:
        raise HTTPException(status_code=401, detail="Invalid API key")
    # BR-1.4: validate_api_key authenticates but does NOT bind the org RLS GUC.
    # Without this, list_all() under the prod app role returns only global/shared
    # agents — a tenant's own agents would vanish from their model list. Bind the
    # caller's org so they see global + their org's agents.
    from app.auth.middleware import _bind_org_context
    await _bind_org_context(auth_user, session)

    repo = AgentRepository(session)
    agents = await repo.list_all()

    # Filter by per-agent access_policy. Admins see everything.
    if auth_user.role != _UserRole.ADMIN:
        _email = (getattr(auth_user, "email", "") or "") or ""
        _tier = derive_user_tier(_email, auth_user.role)
        agents = [
            a for a in agents
            if can_user_access_agent(
                user_email=_email,
                user_role=auth_user.role,
                user_tier=_tier,
                access_policy=a.get("accessPolicy"),
            )
        ]

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
    # BR-1.4: bind the org RLS GUC BEFORE any org-scoped access. validate_api_key
    # authenticates but doesn't bind org; without this the agent lookup below sees
    # only global agents and, worse, chat_with_agent's conversation/message INSERTs
    # (org_id default = current_org_id() = NULL under an empty GUC) are rejected by
    # FORCE RLS in prod. One bind point covers every downstream path (dual-layer,
    # passthrough, enhanced, streaming) since they all share this session.
    from app.auth.middleware import _bind_org_context
    await _bind_org_context(auth_user, session)
    # ---- Tool-mode routing ----
    # (a) client sends tools AND agent has its own server tools  -> dual-layer
    # (b) client sends tools AND agent has no server tools       -> passthrough
    # (c) no client tools                                        -> enhanced mode (full Brigade loop)
    if request.tools:
        from app.db.repositories import AgentRepository as _AR
        _repo = _AR(session)
        _agent = await _repo.get(request.model)
        if _agent and _agent_server_tools_for(_agent):
            return await _dual_layer_chat(
                request=request,
                session=session,
                auth_user=auth_user,
                agent=_agent,
            )
        return await _passthrough_chat(
            request=request,
            session=session,
            auth_user=auth_user,
        )
    # ---- End tool-mode routing ----



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
        model=request.model_override,
        mission_id=request.mission_id,
        case_id=request.case_id,
    )

    # Streaming path (enhanced mode only, no client tools)
    if request.stream:
        return await _enhanced_stream_chat(
            request=request,
            session=session,
            auth_user=auth_user,
            agent_id=agent_id,
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

    # Append a compact tool-call trace footer so chat UIs show what the agent
    # actually did (delegate_to_agent, web_search, memory ops, etc.). Rendered
    # as a collapsed <details> block — LibreChat and most markdown-capable
    # clients show it; plain-text clients see it as a normal section.
    tool_calls = brigade_resp.get("toolCalls") if isinstance(brigade_resp, dict) else None
    if tool_calls:
        lines = ["", "<details><summary>🔧 Tools used (" + str(len(tool_calls)) + ")</summary>", ""]
        for tc in tool_calls:
            name = tc.get("name", "?")
            args = tc.get("arguments") or {}
            try:
                import json as _json
                args_str = _json.dumps(args, separators=(",", ":"))
                if len(args_str) > 180:
                    args_str = args_str[:180] + "…"
            except Exception:
                args_str = str(args)[:180]
            err = tc.get("error")
            status = "❌ " + err if err else "✓"
            lines.append(f"- `{name}` {status} — `{args_str}`")
        lines.append("")
        lines.append("</details>")
        content = (content or "") + "\n" + "\n".join(lines)

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

    # --- Phase 7: billing preflight + user_attrs (for paid_only policies) ---
    from app.api.agent_routes import (
        _fetch_user_attrs, _enforce_billing_or_402, _enforce_org_cap_or_402,
    )
    _user_attrs, _billing_state = await _fetch_user_attrs(auth_user)
    _enforce_billing_or_402(auth_user, _billing_state)
    await _enforce_org_cap_or_402(auth_user)  # BR-3.6 per-org cap

    # --- Per-agent RBAC policy (with audit) ---
    from app.auth.roles import evaluate_agent_access, derive_user_tier
    _email = (getattr(auth_user, "email", "") or "") or ""
    _tier = derive_user_tier(_email, auth_user.role)
    _allowed, _reason = evaluate_agent_access(
        user_email=_email,
        user_role=auth_user.role,
        user_tier=_tier,
        access_policy=agent.get("accessPolicy"),
        user_attrs=_user_attrs,
    )
    if not _allowed:
        # Audit the denial
        try:
            from app.api.agent_routes import _log_rbac_denial as _audit_denial
            await _audit_denial(
                session, auth_user, agent_id, _reason,
                agent.get("accessPolicy"),
                request_path=f"POST /api/v1/openai/v1/chat/completions [{agent_id}]",
            )
        except Exception:
            pass
        raise HTTPException(status_code=403, detail=f"Agent '{agent_id}' is restricted")

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
            from app.api.agent_routes import _legacy_memory_alias
            recalled = await _mm.retrieve(
                user_id=effective_user_id,
                query=request.messages[-1].content if request.messages else "",
                agent_id=agent["id"],
                limit=5,
                case_id=request.case_id,
                # BR-1.1 dual-read: also surface this human's pre-cutover
                # Keycloak-sub memory (None → single canonical namespace).
                legacy_user_id=_legacy_memory_alias(auth_user, effective_user_id),
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
        for _c in (raw.get("choices") or []):
            _m = _c.get("message")
            if isinstance(_m, dict) and isinstance(_m.get("content"), str):
                _m["content"] = strip_channel_artifacts(_m["content"])
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
                        case_id=request.case_id,
                    )
                )
    except Exception as e:
        logger.warning(f"passthrough memory store dispatch failed: {e}")

    # Re-stamp model id in the response with the agent id so the client sees
    # "the-general" not "gpu1-gemma-4-26B-...".
    if "model" in raw:
        raw["model"] = agent_id

    # --- Phase 7: meter local-GPU passthrough chats to Lago ---
    try:
        from app.api.agent_routes import _meter_chat_to_lago as _meter
        _user_email = (getattr(auth_user, "email", "") or "").lower()
        _usage = raw.get("usage") or {}
        _meter_payload = {
            "model": resolved_model,
            # route_type correlates 1:1 with is_local_route's expectations
            "provider": route_type,
            "usage": _usage,
        }
        await _meter(_user_email, resolved_model, _meter_payload,
                     org_id=getattr(auth_user, "org_id", None))
    except Exception as _meter_err:
        logger.debug(f"passthrough meter skipped: {_meter_err}")

    # If the client asked for streaming, wrap the final response as SSE. The
    # passthrough path calls upstream non-streaming under the hood (so Brigade
    # can inject persona + memory + tools), but opencode/Cursor expect SSE when
    # stream=true. Emit one content chunk + stop + [DONE].
    if request.stream:
        import json as _json, time as _time, uuid as _uuid
        from fastapi.responses import StreamingResponse as _Stream
        chat_id = raw.get("id") or f"chatcmpl-brigade-{_uuid.uuid4().hex[:12]}"
        created = raw.get("created") or int(_time.time())
        model_name = raw.get("model") or request.model
        choice0 = (raw.get("choices") or [{}])[0]
        msg = choice0.get("message") or {}
        content = msg.get("content") or ""
        tool_calls = msg.get("tool_calls") or []

        def _chunk(delta, finish=None):
            return "data: " + _json.dumps({
                "id": chat_id, "object": "chat.completion.chunk",
                "created": created, "model": model_name,
                "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
            }) + "\n\n"

        async def _gen():
            yield _chunk({"role": "assistant"})
            if content:
                yield _chunk({"content": content})
            if tool_calls:
                for i, tc in enumerate(tool_calls):
                    fn = tc.get("function") or {}
                    yield _chunk({"tool_calls": [{
                        "index": i, "id": tc.get("id"),
                        "type": tc.get("type", "function"),
                        "function": {"name": fn.get("name"), "arguments": fn.get("arguments") or ""},
                    }]})
            yield _chunk({}, finish=choice0.get("finish_reason") or ("tool_calls" if tool_calls else "stop"))
            yield "data: [DONE]\n\n"

        return _Stream(_gen(), media_type="text/event-stream",
                       headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})

    return raw


async def _dual_layer_chat(
    request: "OpenAIChatRequest",
    session: AsyncSession,
    auth_user: Any,
    agent: Dict[str, Any],
):
    """Dual-layer tool handling: server tools + client tools visible to the LLM.

    Flow (idempotent over message history — stateless between HTTP calls):
      1. Build system prompt = agent persona + retrieved memory.
      2. Compute merged tool list: server tools (from agent config) + client tools.
      3. Rebuild the LLM messages list. Pull in full client history including
         any role="tool" follow-ups from prior client-executed tool calls.
      4. Call the LLM with merged tools.
      5. If LLM returns text: terminal. Store memory, return OpenAI-format reply.
      6. If LLM returns tool_calls:
           - server-owned: execute locally via tool_resolver, append tool result
             to messages, LOOP back to step 4.
           - client-owned: return a response with those tool_calls so the
             client can execute and POST back in a follow-up request.
         (If BOTH server and client calls appear in one response, execute
          server ones first in-process, then return client ones to client.)
    """
    import json as _json
    import time as _time
    import uuid as _uuid
    import asyncio as _asyncio
    from app.auth.roles import UserRole as _UserRole, evaluate_agent_access, derive_user_tier
    from app.llm.tool_resolver import get_tool_by_name
    from app.api.agent_routes import (
        _fetch_user_attrs,
        _enforce_billing_or_402,
        _enforce_org_cap_or_402,
        _log_rbac_denial as _audit_denial,
        _meter_chat_to_lago,
    )
    from fastapi.responses import StreamingResponse as _Stream

    def _dual_to_sse(raw_resp: Dict[str, Any]) -> _Stream:
        """Wrap a completed non-stream chat.completion response into OpenAI SSE chunks.

        Dual-layer runs synchronously (server tools, memory, token metering),
        so by the time we call this we already have the final content and/or
        tool_calls. Emit them as two chunks (delta + stop) + [DONE].
        """
        chat_id = raw_resp.get("id") or f"chatcmpl-brigade-{_uuid.uuid4().hex[:12]}"
        created = raw_resp.get("created") or int(_time.time())
        model_name = raw_resp.get("model") or request.model
        choice0 = (raw_resp.get("choices") or [{}])[0]
        msg = choice0.get("message") or {}
        content = msg.get("content") or ""
        tool_calls = msg.get("tool_calls") or []

        def _chunk(delta: Dict[str, Any], finish: Optional[str] = None) -> str:
            payload = {
                "id": chat_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": model_name,
                "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
            }
            return f"data: {_json.dumps(payload)}\n\n"

        async def _gen():
            # Open with a role marker (required by some SDKs).
            yield _chunk({"role": "assistant"})
            if content:
                yield _chunk({"content": content})
            if tool_calls:
                # Emit each tool_call in a delta. OpenAI format expects indexed tool_calls.
                for i, tc in enumerate(tool_calls):
                    fn = tc.get("function") or {}
                    yield _chunk({
                        "tool_calls": [{
                            "index": i,
                            "id": tc.get("id"),
                            "type": tc.get("type", "function"),
                            "function": {
                                "name": fn.get("name"),
                                "arguments": fn.get("arguments") or "",
                            },
                        }],
                    })
            finish = choice0.get("finish_reason") or ("tool_calls" if tool_calls else "stop")
            yield _chunk({}, finish=finish)
            yield "data: [DONE]\n\n"

        headers = {"Cache-Control": "no-store", "X-Accel-Buffering": "no"}
        return _Stream(_gen(), media_type="text/event-stream", headers=headers)

    # --- Phase 7: billing preflight + user_attrs ---
    _user_attrs, _billing_state = await _fetch_user_attrs(auth_user)
    _enforce_billing_or_402(auth_user, _billing_state)
    await _enforce_org_cap_or_402(auth_user)  # BR-3.6 per-org cap

    # --- Per-agent RBAC policy (with audit) ---
    _email = (getattr(auth_user, "email", "") or "") or ""
    _tier = derive_user_tier(_email, auth_user.role)
    _allowed, _reason = evaluate_agent_access(
        user_email=_email,
        user_role=auth_user.role,
        user_tier=_tier,
        access_policy=agent.get("accessPolicy"),
        user_attrs=_user_attrs,
    )
    if not _allowed:
        try:
            await _audit_denial(
                session, auth_user, agent["id"], _reason,
                agent.get("accessPolicy"),
                request_path=f"POST /api/v1/openai/v1/chat/completions [{agent['id']}] (dual-layer)",
            )
        except Exception:
            pass
        raise HTTPException(status_code=403, detail=f"Agent '{agent['id']}' is restricted")

    # --- Identity + memory isolation ---
    effective_user_id = request.user
    if auth_user and auth_user.role != _UserRole.ADMIN:
        effective_user_id = auth_user.user_id or auth_user.id
    if not effective_user_id or effective_user_id in ("admin", "dev-bypass", "anonymous"):
        effective_user_id = auth_user.user_id or auth_user.id or "anonymous"

    # --- System prompt (persona + memory) ---
    system_parts = []
    if agent.get("persona"):
        system_parts.append(agent["persona"])
    if agent.get("systemPrompt"):
        system_parts.append(agent["systemPrompt"])

    try:
        from app.main import memory_manager as _mm
    except Exception:
        _mm = None

    if _mm and effective_user_id and effective_user_id != "anonymous":
        try:
            latest_user = next(
                (m.content for m in reversed(request.messages) if m.role == "user"),
                "",
            )
            from app.api.agent_routes import _legacy_memory_alias
            recalled = await _mm.retrieve(
                user_id=effective_user_id,
                query=latest_user,
                agent_id=agent["id"],
                limit=5,
                case_id=request.case_id,
                # BR-1.1 dual-read: also surface this human's pre-cutover
                # Keycloak-sub memory (None → single canonical namespace).
                legacy_user_id=_legacy_memory_alias(auth_user, effective_user_id),
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
            logger.warning(f"dual-layer memory retrieve failed: {e}")

    system_content = "\n\n".join(system_parts) if system_parts else (
        f"You are {agent.get('displayName', agent['name'])}, a specialized AI agent."
    )

    # --- Merged tool list ---
    server_tools = _agent_server_tools_for(agent)
    server_tools_openai = [t.to_openai_format() for t in server_tools]
    server_tool_names = {t.name for t in server_tools}
    client_tools = list(request.tools or [])
    client_tool_names = set()
    for t in client_tools:
        fn = (t or {}).get("function") or {}
        if fn.get("name"):
            client_tool_names.add(fn["name"])
    merged_tools = server_tools_openai + client_tools

    # --- Build LLM messages from client history ---
    llm_messages = [{"role": "system", "content": system_content}]
    for m in request.messages:
        if m.role == "system":
            continue
        llm_messages.append({"role": m.role, "content": m.content})

    # Client may also send assistant messages with tool_calls, and role=tool
    # results. Those are preserved above because Pydantic OpenAIChatMessage
    # allows "content: str" but real tool messages use additional fields.
    # We separately accept extras via raw dict in the helper below.
    # (Future enhancement: expand OpenAIChatMessage schema for tool_calls/tool_call_id.)

    # --- LLM client + routing ---
    from app.api.agent_routes import llm_client as _llm_client
    if _llm_client is None:
        raise HTTPException(status_code=503, detail="LLM client not initialized")
    model = request.model_override or agent.get("model") or "default"
    temperature = request.temperature if request.temperature is not None else agent.get("temperature", 0.7)
    max_tokens = request.max_tokens or agent.get("maxTokens", 2000)

    target_url, resolved_model, route_type = _llm_client._resolve_local_model(model)
    if route_type == "local":
        endpoint = f"{target_url}/v1/chat/completions"
        headers = {"Content-Type": "application/json"}
    elif route_type == "direct":
        endpoint = target_url
        headers = {"Content-Type": "application/json"}
    elif route_type == "openrouter":
        import os as _os
        endpoint = f"{target_url}/chat/completions"
        headers = {"Authorization": f"Bearer {_os.getenv('OPENROUTER_API_KEY','')}", "Content-Type": "application/json"}
    else:
        endpoint = f"{target_url}/api/v1/llm/chat/completions"
        headers = {"Authorization": f"Bearer {_llm_client.service_key}", "Content-Type": "application/json"}
        if effective_user_id and effective_user_id not in ("anonymous","dev-bypass",""):
            headers["X-User-ID"] = effective_user_id

    logger.info(
        f"[dual-layer] agent={agent['id']} model={resolved_model} route={route_type} "
        f"server_tools={len(server_tool_names)} client_tools={len(client_tool_names)}"
    )

    # --- Tool loop: server calls execute locally, client calls bubble up ---
    MAX_SERVER_ITERATIONS = 6  # safety cap
    for iteration in range(MAX_SERVER_ITERATIONS + 1):
        payload = {
            "model": resolved_model,
            "messages": llm_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "tools": merged_tools,
        }
        if request.tool_choice is not None and iteration == 0:
            payload["tool_choice"] = request.tool_choice

        try:
            resp = await _llm_client.client.post(endpoint, json=payload, headers=headers)
            resp.raise_for_status()
            raw = resp.json()
        except Exception as e:
            logger.error(f"dual-layer LLM call failed (iter {iteration}): {e}")
            raise HTTPException(status_code=500, detail=f"LLM call failed: {e}")

        choices = raw.get("choices") or []
        if not choices:
            raise HTTPException(status_code=500, detail="LLM returned no choices")
        msg = choices[0].get("message") or {}
        tool_calls = msg.get("tool_calls") or []
        finish_reason = choices[0].get("finish_reason")

        if not tool_calls:
            # Terminal text response — store memory and return.
            reply = msg.get("content") or ""
            reply = strip_channel_artifacts(reply)
            if isinstance(msg, dict):
                msg["content"] = reply
            try:
                latest_user = next(
                    (m.content for m in reversed(request.messages) if m.role == "user"),
                    None,
                )
                if latest_user and reply and _mm and effective_user_id and effective_user_id != "anonymous":
                    _asyncio.create_task(
                        _mm.store(
                            user_id=effective_user_id,
                            agent_id=agent["id"],
                            messages=[
                                {"role": "user", "content": latest_user},
                                {"role": "assistant", "content": reply},
                            ],
                            metadata={"model": model, "mode": "dual-layer"},
                        )
                    )
            except Exception as e:
                logger.warning(f"dual-layer memory store dispatch failed: {e}")
            if "model" in raw:
                raw["model"] = agent["id"]
            # Phase 7: meter local-GPU calls. _meter_chat_to_lago was imported
            # at the top of this function along with _fetch_user_attrs.
            try:
                _user_email = (getattr(auth_user, "email", "") or "").lower()
                _usage = raw.get("usage") or {}
                _route_hint = raw.get("provider") or raw.get("model")
                await _meter_chat_to_lago(
                    _user_email, raw.get("model"),
                    {"model": raw.get("model"), "provider": _route_hint, "usage": _usage},
                    org_id=getattr(auth_user, "org_id", None),
                )
            except Exception as _me:
                logger.debug(f"dual-layer meter skipped: {_me}")
            if request.stream:
                return _dual_to_sse(raw)
            return raw

        # Classify tool calls
        server_calls, client_calls = [], []
        for tc in tool_calls:
            fn = (tc.get("function") or {})
            name = fn.get("name")
            if name in server_tool_names:
                server_calls.append(tc)
            else:
                client_calls.append(tc)

        if client_calls:
            # Return to client for execution. Do NOT execute server calls first
            # in this turn — that would desynchronize the LLM's tool-call plan.
            # Instead pass through what the LLM emitted so the client resends with
            # tool results, and the next iteration will see them.
            if "model" in raw:
                raw["model"] = agent["id"]
            # Phase 7: meter local-GPU calls. _meter_chat_to_lago was imported
            # at the top of this function along with _fetch_user_attrs.
            try:
                _user_email = (getattr(auth_user, "email", "") or "").lower()
                _usage = raw.get("usage") or {}
                _route_hint = raw.get("provider") or raw.get("model")
                await _meter_chat_to_lago(
                    _user_email, raw.get("model"),
                    {"model": raw.get("model"), "provider": _route_hint, "usage": _usage},
                    org_id=getattr(auth_user, "org_id", None),
                )
            except Exception as _me:
                logger.debug(f"dual-layer meter skipped: {_me}")
            if request.stream:
                return _dual_to_sse(raw)
            return raw

        # Only server calls — execute locally and loop
        llm_messages.append({
            "role": "assistant",
            "content": msg.get("content") or "",
            "tool_calls": tool_calls,
        })
        for tc in server_calls:
            call_id = tc.get("id") or _uuid.uuid4().hex
            fn = tc.get("function") or {}
            name = fn.get("name")
            args_raw = fn.get("arguments") or "{}"
            try:
                args = _json.loads(args_raw) if isinstance(args_raw, str) else args_raw
            except Exception:
                args = {}
            tool = get_tool_by_name(name)
            tool_content = ""
            try:
                if tool and tool.handler:
                    call_args = dict(args) if isinstance(args, dict) else {}
                    if getattr(tool, "needs_caller_context", False):
                        call_args["caller_user_id"] = effective_user_id
                    result = await tool.handler(**call_args) if _asyncio.iscoroutinefunction(tool.handler) else tool.handler(**call_args)
                    tool_content = _json.dumps(result) if not isinstance(result, str) else result
                else:
                    tool_content = _json.dumps({"error": f"unknown tool {name}"})
            except Exception as e:
                logger.error(f"server tool {name} failed: {e}")
                tool_content = _json.dumps({"error": str(e)})
            llm_messages.append({
                "role": "tool",
                "tool_call_id": call_id,
                "name": name,
                "content": tool_content,
            })
        # Loop to next LLM iteration
        continue

    # Safety: too many server iterations without terminal
    raise HTTPException(
        status_code=500,
        detail=f"dual-layer loop exceeded {MAX_SERVER_ITERATIONS} server iterations without terminating",
    )


async def _enhanced_stream_chat(
    request: "OpenAIChatRequest",
    session: AsyncSession,
    auth_user: Any,
    agent_id: str,
):
    """Stream a Brigade agent response as OpenAI-format SSE chunks.

    Used for chat UIs (LibreChat, custom clients) that want token-by-token
    output. Persona + memory are injected just like enhanced mode, but the
    LLM is called with stream=True and chunks are translated to the OpenAI
    Chat Completions streaming format:

        data: {"id":"...","choices":[{"delta":{"content":"hi"},"index":0}]}\n\n
        ...
        data: {"choices":[{"delta":{},"finish_reason":"stop","index":0}]}\n\n
        data: [DONE]\n\n
    """
    import json as _json
    import time as _time
    import uuid as _uuid
    import asyncio as _asyncio
    from fastapi.responses import StreamingResponse
    from app.db.repositories import AgentRepository
    from app.auth.roles import UserRole as _UserRole

    # Fetch agent
    repo = AgentRepository(session)
    agent = await repo.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")

    # --- BR-3.5: route the streaming shim through the SAME gates as the
    # non-streaming path (which it previously BYPASSED entirely): billing
    # preflight (402), per-org cap (402), and per-agent RBAC (403) — all BEFORE
    # a single token streams. Metering is applied after the stream completes,
    # below. Mirrors the passthrough/dual-layer preflight exactly. ---
    from app.api.agent_routes import (
        _fetch_user_attrs, _enforce_billing_or_402, _enforce_org_cap_or_402,
        _meter_chat_to_lago, _log_rbac_denial as _audit_denial,
    )
    from app.auth.roles import evaluate_agent_access, derive_user_tier
    _user_attrs, _billing_state = await _fetch_user_attrs(auth_user)
    _enforce_billing_or_402(auth_user, _billing_state)
    await _enforce_org_cap_or_402(auth_user)
    _rbac_email = (getattr(auth_user, "email", "") or "")
    _rbac_tier = derive_user_tier(_rbac_email, auth_user.role)
    _allowed, _reason = evaluate_agent_access(
        user_email=_rbac_email,
        user_role=auth_user.role,
        user_tier=_rbac_tier,
        access_policy=agent.get("accessPolicy"),
        user_attrs=_user_attrs,
    )
    if not _allowed:
        try:
            await _audit_denial(
                session, auth_user, agent_id, _reason, agent.get("accessPolicy"),
                request_path=f"POST /api/v1/openai/v1/chat/completions [stream {agent_id}]",
            )
        except Exception:
            pass
        raise HTTPException(status_code=403, detail=f"Agent '{agent_id}' is restricted")

    # Identity + memory isolation
    effective_user_id = request.user
    if auth_user and auth_user.role != _UserRole.ADMIN:
        effective_user_id = auth_user.user_id or auth_user.id
    if not effective_user_id or effective_user_id in ("admin", "dev-bypass", "anonymous"):
        effective_user_id = auth_user.user_id or auth_user.id or "anonymous"

    # Build system prompt with persona + memory
    system_parts = []
    if agent.get("persona"):
        system_parts.append(agent["persona"])
    if agent.get("systemPrompt"):
        system_parts.append(agent["systemPrompt"])

    try:
        from app.main import memory_manager as _mm
    except Exception:
        _mm = None

    if _mm and effective_user_id and effective_user_id != "anonymous":
        try:
            latest_user = next(
                (m.content for m in reversed(request.messages) if m.role == "user"),
                "",
            )
            from app.api.agent_routes import _legacy_memory_alias
            recalled = await _mm.retrieve(
                user_id=effective_user_id,
                query=latest_user,
                agent_id=agent["id"],
                limit=5,
                case_id=request.case_id,
                # BR-1.1 dual-read: also surface this human's pre-cutover
                # Keycloak-sub memory (None → single canonical namespace).
                legacy_user_id=_legacy_memory_alias(auth_user, effective_user_id),
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
            logger.warning(f"stream memory retrieve failed: {e}")

    system_content = "\n\n".join(system_parts) if system_parts else (
        f"You are {agent.get('displayName', agent['name'])}, a specialized AI agent."
    )

    llm_messages = [{"role": "system", "content": system_content}]
    for m in request.messages:
        if m.role == "system":
            continue
        llm_messages.append({"role": m.role, "content": m.content})

    # Resolve LLM endpoint
    from app.api.agent_routes import llm_client as _llm_client
    if _llm_client is None:
        raise HTTPException(status_code=503, detail="LLM client not initialized")
    model = agent.get("model") or "default"
    temperature = request.temperature if request.temperature is not None else agent.get("temperature", 0.7)
    max_tokens = request.max_tokens or agent.get("maxTokens", 2000)

    target_url, resolved_model, route_type = _llm_client._resolve_local_model(model)
    if route_type == "local":
        endpoint = f"{target_url}/v1/chat/completions"
        headers = {"Content-Type": "application/json"}
    elif route_type == "direct":
        endpoint = target_url
        headers = {"Content-Type": "application/json"}
    elif route_type == "openrouter":
        import os as _os
        endpoint = f"{target_url}/chat/completions"
        headers = {"Authorization": f"Bearer {_os.getenv('OPENROUTER_API_KEY','')}", "Content-Type": "application/json"}
    else:
        endpoint = f"{target_url}/api/v1/llm/chat/completions"
        headers = {"Authorization": f"Bearer {_llm_client.service_key}", "Content-Type": "application/json"}
        if effective_user_id and effective_user_id not in ("anonymous","dev-bypass",""):
            headers["X-User-ID"] = effective_user_id

    # Resolve agent's tool list. If non-empty, the LLM stream becomes a tool
    # loop: stream tokens, accumulate tool_calls, when finish_reason=tool_calls
    # execute server-side, append role=tool results, restart upstream stream.
    from app.llm.tool_resolver import get_tools_for_agent as _get_tools_for_agent
    _agent_tools = _get_tools_for_agent(agent) or []
    _agent_tool_defs = [t.to_openai_format() for t in _agent_tools]
    _agent_tools_by_name = {t.name: t for t in _agent_tools}

    payload = {
        "model": resolved_model,
        "messages": llm_messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": True,
        # BR-3.5: ask the upstream for a final usage tail so metering bills REAL
        # tokens; we fall back to a ~4-chars/token estimate if it's absent.
        "stream_options": {"include_usage": True},
    }
    if _agent_tool_defs:
        payload["tools"] = _agent_tool_defs

    chat_id = f"chatcmpl-brigade-{_uuid.uuid4().hex[:12]}"
    created = int(_time.time())
    full_text_buffer: list[str] = []  # for memory store after stream completes
    # BR-3.5 metering accumulators: real usage (from the include_usage tail) and
    # the set of server-side tools invoked across tool-loop iterations.
    stream_usage: dict = {}
    tools_invoked: list = []
    MAX_TOOL_ITERATIONS = 8

    async def _gen():
        # Strip <think>...</think> tags from streamed text. State carries
        # across tool iterations (a thinking block could span them).
        in_think = False
        carry = ""

        def _emit_content(delta_content):
            """Run delta_content through think-stripping; return SSE chunk or None."""
            nonlocal in_think, carry
            if delta_content is None:
                return None
            chunk = carry + delta_content
            carry = ""
            out = ""
            i = 0
            while i < len(chunk):
                if not in_think:
                    tag = chunk.find("<think>", i)
                    if tag == -1:
                        if "<th" in chunk[max(i, len(chunk)-7):]:
                            safe_to = max(i, len(chunk)-7)
                            out += chunk[i:safe_to]
                            carry = chunk[safe_to:]
                        else:
                            out += chunk[i:]
                        break
                    out += chunk[i:tag]
                    in_think = True
                    i = tag + len("<think>")
                else:
                    end = chunk.find("</think>", i)
                    if end == -1:
                        if "</thi" in chunk[max(i, len(chunk)-8):]:
                            carry = chunk[max(i, len(chunk)-8):]
                        break
                    in_think = False
                    i = end + len("</think>")
            if not out:
                return None
            full_text_buffer.append(out)
            return "data: " + _json.dumps({
                "id": chat_id, "object": "chat.completion.chunk", "created": created, "model": agent_id,
                "choices": [{"index": 0, "delta": {"content": out}, "finish_reason": None}],
            }) + "\n\n"

        running_messages = list(llm_messages)
        iterations = 0

        try:
            while True:
                iterations += 1
                if iterations > MAX_TOOL_ITERATIONS:
                    yield "data: " + _json.dumps({
                        "id": chat_id, "object": "chat.completion.chunk", "created": created, "model": agent_id,
                        "choices": [{"index": 0, "delta": {"content": f"\n[Tool loop hit {MAX_TOOL_ITERATIONS}-iteration cap; stopping.]"}, "finish_reason": "stop"}],
                    }) + "\n\n"
                    break

                iter_payload = {**payload, "messages": running_messages}
                tool_calls_acc = {}  # index -> {"id", "name", "arguments"}
                finish_reason = None

                async with _llm_client.client.stream("POST", endpoint, json=iter_payload, headers=headers) as resp:
                    if resp.status_code >= 400:
                        error_body = await resp.aread()
                        error_text = error_body.decode("utf-8", errors="replace")[:500]
                        yield "data: " + _json.dumps({
                            "id": chat_id, "object": "chat.completion.chunk", "created": created, "model": agent_id,
                            "choices": [{"index": 0, "delta": {"content": f"[Brigade upstream error {resp.status_code}: {error_text}]"}, "finish_reason": "stop"}],
                        }) + "\n\n"
                        yield "data: [DONE]\n\n"
                        return

                    async for line in resp.aiter_lines():
                        if not line or not line.startswith("data: "):
                            continue
                        data_str = line[6:].strip()
                        if data_str == "[DONE]":
                            break
                        try:
                            upstream = _json.loads(data_str)
                        except Exception:
                            continue
                        # BR-3.5: the include_usage tail is an empty-choices chunk
                        # carrying the real token counts — capture for metering.
                        if upstream.get("usage"):
                            stream_usage.update(upstream["usage"] or {})
                        choice = (upstream.get("choices") or [{}])[0]
                        delta = choice.get("delta") or {}

                        emitted = _emit_content(delta.get("content"))
                        if emitted:
                            yield emitted

                        for tc_frag in (delta.get("tool_calls") or []):
                            idx = tc_frag.get("index", 0)
                            slot = tool_calls_acc.setdefault(idx, {"id": None, "name": None, "arguments": ""})
                            if tc_frag.get("id"):
                                slot["id"] = tc_frag["id"]
                            fn = tc_frag.get("function") or {}
                            if fn.get("name"):
                                slot["name"] = fn["name"]
                            if fn.get("arguments"):
                                slot["arguments"] += fn["arguments"]

                        if choice.get("finish_reason"):
                            finish_reason = choice["finish_reason"]

                if finish_reason == "tool_calls" and tool_calls_acc:
                    assembled_calls = []
                    for idx in sorted(tool_calls_acc.keys()):
                        slot = tool_calls_acc[idx]
                        if not slot.get("name"):
                            continue
                        assembled_calls.append({
                            "id": slot["id"] or f"call_{_uuid.uuid4().hex[:8]}",
                            "type": "function",
                            "function": {"name": slot["name"], "arguments": slot["arguments"] or "{}"},
                        })
                    if not assembled_calls:
                        break

                    running_messages.append({
                        "role": "assistant",
                        "content": "".join(full_text_buffer) or None,
                        "tool_calls": assembled_calls,
                    })

                    # Read mission_id from ContextVar (set by chat_with_agent path)
                    _mid = None
                    try:
                        from app.llm.delegation_tools import _CURRENT_MISSION_ID as _CMI
                        _mid = _CMI.get()
                    except Exception:
                        pass

                    try:
                        from app.orchestration import emit_tool_call as _etc, emit_tool_result as _etr
                    except Exception:
                        _etc = None
                        _etr = None

                    for tc in assembled_calls:
                        fn_name = tc["function"]["name"]
                        tools_invoked.append(fn_name)  # BR-3.5 metering attribution
                        try:
                            fn_args = _json.loads(tc["function"]["arguments"] or "{}")
                        except Exception:
                            fn_args = {}
                        tool_def = _agent_tools_by_name.get(fn_name)

                        if _etc:
                            try:
                                await _etc(agent_id=agent["id"], agent_name=agent.get("displayName") or agent["name"],
                                           tool_name=fn_name, arguments=fn_args, mission_id=_mid)
                            except Exception:
                                pass

                        if tool_def and tool_def.handler:
                            try:
                                result = await tool_def.handler(**fn_args)
                                result_text = _json.dumps(result, default=str)[:8000]
                                err = None
                            except Exception as exc:
                                result_text = _json.dumps({"error": str(exc)})
                                err = str(exc)
                        else:
                            result_text = _json.dumps({"error": f"unknown tool: {fn_name}"})
                            err = "unknown tool"

                        if _etr:
                            try:
                                _result_for_event = {"error": err} if err else (
                                    _json.loads(result_text) if result_text.startswith("{") else {"text": result_text}
                                )
                                await _etr(agent_id=agent["id"], agent_name=agent.get("displayName") or agent["name"],
                                           tool_name=fn_name, result=_result_for_event, mission_id=_mid)
                            except Exception:
                                pass

                        running_messages.append({
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "name": fn_name,
                            "content": result_text,
                        })
                    continue  # restart upstream stream with appended messages

                # Natural finish — break out of the iteration loop
                break

            # Final stop chunk + DONE
            yield "data: " + _json.dumps({
                "id": chat_id, "object": "chat.completion.chunk", "created": created, "model": agent_id,
                "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
            }) + "\n\n"
            # BR-3.5: meter the streamed turn BEFORE [DONE] (the streaming shim
            # previously recorded NOTHING — no durable ledger, no Lago, so streamed
            # usage was invisible + uncapped). Prefer the real include_usage tail;
            # fall back to a ~4-chars/token estimate. Keyed on the caller's ORG and
            # routed through the SAME _meter_chat_to_lago as every other path.
            try:
                _stream_total = int(
                    stream_usage.get("total_tokens")
                    or (stream_usage.get("prompt_tokens") or 0) + (stream_usage.get("completion_tokens") or 0)
                    or 0
                )
                if _stream_total <= 0:
                    _prompt_chars = sum(len((m or {}).get("content", "") or "") for m in llm_messages)
                    _stream_total = max(1, (_prompt_chars + len("".join(full_text_buffer))) // 4)
                await _meter_chat_to_lago(
                    (getattr(auth_user, "email", "") or "").lower(),
                    model,
                    {"model": resolved_model, "provider": route_type, "usage": {"total_tokens": _stream_total}},
                    agent=agent,
                    tools_called=tools_invoked,
                    org_id=getattr(auth_user, "org_id", None),
                )
            except Exception as _meter_err:
                logger.debug(f"stream meter skipped: {_meter_err}")
            yield "data: [DONE]\n\n"

            # Background memory store of the final exchange
            full_text = strip_channel_artifacts("".join(full_text_buffer)).strip()
            latest_user_msg = next(
                (m.content for m in reversed(request.messages) if m.role == "user"),
                None,
            )
            if _mm and effective_user_id and effective_user_id != "anonymous" and latest_user_msg and full_text:
                _asyncio.create_task(
                    _mm.store(
                        user_id=effective_user_id,
                        agent_id=agent["id"],
                        messages=[
                            {"role": "user", "content": latest_user_msg},
                            {"role": "assistant", "content": full_text},
                        ],
                        metadata={"model": model, "mode": "stream"},
                        case_id=request.case_id,
                    )
                )
        except Exception as e:
            logger.error(f"stream error: {e}")
            yield "data: " + _json.dumps({
                "id": chat_id, "object": "chat.completion.chunk", "created": created, "model": agent_id,
                "choices": [{"index": 0, "delta": {"content": f"[stream error: {e}]"}, "finish_reason": "stop"}],
            }) + "\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        _gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

