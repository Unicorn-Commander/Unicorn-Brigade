# Agent Connection Types - Visual Reference

Quick reference guide for the 4 connection types in the Orchestration 3D view.

## Connection Color Scheme

```
┌─────────────────────────────────────────────────────────────────┐
│                   Connection Type Colors                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  🟣 HIERARCHICAL (Purple)                                       │
│     Color: rgba(139, 92, 246, 0.8)  |  #c084fc                 │
│     Use: Boss → Subordinate                                     │
│     Example: The General → Team Lead → Worker                   │
│                                                                 │
│  🟡 PEER-TO-PEER (Yellow)                                       │
│     Color: rgba(251, 191, 36, 0.8)  |  #fbbf24                 │
│     Use: Colleague → Colleague                                  │
│     Example: Data Analyst → Finance Agent                       │
│                                                                 │
│  🔵 A2A PROTOCOL (Blue)                                         │
│     Color: rgba(59, 130, 246, 0.8)  |  #60a5fa                 │
│     Use: Internal → External Federated Agent                    │
│     Example: Col. Finance → External Market Data Agent          │
│                                                                 │
│  🔷 AP2 PROTOCOL (Cyan)                                         │
│     Color: rgba(6, 182, 212, 0.8)  |  #22d3ee                  │
│     Use: Internal → Paid External Service                       │
│     Example: Lt. Researcher → OpenAI API                        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Visual Flow Examples

### Hierarchical (Purple)
```
    The General
        │
        ├─> Team Lead (Finance)
        │       │
        │       ├─> Worker (Data Analyst)
        │       └─> Worker (Report Generator)
        │
        └─> Team Lead (Legal)
                │
                └─> Worker (Contract Reviewer)
```
All connections shown in **purple** with particles flowing down the hierarchy.

### Peer-to-Peer (Yellow)
```
    Worker (Data Analyst) ─────────> Worker (Finance Agent)
                "Can I get Q4 revenue data?"

    Specialist (Research) ─────────> Specialist (Legal)
                "Need legal precedent verification"
```
Connections shown in **yellow** - lateral communication between equals.

### A2A Protocol (Blue)
```
    Internal Agent ─────────> External Agent (Federated)
                    [A2A Protocol]

    Col. Finance ─────────> Partner Company's Data Agent
```
Connections shown in **blue** - external federated agent invocation.

### AP2 Protocol (Cyan)
```
    Internal Agent ─────────> Paid External Service
                    [AP2 Protocol]

    Lt. Researcher ─────────> OpenAI GPT-4 API
                              Anthropic Claude API
                              External Data Provider
```
Connections shown in **cyan** - paid external service calls.

## When to Use Each Type

| Connection Type | Relationship | Authority | Cost | Use When |
|----------------|-------------|-----------|------|----------|
| **Hierarchical** | Superior → Subordinate | Command/Delegation | Free | Task assignment, workflow orchestration |
| **Peer-to-Peer** | Colleague → Colleague | Request/Collaboration | Free | Cross-functional data requests, expertise queries |
| **A2A** | Internal → External | Federated Protocol | Free | Partner agent invocation, trusted external agents |
| **AP2** | Internal → Paid | Paid Protocol | $$ | API calls, paid data sources, premium services |

## Implementation Details

### Protocol Field Values

```python
# In backend event emission
protocol = "internal"  # Default hierarchical (purple)
protocol = "peer"      # Peer-to-peer (yellow)
protocol = "a2a"       # Agent-to-Agent (blue)
protocol = "ap2"       # Agent-to-Paid (cyan)
```

### Frontend Detection

```javascript
// frontend/src/components/WorkflowVisualization3D.jsx
if (conn.protocol === 'peer') {
  linkColor = 'rgba(251, 191, 36, 0.8)'; // Yellow
  particleColor = '#fbbf24';
} else if (conn.protocol === 'a2a') {
  linkColor = 'rgba(59, 130, 246, 0.8)'; // Blue
  particleColor = '#60a5fa';
} else if (conn.protocol === 'ap2') {
  linkColor = 'rgba(6, 182, 212, 0.8)'; // Cyan
  particleColor = '#22d3ee';
} else {
  linkColor = 'rgba(139, 92, 246, 0.4)'; // Purple (default)
  particleColor = '#c084fc';
}
```

## Legend Location

The connection type legend is located in the **bottom-left corner** of the 3D Orchestration view:

```
┌─────────────────────────────────────┐
│                                     │
│         3D Visualization            │
│                                     │
│                                     │
│  ┌──────────────────┐              │
│  │ Connection Types │              │
│  │ 🟣 Hierarchical  │              │
│  │ 🟡 Peer-to-Peer  │              │
│  │ 🔵 A2A Protocol  │              │
│  │ 🔷 AP2 Protocol  │              │
│  └──────────────────┘              │
└─────────────────────────────────────┘
```

## Activity Feed Display

Peer-to-peer invocations appear in the Activity Feed with:
- Yellow background highlight
- Yellow border
- Yellow indicator dot
- Format: `Agent A → Agent B: Purpose`

Example:
```
┌─────────────────────────────────────────┐
│          Activity Feed                  │
├─────────────────────────────────────────┤
│ 🟡 Sgt. Data → Col. Finance:            │
│    Request financial metrics            │
│    12:34:56 PM                           │
└─────────────────────────────────────────┘
```

---

**Last Updated**: February 1, 2026  
**See also**: `PEER_TO_PEER_VISUALIZATION.md`
