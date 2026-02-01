# Quick Start: Peer-to-Peer Visualization

## What Was Added

Yellow connections in the 3D Orchestration view for peer-to-peer agent communication (colleague → colleague).

## See It In Action

1. **Start backend**:
   ```bash
   uvicorn app.main:app --reload --port 8100
   ```

2. **Start frontend**:
   ```bash
   cd frontend && npm run dev
   ```

3. **Open Orchestration**:
   ```
   http://localhost:5173/orchestration
   ```

4. **Trigger test events**:
   ```bash
   python scripts/test_peer_visualization.py
   ```

5. **Expected Result**:
   - 🟡 Yellow connections appear between agents
   - Activity feed shows yellow-highlighted peer invocations
   - Connections auto-fade after 5 seconds
   - Legend shows: Hierarchical, Peer-to-Peer, A2A, AP2

## Color Scheme

| Color | Type | Example |
|-------|------|---------|
| 🟣 Purple | Hierarchical | Boss → Subordinate |
| 🟡 Yellow | **Peer-to-Peer** | Colleague → Colleague |
| 🔵 Blue | A2A Protocol | Internal → External |
| 🔷 Cyan | AP2 Protocol | Internal → Paid API |

## Files Changed

- `frontend/src/pages/Orchestration.jsx` - Event handling + activity feed
- `frontend/src/components/WorkflowVisualization3D.jsx` - 3D rendering + legend

## Docs

- `docs/PEER_TO_PEER_VISUALIZATION.md` - Full documentation
- `docs/CONNECTION_TYPES_REFERENCE.md` - Visual reference
- `PEER_TO_PEER_SUMMARY.txt` - Implementation summary

## Build Status

✅ **PASSING** (npm run build succeeds in 6.5s)

---

**Quick Test**: Run `python scripts/test_peer_visualization.py` and watch for yellow connections!
