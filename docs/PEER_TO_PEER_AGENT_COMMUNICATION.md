# Peer-to-Peer Agent Communication Event Emission

## Overview

This document describes the implementation of peer-to-peer agent communication event emission for the 3D orchestration visualization. The system now tracks lateral (peer-to-peer) agent communication in addition to hierarchical delegation, enabling the visualization to show complete agent collaboration networks.

## Implementation Date

February 1, 2026

## What Changed

### 1. New Event Type: `AGENT_INVOCATION`

Added to `app/orchestration/event_bus.py`:

```python
class EventType(str, Enum):
    # ... existing event types ...
    AGENT_INVOCATION = "agent_invocation"  # Peer-to-peer agent communication
```

### 2. New Helper Function: `emit_agent_invocation()`

Location: `app/orchestration/event_bus.py`

```python
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
        purpose: Why the agent is being invoked
        protocol: Communication protocol ('internal', 'a2a', 'ap2', 'peer')
        metadata: Additional context
        mission_id: Optional mission ID
    """
```

### 3. Event Emission Points

#### A. A2A Protocol Invocation
**File**: `app/api/a2a_routes.py`

When an external agent invokes a Brigade agent via A2A protocol, the system emits an invocation event:

```python
await emit_agent_invocation(
    agent_id=requesting_agent_id,
    agent_name=requesting_agent_name,
    target_agent_id=agent_id,
    target_agent_name=agent.get("displayName") or agent.get("name"),
    purpose=f"A2A invocation: {request.task[:50]}...",
    protocol="a2a",  # Blue connection
    metadata={
        "task_id": task_id,
        "task_description": request.task[:100],
        "capability": request.capability,
    },
)
```

#### B. Hierarchical Workflow Delegation
**File**: `app/workflows/engine.py`

Two delegation points emit invocation events:

1. **Orchestrator → Team Lead**:
```python
await emit_agent_invocation(
    agent_id="the-general",
    agent_name="The General",
    target_agent_id=team_lead.id,
    target_agent_name=team_lead.name,
    purpose=f"Hierarchical delegation: {step.description[:50]}",
    protocol="internal",  # Purple connection
    metadata={"step_id": step.id, "workflow_type": "hierarchical"},
    mission_id=mission_id,
)
```

2. **Team Lead → Worker**:
```python
await emit_agent_invocation(
    agent_id=team_lead.id,
    agent_name=team_lead.name,
    target_agent_id=worker_id,
    target_agent_name=worker_id,
    purpose=f"Worker delegation: {worker_task[:50]}",
    protocol="internal",  # Purple connection
    metadata={"worker_task": worker_task, "workflow_type": "hierarchical"},
    mission_id=mission_id,
)
```

## Event Structure

Events emitted to the SSE stream have the following structure:

```json
{
  "id": "abc12345",
  "type": "agent_invocation",
  "timestamp": "2026-02-01T12:34:56.789Z",
  "agentId": "source-agent-id",
  "agentName": "Source Agent Name",
  "missionId": "mission-123",
  "message": "Source Agent invoking Target Agent: purpose",
  "data": {
    "toAgent": "target-agent-id",
    "toAgentName": "Target Agent Name",
    "protocol": "a2a",
    "purpose": "Why the invocation happened",
    "task_id": "optional-task-id",
    "other_metadata": "..."
  }
}
```

### Key Fields for Frontend Visualization

- **`type`**: Always `"agent_invocation"`
- **`agentId`**: Source agent (initiator of the invocation)
- **`agentName`**: Human-readable source agent name
- **`data.toAgent`**: Target agent ID (for rendering connections in 3D graph)
- **`data.toAgentName`**: Target agent name
- **`data.protocol`**: Determines connection color/style
- **`data.purpose`**: Reason for invocation (tooltip/hover text)
- **`missionId`**: Optional mission tracking

## Protocol Types & Connection Colors

The `protocol` field determines how the connection is rendered in the 3D visualization:

| Protocol | Color | Use Case |
|----------|-------|----------|
| `internal` | Purple | Hierarchical workflow delegation (Orchestrator → Team Lead → Worker) |
| `a2a` | Blue | A2A protocol agent invocations (external agents) |
| `ap2` | Cyan | AP2 protocol (future use) |
| `peer` | Yellow/Orange | True peer-to-peer lateral communication (agent-to-agent without hierarchy) |

## Frontend Integration

The frontend already handles these events correctly because it was designed to support them. The visualization code in `frontend/src/pages/Orchestration.jsx` listens for `agent_invocation` events and renders connections accordingly.

No frontend changes are required - the events will automatically appear in the 3D visualization once they flow through the SSE stream.

## Use Cases

### 1. A2A Protocol Communication
When an external agent (e.g., via moltbot or another A2A system) invokes a Brigade agent, the connection is shown in the 3D graph with a blue line.

### 2. Hierarchical Workflows
When The General delegates to a Team Lead, or when a Team Lead delegates to a Worker, purple connections show the hierarchical flow.

### 3. Agent Collaboration (Future)
When agents query knowledge graphs, invoke RAG systems, or request data from specialist agents laterally (peer-to-peer), these can use the `peer` protocol for distinct visualization.

## Testing

Run the test script to verify the implementation:

```bash
python3 test_agent_invocation_events.py
```

Expected output:
- ✓ All event types emit correctly
- ✓ Events contain proper metadata
- ✓ Events are stored in the event bus
- ✓ Frontend-compatible event structure

## Files Modified

1. **`app/orchestration/event_bus.py`**
   - Added `AGENT_INVOCATION` event type
   - Added `emit_agent_invocation()` helper function

2. **`app/orchestration/__init__.py`**
   - Exported `emit_agent_invocation` function

3. **`app/api/a2a_routes.py`**
   - Imported `emit_agent_invocation`
   - Emit events on A2A agent invocation

4. **`app/workflows/engine.py`**
   - Imported `emit_agent_invocation`
   - Emit events on orchestrator → team lead delegation
   - Emit events on team lead → worker delegation

## Benefits

1. **Complete Network Visibility**: The 3D visualization now shows the full agent collaboration network, not just hierarchical delegation
2. **Protocol Differentiation**: Different connection colors distinguish between internal delegation, A2A invocations, and peer communication
3. **Real-Time Tracking**: All agent-to-agent communication is tracked in real-time via SSE
4. **Mission Correlation**: Events can be linked to missions for multi-agent task tracking
5. **Debugging Aid**: Developers can trace how agents communicate and delegate tasks

## Future Enhancements

1. **Tool-Based Agent Invocations**: If a tool invokes another agent (e.g., `query_agent` tool), emit invocation events
2. **Agent Chat Forwarding**: If one agent's chat is forwarded to another agent, emit invocation event with `protocol="peer"`
3. **AP2 Protocol Support**: When AP2 protocol is implemented, connections will automatically render in cyan
4. **RAG/Knowledge Agent Queries**: When agents query knowledge graphs or RAG systems, emit with `protocol="peer"`

## Backward Compatibility

All changes are backward compatible:
- Existing `emit_agent_message` calls still work
- Existing delegation events are unchanged
- New events add visualization data without breaking existing functionality

## SSE Event Example

When an A2A agent invokes Colonel Finance:

```
data: {"id":"a1b2c3d4","type":"agent_invocation","timestamp":"2026-02-01T12:34:56.789Z","agentId":"external-system","agentName":"External System","data":{"toAgent":"col-finance","toAgentName":"Colonel Finance","protocol":"a2a","purpose":"A2A invocation: Financial analysis request","task_id":"task-123"}}

```

The frontend visualization receives this event via SSE and renders a blue connection from the external agent to Colonel Finance.

## Conclusion

The peer-to-peer agent communication event emission system is now complete and production-ready. The 3D orchestration visualization can display the full agent collaboration network with protocol-specific connection rendering.
