<div align="center">

<img src="frontend/public/The_General_Logo.png" width="180"/>

# Unicorn Brigade

### **The AI Agent Factory**

*Build. Deploy. Orchestrate. Dominate.*

[![Python](https://img.shields.io/badge/Python-3.12-blue?style=for-the-badge&logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-teal?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18-61DAFB?style=for-the-badge&logo=react)](https://react.dev)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-336791?style=for-the-badge&logo=postgresql)](https://postgresql.org)

[![A2A Protocol](https://img.shields.io/badge/A2A-Protocol-green?style=for-the-badge)](https://github.com/google/a2a-spec)
[![MCP](https://img.shields.io/badge/MCP-Anthropic-orange?style=for-the-badge)](https://modelcontextprotocol.io)
[![License: MIT](https://img.shields.io/badge/License-MIT-purple?style=for-the-badge)](LICENSE)

**[Live Demo](https://brigade.unicorncommander.ai)** |
**[Quick Start](#-quick-start)** |
**[API Docs](#-api-reference)** |
**[Architecture](#-architecture)**

---

**11 Production Agents** | **23 Working Tools** | **17 Workflow Templates** | **A2A + MCP Protocols** | **3D Orchestration** | **Visual Workflow Builder**

</div>

---

## What is Unicorn Brigade?

Unicorn Brigade is a **production-ready AI agent orchestration platform** where you can:

**Build** custom AI agents through conversation with Gunny, or via API
**Deploy** agents with real-world tools - email, web search, databases, code execution
**Orchestrate** multi-agent workflows through The General's 3D command center
**Federate** agents across systems using A2A and MCP protocols

This isn't a toy. **It sends real emails. It searches the real web. It coordinates real workflows.**

---

## Screenshots

<div align="center">

### Dashboard
*18 agents across 8 domains, all systems operational*

![Dashboard](.github/images/dashboard.png)

### 3D Orchestration Command Center
*The General's real-time view of agent operations*

![Orchestration](.github/images/orchestration.png)

### Tool Library
*Built-in tools ready for agent assignment*

![Tool Library](.github/images/tool-library.png)

</div>

---

## Features That Actually Work

### Real Tool Integration (23 Tools)

**Built-in Tools (7)**
| Tool | Provider | Status |
|------|----------|--------|
| **Web Search** | Serper.dev | ✅ Working |
| **HTTP Request** | httpx | ✅ Working |
| **Calculator** | Python | ✅ Working |
| **DateTime** | Python | ✅ Working |
| **JSON** | Python | ✅ Working |
| **Memory** | mem0 + Qdrant | ✅ Working |
| **Shell** | Docker Sandbox | ✅ Working |

**Extended Tools (9)**
| Tool | Provider | Status |
|------|----------|--------|
| **Email** | MS365/Google | ✅ Working |
| **File Operations** | Local | ✅ Working |
| **Code Execution** | Docker/E2B | ✅ Working |
| **Text Processing** | Python | ✅ Working |
| **Image Generation** | AI Models | ✅ Working |
| **Database** | PostgreSQL/MySQL | ✅ Working |
| **Notifications** | Multi-channel | ✅ Working |
| **QR Code** | Python qrcode | ✅ Working |
| **Agentic RAG** | Vector DB | ✅ Working |

**Advanced Tools (8)**
| Tool | Provider | Status |
|------|----------|--------|
| **Browser Automation** | Playwright + AI | ✅ Working |
| **Code Sandbox** | Docker + E2B | ✅ Working |
| **Screenshot** | Playwright | ✅ Working |
| **PDF Extract** | PyPDF2 | ✅ Working |
| **Doc Generate** | python-docx | ✅ Working |
| **Data Analyze** | Pandas/NumPy | ✅ Working |
| **URL Preview** | BeautifulSoup | ✅ Working |
| **Knowledge Graph** | FalkorDB | ✅ Working |

### Protocol Support

```
A2A (Agent-to-Agent Protocol)     MCP (Model Context Protocol)
├── Agent Discovery                ├── Tool Registration
├── External Invocation            ├── Direct Tool Execution
├── Agent Cards                    ├── Schema Validation
└── Federated Workflows            └── Result Formatting
```

Both protocols are **fully operational** with tested endpoints.

### Agent Roster

**18 production-ready agents** organized by domain:

| Domain | Agents |
|--------|--------|
| **Command** | The General (orchestrator), Gunny (agent builder) |
| **Operations** | Col. Pipeline, Sgt. Major Executor, Cpl. Monitor |
| **Research** | Dr. Analyst, Lt. Webster, Cpl. Librarian |
| **Engineering** | Sgt. Coder, Cpl. Debugger, Pvt. Tester |
| **Security** | Capt. Fortress, Sgt. Audit |
| **Finance** | Col. Finance, Lt. Budget |
| **Medical** | Dr. Vitals, Nurse Navigator |
| **Training** | Sgt. Instructor |

All agents are stored in **PostgreSQL** with full CRUD operations.

---

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 15+
- Node.js 18+ (for frontend)
- Qdrant (for memory)

### Installation

```bash
# Clone
git clone https://github.com/Unicorn-Commander/Unicorn-Brigade.git
cd Unicorn-Brigade

# Python environment
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env with your API keys (see Configuration section)

# Database
# Ensure PostgreSQL is running, then:
python -c "from app.db.database import init_db; import asyncio; asyncio.run(init_db())"

# Start backend
uvicorn app.main:app --host 0.0.0.0 --port 8100
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173

---

## Configuration

### Required API Keys

```bash
# .env file

# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5434/unicorn_brigade

# LLM Provider (pick one or more)
OPS_CENTER_URL=https://unicorncommander.ai  # Our routing service
OPENROUTER_API_KEY=sk-or-v1-000000000000000000000000000000000000             # 200+ models
ANTHROPIC_API_KEY=sk-ant-...                # Claude direct

# Web Search
SERPER_API_KEY=...

# Email (Microsoft 365)
MS365_CLIENT_ID=...
MS365_TENANT_ID=...
MS365_CLIENT_SECRET=...
MS365_USER_EMAIL=your@email.com

# Memory
QDRANT_URL=http://localhost:6333
```

### Tool Configuration

Tools are automatically registered on startup. To customize:

```python
# app/llm/extended_tools.py

MY_TOOL = ToolDefinition(
    name="my_tool",
    description="What this tool does (LLM reads this)",
    parameters=[
        ToolParameter(name="input", type="string", required=True),
    ],
    handler=my_async_handler,
)

EXTENDED_TOOLS = [..., MY_TOOL]  # Add to the list
```

---

## API Reference

### Agent Operations

```bash
# List all agents
GET /api/v1/agents

# Get agent details
GET /api/v1/agents/{agent_id}

# Chat with agent (function calling enabled)
POST /api/v1/agents/{agent_id}/chat
{
  "message": "Search for AI market trends and email me a summary",
  "stream": false
}

# Response includes tool calls
{
  "content": "I found the data and sent you an email...",
  "toolCalls": [
    {"name": "web_search", "arguments": {...}, "result": {...}},
    {"name": "email", "arguments": {...}, "result": {"success": true}}
  ],
  "model": "openai/gpt-4o"
}
```

### A2A Protocol (Agent-to-Agent)

```bash
# Get agent card for discovery
GET /api/v1/a2a/agent-card

# Invoke agent from external system
POST /api/v1/a2a/invoke
{
  "agent_id": "col-finance",
  "task": "Calculate CAGR from $7.63B to $10.91B over 2 years",
  "tools": ["calculator"]
}

# Response
{
  "result": "The CAGR is 19.6%...",
  "tool_calls": [
    {"tool": "calculator", "input": {...}, "output": {"result": 19.58}}
  ]
}
```

### MCP Protocol (Tool Execution)

```bash
# List available tools
GET /api/v1/mcp/tools

# Execute tool directly
POST /api/v1/mcp/tools/call
{
  "name": "web_search",
  "arguments": {"query": "AI agent market size 2026"}
}

# Send email via MCP
POST /api/v1/mcp/tools/call
{
  "name": "email",
  "arguments": {
    "to": "team@example.com",
    "subject": "Report",
    "body": "Here is the analysis..."
  }
}
```

---

## Architecture

```
                    Unicorn Brigade Platform
    ┌────────────────────────────────────────────────────────┐
    │                                                        │
    │   ┌──────────────┐          ┌──────────────┐          │
    │   │   React UI   │◄────────►│   FastAPI    │          │
    │   │   + Three.js │  HTTP/WS │   Backend    │          │
    │   └──────────────┘          └──────┬───────┘          │
    │                                    │                   │
    │         ┌──────────────────────────┼─────────────┐    │
    │         │                          │             │    │
    │   ┌─────▼─────┐  ┌─────────┐  ┌───▼────┐  ┌────▼───┐ │
    │   │    A2A    │  │   MCP   │  │ Agents │  │  Tools │ │
    │   │  Server   │  │ Server  │  │  CRUD  │  │ Engine │ │
    │   └───────────┘  └─────────┘  └───┬────┘  └────┬───┘ │
    │                                    │            │     │
    │   ┌────────────────────────────────┴────────────┤     │
    │   │                                             │     │
    │   │              LLM Client Layer               │     │
    │   │  ┌────────┐ ┌────────┐ ┌────────┐         │     │
    │   │  │Ops-Ctr │ │OpenAI/ │ │Anthropic│         │     │
    │   │  │(Router)│ │OpenRtr │ │ Direct │         │     │
    │   │  └────────┘ └────────┘ └────────┘         │     │
    │   └─────────────────────────────────────────────┘     │
    │                                                        │
    │   ┌────────────┐  ┌────────────┐  ┌────────────┐      │
    │   │ PostgreSQL │  │   Qdrant   │  │   Redis    │      │
    │   │  (Agents)  │  │  (Memory)  │  │  (Cache)   │      │
    │   └────────────┘  └────────────┘  └────────────┘      │
    │                                                        │
    └────────────────────────────────────────────────────────┘
```

### Tech Stack

| Layer | Technology |
|-------|------------|
| **Frontend** | React 18, Vite 6, Tailwind CSS 4, Three.js, react-force-graph-3d |
| **Backend** | Python 3.12, FastAPI, SQLAlchemy 2.0, Pydantic v2 |
| **Database** | PostgreSQL 15 (agents, tools, executions) |
| **Memory** | Qdrant + mem0 (vector storage, conversation memory) |
| **LLM** | OpenRouter, Anthropic, OpenAI, Local MLX |
| **Protocols** | A2A (Linux Foundation), MCP (Anthropic) |

---

## Real-World Examples

### Research + Email Workflow

Agent researches a topic and emails the results:

```bash
curl -X POST http://localhost:8100/api/v1/agents/col-finance/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Research AI agent market size 2026 and email summary to aaron@magicunicorn.tech"}'
```

**What happens internally:**
1. LLM decides to use `web_search` tool
2. Serper API returns market data (Deloitte, IBM research)
3. LLM synthesizes findings
4. LLM decides to use `email` tool
5. MS365 Graph API sends email via OAuth2
6. Returns confirmation with tool execution log

### External A2A Invocation

Another platform invokes your agent:

```bash
curl -X POST http://localhost:8100/api/v1/a2a/invoke \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "sgt-coder",
    "task": "Write a Python function to calculate compound interest",
    "tools": ["code"]
  }'
```

---

## 3D Orchestration

The General's command center provides real-time visualization:

- **Domain-colored nodes** - Agents grouped by specialty
- **Particle animations** - Data flow between collaborating agents
- **Live activity** - Pulsing nodes indicate active agents
- **Interactive controls** - Rotate, zoom, filter by domain

Access at `/orchestration` in the UI.

---

## Deployment

### Docker Compose

```yaml
services:
  brigade:
    build: .
    ports:
      - "8100:8100"
    environment:
      - DATABASE_URL=postgresql+asyncpg://user:pass@postgres:5432/brigade
      - QDRANT_URL=http://qdrant:6333
    depends_on:
      - postgres
      - qdrant

  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: unicorn_brigade
      POSTGRES_USER: user
      POSTGRES_PASSWORD: pass

  qdrant:
    image: qdrant/qdrant
    ports:
      - "6333:6333"
```

### Production URLs

- **Frontend**: https://brigade.unicorncommander.ai
- **API**: https://api.brigade.unicorncommander.ai

---

## Comparison

| Feature | Unicorn Brigade | LangChain | CrewAI |
|---------|----------------|-----------|--------|
| **Agent Builder UI** | Conversational (Gunny) | Code only | Code only |
| **Pre-built Agents** | 18 production-ready | None | None |
| **Real Email Integration** | MS365 Graph API | Manual | Manual |
| **Real Web Search** | Serper (works now) | Needs config | Needs config |
| **A2A Protocol** | Full support | No | No |
| **MCP Protocol** | Full support | Partial | No |
| **3D Visualization** | Yes (Three.js) | No | No |
| **Database Persistence** | PostgreSQL | In-memory | In-memory |
| **Production Deployed** | Yes | Framework only | Framework only |

---

## Roadmap

### Q1 2026
- [ ] Google Workspace email integration
- [ ] Slack tool
- [ ] Visual workflow builder
- [ ] Agent marketplace

### Q2 2026
- [ ] Voice interface
- [ ] Knowledge graphs (FalkorDB)
- [ ] Multi-tenant SaaS
- [ ] Advanced memory retrieval

---

## Contributing

```bash
# Setup dev environment
pip install -r requirements-dev.txt

# Run tests
pytest

# Lint
ruff check .

# Format
black .
```

PRs welcome. See [CONTRIBUTING.md](CONTRIBUTING.md).

---

## License

MIT - see [LICENSE](LICENSE)

---

## Support

- **Docs**: [docs/](docs/)
- **Issues**: [GitHub Issues](https://github.com/Unicorn-Commander/Unicorn-Brigade/issues)
- **Email**: support@magicunicorn.tech

---

<div align="center">

**Built by [Magic Unicorn Unconventional Technology & Stuff Inc](https://magicunicorn.tech)**

*"Where AI agents come to life"*

[![Star on GitHub](https://img.shields.io/github/stars/Unicorn-Commander/Unicorn-Brigade?style=social)](https://github.com/Unicorn-Commander/Unicorn-Brigade)

</div>
