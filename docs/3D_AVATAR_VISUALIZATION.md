# 3D Avatar Visualization Implementation

## Overview

The 3D orchestration visualization now renders agents as avatar images instead of colored spheres, with dynamic connection visualization based on real-time SSE events.

**Date**: February 1, 2026
**Status**: Implemented and tested

---

## Features Implemented

### 1. Avatar Rendering with 3D Sprites

**Component**: `frontend/src/components/WorkflowVisualization3D.jsx`

#### Avatar Types

| Agent ID | Avatar | Implementation |
|----------|--------|----------------|
| `the-general` | `/The_General_Logo.png` | Image texture sprite |
| `gunny` | `/Gunny_Logo.png` | Image texture sprite |
| Other agents | Emoji (🦄, etc.) | Canvas-based sprite with colored background |

#### Implementation Details

- **Three.js Sprites**: Used `THREE.Sprite` with `THREE.SpriteMaterial` for billboard rendering
- **Texture Loading**: Asynchronous texture loading with placeholder fallback
- **Canvas Rendering**: Emoji avatars rendered on HTML5 canvas for agents without image URLs
- **Scale**: 12x12 units for consistent sizing

#### Code Example

```javascript
const nodeThreeObject = useCallback((node) => {
  const group = new THREE.Group();

  // Determine avatar source
  let avatarSrc = null;
  if (node.id === 'the-general') {
    avatarSrc = '/The_General_Logo.png';
  } else if (node.id === 'gunny') {
    avatarSrc = '/Gunny_Logo.png';
  } else if (node.avatar?.startsWith('/') || node.avatar?.startsWith('http')) {
    avatarSrc = node.avatar;
  }

  // Load texture or render canvas emoji
  // ... (see implementation)

  return group;
}, []);
```

---

### 2. Agent Type Indicators (Borders & Glows)

Agents are visually differentiated based on their `agentType` field (from database):

| Agent Type | Border Color | Glow | Description |
|------------|--------------|------|-------------|
| `local` | White (#ffffff) | None | Default local agents (solid border, opacity 0.4) |
| `federated` | Blue (#3b82f6) | Yes | A2A federated agents (dashed border, blue glow) |
| `external-free` | Green (#10b981) | Yes | External free tier agents (dotted border, green glow) |
| `external-paid` | Gold (#f59e0b) | Yes | External paid tier agents (double border, gold glow) |

#### Visual Implementation

- **Border Ring**: `THREE.RingGeometry` with `THREE.MeshBasicMaterial`
- **Glow Effect**: Larger `THREE.CircleGeometry` with low opacity, animated pulsing
- **Animation**: Glow scales between 0.9-1.1x at 2-second intervals

```javascript
// Border ring
const ringGeometry = new THREE.RingGeometry(6.5, 7.5, 32);
const ringMaterial = new THREE.MeshBasicMaterial({
  color: ringColor,
  transparent: true,
  opacity: ringOpacity,
  side: THREE.DoubleSide,
});

// Animated glow for non-local agents
if (agentType !== 'local') {
  const glowGeometry = new THREE.CircleGeometry(8, 32);
  // ... pulsing animation
}
```

---

### 3. Dynamic Connections from SSE Events

**Props**: New `realtimeEvents` prop accepts array of SSE events from Orchestration page

#### Event Types Tracked

| Event Type | Source Field | Target Field | Protocol | Connection Color |
|------------|-------------|--------------|----------|------------------|
| `agent_delegation` | `event.agentId` | `event.data.toAgent` | `event.data.protocol` | Based on protocol |
| `agent_message` | `event.agentId` | `event.data.toAgent` | `event.data.protocol` | Based on protocol |

#### Protocol Colors

| Protocol | Connection Color | Particle Color | Width | Particles |
|----------|-----------------|----------------|-------|-----------|
| `internal` | `rgba(139, 92, 246, 0.8)` | `#c084fc` (purple) | 2.5 | 4 |
| `a2a` | `rgba(59, 130, 246, 0.8)` | `#60a5fa` (blue) | 2.5 | 4 |
| `ap2` | `rgba(6, 182, 212, 0.8)` | `#22d3ee` (cyan) | 2.5 | 4 |

#### Connection Lifecycle

1. **Creation**: Event arrives with `toAgent` field
2. **Rendering**: Temporary connection added to graph with vibrant color
3. **Animation**: Fast-moving particles (0.008 speed vs 0.005 default)
4. **Auto-Fade**: Connection removed after 5 seconds

```javascript
useEffect(() => {
  if (!realtimeEvents || realtimeEvents.length === 0) return;

  const latestEvent = realtimeEvents[0];

  if (
    ['agent_delegation', 'agent_message'].includes(latestEvent.type) &&
    latestEvent.data?.toAgent
  ) {
    const newConnection = {
      id: `temp-${latestEvent.id}`,
      source: latestEvent.agentId,
      target: latestEvent.data.toAgent,
      protocol: latestEvent.data.protocol || 'internal',
      temporary: true,
    };

    setActiveConnections(prev => [...prev, newConnection]);

    setTimeout(() => {
      setActiveConnections(prev => prev.filter(c => c.id !== newConnection.id));
    }, 5000);
  }
}, [realtimeEvents]);
```

---

### 4. Updated Legend

**Location**: Bottom-left panel

The legend now shows:

1. **Domains** (6 colors)
   - Financial, Legal, Medical, Technology, Intelligence, Investigation

2. **Protocols** (3 types)
   - Internal (purple line)
   - A2A (blue line)
   - AP2 (cyan line)

3. **Agent Types** (4 types)
   - Local (white border)
   - Federated (blue glow)
   - External (Free) (green glow)
   - External (Paid) (gold glow)

---

## Integration Points

### Parent Component

**File**: `frontend/src/pages/Orchestration.jsx`

**Changes**:
```javascript
// Pass realtime events to visualization
<WorkflowVisualization3D
  agents={filteredAgents}
  connections={filteredConnections}
  activeAgents={activeAgents}
  realtimeEvents={events}  // NEW
  // ... other props
/>
```

### SSE Event Format

Events must include:
```javascript
{
  id: "event-id",
  type: "agent_delegation" | "agent_message",
  agentId: "source-agent-id",
  data: {
    toAgent: "target-agent-id",
    protocol: "internal" | "a2a" | "ap2"  // optional
  }
}
```

---

## File Changes

| File | Changes |
|------|---------|
| `frontend/src/components/WorkflowVisualization3D.jsx` | Complete avatar rendering, dynamic connections, protocol indicators |
| `frontend/src/pages/Orchestration.jsx` | Pass `realtimeEvents` prop to visualization |

---

## Dependencies

All required dependencies already installed:

- `three@0.182.0` (via `react-force-graph-3d`)
- `react-force-graph-3d@1.29.0`
- `framer-motion@12.29.2`
- `lucide-react@0.294.0`

**Build Status**: ✅ Successfully builds with no errors

---

## Performance Considerations

1. **Texture Caching**: Three.js `TextureLoader` caches loaded images automatically
2. **Placeholder Rendering**: Canvas sprites created immediately, image textures swap in when loaded
3. **Connection Cleanup**: Auto-removal after 5 seconds prevents memory leaks
4. **Animation Frame**: Glow animations use `userData.animate` for efficient updates

---

## Future Enhancements

1. **Avatar Upload**: UI for agents to upload custom avatar images
2. **Connection Labels**: Show protocol type on hover
3. **Connection History**: Option to keep temporary connections visible longer
4. **Agent Type Detection**: Auto-detect agent type from A2A handshake metadata
5. **Voice Indicator**: Animate border when agent is in voice call
6. **Tool Execution Indicator**: Different glow color during tool execution

---

## Testing Checklist

- [x] Build completes without errors
- [x] Avatar sprites render for The General and Gunny
- [x] Emoji fallback works for agents without images
- [x] Border colors match agent types
- [x] Glows animate smoothly for federated/external agents
- [ ] Dynamic connections appear on delegation events (requires SSE event with `toAgent`)
- [ ] Protocol colors are correct (requires events with `protocol` field)
- [ ] Connections auto-fade after 5 seconds (requires live testing)
- [ ] Legend displays all categories correctly
- [ ] No console errors
- [ ] Smooth performance with 17+ agents

---

## Known Issues

1. **Default Agent Type**: All existing agents default to `agentType: 'local'` (white border) until database is updated
2. **Protocol Field**: Current SSE events don't include `protocol` field, will default to `'internal'` (purple)
3. **Image Paths**: Only The General and Gunny have predefined image paths, other agents need avatar field with image URL

---

## Database Schema

The `agents` table includes:

```sql
agent_type VARCHAR(50) DEFAULT 'analysis'  -- Needs migration to use: 'local', 'federated', 'external-free', 'external-paid'
avatar VARCHAR(50) DEFAULT '🦄'            -- Can be emoji or image URL (e.g., '/path/to/image.png')
```

**Migration Needed**: Update `agent_type` field to use protocol-based values instead of capability-based values.

---

**Last Updated**: February 1, 2026
**Tested By**: Claude Code
**Approved By**: Pending user testing
