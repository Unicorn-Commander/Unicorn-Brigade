# MCP Phase 1 Quick Start Guide

## Overview

4 new MCP servers added to Unicorn Brigade (January 2026):

| Server | Tools | Purpose |
|--------|-------|---------|
| **Stripe** | 29 | Payment processing, subscriptions, customers |
| **Linear** | 24 | Issue tracking, project management |
| **Git** | 20 | Local repository operations |
| **Notion** | 15 | Workspace, knowledge base, collaboration |

**Total MCP Servers**: 14 (10 baseline + 4 Phase 1)

---

## Quick Setup

### 1. Get API Keys

```bash
# Stripe (required for payment features)
# Get from: https://dashboard.stripe.com/apikeys
STRIPE_API_KEY=sk_test_000000000000000000000000

# Linear (required for issue tracking)
# Get from: https://linear.app/settings/api
LINEAR_API_KEY=lin_api_...

# Notion (required for workspace features)
# Get from: https://www.notion.so/my-integrations
NOTION_API_KEY=secret_...

# Git (no API key needed - uses local repos)
```

### 2. Update .env

```bash
cd /Volumes/Studio\ Storage/Development/Unicorn-Brigade
cp .env.example .env
# Edit .env and add your API keys
```

### 3. Start the API Server

```bash
# From project root
source venv/bin/activate
uvicorn app.main:app --reload --port 8100
```

### 4. Start MCP Servers

```bash
# Start all Phase 1 servers
curl -X POST http://localhost:8100/api/v1/mcp/registry/servers/stripe/start
curl -X POST http://localhost:8100/api/v1/mcp/registry/servers/linear/start
curl -X POST http://localhost:8100/api/v1/mcp/registry/servers/git/start
curl -X POST http://localhost:8100/api/v1/mcp/registry/servers/notion/start

# Or start on-demand (servers auto-start when tools are called)
```

---

## Example Usage

### Stripe: Create Payment Intent

```bash
curl -X POST http://localhost:8100/api/v1/mcp/registry/tools/call \
  -H "Content-Type: application/json" \
  -d '{
    "server": "stripe",
    "tool": "create_payment_intent",
    "arguments": {
      "amount": 2000,
      "currency": "usd",
      "description": "Test payment"
    }
  }'
```

### Linear: Create Issue

```bash
# First, get your team ID
curl -X POST http://localhost:8100/api/v1/mcp/registry/tools/call \
  -H "Content-Type: application/json" \
  -d '{
    "server": "linear",
    "tool": "list_teams",
    "arguments": {}
  }'

# Then create an issue
curl -X POST http://localhost:8100/api/v1/mcp/registry/tools/call \
  -H "Content-Type: application/json" \
  -d '{
    "server": "linear",
    "tool": "create_issue",
    "arguments": {
      "teamId": "YOUR_TEAM_ID",
      "title": "Test issue from Unicorn Brigade",
      "description": "Created via MCP integration"
    }
  }'
```

### Git: Check Repository Status

```bash
curl -X POST http://localhost:8100/api/v1/mcp/registry/tools/call \
  -H "Content-Type: application/json" \
  -d '{
    "server": "git",
    "tool": "git_status",
    "arguments": {}
  }'
```

### Notion: Search Workspace

```bash
curl -X POST http://localhost:8100/api/v1/mcp/registry/tools/call \
  -H "Content-Type: application/json" \
  -d '{
    "server": "notion",
    "tool": "search",
    "arguments": {
      "query": "meeting notes",
      "filter": {
        "value": "page",
        "property": "object"
      }
    }
  }'
```

---

## Agent Integration

### Assign MCP Servers to Agents

```python
# Example: Configure Financial Analysis agent with Stripe
from app.db.repositories import AgentRepository

agent = await agent_repo.get_by_id("col-finance")
agent.mcp_servers = ["stripe"]
await agent_repo.update(agent)
```

### Use in Agent Conversations

```bash
# Chat with agent - tools are auto-invoked
curl -X POST http://localhost:8100/api/v1/agents/col-finance/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Show me total revenue for last month"
  }'
```

The agent will automatically use Stripe MCP tools to fetch and analyze revenue data.

---

## API Endpoints

### Server Management

```bash
# List all servers
GET /api/v1/mcp/registry/servers

# List running servers
GET /api/v1/mcp/registry/servers/running

# Get server details
GET /api/v1/mcp/registry/servers/{name}

# Start server
POST /api/v1/mcp/registry/servers/{name}/start

# Stop server
POST /api/v1/mcp/registry/servers/{name}/stop

# Health check
GET /api/v1/mcp/registry/health
```

### Tool Invocation

```bash
# Call a tool
POST /api/v1/mcp/registry/tools/call
{
  "server": "stripe",
  "tool": "create_customer",
  "arguments": {...}
}
```

---

## Troubleshooting

### Server won't start

1. Check API key is set: `echo $STRIPE_API_KEY`
2. Verify Node.js/npx installed: `npx --version`
3. Check logs: `GET /api/v1/mcp/registry/servers/stripe`

### Tool call fails

1. Ensure server is running: `GET /api/v1/mcp/registry/servers/running`
2. Check tool name is correct (case-sensitive)
3. Validate arguments match tool schema

### Permission errors (Notion)

1. Share pages with integration in Notion UI
2. Verify integration has correct permissions
3. Wait a few seconds after sharing for sync

---

## Tool Reference

### Stripe (29 tools)

**Payments**: create_payment_intent, capture_payment_intent, cancel_payment_intent
**Customers**: create_customer, update_customer, retrieve_customer, list_customers, search_customers
**Subscriptions**: create_subscription, update_subscription, cancel_subscription, retrieve_subscription, search_subscriptions
**Invoices**: create_invoice, send_invoice, retrieve_invoice, list_invoices, search_invoices
**Products**: create_product, update_product, list_products
**Prices**: create_price, update_price, list_prices
**Balance**: retrieve_balance, list_balance_transactions
**Refunds**: create_refund, retrieve_refund, list_refunds

### Linear (24 tools)

**Issues**: create_issue, update_issue, delete_issue, get_issue, search_issues
**Comments**: add_comment, update_comment, delete_comment
**Projects**: create_project, update_project, list_projects
**Teams**: list_teams, get_team
**Users**: list_users, get_user
**Labels**: create_label, list_labels
**Workflows**: list_workflows, list_workflow_states
**Cycles**: list_cycles, get_cycle
**Milestones**: create_milestone, list_milestones
**Organization**: get_organization

### Git (20 tools)

**Status**: git_status, git_diff, git_log, git_show
**Staging**: git_add, git_reset
**Commits**: git_commit, git_blame
**Branches**: git_branch, git_checkout, git_merge
**Remotes**: git_remote, git_fetch, git_pull, git_push
**Tags**: git_tag
**Search**: git_grep, search_repository, file_history
**Reading**: read_repository

### Notion (15 tools)

**Pages**: create_page, update_page, retrieve_page, archive_page
**Databases**: create_database, update_database, query_database, retrieve_database
**Search**: search
**Users**: list_users, retrieve_user
**Blocks**: append_block_children, retrieve_block_children
**Comments**: create_comment, retrieve_comments

---

## Next Steps

1. Configure API keys in production `.env`
2. Test tool calls with real credentials
3. Assign MCP servers to appropriate agents
4. Build multi-server workflows (e.g., Stripe → Linear → Notion)
5. Monitor via Langfuse observability

---

**Quick Start Updated**: January 31, 2026
**Status**: Ready for testing with API credentials
