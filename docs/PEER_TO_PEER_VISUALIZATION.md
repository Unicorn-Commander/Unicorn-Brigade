# Peer-to-Peer Agent Connection Visualization

**Implementation Date**: February 1, 2026  
**Status**: ✅ Complete

## Overview

Added visual distinction for peer-to-peer agent communication in the 3D Orchestration view. When agents communicate laterally (colleague-to-colleague rather than hierarchical boss-to-subordinate), connections now appear in **yellow/amber** instead of purple.

## Visual Design

### Connection Types (Color Coding)

| Type | Color | Use Case | Example |
|------|-------|----------|---------|
| **Hierarchical** | Purple (`#c084fc`) | Boss → Subordinate | The General → Team Lead |
| **Peer-to-Peer** | Yellow (`#fbbf24`) | Colleague → Colleague | Data Analyst → Finance Agent |
| **A2A Protocol** | Blue (`#3b82f6`) | External federated agents | Internal → External Agent |
| **AP2 Protocol** | Cyan (`#22d3ee`) | Paid external services | Internal → Paid API Service |

## Implementation Details

### Backend Event Structure

The backend emits `agent_invocation` events via the orchestration SSE stream:

```python
# app/orchestration/event_bus.py
await emit_agent_invocation(
    agent_id="sgt-data",
    agent_name="Sgt. Data Analyst",
    target_agent_id="col-finance",
    target_agent_name="Col. Finance",
    purpose="Request financial metrics",
    protocol="peer",  # Can be: internal, peer, a2a, ap2
    mission_id="mission-123"
)
```

**Event Payload Structure**:
```json
{
  "id": "abc12345",
  "type": "agent_invocation",
  "timestamp": "2026-02-01T12:00:00Z",
  "agentId": "sgt-data",
  "agentName": "Sgt. Data Analyst",
  "missionId": "mission-123",
  "message": "Sgt. Data Analyst invoking Col. Finance: Request financial metrics",
  "data": {
    "toAgent": "col-finance",
    "toAgentName": "Col. Finance",
    "protocol": "peer",
    "purpose": "Request financial metrics"
  }
}
```

### Frontend Changes

#### 1. Orchestration.jsx - SSE Event Handling

**File**: `frontend/src/pages/Orchestration.jsx`

**Lines 174-203**: Added handler for `agent_invocation` events:
```javascript
if (event.type === 'agent_invocation') {
  const targetAgentId = event.data?.toAgent || event.targetAgentId;
  const targetAgentName = event.data?.toAgentName || event.targetAgentName;
  const purpose = event.data?.purpose || event.purpose || 'Peer request';

  setEvents(prev => [{
    id: Date.now(),
    type: 'agent_invocation',
    agentId: event.agentId,
    agentName: event.agentName,
    targetAgentId: targetAgentId,
    targetAgentName: targetAgentName,
    purpose: purpose,
    protocol: event.data?.protocol || event.protocol || 'peer',
    timestamp: event.timestamp,
    data: event.data
  }, ...prev].slice(0, 100));

  // Mark both agents as active
  setActiveAgents(prev => [...new Set([...prev, event.agentId])]);
  setActiveAgents(prev => [...new Set([...prev, targetAgentId])]);

  return; // Skip further processing
}
```

**Lines 603-623**: Activity feed rendering with yellow highlighting:
```javascript
if (event.type === 'agent_invocation') {
  return (
    <div className="bg-yellow-400/10 border border-yellow-400/30">
      <div className="w-2 h-2 rounded-full bg-yellow-400" />
      <p className="text-xs">
        <span className="text-yellow-400">{event.agentName}</span> →{' '}
        <span className="text-yellow-400">{event.targetAgentName}</span>:{' '}
        {event.purpose}
      </p>
    </div>
  );
}
```

#### 2. WorkflowVisualization3D.jsx - 3D Connection Rendering

**File**: `frontend/src/components/WorkflowVisualization3D.jsx`

**Lines 91-123**: Dynamic connection creation from SSE events:
```javascript
if (latestEvent.type === 'agent_invocation') {
  const targetAgentId = latestEvent.data?.toAgent || latestEvent.targetAgentId;
  const purpose = latestEvent.data?.purpose || latestEvent.purpose;
  const protocol = latestEvent.data?.protocol || 'peer';

  if (!targetAgentId) return;

  const newConnection = {
    id: `peer-${latestEvent.agentId}-${targetAgentId}-${Date.now()}`,
    source: latestEvent.agentId,
    target: targetAgentId,
    label: purpose,
    protocol: protocol,
    isPeer: true,
    temporary: true,
    timestamp: Date.now(),
  };

  // Add connection (avoid duplicates)
  setActiveConnections(prev => {
    const exists = prev.some(c =>
      c.source === newConnection.source &&
      c.target === newConnection.target &&
      Date.now() - c.timestamp < 4000
    );
    if (exists) return prev;
    return [...prev, newConnection];
  });

  // Auto-fade after 5 seconds
  setTimeout(() => {
    setActiveConnections(prev => prev.filter(c => c.id !== newConnection.id));
  }, 5000);
}
```

**Lines 186-198**: Protocol-based color mapping:
```javascript
if (conn.protocol === 'peer') {
  linkColor = 'rgba(251, 191, 36, 0.8)'; // Yellow/amber
  particleColor = '#fbbf24';
} else if (conn.protocol === 'a2a') {
  linkColor = 'rgba(59, 130, 246, 0.8)'; // Blue
  particleColor = '#60a5fa';
} else if (conn.protocol === 'ap2') {
  linkColor = 'rgba(6, 182, 212, 0.8)'; // Cyan
  particleColor = '#22d3ee';
} else {
  linkColor = 'rgba(139, 92, 246, 0.4)'; // Purple (hierarchical)
  particleColor = '#c084fc';
}
```

**Lines 526-547**: Updated legend to show all 4 connection types:
```javascript
<div>
  <p>Connection Types</p>
  <div>
    <div>🟣 Hierarchical</div>
    <div>🟡 Peer-to-Peer</div>
    <div>🔵 A2A Protocol</div>
    <div>🔷 AP2 Protocol</div>
  </div>
</div>
```

## Testing

### Test Script

**File**: `scripts/test_peer_visualization.py`

```bash
# Run test (requires backend running)
python scripts/test_peer_visualization.py

# Expected output:
# ✓ Events emitted successfully
# Frontend checklist:
#   1. Open http://localhost:5173/orchestration
#   2. Check Activity Feed for yellow peer invocations
#   3. Verify 3D visualization shows yellow connections
#   4. Confirm legend shows 'Peer-to-Peer' in yellow
```

### Manual Testing

1. **Start backend**:
   ```bash
   uvicorn app.main:app --reload --port 8100
   ```

2. **Start frontend**:
   ```bash
   cd frontend && npm run dev
   ```

3. **Open Orchestration page**:
   ```
   http://localhost:5173/orchestration
   ```

4. **Trigger peer invocation** (via API or test script):
   ```bash
   python scripts/test_peer_visualization.py
   ```

5. **Expected behavior**:
   - Activity feed shows yellow-highlighted peer invocations
   - 3D visualization renders yellow connections between agents
   - Connections auto-fade after 5 seconds
   - Both source and target agents pulse as "active"

## UI/UX Features

### Activity Feed
- Yellow background (`bg-yellow-400/10`)
- Yellow border (`border-yellow-400/30`)
- Yellow dot indicator
- Format: `Agent A → Agent B: Purpose`
- Timestamp displayed

### 3D Visualization
- Yellow line connections (`rgba(251, 191, 36, 0.8)`)
- Yellow particles flowing along connection (`#fbbf24`)
- Thicker line width (2.5px vs 1.5px for static)
- More particles (4 vs 2)
- Faster particle speed (0.008 vs 0.005)
- Auto-fade after 5 seconds

### Legend
- Shows all 4 connection types
- Color-coded dots for easy identification
- Clear labels: "Hierarchical", "Peer-to-Peer", "A2A Protocol", "AP2 Protocol"

## Key Differentiators

| Aspect | Hierarchical | Peer-to-Peer |
|--------|-------------|--------------|
| **Relationship** | Boss → Subordinate | Colleague → Colleague |
| **Color** | Purple | Yellow |
| **Authority** | Command/delegation | Request/collaboration |
| **Example** | General assigns task | Data agent asks finance agent |

## Files Modified

1. `/frontend/src/pages/Orchestration.jsx` - SSE event handling, activity feed
2. `/frontend/src/components/WorkflowVisualization3D.jsx` - 3D rendering, colors, legend

## Files Created

1. `/scripts/test_peer_visualization.py` - Test script
2. `/docs/PEER_TO_PEER_VISUALIZATION.md` - This document

## Success Criteria

✅ Frontend handles `agent_invocation` events from SSE  
✅ Peer-to-peer connections appear in yellow/orange  
✅ Legend shows all 4 connection types  
✅ Activity feed displays peer invocations distinctly  
✅ Connections auto-fade after 5 seconds  
✅ No errors in browser console  
✅ Build succeeds (`npm run build`)  

## Future Enhancements

- [ ] Connection strength visualization (thickness based on frequency)
- [ ] Bi-directional connections (A→B and B→A simultaneously)
- [ ] Connection history panel showing recent peer interactions
- [ ] Filter connections by type (show only peer, only hierarchical, etc.)
- [ ] Click on connection to see interaction details
- [ ] Aggregate peer relationships over time

## Notes

- Default protocol is `"peer"` if not specified
- Connections are temporary and auto-fade to keep visualization clean
- Both source and target agents show as "active" during peer interaction
- Duplicate detection prevents overlapping connections within 4 seconds
- Backend event structure matches frontend expectations (via `data.toAgent`)

---

**Last Updated**: February 1, 2026  
**Author**: Claude Code  
**Status**: ✅ Production Ready
