# Unicorn Brigade - Claude Code Context

## Project Overview

**Unicorn Brigade** is the AI Agent Factory - a production-ready platform for building, deploying, and orchestrating AI agents with real-world tool integrations.

**Key Capabilities:**
- Build agents through conversation with Gunny or via API
- 17 production agents across 12 domains
- 23 working tools (web search, email, calculator, memory, browser automation, code sandbox, etc.)
- A2A and MCP protocol support for agent federation
- 3D orchestration visualization with The General
- Visual workflow builder with interactive diagrams
- 11 pre-configured MCP servers (real, npm-runnable, credential-gated; tools discovered at runtime), 25 hierarchical workflows

---

## CURRENT STATUS: January 2026

### Working Features

- **Function Calling** - Agents automatically use assigned tools during conversations
- **Real-Time Orchestration** - SSE event streaming, live agent activity monitoring
- **Dynamic Agent Creation** - The General can spawn new agents/teams via MetaAgent
- **3-Tier Hierarchical Workflows** - Orchestrator → Team Leads → Workers for cost-optimized multi-agent execution
- **Web Search** - Serper.dev integration (tested, working)
- **Email** - Microsoft 365 Graph API with OAuth2 (tested, sending real emails)
- **A2A Protocol** - External agent invocation working
- **MCP Protocol** - Tool registration and direct execution working
- **3D Orchestration** - Three.js visualization with react-force-graph-3d
- **Memory** - mem0 + Qdrant vector storage
- **11 Production Agents** - Stored in PostgreSQL, full CRUD
- **Visual Workflow Builder** - Interactive workflow diagrams with @xyflow/react
- **Ralph Self-Correction** - Automatic workflow retry with error recovery and mid-execution guidance

### Tech Stack

| Layer | Technology |
|-------|------------|
| **Backend** | Python 3.12, FastAPI, SQLAlchemy 2.0, Pydantic v2 |
| **Frontend** | React 18, Vite 6, Tailwind CSS 4, Three.js |
| **Database** | PostgreSQL 16 |
| **Memory** | Qdrant + mem0 (default) or Zep (temporal knowledge graph) |
| **Knowledge Graph** | FalkorDB (AI-native graph database) |
| **LLM** | Ops-Center routing, OpenRouter, Anthropic direct |
| **Observability** | Langfuse (self-hosted), Prometheus |
| **Advanced Tools** | browser-use, Playwright, code sandbox |
| **Voice** | LiveKit (self-hosted), self-hosted STT/TTS (Kokoro, Whisper, Chatterbox) |

---

## Directory Structure

```
Unicorn-Brigade/
├── app/                          # Python backend (FastAPI)
│   ├── api/                      # API route handlers
│   │   ├── agent_routes.py       # Agent CRUD + chat (function calling)
│   │   ├── orchestration_routes.py # Real-time SSE streaming + The General
│   │   ├── a2a_routes.py         # A2A protocol endpoints
│   │   ├── mcp_routes.py         # MCP tool endpoints
│   │   ├── builder_routes.py     # Gunny agent builder
│   │   ├── system_routes.py      # Health, stats
│   │   └── apikey_routes.py      # API key management
│   ├── orchestration/            # Real-time event system
│   │   ├── event_bus.py          # SSE event bus + agent state tracking
│   │   └── __init__.py           # Module exports
│   ├── db/                       # Database layer
│   │   ├── database.py           # Async SQLAlchemy engine
│   │   ├── models.py             # ORM models (Agent, Tool, etc.)
│   │   ├── repositories.py       # Data access (AgentRepository, etc.)
│   │   └── init_db.py            # Database initialization + seeding
│   ├── llm/                      # LLM integration
│   │   ├── ops_center_client.py  # Main LLM client (function calling)
│   │   ├── builtin_tools.py      # Core 7 tools
│   │   ├── extended_tools.py     # Email, file, code, etc. (8 tools)
│   │   ├── tool_models.py        # ToolDefinition, ToolResult
│   │   └── tool_resolver.py      # Agent tool resolution
│   ├── protocols/                # Protocol implementations
│   │   ├── a2a.py                # A2A agent cards, invocation
│   │   └── mcp.py                # MCP server, tool registry
│   ├── workflows/                # 3-Tier Hierarchical Workflows
│   │   ├── __init__.py           # Module exports
│   │   ├── schema.py             # Pydantic models (WorkerSpec, TeamLeadSpec, etc.)
│   │   ├── team_leads.py         # 8 domains, 40 workers
│   │   ├── engine.py             # WorkflowEngine with delegation
│   │   ├── ralph_engine.py       # Ralph self-correction engine
│   │   └── templates.py          # 25 workflow templates (19 core + 6 expansion)
│   ├── mcp/                      # MCP Server Registry (new)
│   │   ├── __init__.py           # Module exports
│   │   ├── registry.py           # 11 pre-configured MCP servers (real npx-runnable packages)
│   │   └── sandbox_executor.py   # Hybrid Docker/E2B code sandbox
│   ├── auth/                     # Authentication & Authorization
│   │   ├── __init__.py           # Module exports
│   │   ├── middleware.py         # API key validation, role checking
│   │   └── roles.py              # RBAC configuration
│   ├── security/                 # Security utilities
│   │   ├── __init__.py           # Module exports
│   │   └── validation.py         # Path traversal, input sanitization
│   ├── memory/                   # Memory system
│   │   ├── manager.py            # mem0 integration
│   │   └── zep_manager.py        # Zep temporal knowledge graph
│   ├── knowledge/                # Knowledge graph
│   │   └── graph_manager.py      # FalkorDB integration
│   ├── voice/                    # Voice system
│   │   ├── config.py             # Voice configuration (env + runtime)
│   │   ├── livekit_agent.py      # LiveKit agent worker
│   │   └── providers/            # STT/TTS provider implementations
│   │       ├── base.py           # Abstract base classes
│   │       ├── registry.py       # Provider registry
│   │       ├── stt_factory.py    # STT factory + LiveKit adapter
│   │       ├── tts_factory.py    # TTS factory + LiveKit adapter
│   │       ├── stt_whisper_cpp.py    # whisper.cpp (CoreML/ANE)
│   │       ├── stt_faster_whisper.py # faster-whisper (CUDA)
│   │       ├── stt_mlx_whisper.py    # mlx-whisper (Metal)
│   │       ├── tts_kokoro.py     # Kokoro-82M (CPU-friendly)
│   │       ├── tts_chatterbox.py # Chatterbox (voice cloning)
│   │       ├── tts_marvis.py     # Marvis (Apple Silicon MLX)
│   │       ├── tts_cosyvoice.py  # CosyVoice2 (ultra-low latency)
│   │       └── tts_custom.py     # Custom models (Vibe Voice, etc.)
│   ├── observability/            # Tracing and monitoring
│   │   └── langfuse_client.py    # Langfuse tracer
│   └── main.py                   # FastAPI app entry point
├── frontend/                     # React frontend
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Dashboard.jsx
│   │   │   ├── AgentLibrary.jsx
│   │   │   ├── AgentChat.jsx     # Chat with function calling UI
│   │   │   ├── Orchestration.jsx # 3D command center
│   │   │   ├── ToolLibrary.jsx
│   │   │   └── ...
│   │   ├── components/
│   │   │   ├── WorkflowVisualization3D.jsx  # Three.js/force-graph
│   │   │   ├── WorkflowDiagram.jsx          # Visual workflow builder (@xyflow/react)
│   │   │   └── ...
│   │   └── App.jsx
│   └── package.json
├── data/
│   └── seed_agents.json          # Initial agent definitions
├── .env                          # Configuration (API keys, DB URL)
├── requirements.txt              # Python dependencies
└── README.md                     # Project documentation
```

---

## Key Files Reference

### Backend Entry Point
**`app/main.py`** - FastAPI application setup, middleware, route registration

### LLM Client with Function Calling
**`app/llm/ops_center_client.py`**
- `execute_tool_loop()` (lines ~510-617) - Complete agentic tool loop
- `chat_completion_with_tools()` - Sends tools to LLM
- `parse_tool_calls()` - Handles OpenAI + Claude response formats

### Agent Chat with Tools
**`app/api/agent_routes.py`**
- `chat_with_agent()` - Chat endpoint with function calling
- Uses `execute_tool_loop()` when agent has tools

### Tool Definitions
**`app/llm/builtin_tools.py`** - Core tools (7):
- web_search, http_request, calculator, datetime, json, shell, memory

**`app/llm/extended_tools.py`** - Extended tools (9):
- email (MS365), file, code, text, image, database, notify, qrcode, agentic_rag

**`app/llm/advanced_tools.py`** - Advanced tools (8):
- browser (Playwright + AI), code_sandbox (Docker/E2B), screenshot, pdf_extract, doc_generate, data_analyze, url_preview, knowledge_graph (FalkorDB)

### Real-Time Orchestration
**`app/orchestration/event_bus.py`**
- `OrchestrationEventBus` singleton - Central event hub with SSE streaming
- `emit_agent_started/completed/tool_call/tool_result()` - Helper functions
- `AgentState`, `ActiveMission` - State tracking dataclasses

**`app/api/orchestration_routes.py`**
- `GET /orchestration/events` - SSE stream for frontend
- `POST /orchestration/command` - The General processes natural language commands
- `POST /orchestration/missions` - Create missions with auto-agent-assignment

### A2A Protocol
**`app/api/a2a_routes.py`**
- `GET /api/v1/a2a/agent-card` - Agent discovery
- `POST /api/v1/a2a/invoke` - External agent invocation

### MCP Protocol
**`app/api/mcp_routes.py`**
- `GET /api/v1/mcp/tools` - List registered tools
- `POST /api/v1/mcp/tools/call` - Direct tool execution

### Database
**`app/db/repositories.py`** - `AgentRepository` with full CRUD
**`app/db/models.py`** - `Agent` ORM model

---

## API Endpoints

### Agents
```
GET    /api/v1/agents              # List all
GET    /api/v1/agents/{id}         # Get one
POST   /api/v1/agents              # Create
PUT    /api/v1/agents/{id}         # Update
DELETE /api/v1/agents/{id}         # Delete
POST   /api/v1/agents/{id}/chat    # Chat (function calling)
```

### A2A Protocol
```
GET    /api/v1/a2a/agent-card      # Discovery
POST   /api/v1/a2a/invoke          # External invocation
```

### MCP Protocol
```
GET    /api/v1/mcp/tools           # List tools
POST   /api/v1/mcp/tools/call      # Execute tool
POST   /api/v1/mcp/register        # Register tool
```

### MCP Server Registry (New Jan 2026)
```
# Server Management
GET    /api/v1/mcp/registry/servers           # List all 14 registered MCP servers
GET    /api/v1/mcp/registry/servers/running   # List currently running servers
GET    /api/v1/mcp/registry/servers/{name}    # Get server details
POST   /api/v1/mcp/registry/servers           # Register new MCP server
DELETE /api/v1/mcp/registry/servers/{name}    # Unregister server
POST   /api/v1/mcp/registry/servers/{name}/start   # Start MCP server
POST   /api/v1/mcp/registry/servers/{name}/stop    # Stop MCP server
POST   /api/v1/mcp/registry/servers/{name}/restart # Restart MCP server

# Tool Invocation
POST   /api/v1/mcp/registry/tools/call        # Call tool on MCP server

# Code Sandbox (Docker + E2B)
GET    /api/v1/mcp/registry/sandbox/status    # Get sandbox status
POST   /api/v1/mcp/registry/sandbox/execute   # Execute code in sandbox
POST   /api/v1/mcp/registry/sandbox/execute/fallback  # Execute with auto-fallback

# Health
GET    /api/v1/mcp/registry/health            # MCP subsystem health
```

### Orchestration (Real-Time)
```
GET    /api/v1/orchestration/events       # SSE stream of agent activity
GET    /api/v1/orchestration/state        # Current state snapshot
GET    /api/v1/orchestration/missions     # List missions
POST   /api/v1/orchestration/missions     # Create mission (auto-assign agents)
POST   /api/v1/orchestration/command      # Send command to The General
POST   /api/v1/orchestration/agents/create # Dynamic agent creation
GET    /api/v1/orchestration/agents/active # Currently active agents
```

### Hierarchical Workflows (3-Tier Agent Hierarchy)
```
# Workflow Templates
GET    /api/v1/hierarchical/templates              # List workflow templates
GET    /api/v1/hierarchical/templates/{id}         # Get template details

# Workflow Execution
POST   /api/v1/hierarchical/execute                # Execute workflow (sync or async)
GET    /api/v1/hierarchical/executions             # List executions (filter by state/workflow)
GET    /api/v1/hierarchical/executions/{id}        # Get execution details with step results
POST   /api/v1/hierarchical/executions/{id}/cancel # Cancel running execution
POST   /api/v1/hierarchical/executions/{id}/checkpoint  # Respond to HITL checkpoint

# Domain Team Leads (7B-14B local models)
GET    /api/v1/hierarchical/domains                # List all 8 domains
GET    /api/v1/hierarchical/domains/{domain}       # Get domain + team lead details
POST   /api/v1/hierarchical/domains/{domain}/execute  # Direct team lead task

# Workers (1B-3B local models)
GET    /api/v1/hierarchical/workers                # List all 40 workers
GET    /api/v1/hierarchical/workers/{id}           # Get worker details + examples
POST   /api/v1/hierarchical/workers/{id}/execute   # Direct worker task (testing)

# Model Information
GET    /api/v1/hierarchical/models                 # Model usage summary + costs
GET    /api/v1/hierarchical/health                 # Hierarchical subsystem health
```

### Voice (LiveKit + Self-Hosted STT/TTS)
```
# Room Management
POST   /api/v1/voice/rooms                # Create voice room for agent
GET    /api/v1/voice/rooms                # List active rooms
GET    /api/v1/voice/rooms/{id}           # Get room details
GET    /api/v1/voice/rooms/{id}/token     # Get participant token
DELETE /api/v1/voice/rooms/{id}           # Close room
POST   /api/v1/voice/rooms/{id}/agent/join # Trigger agent to join
GET    /api/v1/voice/config               # Voice configuration options
GET    /api/v1/voice/health               # Voice service health

# Voice Settings & Providers
GET    /api/v1/voice/settings             # Get current voice config
PUT    /api/v1/voice/settings             # Update voice config (runtime)
POST   /api/v1/voice/settings/reset       # Reset to env defaults
GET    /api/v1/voice/providers            # List all available providers
GET    /api/v1/voice/providers/stt        # List STT providers with details
GET    /api/v1/voice/providers/tts        # List TTS providers with details
GET    /api/v1/voice/voices               # List available TTS voices
POST   /api/v1/voice/test/stt             # Test STT with audio upload
POST   /api/v1/voice/test/tts             # Test TTS, returns WAV audio
```

### System
```
GET    /api/v1/health              # Health check
GET    /api/v1/stats               # System stats
GET    /api/v1/models              # Available LLM models
```

### Langflow (Visual Workflow Builder)
```
# Flow Management
GET    /api/v1/langflow/health               # Langflow service health
GET    /api/v1/langflow/flows                # List available flows
GET    /api/v1/langflow/flows/{id}           # Get flow details
POST   /api/v1/langflow/flows                # Create new flow
PATCH  /api/v1/langflow/flows/{id}           # Update flow
DELETE /api/v1/langflow/flows/{id}           # Delete flow

# Flow Execution
POST   /api/v1/langflow/flows/{id}/run       # Execute flow with inputs

# Import/Export
POST   /api/v1/langflow/flows/import         # Import flow from JSON
GET    /api/v1/langflow/flows/{id}/export    # Export flow as JSON

# Workflow Conversion
GET    /api/v1/langflow/flows/{id}/convert   # Convert to Brigade workflow format
POST   /api/v1/langflow/workflows/convert-to-langflow  # Convert Brigade workflow to Langflow
```

---

## Environment Variables

```bash
# API
API_HOST=0.0.0.0
API_PORT=8100

# Authentication (Required in production)
BRIGADE_ADMIN_KEY=your-64-char-hex-admin-key  # Master admin key (openssl rand -hex 32)
AUTH_BYPASS=false                              # NEVER set true in production

# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5434/unicorn_brigade

# LLM
OPS_CENTER_URL=https://unicorncommander.ai
OPENROUTER_API_KEY=sk-or-v1-000000000000000000000000000000000000
ANTHROPIC_API_KEY=sk-ant-...

# Tools
SERPER_API_KEY=...              # Web search

# Microsoft 365 Email
MS365_CLIENT_ID=...
MS365_TENANT_ID=...
MS365_CLIENT_SECRET=...
MS365_USER_EMAIL=aaron@magicunicorn.tech

# Memory
QDRANT_URL=http://localhost:6333

# Langfuse Observability (self-hosted)
LANGFUSE_ENABLED=true
LANGFUSE_HOST=http://localhost:3001
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...

# Advanced Tools
BROWSER_USE_ENABLED=false
CODE_SANDBOX_ENABLED=true

# FalkorDB Knowledge Graph
FALKORDB_ENABLED=true
FALKORDB_HOST=brigade-falkordb
FALKORDB_PORT=6380

# Voice STT (Speech-to-Text) - Self-Hosted
VOICE_STT_PROVIDER=mlx-whisper      # whisper-cpp, faster-whisper, mlx-whisper
VOICE_STT_MODEL=large-v3-turbo      # tiny, base, small, medium, large-v3, large-v3-turbo
VOICE_STT_DEVICE=auto               # auto, cpu, cuda, mps
VOICE_STT_COMPUTE_TYPE=float16      # float16, int8, float32
VOICE_STT_LANGUAGE=en

# Voice TTS (Text-to-Speech) - Self-Hosted
VOICE_TTS_PROVIDER=kokoro           # kokoro, chatterbox, marvis, cosyvoice, custom
VOICE_TTS_MODEL=kokoro-82m
VOICE_TTS_VOICE=af_bella            # Provider-specific voice ID
VOICE_TTS_SAMPLE_RATE=24000
VOICE_TTS_SPEED=1.0

# Custom TTS Models (for Vibe Voice, etc.)
# CUSTOM_TTS_MODEL_PATH=/path/to/model
# CUSTOM_TTS_CONFIG_PATH=/path/to/config.json

# Langflow Visual Workflow Builder
LANGFLOW_ENABLED=true
LANGFLOW_HOST=http://localhost:7860
LANGFLOW_API_KEY=                       # Optional API key for authentication
LANGFLOW_SUPERUSER=admin
LANGFLOW_SUPERUSER_PASSWORD=changeme
LANGFLOW_SECRET_KEY=your-secret-key
```

---

## Common Operations

### Start Development

```bash
# Backend
source venv/bin/activate
uvicorn app.main:app --reload --port 8100

# Frontend
cd frontend && npm run dev
```

### Start Full Stack with Docker

```bash
# Core services only
docker-compose up -d

# With Langfuse Observability
docker-compose -f docker-compose.yml -f docker-compose.langfuse.yml up -d
# Access Langfuse UI at http://localhost:3001

# With Zep Memory (alternative to mem0)
docker-compose -f docker-compose.yml -f docker-compose.zep.yml up -d
# Set MEMORY_PROVIDER=zep in .env

# With FalkorDB Knowledge Graph
docker-compose -f docker-compose.yml -f docker-compose.falkordb.yml up -d
# Access FalkorDB Browser at http://localhost:3002

# With LiveKit Voice
docker-compose -f docker-compose.yml -f docker-compose.livekit.yml up -d
# Voice API at /api/v1/voice/rooms

# With Langflow Visual Workflows
docker-compose -f docker-compose.yml -f docker-compose.langflow.yml up -d
# Access Langflow UI at http://localhost:7860
# API at /api/v1/langflow/flows

# Full stack with everything
docker-compose -f docker-compose.yml \
  -f docker-compose.langfuse.yml \
  -f docker-compose.zep.yml \
  -f docker-compose.falkordb.yml \
  -f docker-compose.livekit.yml \
  -f docker-compose.langflow.yml up -d
```

### Test Function Calling

```bash
# Chat with agent (tools auto-invoked)
curl -X POST http://localhost:8100/api/v1/agents/col-finance/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Search for AI market trends"}'
```

### Test Real-Time Orchestration

```bash
# Get current orchestration state
curl http://localhost:8100/api/v1/orchestration/state

# Connect to SSE stream (in another terminal)
curl -N http://localhost:8100/api/v1/orchestration/events

# Send command to The General
curl -X POST http://localhost:8100/api/v1/orchestration/command \
  -H "Content-Type: application/json" \
  -d '{"command": "Create a new agent to handle customer support"}'

# Create a mission with auto-assigned agents
curl -X POST http://localhost:8100/api/v1/orchestration/missions \
  -H "Content-Type: application/json" \
  -d '{"name": "Market Research", "task": "Analyze Q4 tech sector trends", "auto_assign": true}'
```

### Test A2A Invocation

```bash
curl -X POST http://localhost:8100/api/v1/a2a/invoke \
  -H "Content-Type: application/json" \
  -d '{"agent_id": "col-finance", "task": "Calculate 2+2", "tools": ["calculator"]}'
```

### Test MCP Tool

```bash
curl -X POST http://localhost:8100/api/v1/mcp/tools/call \
  -H "Content-Type: application/json" \
  -d '{"name": "email", "arguments": {"to": "test@example.com", "subject": "Test", "body": "Hello"}}'
```

### Test Langflow Integration

```bash
# Check Langflow health
curl http://localhost:8100/api/v1/langflow/health

# List available flows
curl http://localhost:8100/api/v1/langflow/flows

# Run a flow
curl -X POST http://localhost:8100/api/v1/langflow/flows/{flow_id}/run \
  -H "Content-Type: application/json" \
  -d '{"inputs": {"input_value": "Hello, world!"}}'

# Export a flow
curl http://localhost:8100/api/v1/langflow/flows/{flow_id}/export

# Convert flow to Brigade workflow format
curl http://localhost:8100/api/v1/langflow/flows/{flow_id}/convert
```

### Database Access

```bash
PGPASSWORD=leads_password_dev psql -h localhost -p 5434 -U leads_user -d unicorn_brigade
```

---

## Working Tool Integrations

| Tool | Config | Notes |
|------|--------|-------|
| **Web Search** | `SERPER_API_KEY` | Returns Google SERP results |
| **Email** | `MS365_*` vars | OAuth2 client credentials, Graph API |
| **Memory** | `QDRANT_URL` | mem0 wrapper for Qdrant vectors |
| **Calculator** | None | Safe math evaluation |
| **HTTP** | None | httpx for external APIs |
| **Browser** | `BROWSER_USE_ENABLED=true` | AI-driven browser automation (requires playwright install) |
| **Code Sandbox** | `CODE_SANDBOX_ENABLED=true` | Secure Python with numpy/pandas |
| **Screenshot** | `BROWSER_USE_ENABLED=true` | Webpage screenshots via Playwright |
| **Knowledge Store** | `FALKORDB_ENABLED=true` | Store facts/entities in knowledge graph |
| **Knowledge Query** | `FALKORDB_ENABLED=true` | Query knowledge graph relationships |

### MCP Servers (Self-Hosted - Jan 2026)

**Baseline Servers (10)**:

| Server | Config | Capabilities |
|--------|--------|--------------|
| **GitHub** | `GITHUB_TOKEN` | create_repository, create_issue, create_pull_request, search_code |
| **Playwright** | Built-in | browser_navigate, browser_click, browser_fill, browser_snapshot |
| **Slack** | `SLACK_BOT_TOKEN` | conversations_history, conversations_search_messages, reactions_add |
| **PostgreSQL** | `DATABASE_URL` | query, list_tables, describe_table, list_schemas |
| **Filesystem** | `WORKSPACE_PATH` | read_file, write_file, list_directory, search_files |
| **Memory** | Built-in | store, retrieve, list, delete |
| **HTTP Fetch** | Built-in | fetch (GET, POST, PUT, DELETE) |
| **Brave Search** | `BRAVE_API_KEY` | brave_web_search, brave_local_search |
| **Google Drive** | `GOOGLE_APPLICATION_CREDENTIALS` | search_files, get_file, download_file |
| **Puppeteer** | Built-in | navigate, screenshot, click, fill, evaluate |

**MCP registry truth (rewritten 2026-07-02):** the former “Phase 1–9” tables listed 36
fabricated servers with invented npm package names and hand-authored tool counts. The registry
(`app/mcp/registry.py`) now holds **11 real, npx-runnable servers** — github, filesystem, postgres,
playwright, slack, memory, brave-search, google-drive, puppeteer, stripe (`@stripe/mcp`), notion
(`@notionhq/notion-mcp-server`). Capabilities in the registry are *declared*; actual tool lists are
discovered at runtime when a server starts. Add new servers only with verified-published packages.

### Voice Providers (Self-Hosted - Jan 2026)

| Provider | Type | Config | Notes |
|----------|------|--------|-------|
| **mlx-whisper** | STT | `VOICE_STT_PROVIDER=mlx-whisper` | Apple Silicon Metal, unified memory |
| **faster-whisper** | STT | `VOICE_STT_PROVIDER=faster-whisper` | CUDA GPUs, CTranslate2, INT8 quantization |
| **whisper.cpp** | STT | `VOICE_STT_PROVIDER=whisper-cpp` | CoreML/Apple Neural Engine |
| **Kokoro-82M** | TTS | `VOICE_TTS_PROVIDER=kokoro` | CPU-friendly, 11 voices, Apache 2.0 |
| **Chatterbox** | TTS | `VOICE_TTS_PROVIDER=chatterbox` | Voice cloning, emotion control, MIT |
| **Marvis** | TTS | `VOICE_TTS_PROVIDER=marvis` | Apple Silicon MLX native |
| **CosyVoice2** | TTS | `VOICE_TTS_PROVIDER=cosyvoice` | 150ms latency, multi-language |
| **Custom** | TTS | `VOICE_TTS_PROVIDER=custom` | Local ONNX/PyTorch models |

**Kokoro Voices**: af_bella, af_sarah, af_nicole, af_sky, am_adam, am_michael, bf_emma, bf_isabella, bm_george, bm_lewis

---

## Recent Changes (Jan 2026)

1. **Real-Time Orchestration** - SSE event bus for live agent activity streaming
2. **The General Commands** - `/orchestration/command` endpoint for natural language orchestration
3. **Dynamic Agent Creation** - MetaAgent integration for spawning agents on-the-fly
4. **Mission System** - Create multi-agent missions with auto-assignment
5. **Function Calling Wired** - `execute_tool_loop()` now used in agent chat
6. **MS365 Email** - OAuth2 token caching, Graph API sendMail
7. **DB Migration** - Agents moved from in-memory JSON to PostgreSQL
8. **3D Orchestration** - react-force-graph-3d (replaced reagraph for React 18 compat)
9. **Tool Resolver** - Maps agent tool names to ToolDefinition objects
10. **Langfuse Observability** - Self-hosted LLM tracing, cost tracking, evaluation
11. **Browser Automation Tool** - AI-driven browser control via browser-use library
12. **Code Sandbox Tool** - Secure Python execution with numpy/pandas support
13. **Screenshot Tool** - Webpage screenshot capture via Playwright
14. **Zep Memory System** - Alternative to mem0 with temporal knowledge graph (Graphiti)
15. **FalkorDB Knowledge Graph** - AI-native graph for entity/relationship tracking
16. **LiveKit Voice Agents** - Real-time voice conversations with agents (STT/TTS)
17. **Self-Hosted Voice Providers** - Complete STT/TTS provider system:
    - STT: mlx-whisper (Metal), faster-whisper (CUDA), whisper.cpp (CoreML)
    - TTS: Kokoro-82M, Chatterbox (voice cloning), Marvis (MLX), CosyVoice2, Custom
18. **Voice Provider Registry** - Factory pattern for runtime provider selection
19. **Voice Settings API** - Environment variables + runtime configuration updates
20. **Voice Cloning Support** - Chatterbox/CosyVoice2 can clone from 5-10s samples
21. **Langflow Integration** - Visual workflow builder integration:
    - Flow management (list, get, create, update, delete)
    - Flow execution with inputs and session continuity
    - Import/export flows as JSON
    - Convert between Langflow and Brigade workflow formats
22. **Protocol Routes Complete** (Jan 30, 2026):
    - A2A invoke wired to actual agent execution with function calling
    - Agent discovery queries database for real agents
    - MCP resource reading supports file:// and http:// URIs
23. **MCP Server Registry** (Jan 30-31, 2026):
    - Central registry of 11 real, npx-runnable MCP servers (fabricated phase-1..9 entries removed 2026-07-02)
    - Subprocess-based server lifecycle management (start/stop/restart)
    - JSON-RPC tool invocation for STDIO transport
    - HTTP/SSE transport support for remote servers
24. **Hybrid Code Sandbox** (Jan 30, 2026):
    - Self-hosted Docker execution (preferred for privacy/cost)
    - E2B cloud sandbox as optional fallback
    - Supports Python, JavaScript, TypeScript, Bash
    - Network isolation, resource limits, timeout handling
    - Auto-detect best available backend
25. **Security Hardening** (Jan 30, 2026):
    - API key authentication middleware (`app/auth/`)
    - Role-based access control (Admin, Operator, Viewer)
    - MCP registry endpoints require admin authentication
    - Shell tool now executes in Docker sandbox, not host
    - Path traversal validation (`app/security/validation.py`)
    - Fixed orchestration response parsing bug
    - Fixed uninitialized variable in tool logging
26. **3-Tier Hierarchical Workflows** (Jan 30, 2026):
    - Architecture: Orchestrator (GPT-4o) → Team Leads (7B-14B local) → Workers (1B-3B local)
    - 8 domains: Research, Finance, Content, Sales, DevOps, Legal, Medical, Investigation
    - 40 narrow-scope workers optimized for small local models
    - 25 workflow templates:
      - 6 core workflows: Investment Due Diligence, Autonomous Sales Pipeline, Incident Response, Content Production, Legal Case Analysis, Medical Documentation Review
      - 2 Phase 1 workflows: Help Desk Triage, RFP Response Generation
      - 11 professional workflows (across 8 domains)
      - 6 Phase 2 expansion workflows: API Integration Automation, Contract Analysis, Meeting Intelligence, Research Literature Review, Multi-Channel Content Distribution, Compliance Audit
    - Human-in-the-loop checkpoints for approvals
    - Cost tracking (API models charged, local models free)
    - Direct testing at Team Lead and Worker levels
27. **Tool Library Expansion** (Jan 31, 2026):
    - Expanded from 15 to 23 working tools
    - All tools now visible in Tool Library UI
    - Categorized as Built-in (7), Extended (9), Advanced (8)
    - Updated tool_routes.py to expose all tool types
28. **Visual Workflow Diagram Component** (Jan 31, 2026):
    - Interactive workflow visualization with @xyflow/react v12
    - Custom StepNode components with icons for orchestrator/team-lead/worker/checkpoint
    - Horizontal left-to-right flow layout
    - Real-time execution state tracking
    - MiniMap and controls for navigation
    - Fixed infinite render loop bug, component remounting issues
29. **Agent Database Cleanup** (Jan 31, 2026):
    - Reduced from 65 test agents to 17 production agents (cleaned to 11, then added 6)
    - Removed duplicate and test agents without proper prefixes
    - All remaining agents follow military naming convention
30. **Phase 2-4 'platform expansion' entries removed** (2026-07-02): they described fabricated MCP servers.
33. **Phase 1 Implementation Complete** (Jan 31, 2026):
    - **MCP Server Registry**: Stripe + Notion added (real packages; Linear/Git entries later removed as unrunnable)
    - **New Agents**: 3 production agents added (11 → 14):
      - sql-analyst: SQL query generation and database interaction
      - support-agent: Customer support and ticket triage
      - code-reviewer: Code review, quality analysis, best practices
    - **Workflow Templates**: Expanded from 6 to 19 workflows:
      - 6 original high-value workflows
      - 2 Phase 1 priority: Help Desk Triage, RFP Response Generation
      - 11 additional professional workflows (competitive intel, code review, data reports, etc.)
    - **Frontend Workflow Gallery**: Visual workflow discovery and execution
      - WorkflowCard component with mini-diagram previews
      - WorkflowGallery with grid/list views
      - WorkflowFilters for search, tags, complexity filtering
      - Full integration in Workflows page
34. **Ralph Self-Correction Engine** (Jan 31, 2026):
    - **Self-Correcting Workflows**: Automatic retry with error recovery inspired by open-ralph-wiggum
    - **Key Features**:
      - Automatic task breakdown with dependency tracking
      - Iterative self-correction on failures (up to 5 iterations by default)
      - Mid-execution guidance injection without restart
      - Complete state persistence (.ralph/ directory)
      - Progress tracking and iteration history
    - **API Endpoints**: `/api/v1/ralph/*` (execute, progress, guidance, cancel)
    - **Frontend UI**: Ralph Monitor at `/ralph-monitor` with real-time progress
    - **Integration**: Works seamlessly with hierarchical workflows
    - **Use Cases**: Handles transient failures (API timeouts, rate limits), enables human-in-the-loop corrections
    - **Documentation**: `docs/RALPH_SELF_CORRECTION.md`
    - **Tests**: Comprehensive test suite in `tests/test_ralph_engine.py`
35. **Agent Trace - Code Attribution Tracking** (Jan 31, 2026):
    - **Production-Ready System**: Full implementation of agent-trace.dev specification for AI code attribution
    - **Database Schema**: PostgreSQL table with 14 columns, 6 indexes for optimal performance
    - **7 API Endpoints**: health, stats, recent, files, agents, sessions, report generation (JSON/CSV)
    - **Frontend Integration**: traceService.js updated, Code Attribution page in navigation (SYSTEM section)
    - **AgentTraceRecorder**: Automatic code tracking integrated with LLM client
    - **Key Features**:
      - Tracks which AI agent/model generated each piece of code
      - Records file location, line numbers, code hashes (SHA-256)
      - Stores user prompts for full context
      - Metadata tracking (tokens, duration, language, framework)
      - Operation types (generation, edit, deletion)
    - **Testing**: 9/9 comprehensive tests passing
    - **Documentation**: Deployment guide, integration guide, verification report
    - **Bug Fixes**: File path normalization, foreign key constraints
    - **Use Cases**: Code review, compliance auditing, productivity analysis, debugging
    - **Files**:
      - Backend: `app/api/trace_routes.py`, `app/observability/agent_trace.py`
      - Database: `app/db/models.py` (CodeAttribution), `app/db/repositories.py` (CodeAttributionRepository)
      - Frontend: `frontend/src/services/traceService.js`, `frontend/src/pages/CodeAttribution.jsx`
      - Tests: `scripts/test_agent_trace_full.py`, `examples/agent_trace_demo.py`
      - Docs: `docs/AGENT_TRACE_DEPLOYMENT.md`, `docs/AGENT_TRACE_VERIFICATION.md`, `docs/AGENT_TRACE_INTEGRATION.md`

---

## Next Steps

- [x] Deploy Langfuse stack (`docker-compose -f docker-compose.yml -f docker-compose.langfuse.yml up -d`)
- [x] Switch to Zep memory system (temporal knowledge graph, sub-200ms latency)
- [x] Add FalkorDB knowledge graph (AI-native, multi-agent support)
- [x] LiveKit voice agent support
- [x] Self-hosted voice providers (Kokoro, Whisper, Chatterbox, CosyVoice2)
- [x] Voice provider registry and settings API
- [x] Langflow integration for visual workflow building
- [x] Tool Library expansion to 23 tools (all visible in UI)
- [x] Visual workflow diagram component (@xyflow/react)
- [x] Agent database cleanup (65 → 17 production agents via 11 cleanup + 6 new)
- [ ] Vibe Voice TTS integration (user will provide model)
- [x] Frontend tool call visualization (ToolCallCard.jsx + SSE handling)
- [x] Frontend voice call UI (VoiceCallModal, VoiceCallButton, useVoiceCall hook)
- [x] Google Workspace email provider (app/integrations/google_email.py)
- [x] Slack integration (app/api/slack_routes.py, app/llm/slack_tools.py)
- [x] Guardrails integration research and planning (docs/guardrails-plan.md)
- [x] MCP Server Registry (pruned 2026-07-02 to 11 real npx-runnable servers)
- [x] Hybrid Code Sandbox (Docker + E2B fallback)
- [x] Protocol routes complete (A2A invoke, agent discovery, MCP resource reading)
- [x] 3-Tier Hierarchical Workflows (Orchestrator → Team Leads → Workers)
- [x] Ralph Self-Correction Engine (automatic workflow retry with error recovery - Jan 31, 2026)
- [x] Agent Trace integration (code attribution tracking for AI-generated code - Jan 31, 2026)
- [ ] Guardrails deployment on Ops-Center (Presidio, Llama Guard 3, Guardrails AI)
- [ ] Add further MCP servers only as verified-published packages (e.g. @hubspot/mcp-server now exists)

---

## Guardrails Integration (Planned - Jan 2026)

LLM guardrails are deployed on the Ops-Center side via LiteLLM proxy. See `docs/guardrails-plan.md` for full details.

### Recommended Stack (Self-Hosted)

| Component | Purpose | Latency |
|-----------|---------|---------|
| **LiteLLM Built-in** | Keyword/pattern blocking | 5-10ms |
| **Microsoft Presidio** | PII detection/masking | 30-50ms |
| **Llama Guard 3-1B** | Content safety | 150-200ms |
| **Guardrails AI** | Toxicity, bias, validators | 20-40ms |

### Quick Start

```bash
# Deploy guardrails services
./scripts/setup_guardrails.sh

# Services:
# - Presidio Analyzer:    http://localhost:5001
# - Presidio Anonymizer:  http://localhost:5002
# - Llama Guard Service:  http://localhost:8085
# - Guardrails AI:        http://localhost:8086
```

### Docker Compose

```bash
# Add guardrails to existing stack
docker-compose -f docker-compose.yml -f docker-compose.guardrails.yml up -d
```

### Key Files

- `docs/guardrails-plan.md` - Full implementation plan
- `docker-compose.guardrails.yml` - Service definitions
- `config/guardrails/litellm_config.yaml` - LiteLLM proxy config template
- `services/llama-guard/` - Llama Guard FastAPI service
- `services/guardrails-ai/` - Guardrails AI service
- `config/presidio/` - Presidio configuration

---

**Last Updated**: July 2, 2026 (menu audit: registry truth pass, unified auth client, live health)
**Status**: Production-ready with **17 production agents**, 23 working tools (Built-in + Extended + Advanced), **25 workflow templates**, real-time orchestration, function calling, A2A (DB-backed discovery), MCP Server Registry (**11 real npx-runnable servers** + hybrid code sandbox), email (MS365 + Google), Slack integration, web search, self-hosted voice (Kokoro, Whisper, Chatterbox + LiveKit WebRTC UI), Langflow visual workflows, 3-tier hierarchical workflows (8 domains, 40 workers), **Ralph self-correction engine** (automatic retry, error recovery, mid-execution guidance), visual workflow gallery with discovery UI (@xyflow/react + WorkflowCard/Gallery/Filters), guardrails planning complete

---
