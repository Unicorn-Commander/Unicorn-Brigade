"""
Agent management and chat routes.
Provides full CRUD for agents and real-time chat with function calling via Ops-Center LLM.
"""

from contextlib import asynccontextmanager
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Dict, List, Optional, Any, Annotated
from sqlalchemy.ext.asyncio import AsyncSession
import json
import logging
import os
import time

from app.db.database import get_session
from app.db.repositories import AgentRepository, ToolExecutionRepository
from app.llm.ops_center_client import OpsCenterLLMClient, ToolCall, ToolResult, DEFAULT_MODEL
from app.llm.tool_resolver import get_tools_for_agent
from app.llm.mlx_provider import MLXLLMClient
from app.llm.gemma_sanitize import strip_channel_artifacts
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
from app.observability.metrics import (
    agent_chat_total,
    agent_tool_calls_total,
    agent_active,
)
from app.agents.deep_research import DeepResearchAgent, ResearchDepth
from app.integrations.lago import (
    emit_ai_api_call,
    emit_agent_work,
    estimate_local_cost,
    is_local_route,
    rag_used,
    classify_rate_tier,
)
from app.integrations.ops_center_billing import get_billing_state
import asyncio

import re as _re

def _strip_thinking(text: str) -> str:
    """Strip <think>...</think> blocks from model output.

    Handles three cases:
      1. Closed blocks: <think>...</think> -> removed entirely.
      2. Orphan opening with usable content: chat templates that prefill
         '<think>\n' but where the model produces its actual answer inside
         that block (e.g. Qwen3 nothink.jinja under llama.cpp). We strip
         just the opening tag and preserve the content so the user sees
         a real reply instead of an empty string.
      3. Truncated mid-thinking with nothing after: handled by step 2 —
         the content (still raw thinking) is preserved rather than dropped,
         which is less bad than an empty response.
    """
    if not text:
        return text
    cleaned = _re.sub(r'<think>.*?</think>\s*', '', text, flags=_re.DOTALL)
    # Strip orphan opening tag but preserve content after it
    cleaned = _re.sub(r'<think>\n?', '', cleaned)
    return cleaned.strip()


def _make_think_stripper():
    """Stateful streaming stripper for <think>...</think> blocks.

    The non-streaming path strips think blocks after the fact, but a token
    stream can't — so this state machine suppresses think content as it flows,
    holding back only the trailing text that might be an incomplete tag (so a
    tag split across tokens is still caught). Returns (feed, flush): feed(delta)
    yields the emittable, think-free text; flush() returns any safe remainder.
    """
    OPEN, CLOSE = "<think>", "</think>"
    st = {"in": False, "buf": ""}

    def _safe_len(buf, tag):
        # All of buf except a trailing run that is a proper prefix of tag and so
        # could grow into the full tag on the next token.
        for k in range(min(len(tag) - 1, len(buf)), 0, -1):
            if buf.endswith(tag[:k]):
                return len(buf) - k
        return len(buf)

    def feed(delta):
        st["buf"] += delta or ""
        out = []
        while True:
            buf = st["buf"]
            if not st["in"]:
                i = buf.find(OPEN)
                if i == -1:
                    n = _safe_len(buf, OPEN)
                    out.append(buf[:n])
                    st["buf"] = buf[n:]
                    break
                out.append(buf[:i])
                st["buf"] = buf[i + len(OPEN):]
                st["in"] = True
            else:
                i = buf.find(CLOSE)
                if i == -1:
                    # Drop the think content; keep only a possible partial close tag.
                    n = _safe_len(buf, CLOSE)
                    st["buf"] = buf[n:]
                    break
                st["buf"] = buf[i + len(CLOSE):]
                st["in"] = False
        return "".join(out)

    def flush():
        rest = "" if st["in"] else st["buf"]
        st["buf"] = ""
        return rest

    return feed, flush


logger = logging.getLogger(__name__)
router = APIRouter()

# Injected during startup via init_agent_routes()
llm_client: OpsCenterLLMClient = None
memory_manager = None

# Strong refs to fire-and-forget emit tasks so the event loop can't GC them
# mid-flight (asyncio keeps only a weak ref to a bare create_task result).
_bg_tasks: set = set()


def _spawn(coro) -> None:
    """Fire-and-forget a coroutine, holding a strong ref until it completes."""
    t = asyncio.create_task(coro)
    _bg_tasks.add(t)
    t.add_done_callback(_bg_tasks.discard)


def init_agent_routes(client: OpsCenterLLMClient, memory=None):
    global llm_client, memory_manager
    llm_client = client
    memory_manager = memory


async def _log_rbac_denial(
    session: AsyncSession,
    user: AuthUser,
    agent_id: str,
    reason: str,
    policy_snapshot,
    request_path: str = "",
) -> None:
    """Record a denial to the rbac_denials audit table. Non-fatal — never raises."""
    try:
        from sqlalchemy import text
        from app.auth.roles import derive_user_tier
        email = (getattr(user, "email", "") or "") or ""
        tier = derive_user_tier(email, user.role)
        role_val = user.role.value if hasattr(user.role, "value") else str(user.role)
        await session.execute(
            text("""
                INSERT INTO rbac_denials
                (user_id, user_email, user_role, user_tier, agent_id, reason,
                 policy_snapshot, auth_source, request_path)
                VALUES (:uid, :email, :role, :tier, :aid, :reason, :policy, :src, :path)
            """),
            {
                "uid": str(getattr(user, "user_id", "") or user.id),
                "email": email,
                "role": role_val,
                "tier": tier,
                "aid": agent_id,
                "reason": reason,
                "policy": json.dumps(policy_snapshot) if policy_snapshot is not None else None,
                "src": getattr(user, "auth_source", None),
                "path": request_path[:500],
            },
        )
        await session.commit()
    except Exception as _e:
        logger.debug(f"rbac_denials insert failed: {_e}")


async def _ensure_agent_access_audited(
    session: AsyncSession,
    user: AuthUser,
    agent_id: str,
    agent: Optional[dict],
    request_path: str = "",
    user_attrs: Optional[dict] = None,
) -> None:
    """Call _ensure_agent_access; on a 403 denial, record to rbac_denials and re-raise.

    Use this in user-facing chat/action endpoints. The raw sync helper is
    kept for lightweight pre-checks and for paths where the audit table
    isn't warranted (e.g. internal listings).
    """
    try:
        _ensure_agent_access(user, agent_id, agent, user_attrs=user_attrs)
    except HTTPException as e:
        if e.status_code == 403:
            detail = e.detail if isinstance(e.detail, dict) else {}
            reason = detail.get("reason") if isinstance(detail, dict) else None
            if not reason:
                reason = "service-key-binding" if agent is None else "policy-denied"
            policy = detail.get("policy") if isinstance(detail, dict) else None
            if policy is None and agent is not None:
                policy = agent.get("accessPolicy")
            await _log_rbac_denial(session, user, agent_id, reason, policy, request_path)
        raise


def _ensure_agent_access(
    user: AuthUser,
    agent_id: str,
    agent: Optional[dict] = None,
    user_attrs: Optional[dict] = None,
) -> None:
    """Two-layer access check:
      1) Service-key binding (existing): service keys bound to a specific
         agent only talk to that agent.
      2) Per-agent RBAC policy: ``agents.access_policy`` gates access by
         user email / tier / org / payment status. Admins bypass.

    ``user_attrs`` is passed through to ``evaluate_agent_access`` so policies
    like ``{"paid_only": true}`` can be resolved. See ``_fetch_user_attrs``.

    On denial, raises HTTPException 403. Caller is responsible for audit
    logging (see ``_log_rbac_denial``) since this helper is sync.
    """
    if not user.can_access_agent(agent_id):
        raise HTTPException(status_code=403, detail="Access to agent denied")
    if agent is not None:
        from app.auth.roles import evaluate_agent_access, derive_user_tier
        email = (getattr(user, "email", "") or "") or ""
        tier = derive_user_tier(email, user.role)
        allowed, reason = evaluate_agent_access(
            user_email=email,
            user_role=user.role,
            user_tier=tier,
            access_policy=agent.get("accessPolicy"),
            user_attrs=user_attrs,
        )
        if not allowed:
            # Attach reason + policy for the caller to audit-log after the raise
            raise HTTPException(
                status_code=403,
                detail={
                    "message": f"Agent '{agent_id}' is restricted",
                    "reason": reason,
                    "policy": agent.get("accessPolicy"),
                },
            )


# ---------------------------------------------------------------------------
# Phase 7: billing preflight + metering
# ---------------------------------------------------------------------------

async def _user_apps(user_id: Optional[str]) -> list:
    """Look up users.apps for a given user_id. Cached briefly per call."""
    if not user_id:
        return []
    try:
        from app.db.database import async_session
        from app.db.models import User as _User
        from sqlalchemy import select as _select
        async with async_session() as s:
            r = await s.execute(_select(_User).where(_User.id == user_id))
            u = r.scalar_one_or_none()
            return list(u.apps or []) if u else []
    except Exception:
        return []


async def _fetch_user_attrs(user: AuthUser) -> tuple:
    """Return ``(user_attrs, billing_state)`` for a Brigade chat caller.

    Admins short-circuit to a ``paid=True`` stub so they never 402 or get
    filtered by ``{"paid_only": true}`` policies. For everyone else we hit
    Ops-Center's ``/api/v1/billing/state`` (cached 30s) and project the
    result into the attrs dict consumed by ``evaluate_agent_access``.

    Also surfaces user.apps from the DB so accessPolicy.apps checks work.
    """
    apps = await _user_apps(getattr(user, "user_id", None) or getattr(user, "id", None)) if user else []
    if not user or user.role == UserRole.ADMIN:
        return {"paid": True, "key_name": (getattr(user, "key_name", "") or ""), "apps": apps}, {
            "paid": True,
            "credits_remaining": float("inf"),
            "subscription_tier": "admin",
        }
    # Service-delegated callers: keys minted via /api/v1/admin/user-keys are by
    # definition for B2B customers whose upstream service is the paying
    # subscriber (Crisis Ops, Ops-Center, etc.). Treat them as paid so the
    # consumer billing wall doesn't block enterprise seats. The list of trusted
    # key names is BRIGADE_TRUSTED_KEY_NAMES (comma-separated, case-insensitive).
    trusted_names = {
        n.strip().lower()
        for n in os.getenv("BRIGADE_TRUSTED_KEY_NAMES", "crisis-ops,ops-center").split(",")
        if n.strip()
    }
    key_name = (getattr(user, "key_name", "") or "").lower()
    if key_name and key_name in trusted_names:
        return {"paid": True, "key_name": key_name, "apps": apps}, {
            "paid": True,
            "credits_remaining": float("inf"),
            "subscription_tier": f"service:{key_name}",
        }
    email = (getattr(user, "email", "") or "").lower()
    user_kn = (getattr(user, "key_name", "") or "").lower()
    if not email:
        return {"paid": False, "key_name": user_kn, "apps": apps}, {
            "paid": False,
            "credits_remaining": 0.0,
            "subscription_tier": None,
        }
    state = await get_billing_state(email)
    return {"paid": bool(state.get("paid")), "key_name": user_kn, "apps": apps}, state


def _enforce_billing_or_402(user: AuthUser, billing_state: dict) -> None:
    """Raise 402 if a non-admin user has no credits and no paid subscription.

    This is the ONLY place Brigade enforces billing. If Ops-Center returned
    an "unknown" state (lookup failed), ``credits_remaining`` will be 0 and
    ``paid`` will be False — which fail-safes to "block" for non-admins.
    """
    if not user or user.role == UserRole.ADMIN:
        return
    credits = float(billing_state.get("credits_remaining") or 0)
    paid = bool(billing_state.get("paid"))
    if credits <= 0 and not paid:
        raise HTTPException(
            status_code=402,
            detail={
                "error": "payment_required",
                "message": (
                    "You are out of credits. Add credits or upgrade to a paid "
                    "plan to continue chatting."
                ),
                "credits_remaining": credits,
                "subscription_tier": billing_state.get("subscription_tier"),
                "paid": paid,
            },
        )


def _chat_outcome(tool_calls_log) -> str:
    """'partial' if any tool errored during the chat (the answer was still
    delivered, just not cleanly), else 'success'. Feeds the value event's
    outcome dimension."""
    return "partial" if any(t.get("error") for t in (tool_calls_log or [])) else "success"


async def _meter_chat_to_lago(
    user_email: Optional[str],
    model: Optional[str],
    response_dict: Optional[dict],
    agent: Optional[dict] = None,
    tools_called: Optional[list] = None,
    outcome: str = "success",
) -> None:
    """Meter a completed chat with TWO independent best-effort events:

      * ``ai_api_call`` (LLM COGS) — unchanged behavior: only local-GPU routes,
        mirrored to the credit-deduction webhook. Cloud/gateway routes are
        skipped (they meter themselves). Now also carries the value dims for
        analytics.
      * ``agent_work`` (per-agent VALUE) — emitted for EVERY chat that has a
        user + agent, on ALL routes, carrying agent/user/tools/rag/outcome.
        This is what makes usage attributable per-agent AND per-user even on
        ``uc/`` routes, and is the basis for value-based billing. It charges
        nothing until a Lago plan is configured for it.

    Never raises.
    """
    if not user_email:
        return
    response_dict = response_dict or {}
    provider = response_dict.get("provider")
    usage = response_dict.get("usage") or {}
    total_tokens = int(
        usage.get("total_tokens")
        or (usage.get("prompt_tokens") or 0) + (usage.get("completion_tokens") or 0)
        or 0
    )
    model_used = response_dict.get("model") or model
    agent = agent or {}
    agent_id = agent.get("id")
    tools_used = [t for t in (tools_called or []) if t]
    used_rag = rag_used(tools_used)
    rate_tier = classify_rate_tier(agent, used_rag)
    try:
        rate_multiplier = float(agent.get("rateMultiplier", agent.get("rate_multiplier", 1.0)) or 1.0)
    except (TypeError, ValueError):
        rate_multiplier = 1.0
    agent_name = agent.get("displayName") or agent.get("name")

    # 1) LLM COGS — unchanged conditions (local-GPU routes, tokens > 0).
    if total_tokens > 0 and is_local_route(provider, model_used):
        try:
            await emit_ai_api_call(
                user=user_email,
                model=model_used or "unknown",
                tokens=total_tokens,
                cost=estimate_local_cost(total_tokens),
                agent_id=agent_id,
                agent_name=agent_name,
                agent_domain=agent.get("domain"),
                tools_used=tools_used or None,
                used_rag=used_rag,
                rate_tier=rate_tier,
                rate_multiplier=rate_multiplier,
            )
        except Exception as e:
            logger.debug(f"Lago COGS emission failed (ignored): {e}")

    # 2) Per-agent VALUE event — every chat with a user + agent, ALL routes.
    if agent_id:
        try:
            await emit_agent_work(
                user=user_email,
                agent_id=agent_id,
                model=model_used or model,
                tokens=total_tokens,
                outcome=outcome,
                agent_name=agent_name,
                agent_domain=agent.get("domain"),
                tools_used=tools_used or None,
                used_rag=used_rag,
                rate_tier=rate_tier,
                rate_multiplier=rate_multiplier,
            )
        except Exception as e:
            logger.debug(f"Lago agent_work emission failed (ignored): {e}")


# ---- Pydantic Models ----

class AgentCreateRequest(BaseModel):
    name: str
    displayName: Optional[str] = None
    title: Optional[str] = None
    rank: Optional[str] = None
    avatar: Optional[str] = "🦄"
    avatarUrl: Optional[str] = None
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
    billingTier: Optional[str] = "standard"
    rateMultiplier: Optional[float] = 1.0
    basePricePerCall: Optional[float] = None
    # BR-1.4: when true, create a GLOBAL/shared agent (NULL org_id) visible to
    # every org. Admin-only and inserted via the owner session (the RLS-subject
    # app role cannot write a NULL-org row). Default false = a per-org agent
    # scoped to the caller's organization.
    shared: Optional[bool] = False


class AgentUpdateRequest(BaseModel):
    displayName: Optional[str] = None
    title: Optional[str] = None
    rank: Optional[str] = None
    avatar: Optional[str] = None
    avatarUrl: Optional[str] = None
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
    accessPolicy: Optional[Dict[str, Any]] = None
    billingTier: Optional[str] = None
    rateMultiplier: Optional[float] = None
    basePricePerCall: Optional[float] = None


class ChatRequest(BaseModel):
    message: str
    stream: Optional[bool] = False
    model: Optional[str] = None
    temperature: Optional[float] = None
    maxTokens: Optional[int] = None
    user_id: Optional[str] = "anonymous"
    history: Optional[List[Dict[str, str]]] = []
    speaker_name: Optional[str] = None
    # Per-case scope: when set, memory groups become {user}__{case}__{agent}
    # so the same user's memories don't bleed across cases. Crisis Ops sends
    # this on every chat; other Brigade consumers can omit and get the
    # legacy {user}__{agent} grouping.
    case_id: Optional[str] = None
    # Per-call correlation id. When set, every orchestration event emitted
    # during this chat (and any nested delegate_to_agent calls) carries this
    # value as mission_id, so a downstream subscriber can filter events that
    # belong only to this chat. If unset, chat_with_agent generates one.
    mission_id: Optional[str] = None
    # Stable room context. When the caller is a Stable chat/voice room, these
    # identify the room so room-aware tools (ToolDefinition.needs_room_context,
    # e.g. the canvas authoring tools) can act on the right room on the agent's
    # behalf. Both optional; other Brigade consumers omit them and behave
    # exactly as before.
    room_id: Optional[str] = None
    room_name: Optional[str] = None


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

async def _load_tool_catalog(session: AsyncSession) -> Dict[str, Dict[str, Any]]:
    """name -> {costTier, permissionLevel, provider, external, displayName}.

    Best-effort: if the catalog table is absent/empty (fresh DB pre-migration) we
    return {} and callers fall back to neutral defaults, so the roster never 500s
    on a missing catalog.
    """
    from sqlalchemy import text
    try:
        rows = await session.execute(text(
            "SELECT name, display_name, cost_tier, permission_level, provider, external "
            "FROM tool_catalog"
        ))
        return {
            r[0]: {
                "name": r[0],
                "displayName": r[1],
                "costTier": r[2],
                "permissionLevel": r[3],
                "provider": r[4],
                "external": r[5],
            }
            for r in rows
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"tool_catalog unavailable, serving roster without tool metadata: {exc}")
        return {}


def _enrich_agent_tools(agent: Dict[str, Any], catalog: Dict[str, Dict[str, Any]]) -> None:
    """Attach per-tool cost/permission detail + a cost rollup to an agent dict.

    Adds `toolDetails` (one entry per tool, catalog-looked-up with neutral
    fallback) and `toolCostSummary` (counts so a UI can badge an agent without
    re-deriving). Leaves the original `tools` string array untouched."""
    tools = agent.get("tools") or []
    details = []
    paid = 0
    external = 0
    max_perm = 0
    for t in tools:
        meta = catalog.get(t)
        if meta is None:
            meta = {
                "name": t,
                "displayName": None,
                "costTier": "free",
                "permissionLevel": 1,
                "provider": None,
                "external": False,
            }
        details.append(meta)
        if meta["costTier"] != "free":
            paid += 1
        if meta["external"]:
            external += 1
        if (meta["permissionLevel"] or 0) > max_perm:
            max_perm = meta["permissionLevel"] or 0
    agent["toolDetails"] = details
    agent["toolCostSummary"] = {
        "total": len(details),
        "paid": paid,
        "external": external,
        "maxPermissionLevel": max_perm,
    }


@router.get("/tool-catalog")
async def get_tool_catalog(
    session: AsyncSession = Depends(get_session),
    user: Annotated[AuthUser, Depends(require_api_key)] = None,
):
    """The tool cost/permission catalog (for UI legends + admin review)."""
    catalog = await _load_tool_catalog(session)
    return {"tools": sorted(catalog.values(), key=lambda x: x["name"])}


@router.get("/agents")
async def list_agents(
    session: AsyncSession = Depends(get_session),
    user: Annotated[AuthUser, Depends(require_api_key)] = None,
):
    """List all agents visible to the caller (per-agent access_policy enforced)."""
    repo = AgentRepository(session)
    if user and user.role != UserRole.ADMIN and user.agent_id:
        agent = await repo.get(user.agent_id)
        agents = [agent] if agent else []
    else:
        agents = await repo.list_all()

    # Apply per-agent RBAC. Admins see everything; others filtered by policy.
    if user and user.role != UserRole.ADMIN:
        from app.auth.roles import can_user_access_agent, derive_user_tier
        email = (getattr(user, "email", "") or "") or ""
        tier = derive_user_tier(email, user.role)
        agents = [
            a for a in agents
            if can_user_access_agent(
                user_email=email,
                user_role=user.role,
                user_tier=tier,
                access_policy=a.get("accessPolicy"),
            )
        ]

    catalog = await _load_tool_catalog(session)
    for agent in agents:
        agent.setdefault("_count", {"messages": 0, "tasks": 0, "apiKeys": 0})
        agent.setdefault("agentTools", [])
        _enrich_agent_tools(agent, catalog)
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


@asynccontextmanager
async def _agent_writer(agent_id: str, session: AsyncSession):
    """Async context yielding ``(agent, repo)`` for MUTATING ``agent_id`` under
    enforced RLS, or ``(None, None)`` when the agent is not visible to the caller.

    BR-1.4 (C1) tenancy — the ``agents`` RLS policy is::

        USING      (org_id IS NULL OR org_id = current_org_id())
        WITH CHECK (org_id = current_org_id())

    A shared/global agent (``org_id IS NULL`` — the 17-agent seed roster) is
    READABLE by the RLS-subject request session but NOT writable by it: any
    UPDATE that leaves ``org_id`` NULL fails ``WITH CHECK`` (NULL <>
    current_org_id()) and 500s under enforced RLS (masked only in single-role dev
    where the superuser bypasses RLS). So we READ the target via the request
    session first — RLS lets that session see ONLY a shared agent or one in the
    caller's OWN org, never another tenant's private agent, so the read itself is
    isolation-safe — then route the write:

      * ``org_id IS NULL`` (shared) → yield an OWNER/admin-session repo
        (RLS-exempt) so the mutation passes, mirroring ``create_agent``'s
        shared-creation path. Operators keep managing the shared roster at runtime.
      * ``org_id == caller`` → yield the request-session repo (``WITH CHECK``
        passes for the caller's own org).

    ``delete_agent`` uses this same routing so shared-agent DELETE is CONSISTENT
    with shared-agent UPDATE (both go through the owner session) instead of
    relying on DELETE checking only the ``USING`` clause.
    """
    repo = AgentRepository(session)
    agent = await repo.get(agent_id)
    if agent is None:
        yield None, None
        return
    if agent.get("orgId") is None:
        # Shared (NULL-org) catalog agent — route through the RLS-exempt owner
        # session. Safe: the RLS read above already proved this is a SHARED agent,
        # not another tenant's private one.
        from app.db.database import admin_session
        async with admin_session() as owner_sess:
            yield agent, AgentRepository(owner_sess)
    else:
        yield agent, repo


@router.post("/agents", status_code=201)
async def create_agent(
    request: AgentCreateRequest,
    session: AsyncSession = Depends(get_session),
    user: Annotated[AuthUser, Depends(require_operator)] = None,
):
    """Create a new agent.

    BR-1.4 tenancy: agents are org-isolated by RLS. A normal create is scoped to
    the caller's org automatically (the org_id DB default = current_org_id(), and
    the RLS WITH CHECK enforces it). Creating a GLOBAL/shared agent (NULL org_id,
    visible to every org) is ADMIN-ONLY and must run on the owner/admin session,
    because the RLS-subject app role can never satisfy WITH CHECK for a NULL row.
    """
    data = request.model_dump(exclude_none=True)
    wants_shared = bool(data.pop("shared", False))

    if wants_shared:
        # Shared (global) agent: gate to admins, then insert a NULL-org row via
        # the owner session (not subject to RLS). This is the ONLY sanctioned way
        # to add to the global roster at runtime.
        if user is None or user.role != UserRole.ADMIN:
            raise HTTPException(
                status_code=403,
                detail="Only admins can create shared (global) agents",
            )
        from app.db.database import admin_session
        data["org_id"] = None  # explicit NULL = global; overrides the org default
        async with admin_session() as owner_sess:
            agent = await AgentRepository(owner_sess).create(data)
        return agent

    # Per-org agent: leave org_id unset so the DB default (current_org_id()) tags
    # it with the caller's bound org. RLS WITH CHECK guarantees it can't land in
    # another org even if a caller tried to force one.
    data.pop("org_id", None)
    repo = AgentRepository(session)
    agent = await repo.create(data)
    return agent


@router.put("/agents/{agent_id}")
async def update_agent(
    agent_id: str,
    request: AgentUpdateRequest,
    session: AsyncSession = Depends(get_session),
    user: Annotated[AuthUser, Depends(require_admin)] = None,
):
    """Update an existing agent.

    Uses ``exclude_unset`` so callers can explicitly set a nullable field
    back to None (e.g. clearing accessPolicy). Fields not sent stay untouched.

    C1 tenancy: a shared (NULL-org) agent is mutated via the RLS-exempt owner
    session (see ``_agent_writer``); a per-org agent on the request session.
    """
    updates = request.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    async with _agent_writer(agent_id, session) as (agent, repo):
        if agent is None:
            raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")
        updated = await repo.update(agent_id, updates)
        if not updated:
            raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")
        return updated


@router.delete("/agents/{agent_id}")
async def delete_agent(
    agent_id: str,
    session: AsyncSession = Depends(get_session),
    user: Annotated[AuthUser, Depends(require_admin)] = None,
):
    """Delete an agent.

    C1 tenancy: a shared (NULL-org) agent's DELETE is routed through the owner
    session too — CONSISTENT with shared-agent update — so it never depends on the
    DELETE-only ``USING`` clause. A per-org agent deletes on the request session
    (``USING`` scopes it to the caller's org).
    """
    async with _agent_writer(agent_id, session) as (agent, repo):
        if agent is None:
            raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")
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
    """Import agents from JSON array. Upserts by ID.

    C1 tenancy: an existing SHARED (NULL-org) agent (e.g. re-importing the seed
    roster) is updated via the RLS-exempt owner session (``_agent_writer``); a
    per-org agent updates on the request session. New agents are created on the
    request session so the DB default (current_org_id()) tags them to the caller's
    org and RLS WITH CHECK passes.
    """
    repo = AgentRepository(session)
    created = 0
    updated = 0
    for agent_data in agents:
        agent_id = agent_data.get("id")
        did_update = False
        if agent_id:
            async with _agent_writer(agent_id, session) as (existing, w_repo):
                if existing:
                    await w_repo.update(agent_id, agent_data)
                    updated += 1
                    did_update = True
            if did_update:
                continue
        await repo.create(agent_data)
        created += 1
    return {"created": created, "updated": updated, "total": created + updated}


# ---- Chat with Function Calling ----

def _legacy_memory_alias(user, effective_user_id):
    """The pre-BR-1.1 memory key (a Keycloak ``sub``) to DUAL-READ for this chat,
    or None.

    BR-1.1 made ``user_id`` the canonical local users.id, but a user's older
    agent memory was stored in Graphiti under their raw sub. Passing that sub as
    ``legacy_user_id`` to memory retrieval re-includes the ``{sub}__{agent}``
    namespace so a cutover SSO user doesn't silently lose everything from before.

    We alias ONLY when the memory being queried belongs to the authenticated
    principal THEMSELVES — i.e. ``effective_user_id`` is their own canonical id —
    and their sub actually differs from it. That keeps an admin who delegates
    with an explicit ``user_id`` from ever bleeding their own sub onto another
    user's memory (we don't have the delegated target's sub here; that remains a
    documented residual). Retrieval-only: writes are always canonical.
    """
    if user is None:
        return None
    kc = getattr(user, "keycloak_id", None)
    if not kc:
        return None
    own = getattr(user, "user_id", None) or getattr(user, "id", None)
    if own and str(effective_user_id) == str(own) and str(kc) != str(own):
        return kc
    return None


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

    # Phase 7: fetch billing state once per request, 402 out-of-credits non-admins,
    # and carry the paid signal into per-agent RBAC.
    user_attrs, billing_state = await _fetch_user_attrs(user)
    _enforce_billing_or_402(user, billing_state)

    # Memory isolation: non-admin users cannot spoof user_id. Force it to their
    # authenticated identity. Admins may pass user_id explicitly (for delegation,
    # batch ops, admin tooling, etc.).
    from app.auth.roles import UserRole as _UserRole
    if user and user.role != _UserRole.ADMIN:
        authenticated_id = user.user_id or user.id
        if authenticated_id and authenticated_id not in ("admin", "dev-bypass", "anonymous"):
            request.user_id = authenticated_id

    repo = AgentRepository(session)
    agent = await repo.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")

    # Per-agent RBAC (with audit logging on denial)
    await _ensure_agent_access_audited(
        session, user, agent_id, agent,
        request_path=f"POST /api/v1/agents/{agent_id}/chat",
        user_attrs=user_attrs,
    )

    # Build system message from agent config
    system_parts = []
    if agent.get("persona"):
        system_parts.append(agent["persona"])
    if agent.get("systemPrompt"):
        system_parts.append(agent["systemPrompt"])
    # Inject relevant memories for this user+agent pair (Phase 2)
    if memory_manager and request.user_id and request.user_id != "anonymous":
        try:
            # BR-1.1 dual-read: also surface memory this human accreted under
            # their pre-cutover Keycloak sub (None → single canonical namespace).
            legacy_uid = _legacy_memory_alias(user, request.user_id)
            recalled = await memory_manager.retrieve(
                user_id=request.user_id,
                query=request.message,
                agent_id=agent["id"],
                limit=5,
                legacy_user_id=legacy_uid,
            )
            if recalled:
                mem_lines = []
                for m in recalled:
                    text = m.get("memory") or m.get("text") or m.get("content") or ""
                    if text:
                        mem_lines.append(f"- {text}")
                if mem_lines:
                    system_parts.append(
                        "## Relevant context from prior conversations with this user:\n" + "\n".join(mem_lines)
                    )
        except Exception as mem_err:
            logger.warning(f"Memory retrieval failed: {mem_err}")

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
    model = request.model or agent.get("model") or DEFAULT_MODEL
    temperature = request.temperature if request.temperature is not None else agent.get("temperature", 0.7)
    max_tokens = request.maxTokens or agent.get("maxTokens", 2000)

    # Resolve agent tools
    agent_tools = get_tools_for_agent(agent)

    # User email for Phase 7 Lago metering; safe for admin/anonymous (empty string)
    user_email_for_metering = (getattr(user, "email", "") or "").lower()

    if request.stream:
        return StreamingResponse(
            _stream_chat(
                messages, model, temperature, max_tokens, agent,
                request.user_id, agent_tools, session,
                user_email=user_email_for_metering,
            ),
            media_type="text/event-stream"
        )

    # Non-streaming
    _metric_agent = agent.get("id", "unknown")
    try:
        agent_active.labels(agent=_metric_agent).inc()
    except Exception:
        pass
    try:
        tool_calls_log = []
        agent_name = agent.get("displayName", agent["name"])

        # Per-call correlation: tag every orchestration event emitted during
        # this chat with the same mission_id so a downstream subscriber can
        # filter events that belong only to this run. Generated if not given.
        import uuid as _uuid_mod
        mission_id = request.mission_id or f"chat-{_uuid_mod.uuid4().hex[:12]}"
        # Stash on a context var so delegate_to_agent_handler (called from a
        # tool handler) can read it without an explicit parameter chain.
        from app.llm.delegation_tools import (
            _CURRENT_MISSION_ID, _CURRENT_CASE_ID,
            _CURRENT_AGENT_ID, _CURRENT_AGENT_NAME,
        )
        _mission_token = _CURRENT_MISSION_ID.set(mission_id)
        _case_token = _CURRENT_CASE_ID.set(request.case_id) if request.case_id else None
        # Identify the running agent so a delegate_to_agent call from inside its
        # tool loop can emit a source->target edge for the live org chart.
        _CURRENT_AGENT_ID.set(agent["id"])
        _CURRENT_AGENT_NAME.set(agent_name)
        # Stamp correlation ids onto every log record for this request.
        from app.observability import mission_id_ctx, agent_id_ctx
        mission_id_ctx.set(mission_id)
        agent_id_ctx.set(agent["id"])

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
            mission_id=mission_id,
        )

        if agent_tools:
            # ---- Function calling path ----
            def on_tool_call(tc: ToolCall):
                tool_calls_log.append({
                    "id": tc.id,
                    "name": tc.name,
                    "arguments": tc.arguments,
                })
                try:
                    agent_tool_calls_total.labels(
                        agent=_metric_agent, tool=tc.name
                    ).inc()
                except Exception:
                    pass
                logger.info(f"Tool call: {tc.name}({tc.arguments})")
                # Emit to orchestration event bus
                _spawn(emit_tool_call(
                    agent_id=agent["id"],
                    agent_name=agent_name,
                    tool_name=tc.name,
                    arguments=tc.arguments,
                    mission_id=mission_id,
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
                _spawn(emit_tool_result(
                    agent_id=agent["id"],
                    agent_name=agent_name,
                    tool_name=tr.name,
                    result=tr.result if not tr.error else {"error": tr.error},
                    mission_id=mission_id,
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
                # Room context for room-aware tools (needs_room_context).
                # agent_id is the running agent's id, injected as
                # caller_agent_id alongside caller_room_id/caller_room_name.
                agent_id=agent["id"],
                room_id=request.room_id,
                room_name=request.room_name,
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

        content = strip_channel_artifacts(_strip_thinking(llm_client.get_response_content(response)))
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
            mission_id=mission_id,
        )

        # End Langfuse trace
        tracer.end_trace(
            output={"content": content[:500] if content else "", "tools_used": len(tool_calls_log)},
            status="success",
        )

        # Auto-persist conversation (Phase 2: agents remember)
        try:
            from sqlalchemy import text as _sa_text
            from app.db.repositories import ConversationRepository
            conv_repo = ConversationRepository(session)
            user_id = request.user_id or "anonymous"

            # Find or create conversation for this user+agent pair
            existing = await session.execute(
                _sa_text(
                    "SELECT id FROM conversations WHERE agent_id = :aid AND user_id = :uid ORDER BY updated_at DESC LIMIT 1"
                ),
                {"aid": agent["id"], "uid": user_id}
            )
            row = existing.first()

            if row:
                conv_id = str(row[0])
            else:
                conv = await conv_repo.create({
                    "agent_id": agent["id"],
                    "user_id": user_id,
                    "title": request.message[:100],
                    "model": model,
                })
                conv_id = str(conv["id"])

            total_tokens = (usage.get("prompt_tokens", 0) or 0) + (usage.get("completion_tokens", 0) or 0)

            # Save user message
            await conv_repo.add_message(conv_id, {
                "role": "user",
                "content": request.message,
            })
            # Save assistant response
            await conv_repo.add_message(conv_id, {
                "role": "assistant",
                "content": content or "",
                "model": model,
                "tokens_used": total_tokens,
                "tool_calls": tool_calls_log if tool_calls_log else None,
            })
            await session.commit()
        except Exception as persist_err:
            logger.warning(f"Failed to persist conversation: {persist_err}")

        # Store exchange in long-term memory (Phase 2)
        if memory_manager and request.user_id and request.user_id != "anonymous" and content:
            try:
                await memory_manager.store(
                    user_id=request.user_id,
                    agent_id=agent["id"],
                    messages=[
                        {"role": "user", "content": request.message},
                        {"role": "assistant", "content": content},
                    ],
                    metadata={"model": model, "agent_name": agent_name},
                )
            except Exception as mem_err:
                logger.warning(f"Memory store failed: {mem_err}")

        # Phase 7: meter local-GPU LLM cost to Lago (cloud/gateway routes meter
        # themselves) + emit the per-agent value event (all routes).
        await _meter_chat_to_lago(
            user_email_for_metering, model, result,
            agent=agent,
            tools_called=[t.get("name") for t in (tool_calls_log or [])],
            outcome=_chat_outcome(tool_calls_log),
        )

        try:
            agent_chat_total.labels(agent=_metric_agent, outcome="ok").inc()
        except Exception:
            pass
        return result

    except Exception as e:
        logger.error(f"Chat error with agent {agent_id}: {e}")
        try:
            agent_chat_total.labels(agent=_metric_agent, outcome="error").inc()
        except Exception:
            pass
        # End trace with error status
        try:
            tracer.end_trace(output={"error": str(e)}, status="error")
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        try:
            agent_active.labels(agent=_metric_agent).dec()
        except Exception:
            pass


async def _stream_chat(
    messages, model, temperature, max_tokens, agent, user_id, agent_tools, session,
    user_email: Optional[str] = None,
):
    """SSE streaming chat generator with function calling support."""
    from app.llm.delegation_tools import _CURRENT_AGENT_ID, _CURRENT_AGENT_NAME
    _agent_tok = _agentname_tok = None
    try:
        tool_names = [t.name for t in agent_tools] if agent_tools else []

        start_event = {
            "type": "start",
            "agent": agent.get("displayName", agent["name"]),
            "model": model,
            "tools": tool_names,
        }
        yield f"data: {json.dumps(start_event)}\n\n"

        # Emit to the orchestration bus so the live Activity view lights up for
        # streaming chats too (the non-streaming branch already emits these).
        agent_name = agent.get("displayName", agent["name"])
        await emit_agent_started(
            agent_id=agent["id"],
            agent_name=agent_name,
            task=(messages[-1].get("content", "") if messages else "")[:100],
            mission_id=None,
        )
        # Identify the running agent for delegation-edge emits (same as the
        # non-streaming path); the generator body is the context the tool loop
        # runs in, so a delegate_to_agent call below can read these.
        _agent_tok = _CURRENT_AGENT_ID.set(agent["id"])
        _agentname_tok = _CURRENT_AGENT_NAME.set(agent_name)

        tool_calls_log = []

        # If agent has tools, run the tool loop first (non-streaming),
        # emitting tool_call / tool_result events, then stream the final response.
        if agent_tools:
            import asyncio as _asyncio
            _live_q: "_asyncio.Queue" = _asyncio.Queue()

            def on_tool_call(tc: ToolCall):
                tool_calls_log.append({
                    "id": tc.id,
                    "name": tc.name,
                    "arguments": tc.arguments,
                })
                # Mirror to the orchestration bus (live Activity view) and emit a
                # live SSE frame mid-loop so the client shows "using <tool>…"
                # progress DURING the wait, carrying the tool-call id.
                _spawn(emit_tool_call(
                    agent_id=agent["id"], agent_name=agent_name,
                    tool_name=tc.name, arguments=tc.arguments, mission_id=None,
                ))
                _live_q.put_nowait({
                    "type": "tool_call",
                    "id": tc.id,
                    "name": tc.name,
                    "arguments": tc.arguments,
                })

            def on_tool_result(tr: ToolResult):
                _name = None
                for entry in tool_calls_log:
                    if entry["id"] == tr.tool_call_id:
                        entry["result"] = tr.result
                        entry["error"] = tr.error
                        _name = entry["name"]
                        break
                _spawn(emit_tool_result(
                    agent_id=agent["id"], agent_name=agent_name,
                    tool_name=_name,
                    result=tr.result if not tr.error else {"error": tr.error},
                    mission_id=None,
                ))
                _live_q.put_nowait({
                    "type": "tool_result",
                    "id": tr.tool_call_id,
                    "name": _name,
                    "result": tr.result,
                    "error": tr.error,
                    "success": tr.error is None,
                })

            # Run the tool loop as a task and forward tool events from the queue
            # as the callbacks fire mid-loop; drain whatever's left once done.
            _loop_task = _asyncio.create_task(llm_client.execute_tool_loop(
                messages=messages,
                tools=agent_tools,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                user_id=user_id,
                on_tool_call=on_tool_call,
                on_tool_result=on_tool_result,
            ))
            # Forward each tool event from the queue as the callbacks fire
            # mid-loop (live progress), then settle the loop result.
            while not _loop_task.done() or not _live_q.empty():
                try:
                    _evt = await _asyncio.wait_for(_live_q.get(), timeout=0.25)
                    yield f"data: {json.dumps(_evt)}\n\n"
                except _asyncio.TimeoutError:
                    continue
            response = await _loop_task

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

            # The tool-loop response is already complete; emit it as a few larger
            # chunks (a light "typing" feel) rather than hundreds of tiny frames.
            content = strip_channel_artifacts(_strip_thinking(llm_client.get_response_content(response)))
            chunk_size = 180
            for i in range(0, len(content), chunk_size):
                chunk = content[i:i + chunk_size]
                yield f"data: {json.dumps({'type': 'token', 'content': chunk})}\n\n"

            yield f"data: {json.dumps({'type': 'complete', 'content': content, 'model': model, 'toolCalls': tool_calls_log})}\n\n"

            # Phase 7: meter BEFORE [DONE] so a client disconnect after the answer
            # doesn't drop the billing row (the call is best-effort + idempotent).
            await _meter_chat_to_lago(
                user_email, model, {
                    "model": response.get("model", model),
                    "provider": response.get("provider"),
                    "usage": response.get("usage", {}),
                },
                agent=agent,
                tools_called=[t.get("name") for t in (tool_calls_log or [])],
                outcome=_chat_outcome(tool_calls_log),
            )

            yield "data: [DONE]\n\n"

        else:
            # No tools — stream directly from LLM, stripping <think> live so the
            # raw chain-of-thought never reaches the client (parity with the
            # tool-loop path, which strips before chunking).
            accumulated = ""
            feed, flush = _make_think_stripper()
            real_usage = None
            async for chunk_data in llm_client.chat_completion_stream(
                messages=messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                user_id=user_id,
            ):
                try:
                    chunk = json.loads(chunk_data)
                    # Final usage chunk (stream_options.include_usage) carries the
                    # real token counts and has an empty choices array.
                    if chunk.get("usage"):
                        real_usage = chunk["usage"]
                    choices = chunk.get("choices") or []
                    if not choices:
                        continue
                    delta = choices[0].get("delta", {})
                    token = delta.get("content", "")
                    if token:
                        accumulated += token
                        visible = feed(token)
                        if visible:
                            yield f"data: {json.dumps({'type': 'token', 'content': visible})}\n\n"
                except (json.JSONDecodeError, IndexError, KeyError):
                    continue

            tail = flush()
            if tail:
                yield f"data: {json.dumps({'type': 'token', 'content': tail})}\n\n"
            # Canonical final content uses the same strip as the non-stream path.
            final = strip_channel_artifacts(_strip_thinking(accumulated))
            yield f"data: {json.dumps({'type': 'complete', 'content': final, 'model': model})}\n\n"

            # Phase 7: meter BEFORE [DONE] so a disconnect after the answer doesn't
            # drop billing. Prefer the REAL usage from the stream's final
            # include_usage chunk; fall back to a ~4-chars/token estimate when the
            # upstream didn't surface it. Cloud-routed streams are skipped by
            # is_local_route() inside _meter_chat_to_lago.
            try:
                if real_usage and (
                    real_usage.get("total_tokens")
                    or real_usage.get("completion_tokens")
                    or real_usage.get("prompt_tokens")
                ):
                    meter_usage = real_usage
                else:
                    prompt_chars = sum(len((m or {}).get("content", "") or "") for m in (messages or []))
                    est_tokens = max(1, (prompt_chars + len(accumulated)) // 4)
                    meter_usage = {"total_tokens": est_tokens}
                await _meter_chat_to_lago(
                    user_email, model, {
                        "model": model,
                        "provider": None,
                        "usage": meter_usage,
                    },
                    agent=agent,
                    tools_called=[],
                )
            except Exception as _meter_err:
                logger.debug(f"Stream meter failed: {_meter_err}")

            yield "data: [DONE]\n\n"

    except Exception as e:
        logger.error(f"Stream error: {e}")
        yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
    finally:
        # Reset the agent-id contextvars (defensive — the generator has its own
        # task context, but keep it clean).
        for _tok, _var in ((_agent_tok, _CURRENT_AGENT_ID), (_agentname_tok, _CURRENT_AGENT_NAME)):
            if _tok is not None:
                try:
                    _var.reset(_tok)
                except Exception:
                    pass
        # Always return the agent to idle on the orchestration bus.
        try:
            await emit_agent_completed(
                agent_id=agent["id"],
                agent_name=agent.get("displayName", agent["name"]),
                result="",
                mission_id=None,
            )
        except Exception:
            pass


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
    """Attach a tool to an agent.

    C1 tenancy: a shared (NULL-org) agent's tools are mutated via the RLS-exempt
    owner session (``_agent_writer``); a per-org agent on the request session.
    """
    _ensure_agent_access(user, agent_id)

    tool_entry = {
        "id": f"{agent_id}-{request.toolId}",
        "toolId": request.toolId,
        "config": request.config,
        "isEnabled": True,
    }

    async with _agent_writer(agent_id, session) as (agent, repo):
        if agent is None:
            raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")
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
    """Detach a tool from an agent.

    C1 tenancy: a shared (NULL-org) agent's tools are mutated via the RLS-exempt
    owner session (``_agent_writer``); a per-org agent on the request session.
    """
    _ensure_agent_access(user, agent_id)

    async with _agent_writer(agent_id, session) as (agent, repo):
        if agent is None:
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
    """Update tool configuration for an agent.

    C6: NOT IMPLEMENTED. Agents persist their tools as a plain name array
    (``agents.tools``) with no per-tool config column anywhere in the schema, so
    there is nowhere to store a per-tool config today. The previous implementation
    reported ``{"message": "Tool config updated"}`` while persisting NOTHING — a
    silent no-op masquerading as success. We now return ``501 Not Implemented``
    (after the access + attachment checks) rather than lie. Add a per-agent-tool
    config table/column before turning this into a real mutation.
    """
    _ensure_agent_access(user, agent_id)

    repo = AgentRepository(session)
    agent = await repo.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")
    if tool_id not in (agent.get("tools") or []):
        raise HTTPException(
            status_code=404, detail=f"Tool not attached to agent: {tool_id}"
        )

    raise HTTPException(
        status_code=501,
        detail=(
            "Per-tool config persistence is not implemented (agents.tools stores "
            "tool names only; there is no per-tool config store)."
        ),
    )


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

        content = strip_channel_artifacts(_strip_thinking(llm_client.get_response_content(response)))
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

    # Phase 7: billing preflight + user_attrs for RBAC (MLX is a local path;
    # without a billing check free users could burn GPU indefinitely).
    user_attrs, billing_state = await _fetch_user_attrs(user)
    _enforce_billing_or_402(user, billing_state)

    repo = AgentRepository(session)
    agent = await repo.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")

    # Per-agent RBAC (with audit logging on denial)
    await _ensure_agent_access_audited(
        session, user, agent_id, agent,
        request_path=f"POST /api/v1/agents/{agent_id}/chat/local",
        user_attrs=user_attrs,
    )

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

        # Phase 7: MLX is always a local path — meter to Lago.
        _mlx_user_email = (getattr(user, "email", "") or "").lower()
        await _meter_chat_to_lago(_mlx_user_email, request.model, result)

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


# ---- Admin: RBAC audit log ----

@router.get("/admin/rbac/denials")
async def list_rbac_denials(
    session: AsyncSession = Depends(get_session),
    user: Annotated[AuthUser, Depends(require_admin)] = None,
    limit: int = 100,
    agent_id: Optional[str] = None,
    user_email: Optional[str] = None,
):
    """Recent RBAC denials. Admin only.

    Supports optional filtering by ``agent_id`` or ``user_email``. Newest first.
    """
    from sqlalchemy import text
    clauses = []
    params: Dict[str, Any] = {"limit": max(1, min(1000, limit))}
    if agent_id:
        clauses.append("agent_id = :aid")
        params["aid"] = agent_id
    if user_email:
        clauses.append("LOWER(user_email) = LOWER(:em)")
        params["em"] = user_email
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = f"""
        SELECT id, user_id, user_email, user_role, user_tier, agent_id,
               reason, policy_snapshot, auth_source, request_path, denied_at
        FROM rbac_denials
        {where}
        ORDER BY denied_at DESC
        LIMIT :limit
    """
    result = await session.execute(text(sql), params)
    rows = result.mappings().all()
    return {
        "denials": [
            {
                "id": str(r["id"]),
                "user_id": r["user_id"],
                "user_email": r["user_email"],
                "user_role": r["user_role"],
                "user_tier": r["user_tier"],
                "agent_id": r["agent_id"],
                "reason": r["reason"],
                "policy_snapshot": r["policy_snapshot"],
                "auth_source": r["auth_source"],
                "request_path": r["request_path"],
                "denied_at": r["denied_at"].isoformat() + "Z" if r["denied_at"] else None,
            }
            for r in rows
        ],
        "count": len(rows),
    }


@router.get("/admin/activity/conversations")
async def list_conversations_for_user(
    session: AsyncSession = Depends(get_session),
    user: Annotated[AuthUser, Depends(require_admin)] = None,
    user_id: Optional[str] = None,
    since: Optional[str] = None,
    limit: int = 100,
):
    """Admin: list conversations for a given user_id (email or UUID).

    Used by Ops Center's activity aggregator to show per-user chat history.
    ``since`` is an ISO timestamp; defaults to 7 days ago.
    """
    from sqlalchemy import text
    from datetime import datetime, timedelta
    if not user_id:
        return {"conversations": [], "count": 0}
    since_dt = None
    if since:
        try:
            since_dt = datetime.fromisoformat(since.replace("Z", ""))
        except Exception:
            since_dt = None
    if since_dt is None:
        since_dt = datetime.utcnow() - timedelta(days=7)

    sql = """
        SELECT id, agent_id, user_id, title, model, status,
               message_count, total_tokens, created_at, updated_at
        FROM conversations
        WHERE user_id = :uid AND created_at >= :since
        ORDER BY created_at DESC
        LIMIT :lim
    """
    result = await session.execute(text(sql), {"uid": user_id, "since": since_dt, "lim": max(1, min(500, limit))})
    rows = result.mappings().all()
    return {
        "conversations": [
            {
                "id": str(r["id"]),
                "agent_id": r["agent_id"],
                "user_id": r["user_id"],
                "title": r["title"],
                "model": r["model"],
                "status": r["status"],
                "message_count": r["message_count"] or 0,
                "total_tokens": r["total_tokens"] or 0,
                "created_at": r["created_at"].isoformat() + "Z" if r["created_at"] else None,
                "updated_at": r["updated_at"].isoformat() + "Z" if r["updated_at"] else None,
            }
            for r in rows
        ],
        "count": len(rows),
    }
