# Orchestration Demo - Visual Flow Diagram

## Demo Page Layout

```
┌─────────────────────────────────────────────────────────────────┐
│ 🦄 Unicorn Brigade - Live Orchestration Demo                   │
│ Showcasing 1,500 agents executing workflows in real-time       │
│                                                                 │
│ [⏸️ Pause]  [🔄 Reset]  [⛶ Fullscreen]                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│ Scene 3 of 6: Cybersecurity Incident Response                  │
│ [━━━━][━━━━][████][━━━━][━━━━][━━━━]  Auto-playing • 7s/scene │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐               │
│ │  1500   │ │    1    │ │   30    │ │   45    │               │
│ │ Agents  │ │Workflow │ │ Active  │ │  Links  │               │
│ └─────────┘ └─────────┘ └─────────┘ └─────────┘               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│                   ┌────────────────────────┐                   │
│                   │   3D VISUALIZATION     │                   │
│          ⭐       │                        │                   │
│     The General   │   🔒  🔒  🔒  🔒       │                   │
│          │        │    ╲  │  ╱  │          │                   │
│          │        │     ╲ │ ╱   │          │                   │
│     ┌────┴────┐   │      ●●●   ●●●         │                   │
│     │ 💰 ⚖️ 🔒│   │     Workers             │                   │
│     │ 💻 🔍 📊│   │   (Purple Links)        │                   │
│     └─────────┘   │                        │                   │
│   Domain Leaders  └────────────────────────┘                   │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐            │
│ │  Scene 1     │ │  Scene 2     │ │🟢 Scene 3    │            │
│ │  Market      │ │  Financial   │ │  Cyber       │            │
│ │  Research    │ │  Analysis    │ │  Security    │            │
│ │              │ │              │ │              │            │
│ │  5→20        │ │  8→25        │ │  10→30       │            │
│ │  Hierarchical│ │  Hierarchical│ │  Hierarchical│            │
│ └──────────────┘ └──────────────┘ └──────────────┘            │
└─────────────────────────────────────────────────────────────────┘
```

## Agent Spatial Distribution

```
                    Top View of 3D Space
                         (z-axis)
                            ↑
                            │
        💻 Tech (150°)      │      🔍 Intel (30°)
          ●●●●●             │         ●●●●●
           ●●●              │          ●●●
                            │
    📊 Research ───●●●●●────⭐────●●●●●─── 💰 Finance
      (180°)        ●●●     │     ●●●      (0°)
                            │
                        ●●●│●●●
                       ●●● │ ●●●
                      🔒   │   ⚖️
                   Cyber   │  Legal
                  (210°)   │  (330°)

    Legend:
    ⭐ = The General (center: 0,0,0)
    ●●● = Agent clusters (50-100 agents per domain)
    Agents positioned in circles around leaders
    Z-axis adds depth variation (-50 to +50)
```

## Workflow Execution Timeline

```
Scene: Cybersecurity Incident Response (7 seconds)

0.0s  │ ⭐ The General
      │  └─ Activates (green highlight)
      │  └─ Camera zooms to Cybersecurity cluster
      │
1.0s  │ ⭐ → 🔒 🔒 🔒 ... (10 team leads)
      │  └─ Purple connections appear
      │  └─ Team leads activate
      │
2.5s  │ 🔒 → ●●● (workers)
      │  └─ Purple connections to 30 workers
      │  └─ Workers activate
      │  └─ Peak visual activity ✨
      │
5.5s  │ Connections fade
      │  └─ Purple lines become transparent
      │  └─ Particle effects stop
      │
6.5s  │ Agents return to idle
      │  └─ Green highlights disappear
      │  └─ Scene complete
      │
7.0s  │ Scene transitions
      │  └─ Camera pans to next domain
      │  └─ Next scenario begins
```

## Connection Types

### Hierarchical (Purple)
```
    Orchestrator
         │
         │ ═══════════════ (purple, 80% opacity)
         │ ▶▶▶▶▶▶▶▶▶     (particles flowing down)
         ▼
    Team Lead
         │
         │ ═══════════════ (purple, 60% opacity)
         │ ▶▶▶▶▶▶▶▶▶
         ▼
    Worker
```

### Peer-to-Peer (Yellow)
```
    Team Lead A ◀═══════▶ Team Lead B
                 (yellow, 80% opacity)
                 ◀▶◀▶◀▶  (bidirectional particles)

    Used in Multi-Domain Coordination (Scene 6)
```

## Agent Type Visual Indicators

```
┌─────────────────────────────────────────────────────────────┐
│                    Agent Rendering                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Local Agent:              Federated Agent:                 │
│  ┌─────────┐               ┌─────────┐                     │
│  │   💰    │               │   💰    │                     │
│  │         │               │         │                     │
│  └─────────┘               └─────────┘                     │
│   white border             blue border + glow              │
│   (60% of agents)          (25% of agents)                 │
│                                                             │
│  External Free:            External Paid:                   │
│  ┌─────────┐               ┌─────────┐                     │
│  │   💰    │               │   💰    │                     │
│  │         │               │         │                     │
│  └─────────┘               └─────────┘                     │
│   green border + glow      gold border + glow              │
│   (10% of agents)          (5% of agents)                  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Camera Movement Pattern

```
Scene 1: Market Research
├─ Initial: (0, 0, 500) → (0, 0, 0)
└─ Zoom to: (research_x+250, research_y+150, research_z+200)

Scene 2: Financial Analysis
├─ Pan from: Research cluster
└─ Zoom to: (finance_x+250, finance_y+150, finance_z+200)

Scene 3: Cybersecurity
├─ Pan from: Finance cluster
└─ Zoom to: (cyber_x+250, cyber_y+150, cyber_z+200)

Scene 4: Legal Review
├─ Pan from: Cybersecurity cluster
└─ Zoom to: (legal_x+250, legal_y+150, legal_z+200)

Scene 5: Medical Diagnosis
├─ Pan from: Legal cluster
└─ Zoom to: (medical_x+250, medical_y+150, medical_z+200)

Scene 6: Multi-Domain (Grand Finale)
├─ Pull back from: Medical cluster
└─ Overview: (0, 500, 600) → (0, 0, 0)
    └─ Shows entire network
    └─ Yellow peer connections everywhere
    └─ All domains active simultaneously
```

## Performance Budget

```
┌─────────────────────────────────────────────────────┐
│ Performance Target: 60 FPS (16.67ms per frame)      │
├─────────────────────────────────────────────────────┤
│                                                     │
│ Node Rendering:        ~8ms  (1500 sprites)        │
│ Link Rendering:        ~3ms  (50-100 connections)  │
│ Particle Animation:    ~2ms  (200-400 particles)   │
│ Camera Movement:       ~1ms  (smooth transitions)  │
│ State Updates:         ~1ms  (React re-renders)    │
│ Force Simulation:      ~1ms  (physics engine)      │
│                       ─────                         │
│ Total Frame Time:     ~16ms  ✅ Within budget      │
│                                                     │
│ Optimization Techniques:                            │
│ • Memoized agent generation                        │
│ • Batched state updates                            │
│ • Timeout cleanup (no memory leaks)                │
│ • Limited active connections (<100)                │
│ • Temporary connection auto-fade (5s)              │
│                                                     │
└─────────────────────────────────────────────────────┘
```

## State Management Flow

```
┌──────────────────────────────────────────────────────────┐
│                   Component State                        │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  agents (1500) ─────────┐                               │
│                         │                               │
│                         ▼                               │
│  currentScene (0-5) ───▶ executeWorkflow()             │
│                         │                               │
│                         ▼                               │
│                    ┌─────────┐                          │
│                    │ Stage 1 │ Activate orchestrator    │
│                    └────┬────┘                          │
│                         │ +1s                           │
│                    ┌────▼────┐                          │
│                    │ Stage 2 │ Delegate to leads       │
│                    └────┬────┘                          │
│                         │ +1.5s                         │
│                    ┌────▼────┐                          │
│                    │ Stage 3 │ Assign to workers       │
│                    └────┬────┘                          │
│                         │ +3s                           │
│                    ┌────▼────┐                          │
│                    │ Stage 4 │ Fade & cleanup          │
│                    └─────────┘                          │
│                         │                               │
│                         ▼                               │
│  connections[] ◀────────┴───────┐                       │
│  activeAgents[] ◀───────────────┤                       │
│                                 │                       │
│  isPlaying ────────────────────▶ Auto-advance           │
│                                 │                       │
│                                 ▼                       │
│                         currentScene++                  │
│                         (loop to 0)                     │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

## Use Case Scenarios

### 1. Conference Presentation
```
Before:
├─ Open /orchestration/demo
├─ Wait for agents to load (3s)
└─ Click fullscreen

During:
├─ Let auto-play run
├─ Pause on interesting scenes
├─ Explain workflow patterns
└─ Point out domain clusters

After:
├─ Press ESC to exit fullscreen
├─ Click Reset
└─ Close tab
```

### 2. Background Display
```
Setup:
├─ Open /orchestration/demo
├─ Click fullscreen
├─ Reduce browser zoom to 75%
└─ Leave running

Monitor:
├─ Check every hour
├─ Refresh if memory > 2GB
└─ Restart if FPS < 30
```

### 3. Sales Demo
```
Preparation:
├─ Pre-load page 1 minute early
├─ Test audio/video setup
└─ Bookmark scene 6 (multi-domain)

Presentation:
├─ Start with scene 1 (simple)
├─ Progress through scenarios
├─ Jump to scene 6 (impressive finale)
├─ Pause and discuss scale
└─ Reset for questions
```

## Troubleshooting Flowchart

```
                   ┌──────────────┐
                   │ Demo not     │
                   │ working?     │
                   └──────┬───────┘
                          │
        ┌─────────────────┼─────────────────┐
        │                 │                 │
   ┌────▼────┐      ┌─────▼─────┐    ┌─────▼─────┐
   │ Agents  │      │ Connections│    │  Camera   │
   │ missing?│      │ not shown? │    │  stuck?   │
   └────┬────┘      └─────┬──────┘    └─────┬─────┘
        │                 │                  │
   ┌────▼────┐      ┌─────▼──────┐    ┌─────▼─────┐
   │ Check   │      │ Check      │    │ Check     │
   │ console │      │ activeAgents│   │ fgRef     │
   │ errors  │      │ state      │    │ current   │
   └────┬────┘      └─────┬──────┘    └─────┬─────┘
        │                 │                  │
   ┌────▼────┐      ┌─────▼──────┐    ┌─────▼─────┐
   │ Refresh │      │ Click      │    │ Click     │
   │ page    │      │ Reset      │    │ Reset     │
   └─────────┘      └────────────┘    └───────────┘
```

---

**Visual Reference**: This diagram shows the complete flow, layout, and interaction patterns of the Orchestration Demo page.

**Last Updated**: February 1, 2026
