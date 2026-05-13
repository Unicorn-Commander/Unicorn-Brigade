"""
A2A (Agent-to-Agent) Protocol API Routes

Exposes Brigade agents via the A2A protocol for federation with external systems.
Enables moltbot, other AI assistants, and A2A clients to discover and invoke Brigade agents.

Endpoints:
- GET /a2a/info - Server info and capabilities
- GET /a2a/agents - List all available agents (agent cards)
- GET /a2a/agents/{agent_id}/card - Get agent card for a specific agent
- POST /a2a/agents/{agent_id}/invoke - Invoke an agent
- GET /a2a/tasks/{task_id}/status - Check task status (for async)
- GET /a2a/discover - Search for agents by capability/domain/query
"""

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Dict, List, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
import logging
import uuid
import time
import json
import os

_PUBLIC_BASE_URL = os.environ.get("BRIGADE_URL") or os.environ.get("BRIGADE_PUBLIC_URL") or "http://localhost:8100"

from app.db.database import get_session
from app.db.repositories import AgentRepository
from app.llm.ops_center_client import OpsCenterLLMClient
from app.llm.tool_resolver import get_tools_for_agent
from app.orchestration import emit_agent_invocation
from app.protocols.a2a import (
    AgentCard,
    AgentEndpoint,
    AgentCapability,
    AuthConfig,
    RateLimitConfig,
    PricingConfig,
    AgentMetadata,
    A2AInvokeRequest,
    A2AInvokeResponse,
    InvocationStatus,
    AuthType,
    AgentStatus,
)

logger = logging.getLogger(__name__)
router = APIRouter()

# Global LLM client (injected during startup)
llm_client: OpsCenterLLMClient = None

# In-memory task storage (for async invocations)
_tasks: Dict[str, Dict[str, Any]] = {}


def init_a2a_routes(client: OpsCenterLLMClient):
    """Initialize A2A routes with LLM client."""
    global llm_client
    llm_client = client


def _agent_to_card(agent: Dict[str, Any], base_url: str = None) -> AgentCard:
    if base_url is None:
        base_url = _PUBLIC_BASE_URL
    """Convert a DB agent to an A2A AgentCard."""
    agent_id = agent["id"]

    # Build capabilities from agent's capabilities list
    capabilities = []
    for cap_name in agent.get("capabilities", []):
        capabilities.append(AgentCapability(
            name=cap_name,
            description=f"{cap_name} capability",
            domains=[agent.get("domain", "general")],
        ))

    # Add tool-based capabilities
    for tool_name in agent.get("tools", []):
        capabilities.append(AgentCapability(
            name=f"tool:{tool_name}",
            description=f"Can use the {tool_name} tool",
            tags=["tool", tool_name],
        ))

    return AgentCard(
        id=agent_id,
        name=agent.get("displayName") or agent.get("name"),
        description=agent.get("bio") or agent.get("persona", "")[:200] or "AI Agent",
        version="1.0.0",
        endpoints=AgentEndpoint(
            invoke_url=f"{base_url}/api/v1/a2a/agents/{agent_id}/invoke",
            stream_url=f"{base_url}/api/v1/a2a/agents/{agent_id}/invoke?stream=true",
            card_url=f"{base_url}/api/v1/a2a/agents/{agent_id}/card",
        ),
        capabilities=capabilities,
        domain=agent.get("domain"),
        subdomain=agent.get("subdomain"),
        tags=agent.get("capabilities", []),
        auth=AuthConfig(
            auth_type=AuthType.API_KEY if agent.get("requiresAuth") else AuthType.NONE,
            api_key_header="X-API-Key",
        ),
        rate_limits=RateLimitConfig(
            requests_per_minute=60,
            requests_per_hour=1000,
        ),
        pricing=PricingConfig(
            model=agent.get("pricingModel", "free"),
            price_per_call=agent.get("basePrice"),
        ),
        status=AgentStatus.ACTIVE if agent.get("status") == "active" else AgentStatus.INACTIVE,
        metadata=AgentMetadata(
            organization="Unicorn Brigade",
            website="https://unicorncommander.ai",
        ),
        provider="Unicorn Brigade",
    )


# ---- Request/Response Models ----

class A2AInvokeBody(BaseModel):
    """Request body for A2A invocation."""
    task: str
    capability: Optional[str] = None
    context: Dict[str, Any] = {}
    input_data: Optional[Dict[str, Any]] = None
    session_id: Optional[str] = None
    conversation_history: List[Dict[str, Any]] = []
    user_id: Optional[str] = None
    timeout_seconds: int = 120
    stream: bool = False


class A2ADiscoverQuery(BaseModel):
    """Query parameters for agent discovery."""
    query: Optional[str] = None
    domain: Optional[str] = None
    capability: Optional[str] = None
    tags: Optional[List[str]] = None
    limit: int = 50


# ---- Endpoints ----

@router.get("/a2a/info")
async def get_a2a_info():
    """Get A2A server info and capabilities."""
    return {
        "name": "Unicorn Brigade",
        "version": "1.0.0",
        "protocol": "a2a",
        "a2a_version": "1.0.0",
        "description": "AI Agent Factory - Enterprise agent orchestration platform",
        "provider": "Magic Unicorn Unconventional Technology & Stuff Inc",
        "capabilities": {
            "discovery": True,
            "invocation": True,
            "streaming": True,
            "async_tasks": True,
            "federation": True,
        },
        "endpoints": {
            "agents": "/api/v1/a2a/agents",
            "discover": "/api/v1/a2a/discover",
            "invoke": "/api/v1/a2a/agents/{agent_id}/invoke",
            "card": "/api/v1/a2a/agents/{agent_id}/card",
            "status": "/api/v1/a2a/tasks/{task_id}/status",
        },
    }


@router.get("/a2a/agents")
async def list_a2a_agents(
    domain: Optional[str] = None,
    status: Optional[str] = "active",
    session: AsyncSession = Depends(get_session),
):
    """List all agents as A2A agent cards."""
    repo = AgentRepository(session)
    agents = await repo.list_all()

    # Filter by domain and status
    if domain:
        agents = [a for a in agents if a.get("domain") == domain]
    if status:
        agents = [a for a in agents if a.get("status") == status]

    cards = [_agent_to_card(a) for a in agents]

    return {
        "agents": [card.model_dump() for card in cards],
        "count": len(cards),
        "protocol": "a2a/1.0",
    }


@router.get("/a2a/agents/{agent_id}/card")
async def get_agent_card(
    agent_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Get the A2A agent card for a specific agent."""
    repo = AgentRepository(session)
    agent = await repo.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")

    card = _agent_to_card(agent)
    return card.model_dump()


@router.post("/a2a/agents/{agent_id}/invoke")
async def invoke_agent(
    agent_id: str,
    request: A2AInvokeBody,
    session: AsyncSession = Depends(get_session),
):
    """
    Invoke an agent via A2A protocol.

    This is the main entry point for agent-to-agent communication.
    """
    repo = AgentRepository(session)
    agent = await repo.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")

    if agent.get("status") != "active":
        raise HTTPException(status_code=503, detail=f"Agent not available: {agent_id}")

    task_id = str(uuid.uuid4())
    start_time = time.time()

    logger.info(f"A2A invoke: agent={agent_id}, task_id={task_id}, task={request.task[:50]}...")

    # Emit agent invocation event for peer-to-peer communication tracking
    # Extract requesting agent info from context if available
    requesting_agent_id = request.context.get("requesting_agent_id", "external")
    requesting_agent_name = request.context.get("requesting_agent_name", "External System")

    await emit_agent_invocation(
        agent_id=requesting_agent_id,
        agent_name=requesting_agent_name,
        target_agent_id=agent_id,
        target_agent_name=agent.get("displayName") or agent.get("name"),
        purpose=f"A2A invocation: {request.task[:50]}...",
        protocol="a2a",  # This will make connection blue
        metadata={
            "task_id": task_id,
            "task_description": request.task[:100],
            "capability": request.capability,
        },
    )

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

    # Add conversation history
    for msg in request.conversation_history:
        messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})

    # Add context if provided
    if request.context:
        context_str = json.dumps(request.context, indent=2)
        messages.append({"role": "system", "content": f"Context:\n{context_str}"})

    # Add the task
    messages.append({"role": "user", "content": request.task})

    # Resolve model and params
    model = agent.get("model", "openai/gpt-4o-mini")
    temperature = agent.get("temperature", 0.7)
    max_tokens = agent.get("maxTokens", 2000)

    # Get agent tools
    agent_tools = get_tools_for_agent(agent)

    try:
        tool_calls_log = []

        if agent_tools:
            # Function calling path
            def on_tool_call(tc):
                tool_calls_log.append({
                    "id": tc.id,
                    "name": tc.name,
                    "arguments": tc.arguments,
                    "timestamp": time.time(),
                })

            def on_tool_result(tr):
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
                user_id=request.user_id,
                on_tool_call=on_tool_call,
                on_tool_result=on_tool_result,
            )
        else:
            # Plain chat
            response = await llm_client.chat_completion(
                messages=messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                user_id=request.user_id,
            )

        content = llm_client.get_response_content(response)
        usage = response.get("usage", {})
        duration = time.time() - start_time

        # Build A2A response
        a2a_response = A2AInvokeResponse(
            status=InvocationStatus.COMPLETED,
            result=content,
            output_data={"content": content, "tool_calls": tool_calls_log} if tool_calls_log else None,
            task_id=task_id,
            tool_calls=[],  # Simplified for now
            tokens_used={
                "input": usage.get("prompt_tokens", 0),
                "output": usage.get("completion_tokens", 0),
            },
            duration_seconds=duration,
            agent_id=agent_id,
            agent_version="1.0.0",
            model_used=model,
        )

        logger.info(f"A2A invoke complete: task_id={task_id}, duration={duration:.2f}s")
        return a2a_response.model_dump()

    except Exception as e:
        logger.error(f"A2A invoke error: agent={agent_id}, error={e}")
        error_response = A2AInvokeResponse(
            status=InvocationStatus.FAILED,
            error=str(e),
            error_code="INVOCATION_FAILED",
            task_id=task_id,
            agent_id=agent_id,
            duration_seconds=time.time() - start_time,
        )
        return error_response.model_dump()


@router.post("/a2a/discover")
async def discover_agents(
    query: A2ADiscoverQuery,
    session: AsyncSession = Depends(get_session),
):
    """
    Discover agents by capability, domain, or search query.

    This enables federated discovery across the Brigade agent catalog.
    """
    repo = AgentRepository(session)
    all_agents = await repo.list_all()

    # Filter agents
    matching = []
    for agent in all_agents:
        if agent.get("status") != "active":
            continue

        card = _agent_to_card(agent)

        # Query filter
        if query.query and not card.matches_query(query.query):
            continue

        # Domain filter
        if query.domain and card.domain != query.domain:
            continue

        # Capability filter
        if query.capability:
            if not any(cap.name == query.capability or f"tool:{query.capability}" == cap.name for cap in card.capabilities):
                continue

        # Tags filter
        if query.tags:
            if not any(tag in card.tags for tag in query.tags):
                continue

        matching.append(card)

    # Apply limit
    matching = matching[:query.limit]

    return {
        "agents": [card.model_dump() for card in matching],
        "count": len(matching),
        "query": query.model_dump(),
    }


@router.get("/a2a/tasks/{task_id}/status")
async def get_task_status(task_id: str):
    """Get status of an async task."""
    task = _tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

    return task


@router.get("/a2a/domains")
async def list_domains(session: AsyncSession = Depends(get_session)):
    """List all available domains with agent counts."""
    repo = AgentRepository(session)
    domains = await repo.get_domains()

    return {
        "domains": domains,
        "count": len(domains),
    }
