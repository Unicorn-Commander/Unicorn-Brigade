# 🦄 Unicorn Brigade - UC-Cloud Integration Guide

## Overview

**Unicorn Brigade** is deployed as a **microservice** within the UC-Cloud ecosystem. This document explains how Brigade integrates with UC-Cloud infrastructure and how to deploy it in production.

---

## 🏗️ Integration Architecture

### Brigade's Role in UC-Cloud Ecosystem

```
UC-Cloud Ecosystem
│
├── Ops-Center (Main Dashboard)
│   ├── Service monitoring
│   ├── Billing (Lago)
│   ├── User management
│   └── LLM routing
│
├── Open-WebUI (Chat Interface)
│   ├── Conversations
│   ├── MCP tool use
│   └── Multi-model chat
│
├── **Unicorn Brigade** (Agent Management) ← YOU ARE HERE
│   ├── Build agents (Gunny chat)
│   ├── Browse agent library
│   ├── Agent Cards (A2A protocol)
│   └── Agent API endpoints
│
└── Center-Deep (Search)
    └── Metasearch engine
```

### What Brigade Does

**Brigade is the "Agent Factory"**:
- Users come here to **BUILD** and **MANAGE** agents
- Once agents exist, they're **USED** in Open-WebUI
- Everything is **MONITORED** in Ops-Center
- Everything is **AUTHENTICATED** via Keycloak

**Think of it like**:
- **Ops-Center** = AWS Console (infrastructure management)
- **Brigade** = GitHub (code/agent repository)
- **Open-WebUI** = VS Code (where you actually work)
- **Center-Deep** = Google Search (research tool)

---

## 🔌 Shared Infrastructure

### What Brigade Uses from UC-Cloud

#### 1. **PostgreSQL Database**
- **Container**: `unicorn-postgresql`
- **Host**: `unicorn-postgresql:5432`
- **Database**: `brigade_db` (separate database)
- **Schema**: Managed by Prisma (auto-created)
- **Connection**: Via DATABASE_URL environment variable

#### 2. **Redis Cache**
- **Container**: `unicorn-redis`
- **Host**: `unicorn-redis:6379`
- **Usage**: Session storage, caching, rate limiting
- **Connection**: Via REDIS_URL environment variable

#### 3. **Keycloak SSO (uchub realm)**
- **Container**: `uchub-keycloak`
- **URL**: `https://auth.unicorncommander.ai`
- **Realm**: `uchub`
- **Client ID**: `brigade`
- **Purpose**: Single Sign-On authentication
- **Identity Providers**: Google, GitHub, Microsoft

#### 4. **Traefik Reverse Proxy**
- **Container**: `traefik`
- **Routes**:
  - `brigade.unicorncommander.ai` → Frontend
  - `api.brigade.unicorncommander.ai` → Backend API
- **SSL/TLS**: Let's Encrypt certificates (automatic)

#### 5. **Ops-Center LLM Router**
- **Container**: `ops-center-direct`
- **Endpoint**: `http://ops-center-direct:8084/api/v1/llm/chat/completions`
- **Purpose**: LLM inference routing (instead of direct OpenAI calls)
- **Billing**: Usage tracked via Ops-Center

#### 6. **Docker Networks**
- `unicorn-network`: Internal service communication
- `web`: Traefik routing
- `uchub-network`: Keycloak authentication

---

## 📦 Deployment Configuration

### Docker Compose Structure

Brigade has its own compose file that integrates with UC-Cloud:

```yaml
# /home/muut/Production/UC-Cloud/docker-compose.brigade.yml

services:
  unicorn-brigade:
    build: ./Unicorn-Brigade/Dockerfile.backend
    ports: ["8101:8112"]
    environment:
      # Shared infrastructure
      DATABASE_URL: postgresql://unicorn:${POSTGRES_PASSWORD}@unicorn-postgresql:5432/brigade_db
      REDIS_URL: redis://unicorn-redis:6379
      OPS_CENTER_URL: http://ops-center-direct:8084

      # Keycloak SSO
      KEYCLOAK_URL: https://auth.unicorncommander.ai
      KEYCLOAK_REALM: uchub
      KEYCLOAK_CLIENT_ID: brigade
      KEYCLOAK_CLIENT_SECRET: REMOVED

      # Public URLs
      BRIGADE_URL: https://brigade.unicorncommander.ai
      BRIGADE_API_URL: https://api.brigade.unicorncommander.ai
      BRIGADE_FRONTEND_URL: https://brigade.unicorncommander.ai
      BRIGADE_CALLBACK_URL: https://api.brigade.unicorncommander.ai/api/auth/oidc/callback
    networks:
      - unicorn-network
      - web
      - uchub-network
    volumes:
      - ./Unicorn-Brigade/agents:/app/agents:ro
      - ./Unicorn-Brigade/tools:/app/tools:ro
      - brigade_backend_logs:/app/logs
      - brigade_uploads:/app/uploads
    labels:
      # Traefik routing
      - "traefik.enable=true"
      - "traefik.http.routers.brigade-backend.rule=Host(`api.brigade.unicorncommander.ai`)"
      - "traefik.http.routers.brigade-backend.entrypoints=https"
      - "traefik.http.routers.brigade-backend.tls.certresolver=letsencrypt"

  unicorn-brigade-ui:
    build: ./Unicorn-Brigade/Dockerfile.frontend
    ports: ["8102:80"]
    environment:
      VITE_API_URL: https://api.brigade.unicorncommander.ai/api
      VITE_WS_URL: wss://api.brigade.unicorncommander.ai
      VITE_OPS_CENTER_URL: https://unicorncommander.ai
    networks:
      - unicorn-network
      - web
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.brigade-ui.rule=Host(`brigade.unicorncommander.ai`)"
      - "traefik.http.routers.brigade-ui.entrypoints=https"
      - "traefik.http.routers.brigade-ui.tls.certresolver=letsencrypt"

networks:
  unicorn-network:
    external: true
  web:
    external: true
  uchub-network:
    external: true

volumes:
  brigade_backend_logs:
    name: uc-cloud_brigade_backend_logs
  brigade_uploads:
    name: uc-cloud_brigade_uploads
```

---

## 🚀 Production Deployment

### Prerequisites

Brigade requires UC-Cloud infrastructure to be running:

```bash
# Verify required services are running
docker ps | grep -E "unicorn-postgresql|unicorn-redis|uchub-keycloak|traefik|ops-center"
```

Should show:
- ✅ `unicorn-postgresql`
- ✅ `unicorn-redis`
- ✅ `uchub-keycloak`
- ✅ `traefik`
- ✅ `ops-center-direct`

### Step 1: Database Setup

Brigade uses a separate database in the shared PostgreSQL instance:

```bash
# Create brigade_db database (if not exists)
docker exec unicorn-postgresql psql -U unicorn -c "CREATE DATABASE brigade_db;"

# Initialize Prisma schema
cd /home/muut/Production/UC-Cloud/Unicorn-Brigade
npx prisma db push
```

### Step 2: Keycloak Configuration

Brigade client must be configured in Keycloak `uchub` realm:

```bash
# Get Keycloak admin token
docker exec uchub-keycloak /opt/keycloak/bin/kcadm.sh config credentials \
  --server http://localhost:8080 \
  --realm master \
  --user admin \
  --password MagicUnicorn2025!

# Verify brigade client exists
docker exec uchub-keycloak /opt/keycloak/bin/kcadm.sh get clients \
  --realm uchub \
  --fields clientId,redirectUris | grep -A 5 brigade
```

**Expected redirect URIs**:
- `https://api.brigade.unicorncommander.ai/api/auth/oidc/callback`
- `http://localhost:8112/api/auth/oidc/callback` (development)

### Step 3: Build Docker Images

```bash
cd /home/muut/Production/UC-Cloud

# Build backend
docker compose -f docker-compose.brigade.yml build unicorn-brigade

# Build frontend
docker compose -f docker-compose.brigade.yml build unicorn-brigade-ui
```

### Step 4: Start Services

```bash
# Start both containers
docker compose -f docker-compose.brigade.yml up -d

# Verify they're running
docker ps | grep brigade

# Check logs
docker logs unicorn-brigade --tail 50
docker logs unicorn-brigade-ui --tail 50
```

### Step 5: Verify Deployment

```bash
# Check backend health
curl https://api.brigade.unicorncommander.ai/health

# Check frontend (should return HTML)
curl -I https://brigade.unicorncommander.ai

# Test Keycloak login redirect
curl -I https://brigade.unicorncommander.ai/login
```

---

## 🔧 Configuration Files

### Environment Variables

Brigade uses these files for configuration:

#### Backend: `/Unicorn-Brigade/.env`
```env
# Database (shared PostgreSQL)
DATABASE_URL=postgresql://unicorn:REMOVED@unicorn-postgresql:5432/brigade_db?schema=public

# Redis (shared)
REDIS_URL=redis://unicorn-redis:6379

# Keycloak SSO
KEYCLOAK_URL=https://auth.unicorncommander.ai
KEYCLOAK_REALM=uchub
KEYCLOAK_CLIENT_ID=brigade
KEYCLOAK_CLIENT_SECRET=REMOVED

# Public URLs
BRIGADE_URL=https://brigade.unicorncommander.ai
BRIGADE_API_URL=https://api.brigade.unicorncommander.ai
BRIGADE_CALLBACK_URL=https://api.brigade.unicorncommander.ai/api/auth/oidc/callback
BRIGADE_FRONTEND_URL=https://brigade.unicorncommander.ai

# Ops-Center integration
OPS_CENTER_URL=http://ops-center-direct:8084
OPS_CENTER_LLM_ENDPOINT=http://ops-center-direct:8084/api/v1/llm/chat/completions

# Security
JWT_SECRET=your-jwt-secret-here
SESSION_SECRET=your-session-secret-here

# Node
NODE_ENV=production
PORT=8112
```

#### Frontend: `/Unicorn-Brigade/frontend/.env`
```env
VITE_API_URL=https://api.brigade.unicorncommander.ai/api
VITE_WS_URL=wss://api.brigade.unicorncommander.ai
VITE_OPS_CENTER_URL=https://unicorncommander.ai
VITE_NODE_ENV=production
```

---

## 📊 Database Schema

Brigade creates these tables in `brigade_db`:

```sql
-- Users (synced from Keycloak)
CREATE TABLE "User" (
  id TEXT PRIMARY KEY,
  username TEXT,
  email TEXT UNIQUE,
  keycloakId TEXT,
  role TEXT DEFAULT 'user'
);

-- Sessions (for cookie auth)
CREATE TABLE "Session" (
  id TEXT PRIMARY KEY,
  userId TEXT REFERENCES "User"(id),
  token TEXT,
  refreshToken TEXT,
  expiresAt TIMESTAMP
);

-- Agents (core data)
CREATE TABLE "Agent" (
  id TEXT PRIMARY KEY,
  name TEXT UNIQUE,
  displayName TEXT,
  domain TEXT,
  subdomain TEXT,
  rank TEXT,
  avatar TEXT,
  bio TEXT,
  title TEXT,
  systemPrompt TEXT,
  model TEXT,
  temperature REAL,
  maxTokens INTEGER,
  status TEXT,
  capabilities TEXT[], -- JSON array
  createdAt TIMESTAMP,
  updatedAt TIMESTAMP,
  createdBy TEXT REFERENCES "User"(id),
  sessionId TEXT  -- Link to build session
);

-- Tools available to agents
CREATE TABLE "Tool" (
  id TEXT PRIMARY KEY,
  name TEXT,
  description TEXT,
  type TEXT,
  schema JSONB
);

-- Agent-Tool mappings
CREATE TABLE "AgentTool" (
  id TEXT PRIMARY KEY,
  agentId TEXT REFERENCES "Agent"(id),
  toolId TEXT REFERENCES "Tool"(id),
  config JSONB
);

-- API Keys for agent access
CREATE TABLE "AgentApiKey" (
  id TEXT PRIMARY KEY,
  agentId TEXT REFERENCES "Agent"(id),
  name TEXT,
  key TEXT,  -- Hashed
  keyPrefix TEXT,
  permissions TEXT[], -- JSON array
  expiresAt TIMESTAMP,
  isActive BOOLEAN,
  createdAt TIMESTAMP
);

-- Build history from Gunny
CREATE TABLE "BuildSession" (
  id TEXT PRIMARY KEY,
  userId TEXT REFERENCES "User"(id),
  agentId TEXT REFERENCES "Agent"(id),
  messages JSONB,
  phase TEXT,  -- discovery, design, review, created
  createdAt TIMESTAMP,
  completedAt TIMESTAMP
);
```

---

## 🔐 Security & Authentication Flow

### Login Flow

```
1. User visits https://brigade.unicorncommander.ai
2. Frontend detects no session → redirects to /login
3. Login page auto-initiates SSO → GET /api/auth/oidc/login
4. Backend generates OIDC URL → redirects to Keycloak
5. Keycloak shows login page (Google/GitHub/Microsoft/Username+Password)
6. User authenticates → Keycloak redirects with code
7. Backend receives code at /api/auth/oidc/callback
8. Backend exchanges code for tokens → creates user in brigade_db
9. Backend sets session cookie (domain: .unicorncommander.ai)
10. Backend redirects to https://brigade.unicorncommander.ai/dashboard
11. User is authenticated ✅
```

### API Authentication

```javascript
// All API requests include session cookie automatically
fetch('https://api.brigade.unicorncommander.ai/api/agents', {
  credentials: 'include',  // Sends cookies cross-domain
  headers: {
    'Content-Type': 'application/json'
  }
});
```

### Cross-Subdomain Cookies

Brigade sets cookies with `domain: .unicorncommander.ai` so they work across:
- `brigade.unicorncommander.ai` (frontend)
- `api.brigade.unicorncommander.ai` (backend API)
- `unicorncommander.ai` (Ops-Center)

---

## 🛠️ Maintenance & Operations

### Common Tasks

#### Update Brigade Code
```bash
cd /home/muut/Production/UC-Cloud/Unicorn-Brigade

# Pull latest changes (if from git)
git pull origin main

# Rebuild images
docker compose -f ../docker-compose.brigade.yml build

# Restart containers
docker compose -f ../docker-compose.brigade.yml restart
```

#### View Logs
```bash
# Backend logs
docker logs unicorn-brigade -f

# Frontend logs
docker logs unicorn-brigade-ui -f

# Filter for errors
docker logs unicorn-brigade 2>&1 | grep -i error
```

#### Database Migrations
```bash
cd /home/muut/Production/UC-Cloud/Unicorn-Brigade

# After schema changes in prisma/schema.prisma
npx prisma generate
npx prisma db push

# Restart backend to pick up changes
docker compose -f ../docker-compose.brigade.yml restart unicorn-brigade
```

#### Clear User Sessions
```bash
# Clear all sessions (force re-login)
docker exec unicorn-postgresql psql -U unicorn -d brigade_db -c "DELETE FROM \"Session\";"
```

#### Backup Brigade Data
```bash
# Backup database
docker exec unicorn-postgresql pg_dump -U unicorn brigade_db > brigade_backup_$(date +%Y%m%d).sql

# Backup uploaded files
tar -czf brigade_uploads_$(date +%Y%m%d).tar.gz \
  /var/lib/docker/volumes/uc-cloud_brigade_uploads/_data/
```

---

## 🔄 Standalone Deployment (Optional)

If you want to run Brigade **without** UC-Cloud infrastructure:

### Requirements

You'll need to deploy:
1. **PostgreSQL** - Your own database server
2. **Redis** - Your own cache server
3. **Keycloak** - Your own auth server (or use a different auth method)
4. **Reverse Proxy** - Nginx/Caddy for SSL

### Modified docker-compose.yml

```yaml
version: '3.8'

services:
  brigade-postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: brigade
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: brigade_db
    volumes:
      - brigade_postgres_data:/var/lib/postgresql/data

  brigade-redis:
    image: redis:7-alpine
    volumes:
      - brigade_redis_data:/data

  brigade-backend:
    build: ./Dockerfile.backend
    environment:
      DATABASE_URL: postgresql://brigade:${POSTGRES_PASSWORD}@brigade-postgres:5432/brigade_db
      REDIS_URL: redis://brigade-redis:6379
      # ... rest of config
    depends_on:
      - brigade-postgres
      - brigade-redis

  brigade-frontend:
    build: ./Dockerfile.frontend
    # ... config
    depends_on:
      - brigade-backend

volumes:
  brigade_postgres_data:
  brigade_redis_data:
```

**Note**: Standalone deployment is **not recommended** because:
- Loses SSO integration with UC-Cloud
- Loses Ops-Center LLM routing (cost optimization)
- Loses billing integration
- Requires duplicate infrastructure

---

## 📈 Monitoring & Observability

### Health Checks

Brigade provides health endpoints:

```bash
# Backend health
curl https://api.brigade.unicorncommander.ai/health

# Response: {"status":"healthy","timestamp":"2025-10-15T..."}
```

### Metrics

Brigade integrates with Ops-Center for monitoring:

- **API Requests**: Tracked per endpoint
- **LLM Calls**: Routed through Ops-Center
- **Response Times**: Measured and logged
- **Error Rates**: Tracked in logs
- **User Sessions**: Active sessions count

### Logs

Logs are stored in Docker volumes:

```bash
# View backend logs
docker exec unicorn-brigade ls -lah /app/logs/

# Tail error log
docker exec unicorn-brigade tail -f /app/logs/error.log

# Export logs
docker cp unicorn-brigade:/app/logs/ ./brigade-logs/
```

---

## 🚨 Troubleshooting

### "Failed to load dashboard data"

**Cause**: Frontend calling wrong API endpoint

**Fix**: Verify frontend environment variables:
```bash
docker exec unicorn-brigade-ui cat /usr/share/nginx/html/assets/*.js | grep -o 'VITE_API_URL.*'
```

Should show: `https://api.brigade.unicorncommander.ai/api`

**Rebuild if needed**:
```bash
docker compose -f docker-compose.brigade.yml build unicorn-brigade-ui
docker compose -f docker-compose.brigade.yml restart unicorn-brigade-ui
```

### "401 Unauthorized" on API calls

**Cause**: Session cookie not being sent or expired

**Fix**:
1. Clear browser cookies for `brigade.unicorncommander.ai`
2. Login again
3. Check cookie domain in browser DevTools (should be `.unicorncommander.ai`)

### "Invalid parameter: redirect_uri" from Keycloak

**Cause**: Callback URL not registered in Keycloak client

**Fix**:
```bash
# Update Keycloak brigade client
CLIENT_ID=$(docker exec uchub-keycloak /opt/keycloak/bin/kcadm.sh get clients --realm uchub --fields id,clientId | grep -B 1 '"clientId" : "brigade"' | grep '"id"' | cut -d'"' -f4)

docker exec uchub-keycloak /opt/keycloak/bin/kcadm.sh update clients/$CLIENT_ID --realm uchub \
  -s 'redirectUris=["https://api.brigade.unicorncommander.ai/api/auth/oidc/callback","http://localhost:8112/api/auth/oidc/callback"]'
```

### "Cannot connect to database"

**Cause**: PostgreSQL not running or brigade_db doesn't exist

**Fix**:
```bash
# Check PostgreSQL is running
docker ps | grep unicorn-postgresql

# Create database if missing
docker exec unicorn-postgresql psql -U unicorn -c "CREATE DATABASE brigade_db;"

# Push Prisma schema
cd /home/muut/Production/UC-Cloud/Unicorn-Brigade
npx prisma db push
```

---

## 📝 Summary

**Unicorn Brigade Integration Summary**:

- ✅ **Deployment**: Microservice in UC-Cloud monorepo
- ✅ **Database**: Separate `brigade_db` in shared PostgreSQL
- ✅ **Authentication**: Keycloak `uchub` realm SSO
- ✅ **Caching**: Shared Redis instance
- ✅ **LLM Routing**: Via Ops-Center (not direct OpenAI)
- ✅ **Reverse Proxy**: Traefik with Let's Encrypt SSL
- ✅ **Monitoring**: Integrated with Ops-Center
- ✅ **Billing**: Usage tracked via Ops-Center → Lago

**Repository Strategy**: Keep in UC-Cloud monorepo as a microservice

**Why Monorepo?**
- Shares infrastructure (PostgreSQL, Redis, Keycloak, Traefik)
- Easier to maintain consistent versions
- Single deployment process
- Integrated monitoring and billing
- Simplified authentication flow

---

**Built with 💜 by Magic Unicorn Unconventional Technology & Stuff Inc.**
