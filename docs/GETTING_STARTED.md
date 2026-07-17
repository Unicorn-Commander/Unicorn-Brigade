# Unicorn Brigade - Getting Started & Deployment Guide

This guide covers everything you need to deploy and run Unicorn Brigade, from a quick local setup to production deployment.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Quick Start (5 Minutes)](#quick-start-5-minutes)
3. [Configuration](#configuration)
4. [First Steps After Deployment](#first-steps-after-deployment)
5. [Production Deployment](#production-deployment)
6. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required Software

| Software | Minimum Version | Purpose |
|----------|----------------|---------|
| **Docker** | 24.0+ | Container runtime |
| **Docker Compose** | 2.20+ | Multi-container orchestration |

Install Docker Desktop (includes Docker Compose):
- **macOS/Windows**: [https://www.docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop)
- **Linux**: [https://docs.docker.com/engine/install](https://docs.docker.com/engine/install)

Verify installation:
```bash
docker --version        # Docker version 24.x.x or higher
docker compose version  # Docker Compose version v2.x.x
```

### Required API Keys

At minimum, you need **one LLM provider** to run agents:

| API Key | Required | Where to Get It |
|---------|----------|-----------------|
| **OpenAI API Key** | Yes (or Anthropic) | [https://platform.openai.com/api-keys](https://platform.openai.com/api-keys) |
| **Anthropic API Key** | Optional | [https://console.anthropic.com](https://console.anthropic.com) |

### Optional API Keys (Enable More Features)

| API Key | Feature | Where to Get It |
|---------|---------|-----------------|
| **Serper API Key** | Web search tool | [https://serper.dev](https://serper.dev) (2,500 free searches) |
| **GitHub Token** | GitHub MCP server | [https://github.com/settings/tokens](https://github.com/settings/tokens) (scopes: repo, read:packages, read:org) |
| **Brave API Key** | Brave web search | [https://brave.com/search/api](https://brave.com/search/api) |
| **Stripe API Key** | Billing features | [https://dashboard.stripe.com/apikeys](https://dashboard.stripe.com/apikeys) |

### Optional API Keys (Email Providers)

Choose one if you want email capabilities:

| Provider | Where to Get It |
|----------|-----------------|
| **Microsoft 365** | [Azure Portal - App Registrations](https://portal.azure.com/#view/Microsoft_AAD_RegisteredApps) (requires Mail.Send permission) |
| **Google Workspace** | [Google Cloud Console](https://console.cloud.google.com/apis/credentials) (enable Gmail API) |
| **Resend** | [https://resend.com](https://resend.com) |
| **SendGrid** | [https://sendgrid.com](https://sendgrid.com) |

### Optional API Keys (Voice - Cloud Providers)

Only needed if using cloud voice providers (self-hosted alternatives available):

| Provider | Feature | Where to Get It |
|---------|---------|-----------------|
| **Deepgram** | Cloud STT | [https://console.deepgram.com](https://console.deepgram.com) |
| **ElevenLabs** | Cloud TTS | [https://elevenlabs.io](https://elevenlabs.io) |

---

## Quick Start (5 Minutes)

### Step 1: Clone the Repository

```bash
git clone https://git.unicorncommander.ai/UnicornCommander/Unicorn-Brigade.git
cd Unicorn-Brigade
```

### Step 2: Create Environment File

```bash
cp .env.example .env
```

### Step 3: Generate Admin Key

Generate a secure 64-character hex key for admin authentication:

```bash
openssl rand -hex 32
```

This outputs something like: `a1b2c3d4e5f6...` (64 characters)

### Step 4: Configure Required Variables

Open `.env` and set these required values:

```bash
# REQUIRED: Your admin key (paste the output from Step 3)
BRIGADE_ADMIN_KEY=your-64-char-hex-admin-key-from-step-3

# REQUIRED: At least one LLM provider
OPENAI_API_KEY=sk-your-openai-api-key-here

# REQUIRED: Database passwords (change these!)
POSTGRES_PASSWORD=your-secure-postgres-password
REDIS_PASSWORD=your-secure-redis-password

# OPTIONAL but recommended: Web search
SERPER_API_KEY=your-serper-api-key
```

### Step 5: Start Services

```bash
docker compose up -d
```

This starts the core services:
- **brigade-api** - FastAPI backend (port 8100)
- **brigade-frontend** - React UI (port 3000)
- **brigade-postgres** - PostgreSQL database (port 5432)
- **brigade-redis** - Redis cache (port 6379)
- **brigade-qdrant** - Qdrant vector database (port 6333)

### Step 6: Access the Application

Open your browser to: **[http://localhost:3000](http://localhost:3000)**

The API is available at: **[http://localhost:8100](http://localhost:8100)**

API documentation (Swagger): **[http://localhost:8100/docs](http://localhost:8100/docs)**

### Verify Everything is Running

```bash
# Check service status
docker compose ps

# Check API health
curl http://localhost:8100/api/v1/health

# List available agents
curl -H "X-API-Key: YOUR_BRIGADE_ADMIN_KEY" http://localhost:8100/api/v1/agents
```

---

## Configuration

### Required Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `BRIGADE_ADMIN_KEY` | Master admin key for authentication | `openssl rand -hex 32` output |
| `OPENAI_API_KEY` | OpenAI API key (or use Anthropic) | `sk-...` |
| `POSTGRES_PASSWORD` | PostgreSQL database password | Strong password |
| `REDIS_PASSWORD` | Redis cache password | Strong password |

### Security Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `AUTH_BYPASS` | Skip authentication (NEVER in production!) | `false` |
| `SECRET_KEY` | JWT/session secret | Change in production |
| `CORS_ORIGINS` | Allowed CORS origins | `http://localhost:3000,http://localhost:8100` |

### LLM Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI API key | Required |
| `OPENAI_MODEL` | Default OpenAI model | `gpt-4o-mini` |
| `OPENAI_TEMPERATURE` | Response creativity (0-1) | `0.7` |
| `ANTHROPIC_API_KEY` | Anthropic API key (optional) | - |
| `ANTHROPIC_MODEL` | Anthropic model | `claude-3-5-sonnet-20241022` |

### Memory Provider Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `MEMORY_PROVIDER` | Vector memory backend (`mem0`) | `mem0` |
| `QDRANT_URL` | Qdrant vector DB URL | `http://brigade-qdrant:6333` |
| `QDRANT_COLLECTION` | Qdrant collection name | `brigade_memories` |
| `FALKORDB_ENABLED` | Enable Graphiti + FalkorDB temporal knowledge graph | `true` |
| `FALKORDB_HOST` / `FALKORDB_PORT` | FalkorDB graph backend | `brigade-falkordb` / `6380` |

> The advanced temporal-memory tier is **Graphiti over FalkorDB**
> (`app/memory/graphiti_manager.py`). mem0 + Qdrant remains the lightweight
> default vector store.

### Optional Integrations

#### Slack Integration

```bash
# Create a Slack App at https://api.slack.com/apps
# Bot Token Scopes: chat:write, channels:read, channels:history, users:read, reactions:write
SLACK_BOT_TOKEN=xoxb-000000000000-000000000000-000000000000-000000000000
SLACK_USER_TOKEN=xoxb-000000000000-000000000000-000000000000-000000000000    # Optional, for search
SLACK_SIGNING_SECRET=your-signing-secret
SLACK_APP_ID=A0123456789
```

#### Microsoft 365 Email

```bash
# Create App Registration in Azure AD with Mail.Send permission
EMAIL_PROVIDER=ms365
MS365_CLIENT_ID=your-azure-app-client-id
MS365_TENANT_ID=your-azure-tenant-id
MS365_CLIENT_SECRET=your-azure-app-client-secret
MS365_USER_EMAIL=your-email@yourdomain.com
```

#### Google Workspace Email

```bash
# Create OAuth2 credentials at Google Cloud Console
# Enable Gmail API, scopes: gmail.send, gmail.readonly, gmail.modify
EMAIL_PROVIDER=google
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
GOOGLE_REFRESH_TOKEN=your-refresh-token
GOOGLE_USER_EMAIL=your-email@yourdomain.com
```

#### Resend or SendGrid Email

```bash
# Resend
EMAIL_PROVIDER=resend
RESEND_API_KEY=re_your-api-key
RESEND_FROM_EMAIL=noreply@yourdomain.com

# SendGrid
EMAIL_PROVIDER=sendgrid
SENDGRID_API_KEY=SG.your-api-key
SENDGRID_FROM_EMAIL=noreply@yourdomain.com
```

### Enabling Voice

Voice support uses self-hosted STT (Speech-to-Text) and TTS (Text-to-Speech) by default:

```bash
# Start with LiveKit voice support
docker compose -f docker-compose.yml -f docker-compose.livekit.yml up -d

# STT Provider (Speech-to-Text)
VOICE_STT_PROVIDER=faster-whisper    # faster-whisper, whisper-cpp, mlx-whisper
VOICE_STT_MODEL=large-v3-turbo       # tiny, base, small, medium, large-v3
VOICE_STT_DEVICE=auto                # auto, cpu, cuda, mps

# TTS Provider (Text-to-Speech)
VOICE_TTS_PROVIDER=kokoro            # kokoro, chatterbox, marvis, cosyvoice
VOICE_TTS_MODEL=kokoro-82m
VOICE_TTS_VOICE=af_bella             # See .env.example for voice list
```

### Enabling Langflow (Visual Workflows)

```bash
# Start with Langflow
docker compose -f docker-compose.yml -f docker-compose.langflow.yml up -d

# Access Langflow UI at http://localhost:7860
LANGFLOW_ENABLED=true
LANGFLOW_HOST=http://localhost:7860
LANGFLOW_SUPERUSER=admin
LANGFLOW_SUPERUSER_PASSWORD=changeme    # Change this!
```

### Enabling Observability (Langfuse)

```bash
# Start with Langfuse tracing
docker compose -f docker-compose.yml -f docker-compose.langfuse.yml up -d

# Access Langfuse UI at http://localhost:3001
LANGFUSE_ENABLED=true
LANGFUSE_HOST=http://localhost:3001
LANGFUSE_PUBLIC_KEY=pk-lf-your-public-key
LANGFUSE_SECRET_KEY=sk-lf-your-secret-key
```

### Enabling the Knowledge Graph / Temporal Memory (FalkorDB + Graphiti)

FalkorDB is the graph backend for both the knowledge-graph tools and the
Graphiti temporal-memory tier.

```bash
# Start with FalkorDB
docker compose -f docker-compose.yml -f docker-compose.falkordb.yml up -d

# Access FalkorDB Browser at http://localhost:3002
FALKORDB_ENABLED=true
FALKORDB_HOST=brigade-falkordb
FALKORDB_PORT=6380
```

### Compose Overlay Matrix

Brigade ships several compose overlays. Layer the ones you need on top of the
base `docker-compose.yml`:

| Overlay file | Status | Purpose |
| ------------ | ------ | ------- |
| `docker-compose.yml` | **Required** | Base stack: API, frontend, Postgres, Redis, Qdrant |
| `docker-compose.falkordb.yml` | Optional | FalkorDB graph backend for knowledge graph + Graphiti memory |
| `docker-compose.livekit.yml` | Optional | LiveKit server for voice agents |
| `docker-compose.langflow.yml` | Optional | Langflow visual workflow builder |
| `docker-compose.langfuse.yml` | Optional | Langfuse LLM observability |
| `docker-compose.guardrails.yml` | Optional | Presidio / Llama Guard / Guardrails AI |
| `docker-compose.mcp.yml` | Optional | Code sandbox + browser automation for MCP servers |
| `docker-compose.zep.yml` | **Dead** | Legacy Zep memory — superseded by Graphiti + FalkorDB; do not use |

### Full Stack Deployment

To run the common optional services:

```bash
docker compose -f docker-compose.yml \
  -f docker-compose.langfuse.yml \
  -f docker-compose.falkordb.yml \
  -f docker-compose.livekit.yml \
  -f docker-compose.langflow.yml up -d
```

---

## First Steps After Deployment

### Using the Admin Key

The `BRIGADE_ADMIN_KEY` is your master key with full admin access. Include it in the `X-API-Key` header for all API requests:

```bash
# Example: List all agents
curl -H "X-API-Key: YOUR_BRIGADE_ADMIN_KEY" http://localhost:8100/api/v1/agents

# Example: Chat with an agent
curl -X POST http://localhost:8100/api/v1/agents/col-finance/chat \
  -H "X-API-Key: YOUR_BRIGADE_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"message": "What can you help me with?"}'
```

In the web UI, click on Settings/Profile to enter your admin key.

### Creating User API Keys

API keys are scoped to specific agents and have configurable permissions. Use your admin key to create new keys:

```bash
# Create an API key for an agent
curl -X POST http://localhost:8100/api/v1/agents/{agent_id}/api-keys \
  -H "X-API-Key: YOUR_BRIGADE_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My Integration Key",
    "permissions": ["chat", "read"],
    "rateLimit": 100,
    "expiresInDays": 90
  }'
```

Response includes the full key (shown only once):
```json
{
  "id": "key-uuid",
  "key": "ubk_abc123...",
  "keyPrefix": "ubk_abc1",
  "name": "My Integration Key",
  "permissions": ["chat", "read"],
  "expiresAt": "2026-04-30T00:00:00Z"
}
```

**Important**: Store the full `key` value securely. It is only shown once!

Available permissions:
- `read` - View agents and data
- `chat` - Send messages to agents
- `write` - Create/update agents
- `admin` - Full access

### List API Keys for an Agent

```bash
curl -H "X-API-Key: YOUR_BRIGADE_ADMIN_KEY" \
  http://localhost:8100/api/v1/agents/{agent_id}/api-keys
```

### Revoke an API Key

```bash
curl -X DELETE http://localhost:8100/api/v1/agents/{agent_id}/api-keys/{key_id} \
  -H "X-API-Key: YOUR_BRIGADE_ADMIN_KEY"
```

### Testing That Agents Work

#### 1. Check System Health

```bash
curl http://localhost:8100/api/v1/health
# Expected: {"status": "healthy", ...}
```

#### 2. List Available Agents

```bash
curl -H "X-API-Key: YOUR_ADMIN_KEY" http://localhost:8100/api/v1/agents
```

The platform comes with 11 production agents across 8 domains.

#### 3. Test Agent Chat (No Tools)

```bash
curl -X POST http://localhost:8100/api/v1/agents/gunny/chat \
  -H "X-API-Key: YOUR_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello, introduce yourself"}'
```

#### 4. Test Agent with Tools (Web Search)

Requires `SERPER_API_KEY` to be set:

```bash
curl -X POST http://localhost:8100/api/v1/agents/col-finance/chat \
  -H "X-API-Key: YOUR_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"message": "Search for the latest AI market trends"}'
```

You should see the agent invoke the `web_search` tool and return results.

#### 5. Test The General (Orchestration)

```bash
# Get orchestration state
curl -H "X-API-Key: YOUR_ADMIN_KEY" http://localhost:8100/api/v1/orchestration/state

# Send a command to The General
curl -X POST http://localhost:8100/api/v1/orchestration/command \
  -H "X-API-Key: YOUR_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"command": "What agents are available?"}'
```

#### 6. Test A2A Protocol

```bash
# Get agent card (discovery)
curl http://localhost:8100/api/v1/a2a/agent-card

# Invoke an agent externally
curl -X POST http://localhost:8100/api/v1/a2a/invoke \
  -H "X-API-Key: YOUR_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"agent_id": "col-finance", "task": "Calculate 2+2", "tools": ["calculator"]}'
```

#### 7. Test MCP Protocol

```bash
# List available MCP tools
curl -H "X-API-Key: YOUR_ADMIN_KEY" http://localhost:8100/api/v1/mcp/tools

# Execute a tool directly
curl -X POST http://localhost:8100/api/v1/mcp/tools/call \
  -H "X-API-Key: YOUR_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name": "calculator", "arguments": {"expression": "42 * 3.14"}}'
```

---

## Production Deployment

### HTTPS/TLS Setup with Reverse Proxy

In production, always run behind a reverse proxy with TLS. Here's an example Nginx configuration:

```nginx
# /etc/nginx/sites-available/unicorn-brigade
server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

    # Frontend
    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # API
    location /api/ {
        proxy_pass http://127.0.0.1:8100;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # SSE support for orchestration events
        proxy_set_header Connection '';
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 86400;
    }

    # WebSocket support (for voice)
    location /ws/ {
        proxy_pass http://127.0.0.1:8100;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }
}
```

Generate TLS certificates with Let's Encrypt:
```bash
sudo certbot --nginx -d your-domain.com
```

### Security Settings

**Critical**: Ensure these settings in production:

```bash
# .env for production

# NEVER enable auth bypass in production
AUTH_BYPASS=false

# Generate a strong admin key
BRIGADE_ADMIN_KEY=$(openssl rand -hex 32)

# Generate a strong secret key
SECRET_KEY=$(openssl rand -hex 32)

# Restrict CORS to your domain
CORS_ORIGINS=https://your-domain.com

# Use production environment
ENVIRONMENT=production
```

### Database Backups

#### Automated PostgreSQL Backups

Create a backup script (`/opt/backups/backup-brigade.sh`):

```bash
#!/bin/bash
BACKUP_DIR=/opt/backups/brigade
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/brigade_${TIMESTAMP}.sql.gz"

# Create backup directory
mkdir -p $BACKUP_DIR

# Dump and compress
docker exec brigade-postgres pg_dump -U brigade brigade | gzip > $BACKUP_FILE

# Keep only last 7 days
find $BACKUP_DIR -name "*.sql.gz" -mtime +7 -delete

echo "Backup created: $BACKUP_FILE"
```

Add to cron (daily at 2 AM):
```bash
0 2 * * * /opt/backups/backup-brigade.sh >> /var/log/brigade-backup.log 2>&1
```

#### Restore from Backup

```bash
gunzip -c /opt/backups/brigade/brigade_TIMESTAMP.sql.gz | \
  docker exec -i brigade-postgres psql -U brigade brigade
```

### Qdrant Vector Database Backup

```bash
# Backup Qdrant data
docker exec brigade-qdrant tar czf /tmp/qdrant-backup.tar.gz /qdrant/storage
docker cp brigade-qdrant:/tmp/qdrant-backup.tar.gz ./backups/
```

### Monitoring Recommendations

#### Health Check Endpoints

Set up monitoring for these endpoints:

| Endpoint | Expected Status | Description |
|----------|----------------|-------------|
| `GET /api/v1/health` | 200 | API health |
| `GET /` (port 3000) | 200 | Frontend health |

#### Prometheus Metrics

The API exposes Prometheus metrics. Add to your Prometheus config:

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'unicorn-brigade'
    static_configs:
      - targets: ['localhost:8100']
    metrics_path: /metrics
```

#### Recommended Monitoring Stack

- **Prometheus** - Metrics collection
- **Grafana** - Dashboards and alerting
- **Langfuse** - LLM-specific observability (included in docker-compose.langfuse.yml)

#### Key Metrics to Monitor

- API response times (p50, p95, p99)
- Error rates (5xx responses)
- Database connections
- Redis memory usage
- Qdrant collection size
- LLM token usage and costs (via Langfuse)

#### Log Aggregation

Logs are written to `./logs/` on the host. Consider using:
- **Loki + Grafana** for log aggregation
- **ELK Stack** (Elasticsearch, Logstash, Kibana)

---

## Troubleshooting

### Common Issues and Solutions

#### 1. Services Won't Start

**Symptom**: `docker compose up` fails or containers exit immediately.

**Check logs**:
```bash
docker compose logs brigade-api
docker compose logs brigade-postgres
```

**Common causes**:
- Missing environment variables: Ensure `.env` exists and has required values
- Port conflicts: Check if ports 3000, 8100, 5432, 6379, 6333 are available
- Insufficient memory: Ensure Docker has at least 4GB RAM allocated

#### 2. Authentication Errors (401)

**Symptom**: API returns `{"detail": "Invalid or missing API key"}`

**Solutions**:
1. Verify your admin key is correct:
   ```bash
   echo $BRIGADE_ADMIN_KEY  # Check .env value
   ```
2. Include the header correctly:
   ```bash
   curl -H "X-API-Key: YOUR_KEY" http://localhost:8100/api/v1/agents
   ```
3. For development only, temporarily enable bypass (NEVER in production):
   ```bash
   AUTH_BYPASS=true  # In .env, then restart
   ```

#### 3. Database Connection Errors

**Symptom**: "Connection refused" or "database does not exist"

**Solutions**:
1. Wait for PostgreSQL to fully start:
   ```bash
   docker compose logs brigade-postgres | tail -20
   # Look for: "database system is ready to accept connections"
   ```
2. Verify credentials match:
   ```bash
   # Check .env
   POSTGRES_USER=brigade
   POSTGRES_PASSWORD=your-password
   POSTGRES_DB=brigade
   ```
3. Reset database (warning: data loss):
   ```bash
   docker compose down -v  # Removes volumes
   docker compose up -d
   ```

#### 4. LLM/OpenAI Errors

**Symptom**: Agent chat returns errors about API keys or rate limits

**Solutions**:
1. Verify your API key:
   ```bash
   curl https://api.openai.com/v1/models \
     -H "Authorization: Bearer $OPENAI_API_KEY"
   ```
2. Check your OpenAI account has credits
3. Try a different model:
   ```bash
   OPENAI_MODEL=gpt-3.5-turbo  # Cheaper, faster
   ```

#### 5. Web Search Not Working

**Symptom**: "web_search tool failed" or empty results

**Solutions**:
1. Verify Serper API key:
   ```bash
   curl -X POST https://google.serper.dev/search \
     -H "X-API-KEY: $SERPER_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{"q": "test"}'
   ```
2. Check your Serper account has remaining queries
3. Ensure the agent has web_search in its tools list

#### 6. Frontend Can't Connect to API

**Symptom**: Network errors in browser console, CORS errors

**Solutions**:
1. Verify CORS origins include frontend URL:
   ```bash
   CORS_ORIGINS=http://localhost:3000,http://localhost:8100
   ```
2. Check API is running:
   ```bash
   curl http://localhost:8100/api/v1/health
   ```
3. Check browser developer tools (Network tab) for actual error

#### 7. Voice Not Working

**Symptom**: Voice calls fail, no audio

**Solutions**:
1. Ensure LiveKit is running:
   ```bash
   docker compose -f docker-compose.yml -f docker-compose.livekit.yml up -d
   docker compose logs brigade-livekit
   ```
2. Check voice provider is available:
   ```bash
   curl -H "X-API-Key: YOUR_KEY" http://localhost:8100/api/v1/voice/health
   ```
3. Verify browser has microphone permissions

### How to Check Logs

#### View All Service Logs

```bash
docker compose logs -f              # All services, follow mode
docker compose logs brigade-api     # API only
docker compose logs brigade-frontend  # Frontend only
```

#### View Specific Time Range

```bash
docker compose logs --since 1h brigade-api  # Last hour
docker compose logs --since 30m --until 10m brigade-api  # 30-10 minutes ago
```

#### Check Application Logs

```bash
# Logs are also written to disk
ls -la ./logs/
cat ./logs/app.log | tail -100
```

### How to Verify Services are Running

```bash
# Check container status
docker compose ps

# Expected output:
# NAME                STATUS
# brigade-api         running (healthy)
# brigade-frontend    running (healthy)
# brigade-postgres    running (healthy)
# brigade-redis       running (healthy)
# brigade-qdrant      running (healthy)

# Check individual service health
docker inspect brigade-api --format='{{.State.Health.Status}}'

# Check resource usage
docker stats --no-stream
```

### Getting Help

1. **Check the logs first** - Most issues are visible in `docker compose logs`
2. **Review CLAUDE.md** - Contains detailed technical documentation
3. **API Documentation** - Available at `http://localhost:8100/docs`
4. **GitHub Issues** - Search existing issues or create a new one

---

## Quick Reference

### Start/Stop Commands

```bash
# Start core services
docker compose up -d

# Start with optional services
docker compose -f docker-compose.yml -f docker-compose.langfuse.yml up -d

# Stop all services
docker compose down

# Stop and remove volumes (data loss!)
docker compose down -v

# Restart a specific service
docker compose restart brigade-api

# View logs
docker compose logs -f brigade-api
```

### Common API Calls

```bash
# Health check
curl http://localhost:8100/api/v1/health

# List agents
curl -H "X-API-Key: $KEY" http://localhost:8100/api/v1/agents

# Chat with agent
curl -X POST http://localhost:8100/api/v1/agents/{agent_id}/chat \
  -H "X-API-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello"}'

# Create API key
curl -X POST http://localhost:8100/api/v1/agents/{agent_id}/api-keys \
  -H "X-API-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{"name": "My Key", "permissions": ["chat"]}'
```

### Port Reference

| Port | Service | Description |
|------|---------|-------------|
| 3000 | Frontend | React UI |
| 8100 | API | FastAPI backend |
| 5432 | PostgreSQL | Database |
| 6379 | Redis | Cache |
| 6333 | Qdrant | Vector DB |
| 3001 | Langfuse | Observability UI |
| 3002 | FalkorDB | Knowledge graph browser |
| 7860 | Langflow | Visual workflow builder |
| 7880 | LiveKit | Voice server |

---

*Last Updated: January 30, 2026*
