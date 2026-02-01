# MCP & Tool Integration Plan - January 2026

## Priority 1: Core MCP Servers (This Week)

### 1. GitHub MCP Server
```bash
# Install official GitHub MCP
npm install @modelcontextprotocol/server-github

# Or via Claude Code
claude mcp add github -- npx -y @modelcontextprotocol/server-github
```
**Capabilities:** Commits, branches, PRs, issues, repo search
**Why:** Essential for development agents (cpt-fullstack, ssg-hopper)

### 2. Filesystem MCP Server
```bash
npm install @modelcontextprotocol/server-filesystem
```
**Capabilities:** Read, write, edit, search local files
**Why:** Foundation for code generation and file management

### 3. PostgreSQL MCP Server
```bash
npm install @modelcontextprotocol/server-postgres
```
**Capabilities:** Schema inspection, SQL queries, analytics
**Why:** We already use Postgres - enable AI querying of our data

### 4. Slack MCP Server (Upgrade)
```bash
# Most powerful community implementation
npm install @korotovsky/slack-mcp-server
```
**Capabilities:** Full workspace access, DMs, history, Apps support
**Why:** Replace basic integration with full MCP capabilities

---

## Priority 2: Browser & Code Execution (Next Week)

### 5. Playwright MCP Server
```bash
npm install @playwright/mcp
```
**Capabilities:** Browser control via accessibility tree (fast, reliable)
**Why:** AI-driven web automation without vision models

### 6. Code Sandbox Integration
**Option A: E2B (Recommended for production)**
```python
# requirements.txt
e2b>=1.0.0

# Usage
from e2b import Sandbox

sandbox = Sandbox()
result = sandbox.run_code("print('Hello from sandbox')")
```
- 150ms startup, Firecracker isolation
- $150/mo Pro tier

**Option B: Self-hosted Docker (Cost-effective)**
```yaml
# docker-compose.sandbox.yml
services:
  code-sandbox:
    image: svngoku/mcp-docker-code-interpreter
    ports:
      - "8200:8000"
    volumes:
      - sandbox-data:/data
```

---

## Priority 3: Knowledge & Data (Week 3)

### 7. Google Drive MCP Server
```bash
npm install @anthropic/mcp-server-google-drive
```
**Capabilities:** Search, summarize, organize cloud documents
**Requires:** Google Cloud OAuth setup

### 8. MongoDB MCP Server
```bash
npm install @mongodb-js/mongodb-mcp-server
```
**Capabilities:** NoSQL queries, document operations
**Why:** Expand beyond Postgres for document-heavy workflows

### 9. Enhanced RAG with LlamaIndex
```python
# requirements.txt
llama-index>=0.11.0
llama-index-vector-stores-qdrant>=0.3.0

# Integration with existing Qdrant
from llama_index.vector_stores.qdrant import QdrantVectorStore
from llama_index.core import VectorStoreIndex

vector_store = QdrantVectorStore(
    client=qdrant_client,
    collection_name="brigade_knowledge"
)
index = VectorStoreIndex.from_vector_store(vector_store)
```

---

## Priority 4: Enterprise Integrations (Week 4)

### 10. Jira/Linear MCP Server
```bash
# DX Heroes implementation (beta)
npm install @dx-heroes/mcp-server-jira-linear
```
**Capabilities:** Issue CRUD, sprint tracking, project management
**Why:** spc-qa and cpt-fullstack need project integration

### 11. HubSpot/Salesforce Connector
```python
# Use Composio for 500+ app integrations
pip install composio-core

from composio import ComposioToolSet
toolset = ComposioToolSet()
tools = toolset.get_tools(apps=["hubspot", "salesforce"])
```

### 12. Calendar Integration
```bash
npm install @anthropic/mcp-server-google-calendar
```
**Capabilities:** AI-powered scheduling, availability checking
**Why:** Mission coordination needs calendar awareness

---

## Architecture: MCP Registry in Unicorn Brigade

### New File: `app/mcp/registry.py`
```python
from typing import Dict, List, Optional
from dataclasses import dataclass
import subprocess
import asyncio

@dataclass
class MCPServer:
    name: str
    command: str
    args: List[str]
    env: Dict[str, str] = None
    capabilities: List[str] = None

class MCPRegistry:
    """Central registry for MCP servers"""

    SERVERS = {
        "github": MCPServer(
            name="GitHub",
            command="npx",
            args=["-y", "@modelcontextprotocol/server-github"],
            env={"GITHUB_TOKEN": "${GITHUB_TOKEN}"},
            capabilities=["repos", "issues", "prs", "commits"]
        ),
        "postgres": MCPServer(
            name="PostgreSQL",
            command="npx",
            args=["-y", "@modelcontextprotocol/server-postgres"],
            env={"DATABASE_URL": "${DATABASE_URL}"},
            capabilities=["query", "schema", "analytics"]
        ),
        "filesystem": MCPServer(
            name="Filesystem",
            command="npx",
            args=["-y", "@modelcontextprotocol/server-filesystem", "/workspace"],
            capabilities=["read", "write", "search", "edit"]
        ),
        "slack": MCPServer(
            name="Slack",
            command="npx",
            args=["-y", "@korotovsky/slack-mcp-server"],
            env={"SLACK_TOKEN": "${SLACK_BOT_TOKEN}"},
            capabilities=["channels", "messages", "search", "users"]
        ),
        "playwright": MCPServer(
            name="Playwright",
            command="npx",
            args=["-y", "@playwright/mcp"],
            capabilities=["navigate", "click", "type", "screenshot"]
        ),
    }

    def __init__(self):
        self.running_servers: Dict[str, subprocess.Popen] = {}

    async def start_server(self, name: str) -> bool:
        """Start an MCP server by name"""
        if name not in self.SERVERS:
            return False

        server = self.SERVERS[name]
        env = {**os.environ}
        if server.env:
            for key, value in server.env.items():
                if value.startswith("${"):
                    env_var = value[2:-1]
                    env[key] = os.getenv(env_var, "")
                else:
                    env[key] = value

        proc = subprocess.Popen(
            [server.command] + server.args,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        self.running_servers[name] = proc
        return True

    def list_available(self) -> List[Dict]:
        """List all available MCP servers"""
        return [
            {
                "name": name,
                "display_name": server.name,
                "capabilities": server.capabilities,
                "running": name in self.running_servers
            }
            for name, server in self.SERVERS.items()
        ]
```

### New API Endpoint: `app/api/mcp_registry_routes.py`
```python
from fastapi import APIRouter, HTTPException
from app.mcp.registry import MCPRegistry

router = APIRouter(prefix="/mcp/registry", tags=["MCP Registry"])
registry = MCPRegistry()

@router.get("/servers")
async def list_servers():
    """List all available MCP servers"""
    return {"servers": registry.list_available()}

@router.post("/servers/{name}/start")
async def start_server(name: str):
    """Start an MCP server"""
    if await registry.start_server(name):
        return {"status": "started", "server": name}
    raise HTTPException(404, f"Server {name} not found")

@router.post("/servers/{name}/stop")
async def stop_server(name: str):
    """Stop an MCP server"""
    if registry.stop_server(name):
        return {"status": "stopped", "server": name}
    raise HTTPException(404, f"Server {name} not running")
```

---

## Environment Variables to Add

```bash
# .env additions

# GitHub MCP
GITHUB_TOKEN=ghp_000000000000000000000000000000000000

# Google APIs
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
GOOGLE_DRIVE_FOLDER_ID=optional-folder-id

# Code Sandbox (E2B)
E2B_API_KEY=e2b_xxxxxxxxxxxx

# Slack MCP (upgrade)
SLACK_BOT_TOKEN=xoxb-000000000000-000000000000-000000000000-000000000000
SLACK_APP_TOKEN=xapp-xxxxxxxxxxxx

# Jira
JIRA_API_TOKEN=xxxxxxxxxxxx
JIRA_EMAIL=your-email@company.com
JIRA_URL=https://your-org.atlassian.net

# HubSpot
HUBSPOT_API_KEY=xxxxxxxxxxxx

# Composio (multi-app)
COMPOSIO_API_KEY=xxxxxxxxxxxx
```

---

## Docker Compose Addition

```yaml
# docker-compose.mcp.yml
version: '3.8'

services:
  # Code execution sandbox
  code-sandbox:
    image: svngoku/mcp-docker-code-interpreter
    ports:
      - "8200:8000"
    volumes:
      - sandbox-data:/data
    environment:
      - SANDBOX_TIMEOUT=300
    restart: unless-stopped

  # Browser automation
  browserless:
    image: browserless/chrome:latest
    ports:
      - "3333:3000"
    environment:
      - MAX_CONCURRENT_SESSIONS=10
      - CONNECTION_TIMEOUT=60000
    restart: unless-stopped

volumes:
  sandbox-data:
```

---

## Agent Tool Assignments

Update `data/seed_agents.json` to assign new MCP tools:

| Agent | New Tools to Add |
|-------|-----------------|
| cpt-fullstack | github, filesystem, code_sandbox |
| ssg-hopper | github, filesystem, code_sandbox |
| maj-devops | github, filesystem, shell |
| sgt-scraper | playwright, browserless |
| detective-holmes | playwright, web_search, google_drive |
| col-finance | hubspot, google_drive, calendar |
| lt-market | web_search, playwright, hubspot |
| mission-control | slack, calendar, jira |
| the-general | All orchestration tools |

---

## Testing New Integrations

```python
# scripts/test_mcp_servers.py
import asyncio
import httpx

async def test_mcp_servers():
    """Test all MCP server integrations"""

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Test GitHub MCP
        r = await client.post(
            "http://localhost:8100/api/v1/mcp/request",
            json={
                "method": "tools/call",
                "params": {
                    "name": "github_search_repos",
                    "arguments": {"query": "langgraph"}
                }
            }
        )
        print(f"GitHub MCP: {r.status_code}")

        # Test Filesystem MCP
        r = await client.post(
            "http://localhost:8100/api/v1/mcp/request",
            json={
                "method": "tools/call",
                "params": {
                    "name": "read_file",
                    "arguments": {"path": "/workspace/README.md"}
                }
            }
        )
        print(f"Filesystem MCP: {r.status_code}")

        # Test Code Sandbox
        r = await client.post(
            "http://localhost:8200/execute",
            json={
                "code": "print('Hello from sandbox')",
                "language": "python"
            }
        )
        print(f"Code Sandbox: {r.status_code}")

if __name__ == "__main__":
    asyncio.run(test_mcp_servers())
```

---

## Summary: What This Enables

1. **Development Workflows**: GitHub + Filesystem + Code Sandbox = AI pair programming
2. **Research & Analysis**: Google Drive + Web Search + Playwright = Deep research agents
3. **Enterprise Integration**: Slack + Jira + HubSpot = Business automation
4. **Real-time Knowledge**: LlamaIndex + Qdrant + Graphiti = Persistent agent memory
5. **Browser Automation**: Playwright MCP = Web scraping, form filling, testing

## Next Steps

1. Run `npm install` for MCP servers
2. Add environment variables
3. Update docker-compose with sandbox services
4. Update agent tool assignments
5. Run integration tests

---

*Last Updated: January 30, 2026*
