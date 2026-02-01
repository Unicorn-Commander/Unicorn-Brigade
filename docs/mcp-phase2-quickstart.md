# MCP Phase 2 Quick Start Guide
## Airtable, Vercel, Cloudflare, Supabase

**Integration Date**: January 31, 2026
**Status**: Complete
**Total Servers**: 18 (10 baseline + 4 Phase 1 + 4 Phase 2)
**Phase 2 Tools**: 99 new capabilities

---

## Overview

Phase 2 adds 4 high-value MCP servers focused on modern cloud infrastructure and flexible data management:

| Server | Type | Tools | Priority |
|--------|------|-------|----------|
| **Airtable** | Database | 19 | HIGH |
| **Vercel** | Deployment | 25 | MEDIUM-HIGH |
| **Cloudflare** | Edge Platform | 30 | MEDIUM-HIGH |
| **Supabase** | Backend | 25 | MEDIUM-HIGH |

---

## 1. Airtable Database

### What It Does
Flexible spreadsheet-database hybrid for structured data management with visual interface.

### Configuration

```bash
# .env
AIRTABLE_API_KEY=patYourAirtablePersonalAccessToken
AIRTABLE_BASE_ID=appYourAirtableBaseId
```

**Get API Key**: https://airtable.com/create/tokens
**Required Scopes**: `data.records:read`, `data.records:write`, `schema.bases:read`
**Get Base ID**: From URL `https://airtable.com/YOUR_BASE_ID/...`

### Key Capabilities (19 tools)

**Record Operations**:
- `create_record`, `update_record`, `delete_record`, `get_record`
- `list_records`, `query_records`, `search_records`
- `batch_create`, `batch_update`

**Schema Management**:
- `list_tables`, `get_table_schema`, `describe_table`
- `get_base_schema`, `list_bases`
- `create_field`, `update_field`, `delete_field`

**Views**:
- `get_view`, `list_views`

### Use Cases

✅ **CRM Data Management** - Customer records, lead tracking
✅ **Content Calendars** - Editorial planning, publishing schedules
✅ **Product Roadmaps** - Feature tracking, release planning
✅ **Data Collection** - Surveys, forms, structured input
✅ **Flexible Schemas** - No rigid database migrations needed

### Example Workflow

```python
# Agent with Airtable access
agent = {
    "name": "crm-manager",
    "mcp_servers": ["airtable"],
    "instructions": "Manage customer records in Airtable CRM base"
}

# Sample tasks:
# "Add new customer John Doe from Acme Corp to CRM"
# "Update customer status to 'Active' for all Q1 signups"
# "Generate report of all customers by industry"
```

---

## 2. Vercel Deployment

### What It Does
Frontend deployment platform with edge functions, domains, and environment management.

### Configuration

```bash
# .env
VERCEL_TOKEN=your_vercel_token
VERCEL_TEAM_ID=team_your_team_id  # Optional for team deployments
```

**Get Token**: https://vercel.com/account/tokens
**Required Permissions**: Deployment and project management
**Team ID**: Found in team settings URL (optional)

### Key Capabilities (25 tools)

**Deployment Lifecycle**:
- `deploy_project`, `create_deployment`, `get_deployment`, `list_deployments`
- `delete_deployment`, `cancel_deployment`, `promote_deployment`

**Project Management**:
- `list_projects`, `get_project`, `create_project`, `update_project`, `delete_project`

**Configuration**:
- `list_env_vars`, `create_env_var`, `update_env_var`, `delete_env_var`
- `list_domains`, `add_domain`, `remove_domain`, `verify_domain`

**Monitoring**:
- `get_deployment_logs`, `get_build_logs`, `get_function_logs`

**Team**:
- `list_teams`, `get_team`

### Use Cases

✅ **Automated Deployments** - CI/CD integration, PR previews
✅ **Preview Environments** - Feature branch deployments
✅ **Edge Function Management** - Deploy serverless functions
✅ **Domain Management** - DNS, SSL, custom domains
✅ **Environment Variables** - Config automation across environments
✅ **Deployment Monitoring** - Logs, metrics, debugging

### Example Workflow

```python
# DevOps agent with Vercel access
agent = {
    "name": "devops-deployer",
    "mcp_servers": ["vercel", "github", "slack"],
    "instructions": "Manage deployments and notify team on Slack"
}

# Sample tasks:
# "Deploy main branch to production"
# "Create preview deployment for PR #123"
# "Update NEXT_PUBLIC_API_URL env var to new endpoint"
# "Show deployment logs for failed build"
```

---

## 3. Cloudflare Edge Platform

### What It Does
Edge computing platform with Workers, KV storage, R2 object storage, DNS, and CDN.

### Configuration

```bash
# .env
CLOUDFLARE_API_TOKEN=your_cloudflare_api_token
CLOUDFLARE_ACCOUNT_ID=your_cloudflare_account_id
```

**Get API Token**: https://dash.cloudflare.com/profile/api-tokens
**Required Permissions**: Workers Scripts:Edit, Workers KV:Edit, R2:Edit, Zone:Read, DNS:Edit
**Account ID**: Dashboard URL or Workers overview

### Key Capabilities (30 tools)

**Workers (Edge Functions)**:
- `deploy_worker`, `create_worker`, `update_worker`, `delete_worker`
- `list_workers`, `get_worker`, `get_worker_logs`

**KV Storage (Key-Value)**:
- `kv_get`, `kv_put`, `kv_delete`, `kv_list`, `kv_list_namespaces`

**R2 (Object Storage)**:
- `r2_upload`, `r2_download`, `r2_delete`, `r2_list`, `r2_create_bucket`

**Zones & DNS**:
- `list_zones`, `get_zone`, `purge_cache`
- `create_dns_record`, `update_dns_record`, `delete_dns_record`, `list_dns_records`

**Analytics & Rules**:
- `get_analytics`, `get_firewall_events`, `get_zone_analytics`
- `create_page_rule`, `list_page_rules`, `update_page_rule`

### Use Cases

✅ **Edge Function Deployment** - Deploy Workers to 200+ locations
✅ **Global Data Caching** - KV for distributed caching
✅ **Object Storage** - R2 for large files, backups
✅ **DNS Automation** - Manage DNS records programmatically
✅ **Performance Optimization** - Cache purging, page rules
✅ **Analytics & Monitoring** - Traffic, firewall events
✅ **CDN Management** - Cache control, edge caching

### Example Workflow

```python
# Infrastructure agent with Cloudflare
agent = {
    "name": "edge-infrastructure",
    "mcp_servers": ["cloudflare", "github"],
    "instructions": "Deploy edge functions and manage DNS"
}

# Sample tasks:
# "Deploy worker script from GitHub repo to Cloudflare"
# "Create DNS A record pointing api.example.com to 1.2.3.4"
# "Purge cache for example.com"
# "Upload backup file to R2 bucket"
# "Get analytics for last 7 days"
```

---

## 4. Supabase Backend

### What It Does
Open-source Firebase alternative with PostgreSQL, authentication, storage, real-time, edge functions.

### Configuration

```bash
# .env
SUPABASE_URL=https://your-project-ref.supabase.co
SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...your_anon_key
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...your_service_role_key
```

**Get Credentials**: https://app.supabase.com/project/YOUR_PROJECT/settings/api
**Anon Key**: Safe for client-side (RLS policies apply)
**Service Role Key**: Admin access - keep secure, server-side only

### Key Capabilities (25 tools)

**Database**:
- `query_database`, `execute_sql`, `list_tables`, `describe_table`

**Authentication**:
- `auth_create_user`, `auth_update_user`, `auth_delete_user`, `auth_get_user`, `auth_list_users`
- `auth_send_magic_link`, `auth_verify_otp`, `auth_sign_out`

**Storage**:
- `storage_upload`, `storage_download`, `storage_delete`, `storage_list`
- `storage_create_bucket`, `storage_delete_bucket`, `storage_list_buckets`

**Real-time**:
- `realtime_subscribe`, `realtime_unsubscribe`, `realtime_broadcast`

**Edge Functions**:
- `edge_functions_invoke`, `edge_functions_list`, `edge_functions_deploy`

### Use Cases

✅ **Full-Stack App Development** - Backend in minutes
✅ **User Authentication** - Email, magic links, OTP
✅ **File Storage** - User uploads, CDN delivery
✅ **Real-Time Data Sync** - Live updates, collaborative features
✅ **Database Operations** - PostgreSQL queries, RLS policies
✅ **Edge Function Execution** - Serverless backend logic

### Example Workflow

```python
# Full-stack agent with Supabase
agent = {
    "name": "backend-orchestrator",
    "mcp_servers": ["supabase", "slack"],
    "instructions": "Manage backend operations and notify team"
}

# Sample tasks:
# "Create new user account for john@example.com"
# "Query users table for all active subscribers"
# "Upload profile image to avatars bucket"
# "Send magic link to user for passwordless login"
# "Subscribe to real-time updates on orders table"
```

---

## Multi-Server Workflows

### DevOps Pipeline
**Servers**: GitHub + Vercel + Cloudflare + Slack

```python
workflow = {
    "name": "Full Deployment Pipeline",
    "steps": [
        "Monitor GitHub for new commits",
        "Deploy to Vercel staging",
        "Run tests on preview URL",
        "Deploy Cloudflare Workers",
        "Update DNS records",
        "Notify team on Slack"
    ]
}
```

### Data Pipeline
**Servers**: Airtable + Supabase + Slack

```python
workflow = {
    "name": "Customer Data Sync",
    "steps": [
        "Fetch new customers from Airtable CRM",
        "Create user accounts in Supabase Auth",
        "Sync data to Supabase database",
        "Send welcome emails",
        "Notify sales team on Slack"
    ]
}
```

### Infrastructure Management
**Servers**: Cloudflare + Vercel + GitHub

```python
workflow = {
    "name": "Multi-Cloud Deployment",
    "steps": [
        "Pull latest code from GitHub",
        "Deploy frontend to Vercel",
        "Deploy Workers to Cloudflare",
        "Configure DNS and CDN",
        "Monitor analytics"
    ]
}
```

---

## Testing Phase 2 Servers

### 1. Start MCP Server

```bash
# Start Airtable server
curl -X POST http://localhost:8100/api/v1/mcp/registry/servers/airtable/start

# Check if running
curl http://localhost:8100/api/v1/mcp/registry/servers/running
```

### 2. Call Tool Directly

```bash
# List Airtable records
curl -X POST http://localhost:8100/api/v1/mcp/registry/tools/call \
  -H "Content-Type: application/json" \
  -d '{
    "server_name": "airtable",
    "tool_name": "list_records",
    "arguments": {
      "table_name": "Customers"
    }
  }'
```

### 3. Assign to Agent

```bash
# Create agent with Phase 2 servers
curl -X POST http://localhost:8100/api/v1/agents \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "devops-agent",
    "name": "DevOps Agent",
    "role": "Infrastructure Management",
    "tools": ["vercel", "cloudflare"],
    "instructions": "Deploy applications and manage edge infrastructure"
  }'
```

---

## Environment Setup Checklist

### Airtable
- [ ] Create personal access token at https://airtable.com/create/tokens
- [ ] Grant `data.records:read`, `data.records:write`, `schema.bases:read` scopes
- [ ] Copy Base ID from Airtable URL
- [ ] Add `AIRTABLE_API_KEY` and `AIRTABLE_BASE_ID` to `.env`

### Vercel
- [ ] Create token at https://vercel.com/account/tokens
- [ ] Add `VERCEL_TOKEN` to `.env`
- [ ] (Optional) Add `VERCEL_TEAM_ID` for team deployments

### Cloudflare
- [ ] Create API token at https://dash.cloudflare.com/profile/api-tokens
- [ ] Grant Workers, KV, R2, Zone, DNS permissions
- [ ] Get Account ID from dashboard
- [ ] Add `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID` to `.env`

### Supabase
- [ ] Create project at https://app.supabase.com
- [ ] Copy project URL from settings
- [ ] Copy `anon` key and `service_role` key
- [ ] Add all three variables to `.env`
- [ ] IMPORTANT: Never expose `service_role` key client-side

---

## Platform Coverage After Phase 2

| Category | Servers |
|----------|---------|
| **Databases** | PostgreSQL, Airtable, Supabase |
| **Deployment** | Vercel, Cloudflare |
| **Version Control** | GitHub, Git |
| **Project Management** | Linear, Notion |
| **Payments** | Stripe |
| **Collaboration** | Slack, Notion |
| **Storage** | Google Drive, Cloudflare R2, Supabase Storage |
| **Authentication** | Supabase Auth |
| **Edge Computing** | Cloudflare Workers, Vercel Functions |

---

## Metrics

- **Total Servers**: 18 (10 baseline + 4 Phase 1 + 4 Phase 2)
- **Phase 2 Tools**: 99 new capabilities
- **Platform Tools**: 187 total capabilities
- **Average Tools/Server**: 25 (Phase 2)
- **Server Growth**: +28.6% vs Phase 1

---

## Next Steps

### Immediate
1. Configure production API keys for all Phase 2 servers
2. Test with live credentials
3. Create example workflows combining Phase 2 servers

### Short-term
1. Build DevOps workflow (Vercel + Cloudflare + GitHub)
2. Create data pipeline (Airtable + Supabase)
3. Add frontend UI for Phase 2 server management
4. Document integration patterns

### Medium-term
1. Plan Phase 3 servers (MongoDB, Twilio, Sentry, HubSpot)
2. Build specialized agent templates using Phase 2 servers
3. Create multi-server orchestration examples

---

## Resources

- **MCP Registry**: https://registry.modelcontextprotocol.io/
- **MCP Documentation**: https://modelcontextprotocol.io
- **Phase 2 Status**: `docs/mcp-phase2-status.json`
- **Research**: `docs/mcp-servers-research-2026.md`

---

**Last Updated**: January 31, 2026
**Status**: Production Ready
**Team**: MCP Phase 2 Integration Team Lead (Claude Sonnet 4.5)
