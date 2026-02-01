# Phase 1 & Phase 2 Test Suite

Comprehensive E2E tests for Unicorn Brigade Phase 1 and Phase 2 implementations.

## Test Coverage

### 1. MCP Server Registry Tests (`test_mcp_registry.py`)

**Coverage**: 14 MCP servers (10 baseline + 4 Phase 1)

**Test Classes**:
- `TestMCPServerConfiguration` - Server registration and configuration
  - Total server count (14 servers)
  - Baseline servers (GitHub, Playwright, Slack, PostgreSQL, Filesystem, Memory, HTTP Fetch, Brave Search, Google Drive, Puppeteer)
  - Phase 1 servers (Stripe, Linear, Git, Notion)
  - Server field validation
  - Capability verification

- `TestMCPServerLifecycle` - Server process management
  - Register/unregister custom servers
  - Start/stop server processes
  - Handle already-running servers
  - List running servers

- `TestMCPToolInvocation` - Tool execution
  - STDIO transport tool calls
  - HTTP transport tool calls
  - Error handling for nonexistent servers

- `TestMCPEnvironmentVariables` - Environment configuration
  - Variable substitution
  - Missing variable handling

- `TestMCPServerQueries` - Server discovery
  - Filter by capability
  - Filter by enabled status
  - Transport type validation

**Total Tests**: 25+

---

### 2. New Agent Tests (`test_new_agents.py`)

**Coverage**: 13 production agents from `seed_agents.json`

**Test Classes**:
- `TestAgentCount` - Agent inventory
  - Total count (13 agents)
  - Unique IDs and names

- `TestAgentStructure` - JSON schema validation
  - Required fields (19 fields per agent)
  - Non-empty system prompts and personas
  - Capabilities and tools
  - Temperature and maxTokens validation

- `TestCoreAgents` - Orchestration agents
  - The General (orchestrator)
  - Gunny (agent builder)

- `TestPhase1Agents` - Specialized agents
  - SQL Analyst (text-to-SQL)
  - Support Agent (customer service)
  - Code Reviewer (PR analysis)

- `TestDomainAgents` - Domain specialists
  - Technology (Sgt. Cipher, Cpt. Fullstack, Maj. DevOps)
  - Financial (Col. Finance, Lt. TaxStrat)
  - Legal (Judge Advocate)
  - Medical (Doc MedResearch)
  - Investigation (Detective Holmes)
  - Intelligence (Prof. DataSci)

- `TestAgentTypes` - Type classification
  - Research, Code, Analysis types

- `TestAgentModels` - LLM configuration
  - Model format validation
  - Model diversity

- `TestAgentTools` - Tool assignments
  - Common tools (memory, json)
  - Domain-specific tools (web_search, calculator)

- `TestAgentStatus` - Availability
  - Active status
  - Creation dates

**Total Tests**: 35+

---

### 3. Workflow Execution Tests (`test_workflow_execution.py`)

**Coverage**: 3-tier hierarchical workflows (Orchestrator → Team Leads → Workers)

**Test Classes**:
- `TestWorkflowSchema` - Schema definitions
  - WorkerSpec creation (1B-3B local models)
  - TeamLeadSpec creation (7B-14B local models)
  - WorkflowStep creation
  - Checkpoint creation

- `TestTeamLeadConfiguration` - 8 domain team leads
  - Research, Finance, Content, Sales, DevOps, Legal, Medical, Investigation
  - Worker assignments
  - System prompts

- `TestWorkerConfiguration` - Worker specs
  - Few-shot examples
  - Input/output schemas
  - Small model sizes (1B-3B)

- `TestWorkflowTemplates` - Workflow definitions
  - Investment Due Diligence workflow
  - Step definitions
  - Step dependencies

- `TestWorkflowValidation` - Validation logic
  - Required inputs
  - Final outputs
  - Orchestrator model configuration

- `TestCheckpointHandling` - HITL checkpoints
  - Checkpoint types (HUMAN_APPROVAL, HUMAN_INPUT, REVIEW, GATE)
  - Required field validation

- `TestWorkflowStepTimeout` - Timeout handling
  - Timeout configurations

- `TestWorkflowSerialization` - JSON export
  - Worker to_dict()
  - Team lead to_dict()

- `TestWorkflowCount` - Template inventory
  - Minimum templates
  - Workflow uniqueness

- `TestModelTierUsage` - Model tier validation
  - Workers don't use orchestrator models
  - Team leads use mid-tier models

**Total Tests**: 30+

---

### 4. Integration Tests (`test_integration_phase2.py`)

**Coverage**: End-to-end scenarios with mocked services

**Test Classes**:
- `TestAgentChatIntegration` - Agent tool usage
  - Calculator tool
  - Web search tool
  - Memory storage/retrieval

- `TestMCPServerIntegration` - MCP tool calls
  - GitHub server (create_repository)
  - Filesystem server (read_file)
  - Stripe server (create_payment_intent)

- `TestA2AProtocolIntegration` - Agent-to-Agent
  - Agent discovery (agent cards)
  - Agent invocation

- `TestOrchestrationIntegration` - Event streaming
  - Event emission (agent_started, tool_call, etc.)
  - State tracking

- `TestWorkflowIntegration` - Workflow execution
  - Workflow validation
  - Step execution (mocked)

- `TestMultiAgentCoordination` - Multi-agent scenarios
  - Sequential execution
  - Parallel execution

- `TestErrorHandling` - Error scenarios
  - Tool execution errors
  - MCP server not found
  - Workflow missing inputs

- `TestToolChaining` - Tool combinations
  - Web search → memory store
  - Calculator → JSON format

- `TestPerformanceBasics` - Performance checks
  - Calculator performance (100 calls < 1s)
  - JSON format performance (100 calls < 1s)

**Total Tests**: 25+

---

## Running Tests

### Run All Phase 2 Tests

```bash
./scripts/test_phase2.sh
```

### Run Specific Test Suite

```bash
./scripts/test_phase2.sh mcp          # MCP registry tests only
./scripts/test_phase2.sh agents       # Agent configuration tests only
./scripts/test_phase2.sh workflows    # Workflow execution tests only
./scripts/test_phase2.sh integration  # Integration tests only
./scripts/test_phase2.sh existing     # Existing test suite
```

### Run Individual Test File

```bash
pytest tests/test_mcp_registry.py -v
pytest tests/test_new_agents.py -v
pytest tests/test_workflow_execution.py -v
pytest tests/test_integration_phase2.py -v
```

### Run Specific Test Class

```bash
pytest tests/test_mcp_registry.py::TestMCPServerConfiguration -v
pytest tests/test_new_agents.py::TestPhase1Agents -v
pytest tests/test_workflow_execution.py::TestTeamLeadConfiguration -v
```

### Run Specific Test

```bash
pytest tests/test_mcp_registry.py::TestMCPServerConfiguration::test_total_server_count -v
pytest tests/test_new_agents.py::TestPhase1Agents::test_sql_analyst_exists -v
```

### Run with Coverage

```bash
pytest tests/ --cov=app --cov-report=html
```

---

## Test Structure

### Mocking Strategy

All tests use proper mocking to avoid:
- Real API calls (OpenAI, Anthropic, Serper, etc.)
- External service dependencies (Qdrant, PostgreSQL, etc.)
- Network I/O
- File system modifications

**Common Mock Patterns**:

```python
# Mock LLM client
with patch('app.llm.ops_center_client.OpsCenterLLMClient') as mock_client_class:
    mock_client = AsyncMock()
    mock_client_class.return_value = mock_client
    mock_client.execute_tool_loop.return_value = {...}

# Mock subprocess (MCP servers)
with patch('subprocess.Popen') as mock_popen:
    mock_proc = MagicMock()
    mock_proc.pid = 12345
    mock_popen.return_value = mock_proc

# Mock HTTP requests
with patch('httpx.AsyncClient.post') as mock_post:
    mock_response = Mock()
    mock_response.json.return_value = {...}
    mock_post.return_value = mock_response
```

### Test Fixtures

Defined in `tests/conftest.py`:
- `test_task` - Sample task dictionary
- `test_user_id` - Test user ID
- Environment variables set for testing

---

## Success Criteria

✅ **All tests pass** when run with `pytest tests/`

✅ **No real API calls** - All external services mocked

✅ **50+ test cases** across all test files

✅ **Comprehensive coverage**:
- 14 MCP servers validated
- 13 agents validated
- 3-tier workflow hierarchy validated
- Integration scenarios tested

---

## Test Markers

Tests use pytest markers for categorization:

- `@pytest.mark.asyncio` - Async test (auto-detected)
- `@pytest.mark.integration` - Integration test
- `@pytest.mark.slow` - Slow-running test

### Run Only Integration Tests

```bash
pytest tests/ -m integration -v
```

### Skip Slow Tests

```bash
pytest tests/ -m "not slow" -v
```

---

## Troubleshooting

### Import Errors

Ensure you're running from project root and virtual environment is activated:

```bash
cd /path/to/Unicorn-Brigade
source venv/bin/activate
pytest tests/
```

### Module Not Found

Install test dependencies:

```bash
pip install -r requirements.txt
pip install pytest pytest-asyncio pytest-cov
```

### Async Warnings

The project uses `pytest-asyncio` with `asyncio_mode = auto` in `pytest.ini`. No need to manually mark async tests.

---

## Contributing Tests

When adding new features, add corresponding tests:

1. **New MCP Server**: Add tests to `test_mcp_registry.py`
2. **New Agent**: Update `test_new_agents.py` with validation
3. **New Workflow**: Add template tests to `test_workflow_execution.py`
4. **New Integration**: Add scenario to `test_integration_phase2.py`

Follow existing patterns:
- Use mocking for external dependencies
- Write descriptive test names
- Add docstrings explaining what's tested
- Group related tests in classes

---

## Test Summary

| Test File | Test Classes | Tests | Coverage |
|-----------|--------------|-------|----------|
| `test_mcp_registry.py` | 5 | 25+ | MCP servers, lifecycle, tool calls |
| `test_new_agents.py` | 9 | 35+ | Agent configurations, Phase 1 agents |
| `test_workflow_execution.py` | 10 | 30+ | 3-tier hierarchy, team leads, workers |
| `test_integration_phase2.py` | 9 | 25+ | E2E scenarios, multi-agent coordination |
| **Total** | **33** | **115+** | **Phase 1 & 2 features** |

---

**Last Updated**: January 31, 2026
**Test Suite Version**: 1.0.0
**Compatible with**: Unicorn Brigade v2.0.0+
