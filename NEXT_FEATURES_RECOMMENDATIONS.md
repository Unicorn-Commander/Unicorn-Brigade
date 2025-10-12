# 🦄 Unicorn Brigade - Next Features & Enhancements

## Current State Analysis

### ✅ What We Have (Good):

1. **Settings Page** (ProviderSettings.jsx)
   - Provider management (OpenRouter, OpenAI, Anthropic, Google, Ollama)
   - API key management with encryption
   - Default model configuration
   - Temperature & max tokens
   - Quick setup for OpenRouter
   - Test connections
   - **Score: 9/10** - Very well built!

2. **Agent Detail Page** (AgentDetail.jsx)
   - Basic configuration (model, temperature, max tokens)
   - System prompt editor
   - API key list
   - Tool display
   - **Score: 6/10** - Functional but basic

3. **Agent Builder Chat** (AgentBuilderChat.jsx)
   - Conversational agent creation
   - Session management
   - Markdown rendering
   - **Score: 7/10** - Works but no parameter control

---

## 🎯 Priority Enhancements

### Priority 1: LLM Parameter Controls (HIGH)

#### 1.1 Enhanced Agent Builder Chat

**Problem**: Users can't specify model preferences before chatting with The General.

**Solution**: Add a collapsible "Agent Preferences" panel in Builder Chat

```jsx
// Add to AgentBuilderChat.jsx
<div className="preferences-panel">
  <h3>Agent Preferences (Optional)</h3>
  <select model>
    <option>Let The General decide</option>
    <option>gpt-4-turbo</option>
    <option>claude-3.5-sonnet</option>
    <option>gemini-pro</option>
  </select>

  <input type="range" temperature (0-2) />
  <input type="number" maxTokens />

  <select domain>
    <option>Any domain</option>
    <option>Financial</option>
    <option>Legal</option>
    ...
  </select>
</div>
```

**Features**:
- Collapsible panel at top of chat
- Optional - defaults to "Let The General decide"
- Passed to backend with each message
- The General uses these as constraints
- Can be changed mid-conversation

**Implementation**: 2-3 hours

---

#### 1.2 Enhanced Agent Detail Configuration Tab

**Problem**:
- Model is text input (should be dropdown with available models)
- Missing advanced parameters
- No tool selector

**Solution**: Complete configuration interface

**Missing Parameters**:
```javascript
// Add to AgentDetail.jsx configuration tab
{
  // Existing
  model, temperature, maxTokens,

  // Add these:
  topP: 1.0,                    // Nucleus sampling
  frequencyPenalty: 0.0,        // Reduce repetition
  presencePenalty: 0.0,         // Encourage new topics
  stop: [],                     // Stop sequences

  // Provider-specific
  provider: 'openrouter',       // Which provider to use
  streaming: true,              // Enable streaming

  // Safety
  safeMode: false,              // Content filtering
  maxRetries: 3,                // Auto-retry on failure
}
```

**UI Design**:
```
Configuration Tab:

  Basic Settings:
    [x] Model: [Dropdown: gpt-4-turbo, claude-3.5-sonnet, etc.]
    [x] Provider: [Auto-select based on model]
    [x] Temperature: [Slider 0-2 with visual]
    [x] Max Tokens: [Input with presets: 2K, 4K, 8K, 16K]

  Advanced Settings (Collapsible):
    [x] Top-P (Nucleus Sampling): [Slider 0-1]
    [x] Frequency Penalty: [Slider -2 to 2]
    [x] Presence Penalty: [Slider -2 to 2]
    [x] Stop Sequences: [Tag input]

  Tool Configuration:
    [Available Tools] → [Add] → [Assigned Tools]
    - Web Search
    - File System
    - Database Query
    [+ Browse Tool Library]

  Behavior:
    [x] Enable Streaming: [Toggle]
    [x] Safe Mode: [Toggle]
    [x] Max Retries: [Number input]
```

**Implementation**: 4-5 hours

---

### Priority 2: Tool Management UI (MEDIUM)

#### 2.1 Tool Selector in Agent Detail

**Current**: Tools are displayed but can't be added/removed

**Solution**: Drag-and-drop or dual-list selector

```jsx
<div className="tool-selector">
  <div className="available-tools">
    <h4>Available Tools</h4>
    <input search />
    <div className="tool-list">
      {tools.filter(not assigned).map(tool => (
        <ToolCard
          tool={tool}
          onAdd={() => assignTool(tool)}
        />
      ))}
    </div>
  </div>

  <div className="assigned-tools">
    <h4>Assigned Tools</h4>
    <div className="tool-list">
      {agent.tools.map(tool => (
        <ToolCard
          tool={tool}
          onRemove={() => unassignTool(tool)}
          onConfigure={() => configureToolSettings(tool)}
        />
      ))}
    </div>
  </div>
</div>
```

**Features**:
- Search/filter available tools
- Preview tool details
- Configure tool-specific settings
- Reorder tools (priority)

**Implementation**: 3-4 hours

---

#### 2.2 API Key Generation (Currently Non-Functional)

**Current**: Button exists but doesn't work

**Solution**: Working API key generation modal

```jsx
<button onClick={generateApiKey}>Generate New Key</button>

// Modal:
<GenerateApiKeyModal>
  <input name="Key Name" />
  <input permissions (multiselect: read, write, invoke) />
  <input rateLimit (requests per minute) />
  <input expiresAt (date picker) />

  <button Generate />

  // On success, show once:
  <div className="key-reveal">
    <warning>⚠️ Save this key now! You won't see it again.</warning>
    <code>sk-agent-xxxxxxxxxxxxx</code>
    <button copy />
  </div>
</GenerateApiKeyModal>
```

**Implementation**: 2-3 hours

---

### Priority 3: Visual Agent Builder (OPTIONAL)

**Context**: OpenAI AgentKit has drag-and-drop canvas

**Question**: Do you want a visual builder alongside The General?

**Option A: Simple Visual Builder**
```
[Start] → [LLM] → [Tools] → [Memory] → [Output]

Drag nodes to canvas
Connect with arrows
Configure each node
Export as agent config
```

**Pros**:
- Intuitive for some users
- Good for complex workflows
- Visual representation of agent flow

**Cons**:
- Lots of development time (2-3 weeks)
- Duplicates The General's functionality
- May complicate UX

**Option B: Hybrid Approach** (RECOMMENDED)
```
Chat with The General → Generate visual representation → Edit visually if needed
```

- Start with conversation (easier)
- Generate visual flowchart of agent
- Option to edit visually
- Best of both worlds

**My Recommendation**: **Wait on this**. The conversational builder (The General) is unique and powerful. Visual builder can be added later if users request it.

---

### Priority 4: Visual Orchestration (FUTURE)

**Context**: Multi-agent workflows with visual flow

**Example**:
```
[User Query]
    ↓
[Router Agent] → Determines which agents needed
    ↓
[Parallel Execution]
├─ [Financial Agent]
├─ [Legal Agent]
└─ [Risk Agent]
    ↓
[Aggregator Agent] → Combines results
    ↓
[Response]
```

**Features**:
- Visual workflow designer
- Multi-agent coordination
- Conditional logic
- Loops and branches
- LangGraph integration

**Implementation**: 3-4 weeks (major feature)

**My Recommendation**: **Roadmap for Q2 2026**. This is a big feature that differentiates you from competitors, but foundational features should come first.

---

## 📋 Complete Implementation Checklist

### Phase 1: Essential Enhancements (1-2 weeks)

#### Week 1: LLM Parameters
- [ ] Add Agent Preferences panel to Builder Chat (3h)
- [ ] Enhance Agent Detail Configuration tab (5h)
  - [ ] Model dropdown with available models
  - [ ] Top-P slider
  - [ ] Frequency/Presence penalty sliders
  - [ ] Advanced settings collapsible section
- [ ] Backend: Update agent creation to accept all parameters (2h)
- [ ] Backend: Pass parameters to LiteLLM (1h)

#### Week 2: Tool Management
- [ ] Tool selector in Agent Detail (4h)
  - [ ] Available tools list
  - [ ] Assigned tools list
  - [ ] Add/remove functionality
  - [ ] Tool configuration modal
- [ ] API Key generation modal (3h)
  - [ ] Generate key endpoint (backend)
  - [ ] Key reveal UI
  - [ ] Copy to clipboard
- [ ] Settings enhancements (2h)
  - [ ] System-wide defaults
  - [ ] Cost tracking toggle

### Phase 2: Nice-to-Haves (1-2 weeks)

- [ ] Agent Templates
  - [ ] Pre-built agent templates by domain
  - [ ] One-click deploy templates
  - [ ] Template marketplace (future)

- [ ] Agent Testing Interface
  - [ ] Test agent with sample inputs
  - [ ] View responses
  - [ ] Debug mode

- [ ] Usage Analytics
  - [ ] Per-agent usage stats
  - [ ] Cost tracking
  - [ ] Performance metrics

### Phase 3: Advanced Features (4-6 weeks)

- [ ] Visual Orchestration
  - [ ] Multi-agent workflow designer
  - [ ] Visual canvas with nodes
  - [ ] Conditional logic
  - [ ] LangGraph integration

- [ ] MCP Integration
  - [ ] MCP server management UI
  - [ ] Discover and add MCP servers
  - [ ] Tool sync from MCP

- [ ] A2A Protocol Enhancement
  - [ ] Agent discovery UI
  - [ ] Test A2A invocations
  - [ ] Agent marketplace

---

## 🎨 Design Mockups

### Enhanced Agent Builder Chat
```
┌─────────────────────────────────────────────────────────┐
│ The General - Chief Agent Engineering Officer           │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ 🔧 Agent Preferences (Optional) ▼                   │ │
│ │                                                      │ │
│ │ Model: [Let The General decide ▼]                   │ │
│ │ Domain: [Any ▼]                                      │ │
│ │ Temperature: [───●──────] 0.7                        │ │
│ │ Max Tokens: [4096]                                   │ │
│ └─────────────────────────────────────────────────────┘ │
│                                                          │
│ [Chat messages...]                                       │
│                                                          │
│ [Type your message...]                         [Send]    │
└─────────────────────────────────────────────────────────┘
```

### Enhanced Configuration Tab
```
┌─────────────────────────────────────────────────────────┐
│ Configuration                                            │
│                                                          │
│ Basic Settings                                           │
│ ┌─────────────┬─────────────────────────────────────┐  │
│ │ Model       │ [gpt-4-turbo ▼]                     │  │
│ │ Provider    │ OpenRouter (auto-selected)          │  │
│ │ Temperature │ [────●──────] 0.7                    │  │
│ │ Max Tokens  │ [4096] [2K] [4K] [8K] [16K]         │  │
│ └─────────────┴─────────────────────────────────────┘  │
│                                                          │
│ ▼ Advanced Settings                                      │
│ ┌─────────────┬─────────────────────────────────────┐  │
│ │ Top-P       │ [──────────●] 1.0                    │  │
│ │ Freq Penalty│ [─────●─────] 0.0                    │  │
│ │ Pres Penalty│ [─────●─────] 0.0                    │  │
│ │ Stop Seq    │ [<END>] [×]                          │  │
│ └─────────────┴─────────────────────────────────────┘  │
│                                                          │
│ ▼ Tool Configuration                                     │
│ ┌──────────────────┐    ┌──────────────────┐          │
│ │ Available Tools  │    │ Assigned Tools   │          │
│ │ ──────────────── │    │ ──────────────── │          │
│ │ □ Web Search     │→   │ ☑ File System    │          │
│ │ □ Database       │    │ ☑ API Client     │          │
│ │ □ Code Executor  │←   │                  │          │
│ └──────────────────┘    └──────────────────┘          │
│                                                          │
│ [Save Changes]                            [Cancel]       │
└─────────────────────────────────────────────────────────┘
```

---

## 💭 My Recommendations

### What to Build Next (In Order):

1. **✅ YES - Enhanced Agent Builder Preferences** (3h)
   - Simple, high-impact
   - Users want control over model selection
   - Non-invasive addition

2. **✅ YES - Enhanced Agent Detail Configuration** (5h)
   - Makes agent editing more powerful
   - Missing parameters are needed
   - Better UX with dropdowns/sliders

3. **✅ YES - Tool Management UI** (4h)
   - Complete the agent building experience
   - Users need to assign tools easily
   - Visual tool selection is intuitive

4. **✅ YES - API Key Generation** (3h)
   - Button is there but broken
   - Critical for agent invocation
   - Quick win

5. **⏳ MAYBE - Agent Templates** (4h)
   - Nice-to-have
   - Can wait until you have more agents
   - Good for onboarding

6. **⏸️  LATER - Visual Builder** (2-3 weeks)
   - The General is working great
   - Can add later if requested
   - Big time investment

7. **📅 ROADMAP - Visual Orchestration** (4-6 weeks)
   - Differentiating feature
   - Multi-agent workflows
   - Q1-Q2 2026 feature

---

## 🚀 Quick Wins (This Week)

If you want immediate improvements, I recommend:

**Day 1-2**: Enhanced Agent Builder Preferences
- Add collapsible preferences panel to Builder Chat
- Model, domain, temperature, max tokens
- Pass to backend with messages

**Day 3-4**: Enhanced Configuration Tab
- Model dropdown (fetch from providers)
- Advanced parameters (top-p, penalties)
- Better visual layout

**Day 5**: Tool Management & API Keys
- Tool selector
- Working API key generation

**Total Time**: ~20 hours of focused work

---

## 🤔 Questions for You:

1. **LLM Parameters**: Do you want users to control these BEFORE talking to The General, or should The General always decide and users edit afterwards?

2. **Visual Builder**: Is this something you want, or is The General's conversational approach sufficient?

3. **Visual Orchestration**: Is multi-agent workflow orchestration important for your use case?

4. **Priority**: Which of these would give you the most value right now?
   - Agent parameter controls
   - Tool management
   - API key generation
   - Templates
   - Something else?

---

## 🎯 My Suggestion:

**Build these 3 things next** (in order):

1. **Enhanced Agent Builder Preferences** - Let users guide The General
2. **Enhanced Agent Detail Configuration** - Complete the agent editing experience
3. **Tool Management UI** - Make tool assignment visual and easy

These 3 features will make Unicorn Brigade feel complete and professional, without over-engineering or adding complexity.

**Skip for now**:
- Visual Builder (The General is unique!)
- Visual Orchestration (roadmap Q2 2026)

---

**Want me to build any of these?** I can launch subagents to implement them in parallel! Just let me know which ones you want. 🦄⚔️
