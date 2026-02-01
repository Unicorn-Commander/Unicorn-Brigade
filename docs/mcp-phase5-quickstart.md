# MCP Phase 5 Quick Start Guide
## Intercom, Asana, Trello, QuickBooks

**Integration Date**: January 31, 2026
**Status**: Complete
**Total Servers**: 30 (10 baseline + 4 Phase 1 + 4 Phase 2 + 4 Phase 3 + 4 Phase 4 + 4 Phase 5)
**Phase 5 Tools**: 150 new capabilities

---

## Overview

Phase 5 adds 4 versatile MCP servers focused on customer messaging, team collaboration, visual project management, and financial automation:

| Server | Type | Tools | Priority |
|--------|------|-------|----------|
| **Intercom** | Customer Messaging & Support | 35 | MEDIUM-HIGH |
| **Asana** | Team Collaboration & Work Management | 36 | MEDIUM |
| **Trello** | Visual Project Management | 35 | MEDIUM |
| **QuickBooks** | Accounting & Financial Management | 44 | MEDIUM-HIGH |

---

## 1. Intercom Customer Messaging

### What It Does
Complete customer messaging platform combining live chat, support tickets, help center, and proactive messaging for unified customer engagement.

### Configuration

```bash
# .env
INTERCOM_ACCESS_TOKEN=dG9rOmxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
INTERCOM_APP_ID=xxxxxxxx
```

**Access Token**:
- Developer access token with full permissions
- Format: Starts with `dG9r` (base64 encoded)

**Get Credentials**: https://app.intercom.com/a/apps/YOUR_APP_ID/developer-hub/app-packages
1. Go to Developer Hub in Intercom Settings
2. Create a new Developer App
3. Configure required scopes (see below)
4. Generate access token from app credentials
5. Copy App ID from app settings (General section)

**Required Scopes**:
- Read and manage conversations
- Read and manage contacts
- Read and manage messages
- Read and manage tickets
- Read and manage articles
- Read and manage companies
- Read teams and admins

### Key Capabilities (35 tools)

**Conversation Management**:
- `create_conversation`, `get_conversation`, `list_conversations`, `reply_to_conversation`, `close_conversation`
- `assign_conversation`, `snooze_conversation`, `tag_conversation`

**Contact Management**:
- `create_contact`, `update_contact`, `delete_contact`, `get_contact`, `search_contacts`, `merge_contacts`

**Messaging**:
- `send_message`, `send_email`

**Support Tickets**:
- `create_ticket`, `update_ticket`, `get_ticket`, `list_tickets`

**Tagging & Organization**:
- `add_tag`, `remove_tag`, `list_tags`
- `create_note`, `list_notes`

**Team Management**:
- `list_teams`, `list_admins`

**Help Center**:
- `create_article`, `update_article`, `get_article`, `search_articles`

**Company Management**:
- `get_company`, `create_company`, `update_company`, `list_companies`

### Use Cases

✅ **Live Chat Support** - Real-time customer conversations
✅ **Customer Messaging** - Proactive outreach and engagement
✅ **Product Tours** - Onboarding flows and feature discovery
✅ **Support Tickets** - Structured issue tracking
✅ **Help Center** - Self-service knowledge base
✅ **Multi-Channel Communication** - Email, chat, in-app messaging
✅ **Customer Segmentation** - Targeted messaging campaigns
✅ **Automated Messaging** - Triggered campaigns and workflows

### Example Workflow

```python
# Customer support agent with Intercom
agent = {
    "name": "customer-engagement",
    "mcp_servers": ["intercom", "zendesk", "slack", "twilio"],
    "instructions": "Handle customer conversations and support tickets across channels"
}

# Sample tasks:
# "Reply to open Intercom conversations from VIP customers"
# "Create support ticket for customer issue and assign to team"
# "Send proactive message to customers who haven't logged in for 30 days"
# "Search help center articles about billing issues"
# "Create conversation note with customer context from CRM"
# "Tag conversations by topic and urgency level"
```

---

## 2. Asana Work Management

### What It Does
Flexible work management platform for task tracking, project organization, portfolio management, and goal setting (OKRs) across teams.

### Configuration

```bash
# .env
ASANA_ACCESS_TOKEN=1/xxxxxxxxxxxxxxxxxxxxxxxxxxxx:xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
ASANA_WORKSPACE_GID=REMOVED
```

**Access Token**:
- Personal access token with full permissions
- Format: Starts with `1/` followed by long alphanumeric string

**Workspace GID**:
- Global identifier for your Asana workspace
- Found in URL: https://app.asana.com/0/WORKSPACE_GID

**Get Credentials**: https://app.asana.com/0/my-apps
1. Go to Asana My Apps page
2. Click "Create new personal access token"
3. Give it a descriptive name (e.g., "Unicorn Brigade Integration")
4. Copy the token immediately (shown only once!)
5. Get Workspace GID from workspace URL or API

**Required Permissions**:
- Full access to tasks, projects, portfolios, goals
- Read and write access to workspace data
- Team and user information access

### Key Capabilities (36 tools)

**Task Management**:
- `create_task`, `update_task`, `delete_task`, `get_task`, `search_tasks`, `duplicate_task`
- `add_comment`, `list_comments`

**Project Management**:
- `create_project`, `update_project`, `delete_project`, `get_project`, `list_projects`, `duplicate_project`
- `create_section`, `update_section`, `delete_section`, `list_sections`

**Task-Project Relationships**:
- `add_task_to_project`, `remove_task_from_project`, `move_task`

**Portfolio Management**:
- `create_portfolio`, `update_portfolio`, `list_portfolios`

**Goal Tracking**:
- `create_goal`, `update_goal`, `list_goals`

**Team & Workspace**:
- `list_teams`, `get_team`
- `list_workspaces`, `get_workspace`
- `list_users`, `get_user`

**Tagging**:
- `add_tag`, `remove_tag`, `list_tags`

### Use Cases

✅ **Team Task Management** - Coordinated task tracking across teams
✅ **Cross-Functional Workflows** - Shared projects and dependencies
✅ **Portfolio Management** - Multiple projects and programs
✅ **Goal Tracking (OKRs)** - Objectives and key results alignment
✅ **Marketing Campaigns** - Campaign planning and execution
✅ **Product Roadmaps** - Feature planning and prioritization
✅ **Team Collaboration** - Comments, assignments, due dates
✅ **Work Requests** - Intake and triage workflows

### Example Workflow

```python
# Team collaboration agent with Asana
agent = {
    "name": "project-coordinator",
    "mcp_servers": ["asana", "slack", "github", "google-drive"],
    "instructions": "Coordinate team projects, tasks, and deliverables"
}

# Sample tasks:
# "Create new project for Q1 marketing campaign with 10 tasks"
# "Assign high-priority tasks to team members by expertise"
# "Search for overdue tasks and notify assignees via Slack"
# "Create portfolio for product launch with 3 sub-projects"
# "Update goal progress and add milestone completions"
# "Duplicate last quarter's project structure for new quarter"
```

---

## 3. Trello Visual Project Management

### What It Does
Visual kanban boards for simple, intuitive project tracking with cards, lists, checklists, and labels for team collaboration.

### Configuration

```bash
# .env
TRELLO_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TRELLO_API_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

**API Key**:
- 32-character alphanumeric key
- Unique per Trello account

**API Token**:
- 64-character alphanumeric token
- Generated per application with expiration options

**Get Credentials**: https://trello.com/power-ups/admin
1. Visit Trello API Key page: https://trello.com/app-key
2. Copy your API Key (shown at top)
3. Click "Token" link to generate token
4. Authorize the application (choose expiration: 1 day, 30 days, never)
5. Copy the generated token immediately

**Required Permissions**:
- Read and write access to boards
- Read and write access to cards and lists
- Member and organization access

### Key Capabilities (35 tools)

**Board Management**:
- `create_board`, `update_board`, `delete_board`, `get_board`, `list_boards`

**List Management**:
- `create_list`, `update_list`, `archive_list`, `get_list`, `list_lists`

**Card Management**:
- `create_card`, `update_card`, `delete_card`, `get_card`, `list_cards`, `move_card`

**Comments**:
- `add_comment`, `update_comment`, `delete_comment`, `list_comments`

**Member Management**:
- `add_member`, `remove_member`, `list_members`

**Labels**:
- `create_label`, `update_label`, `delete_label`, `list_labels`, `add_label_to_card`

**Checklists**:
- `create_checklist`, `update_checklist`, `delete_checklist`, `list_checklists`

**Attachments**:
- `add_attachment`, `delete_attachment`, `list_attachments`

### Use Cases

✅ **Visual Kanban Boards** - Drag-and-drop workflow management
✅ **Simple Project Tracking** - Lightweight task management
✅ **Content Calendars** - Editorial planning and scheduling
✅ **Sales Pipelines** - Lead and opportunity tracking
✅ **Personal Organization** - To-do lists and task boards
✅ **Team Collaboration** - Shared boards and assignments
✅ **Event Planning** - Coordination and task delegation
✅ **Agile Workflows** - Sprint boards and backlogs

### Example Workflow

```python
# Visual project management agent with Trello
agent = {
    "name": "kanban-coordinator",
    "mcp_servers": ["trello", "slack", "google-drive", "github"],
    "instructions": "Manage visual project boards and move work through stages"
}

# Sample tasks:
# "Create new board for product launch with lists: Backlog, To Do, In Progress, Review, Done"
# "Create cards from GitHub issues and add to backlog list"
# "Move all cards in 'In Progress' that are older than 7 days to 'Review'"
# "Add checklist to card with sub-tasks from project requirements"
# "Apply red label to high-priority cards and notify team via Slack"
# "Add team members to board and assign cards by specialty"
```

---

## 4. QuickBooks Accounting

### What It Does
Small business accounting platform for invoice generation, payment tracking, expense management, and financial reporting.

### Configuration

```bash
# .env
QUICKBOOKS_CLIENT_ID=ABxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
QUICKBOOKS_CLIENT_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
QUICKBOOKS_REALM_ID=REMOVED
QUICKBOOKS_REFRESH_TOKEN=AB11xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

**Client ID & Secret**:
- OAuth2 credentials from Intuit Developer Dashboard
- Client ID starts with `AB`
- Used for authentication

**Realm ID**:
- Company ID for QuickBooks company
- Found in QuickBooks URL or OAuth callback
- Numeric identifier

**Refresh Token**:
- Long-lived token for API access
- Obtained via OAuth2 authorization code flow
- Must be refreshed periodically

**Get Credentials**: https://developer.intuit.com/app/developer/qbo/docs/get-started
1. Create Intuit Developer account
2. Create new app in Developer Dashboard
3. Configure OAuth2 redirect URIs
4. Copy Client ID and Client Secret from Keys & credentials
5. Implement OAuth2 flow to get authorization code
6. Exchange code for access and refresh tokens
7. Get Realm ID from OAuth callback or company settings
8. Store refresh token for long-term access

**Required Scopes**:
- `com.intuit.quickbooks.accounting` (full accounting access)

### Key Capabilities (44 tools)

**Invoice Management**:
- `create_invoice`, `update_invoice`, `delete_invoice`, `get_invoice`, `list_invoices`, `send_invoice`

**Payment Processing**:
- `create_payment`, `update_payment`, `get_payment`, `list_payments`

**Customer Management**:
- `create_customer`, `update_customer`, `delete_customer`, `get_customer`, `list_customers`, `search_customers`

**Vendor Management**:
- `create_vendor`, `update_vendor`, `delete_vendor`, `get_vendor`, `list_vendors`

**Bill Management**:
- `create_bill`, `update_bill`, `delete_bill`, `get_bill`, `list_bills`

**Estimate Management**:
- `create_estimate`, `update_estimate`, `get_estimate`, `list_estimates`, `send_estimate`

**Expense Tracking**:
- `create_expense`, `update_expense`, `get_expense`, `list_expenses`

**Purchase Orders**:
- `create_purchase_order`, `update_purchase_order`, `get_purchase_order`

**Financial Reports**:
- `get_profit_loss_report`, `get_balance_sheet_report`, `get_cash_flow_report`

**Chart of Accounts**:
- `list_accounts`, `get_account`, `create_account`

### Use Cases

✅ **Small Business Accounting** - Complete bookkeeping automation
✅ **Invoice Generation** - Automated billing and invoicing
✅ **Payment Tracking** - Reconciliation and accounts receivable
✅ **Expense Management** - Categorization and tracking
✅ **Vendor Bill Processing** - Accounts payable automation
✅ **Customer Payment Reconciliation** - Cash flow management
✅ **Financial Reporting** - P&L, balance sheet, cash flow
✅ **Tax Preparation** - Organized records for tax compliance

### Example Workflow

```python
# Financial automation agent with QuickBooks
agent = {
    "name": "finance-automation",
    "mcp_servers": ["quickbooks", "stripe", "shopify", "twilio"],
    "instructions": "Automate financial operations and reporting"
}

# Sample tasks:
# "Create invoice for customer from Shopify order and send via email"
# "Record payment from Stripe and reconcile with invoice"
# "Create expense records for all vendor bills from last week"
# "Generate profit & loss report for current month"
# "Send payment reminder SMS via Twilio for overdue invoices"
# "Create estimate for new customer and track approval status"
```

---

## Multi-Server Workflows

### Customer Support Escalation
**Servers**: Intercom + Zendesk + Slack + Twilio

```python
workflow = {
    "name": "Multi-Channel Support Escalation",
    "steps": [
        "Intercom: Customer starts live chat conversation",
        "Intercom: AI agent provides initial response and troubleshooting",
        "Intercom: Escalate complex technical issue to support team",
        "Zendesk: Create support ticket with conversation context",
        "Slack: Notify support team channel with ticket details",
        "Twilio: Send SMS acknowledgment to customer with ticket number",
        "Intercom: Update conversation with Zendesk ticket link",
        "Zendesk: Support agent resolves issue and closes ticket",
        "Intercom: Close conversation with satisfaction survey"
    ]
}
```

### Team Project Management
**Servers**: Asana + Trello + Slack + GitHub

```python
workflow = {
    "name": "Cross-Platform Project Coordination",
    "steps": [
        "Asana: Create project and break down into granular tasks",
        "Trello: Create visual kanban board for team workflow",
        "Asana: Assign tasks to developers with due dates and priorities",
        "Slack: Notify team of new assignments and project kickoff",
        "GitHub: Create feature branches for development tasks",
        "Trello: Team moves cards through workflow (To Do → In Progress → Done)",
        "Asana: Update task progress percentages and add status comments",
        "GitHub: Link pull requests to Asana task IDs in PR description",
        "Slack: Post daily standup summary from Asana and Trello",
        "Asana: Mark project complete when all tasks done"
    ]
}
```

### Financial Automation
**Servers**: QuickBooks + Stripe + Shopify + Twilio

```python
workflow = {
    "name": "End-to-End Financial Workflow",
    "steps": [
        "Shopify: Customer places order for products",
        "Stripe: Process credit card payment and capture funds",
        "QuickBooks: Create invoice record automatically from order",
        "QuickBooks: Record payment and reconcile with Stripe payout",
        "Shopify: Update order status to fulfilled after payment",
        "QuickBooks: Create expense records for cost of goods sold",
        "Twilio: Send payment confirmation SMS with receipt to customer",
        "QuickBooks: Categorize expenses by product line and department",
        "QuickBooks: Generate monthly profit & loss report",
        "QuickBooks: Track cash flow, accounts receivable, and aging"
    ]
}
```

### Marketing Campaign Management
**Servers**: Asana + Intercom + HubSpot + Slack

```python
workflow = {
    "name": "Marketing Campaign Planning and Execution",
    "steps": [
        "Asana: Create campaign project with tasks, timeline, and deliverables",
        "Asana: Assign content creation, design, copy, and approval tasks",
        "HubSpot: Set up email automation sequence with segmented lists",
        "Intercom: Create in-app product tour for new feature announcement",
        "Asana: Track task completion and move to review stage",
        "HubSpot: Launch email campaign to customer segments",
        "Intercom: Trigger in-app messaging for active users",
        "Slack: Post real-time campaign performance metrics",
        "Asana: Mark campaign complete and create post-mortem task",
        "Asana: Document learnings and best practices for next campaign"
    ]
}
```

---

## Testing Phase 5 Servers

### 1. Start MCP Server

```bash
# Start Intercom server
curl -X POST http://localhost:8100/api/v1/mcp/registry/servers/intercom/start

# Check if running
curl http://localhost:8100/api/v1/mcp/registry/servers/running
```

### 2. Call Tool Directly

```bash
# List Intercom conversations
curl -X POST http://localhost:8100/api/v1/mcp/registry/tools/call \
  -H "Content-Type: application/json" \
  -d '{
    "server_name": "intercom",
    "tool_name": "list_conversations",
    "arguments": {
      "limit": 10,
      "order": "desc"
    }
  }'

# Create Asana task
curl -X POST http://localhost:8100/api/v1/mcp/registry/tools/call \
  -H "Content-Type: application/json" \
  -d '{
    "server_name": "asana",
    "tool_name": "create_task",
    "arguments": {
      "name": "Complete Phase 5 integration",
      "notes": "Add 4 new MCP servers to platform"
    }
  }'
```

### 3. Assign to Agent

```bash
# Create customer engagement agent with Phase 5 servers
curl -X POST http://localhost:8100/api/v1/agents \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "customer-engagement",
    "name": "Customer Engagement Specialist",
    "role": "Multi-Channel Customer Support",
    "tools": ["intercom", "zendesk", "slack", "twilio"],
    "instructions": "Handle customer conversations, support tickets, and proactive messaging"
  }'
```

---

## Environment Setup Checklist

### Intercom
- [ ] Create Intercom account or access existing workspace
- [ ] Navigate to Developer Hub in Settings
- [ ] Create new Developer App with required scopes
- [ ] Configure permissions: conversations, contacts, messages, tickets, articles, companies
- [ ] Generate access token from app credentials
- [ ] Copy App ID from app settings (General section)
- [ ] Add both variables to `.env`
- [ ] Test with Intercom API explorer

### Asana
- [ ] Create Asana account or access existing workspace
- [ ] Navigate to https://app.asana.com/0/my-apps
- [ ] Click "Create new personal access token"
- [ ] Give token a descriptive name
- [ ] Copy token immediately (shown only once!)
- [ ] Get Workspace GID from URL or API call
- [ ] Add both variables to `.env`
- [ ] Verify token works with API test request

### Trello
- [ ] Create Trello account or access existing
- [ ] Navigate to https://trello.com/app-key
- [ ] Copy API Key from top of page
- [ ] Click "Token" link to generate token
- [ ] Choose expiration (never for production)
- [ ] Authorize application access
- [ ] Copy generated token immediately
- [ ] Add both variables to `.env`
- [ ] Test with Trello API

### QuickBooks
- [ ] Create Intuit Developer account
- [ ] Create new app in Developer Dashboard
- [ ] Configure OAuth2 settings and redirect URIs
- [ ] Copy Client ID and Client Secret
- [ ] Implement OAuth2 authorization code flow
- [ ] Exchange authorization code for tokens
- [ ] Get Realm ID from OAuth callback
- [ ] Store refresh token securely
- [ ] Add all four variables to `.env`
- [ ] Test authentication with QuickBooks API
- [ ] Set up token refresh mechanism

---

## Platform Coverage After Phase 5

| Category | Servers |
|----------|---------|
| **Databases** | PostgreSQL, Airtable, Supabase, MongoDB |
| **E-Commerce** | Shopify, Stripe |
| **Accounting** | QuickBooks |
| **CRM** | Salesforce, HubSpot |
| **Project Management** | Jira, Linear, Notion, Asana, Trello |
| **Customer Support** | Zendesk, Intercom |
| **Deployment** | Vercel, Cloudflare |
| **Version Control** | GitHub, Git |
| **Payments** | Stripe |
| **Collaboration** | Slack, Notion, Asana |
| **Storage** | Google Drive, Cloudflare R2, Supabase Storage |
| **Edge Computing** | Cloudflare Workers, Vercel Functions |
| **Communications** | Twilio, Intercom |
| **Monitoring** | Sentry |
| **Marketing** | HubSpot, Salesforce |
| **Messaging** | Intercom, Slack |

---

## Industry-Specific Coverage

### Customer Support
**Servers**: Intercom, Zendesk, Twilio, Slack, HubSpot
**Capabilities**: Live chat, ticketing, multi-channel communication, help center, customer data

### Team Collaboration
**Servers**: Asana, Trello, Slack, Notion, Linear
**Capabilities**: Task management, project tracking, communication, documentation, workflows

### Financial Management
**Servers**: QuickBooks, Stripe, Shopify, Salesforce
**Capabilities**: Invoicing, payments, expense tracking, reporting, reconciliation

### Project Management
**Servers**: Asana, Trello, Jira, Linear, Notion
**Capabilities**: Task tracking, sprint planning, kanban boards, goals, roadmaps

### Marketing Automation
**Servers**: HubSpot, Salesforce, Intercom, Twilio
**Capabilities**: Campaigns, lead nurturing, messaging, email/SMS, engagement

### Small Business
**Servers**: QuickBooks, Stripe, Shopify, Trello, Asana
**Capabilities**: Accounting, payments, e-commerce, project tracking, team coordination

---

## Metrics

- **Total Servers**: 30 (10 baseline + 4×5 phases)
- **Phase 5 Tools**: 150 new capabilities
- **Platform Tools**: 651 total capabilities
- **Average Tools/Server**: 38 (Phase 5)
- **Server Growth**: +15.4% vs Phase 4

---

## Next Steps

### Immediate
1. Configure production API keys for all Phase 5 servers
2. Test with live credentials (Intercom, Asana, Trello, QuickBooks)
3. Create example workflows combining Phase 5 servers
4. Test customer support workflow with Intercom + Zendesk

### Short-term
1. Build multi-channel support workflow (Intercom + Zendesk + Twilio)
2. Create team collaboration workflow (Asana + Trello + Slack)
3. Implement financial automation (QuickBooks + Stripe + Shopify)
4. Add visual project management (Trello + GitHub + Asana)
5. Add frontend UI for Phase 5 server management

### Medium-term
1. Plan Phase 6 servers (Mailchimp, ActiveCampaign, Calendly, DocuSign)
2. Build specialized agent templates using Phase 5 servers
3. Create cross-phase orchestration examples
4. Develop industry-specific workflows (support, marketing, finance)
5. Build phase-specific agent presets for common use cases

---

## Integration Highlights

### Intercom
- **Why**: Complete customer messaging platform with live chat and support
- **Best For**: Customer engagement, support ticketing, proactive messaging
- **Power Move**: Unified inbox for all customer conversations across channels
- **Scales**: Millions of conversations, enterprise support teams

### Asana
- **Why**: Flexible work management for cross-functional teams
- **Best For**: Task tracking, portfolio management, goal setting (OKRs)
- **Power Move**: Portfolio-level visibility across multiple projects
- **Scales**: Thousands of teams, millions of tasks

### Trello
- **Why**: Visual kanban boards for intuitive project tracking
- **Best For**: Simple workflows, content calendars, sales pipelines
- **Power Move**: Drag-and-drop simplicity with powerful automation
- **Scales**: Millions of boards, unlimited cards and lists

### QuickBooks
- **Why**: Industry-standard small business accounting
- **Best For**: Invoice automation, expense tracking, financial reporting
- **Power Move**: Complete bookkeeping automation from order to payment
- **Scales**: Small businesses to mid-market companies

---

## Resources

- **MCP Registry**: https://registry.modelcontextprotocol.io/
- **MCP Documentation**: https://modelcontextprotocol.io
- **Phase 5 Status**: `docs/mcp-phase5-status.json`
- **Intercom API Docs**: https://developers.intercom.com/
- **Asana API Docs**: https://developers.asana.com/
- **Trello API Docs**: https://developer.atlassian.com/cloud/trello/
- **QuickBooks API Docs**: https://developer.intuit.com/app/developer/qbo/docs/

---

**Last Updated**: January 31, 2026
**Status**: Production Ready
**Team**: MCP Phase 5 Integration Team Lead (Claude Sonnet 4.5)
