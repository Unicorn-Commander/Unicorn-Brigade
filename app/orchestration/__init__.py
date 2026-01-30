"""
Orchestration Module - Real-time agent coordination

Provides:
- Event bus for agent activity streaming
- Mission tracking
- Agent state management
"""

from app.orchestration.event_bus import (
    OrchestrationEventBus,
    OrchestrationEvent,
    EventType,
    ActiveMission,
    AgentState,
    event_bus,
    emit_agent_started,
    emit_agent_thinking,
    emit_tool_call,
    emit_tool_result,
    emit_agent_completed,
    emit_agent_message,
    emit_agent_created,
)

__all__ = [
    "OrchestrationEventBus",
    "OrchestrationEvent",
    "EventType",
    "ActiveMission",
    "AgentState",
    "event_bus",
    "emit_agent_started",
    "emit_agent_thinking",
    "emit_tool_call",
    "emit_tool_result",
    "emit_agent_completed",
    "emit_agent_message",
    "emit_agent_created",
]
