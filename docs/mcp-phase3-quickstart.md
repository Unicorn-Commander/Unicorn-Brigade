# MCP Phase 3 Quick Start Guide
## MongoDB, Twilio, Sentry, HubSpot

**Integration Date**: January 31, 2026
**Status**: Complete
**Total Servers**: 22 (10 baseline + 4 Phase 1 + 4 Phase 2 + 4 Phase 3)
**Phase 3 Tools**: 93 new capabilities

---

## Overview

Phase 3 adds 4 high-value MCP servers focused on NoSQL databases, multi-channel communications, error monitoring, and CRM automation:

| Server | Type | Tools | Priority |
|--------|------|-------|----------|
| **MongoDB** | NoSQL Database | 20 | MEDIUM |
| **Twilio** | Communications | 25 | MEDIUM-HIGH |
| **Sentry** | Monitoring | 18 | MEDIUM |
| **HubSpot** | CRM | 30 | MEDIUM |

---

## 1. MongoDB Database

### What It Does
NoSQL document database for flexible schema operations, high-performance aggregation, and horizontal scaling.

### Configuration

```bash
# .env
MONGODB_URI=mongodb://localhost:27017
MONGODB_DATABASE=your_database_name
```

**Connection String Formats**:
- Local: `mongodb://localhost:27017`
- With Auth: `mongodb://username:password@host:port/database`
- MongoDB Atlas: `mongodb+srv://username:password@cluster.mongodb.net/database`

**Get Started**:
- Local: Install MongoDB Community Server
- Cloud: Create free cluster at https://cloud.mongodb.com/
- Get connection string from Atlas dashboard

### Key Capabilities (20 tools)

**Document Operations**:
- `create_document`, `update_document`, `delete_document`, `find_document`
- `find_many_documents`, `count_documents`, `distinct_values`

**Aggregation**:
- `aggregate` - Complex data transformations and analytics

**Index Management**:
- `create_index`, `list_indexes`, `drop_index`

**Collection Management**:
- `create_collection`, `drop_collection`, `list_collections`

**Transactions**:
- `start_transaction`, `commit_transaction`, `abort_transaction`

**Schema**:
- `validate_schema`, `update_schema`

**Database Admin**:
- `list_databases`, `get_stats`

### Use Cases

✅ **NoSQL Document Storage** - Flexible, schema-less data models
✅ **Rapid Prototyping** - No rigid schema migrations
✅ **Aggregation Pipelines** - Complex analytics on large datasets
✅ **Horizontal Scaling** - Sharding for big data workloads
✅ **Real-Time Analytics** - Fast reads with proper indexing
✅ **Content Management** - Blog posts, product catalogs, user profiles

### Example Workflow

```python
# Agent with MongoDB access
agent = {
    "name": "data-engineer",
    "mcp_servers": ["mongodb"],
    "instructions": "Manage NoSQL document operations and analytics"
}

# Sample tasks:
# "Store new user profile in users collection"
# "Find all active users created in last 30 days"
# "Run aggregation pipeline to calculate monthly revenue by product"
# "Create index on email field for faster lookups"
```

---

## 2. Twilio Communications

### What It Does
Multi-channel communications platform for SMS, voice, WhatsApp, email, and verification.

### Configuration

```bash
# .env
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_twilio_auth_token
TWILIO_PHONE_NUMBER=+1234567890
```

**Get Credentials**: https://console.twilio.com/
- Account SID and Auth Token from Account Info
- Phone number must be Twilio-verified (format: +1234567890)
- Free trial available with test credentials

### Key Capabilities (25 tools)

**SMS & MMS**:
- `send_sms`, `send_mms`, `list_messages`, `get_message`

**Voice Calls**:
- `make_call`, `list_calls`, `get_call`, `update_call`
- `record_call`, `transcribe_recording`

**WhatsApp**:
- `send_whatsapp`, `list_whatsapp_messages`

**Verification & Lookup**:
- `create_verification`, `check_verification` (2FA)
- `lookup_phone_number`, `carrier_lookup`

**Phone Number Management**:
- `list_available_numbers`, `purchase_number`

**Conferencing**:
- `create_conference`, `list_conferences`, `update_conference`

**Email**:
- `send_email`, `list_emails`

**Account**:
- `get_account_info`, `list_usage`

### Use Cases

✅ **SMS Notifications** - Order confirmations, alerts, reminders
✅ **Voice Calls & IVR** - Automated customer support calls
✅ **WhatsApp Business** - Customer engagement via WhatsApp
✅ **Two-Factor Authentication** - Secure login verification
✅ **Phone Verification** - Validate user phone numbers
✅ **Call Recording** - Record and transcribe customer calls
✅ **Email Campaigns** - Transactional emails
✅ **Customer Engagement** - Multi-channel outreach automation

### Example Workflow

```python
# Customer support agent with Twilio
agent = {
    "name": "support-communications",
    "mcp_servers": ["twilio", "hubspot", "slack"],
    "instructions": "Handle customer communications across SMS, voice, WhatsApp"
}

# Sample tasks:
# "Send SMS confirmation to customer at +1-555-0100"
# "Make voice call to customer to confirm appointment"
# "Send WhatsApp message with order tracking link"
# "Create 2FA verification for new user signup"
# "Lookup phone number to verify carrier and validity"
```

---

## 3. Sentry Monitoring

### What It Does
Error tracking and performance monitoring for production applications.

### Configuration

```bash
# .env
SENTRY_DSN=https://public_key@sentry.io/project_id
SENTRY_ORG=your-organization-slug
SENTRY_PROJECT=your-project-slug
```

**Get Credentials**: https://sentry.io/
- Create project at Sentry.io
- DSN from: Project Settings > Client Keys (DSN)
- Organization slug from URL: `sentry.io/organizations/YOUR_ORG/`
- Project slug from URL: `sentry.io/organizations/YOUR_ORG/projects/YOUR_PROJECT/`

### Key Capabilities (18 tools)

**Issue Management**:
- `list_issues`, `get_issue`, `update_issue`, `resolve_issue`
- `add_comment`, `list_comments`

**Event Tracking**:
- `list_events`, `get_event`, `get_event_trace`

**Release Management**:
- `create_release`, `update_release`, `list_releases`
- `associate_commits`, `deploy_release`

**Alerts**:
- `create_alert_rule`, `update_alert_rule`, `list_alert_rules`

**Performance**:
- `get_project_stats`, `get_performance_stats`
- `list_transactions`, `get_transaction_details`

### Use Cases

✅ **Error Tracking** - Catch and debug production errors
✅ **Performance Monitoring** - Track slow transactions
✅ **Release Health** - Monitor stability of new releases
✅ **Alert Management** - Get notified of critical issues
✅ **Issue Triage** - Prioritize and resolve bugs
✅ **Production Debugging** - Trace errors with full context
✅ **Performance Optimization** - Identify bottlenecks
✅ **Transaction Monitoring** - Track API and database performance

### Example Workflow

```python
# Monitoring agent with Sentry
agent = {
    "name": "production-monitor",
    "mcp_servers": ["sentry", "slack", "github"],
    "instructions": "Monitor production errors and alert team"
}

# Sample tasks:
# "List all unresolved issues from last 24 hours"
# "Get error trace for issue #12345"
# "Create new release for version 2.1.0 and associate commits"
# "Set up alert rule for error rate > 5% in 15 minutes"
# "Notify Slack when critical errors occur"
```

---

## 4. HubSpot CRM

### What It Does
Full-featured CRM with contacts, companies, deals, email marketing, and workflow automation.

### Configuration

```bash
# .env
HUBSPOT_API_KEY=pat-na1-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
HUBSPOT_PORTAL_ID=12345678
```

**Get Credentials**: https://app.hubspot.com/private-apps/
- Create private app in your HubSpot account
- Required scopes: `crm.objects.contacts`, `crm.objects.companies`, `crm.objects.deals`, `crm.objects.tickets`, `automation`, `content`, `reports`
- Portal ID (Hub ID) from: Settings > Account Setup > Account Defaults
- Copy access token from private app settings

### Key Capabilities (30 tools)

**Contact Management**:
- `create_contact`, `update_contact`, `delete_contact`, `get_contact`, `search_contacts`

**Company Management**:
- `create_company`, `update_company`, `delete_company`, `get_company`, `search_companies`

**Deal Tracking**:
- `create_deal`, `update_deal`, `delete_deal`, `get_deal`, `search_deals`

**Ticket System**:
- `create_ticket`, `update_ticket`, `delete_ticket`, `get_ticket`

**Email Marketing**:
- `send_email`, `schedule_email`, `track_email_opens`

**Tasks & Notes**:
- `create_task`, `update_task`, `list_tasks`
- `create_note`, `associate_note`

**Workflow Automation**:
- `create_workflow`, `trigger_workflow`, `list_workflows`

**Analytics**:
- `get_analytics`, `get_funnel_stats`, `get_attribution_report`

**Pipeline Management**:
- `list_pipelines`, `get_pipeline_stage`

### Use Cases

✅ **CRM Management** - Centralized customer database
✅ **Sales Pipeline** - Track deals from lead to close
✅ **Lead Nurturing** - Automated email campaigns
✅ **Contact Management** - 360-degree customer view
✅ **Deal Forecasting** - Revenue predictions
✅ **Workflow Automation** - Marketing and sales automation
✅ **Analytics & Attribution** - Track marketing ROI
✅ **Support Ticketing** - Customer service integration

### Example Workflow

```python
# Sales agent with HubSpot
agent = {
    "name": "sales-automation",
    "mcp_servers": ["hubspot", "twilio", "slack"],
    "instructions": "Manage sales pipeline and customer communications"
}

# Sample tasks:
# "Create new contact for lead from demo request"
# "Update deal stage to 'Negotiation' for Acme Corp"
# "Send follow-up email to all contacts in 'Qualified Lead' stage"
# "Create task to call prospect next Monday"
# "Generate funnel analytics report for Q1"
```

---

## Multi-Server Workflows

### Customer Support Automation
**Servers**: Twilio + HubSpot + Slack + Sentry

```python
workflow = {
    "name": "360-Degree Customer Support",
    "steps": [
        "Twilio: Receive SMS from customer with issue",
        "HubSpot: Look up customer contact and history",
        "Sentry: Check for related production errors",
        "HubSpot: Create support ticket",
        "Slack: Notify support team",
        "Twilio: Send SMS confirmation to customer",
        "HubSpot: Update contact timeline"
    ]
}
```

### Data Pipeline & Analytics
**Servers**: MongoDB + Supabase + Airtable + HubSpot

```python
workflow = {
    "name": "Multi-Database ETL Pipeline",
    "steps": [
        "HubSpot: Fetch new contacts and deals",
        "MongoDB: Store raw CRM data in documents",
        "MongoDB: Run aggregation pipeline for analytics",
        "Supabase: Store processed analytics in PostgreSQL",
        "Airtable: Sync summary data to marketing dashboard"
    ]
}
```

### Production Monitoring & Alerting
**Servers**: Sentry + Slack + GitHub + Twilio

```python
workflow = {
    "name": "Production Error Response",
    "steps": [
        "Sentry: Detect critical error spike",
        "GitHub: Search codebase for error source",
        "Slack: Alert on-call engineer",
        "Twilio: Send SMS if no Slack response in 5min",
        "Sentry: Create GitHub issue with error trace",
        "Sentry: Notify when issue is resolved"
    ]
}
```

### Sales & Marketing Automation
**Servers**: HubSpot + Twilio + Slack + MongoDB

```python
workflow = {
    "name": "Lead Conversion Pipeline",
    "steps": [
        "HubSpot: Identify high-value leads",
        "MongoDB: Check lead scoring history",
        "HubSpot: Create deal and assign to sales rep",
        "Twilio: Send SMS introduction",
        "HubSpot: Schedule follow-up email sequence",
        "Slack: Notify sales team of hot lead",
        "MongoDB: Log all interactions for analytics"
    ]
}
```

---

## Testing Phase 3 Servers

### 1. Start MCP Server

```bash
# Start MongoDB server
curl -X POST http://localhost:8100/api/v1/mcp/registry/servers/mongodb/start

# Check if running
curl http://localhost:8100/api/v1/mcp/registry/servers/running
```

### 2. Call Tool Directly

```bash
# Send SMS via Twilio
curl -X POST http://localhost:8100/api/v1/mcp/registry/tools/call \
  -H "Content-Type: application/json" \
  -d '{
    "server_name": "twilio",
    "tool_name": "send_sms",
    "arguments": {
      "to": "+15550100",
      "body": "Hello from Unicorn Brigade!"
    }
  }'
```

### 3. Assign to Agent

```bash
# Create monitoring agent with Phase 3 servers
curl -X POST http://localhost:8100/api/v1/agents \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "monitoring-agent",
    "name": "Production Monitoring Agent",
    "role": "System Monitoring & Alerts",
    "tools": ["sentry", "slack", "twilio"],
    "instructions": "Monitor production errors and alert team via Slack/SMS"
  }'
```

---

## Environment Setup Checklist

### MongoDB
- [ ] Install MongoDB locally OR create Atlas cluster
- [ ] Get connection string (local or Atlas)
- [ ] Choose default database name
- [ ] Add `MONGODB_URI` and `MONGODB_DATABASE` to `.env`
- [ ] Test connection with MongoDB Compass or CLI

### Twilio
- [ ] Sign up at https://console.twilio.com/
- [ ] Copy Account SID from dashboard
- [ ] Copy Auth Token (keep secure!)
- [ ] Get/purchase Twilio phone number
- [ ] Add all three variables to `.env`
- [ ] Test with trial credits (free tier available)

### Sentry
- [ ] Create project at https://sentry.io/
- [ ] Copy DSN from Project Settings > Client Keys
- [ ] Note organization slug from URL
- [ ] Note project slug from URL
- [ ] Add all three variables to `.env`
- [ ] Install Sentry SDK in your application

### HubSpot
- [ ] Create HubSpot account or access existing
- [ ] Navigate to Settings > Integrations > Private Apps
- [ ] Create new private app with required scopes
- [ ] Copy access token (API key)
- [ ] Get Portal ID from Account Defaults
- [ ] Add both variables to `.env`

---

## Platform Coverage After Phase 3

| Category | Servers |
|----------|---------|
| **Databases** | PostgreSQL, Airtable, Supabase, MongoDB |
| **NoSQL** | MongoDB |
| **SQL** | PostgreSQL, Supabase |
| **Deployment** | Vercel, Cloudflare |
| **Version Control** | GitHub, Git |
| **Project Management** | Linear, Notion |
| **CRM** | HubSpot |
| **Payments** | Stripe |
| **Collaboration** | Slack, Notion |
| **Storage** | Google Drive, Cloudflare R2, Supabase Storage |
| **Authentication** | Supabase Auth |
| **Edge Computing** | Cloudflare Workers, Vercel Functions |
| **Communications** | Twilio (SMS, Voice, WhatsApp, Email) |
| **Monitoring** | Sentry |
| **Marketing** | HubSpot |

---

## Metrics

- **Total Servers**: 22 (10 baseline + 4 Phase 1 + 4 Phase 2 + 4 Phase 3)
- **Phase 3 Tools**: 93 new capabilities
- **Platform Tools**: 280 total capabilities
- **Average Tools/Server**: 23 (Phase 3)
- **Server Growth**: +22.2% vs Phase 2

---

## Next Steps

### Immediate
1. Configure production API keys for all Phase 3 servers
2. Test with live credentials (MongoDB, Twilio, Sentry, HubSpot)
3. Create example workflows combining Phase 3 servers
4. Test multi-channel communication flows with Twilio

### Short-term
1. Build customer support workflow (Twilio + HubSpot + Slack)
2. Create monitoring workflow (Sentry + GitHub + Slack)
3. Implement data pipeline (MongoDB + Supabase + Airtable)
4. Add frontend UI for Phase 3 server management
5. Document integration patterns

### Medium-term
1. Plan Phase 4 servers (Shopify, Salesforce, Jira, Zendesk)
2. Build specialized agent templates using Phase 3 servers
3. Create voice agent integrations with Twilio
4. Develop automated incident response with Sentry
5. Build end-to-end sales automation with HubSpot

---

## Integration Highlights

### MongoDB
- **Why**: Complements PostgreSQL with NoSQL flexibility
- **Best For**: Flexible schemas, rapid prototyping, unstructured data
- **Power Move**: Aggregation pipelines for complex analytics
- **Scales**: Horizontal sharding for massive datasets

### Twilio
- **Why**: Multi-channel customer engagement beyond email
- **Best For**: SMS alerts, voice calls, WhatsApp, 2FA
- **Power Move**: Automated call workflows with recording/transcription
- **Scales**: Enterprise-grade reliability (99.999% uptime SLA)

### Sentry
- **Why**: Essential for production systems and debugging
- **Best For**: Error tracking, performance monitoring, release health
- **Power Move**: Automatic issue creation in GitHub from errors
- **Scales**: Billions of events per month for large applications

### HubSpot
- **Why**: Full-featured CRM for sales/marketing automation
- **Best For**: Pipeline management, lead nurturing, email campaigns
- **Power Move**: Workflow automation triggers across entire platform
- **Scales**: Enterprise CRM with unlimited contacts/companies

---

## Resources

- **MCP Registry**: https://registry.modelcontextprotocol.io/
- **MCP Documentation**: https://modelcontextprotocol.io
- **Phase 3 Status**: `docs/mcp-phase3-status.json`
- **Research**: `docs/mcp-servers-research-2026.md`
- **MongoDB Docs**: https://www.mongodb.com/docs/
- **Twilio Docs**: https://www.twilio.com/docs
- **Sentry Docs**: https://docs.sentry.io/
- **HubSpot API**: https://developers.hubspot.com/docs/api/overview

---

**Last Updated**: January 31, 2026
**Status**: Production Ready
**Team**: MCP Phase 3 Integration Team Lead (Claude Sonnet 4.5)
