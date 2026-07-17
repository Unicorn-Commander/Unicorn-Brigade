"""
Orchestration Event Bus - Real-time agent activity streaming

This module provides:
- Event publishing from agents during execution
- SSE subscription for frontends
- Active mission tracking
- Agent state management
"""

import asyncio
from contextvars import ContextVar
from typing import Dict, Any, List, Optional, Set, Callable, AsyncGenerator
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import json
import logging
import uuid

logger = logging.getLogger(__name__)


# M4: the org that OWNS the work emitting orchestration events. The auth
# middleware (``_bind_org_context``) sets this per request and the scheduler
# (``_bind_org``) sets it per job; ``publish()`` reads it to STAMP each event's
# ``org_id`` so the SSE stream can filter to the subscriber's own org. A
# ``ContextVar`` is per-task — a child task spawned via ``asyncio.create_task``
# inherits a COPY of the context at creation time — so a value set while handling
# one request can never bleed into another request's events.
current_org_id_var: ContextVar[Optional[str]] = ContextVar(
    "orchestration_current_org_id", default=None
)


def event_visible_to_org(
    event_org_id: Optional[str], subscriber_org_id: Optional[str]
) -> bool:
    """M4 SSE visibility rule: an orchestration event reaches a subscriber ONLY
    when it is stamped with the subscriber's own org.

    Plain equality, which gives the safe-by-default behavior: an UNATTRIBUTED
    event (``org_id is None`` — emitted with no bound org context) is withheld
    from any concrete-org subscriber, so an event that failed to get stamped can
    never leak cross-org. A subscriber with no bound org (also None) sees only
    those unattributed events, never a tenant's.
    """
    return event_org_id == subscriber_org_id


class EventType(str, Enum):
    """Types of orchestration events"""
    # Agent lifecycle
    AGENT_STARTED = "agent_started"
    AGENT_THINKING = "agent_thinking"
    AGENT_RESPONDING = "agent_responding"
    AGENT_COMPLETED = "agent_completed"
    AGENT_ERROR = "agent_error"

    # Tool execution
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"

    # Mission/workflow
    MISSION_CREATED = "mission_created"
    MISSION_UPDATED = "mission_updated"
    MISSION_COMPLETED = "mission_completed"
    MISSION_FAILED = "mission_failed"

    # Agent creation (The General creating sub-agents)
    AGENT_CREATED = "agent_created"
    AGENT_ASSIGNED = "agent_assigned"

    # Communication
    AGENT_MESSAGE = "agent_message"
    AGENT_DELEGATION = "agent_delegation"
    AGENT_INVOCATION = "agent_invocation"  # Peer-to-peer agent communication


@dataclass
class OrchestrationEvent:
    """A single orchestration event"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    type: EventType = EventType.AGENT_STARTED
    timestamp: datetime = field(default_factory=datetime.utcnow)

    # Context
    agent_id: str = ""
    agent_name: str = ""
    mission_id: Optional[str] = None
    # M4: the org this event belongs to. Stamped by publish() from
    # current_org_id_var when unset; the SSE stream filters on it so a subscriber
    # only ever receives its own org's events. None = unattributed (system).
    org_id: Optional[str] = None

    # Event data
    data: Dict[str, Any] = field(default_factory=dict)
    message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type.value,
            "timestamp": self.timestamp.isoformat(),
            "agentId": self.agent_id,
            "agentName": self.agent_name,
            "missionId": self.mission_id,
            "orgId": self.org_id,
            "data": self.data,
            "message": self.message,
        }

    def to_sse(self) -> str:
        """Format as Server-Sent Event"""
        return f"data: {json.dumps(self.to_dict())}\n\n"


@dataclass
class ActiveMission:
    """Tracks an active mission/workflow"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    description: str = ""
    status: str = "active"  # active, completed, failed, paused
    progress: int = 0

    # Agents involved
    agents: List[str] = field(default_factory=list)
    lead_agent: Optional[str] = None

    # Timing
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None

    # Results
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    # S4 tenancy: the org that owns this mission, auto-stamped from the bound
    # request/job context at creation (mirrors how publish() stamps events). The
    # snapshot/list endpoints filter on it with event_visible_to_org so one tenant
    # never sees another's mission name/description/task.
    org_id: Optional[str] = field(default_factory=lambda: current_org_id_var.get())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "status": self.status,
            "progress": self.progress,
            "agents": self.agents,
            "leadAgent": self.lead_agent,
            "createdAt": self.created_at.isoformat(),
            "updatedAt": self.updated_at.isoformat(),
            "completedAt": self.completed_at.isoformat() if self.completed_at else None,
            "orgId": self.org_id,
        }


@dataclass
class AgentState:
    """Current state of an agent"""
    agent_id: str
    agent_name: str
    status: str = "idle"  # idle, thinking, executing, waiting
    current_task: Optional[str] = None
    current_mission: Optional[str] = None
    last_activity: datetime = field(default_factory=datetime.utcnow)
    # S4 tenancy: owning org, auto-stamped from the bound context at creation so
    # the active-agents snapshot can be scoped to the caller's org.
    org_id: Optional[str] = field(default_factory=lambda: current_org_id_var.get())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agentId": self.agent_id,
            "agentName": self.agent_name,
            "status": self.status,
            "currentTask": self.current_task,
            "currentMission": self.current_mission,
            "lastActivity": self.last_activity.isoformat(),
            "orgId": self.org_id,
        }


class OrchestrationEventBus:
    """
    Central event bus for orchestration events.

    Agents publish events here, frontends subscribe via SSE.
    """

    _instance: Optional["OrchestrationEventBus"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        # Event queue for subscribers
        self._subscribers: Set[asyncio.Queue] = set()

        # State tracking
        self._missions: Dict[str, ActiveMission] = {}
        self._agent_states: Dict[str, AgentState] = {}
        self._recent_events: List[OrchestrationEvent] = []
        self._max_recent_events = 100

        logger.info("OrchestrationEventBus initialized")

    async def publish(self, event: OrchestrationEvent):
        """Publish an event to all subscribers"""
        # M4: stamp the originating org (from the per-task context) so the SSE
        # stream can filter cross-org events. Only when unset, so an event that
        # already carries an explicit org is left untouched.
        if event.org_id is None:
            event.org_id = current_org_id_var.get()

        # Store in recent events
        self._recent_events.append(event)
        if len(self._recent_events) > self._max_recent_events:
            self._recent_events.pop(0)

        # Update agent state
        if event.agent_id:
            self._update_agent_state(event)

        # Update mission if applicable
        if event.mission_id:
            self._update_mission(event)

        # Broadcast to all subscribers. Non-blocking: a slow or abandoned client
        # must never block the publisher or grow memory without bound, so on a
        # full queue we drop the oldest event to make room for the newest.
        dead_subscribers = set()
        for queue in self._subscribers:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                try:
                    queue.get_nowait()
                    queue.put_nowait(event)
                except Exception:
                    pass
            except Exception as e:
                logger.warning(f"Failed to publish to subscriber: {e}")
                dead_subscribers.add(queue)

        # Clean up dead subscribers
        self._subscribers -= dead_subscribers

        logger.debug(f"Published event: {event.type.value} from {event.agent_id}")

    def _update_agent_state(self, event: OrchestrationEvent):
        """Update agent state based on event"""
        agent_id = event.agent_id

        if agent_id not in self._agent_states:
            self._agent_states[agent_id] = AgentState(
                agent_id=agent_id,
                agent_name=event.agent_name or agent_id
            )

        state = self._agent_states[agent_id]
        state.last_activity = event.timestamp
        state.current_mission = event.mission_id

        # Update status based on event type
        status_map = {
            EventType.AGENT_STARTED: "thinking",
            EventType.AGENT_THINKING: "thinking",
            EventType.TOOL_CALL: "executing",
            EventType.TOOL_RESULT: "thinking",
            EventType.AGENT_RESPONDING: "responding",
            EventType.AGENT_COMPLETED: "idle",
            EventType.AGENT_ERROR: "error",
        }

        if event.type in status_map:
            state.status = status_map[event.type]

        if event.type == EventType.AGENT_STARTED:
            state.current_task = event.data.get("task", event.message)

    def _update_mission(self, event: OrchestrationEvent):
        """Update mission based on event"""
        mission_id = event.mission_id
        if not mission_id:
            return

        if mission_id not in self._missions:
            return

        mission = self._missions[mission_id]
        mission.updated_at = event.timestamp

        if event.type == EventType.MISSION_UPDATED:
            if "progress" in event.data:
                mission.progress = event.data["progress"]
            if "status" in event.data:
                mission.status = event.data["status"]

        elif event.type == EventType.MISSION_COMPLETED:
            mission.status = "completed"
            mission.progress = 100
            mission.completed_at = event.timestamp
            mission.result = event.data.get("result")

        elif event.type == EventType.MISSION_FAILED:
            mission.status = "failed"
            mission.completed_at = event.timestamp
            mission.error = event.data.get("error", event.message)

    async def subscribe(self) -> AsyncGenerator[OrchestrationEvent, None]:
        """Subscribe to orchestration events (SSE stream)"""
        # Bounded so a slow/stalled SSE client can't grow memory without limit;
        # publish() drops the oldest event when this is full.
        queue: asyncio.Queue = asyncio.Queue(maxsize=1000)
        self._subscribers.add(queue)

        logger.info(f"New subscriber connected. Total: {len(self._subscribers)}")

        try:
            while True:
                event = await queue.get()
                yield event
        finally:
            self._subscribers.discard(queue)
            logger.info(f"Subscriber disconnected. Total: {len(self._subscribers)}")

    # Mission management

    def create_mission(
        self,
        name: str,
        description: str = "",
        agents: List[str] = None,
        lead_agent: str = None,
    ) -> ActiveMission:
        """Create a new mission"""
        mission = ActiveMission(
            name=name,
            description=description,
            agents=agents or [],
            lead_agent=lead_agent,
        )
        self._missions[mission.id] = mission

        # Publish event
        asyncio.create_task(self.publish(OrchestrationEvent(
            type=EventType.MISSION_CREATED,
            mission_id=mission.id,
            agent_id=lead_agent or "",
            message=f"Mission created: {name}",
            data=mission.to_dict(),
        )))

        return mission

    def get_mission(self, mission_id: str) -> Optional[ActiveMission]:
        return self._missions.get(mission_id)

    def get_active_missions(self) -> List[ActiveMission]:
        return [m for m in self._missions.values() if m.status == "active"]

    def get_all_missions(self) -> List[ActiveMission]:
        return list(self._missions.values())

    # Agent state

    def get_agent_state(self, agent_id: str) -> Optional[AgentState]:
        return self._agent_states.get(agent_id)

    def get_active_agents(self) -> List[AgentState]:
        return [s for s in self._agent_states.values() if s.status != "idle"]

    def get_all_agent_states(self) -> List[AgentState]:
        return list(self._agent_states.values())

    # Recent events

    def get_recent_events(self, limit: int = 50) -> List[OrchestrationEvent]:
        return self._recent_events[-limit:]

    # State snapshot for initial load

    def get_state_snapshot(self, viewer_org_id: Optional[str] = None) -> Dict[str, Any]:
        """Get current state for initial page load.

        S4 tenancy: when ``viewer_org_id`` is provided, missions / agent states /
        events / counts are all filtered to what that org may see (same rule as the
        SSE stream — ``event_visible_to_org``), so the snapshot cannot leak another
        tenant's activity. ``None`` (unset) returns the unfiltered global view for
        trusted/internal callers only.
        """
        missions = list(self._missions.values())
        agents = list(self._agent_states.values())
        active_missions = self.get_active_missions()
        active_agents = self.get_active_agents()
        recent = self._recent_events[-20:]
        if viewer_org_id is not None:
            missions = [m for m in missions if event_visible_to_org(m.org_id, viewer_org_id)]
            agents = [s for s in agents if event_visible_to_org(s.org_id, viewer_org_id)]
            active_missions = [m for m in active_missions if event_visible_to_org(m.org_id, viewer_org_id)]
            active_agents = [s for s in active_agents if event_visible_to_org(s.org_id, viewer_org_id)]
            recent = [e for e in recent if event_visible_to_org(getattr(e, "org_id", None), viewer_org_id)]
        return {
            "missions": [m.to_dict() for m in missions],
            "agentStates": [s.to_dict() for s in agents],
            "recentEvents": [e.to_dict() for e in recent],
            "activeAgentCount": len(active_agents),
            "activeMissionCount": len(active_missions),
        }


# Global singleton
event_bus = OrchestrationEventBus()


# Helper functions for agents to easily publish events

async def emit_agent_started(agent_id: str, agent_name: str, task: str, mission_id: str = None):
    await event_bus.publish(OrchestrationEvent(
        type=EventType.AGENT_STARTED,
        agent_id=agent_id,
        agent_name=agent_name,
        mission_id=mission_id,
        message=f"{agent_name} started working",
        data={"task": task},
    ))


async def emit_agent_thinking(agent_id: str, agent_name: str, thought: str, mission_id: str = None):
    await event_bus.publish(OrchestrationEvent(
        type=EventType.AGENT_THINKING,
        agent_id=agent_id,
        agent_name=agent_name,
        mission_id=mission_id,
        message=thought,
    ))


async def emit_tool_call(agent_id: str, agent_name: str, tool_name: str, arguments: Dict, mission_id: str = None):
    await event_bus.publish(OrchestrationEvent(
        type=EventType.TOOL_CALL,
        agent_id=agent_id,
        agent_name=agent_name,
        mission_id=mission_id,
        message=f"Calling {tool_name}",
        data={"tool": tool_name, "arguments": arguments},
    ))


async def emit_tool_result(agent_id: str, agent_name: str, tool_name: str, result: Any, mission_id: str = None):
    await event_bus.publish(OrchestrationEvent(
        type=EventType.TOOL_RESULT,
        agent_id=agent_id,
        agent_name=agent_name,
        mission_id=mission_id,
        message=f"{tool_name} completed",
        data={"tool": tool_name, "result": result if isinstance(result, dict) else {"value": str(result)[:500]}},
    ))


async def emit_agent_completed(agent_id: str, agent_name: str, result: str, mission_id: str = None):
    await event_bus.publish(OrchestrationEvent(
        type=EventType.AGENT_COMPLETED,
        agent_id=agent_id,
        agent_name=agent_name,
        mission_id=mission_id,
        message=f"{agent_name} completed task",
        data={"result": result[:500] if result else ""},
    ))


async def emit_agent_message(agent_id: str, agent_name: str, message: str, to_agent: str = None, mission_id: str = None):
    await event_bus.publish(OrchestrationEvent(
        type=EventType.AGENT_MESSAGE,
        agent_id=agent_id,
        agent_name=agent_name,
        mission_id=mission_id,
        message=message,
        data={"toAgent": to_agent} if to_agent else {},
    ))


async def emit_agent_created(creator_id: str, creator_name: str, new_agent: Dict, mission_id: str = None):
    await event_bus.publish(OrchestrationEvent(
        type=EventType.AGENT_CREATED,
        agent_id=creator_id,
        agent_name=creator_name,
        mission_id=mission_id,
        message=f"Created new agent: {new_agent.get('name', 'Unknown')}",
        data={"newAgent": new_agent},
    ))


async def emit_agent_invocation(
    agent_id: str,
    agent_name: str,
    target_agent_id: str,
    target_agent_name: str,
    purpose: str,
    protocol: str = "internal",
    metadata: Optional[Dict[str, Any]] = None,
    mission_id: str = None,
):
    """
    Emit agent invocation event (peer-to-peer communication).

    Args:
        agent_id: ID of the invoking agent
        agent_name: Name of the invoking agent
        target_agent_id: ID of the agent being invoked
        target_agent_name: Name of the agent being invoked
        purpose: Why the agent is being invoked (e.g., "request data", "query knowledge")
        protocol: Communication protocol ('internal', 'a2a', 'ap2')
        metadata: Additional context
        mission_id: Optional mission ID
    """
    await event_bus.publish(OrchestrationEvent(
        type=EventType.AGENT_INVOCATION,
        agent_id=agent_id,
        agent_name=agent_name,
        mission_id=mission_id,
        message=f"{agent_name} invoking {target_agent_name}: {purpose}",
        data={
            "toAgent": target_agent_id,  # For frontend connection rendering
            "toAgentName": target_agent_name,
            "protocol": protocol,  # For connection color (internal, a2a, ap2, peer)
            "purpose": purpose,
            **(metadata or {}),
        },
    ))
