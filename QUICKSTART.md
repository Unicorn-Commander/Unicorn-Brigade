# Unicorn Brigade - Agent Builder Quick Start

## 🚀 Get Started in 5 Minutes

### 1. Setup (One Time)

```bash
# Run automated setup
./scripts/setup-agent-builder.sh

# Add your API key to .env
echo "OPENROUTER_API_KEY=your_key_here" >> .env
```

### 2. Start Services

**Terminal 1 - Backend**:
```bash
npm run dev
```

**Terminal 2 - Frontend**:
```bash
cd frontend && npm run dev
```

### 3. Test Everything

**Terminal 3**:
```bash
./scripts/test-agent-builder.sh
```

### 4. Build Your First Agent

1. Open http://localhost:8113/builder-chat
2. Chat with The General:
   ```
   "I need a financial analyst agent that can analyze company
   financial statements and provide investment recommendations."
   ```
3. Answer The General's questions
4. Confirm the configuration
5. Your agent is created! 🎉

### 5. View Your Agents

Open http://localhost:8113/library to see all your agents.

---

## 📚 Key URLs

| Service | URL | Description |
|---------|-----|-------------|
| The General | http://localhost:8113/builder-chat | Chat to create agents |
| Agent Library | http://localhost:8113/library | Browse all agents |
| API Docs | http://localhost:8112 | Backend API |
| Health Check | http://localhost:8112/health | System status |

---

## 🎯 Quick Examples

### Create Agent via API

```bash
curl -X POST http://localhost:8112/api/agents-new \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My Agent",
    "title": "My Specialist",
    "domain": "technology",
    "systemPrompt": "You are a helpful agent.",
    "model": "gpt-4-turbo",
    "temperature": 0.7,
    "maxTokens": 2048
  }'
```

### List All Agents

```bash
curl http://localhost:8112/api/agents-new
```

### Invoke an Agent

```bash
# 1. Generate API key
curl -X POST http://localhost:8112/api/agents-new/{agent-id}/api-keys \
  -H "Content-Type: application/json" \
  -d '{"name": "My Key"}'

# 2. Use the key to invoke
curl -X POST http://localhost:8112/api/agents-new/{agent-id}/invoke \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ub_your_key_here" \
  -d '{"message": "Hello agent!"}'
```

---

## 🐛 Troubleshooting

### Backend won't start
```bash
# Run migrations
npm run migrate

# Check logs
npm run dev
```

### Frontend won't start
```bash
cd frontend
npm install
npm run dev
```

### The General not responding
```bash
# Check your .env has OPENROUTER_API_KEY
cat .env | grep OPENROUTER

# Test the service
curl http://localhost:8112/api/agent-builder/info
```

### Database errors
```bash
# Reset database (WARNING: deletes all data)
rm unicorn.db
npm run migrate
```

---

## 📖 Full Documentation

- **Setup Guide**: `AGENT_BUILDER_SETUP.md`
- **Implementation Report**: `AGENT_BUILDER_REPORT.md`
- **Prisma Schema**: `prisma/schema.prisma`

---

## 💬 Need Help?

1. Check the logs (backend console and browser console)
2. Run tests: `./scripts/test-agent-builder.sh`
3. Read full docs: `AGENT_BUILDER_SETUP.md`
4. Check environment variables in `.env`

---

## 🎖️ The General's Domains

The General can create agents in these domains:

- **financial** - Bookkeeping, investment, tax, forensics
- **legal** - Contracts, litigation, compliance, research
- **medical** - Diagnosis, research, patient care
- **technology** - Software, cybersecurity, data science, cloud
- **investigation** - OSINT, fraud detection, research
- **orchestration** - Multi-agent coordination
- **meta** - Agent building, system management
- **intelligence** - Information gathering and analysis

---

**Ready to build? Start chatting with The General!** 🦄⚔️

http://localhost:8113/builder-chat
