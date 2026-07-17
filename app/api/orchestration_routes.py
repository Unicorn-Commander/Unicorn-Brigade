"""
Orchestration API Routes - Real-time agent activity streaming

Endpoints:
- GET /api/v1/orchestration/events - SSE stream of agent events
- GET /api/v1/orchestration/state - Current orchestration state
- GET /api/v1/orchestration/missions - Active missions
- POST /api/v1/orchestration/missions - Create mission
- POST /api/v1/orchestration/command - Send command to The General
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Annotated
import logging
import json

from app.db.database import get_session
from app.db.repositories import AgentRepository
from app.auth.middleware import (
    require_api_key,
    require_operator,
    require_admin,
    require_sse_access,
    get_current_user_optional,
    AuthUser,
)
from app.auth.sse_ticket import mint_ticket, TTL_SECONDS as SSE_TICKET_TTL, SSE_TICKET_COOKIE
from app.security.rate_limit import rate_limit
from app.orchestration import (
    event_bus,
    emit_agent_started,
    emit_agent_completed,
    emit_agent_message,
    emit_agent_created,
    EventType,
    OrchestrationEvent,
)
from app.orchestration.event_bus import event_visible_to_org
from app.engine.meta_agent import MetaAgent
from app.llm.ops_center_client import OpsCenterLLMClient

logger = logging.getLogger(__name__)


def extract_content(response: Dict[str, Any]) -> str:
    """
    Extract content from LLM response.

    Handles both OpenAI format (choices[0].message.content) and
    simplified format (content at top level).
    """
    # OpenAI format: {"choices": [{"message": {"content": "..."}}]}
    if "choices" in response and len(response["choices"]) > 0:
        choice = response["choices"][0]
        if "message" in choice and "content" in choice["message"]:
            return choice["message"]["content"] or ""
        # Delta format for streaming
        if "delta" in choice and "content" in choice["delta"]:
            return choice["delta"]["content"] or ""

    # Simplified format: {"content": "..."}
    if "content" in response:
        return response["content"] or ""

    # Fallback: stringify the response
    logger.warning(f"Unexpected response format, no content found: {list(response.keys())}")
    return ""
router = APIRouter(prefix="/orchestration", tags=["orchestration"])

# Will be set by main.py
llm_client: OpsCenterLLMClient = None
meta_agent: MetaAgent = None


def init_orchestration_routes(client: OpsCenterLLMClient):
    """Initialize with LLM client"""
    global llm_client, meta_agent
    llm_client = client
    meta_agent = MetaAgent(client)
    logger.info("Orchestration routes initialized with LLM client")


# ============================================================================
# SSE Event Stream
# ============================================================================

@router.post("/events/ticket")
async def mint_events_ticket(
    response: Response,
    user: Annotated[Optional[AuthUser], Depends(get_current_user_optional)] = None,
    _rl: Annotated[None, rate_limit("orch_sse_ticket", 30, 60)] = None,
):
    """Mint a short-lived, single-use ticket for the SSE stream.

    A browser ``EventSource`` can't send auth headers, so the client calls this
    (with its normal Bearer/X-API-Key/cookie auth) and then opens the stream.
    Authenticating here at *viewer* level — rather than via ``require_operator``
    (every POST under /orchestration would otherwise demand operator) — matches
    what reading the stream requires, so viewer-role users can still see the
    live feed. The ticket only ever grants the holder's own access.

    The ticket is returned BOTH in the body and as an HttpOnly cookie scoped to
    the orchestration routes: the client opens ``GET /events`` and the cookie
    carries the ticket automatically, keeping it out of the URL/access logs. The
    ``?ticket=`` query param stays supported as a fallback (older clients / if
    the cookie is stripped in transit).
    """
    if user is None:
        raise HTTPException(
            status_code=401,
            detail="Authentication required to open the activity stream",
        )
    ticket = mint_ticket(user)
    response.set_cookie(
        key=SSE_TICKET_COOKIE,
        value=ticket,
        max_age=SSE_TICKET_TTL,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/api/v1/orchestration",
    )
    return {"ticket": ticket, "expires_in": SSE_TICKET_TTL}


@router.get("/events")
async def stream_events(
    mission_id: Optional[str] = None,
    user: Annotated[AuthUser, Depends(require_sse_access)] = None,
):
    """
    Server-Sent Events stream of orchestration activity.

    Connect to this endpoint to receive real-time updates about:
    - Agent activity (started, thinking, tool calls, completed)
    - Mission progress
    - Agent creation/delegation

    If ``mission_id`` is provided, only events with a matching mission_id
    are streamed. Used by Crisis Ops to surface per-chat progress without
    bleeding events from other concurrent chats into the user's view.

    M4 tenancy: events are ALSO filtered to the subscriber's active org. Every
    event is stamped at emit time with the org that owns the emitting work (see
    ``event_bus.publish`` / ``current_org_id_var``); a subscriber only receives
    events stamped with its own org, so an authenticated caller can never observe
    another tenant's orchestration activity. ``user.org_id`` is the org bound
    during auth (header path) or captured at ticket-mint time (EventSource path).
    """
    subscriber_org_id = getattr(user, "org_id", None)

    async def generate():
        # Send initial connection event
        yield f"data: {json.dumps({'type': 'connected', 'mission_id': mission_id})}\n\n"

        # Stream events as they come, filtering by org (M4) then mission_id.
        async for event in event_bus.subscribe():
            if not event_visible_to_org(event.org_id, subscriber_org_id):
                continue
            if mission_id and event.mission_id != mission_id:
                continue
            yield event.to_sse()

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )


# ============================================================================
# State Endpoints
# ============================================================================

@router.get("/state")
async def get_orchestration_state(
    session: AsyncSession = Depends(get_session),
    user: Annotated[AuthUser, Depends(require_api_key)] = None,
):
    """
    Get current orchestration state.

    Returns:
    - Active missions
    - Agent states
    - Recent events
    - Statistics
    """
    # S4 tenancy: scope the ENTIRE snapshot (missions, agentStates, recentEvents,
    # and the counts) to the caller's org. ActiveMission/AgentState are now stamped
    # with their owning org at creation, so get_state_snapshot filters them with the
    # same event_visible_to_org rule the SSE stream uses — no cross-tenant activity
    # leaks and the stream filter is untouched.
    subscriber_org_id = getattr(user, "org_id", None)
    state = event_bus.get_state_snapshot(viewer_org_id=subscriber_org_id)

    # Add agent info from database
    repo = AgentRepository(session)
    agents = await repo.list_all()

    # Merge with real agent data (agents are already dicts)
    agent_map = {a["id"]: a for a in agents}
    for agent_state in state["agentStates"]:
        agent_id = agent_state["agentId"]
        if agent_id in agent_map:
            agent_state["agent"] = agent_map[agent_id]

    # Add total agent count
    state["totalAgents"] = len(agents)

    return state


@router.get("/agents/active")
async def get_active_agents(
    user: Annotated[AuthUser, Depends(require_api_key)] = None,
):
    """Get currently active agents, scoped to the caller's org.

    S4 tenancy: AgentState is stamped with its owning org at creation, so the list
    is filtered with event_visible_to_org — a tenant never sees another's agents.
    """
    org_id = getattr(user, "org_id", None)
    return {
        "agents": [
            s.to_dict() for s in event_bus.get_active_agents()
            if event_visible_to_org(s.org_id, org_id)
        ]
    }


# ============================================================================
# Mission Management
# ============================================================================

class CreateMissionRequest(BaseModel):
    name: str = Field(..., description="Mission name")
    description: str = Field("", description="Mission description")
    task: str = Field(..., description="Task to accomplish")
    agents: List[str] = Field(default_factory=list, description="Agent IDs to assign")
    auto_assign: bool = Field(True, description="Let The General assign agents")


@router.get("/missions")
async def get_missions(
    status: Optional[str] = Query(None, description="Filter by status (active, completed, failed)"),
    user: Annotated[AuthUser, Depends(require_api_key)] = None,
):
    """Get all missions.

    S4 tenancy: ActiveMission is stamped with its owning org at creation, so the
    list is filtered to the caller's org with event_visible_to_org.
    """
    org_id = getattr(user, "org_id", None)
    missions = [
        m for m in event_bus.get_all_missions()
        if event_visible_to_org(m.org_id, org_id)
    ]

    if status:
        missions = [m for m in missions if m.status == status]

    return {
        "missions": [m.to_dict() for m in missions]
    }


@router.get("/missions/{mission_id}")
async def get_mission(
    mission_id: str,
    user: Annotated[AuthUser, Depends(require_api_key)] = None,
):
    """Get mission details.

    S4 tenancy: a caller can only read a mission its org owns. A cross-org id
    returns 404 (not 403) so it doesn't confirm the mission's existence.
    """
    org_id = getattr(user, "org_id", None)
    mission = event_bus.get_mission(mission_id)
    if not mission or not event_visible_to_org(mission.org_id, org_id):
        raise HTTPException(status_code=404, detail="Mission not found")

    return mission.to_dict()


@router.post("/missions")
async def create_mission(
    request: CreateMissionRequest,
    session: AsyncSession = Depends(get_session),
    user: Annotated[AuthUser, Depends(require_operator)] = None,
    # auto_assign fires a frontier model per mission — cap it so it can't run
    # unbounded LLM spend.
    _rl: Annotated[None, rate_limit("orch_mission", 15, 60)] = None,
):
    """
    Create a new mission.

    If auto_assign is True, The General will analyze the task
    and assign appropriate agents.
    """
    # Create the mission
    mission = event_bus.create_mission(
        name=request.name,
        description=request.description,
        agents=request.agents,
        lead_agent="the-general",
    )

    # If auto-assign, have The General pick agents
    if request.auto_assign and llm_client:
        try:
            # Get available agents
            repo = AgentRepository(session)
            agents = await repo.list_all()
            agent_info = [
                {"id": a["id"], "name": a.get("displayName", a.get("name")), "domain": a.get("domain"), "tools": a.get("tools", [])}
                for a in agents
            ]

            # Ask The General to assign agents
            general_prompt = f"""You are The General, orchestrator of Unicorn Brigade.

A new mission has been created:
- Name: {request.name}
- Task: {request.task}

Available agents:
{json.dumps(agent_info, indent=2)}

Select the best agents for this mission. Return a JSON object:
{{
  "selected_agents": ["agent-id-1", "agent-id-2"],
  "reasoning": "Why these agents were selected",
  "approach": "How they should work together"
}}"""

            response = await llm_client.chat_completion(
                messages=[{"role": "user", "content": general_prompt}],
                model="openai/gpt-4o-mini",
                temperature=0.3,
            )

            content = extract_content(response)

            # Parse response
            import re
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                assignment = json.loads(json_match.group())
                mission.agents = assignment.get("selected_agents", [])

                # Emit assignment event
                await emit_agent_message(
                    agent_id="the-general",
                    agent_name="The General",
                    message=f"Assigned agents to mission: {', '.join(mission.agents)}",
                    mission_id=mission.id,
                )

        except Exception as e:
            logger.error(f"Auto-assign failed: {e}")

    return {
        "mission": mission.to_dict(),
        "message": f"Mission '{request.name}' created"
    }


# ============================================================================
# The General Commands
# ============================================================================

class CommandRequest(BaseModel):
    command: str = Field(..., description="Natural language command")
    context: Dict[str, Any] = Field(default_factory=dict, description="Additional context")


@router.post("/command")
async def send_command(
    request: CommandRequest,
    session: AsyncSession = Depends(get_session),
    user: Annotated[AuthUser, Depends(require_operator)] = None,
    # Runs an unrestricted frontier chat (and can drive agent creation) — cap it
    # so it can't run unbounded LLM spend.
    _rl: Annotated[None, rate_limit("orch_command", 10, 60)] = None,
):
    """
    Send a command to The General.

    The General can:
    - Create new agents
    - Assign agents to tasks
    - Create workflows
    - Coordinate multi-agent operations
    """
    if not llm_client:
        raise HTTPException(status_code=503, detail="LLM client not initialized")

    # Get available agents
    repo = AgentRepository(session)
    agents = await repo.list_all()
    agent_info = [
        {"id": a["id"], "name": a.get("displayName", a.get("name")), "domain": a.get("domain")}
        for a in agents
    ]

    # Emit that The General is processing
    await emit_agent_started(
        agent_id="the-general",
        agent_name="The General",
        task=request.command,
    )

    # The General's system prompt
    system_prompt = f"""You are The General, supreme orchestrator of Unicorn Brigade.

Your capabilities:
1. CREATE_AGENT - Create new specialized agents for tasks
2. ASSIGN_TASK - Assign tasks to existing agents
3. CREATE_MISSION - Create multi-agent missions
4. COORDINATE - Coordinate between agents

Available agents:
{json.dumps(agent_info, indent=2)}

When responding, indicate any actions to take as JSON:
```json
{{
  "action": "CREATE_AGENT|ASSIGN_TASK|CREATE_MISSION|COORDINATE|RESPOND",
  "details": {{ ... }},
  "response": "Your response to the user"
}}
```

Be strategic and efficient. Delegate appropriately."""

    try:
        response = await llm_client.chat_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": request.command},
            ],
            model="openai/gpt-4o",
            temperature=0.7,
        )

        content = extract_content(response)

        # Parse The General's response
        result = {"response": content, "actions": []}

        import re
        json_match = re.search(r'```json\s*([\s\S]*?)\s*```', content)
        if json_match:
            try:
                action_data = json.loads(json_match.group(1))
                result["action"] = action_data.get("action")
                result["details"] = action_data.get("details", {})
                result["response"] = action_data.get("response", content)

                # Execute action if needed
                if result["action"] == "CREATE_AGENT" and meta_agent:
                    # Use meta-agent to create new agent
                    new_agent_spec = result["details"]
                    created = await meta_agent.create_agent(
                        description=new_agent_spec.get("description", ""),
                        capabilities=new_agent_spec.get("capabilities", []),
                    )
                    if created:
                        await emit_agent_created(
                            creator_id="the-general",
                            creator_name="The General",
                            new_agent=created.model_dump() if hasattr(created, 'model_dump') else {},
                        )
                        result["created_agent"] = created.model_dump() if hasattr(created, 'model_dump') else str(created)

            except json.JSONDecodeError:
                pass

        # Emit completion
        await emit_agent_completed(
            agent_id="the-general",
            agent_name="The General",
            result=result["response"][:200],
        )

        return result

    except Exception as e:
        logger.error(f"Command failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Dynamic Agent Creation
# ============================================================================

class CreateAgentRequest(BaseModel):
    description: str = Field(..., description="What the agent should do")
    name: Optional[str] = Field(None, description="Optional name")
    tools: List[str] = Field(default_factory=list, description="Tools the agent needs")
    parent_mission: Optional[str] = Field(None, description="Mission this agent is for")


@router.post("/agents/create")
async def create_dynamic_agent(
    request: CreateAgentRequest,
    session: AsyncSession = Depends(get_session),
    user: Annotated[AuthUser, Depends(require_admin)] = None,
    _rl: Annotated[None, rate_limit("dynamic_agent_create", 5, 60)] = None,
):
    """
    Dynamically create a new agent using The General.

    The General will design the agent's personality, capabilities,
    and system prompt based on the description.
    """
    if not meta_agent:
        raise HTTPException(status_code=503, detail="Meta agent not initialized")

    try:
        # Have meta-agent create the agent
        agent_def = await meta_agent.create_agent(
            description=request.description,
            capabilities=request.tools,
        )

        if not agent_def:
            raise HTTPException(status_code=500, detail="Failed to create agent")

        # Emit creation event
        await emit_agent_created(
            creator_id="the-general",
            creator_name="The General",
            new_agent=agent_def.model_dump() if hasattr(agent_def, 'model_dump') else {"name": str(agent_def)},
            mission_id=request.parent_mission,
        )

        return {
            "agent": agent_def.model_dump() if hasattr(agent_def, 'model_dump') else {"description": str(agent_def)},
            "message": f"Agent created successfully"
        }

    except Exception as e:
        logger.error(f"Agent creation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
