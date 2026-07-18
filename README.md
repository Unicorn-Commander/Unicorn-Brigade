<div align="center">

<img src="frontend/public/The_General_Logo.png" width="180"/>

# Unicorn Brigade

### **The AI Agent Factory**

*Build. Deploy. Orchestrate. Dominate.*

[![Python](https://img.shields.io/badge/Python-3.12-blue?style=for-the-badge&logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-teal?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18-61DAFB?style=for-the-badge&logo=react)](https://react.dev)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791?style=for-the-badge&logo=postgresql)](https://postgresql.org)

[![A2A Protocol](https://img.shields.io/badge/A2A-Protocol-green?style=for-the-badge)](https://github.com/a2aproject/A2A)
[![MCP](https://img.shields.io/badge/MCP-Anthropic-orange?style=for-the-badge)](https://modelcontextprotocol.io)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-purple?style=for-the-badge)](LICENSE)

**[Quick Start](#-quick-start)** |
**[How It Works](#-how-it-works)** |
**[Protocols](#-protocol-innovation)** |
**[API Docs](#-api-reference)** |
**[Roadmap](docs/2026-ROADMAP.md)**

---

**Production Status: 94/100** 🚀

**17 Production Agents** | **23 Working Tools** | **11 MCP Servers** | **25 Workflow Templates** | **4 Protocols** | **Voice Agents** | **Self-Correction**

</div>

---

## ⚡ What is Unicorn Brigade?

Unicorn Brigade is a production-ready orchestration platform for real-time, protocol-first multi-agent coordination. It solves three critical problems in AI agent systems: **observability** (see what agents are doing), **interoperability** (agents talk across platforms), and **cost** (route work to efficient models).

### 🎯 The Core Concept

Think of it as **Mission Control for AI Agents**:

- **The General** 🎖️ - Your AI orchestrator that commands agent operations in real-time
- **Domain Experts** - 17 specialized agents organized into military-style teams
- **3-Tier Hierarchy** - Orchestrator (Opus 4.5) → Team Leads (gpt-oss-120b) → Workers (Granite 3.3 2B) for massive cost reduction
- **Ralph Loops** - Self-correcting workflows that retry on failure with mid-execution guidance
- **Protocol-First** - Native A2A, MCP, UCP, and Agent Trace support
- **Real-Time Coordination** - SSE streaming shows you exactly what every agent is doing, live

### 🔥 This Isn't a Framework. It's a Platform.

**Frameworks require you to write code.** Unicorn Brigade gives you:
- ✅ **Pre-built agents** that work today (email, search, code execution, browser automation)
- ✅ **The General** orchestrates multi-agent operations automatically
- ✅ **11 real, npx-runnable MCP servers** (credential-gated; tools discovered at runtime)
- ✅ **Voice agents** with LiveKit WebRTC + self-hosted STT/TTS
- ✅ **3D visualization** (Three.js) shows your agent swarm in action
- ✅ **Conversation memory** (Graphiti + FalkorDB temporal knowledge graph) that agents actually remember
- ✅ **Code attribution** (Agent Trace) for compliance and auditing

### 🦄 Unicorn Commander: The Complete Platform

**Unicorn Brigade** (this repo) + **Ops-Center** (companion system) = **Unicorn Commander**

| Component | Responsibility |
|-----------|----------------|
| **Unicorn Brigade** | Agent orchestration, protocols, workflow execution, real-time coordination |
| **Ops-Center** | LLM routing, model selection, guardrails, cost optimization, usage analytics |

**How They Work Together**:

1. **Unicorn Brigade** receives commands ("Research AI market, write report, email team")
2. **The General** plans the workflow and assigns agents
3. **Ops-Center** routes LLM calls to optimal models (Claude Opus for strategy, gpt-oss-120b for workers)
4. **Guardrails** (on Ops-Center) scan inputs/outputs for safety, PII, prompt injection
5. **Agents** execute with tools, stream results via SSE
6. **Ops-Center** tracks costs, latency, and model performance

**Result**: Production-grade AI infrastructure with built-in safety, observability, and cost control.

---

## 📸 Screenshots

<div align="center">

### Dashboard - Command Center
<img src=".github/images/dashboard.png" width="800" alt="Unicorn Brigade Dashboard"/>

*Real-time agent status, active missions, and system metrics*

### Orchestration - The General in Action
<img src=".github/images/orchestration.png" width="800" alt="Real-time Orchestration"/>

*3D visualization of multi-agent coordination with SSE streaming*

### Tool Library - 23 Working Tools
<img src=".github/images/tool-library.png" width="800" alt="Tool Library"/>

*Production-ready tools with enterprise integrations*

</div>

---

## 🎬 How It Works

### The General: Your AI Orchestrator

**The General** is the central intelligence that coordinates all agent operations. It:

1. **Receives Natural Language Commands**
   ```
   "Research AI market trends, write a report, and email it to the team"
   ```

2. **Plans Multi-Agent Workflows**
   - Breaks down complex tasks into agent-specific subtasks
   - Assigns agents based on domain expertise and availability
   - Manages dependencies and parallel execution

3. **Orchestrates in Real-Time**
   - Streams live updates via Server-Sent Events (SSE)
   - Shows you tool calls, results, errors as they happen
   - Visualized in 3D with react-force-graph

4. **Self-Corrects with Ralph Loops**
   - Detects failures automatically
   - Retries with improved context
   - Allows mid-execution human guidance without restart

### Hierarchical Multi-Agent Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    THE GENERAL                          │
│              (GPT-5.2 / Claude Opus)                    │
│         "Analyze market, write report, email team"      │
└────────────────┬────────────────────────────────────────┘
                 │ Plans workflow
                 │ Delegates to domain experts
                 ▼
    ┌────────────┴────────────┬────────────────────┐
    │                         │                    │
    ▼                         ▼                    ▼
┌───────────────┐      ┌───────────────┐   ┌───────────────┐
│ TEAM LEAD     │      │ TEAM LEAD     │   │ TEAM LEAD     │
│ Research      │      │ Content       │   │ Operations    │
│ (gpt-oss-120b)│      │ (gpt-oss-120b)│   │ (gpt-oss-120b)│
└──────┬────────┘      └──────┬────────┘   └──────┬────────┘
       │                      │                    │
       │ Delegates tactical   │                    │
       │ work to workers      │                    │
       ▼                      ▼                    ▼
 ┌───────────┐         ┌───────────┐        ┌───────────┐
 │ Worker    │         │ Worker    │        │ Worker    │
 │ Web       │         │ Doc Gen   │        │ Email     │
 │ Search    │         │ (Granite  │        │ Send      │
 │ (Granite) │         │  3.3 2B)  │        │ (Granite) │
 └───────────┘         └───────────┘        └───────────┘

 **Cost Optimization**: 90% of work done by ultra-low cost API models
 **Speed**: Parallel execution across worker pool
 **Intelligence**: Strategic decisions handled by Claude Opus 4.5
```

### Example: Market Research & Email Workflow

```bash
# You send to The General:
POST /api/v1/orchestration/command
{"command": "Research AI agent market 2026 and email findings to aaron@example.com"}

# The General orchestrates:
1. Research Team Lead assigns Web Search Worker
   → Searches Google via Serper API
   → Returns: Market size $7.63B → $50B by 2030

2. Research Team Lead assigns Analysis Worker
   → Synthesizes findings into key insights
   → Returns: 3 key trends, 5 major players

3. Content Team Lead assigns Report Writer
   → Generates professional report in markdown
   → Returns: 500-word executive summary

4. Operations Team Lead assigns Email Worker
   → Sends via MS365 Graph API with OAuth2
   → Returns: Message ID, delivery confirmation

# Real-time SSE stream shows every step:
data: {"type": "agent_started", "agent": "research-web-search", "task": "..."}
data: {"type": "tool_call", "tool": "web_search", "query": "AI agent market 2026"}
data: {"type": "tool_result", "result": {"organic": [...], "market_size": "..."}}
data: {"type": "agent_completed", "agent": "research-web-search", "output": "..."}
...
```

---

## 🔗 Protocol Innovation

Unicorn Brigade implements **4 cutting-edge protocols** for agent interoperability:

### 1️⃣ A2A (Agent-to-Agent Protocol)

**Purpose**: Cross-platform agent federation and discovery

**What it does**:
- Agents publish **Agent Cards** (JSON-LD) describing capabilities
- External agents can discover and invoke your agents
- Your agents can invoke agents on other platforms
- Standardized task format: `{task, context, tools, constraints}`

**Example**:
```bash
# Discover agents with "financial_analysis" capability
GET /api/v1/a2a/discover?capability=financial_analysis

# Invoke an agent from another platform
POST /api/v1/a2a/agents/col-finance/invoke
{
  "task": "Calculate CAGR from $7.63B to $10.91B over 2 years",
  "tools": ["calculator"],
  "context": {"source": "Deloitte report"}
}

# Response includes full execution trace
{
  "status": "success",
  "result": {"output": "CAGR is 19.6% annually", "confidence": 0.95},
  "tool_calls": [{"tool": "calculator", "result": 19.58}],
  "tokens_used": 342,
  "duration_seconds": 1.2
}
```

**Why it matters**: Your agents become **API endpoints** that other AI systems can use. Build once, integrate everywhere.

### 2️⃣ MCP (Model Context Protocol)

**Purpose**: Standardized tool interface for LLMs

**What it does**:
- Tools register with schema (name, parameters, description)
- LLMs discover tools dynamically
- Function calling standardized across OpenAI, Anthropic, local models
- Resource reading (files, databases, APIs) with URI schemes

**Implementation**:
- ✅ **11 real, npx-runnable MCP servers** (declared capabilities; tools discovered at runtime)
- ✅ **Subprocess lifecycle management** (start/stop/restart)
- ✅ **JSON-RPC tool invocation** via STDIO transport
- ✅ **HTTP/SSE transport** for remote servers
- ✅ **Resource URI schemes**: `file://`, `http://`, `db://`, `mcp://`

**Example**:
```bash
# List all available MCP tools
GET /api/v1/mcp/tools
# Returns Brigade's registered tools; MCP-server tool lists are discovered at runtime.

# Invoke tool directly
POST /api/v1/mcp/tools/stripe_create_payment_intent/invoke
{
  "arguments": {
    "amount": 9900,
    "currency": "usd",
    "customer_id": "cus_123"
  }
}

# Read MCP resource
GET /api/v1/mcp/resources/file:///workspace/config.json
```

**Why it matters**: Tools built once work with **any LLM** (OpenAI, Anthropic, Gemini, local). No vendor lock-in.

### 3️⃣ UCP (Universal Commerce Protocol)

**Purpose**: Micropayment layer for agent-to-agent commerce

**What it does**:
- Creates **commerce sessions** for paid agent interactions
- Tracks token usage and charges per call
- Credit-based system with refunds
- Enables agent marketplace economics

**Example**:
```bash
# Create commerce session for paid agent
POST /api/v1/ucp/sessions
{
  "agent_id": "premium-analyst",
  "price_per_call": 0.50
}

# Check balance before call
GET /api/v1/ucp/balance
# Returns: {"credits": 10.50, "currency": "USD"}

# Call is charged automatically
POST /api/v1/a2a/agents/premium-analyst/invoke
{...}

# Session tracks usage
GET /api/v1/ucp/sessions/{session_id}
# Returns: {"calls": 3, "total_cost": 1.50, "remaining_credits": 9.00}
```

**Why it matters**: Enables **agent marketplaces** where agents can charge for premium capabilities.

### 4️⃣ Agent Trace (Code Attribution)

**Purpose**: Track which AI generated which code for compliance

**What it does**:
- Records every code generation with metadata:
  - Agent ID, model, user prompt, code hash (SHA-256)
  - File location, line numbers, timestamp
  - Token usage, generation duration
- Generates compliance reports (JSON/CSV)
- Enables code auditing and debugging

**Example**:
```bash
# Get recent code generations
GET /api/v1/trace/recent?limit=50

# Get all code by specific agent
GET /api/v1/trace/files/sgt-coder

# Generate compliance report
GET /api/v1/trace/report?format=csv&start_date=2026-01-01

# Example trace entry:
{
  "id": "trace_123",
  "agent_id": "sgt-coder",
  "model": "openai/gpt-5.2",
  "file_path": "/app/api/agents.py",
  "lines": "45-78",
  "code_hash": "a3d5f...",
  "user_prompt": "Add agent CRUD endpoints",
  "language": "python",
  "framework": "fastapi",
  "tokens_used": 1234,
  "created_at": "2026-01-31T12:34:56Z"
}
```

**Why it matters**: **Compliance-ready** for regulated industries. Know exactly which AI wrote which code, when, and why.

---

## 🛠️ 23 Production-Ready Tools

Tools are what make agents useful. Unicorn Brigade comes with 23 **working, tested tools**:

<details>
<summary><b>Built-in Tools (7)</b> - Core capabilities</summary>

| Tool | Description | Provider |
|------|-------------|----------|
| **web_search** | Google SERP results with snippets | Serper.dev API |
| **http_request** | Make HTTP requests to any API | httpx library |
| **calculator** | Safe mathematical expressions | Python eval (sandboxed) |
| **datetime** | Time manipulation, timezone conversion | Python datetime |
| **json** | Parse, validate, transform JSON | Python json |
| **memory** | Store/retrieve conversation context | Qdrant + mem0 (default) or Graphiti + FalkorDB (temporal graph) |
| **shell** | Execute shell commands safely | Docker sandbox |

</details>

<details>
<summary><b>Extended Tools (9)</b> - Business operations</summary>

| Tool | Description | Provider |
|------|-------------|----------|
| **email** | Send emails with OAuth2 authentication | MS365 Graph + Google Workspace |
| **file** | Read/write files with path validation | Local filesystem (sandboxed) |
| **code** | Execute Python code with libs | Docker + E2B hybrid sandbox |
| **text** | Extract, summarize, transform text | Python NLP libraries |
| **image** | Generate AI images | DALL-E / Stable Diffusion |
| **database** | Query SQL databases | PostgreSQL / MySQL |
| **notify** | Send notifications to channels | Slack, Discord, webhooks |
| **qrcode** | Generate QR codes | Python qrcode library |
| **agentic_rag** | RAG with document Q&A | Qdrant + LlamaIndex |

</details>

<details>
<summary><b>Advanced Tools (7)</b> - Cutting-edge capabilities</summary>

| Tool | Description | Provider |
|------|-------------|----------|
| **browser** | AI-driven browser automation | Playwright + browser-use (GPT-5.2) |
| **code_sandbox** | Isolated code execution | Docker primary + E2B fallback |
| **screenshot** | Capture webpage screenshots | Playwright |
| **pdf_extract** | Extract text from PDFs | PyPDF2 |
| **doc_generate** | Generate Word documents | python-docx |
| **data_analyze** | Data analysis pipelines | Pandas + NumPy |
| **url_preview** | Fetch page metadata | BeautifulSoup |
| **knowledge_graph** | Store facts in AI-native graph | FalkorDB |

</details>

**Example Tool Execution Flow**:
```
1. Agent receives: "Search for Tesla stock price and save to memory"
2. LLM decides to use: web_search tool
3. Tool executes: Serper API → {"price": "$234.56", "change": "+2.3%"}
4. LLM decides to use: memory tool
5. Tool executes: Qdrant stores → {"success": true, "memory_id": "mem_789"}
6. Agent returns: "Tesla is trading at $234.56, up 2.3% today. I've saved this to memory."
```

---

## 🔌 MCP Servers

Brigade ships a registry of **11 real, npx-runnable MCP servers**
(`app/mcp/registry.py`). Each is a genuinely-published package, credential-gated,
with its actual tool list discovered at runtime when the server starts:

| Server | Package / Config | Notes |
| ------ | ---------------- | ----- |
| GitHub | `GITHUB_TOKEN` | repos, issues, PRs, code search |
| Filesystem | `WORKSPACE_PATH` | read/write/list/search files |
| PostgreSQL | `DATABASE_URL` | query, list/describe tables |
| Playwright | built-in | browser navigate/click/fill/snapshot |
| Slack | `SLACK_BOT_TOKEN` | history, search, reactions |
| Memory | built-in | store/retrieve/list/delete |
| Brave Search | `BRAVE_API_KEY` | web + local search |
| Google Drive | `GOOGLE_APPLICATION_CREDENTIALS` | search/get/download files |
| Puppeteer | built-in | navigate, screenshot, click, fill |
| Stripe | `@stripe/mcp` | payments API tools |
| Notion | `@notionhq/notion-mcp-server` | Notion workspace tools |

> Add new servers only with verified-published packages. Register more via the
> MCP registry API (`POST /api/v1/mcp/registry/servers`).

See [docs/one-key-mcp.md](docs/one-key-mcp.md) to expose these over MCP to
external clients with a single key.

---

## 🔒 Security Model

**Defense-in-Depth Approach**: Multiple layers protect against tool misuse, prompt injection, and data exposure.

### Tool Isolation

- **Per-Agent Allowlists** - Agents only access explicitly assigned tools (Finance agent can't access filesystem)
- **Role-Based Access Control (RBAC)** - Admin, Operator, and Viewer roles with different permissions
- **API Key Authentication** - All API requests require valid authentication tokens

### Sandbox Boundaries

- **Code Execution** - Docker containers + E2B cloud sandbox for Python/JavaScript/TypeScript
  - Network isolation (no outbound internet unless explicitly allowed)
  - Resource limits (CPU, memory, disk)
  - Timeout enforcement
- **Shell Commands** - Execute in isolated Docker containers, not on host system
- **File Operations** - Path traversal validation on all file reads/writes

### MCP Server Security

MCP servers present unique attack surfaces (chaining risks, privilege escalation):

- **Server-Specific Authentication** - Each MCP server requires separate tokens
- **Network Isolation** - MCP servers run in separate containers
- **Tool Chaining Restrictions** - No automatic elevation (e.g., Git MCP can't invoke Filesystem MCP)
- **Audit Logging** - All MCP tool calls logged with agent ID, timestamp, arguments

### Input Validation & Guardrails

- **Prompt Injection Defense** - Input sanitization on user prompts
- **PII Detection** - Presidio scans for personally identifiable information
- **Content Safety** - Llama Guard 3 checks for harmful outputs
- **Agent Trace Auditing** - All AI-generated code tracked with SHA-256 hashes for compliance

### Roadmap (Q1 2026)

- [ ] NeMo Guardrails integration (policy-driven safety)
- [ ] LLM Guard deployment (comprehensive input/output scanning)
- [ ] Rate limiting per agent/user
- [ ] CSRF protection for web endpoints

**Note**: Security is an ongoing priority. Report vulnerabilities to security@unicorncommander.ai

---

## 🎖️ 17 Production Agents (Military Organization)

Agents are organized by **domain expertise** for efficient coordination:

| Domain | Agent | Role | Capabilities |
|--------|-------|------|--------------|
| **Command** | The General | Orchestrator | Multi-agent coordination, planning, delegation |
| **Command** | Gunny | Agent Builder | Conversational agent creation, configuration |
| **Operations** | Col. Pipeline | Workflow Manager | ETL, data pipelines, job orchestration |
| **Operations** | Sgt. Major Executor | Task Runner | Direct task execution, monitoring |
| **Operations** | Cpl. Monitor | System Observer | Health checks, metrics, alerts |
| **Research** | Dr. Analyst | Data Scientist | Statistical analysis, ML workflows |
| **Research** | Lt. Webster | Web Researcher | SERP queries, source validation |
| **Research** | Cpl. Librarian | Document Manager | RAG, indexing, retrieval |
| **Engineering** | Sgt. Coder | Code Generator | Full-stack development, refactoring |
| **Engineering** | Cpl. Debugger | Bug Hunter | Error analysis, debugging, fixes |
| **Engineering** | Pvt. Tester | QA Engineer | Test generation, validation |
| **Security** | Capt. Fortress | Security Analyst | Vulnerability scanning, compliance |
| **Security** | Sgt. Audit | Auditor | Log analysis, policy enforcement |
| **Finance** | Col. Finance | Financial Analyst | Financial modeling, forecasting |
| **Finance** | Lt. Budget | Budget Planner | Cost analysis, optimization |
| **Medical** | Dr. Vitals | Medical Analyst | Clinical documentation, diagnosis support |
| **Medical** | Nurse Navigator | Care Coordinator | Patient routing, appointment scheduling |

**Key Features**:
- ✅ Each agent has **different LLM model** (GPT-5.2, Claude Sonnet, local models)
- ✅ Each agent has **specialized tools** (Finance gets calculator, Research gets web_search)
- ✅ Each agent has **domain knowledge** baked into system prompts
- ✅ Stored in **PostgreSQL** with full CRUD, conversation history, tool assignments

---

## 🎭 25 Hierarchical Workflow Templates

**3-Tier Cost-Optimized Architecture**:

```
Tier 1: Orchestrator (Claude Opus 4.5) - $15/1M tokens
├─ Plans workflow strategy
├─ Handles complex reasoning
└─ Final quality control

Tier 2: Team Leads (gpt-oss-120b) - $0.039-0.19/1M tokens
├─ Domain expertise (Finance, Research, etc.)
├─ Tactical decisions
└─ Worker coordination

Tier 3: Workers (Granite 3.3 2B / Qwen3 VL 30B) - $0.02-0.6/1M tokens
├─ Single-purpose tasks
├─ Tool execution
└─ Data processing
```

**Result**: Designed to route 80% of tasks to ultra-low cost models (10-100× cheaper depending on provider). Model costs vary by provider and date. See [OpenRouter pricing](https://openrouter.ai/models) for current rates.

**Core Workflows (6)**:
1. Investment Due Diligence - Market analysis, financial modeling, risk assessment
2. Autonomous Sales Pipeline - Lead scoring, outreach, follow-up automation
3. Incident Response - Alert triage, log analysis, remediation
4. Content Production - Research, writing, editing, publishing
5. Legal Case Analysis - Document review, precedent research, brief generation
6. Medical Documentation Review - Chart review, diagnosis validation, coding

**Phase 1 Workflows (2)**:
7. Help Desk Triage - Ticket classification, priority assignment, routing
8. RFP Response Generation - Requirements analysis, proposal writing, budget estimation

**Professional Workflows (11)**:
9-19. Competitive Intelligence, Code Review, Data Reports, Compliance Audit, Meeting Intelligence, Contract Analysis, Literature Review, API Integration, Multi-Channel Content Distribution

**Domain Coverage**: Research, Finance, Content, Sales, DevOps, Legal, Medical, Investigation

---

## 🎙️ Voice Agents (Production-Ready WebRTC)

**Full Voice Stack** with LiveKit + self-hosted STT/TTS:

### Speech-to-Text (5 options)
- **mlx-whisper** - Apple Silicon Metal acceleration, unified memory
- **faster-whisper** - CUDA GPUs, CTranslate2, INT8 quantization, 5-10x faster
- **whisper.cpp** - CoreML / Apple Neural Engine, optimized for M-series
- **Deepgram API** - Cloud fallback, 150ms latency
- **AssemblyAI** - Cloud fallback, high accuracy

### Text-to-Speech (5 options)
- **Kokoro-82M** - CPU-friendly, 11 voices, Apache 2.0 license
- **Chatterbox** - Voice cloning from 5-10s samples, emotion control
- **Marvis** - Apple Silicon MLX native, low latency
- **CosyVoice2** - 150ms latency, multi-language, SOTA quality
- **Custom** - Load your own ONNX/PyTorch TTS models

### Voice Features
- ✅ **LiveKit WebRTC** - Sub-500ms end-to-end latency
- ✅ **Runtime configuration** - Switch providers without restart
- ✅ **Voice cloning** - Clone voices from short samples
- ✅ **Frontend components** - VoiceCallModal, VoiceCallButton ready to use
- ✅ **Multi-agent support** - Different voices per agent

**Example**:
```bash
# Create voice room
POST /api/v1/voice/rooms
{"agent_id": "the-general", "room_name": "Strategy Session"}

# Join room from frontend
const token = await fetch(`/api/v1/voice/rooms/${roomId}/token`)
// WebRTC connection auto-configured with LiveKit SDK

# Agent speaks with Kokoro TTS + listens with Whisper STT
# Full duplex conversation with tool execution
```

---

## 🔄 Ralph Self-Correction Loops

**Ralph** is the self-correcting workflow engine inspired by **open-ralph-wiggum**:

### How It Works

1. **Task Breakdown** - Workflow split into checkpointed subtasks
2. **Execution** - Each subtask executes with full error logging
3. **Failure Detection** - Automatic detection of errors, timeouts, rate limits
4. **Self-Correction** - LLM analyzes error and generates fix strategy
5. **Retry** - Task retried with improved context (up to 5 iterations)
6. **Human-in-the-Loop** - Mid-execution guidance injection without restart

### Example Ralph Loop

```bash
# Start workflow
POST /api/v1/ralph/execute
{
  "workflow": "data_pipeline",
  "steps": [
    {"task": "fetch_api_data", "endpoint": "https://api.example.com/data"},
    {"task": "transform_data", "format": "parquet"},
    {"task": "upload_to_s3", "bucket": "company-data"}
  ]
}

# Iteration 1: API call fails (rate limit)
data: {"type": "error", "step": 1, "error": "429 Too Many Requests"}
data: {"type": "self_correct", "strategy": "Add exponential backoff + retry"}

# Iteration 2: Success with backoff
data: {"type": "success", "step": 1, "data": {...}}

# Iteration 2: Transform fails (missing column)
data: {"type": "error", "step": 2, "error": "KeyError: 'user_id'"}
data: {"type": "paused", "message": "Need guidance: Which field should be user_id?"}

# Human provides guidance
POST /api/v1/ralph/executions/{id}/guidance
{"guidance": "Use 'customer_id' field as user_id"}

# Iteration 3: Success with guidance
data: {"type": "success", "step": 2, "output": "data.parquet"}
data: {"type": "success", "step": 3, "s3_uri": "s3://company-data/..."}
data: {"type": "workflow_complete", "iterations": 3, "success": true}
```

**Key Features**:
- ✅ **Automatic retry** with improved context
- ✅ **Error analysis** by LLM (GPT-5.2 analyzes failure)
- ✅ **Mid-execution guidance** without full restart
- ✅ **State persistence** (`.ralph/` directory stores checkpoints)
- ✅ **Iteration history** for debugging

---

## 🧠 Memory System (Graphiti + FalkorDB Temporal Knowledge Graph)

**Memory Architecture Options**:
- **mem0** (default) - Lightweight vector memory with Qdrant backend
- **Graphiti + FalkorDB** (advanced) - Temporal knowledge graph with entity relationships

The advanced tier replaces basic vector memory with a **temporal knowledge
graph** built on [Graphiti](https://github.com/getzep/graphiti) over a
**FalkorDB** graph backend (`app/memory/graphiti_manager.py`).

### What Makes It Special

**Traditional Memory (mem0)**:
- Vector embeddings only
- No time awareness
- No relationships
- Query: "What did user say about X?"

**Graphiti Memory**:
- Vector embeddings + **knowledge graph**
- **Temporal awareness** ("What did user prefer last month vs today?")
- **Entity relationships** ("User's favorite tool connects to their primary use case")
- **Automatic fact extraction** from conversations
- Query: "How has user's workflow evolved over time?"

### Architecture

```
┌─────────────────────────────────────────────────┐
│        Graphiti Temporal Memory                 │
├─────────────────────────────────────────────────┤
│                                                 │
│  ┌──────────────┐        ┌──────────────┐      │
│  │  Embeddings  │◄──────►│  Knowledge   │      │
│  │  (bge-m3 via │        │    Graph     │      │
│  │   gateway)   │        │  (FalkorDB)  │      │
│  └──────────────┘        └──────────────┘      │
│         │                       │               │
│         │  Hybrid Retrieval     │               │
│         └───────────┬───────────┘               │
│                     │                           │
│              ┌──────▼──────┐                    │
│              │  Facts      │                    │
│              │  Entities   │                    │
│              │  Relations  │                    │
│              │  Timeline   │                    │
│              └─────────────┘                    │
│                                                 │
└─────────────────────────────────────────────────┘
```

### Example

```bash
# Conversation 1 (January):
User: "I prefer using PostgreSQL for all my projects"
Assistant: "Noted. I'll remember your PostgreSQL preference."
# Graphiti stores:
# - Entity: "User"
# - Fact: "prefers PostgreSQL"
# - Timestamp: 2026-01-15
# - Relationship: User -[PREFERS]-> PostgreSQL

# Conversation 2 (February):
User: "Actually, I'm migrating everything to MongoDB"
Assistant: "I see you've changed from PostgreSQL to MongoDB."
# Graphiti stores:
# - Fact: "now prefers MongoDB" (2026-02-01)
# - Temporal edge: PostgreSQL preference ENDED at 2026-02-01
# - Relationship: User -[PREFERS]-> MongoDB (active)
# - Relationship: User -[USED_TO_PREFER]-> PostgreSQL (historical)

# Later query:
"What database does user prefer?"
# Returns: MongoDB (with context: "Changed from PostgreSQL on 2026-02-01")

# Historical query:
"What did user prefer in January?"
# Returns: PostgreSQL (temporal query to 2026-01-15)
```

**Why It Matters**: Agents remember **what, when, and why** - not just embeddings.

---

## 🏗️ Architecture

```
                Unicorn Brigade Platform
    ┌──────────────────────────────────────────────────────┐
    │                   THE GENERAL                         │
    │           (Real-Time Orchestrator)                    │
    │    ┌──────────────┐          ┌──────────────┐        │
    │    │   React UI   │◄────────►│   FastAPI    │        │
    │    │  + Three.js  │  SSE/HTTP│   Backend    │        │
    │    │  + @xyflow   │          │              │        │
    │    └──────────────┘          └──────┬───────┘        │
    │                                     │                │
    │         ┌───────────────────────────┼────────┐       │
    │         │                           │        │       │
    │   ┌─────▼─────┐  ┌─────────┐  ┌───▼────┐  ┌▼────┐  │
    │   │    A2A    │  │   MCP   │  │  UCP   │  │Trace│  │
    │   │ Protocol  │  │Protocol │  │Protocol│  │  🔍 │  │
    │   └───────────┘  └─────────┘  └────────┘  └─────┘  │
    │                                                      │
    │   ┌──────────────────────────────────────────────┐  │
    │   │         Agent Coordination Layer             │  │
    │   │  ┌────────┐ ┌────────┐ ┌────────┐           │  │
    │   │  │  17    │ │  11    │ │  Ralph │           │  │
    │   │  │ Agents │ │  MCP   │ │  Loop  │           │  │
    │   │  │        │ │Servers │ │ Engine │           │  │
    │   │  └────────┘ └────────┘ └────────┘           │  │
    │   └──────────────────────────────────────────────┘  │
    │                                                      │
    │   ┌──────────────────────────────────────────────┐  │
    │   │              LLM Layer                        │  │
    │   │  ┌────────┐ ┌─────────┐ ┌─────────┐          │  │
    │   │  │ Claude │ │gpt-oss  │ │ Granite │          │  │
    │   │  │Opus 4.5│ │  120b   │ │ 3.3 2B  │          │  │
    │   │  └────────┘ └─────────┘ └─────────┘          │  │
    │   └──────────────────────────────────────────────┘  │
    │                                                      │
    │   ┌───────┐  ┌───────┐  ┌────────┐  ┌────────┐    │
    │   │Postgre│  │Qdrant │  │Graphiti│  │FalkorDB│    │
    │   │  SQL  │  │Vector │  │Memory  │  │ Graph  │    │
    │   └───────┘  └───────┘  └────────┘  └────────┘    │
    │                                                      │
    │   ┌─────────┐  ┌─────────┐  ┌─────────┐            │
    │   │Langfuse │  │LiveKit  │  │  Ralph  │            │
    │   │ Trace   │  │  Voice  │  │  State  │            │
    │   └─────────┘  └─────────┘  └─────────┘            │
    └──────────────────────────────────────────────────────┘
```

### Tech Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| **Orchestration** | The General (GPT-5.2) + SSE | Real-time multi-agent coordination |
| **Frontend** | React 18, Vite 6, Tailwind 4, Three.js | 3D visualization, responsive UI |
| **Backend** | FastAPI 0.115, Python 3.12 | Async API, protocol servers |
| **Agents** | PostgreSQL 16 | Agent configs, conversation history |
| **Memory** | Graphiti + FalkorDB (advanced) or mem0 + Qdrant (default) | Temporal knowledge graph |
| **Knowledge** | FalkorDB | AI-native graph for entities/relations |
| **LLM Routing** | Ops-Center | Multi-provider routing (OpenRouter, Anthropic) |
| **Observability** | Langfuse (self-hosted) | Tracing, cost tracking, evaluation |
| **Voice** | LiveKit + self-hosted STT/TTS | WebRTC, Whisper, Kokoro |
| **Workflows** | Ralph Engine | Self-correcting execution loops |
| **Protocols** | A2A + MCP + UCP + Agent Trace | Interoperability standards |
| **Containerization** | Docker + Docker Compose | Development + deployment |

---

## 🎯 Quick Start

### Prerequisites

- **Python 3.12+**
- **PostgreSQL 16+**
- **Node.js 18+**
- **Qdrant** (vector database)
- **Redis** (optional, for caching)

### Installation

```bash
# 1. Clone repository
git clone https://git.unicorncommander.ai/UnicornCommander/Unicorn-Brigade.git
cd Unicorn-Brigade

# 2. Python environment
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env with your API keys (see Configuration section)

# 4. Initialize database
python -c "from app.db.database import init_db; import asyncio; asyncio.run(init_db())"

# 5. Start backend
uvicorn app.main:app --host 0.0.0.0 --port 8100 --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173**

### Docker Compose (Recommended)

```bash
# Start full stack
docker-compose up -d

# With all advanced features
docker-compose -f docker-compose.yml \
  -f docker-compose.langfuse.yml \
  -f docker-compose.falkordb.yml \
  -f docker-compose.livekit.yml up -d
```

---

## ⚙️ Configuration

```bash
# .env file

# Authentication
BRIGADE_ADMIN_KEY=your-64-char-hex  # Generate: openssl rand -hex 32
ENVIRONMENT=development  # development | production

# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5434/unicorn_brigade

# LLM Provider
OPS_CENTER_URL=https://unicorncommander.ai
OPENROUTER_API_KEY=sk-or-v1-000000000000000000000000000000000000
ANTHROPIC_API_KEY=sk-ant-...
UC_GATEWAY_URL=https://llm.unicorncommander.ai/v1
UC_GATEWAY_KEY=sk-shared-placeholder
UC_GATEWAY_PER_ORG_KEYS_ENABLED=false
UC_GATEWAY_ORG_KEYS_JSON='{"org-uuid":{"api_key":"sk-org-placeholder","key_alias":"org-alias","max_budget":50}}'

# Tools
SERPER_API_KEY=...  # Web search

# Email
MS365_CLIENT_ID=...
MS365_CLIENT_SECRET=...
MS365_USER_EMAIL=your@email.com

# Memory
ZEP_API_KEY=...  # From zep.cloud

# Voice
VOICE_STT_PROVIDER=mlx-whisper
VOICE_TTS_PROVIDER=kokoro

# Observability
LANGFUSE_ENABLED=true
LANGFUSE_HOST=http://localhost:3001
```

---

## 📚 API Reference

See full API docs at **http://localhost:8100/docs** (Swagger UI)

**Key Endpoints**:

```bash
# The General
POST /api/v1/orchestration/command
GET  /api/v1/orchestration/events  # SSE stream

# Agents
POST /api/v1/agents/{id}/chat
GET  /api/v1/agents

# Protocols
POST /api/v1/a2a/agents/{id}/invoke
GET  /api/v1/a2a/discover
POST /api/v1/mcp/tools/{name}/invoke
POST /api/v1/ucp/sessions

# Workflows
POST /api/v1/hierarchical/execute
POST /api/v1/ralph/execute
POST /api/v1/ralph/executions/{id}/guidance

# Voice
POST /api/v1/voice/rooms
GET  /api/v1/voice/rooms/{id}/token

# Agent Trace
GET  /api/v1/trace/recent
GET  /api/v1/trace/report?format=csv
```

---

## 📊 Comparison

| Feature | Unicorn Brigade | LangChain | CrewAI | AutoGen |
|---------|----------------|-----------|--------|---------|
| **The General** (AI Orchestrator) | ✅ Built-in | ❌ | ❌ | ❌ |
| **Pre-built Agents** | ✅ 17 production-ready | ❌ | ❌ | ❌ |
| **Real-Time Coordination** | ✅ SSE streaming | ❌ | ❌ | ❌ |
| **3D Visualization** | ✅ Three.js | ❌ | ❌ | ❌ |
| **A2A Protocol** | ✅ Full support | ❌ | ❌ | ❌ |
| **MCP Protocol** | ✅ 11 servers | ⚠️ Partial | ❌ | ❌ |
| **UCP Protocol** | ✅ Commerce layer | ❌ | ❌ | ❌ |
| **Agent Trace** | ✅ Code attribution | ❌ | ❌ | ❌ |
| **Ralph Loops** | ✅ Self-correction | ❌ | ❌ | ❌ |
| **Temporal Memory** | ✅ Graphiti + FalkorDB | ⚠️ Basic | ⚠️ Basic | ⚠️ Basic |
| **Voice Agents** | ✅ LiveKit + self-hosted | ❌ | ❌ | ❌ |
| **Hierarchical Workflows** | ✅ 3-tier cost-optimized | ❌ | ⚠️ Basic | ⚠️ Basic |
| **Per-Agent Models** | ✅ Different LLM per agent | ⚠️ Global only | ⚠️ Global only | ⚠️ Global only |

---

## 🗺️ Roadmap

See [docs/2026-ROADMAP.md](docs/2026-ROADMAP.md) for detailed roadmap.

### ✅ What's Operational Today (February 2026)

Test these features right now:

| Feature | Status | Try It |
|---------|--------|--------|
| **A2A Agent Discovery** | ✅ Live | `GET /api/v1/a2a/discover` |
| **A2A Agent Invocation** | ✅ Live | `POST /api/v1/a2a/agents/{id}/invoke` |
| **MCP Tool Registry** | ✅ Live | `GET /api/v1/mcp/tools` |
| **MCP Tool Execution** | ✅ Live | `POST /api/v1/mcp/tools/call` |
| **Ralph Self-Correction** | ✅ Live | `POST /api/v1/ralph/execute` |
| **Voice Calls (STT→LLM→TTS)** | ✅ Live | `POST /api/v1/voice/rooms` |
| **Agent Trace Export** | ✅ Live | `GET /api/v1/trace/report?format=csv` |
| **SSE Event Streaming** | ✅ Live | `GET /api/v1/orchestration/events` |
| **Hierarchical Workflows** | ✅ Live | `POST /api/v1/hierarchical/execute` |
| **The General Commands** | ✅ Live | `POST /api/v1/orchestration/command` |
| **MCP Servers** | ✅ Live | 11 real npx-runnable servers in the registry |
| **Guardrails** | 🚧 Q1 2026 | On Ops-Center (NeMo + LLM Guard) |

### ✅ Completed (January 2026)
- The General real-time orchestration
- 4 protocols (A2A, MCP, UCP, Agent Trace)
- 11 real npx-runnable MCP servers
- Ralph self-correction loops
- Graphiti + FalkorDB temporal memory
- LiveKit voice agents
- 3-tier hierarchical workflows
- Visual workflow builder

### ⏳ Q1 2026
- [ ] NeMo Guardrails (prompt injection, PII detection)
- [ ] Security hardening (rate limiting, CSRF)
- [ ] Test coverage >60%
- [ ] Performance optimization

### ⏳ Q2 2026
- [ ] LiteLLM gateway (model routing)
- [ ] Kubernetes deployment
- [ ] Auto-scaling
- [ ] A2UI protocol (UI components in responses)

---

## 🤝 Contributing

```bash
pip install -r requirements.txt
ruff check .
python -m pytest
```

PRs welcome! See [CONTRIBUTING.md](CONTRIBUTING.md)

---

## 📄 License

Apache License 2.0 - see [LICENSE](LICENSE)

---

## 💬 Support

- **Documentation**: [docs/](docs/) · [Getting Started](docs/GETTING_STARTED.md)
- **Consumer / partner docs**: [One-Key MCP](docs/one-key-mcp.md) · [OpenAI-Compatible API](docs/openai-compat.md) · [Self-Host SSO](docs/self-host-sso.md)
- **Security**: [SECURITY.md](SECURITY.md) · report privately to security@unicorncommander.ai
- **Contributing**: [CONTRIBUTING.md](CONTRIBUTING.md)
- **Roadmap**: [docs/2026-ROADMAP.md](docs/2026-ROADMAP.md)
- **Issues**: [Forgejo Issues](https://git.unicorncommander.ai/UnicornCommander/Unicorn-Brigade/issues)
- **Email**: support@magicunicorn.tech

---

<div align="center">

### Built by [Magic Unicorn Unconventional Technology & Stuff Inc](https://magicunicorn.tech)

*"Where AI agents come to life"*

**Production Status: 94/100** 🚀

**17 Agents** | **23 Tools** | **11 MCP Servers** | **4 Protocols** | **Voice** | **Self-Correction** | **Real-Time Orchestration**

Last Updated: February 1, 2026

</div>
