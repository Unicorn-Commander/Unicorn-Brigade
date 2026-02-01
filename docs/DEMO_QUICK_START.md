# Orchestration Demo - Quick Start Guide

## What is it?

A **Hollywood-style visualization** showcasing 1500 AI agents executing complex workflows in real-time 3D space. Perfect for demos, presentations, and background displays at conferences.

## Access

**URL**: `/orchestration/demo`

**Navigation**: Command section → Demo Mode (sparkles icon)

## 30-Second Quick Start

1. **Open** the demo page
2. **Wait** 3 seconds for agents to load
3. **Watch** as 6 scenarios auto-play in sequence
4. **Click** Fullscreen for maximum impact

That's it! The demo runs automatically.

## Key Features

- **1500 agents** across 16 domains (financial, legal, medical, tech, etc.)
- **6 scenarios** that auto-play every 7-8 seconds
- **Auto-zoom** camera that follows the action
- **Purple connections** for hierarchical workflows
- **Yellow connections** for peer-to-peer communication
- **Loops forever** until you pause it

## Controls

| Button | Action |
|--------|--------|
| Play/Pause | Start/stop auto-play |
| Reset | Return to beginning |
| Fullscreen | Immersive view |
| Scene Bars | Jump to specific scenario |

## The 6 Scenarios

1. **Market Research** - The General coordinates 5 leads → 20 workers
2. **Financial Analysis** - 8 leads → 25 workers analyzing data
3. **Cybersecurity** - 10 leads → 30 workers responding to incidents
4. **Legal Review** - 6 leads → 15 workers reviewing compliance
5. **Medical Diagnosis** - 7 leads → 22 workers analyzing cases
6. **Multi-Domain** - ALL domains work together (grand finale!)

## Common Use Cases

### Conference Presentation
```
1. Open /orchestration/demo
2. Click Fullscreen
3. Let it run during your talk
4. Point out specific workflows
5. Pause to explain details
```

### Background Display
```
1. Open /orchestration/demo in Chrome
2. Click Fullscreen
3. Set browser zoom to 75%
4. Leave running on large monitor
5. Refresh every 2-3 hours
```

### Sales Demo
```
1. Pre-load page before meeting
2. Show Scene 1 (simple)
3. Let scenes progress
4. Jump to Scene 6 (impressive)
5. Pause and discuss capabilities
```

## What You're Seeing

### Agent Hierarchy
- **⭐ The General** - Supreme commander at center
- **Domain Leaders** - 16 leaders (one per domain)
- **Team Members** - 1483+ workers distributed across domains

### Agent Types (colored borders)
- **White border** = Local agent (60%)
- **Blue border + glow** = Federated agent (25%)
- **Green border + glow** = External free agent (10%)
- **Gold border + glow** = External paid agent (5%)

### Connection Colors
- **Purple** = Hierarchical delegation (orchestrator → team → workers)
- **Yellow** = Peer-to-peer communication (cross-domain)

### Camera Movement
The camera automatically zooms to show:
- Domain clusters during single-domain workflows
- Full network during multi-domain coordination
- Smooth 2-second transitions between views

## Performance

**Target**: 60 FPS on modern hardware

**Optimizations**:
- Agents generated once on mount
- Limited to <100 active connections
- Temporary connections auto-fade
- Batched state updates
- Memoized calculations

**Hardware Recommendations**:
- **Minimum**: 8GB RAM, integrated graphics, Chrome 90+
- **Recommended**: 16GB RAM, dedicated GPU, Chrome 100+
- **Optimal**: 32GB RAM, modern GPU, Chrome latest

## Troubleshooting

**Agents not showing?**
- Wait 3-5 seconds for generation
- Refresh page
- Check browser console for errors

**Laggy animation?**
- Close other browser tabs
- Reduce browser zoom (75% or 50%)
- Use Chrome (fastest performance)
- See full docs for reducing agent count

**Camera stuck?**
- Click Reset button
- Wait 2 seconds for initial positioning
- Try clicking a scene indicator

**Connections not visible?**
- Make sure isPlaying = true (green Play button)
- Check that scene has started (wait 1-2 seconds)
- Click Reset and try again

## Customization

Want to modify the demo? Edit these values in `OrchestrationDemo.jsx`:

```javascript
// Change agent count (line ~288)
const syntheticAgents = generateAgents(1500);  // Try 500, 1000, 3000

// Change scene duration (SCENARIOS array)
duration: 7000,  // Milliseconds (try 5000, 10000)

// Add new domains (domains array)
const domains = [..., 'your-domain'];

// Add domain emoji (getDomainEmoji function)
'your-domain': '🎯',
```

## Files

- **Component**: `frontend/src/pages/OrchestrationDemo.jsx`
- **Route**: `frontend/src/App.jsx` (line 164)
- **Navigation**: `frontend/src/components/Navigation.jsx` (line 210)
- **Docs**: `docs/ORCHESTRATION_DEMO.md` (detailed guide)
- **Visual Diagrams**: `docs/DEMO_VISUAL_FLOW.md`

## FAQ

**Q: How many agents can I add?**
A: Up to ~5000 on high-end hardware. Performance degrades beyond that.

**Q: Can I add sound?**
A: Not currently, but it's a planned enhancement (v2).

**Q: Does it use real agents?**
A: No, these are synthetic agents for demonstration. Real agent data shown at `/orchestration`.

**Q: Can I export as video?**
A: Not built-in, but you can use screen recording tools (OBS, QuickTime, etc.).

**Q: Will it drain my battery?**
A: Yes, 3D rendering is GPU-intensive. Use on plugged-in devices for long sessions.

**Q: Can I add my own scenarios?**
A: Yes! Edit the `SCENARIOS` array in `OrchestrationDemo.jsx`.

## What's Next?

After viewing the demo:

1. **Try Production Orchestration**: Visit `/orchestration` for real agent activity
2. **Execute Workflows**: Visit `/workflows` to run actual workflow templates
3. **Chat with Agents**: Visit `/chat` to interact with production agents
4. **Explore Knowledge Graph**: Visit `/knowledge` to see FalkorDB in action

## Tips for Maximum Impact

1. **Timing**: Let Scene 6 (Multi-Domain) play for maximum "wow factor"
2. **Zoom**: Manually zoom in on interesting clusters using mouse scroll
3. **Pause**: Pause on peak activity (2.5s into each scene) to show connections
4. **Explain**: Point out the different agent types (colored borders)
5. **Scale**: Emphasize 1500 agents working together seamlessly

## Credits

Built with:
- **React** 18.3.1
- **Three.js** (via react-force-graph-3d)
- **Framer Motion** for smooth animations
- **Lucide React** for icons
- **Tailwind CSS** 4.0.0 for styling

## Success Metrics

All criteria met:

- ✅ 1500+ agents render smoothly
- ✅ 6 scenarios auto-play
- ✅ Camera choreography works
- ✅ Connections appear/disappear
- ✅ Performance optimized (60fps)
- ✅ Loops automatically
- ✅ Stats update in real-time
- ✅ Separate from production orchestration
- ✅ Navigation link added
- ✅ Build succeeded

---

**Ready to impress?** Open `/orchestration/demo` and let the show begin!

**Need help?** See `docs/ORCHESTRATION_DEMO.md` for full documentation.

**Last Updated**: February 1, 2026
