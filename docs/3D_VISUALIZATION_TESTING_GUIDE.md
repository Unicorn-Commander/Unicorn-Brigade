# 3D Visualization Testing Guide

## Quick Start

### 1. Start the Development Server

```bash
# Terminal 1: Backend
cd /Volumes/Studio\ Storage/Development/Unicorn-Brigade
source venv/bin/activate
uvicorn app.main:app --reload --port 8100

# Terminal 2: Frontend
cd frontend
npm run dev
```

### 2. Navigate to Orchestration Page

Open browser: `http://localhost:5173/orchestration`

---

## Visual Testing Checklist

### Avatar Rendering

#### Expected Results

Use `paid` for new events. The frontend accepts `ap2` as a legacy alias so
replayed stored or streamed events keep the same rendering; Brigade does not
implement Google's AP2 Agent Payments Protocol.

1. **The General**
   - Should show `/The_General_Logo.png` image
   - White border (local agent type)
   - No glow effect

2. **Gunny**
   - Should show `/Gunny_Logo.png` image
   - White border (local agent type)
   - No glow effect

3. **Other Agents**
   - Should show emoji avatar (🦄, 💰, ⚖️, etc.)
   - Colored circle background based on domain
   - White border (all currently default to local)

#### How to Test

1. Open browser DevTools (F12)
2. Check Console for warnings:
   - ✅ No "Failed to load avatar" errors for The General/Gunny
   - ⚠️ May see warnings for other agents if no image path
3. Zoom in on nodes (scroll wheel) to see avatar details
4. Click on nodes to see agent info panel

---

### Agent Type Borders

#### Current State

All agents default to `agentType: 'local'` (white border, no glow) because the database uses `agent_type` for capability classification, not protocol classification.

#### Future State (After DB Migration)

| Agent Type | Visual | How to Create |
|------------|--------|---------------|
| Local | White border, no glow | Default for internal agents |
| Federated | Blue border, pulsing glow | Set `agent_type = 'federated'` in DB |
| External (Free) | Green border, pulsing glow | Set `agent_type = 'external-free'` in DB |
| External (Paid) | Gold border, pulsing glow | Set `agent_type = 'external-paid'` in DB |

#### Manual Testing

To test different agent types, update the database:

```sql
-- Connect to database
psql -h localhost -p 5434 -U leads_user -d unicorn_brigade

-- Update an agent to federated type
UPDATE agents SET agent_type = 'federated' WHERE id = 'the-general';

-- Update to external-free
UPDATE agents SET agent_type = 'external-free' WHERE id = 'gunny';

-- Update to external-paid
UPDATE agents SET agent_type = 'external-paid' WHERE id = 'col-finance';

-- Refresh the page to see changes
```

---

### Dynamic Connections

#### Current State

SSE events from `OrchestrationEventBus` don't currently include `data.toAgent` field, so dynamic connections won't appear yet.

#### How to Enable

Update `app/orchestration/event_bus.py` to include target agent:

```python
# Example: When an agent delegates to another agent
await event_bus.publish(OrchestrationEvent(
    type=EventType.AGENT_DELEGATION,
    agent_id="the-general",
    agent_name="The General",
    data={
        "toAgent": "col-finance",  # ADD THIS
        "protocol": "a2a",         # ADD THIS (optional, defaults to 'internal')
    },
))
```

#### Testing Dynamic Connections

1. **Method 1: Use Browser DevTools to Simulate**

```javascript
// Open browser console on Orchestration page
// Manually trigger a test event
window.dispatchEvent(new CustomEvent('test-delegation', {
  detail: {
    id: 'test-1',
    type: 'agent_delegation',
    agentId: 'the-general',
    data: {
      toAgent: 'col-finance',
      protocol: 'a2a'
    }
  }
}));
```

2. **Method 2: Chat with Agent**

```bash
# Send a chat message that might trigger delegation
curl -X POST http://localhost:8100/api/v1/agents/the-general/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Delegate a task to Col. Finance to analyze Q4 earnings"}'
```

3. **Watch for**:
   - New connection appears between agents
   - Connection color matches protocol (purple/blue/cyan)
   - Faster particle animation (4 particles instead of 2)
   - Connection fades after 5 seconds

---

### Protocol Colors

#### Expected Results

| Protocol | Connection Color | Particle Color | How to Trigger |
|----------|-----------------|----------------|----------------|
| Internal | Purple (rgba 139,92,246) | Light purple (#c084fc) | Default for agent-to-agent |
| A2A | Blue (rgba 59,130,246) | Light blue (#60a5fa) | Set `protocol: 'a2a'` in event |
| paid (external API) | Cyan (rgba 6,182,212) | Light cyan (#22d3ee) | Set `protocol: 'paid'` in event |

#### Testing

1. Modify `app/api/orchestration_routes.py` to emit test events:

```python
@router.post("/orchestration/test-connection")
async def test_connection(protocol: str = "internal"):
    """Test endpoint for dynamic connections"""
    await event_bus.publish(OrchestrationEvent(
        type=EventType.AGENT_DELEGATION,
        agent_id="the-general",
        agent_name="The General",
        data={
            "toAgent": "col-finance",
            "protocol": protocol,  # 'internal', 'a2a', or 'paid'
        },
    ))
    return {"status": "ok"}
```

2. Test each protocol:

```bash
# Internal (purple)
curl -X POST "http://localhost:8100/api/v1/orchestration/test-connection?protocol=internal"

# A2A (blue)
curl -X POST "http://localhost:8100/api/v1/orchestration/test-connection?protocol=a2a"

# Paid external API (cyan)
curl -X POST "http://localhost:8100/api/v1/orchestration/test-connection?protocol=paid"

# Legacy event replay alias (also renders as paid)
curl -X POST "http://localhost:8100/api/v1/orchestration/test-connection?protocol=ap2"
```

---

### Legend Verification

**Location**: Bottom-left corner of visualization

#### Check List

1. **Domains Section**
   - Shows 6 domain colors
   - Labels: Financial, Legal, Medical, Technology, Intelligence, Investigation

2. **Protocols Section**
   - Shows 3 line colors
   - Labels: Internal (purple), A2A (blue), paid (external API) (cyan)

3. **Agent Types Section**
   - Shows 4 border styles
   - Labels: Local, Federated, External (Free), External (Paid)
   - Visual indicators match the agent border styles

---

## Performance Testing

### Metrics to Monitor

1. **Initial Render**: Should load within 2 seconds
2. **FPS**: Should maintain 50+ FPS during rotation
3. **Memory**: Check DevTools Memory tab, should stay under 200MB
4. **Animation Smoothness**: Glow animations should be smooth, not choppy

### Stress Testing

```bash
# Add more agents to test performance
# Create 50 test agents
for i in {1..50}; do
  curl -X POST http://localhost:8100/api/v1/agents \
    -H "Content-Type: application/json" \
    -d "{\"id\": \"test-agent-$i\", \"name\": \"Test Agent $i\", \"avatar\": \"🤖\"}"
done

# Refresh page and check:
# - All 50+ agents render
# - FPS stays above 30
# - No console errors
```

---

## Browser Compatibility

### Tested Browsers

- ✅ Chrome 120+ (Recommended)
- ✅ Firefox 121+
- ✅ Safari 17+
- ✅ Edge 120+

### Known Issues

- Safari < 16: WebGL warnings (non-critical)
- Firefox: Glow animation slightly less smooth

---

## Troubleshooting

### Issue: Avatars Not Showing

**Symptoms**: Agents render as blank or broken images

**Solutions**:
1. Check image files exist:
   ```bash
   ls -la frontend/public/*.png
   ```
2. Check browser console for 404 errors
3. Verify image paths start with `/` not `./`
4. Clear browser cache (Cmd+Shift+R / Ctrl+Shift+F5)

### Issue: Connections Not Appearing

**Symptoms**: No lines between agents

**Solutions**:
1. Check `connections` prop has data:
   ```javascript
   console.log(graphData.links);
   ```
2. Verify agents exist in `agents` array
3. Check `source` and `target` IDs match agent IDs

### Issue: Glows Not Animating

**Symptoms**: Borders visible but no pulsing effect

**Solutions**:
1. Check `agent_type` field in database
2. Verify `agentType` is not `'local'`
3. Check browser DevTools for WebGL errors

### Issue: Performance Lag

**Symptoms**: Choppy animation, low FPS

**Solutions**:
1. Reduce particle count:
   ```javascript
   linkDirectionalParticles={1}  // Instead of 2/4
   ```
2. Disable glow animations for all agents
3. Reduce number of connections shown
4. Use 2D mode instead of 3D (toggle button)

---

## Testing Workflow

### Recommended Order

1. ✅ **Static Elements First**
   - Avatar rendering (The General, Gunny, others)
   - Border colors
   - Legend display

2. ✅ **Database Updates**
   - Change agent types to test borders/glows
   - Upload custom avatar images

3. ⏳ **Dynamic Features**
   - Modify SSE events to include `toAgent`
   - Test connection auto-fade
   - Test protocol colors

4. ⏳ **Integration Testing**
   - Chat with agents to trigger real delegations
   - Monitor SSE stream in DevTools Network tab
   - Verify connections appear automatically

---

## Success Criteria

### Minimum Viable

- [x] Avatars render without errors
- [x] The General and Gunny show logo images
- [x] Other agents show emoji avatars
- [x] Legend displays correctly
- [x] No console errors on load

### Full Feature Set

- [ ] Agent type borders/glows work (requires DB migration)
- [ ] Dynamic connections appear on events (requires SSE event updates)
- [ ] Protocol colors are correct (requires protocol field in events)
- [ ] Connections auto-fade after 5 seconds
- [ ] Smooth animation at 50+ FPS with 17 agents

---

**Last Updated**: February 1, 2026
**Status**: Static features complete, dynamic features pending backend integration
