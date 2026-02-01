# Agent Trace - Code Attribution Tracking

Agent Trace is Unicorn Brigade's implementation of the [Agent Trace spec v1.0](https://agent-trace.dev/) for tracking which AI agents and models generated which code. This provides essential audit trails for enterprise compliance, code governance, and debugging.

## Overview

### What is Agent Trace?

Agent Trace provides:

- **Code Attribution**: Track which agent generated each line of code
- **Audit Trails**: Complete history of code modifications by AI agents
- **Compliance**: Enterprise-grade reporting for regulatory requirements
- **Debugging**: Trace code back to the original prompt and agent
- **Governance**: Understand AI's contribution to your codebase

### Key Features

- ✅ **Automatic Code Extraction**: Auto-detect code blocks in LLM responses
- ✅ **Database Persistence**: PostgreSQL storage with efficient indexing
- ✅ **Langfuse Integration**: Correlate code attribution with LLM traces
- ✅ **Compliance Reports**: Generate audit reports in JSON, CSV formats
- ✅ **Session Tracking**: Track all code generated in a conversation
- ✅ **File History**: Complete modification history for any file
- ✅ **Agent Statistics**: Analyze productivity and code quality by agent

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      Agent Chat / API                            │
└─────────────────────┬───────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                 OpsCenterLLMClient                               │
│              (execute_tool_loop with tracing)                    │
└─────────────────────┬───────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                AgentTraceRecorder                                │
│  • record_code_generation()                                      │
│  • record_edit()                                                 │
│  • record_file_write()                                           │
│  • record_from_llm_response() [Auto-extract]                     │
└─────────────────────┬───────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                CodeAttribution Table (PostgreSQL)                │
│  • session_id, agent_id, model, file_path                        │
│  • start_line, end_line, code_hash, prompt                       │
│  • Indexed for fast queries                                      │
└─────────────────────┬───────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                  TraceRepository                                 │
│  Query & Reporting:                                              │
│  • get_by_file(), get_by_agent(), get_by_session()              │
│  • get_file_history(), get_agent_statistics()                   │
│  • generate_compliance_report()                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Usage

### Environment Configuration

```bash
# Enable/disable Agent Trace (default: true)
AGENT_TRACE_ENABLED=true
```

### Basic Usage - Manual Recording

```python
from app.observability import AgentTraceRecorder
from app.db.database import async_session

async def example():
    async with async_session() as db_session:
        # Create trace recorder
        recorder = AgentTraceRecorder(
            session_id="conv-123",
            db_session=db_session,
            user_id="user-456",
        )

        # Record code generation
        await recorder.record_code_generation(
            agent_id="claude-sonnet",
            agent_name="Claude Sonnet 4.5",
            model="claude-sonnet-4-5-20250929",
            file_path="/app/api/new_endpoint.py",
            code_content='''
def hello_world():
    return "Hello, World!"
            ''',
            prompt="Create a simple hello world function",
            start_line=1,
            metadata={"language": "python"},
        )
```

### Automatic Recording - LLM Integration

The easiest way to use Agent Trace is through automatic integration with the LLM client:

```python
from app.llm.ops_center_client import OpsCenterLLMClient
from app.observability import AgentTraceRecorder
from app.db.database import async_session

async def chat_with_tracing():
    async with async_session() as db_session:
        # Create recorder
        recorder = AgentTraceRecorder(
            session_id="conv-123",
            db_session=db_session,
        )

        # Create LLM client
        client = OpsCenterLLMClient()

        # Execute with tracing
        response = await client.execute_tool_loop(
            messages=[
                {"role": "user", "content": "Write a FastAPI endpoint for user login"}
            ],
            tools=[],  # Your tools here
            model="claude-sonnet-4-5-20250929",
            trace_recorder=recorder,  # Enable tracing
            agent_id="claude-sonnet",
            agent_name="Claude Sonnet 4.5",
        )

        # Code is automatically extracted and recorded!
```

### Auto-Extraction from LLM Response

The recorder automatically detects code blocks in markdown format:

```python
# This LLM response:
"""
Here's the login endpoint:

```python
# File: app/api/auth.py
@router.post("/login")
async def login(credentials: LoginCredentials):
    return {"token": "abc123"}
```
"""

# Automatically creates attribution for:
# - File: app/api/auth.py
# - Language: python
# - Lines: 1-4
# - Code hash: computed from content
```

### Querying Attributions

```python
from app.observability import TraceRepository
from app.db.database import async_session

async def query_examples():
    async with async_session() as db_session:
        repo = TraceRepository(db_session)

        # Get all code for a file
        attributions = await repo.get_by_file(
            file_path="/app/api/auth.py",
            limit=100,
        )

        # Get all code by an agent
        agent_code = await repo.get_by_agent(
            agent_id="claude-sonnet",
            limit=100,
        )

        # Get file modification history
        history = await repo.get_file_history(
            file_path="/app/api/auth.py",
        )
        # Returns: {
        #   "file_path": "/app/api/auth.py",
        #   "total_modifications": 5,
        #   "agents_involved": ["Claude Sonnet 4.5", "GPT-4"],
        #   "models_used": ["claude-sonnet-4-5-20250929", "gpt-4o"],
        #   "history": [...]
        # }

        # Get agent statistics
        stats = await repo.get_agent_statistics(
            agent_id="claude-sonnet",
            days=30,
        )
        # Returns: {
        #   "total_contributions": 150,
        #   "files_modified": 45,
        #   "total_lines_modified": 8500,
        #   "models_used": {...},
        #   "change_types": {...}
        # }

        # Generate compliance report
        report = await repo.generate_compliance_report(
            start_date=datetime(2026, 1, 1),
            end_date=datetime(2026, 1, 31),
            format="detailed",  # or "summary"
        )
```

## REST API Endpoints

All endpoints require authentication via API key.

### Get File Attributions

```bash
GET /api/v1/trace/files/{file_path}?limit=100&offset=0

# Example
curl -H "X-API-Key: your-key" \
  http://localhost:8100/api/v1/trace/files/app/api/auth.py

# Response
{
  "filePath": "app/api/auth.py",
  "totalLines": 150,
  "attributionCount": 3,
  "attributions": [...]
}
```

### Get Agent Attributions

```bash
GET /api/v1/trace/agents/{agent_id}?limit=100&offset=0

# Example
curl -H "X-API-Key: your-key" \
  http://localhost:8100/api/v1/trace/agents/claude-sonnet

# Response
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "sessionId": "conv-123",
    "agentId": "claude-sonnet",
    "agentName": "Claude Sonnet 4.5",
    "model": "claude-sonnet-4-5-20250929",
    "filePath": "/app/api/auth.py",
    "startLine": 1,
    "endLine": 20,
    "changeType": "generation",
    "codeHash": "a1b2c3d4e5f6...",
    "prompt": "Create login endpoint",
    "generatedCode": "...",
    "metadata": {},
    "createdAt": "2026-01-31T12:00:00Z"
  }
]
```

### Get Session Attributions

```bash
GET /api/v1/trace/sessions/{session_id}?limit=100&offset=0

# Example
curl -H "X-API-Key: your-key" \
  http://localhost:8100/api/v1/trace/sessions/conv-123
```

### Get Recent Attributions

```bash
GET /api/v1/trace/recent?days=7&limit=100&offset=0

# Get last week's code generations
curl -H "X-API-Key: your-key" \
  http://localhost:8100/api/v1/trace/recent?days=7
```

### Get Statistics

```bash
GET /api/v1/trace/stats

# Example
curl -H "X-API-Key: your-key" \
  http://localhost:8100/api/v1/trace/stats

# Response
{
  "totalLines": 15000,
  "totalAttributions": 250,
  "uniqueAgents": 5,
  "uniqueFiles": 45,
  "byOperation": {
    "generation": 180,
    "edit": 60,
    "deletion": 10
  },
  "topAgents": [...],
  "topFiles": [...]
}
```

### Generate Compliance Report

```bash
POST /api/v1/trace/report

# JSON format
curl -X POST -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{
    "agentId": "claude-sonnet",
    "startDate": "2026-01-01",
    "endDate": "2026-01-31",
    "format": "json"
  }' \
  http://localhost:8100/api/v1/trace/report

# CSV export
curl -X POST -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{
    "startDate": "2026-01-01",
    "endDate": "2026-01-31",
    "format": "csv"
  }' \
  http://localhost:8100/api/v1/trace/report \
  -o report.csv
```

### Health Check

```bash
GET /api/v1/trace/health

curl -H "X-API-Key: your-key" \
  http://localhost:8100/api/v1/trace/health

# Response
{
  "status": "healthy",
  "subsystem": "agent_trace",
  "database": "connected",
  "totalAttributions": 250,
  "uniqueAgents": 5,
  "uniqueFiles": 45,
  "timestamp": "2026-01-31T12:00:00Z"
}
```

## Database Schema

```sql
CREATE TABLE code_attributions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id VARCHAR(255) NOT NULL,
    agent_id VARCHAR(255) REFERENCES agents(id) ON DELETE SET NULL,
    agent_name VARCHAR(255) NOT NULL,
    model VARCHAR(255) NOT NULL,
    file_path VARCHAR(1000) NOT NULL,
    start_line INTEGER NOT NULL,
    end_line INTEGER NOT NULL,
    change_type VARCHAR(50) NOT NULL DEFAULT 'generation',
    code_hash VARCHAR(32) NOT NULL,
    prompt TEXT,
    generated_code TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Indexes for fast queries
    INDEX idx_session_id (session_id),
    INDEX idx_agent_id (agent_id),
    INDEX idx_file_path (file_path),
    INDEX idx_code_hash (code_hash),
    INDEX idx_created_at (created_at)
);
```

## Langfuse Integration

Agent Trace integrates with Langfuse for correlation:

```python
from app.observability import get_tracer, AgentTraceRecorder

# Create both tracers
langfuse_tracer = get_tracer(
    agent_id="claude-sonnet",
    session_id="conv-123",
)
langfuse_tracer.start_trace(
    name="agent_chat",
    input_data={"message": "Create login endpoint"},
)

# Pass Langfuse tracer to Agent Trace
agent_trace_recorder = AgentTraceRecorder(
    session_id="conv-123",
    db_session=db_session,
    langfuse_tracer=langfuse_tracer,  # Enable correlation
)

# Code attributions will appear as spans in Langfuse traces
```

## Use Cases

### 1. Enterprise Audit Trails

Track all AI-generated code for compliance:

```python
# Monthly audit report
report = await repo.generate_compliance_report(
    start_date=datetime(2026, 1, 1),
    end_date=datetime(2026, 1, 31),
    format="detailed",
)
```

### 2. Code Quality Analysis

Identify which agents produce the best code:

```python
for agent_id in ["claude-sonnet", "gpt-4", "gemini-pro"]:
    stats = await repo.get_agent_statistics(agent_id, days=30)
    print(f"{agent_id}: {stats['total_contributions']} contributions")
```

### 3. Debugging AI-Generated Code

Trace a bug back to the original prompt:

```python
# Find who wrote this buggy file
history = await repo.get_file_history("/app/api/buggy_endpoint.py")
print(f"Original author: {history['history'][0]['agent_name']}")
print(f"Original prompt: {history['history'][0]['prompt']}")
```

### 4. Code Ownership Tracking

Understand AI's contribution to your codebase:

```python
stats = await repo.get_agent_statistics("claude-sonnet", days=90)
print(f"Lines modified: {stats['total_lines_modified']}")
print(f"Files touched: {stats['files_modified']}")
```

## Best Practices

### 1. Enable for Production Agents Only

```python
# Only trace production agents, not test/dev
if agent_config.get("environment") == "production":
    recorder = AgentTraceRecorder(session_id=session_id, db_session=db)
else:
    recorder = None  # Disable tracing
```

### 2. Use Meaningful Session IDs

```python
# Good: conversation ID
session_id = f"conv-{conversation.id}"

# Better: include user and timestamp
session_id = f"user-{user_id}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
```

### 3. Include Rich Metadata

```python
await recorder.record_code_generation(
    # ... required fields ...
    metadata={
        "language": "python",
        "framework": "fastapi",
        "tokens_used": 1500,
        "duration_ms": 2000,
        "user_id": user_id,
        "project": "unicorn-brigade",
    }
)
```

### 4. Regular Cleanup

Set up a cron job to archive old attributions:

```sql
-- Archive attributions older than 1 year
DELETE FROM code_attributions
WHERE created_at < NOW() - INTERVAL '1 year';
```

## Troubleshooting

### Code Not Being Traced

1. Check if tracing is enabled:
   ```bash
   echo $AGENT_TRACE_ENABLED  # Should be "true"
   ```

2. Verify recorder is passed to LLM client:
   ```python
   # Must pass trace_recorder, agent_id, and agent_name
   response = await client.execute_tool_loop(
       ...,
       trace_recorder=recorder,
       agent_id="...",
       agent_name="...",
   )
   ```

3. Check database connection:
   ```python
   # Test database is accessible
   async with async_session() as db:
       result = await db.execute("SELECT 1")
   ```

### Auto-Extraction Not Working

The auto-extractor looks for:
- Markdown code blocks: ` ```language\ncode\n``` `
- File path comments: `# File: path/to/file.py`

Ensure your LLM responses include these patterns.

### Performance Issues

If attribution queries are slow:

```sql
-- Check indexes exist
SELECT indexname FROM pg_indexes
WHERE tablename = 'code_attributions';

-- Analyze query performance
EXPLAIN ANALYZE
SELECT * FROM code_attributions
WHERE file_path = '/app/api/auth.py';
```

## Security Considerations

1. **API Key Authentication**: All trace endpoints require authentication
2. **PII in Prompts**: Be careful not to log sensitive user data in prompts
3. **Code Content Storage**: Generated code is stored in database - ensure proper encryption
4. **Access Control**: Restrict access to compliance reports to authorized users only

## Future Enhancements

- [ ] PDF report generation
- [ ] Real-time code attribution UI overlay
- [ ] Git integration (auto-tag commits with agent attribution)
- [ ] Code diff visualization
- [ ] Agent comparison dashboard
- [ ] Export to SBOM (Software Bill of Materials)

## References

- [Agent Trace Spec v1.0](https://agent-trace.dev/)
- [Langfuse Documentation](https://langfuse.com/docs)
- [PostgreSQL Full-Text Search](https://www.postgresql.org/docs/current/textsearch.html)

---

**Status**: Production-ready (January 2026)
**Spec Version**: Agent Trace v1.0
**Maintainer**: Unicorn Brigade Team
