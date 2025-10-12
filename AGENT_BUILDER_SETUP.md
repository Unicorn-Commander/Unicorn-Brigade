# Unicorn Brigade - Agent Builder System Setup

## Overview

The Agent Builder System allows you to create and manage AI agents through conversational interaction with **The General**, Chief Agent Engineering Officer of Unicorn Brigade.

## Architecture

### Backend Components

1. **Database Schema** (`prisma/schema.prisma`)
   - Enhanced Agent model with identity, organization, technical, and A2A protocol fields
   - Tool model for managing available tools
   - AgentTool join table for agent-tool relationships
   - AgentApiKey model for API key management

2. **API Routes** (`api/routes/agents-new.js`)
   - GET /api/agents-new - List all agents with filtering
   - GET /api/agents-new/:id - Get agent details
   - POST /api/agents-new - Create new agent
   - PUT /api/agents-new/:id - Update agent
   - DELETE /api/agents-new/:id - Delete agent
   - GET /api/agents-new/:id/card - Get A2A Agent Card
   - POST /api/agents-new/:id/invoke - Invoke agent
   - GET /api/agents-new/domains - List available domains
   - POST /api/agents-new/:id/api-keys - Generate API key
   - DELETE /api/agents-new/:id/api-keys/:keyId - Revoke API key

3. **Agent Builder Service** (`core/services/agentBuilderService.js`)
   - Manages conversations with The General
   - Parses agent configurations from natural language
   - Creates agents via Prisma ORM
   - Integrates with LiteLLM for multi-provider LLM access

4. **Agent Builder Routes** (`api/routes/agent-builder.js`)
   - POST /api/agent-builder/chat - Chat with The General
   - POST /api/agent-builder/create - Create agent from configuration
   - GET /api/agent-builder/session/:sessionId - Get conversation history
   - DELETE /api/agent-builder/session/:sessionId - Clear session
   - GET /api/agent-builder/info - Get service information

### Frontend Components

1. **AgentBuilderChat** (`frontend/src/pages/AgentBuilderChat.jsx`)
   - Full-screen chat interface with The General
   - Real-time conversation with markdown rendering
   - Agent creation intent detection
   - Session management

2. **AgentLibrary** (`frontend/src/pages/AgentLibrary.jsx`)
   - Browse all agents grouped by domain
   - Advanced filtering (domain, status, type, search)
   - Grid and list view modes
   - Agent statistics and metadata

3. **AgentDetail** (`frontend/src/pages/AgentDetail.jsx`)
   - View and edit agent details
   - Tabbed interface (Overview, Configuration, System Prompt, API Keys)
   - In-place editing with validation
   - API key management

### Configuration

**The General Configuration** (`config/agents/the-general.json`)
- Pre-configured agent with specialized system prompt
- Domain expertise and tool knowledge
- Conversational agent design capabilities

## Installation & Setup

### 1. Database Migration

Run Prisma migrations to update the database schema:

```bash
cd /Users/aaronstransky/unicorn-command-control
npm run migrate
```

This will:
- Add new fields to the Agent model
- Create Tool, AgentTool, and AgentApiKey tables
- Generate Prisma client with new types

### 2. Environment Variables

Ensure these variables are set in `.env`:

```env
# LiteLLM Configuration (for The General)
OPENROUTER_API_KEY=your_openrouter_key_here
# OR
LITELLM_PROXY_URL=http://localhost:4000
LITELLM_API_KEY=sk-litellm-master-key

# Backend URL (for A2A protocol)
BACKEND_URL=http://localhost:8112

# Database
DATABASE_URL=file:./unicorn.db
```

### 3. Install Dependencies

If not already installed:

```bash
# Backend
npm install

# Frontend
cd frontend
npm install
```

### 4. Start the Services

Terminal 1 - Backend:
```bash
cd /Users/aaronstransky/unicorn-command-control
npm run dev
```

Terminal 2 - Frontend:
```bash
cd /Users/aaronstransky/unicorn-command-control/frontend
npm run dev
```

### 5. Access the Application

- **Backend API**: http://localhost:8112
- **Frontend UI**: http://localhost:8113
- **The General Chat**: http://localhost:8113/builder-chat
- **Agent Library**: http://localhost:8113/library

## Usage Guide

### Creating an Agent with The General

1. Navigate to http://localhost:8113/builder-chat
2. Describe the agent you want to create:
   ```
   "I need a financial forensic accountant agent that can analyze
   transactions, detect fraud patterns, and generate compliance reports."
   ```
3. The General will ask clarifying questions about:
   - Domain and subdomain
   - Required tools and capabilities
   - Personality and communication style
   - Technical parameters (model, temperature, etc.)
4. Review the proposed configuration
5. Confirm to create the agent
6. View the new agent in the library

### Managing Agents

**View All Agents**
- Go to http://localhost:8113/library
- Use filters to find specific agents
- Click on an agent to view details

**Edit Agent**
- Click on an agent in the library
- Click "Edit Agent" button
- Modify fields inline
- Click "Save Changes"

**Delete Agent**
- Navigate to agent detail page
- Click delete button
- Confirm deletion

### Agent Invocation (A2A Protocol)

**Generate API Key**
```bash
curl -X POST http://localhost:8112/api/agents-new/{agent-id}/api-keys \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Production Key",
    "permissions": ["invoke"],
    "rateLimit": 100
  }'
```

**Invoke Agent**
```bash
curl -X POST http://localhost:8112/api/agents-new/{agent-id}/invoke \
  -H "Content-Type: application/json" \
  -H "X-API-Key: {your-api-key}" \
  -d '{
    "message": "Analyze this transaction for fraud indicators...",
    "context": {
      "transaction_id": "TX-12345"
    }
  }'
```

**Get Agent Card (A2A Protocol)**
```bash
curl http://localhost:8112/api/agents-new/{agent-id}/card
```

Returns standardized agent card with:
- Agent identity and capabilities
- Available tools
- Authentication requirements
- Pricing information
- Invocation endpoint

## API Reference

### Agent Fields

```typescript
{
  id: string;
  name: string;
  displayName?: string;
  title?: string;
  type: 'individual' | 'team_lead' | 'orchestrator';
  domain?: string;
  subdomain?: string;
  department?: string;
  rank?: string;
  avatar?: string;
  avatarUrl?: string;
  avatarStyle?: string;
  bio?: string;
  persona: string;
  systemPrompt: string;
  status: 'active' | 'draft' | 'inactive' | 'archived' | 'busy';
  capabilities: string[];
  model: string;
  temperature: number;
  maxTokens: number;
  requiresAuth: boolean;
  pricingModel?: 'free' | 'pay_per_use' | 'subscription';
  basePrice?: number;
  version: string;
  createdBy?: string;
  createdByAgent?: string;
  createdAt: Date;
  updatedAt: Date;
}
```

### Available Domains

- `financial` - Bookkeeping, investment, tax, forensics
- `legal` - Contracts, litigation, compliance, research
- `medical` - Diagnosis, research, patient care
- `technology` - Software dev, cybersecurity, data science, cloud
- `investigation` - OSINT, fraud detection, research
- `orchestration` - Multi-agent coordination
- `meta` - Agent building, system management
- `intelligence` - Information gathering and analysis

## Troubleshooting

### The General Not Responding

**Problem**: Chat interface shows error or no response
**Solution**:
1. Check backend logs for errors
2. Verify OPENROUTER_API_KEY or LITELLM_PROXY_URL is set
3. Ensure LiteLLM provider is working: `http://localhost:8112/health`
4. Check The General config: `http://localhost:8112/api/agent-builder/info`

### Database Errors

**Problem**: Prisma errors when creating agents
**Solution**:
1. Run migrations: `npm run migrate`
2. Regenerate Prisma client: `npx prisma generate`
3. Check database file permissions
4. Reset database if needed: `rm unicorn.db && npm run migrate`

### Agent Creation Fails

**Problem**: Agent not being created from chat
**Solution**:
1. Check backend logs for validation errors
2. Ensure all required fields (name, systemPrompt) are provided
3. Verify tool IDs exist if tools are specified
4. Check Prisma schema matches code expectations

### Frontend Build Errors

**Problem**: Import errors or missing components
**Solution**:
1. Ensure all dependencies are installed: `cd frontend && npm install`
2. Check that all new pages are properly exported
3. Verify import paths are correct
4. Clear build cache: `rm -rf frontend/.vite && npm run dev`

## Development

### Adding New Domains

1. Update domain configuration in `AgentLibrary.jsx`:
```javascript
const domainConfig = {
  your_domain: { icon: '🎯', color: 'purple', emoji: '🎯' }
};
```

2. Add domain to The General's system prompt in `the-general.json`

3. Update domain list in this documentation

### Extending Agent Capabilities

1. Add new fields to Prisma schema
2. Run migration: `npm run migrate`
3. Update API routes to handle new fields
4. Update frontend forms and displays
5. Document new capabilities

### Creating Custom Agents

Beyond using The General, you can create agents programmatically:

```javascript
const agent = await prisma.agent.create({
  data: {
    name: 'My Custom Agent',
    systemPrompt: 'You are...',
    model: 'gpt-4-turbo',
    temperature: 0.7,
    maxTokens: 4096,
    domain: 'custom',
    capabilities: JSON.stringify(['capability1', 'capability2'])
  }
});
```

## Architecture Decisions

### Why "The General"?

The General serves as a conversational interface for agent creation, making it accessible to non-technical users while maintaining flexibility for advanced configurations.

### Why Separate Routes?

`/api/agents-new` vs `/api/agents` - The new routes use enhanced schema and avoid conflicts with legacy code during migration.

### Why LiteLLM?

LiteLLM provides multi-provider support, allowing fallback between OpenAI, Anthropic, Google, and OpenRouter without code changes.

### Why A2A Protocol?

Agent-to-Agent protocol enables agents to discover and invoke each other, creating a distributed agent ecosystem.

## Next Steps

1. **Add Tool Discovery**: Browse and attach tools to agents from UI
2. **Enhanced Testing**: Test interface within agent detail page
3. **Agent Templates**: Pre-built agent configurations for common use cases
4. **Agent Marketplace**: Share and discover agents across teams
5. **Performance Monitoring**: Track agent performance and costs
6. **Team Collaboration**: Multi-user agent management with permissions

## Support

For issues or questions:
1. Check logs: Backend console and browser console
2. Review this documentation
3. Check Prisma schema and migrations
4. Verify environment variables
5. Test API endpoints with curl/Postman

## Credits

Built for Unicorn Brigade - AI Agent Infrastructure Platform
Part of Magic Unicorn Unconventional Technology & Stuff Inc.
