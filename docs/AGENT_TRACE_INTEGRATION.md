# Agent Trace - Code Attribution Tracking

**Agent Trace** is Unicorn Brigade's implementation of the [agent-trace.dev](https://agent-trace.dev/) specification for tracking AI-generated code contributions. It provides enterprise-grade audit trails for compliance, debugging, and understanding which agents/models wrote which code.

---

## What is Agent Trace?

Agent Trace automatically records metadata whenever an AI agent generates or modifies code:

- **Who**: Which agent (e.g., "Cpt. Fullstack", "Code Reviewer")
- **What Model**: Which LLM (e.g., "gpt-4o", "claude-sonnet-4")
- **When**: Timestamp of generation
- **Where**: File path and line range
- **Why**: Original prompt that led to the code
- **What**: The actual code generated

This creates a complete **provenance trail** for all AI-generated code in your codebase.

---

## Why Use Agent Trace?

### 1. Compliance & Audit Trails
- **Enterprise requirement**: Know exactly what code was AI-generated vs human-written
- **Regulatory compliance**: GDPR, SOC2, ISO 27001 require audit trails
- **Legal protection**: Prove which agent generated problematic code

### 2. Debugging & Understanding
- **Code review**: See which agent wrote each function
- **Bug investigation**: Trace bugs back to the agent/model that introduced them
- **Quality tracking**: Compare code quality across different models

### 3. Cost Attribution
- **Billing**: Attribute API costs to specific agents/projects
- **ROI tracking**: Measure productivity gains per agent
- **Optimization**: Identify which models produce best code at lowest cost

### 4. Learning & Improvement
- **Pattern analysis**: Which prompts produce best code?
- **Model comparison**: Which models excel at which tasks?
- **Agent effectiveness**: Which agents need prompt tuning?

---

## How It Works

### Automatic Recording

Every time an agent generates code, Agent Trace automatically records:

```python
{
  "session_id": "session_abc123",
  "agent_id": "cpt-fullstack",
  "agent_name": "Cpt. Fullstack",
  "model": "openai/gpt-4o",
  "file_path": "app/api/users.py",
  "start_line": 42,
  "end_line": 58,
  "code_hash": "sha256:...",
  "prompt": "Create a new endpoint for user registration",
  "generated_code": "def register_user(...):\n    ...",
  "created_at": "2026-01-31T15:30:00Z"
}
```

### Integration Points

Agent Trace hooks into:

1. **LLM Client** (`ops_center_client.py`): Records all code generations
2. **File Write Tool**: Tracks when agents write to files
3. **Code Edit Tool**: Tracks modifications to existing code
4. **Workflow Steps**: Associates code with workflow execution context

### Storage

Attribution records are stored in PostgreSQL for:
- Fast queries by file, agent, or date range
- Efficient compliance report generation
- Long-term audit trail preservation

---

## API Endpoints

### Get Attributions for a File

```bash
GET /api/v1/trace/files/app/api/users.py

Response:
{
  "file_path": "app/api/users.py",
  "total_lines": 150,
  "ai_generated_lines": 58,
  "attributions": [
    {
      "id": "attr_123",
      "agent_id": "cpt-fullstack",
      "agent_name": "Cpt. Fullstack",
      "model": "openai/gpt-4o",
      "start_line": 42,
      "end_line": 58,
      "prompt": "Create user registration endpoint",
      "created_at": "2026-01-31T15:30:00Z"
    }
  ]
}
```

### Get All Code by an Agent

```bash
GET /api/v1/trace/agents/cpt-fullstack?limit=50

Response:
{
  "agent_id": "cpt-fullstack",
  "agent_name": "Cpt. Fullstack",
  "total_contributions": 142,
  "total_lines": 3847,
  "files_touched": 23,
  "contributions": [
    {
      "id": "attr_456",
      "file_path": "app/api/users.py",
      "start_line": 42,
      "end_line": 58,
      "model": "openai/gpt-4o",
      "created_at": "2026-01-31T15:30:00Z"
    }
  ]
}
```

### Get Recent Activity

```bash
GET /api/v1/trace/recent?period=7d

Response:
{
  "period": "7d",
  "total_contributions": 89,
  "total_lines": 2341,
  "contributions": [
    {
      "id": "attr_789",
      "agent_id": "code-reviewer",
      "file_path": "app/utils/validation.py",
      "start_line": 15,
      "end_line": 28,
      "created_at": "2026-01-31T14:00:00Z"
    }
  ]
}
```

### Get Statistics

```bash
GET /api/v1/trace/stats

Response:
{
  "total_contributions": 1247,
  "total_lines": 34582,
  "total_files": 187,
  "total_agents": 11,
  "by_agent": {
    "cpt-fullstack": {"contributions": 342, "lines": 8921},
    "code-reviewer": {"contributions": 156, "lines": 3241}
  },
  "by_model": {
    "openai/gpt-4o": {"contributions": 687, "lines": 19234},
    "anthropic/claude-sonnet-4": {"contributions": 560, "lines": 15348}
  },
  "recent_trend": [
    {"date": "2026-01-31", "contributions": 47, "lines": 1203},
    {"date": "2026-01-30", "contributions": 52, "lines": 1456}
  ]
}
```

### Generate Compliance Report

```bash
POST /api/v1/trace/report
{
  "start_date": "2026-01-01",
  "end_date": "2026-01-31",
  "format": "csv",
  "include_code": false
}

Response:
{
  "report_url": "/reports/trace_2026-01.csv",
  "total_records": 1247,
  "generated_at": "2026-01-31T16:00:00Z"
}
```

---

## Frontend UI

Access the **Code Attribution** page at `/code-attribution` to:

### 1. By File View
- Browse all files with AI-generated code
- See line-by-line attribution with syntax highlighting
- View original prompts that generated each code block

### 2. By Agent View
- List all agents that have generated code
- See statistics per agent (total lines, files, models used)
- Drill down into specific contributions

### 3. Recent Activity
- Timeline of recent code generations
- Filter by time period (24h, 7d, 30d)
- Real-time updates

### 4. Statistics Dashboard
- Total lines of AI-generated code
- Most active agents
- Most modified files
- Model usage breakdown (charts)
- Generation trends over time

---

## Configuration

### Enable/Disable Agent Trace

```bash
# .env
AGENT_TRACE_ENABLED=true  # Default: true
```

### Retention Policy

```bash
# .env
AGENT_TRACE_RETENTION_DAYS=90  # Default: 90 days
```

### Storage Location

Attribution records are stored in PostgreSQL `code_attributions` table.

---

## Compliance Report Example

**CSV Export:**

```csv
ID,Agent,Model,File,Lines,Prompt,Timestamp
attr_123,Cpt. Fullstack,openai/gpt-4o,app/api/users.py,42-58,"Create user registration",2026-01-31T15:30:00Z
attr_124,Code Reviewer,anthropic/claude-sonnet-4,app/utils/validation.py,15-28,"Add input validation",2026-01-31T14:00:00Z
```

**JSON Export:**

```json
{
  "report_period": {
    "start": "2026-01-01",
    "end": "2026-01-31"
  },
  "summary": {
    "total_contributions": 1247,
    "total_lines": 34582,
    "unique_agents": 11,
    "unique_models": 3
  },
  "contributions": [...]
}
```

---

## Privacy & Security

### What's Tracked
- Agent ID and name
- Model used
- File path and line range
- Prompt (sanitized)
- Code content
- Timestamp

### What's NOT Tracked
- User personal data
- API keys or secrets
- Environment variables
- Database connection strings

### Access Control
- Agent Trace endpoints require authentication
- Admin role required for report generation
- Viewer role can see attributions for their own sessions

---

## Use Cases

### 1. Code Review
**Before Agent Trace:**
```
Reviewer: "Who wrote this function?"
Dev: "Uh, I think it was the agent... not sure which one."
```

**With Agent Trace:**
```
Reviewer: Clicks on function → Sees "Generated by Cpt. Fullstack using gpt-4o"
Reviewer: Reads original prompt → "Create async endpoint for user data"
Reviewer: "Ah, this needs caching. Let me ask the agent to revise."
```

### 2. Bug Investigation
**Before Agent Trace:**
```
Bug report: "API endpoint returns 500 error"
Dev: "Need to trace through git history and review PRs..."
```

**With Agent Trace:**
```
Check file → See line 47-62 generated by "support-agent" with prompt "Add error handling"
Review: Agent forgot to handle null case
Fix: Ask agent to regenerate with better prompt
```

### 3. Compliance Audit
**Before Agent Trace:**
```
Auditor: "Show me all AI-generated code in production."
Team: "We'd have to manually review all commits..."
```

**With Agent Trace:**
```
Generate compliance report → Export CSV with all attributions
Auditor: "Perfect, I can see exactly what was AI-generated."
```

### 4. Cost Optimization
**Before Agent Trace:**
```
Finance: "Our AI costs are high. Where is it coming from?"
Team: "Not sure, let's look at API logs..."
```

**With Agent Trace:**
```
Check stats → "code-reviewer agent used 80% of GPT-4o credits"
Decision: "Switch code-reviewer to Claude Sonnet 4 (cheaper, better)"
```

---

## Limitations

### Not a Silver Bullet
Agent Trace tracks **code generation**, not code correctness or quality. You still need:
- Code review
- Testing
- Human oversight

### Partial Coverage
Only tracks code generated **through Unicorn Brigade**. Manual edits or code from external tools won't be attributed.

### Storage Growth
Attribution records grow over time. Set retention policies to manage database size.

---

## Roadmap

Future enhancements:

- [ ] **Diff visualization**: Highlight AI-generated lines in file viewer
- [ ] **Prompt templates**: Tag prompts for pattern analysis
- [ ] **Quality scoring**: Rate code quality per agent/model
- [ ] **Real-time alerts**: Notify when agent generates suspicious code
- [ ] **Git integration**: Add attribution metadata to commit messages
- [ ] **Cost tracking**: Link to actual API costs from OpenRouter/Anthropic
- [ ] **SBOM generation**: Export Software Bill of Materials for compliance

---

## Credits

Agent Trace implements the [agent-trace.dev](https://agent-trace.dev/) specification for standardized code attribution tracking across AI development tools.

---

**Status:** Production-ready (Jan 31, 2026)
**Location:** `app/observability/agent_trace.py`
**API:** `/api/v1/trace/*`
**Frontend:** `/code-attribution`
**Database:** `code_attributions` table
