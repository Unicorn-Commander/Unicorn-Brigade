# Unicorn Brigade - Claude Code Context

## Project Overview

**Unicorn Brigade** is the AI Agent Factory - a production-ready platform for building, deploying, and orchestrating AI agents with real-world tool integrations.

**Key Capabilities:**
- Build agents through conversation with Gunny or via API
- 18 pre-built agents across 8 domains
- 15 working tools (web search, email, calculator, memory, etc.)
- A2A and MCP protocol support for agent federation
- 3D orchestration visualization with The General

---

## CURRENT STATUS: January 2026

### Working Features

- **Function Calling** - Agents automatically use assigned tools during conversations
- **Web Search** - Serper.dev integration (tested, working)
- **Email** - Microsoft 365 Graph API with OAuth2 (tested, sending real emails)
- **A2A Protocol** - External agent invocation working
- **MCP Protocol** - Tool registration and direct execution working
- **3D Orchestration** - Three.js visualization with react-force-graph-3d
- **Memory** - mem0 + Qdrant vector storage
- **18 Agents** - Stored in PostgreSQL, full CRUD

### Tech Stack

| Layer | Technology |
|-------|------------|
| **Backend** | Python 3.12, FastAPI, SQLAlchemy 2.0, Pydantic v2 |
| **Frontend** | React 18, Vite 6, Tailwind CSS 4, Three.js |
| **Database** | PostgreSQL 15 |
| **Memory** | Qdrant + mem0 |
| **LLM** | Ops-Center routing, OpenRouter, Anthropic direct |

---

## Directory Structure

```
Unicorn-Brigade/
├── app/                          # Python backend (FastAPI)
│   ├── api/                      # API route handlers
│   │   ├── agent_routes.py       # Agent CRUD + chat (function calling)
│   │   ├── a2a_routes.py         # A2A protocol endpoints
│   │   ├── mcp_routes.py         # MCP tool endpoints
│   │   ├── builder_routes.py     # Gunny agent builder
│   │   ├── system_routes.py      # Health, stats
│   │   └── apikey_routes.py      # API key management
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
│   ├── memory/                   # Memory system
│   │   └── manager.py            # mem0 integration
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
**`app/llm/builtin_tools.py`** - Core tools:
- web_search, http_request, calculator, datetime, json, shell, memory

**`app/llm/extended_tools.py`** - Extended tools:
- email (MS365), file, code, text, image, database, notify, qrcode

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

### System
```
GET    /api/v1/health              # Health check
GET    /api/v1/stats               # System stats
GET    /api/v1/models              # Available LLM models
```

---

## Environment Variables

```bash
# API
API_HOST=0.0.0.0
API_PORT=8100

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

### Test Function Calling

```bash
# Chat with agent (tools auto-invoked)
curl -X POST http://localhost:8100/api/v1/agents/col-finance/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Search for AI market trends"}'
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

---

## Recent Changes (Jan 2026)

1. **Function Calling Wired** - `execute_tool_loop()` now used in agent chat
2. **MS365 Email** - OAuth2 token caching, Graph API sendMail
3. **DB Migration** - Agents moved from in-memory JSON to PostgreSQL
4. **3D Orchestration** - react-force-graph-3d (replaced reagraph for React 18 compat)
5. **Tool Resolver** - Maps agent tool names to ToolDefinition objects

---

## Next Steps

- [ ] Google Workspace email provider
- [ ] Slack tool integration
- [ ] Visual workflow builder
- [ ] Frontend tool call visualization (show tool cards in chat)

---

**Last Updated**: January 29, 2026
**Status**: Production-ready with working function calling, A2A, MCP, email, web search
