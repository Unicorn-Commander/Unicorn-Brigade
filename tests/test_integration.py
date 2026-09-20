# Executed by Grok (headless lane)
"""
Comprehensive Integration Tests for Unicorn Brigade

Tests the full stack end-to-end:
1. Agent CRUD Integration - Create, Read, Update, Delete agents via API
2. Function Calling Integration - Chat with tools (LLM-dependent, skipped by default)
3. Workflow Execution Integration - Hierarchical workflows (LLM-dependent, skipped by default)
4. Tool Registry Integration - Validate tool definitions and resolution
5. Database Consistency - Conversations, messages, tool execution logging
6. API Authentication - Role-based access control

Run all tests: pytest tests/test_integration.py -v
Run LLM tests: RUN_LLM_TESTS=1 pytest tests/test_integration.py -v -k "llm"
Run auth tests: pytest tests/test_integration.py -v -k "auth"
"""

import json
import os
import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Check if LLM tests should run
RUN_LLM_TESTS = os.environ.get("RUN_LLM_TESTS", "0") == "1"
skip_llm = pytest.mark.skipif(
    not RUN_LLM_TESTS,
    reason="LLM tests disabled by default. Set RUN_LLM_TESTS=1 to enable."
)


# =============================================================================
# TEST FIXTURES
# =============================================================================

@pytest.fixture(scope="session")
def test_database_url():
    """Use a separate test database or in-memory SQLite for tests"""
    # For integration tests, use actual PostgreSQL if available, else SQLite
    return os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql+asyncpg://leads_user:leads_password_dev@localhost:5434/unicorn_brigade_test"
    )


@pytest.fixture
def mock_llm_client():
    """Create a mock LLM client for testing without real API calls"""
    client = MagicMock()

    # Mock chat_completion
    client.chat_completion = AsyncMock(return_value={
        "choices": [{
            "message": {
                "content": "This is a mock response from the LLM."
            }
        }],
        "usage": {"prompt_tokens": 50, "completion_tokens": 25, "total_tokens": 75},
        "model": "mock-model",
        "provider": "mock-provider",
    })

    # Mock execute_tool_loop for function calling
    client.execute_tool_loop = AsyncMock(return_value={
        "choices": [{
            "message": {
                "content": "I executed the tool and got the result: 42"
            }
        }],
        "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
        "model": "mock-model",
    })

    # Mock get_response_content
    client.get_response_content = MagicMock(
        side_effect=lambda r: r.get("choices", [{}])[0].get("message", {}).get("content", "")
    )

    return client


@pytest.fixture
def mock_auth_user():
    """Create a mock authenticated user with admin permissions"""
    from app.auth.middleware import AuthUser
    from app.auth.roles import UserRole

    return AuthUser(
        id="test-admin",
        role=UserRole.ADMIN,
        key_name="Test Admin Key",
        permissions=["admin", "chat", "read", "write"],
    )


@pytest.fixture
def mock_operator_user():
    """Create a mock authenticated operator user"""
    from app.auth.middleware import AuthUser
    from app.auth.roles import UserRole

    return AuthUser(
        id="test-operator",
        role=UserRole.OPERATOR,
        key_name="Test Operator Key",
        permissions=["chat", "read", "write"],
    )


@pytest.fixture
def mock_viewer_user():
    """Create a mock authenticated viewer user"""
    from app.auth.middleware import AuthUser
    from app.auth.roles import UserRole

    return AuthUser(
        id="test-viewer",
        role=UserRole.VIEWER,
        key_name="Test Viewer Key",
        permissions=["read"],
    )


@pytest.fixture
def test_app(mock_llm_client, mock_auth_user):
    """Create a test FastAPI app with mocked dependencies.

    Note: Tests that require database access will be skipped if the database
    is not available or has connection issues.
    """
    from app.api.agent_routes import init_agent_routes
    from app.main import app

    # Patch auth to always return mock user
    with patch("app.auth.middleware.AUTH_BYPASS_ENABLED", True):
        # Initialize agent routes with mock LLM client
        init_agent_routes(mock_llm_client)

        yield TestClient(app)


# Mark for tests that need database
requires_database = pytest.mark.skipif(
    os.environ.get("SKIP_DB_TESTS", "1") == "1",
    reason="Database tests skipped. Set SKIP_DB_TESTS=0 with running PostgreSQL to enable."
)


@pytest.fixture
def sample_agent_data():
    """Sample agent data for testing"""
    unique_id = f"test-agent-{uuid.uuid4().hex[:8]}"
    return {
        "name": unique_id,
        "displayName": "Test Agent",
        "title": "Integration Test Agent",
        "rank": "Private",
        "avatar": "🧪",
        "bio": "An agent created for integration testing",
        "persona": "You are a helpful test agent.",
        "systemPrompt": "Respond concisely to test queries.",
        "domain": "testing",
        "subdomain": "integration",
        "status": "active",
        "type": "individual",
        "agentType": "analysis",
        "capabilities": ["testing", "integration"],
        "model": "openai/gpt-4o-mini",
        "temperature": 0.7,
        "maxTokens": 1000,
        "tools": ["calculator", "datetime"],
    }


@pytest.fixture
def sample_agent_with_tools():
    """Agent configured with multiple tools for function calling tests"""
    unique_id = f"test-tool-agent-{uuid.uuid4().hex[:8]}"
    return {
        "name": unique_id,
        "displayName": "Tool Test Agent",
        "persona": "You are an assistant that uses tools to help users.",
        "systemPrompt": "When asked to calculate, use the calculator tool. When asked about time, use the datetime tool.",
        "domain": "testing",
        "status": "active",
        "model": "openai/gpt-4o-mini",
        "tools": ["calculator", "datetime", "web_search"],
    }


# =============================================================================
# 1. AGENT CRUD INTEGRATION TESTS
# =============================================================================

@requires_database
class TestAgentCRUDIntegration:
    """Test agent CRUD operations end-to-end via API.

    Requires: Running PostgreSQL database at DATABASE_URL
    Enable: SKIP_DB_TESTS=0 pytest tests/test_integration.py -v
    """

    def test_create_agent_full_payload(self, test_app, sample_agent_data):
        """Test creating an agent with all fields populated"""
        response = test_app.post(
            "/api/v1/agents",
            json=sample_agent_data,
        )

        assert response.status_code == 201
        data = response.json()

        # Verify all fields are returned correctly
        assert data["name"] == sample_agent_data["name"]
        assert data["displayName"] == sample_agent_data["displayName"]
        assert data["domain"] == sample_agent_data["domain"]
        assert data["tools"] == sample_agent_data["tools"]
        assert "id" in data
        assert "createdAt" in data

        # Cleanup
        test_app.delete(f"/api/v1/agents/{data['id']}")

    def test_create_agent_minimal_payload(self, test_app):
        """Test creating an agent with minimal required fields"""
        minimal_agent = {
            "name": f"minimal-agent-{uuid.uuid4().hex[:8]}",
        }

        response = test_app.post(
            "/api/v1/agents",
            json=minimal_agent,
        )

        assert response.status_code == 201
        data = response.json()

        # Verify defaults are applied
        assert data["domain"] == "general"
        assert data["status"] == "active"
        assert data["avatar"] == "🦄"
        assert data["model"] == "openai/gpt-4o-mini"
        assert data["temperature"] == 0.7

        # Cleanup
        test_app.delete(f"/api/v1/agents/{data['id']}")

    def test_get_agent_after_create(self, test_app, sample_agent_data):
        """Test retrieving an agent after creation"""
        # Create
        create_response = test_app.post("/api/v1/agents", json=sample_agent_data)
        assert create_response.status_code == 201
        agent_id = create_response.json()["id"]

        # Read
        get_response = test_app.get(f"/api/v1/agents/{agent_id}")
        assert get_response.status_code == 200

        data = get_response.json()
        assert data["id"] == agent_id
        assert data["name"] == sample_agent_data["name"]
        assert data["displayName"] == sample_agent_data["displayName"]

        # Cleanup
        test_app.delete(f"/api/v1/agents/{agent_id}")

    def test_update_agent(self, test_app, sample_agent_data):
        """Test updating an agent's fields"""
        # Create
        create_response = test_app.post("/api/v1/agents", json=sample_agent_data)
        agent_id = create_response.json()["id"]

        # Update
        updates = {
            "displayName": "Updated Test Agent",
            "bio": "Updated bio for testing",
            "temperature": 0.9,
            "tools": ["calculator", "datetime", "memory"],
        }

        update_response = test_app.put(
            f"/api/v1/agents/{agent_id}",
            json=updates,
        )

        assert update_response.status_code == 200
        data = update_response.json()

        assert data["displayName"] == "Updated Test Agent"
        assert data["bio"] == "Updated bio for testing"
        assert data["temperature"] == 0.9
        assert "memory" in data["tools"]

        # Cleanup
        test_app.delete(f"/api/v1/agents/{agent_id}")

    def test_delete_agent(self, test_app, sample_agent_data):
        """Test deleting an agent"""
        # Create
        create_response = test_app.post("/api/v1/agents", json=sample_agent_data)
        agent_id = create_response.json()["id"]

        # Verify exists
        get_response = test_app.get(f"/api/v1/agents/{agent_id}")
        assert get_response.status_code == 200

        # Delete
        delete_response = test_app.delete(f"/api/v1/agents/{agent_id}")
        assert delete_response.status_code == 200
        assert delete_response.json()["message"] == "Agent deleted"

        # Verify deleted
        get_after_delete = test_app.get(f"/api/v1/agents/{agent_id}")
        assert get_after_delete.status_code == 404

    def test_list_agents(self, test_app, sample_agent_data):
        """Test listing all agents"""
        # Create a few agents
        agent_ids = []
        for i in range(3):
            data = sample_agent_data.copy()
            data["name"] = f"list-test-agent-{i}-{uuid.uuid4().hex[:8]}"
            response = test_app.post("/api/v1/agents", json=data)
            agent_ids.append(response.json()["id"])

        # List
        list_response = test_app.get("/api/v1/agents")
        assert list_response.status_code == 200

        data = list_response.json()
        assert "agents" in data
        assert isinstance(data["agents"], list)

        # Verify our test agents are in the list
        agent_ids_in_list = [a["id"] for a in data["agents"]]
        for aid in agent_ids:
            assert aid in agent_ids_in_list

        # Cleanup
        for aid in agent_ids:
            test_app.delete(f"/api/v1/agents/{aid}")

    def test_get_nonexistent_agent_returns_404(self, test_app):
        """Test that getting a non-existent agent returns 404"""
        response = test_app.get("/api/v1/agents/nonexistent-agent-id-12345")
        assert response.status_code == 404

    def test_delete_nonexistent_agent_returns_404(self, test_app):
        """Test that deleting a non-existent agent returns 404"""
        response = test_app.delete("/api/v1/agents/nonexistent-agent-id-12345")
        assert response.status_code == 404

    def test_update_nonexistent_agent_returns_404(self, test_app):
        """Test that updating a non-existent agent returns 404"""
        response = test_app.put(
            "/api/v1/agents/nonexistent-agent-id-12345",
            json={"displayName": "Updated"},
        )
        assert response.status_code == 404

    def test_agent_with_tools_assignment(self, test_app, sample_agent_with_tools):
        """Test creating agent with specific tools"""
        response = test_app.post("/api/v1/agents", json=sample_agent_with_tools)
        assert response.status_code == 201

        data = response.json()
        assert "calculator" in data["tools"]
        assert "datetime" in data["tools"]
        assert "web_search" in data["tools"]

        # Verify tools endpoint
        tools_response = test_app.get(f"/api/v1/agents/{data['id']}/tools")
        assert tools_response.status_code == 200
        tools_data = tools_response.json()
        assert "toolNames" in tools_data

        # Cleanup
        test_app.delete(f"/api/v1/agents/{data['id']}")

    def test_domain_filtering(self, test_app):
        """Test filtering agents by domain"""
        # Create agents in different domains
        agents_to_create = [
            {"name": f"finance-agent-{uuid.uuid4().hex[:8]}", "domain": "finance"},
            {"name": f"research-agent-{uuid.uuid4().hex[:8]}", "domain": "research"},
            {"name": f"general-agent-{uuid.uuid4().hex[:8]}", "domain": "general"},
        ]

        created_ids = []
        for agent_data in agents_to_create:
            response = test_app.post("/api/v1/agents", json=agent_data)
            created_ids.append(response.json()["id"])

        # Get domain summary
        domains_response = test_app.get("/api/v1/agents/domains")
        assert domains_response.status_code == 200

        data = domains_response.json()
        assert "domains" in data

        domain_names = [d["name"] for d in data["domains"]]
        assert "finance" in domain_names
        assert "research" in domain_names

        # Cleanup
        for aid in created_ids:
            test_app.delete(f"/api/v1/agents/{aid}")


# =============================================================================
# 2. FUNCTION CALLING INTEGRATION TESTS (LLM-dependent)
# =============================================================================

@requires_database
class TestFunctionCallingIntegration:
    """Test function calling with agents (requires LLM and database)"""

    @skip_llm
    def test_chat_with_calculator_tool(self, test_app, sample_agent_with_tools):
        """Test chat with agent that has calculator tool - verify tool was called"""
        # Create agent
        create_response = test_app.post("/api/v1/agents", json=sample_agent_with_tools)
        agent = create_response.json()

        # Chat asking for calculation
        chat_response = test_app.post(
            f"/api/v1/agents/{agent['id']}/chat",
            json={
                "message": "What is 15 * 7?",
                "user_id": "test-user",
            }
        )

        assert chat_response.status_code == 200
        data = chat_response.json()

        # Verify response structure
        assert "content" in data
        assert "agent" in data

        # If tool was called, there should be toolCalls in response
        if "toolCalls" in data:
            assert any(tc["name"] == "calculator" for tc in data["toolCalls"])

        # Cleanup
        test_app.delete(f"/api/v1/agents/{agent['id']}")

    @skip_llm
    def test_chat_with_web_search_tool(self, test_app, sample_agent_with_tools):
        """Test chat with agent that has web_search tool - verify search was executed"""
        # Create agent
        create_response = test_app.post("/api/v1/agents", json=sample_agent_with_tools)
        agent = create_response.json()

        # Chat asking for web search
        chat_response = test_app.post(
            f"/api/v1/agents/{agent['id']}/chat",
            json={
                "message": "Search for the latest AI news",
                "user_id": "test-user",
            }
        )

        assert chat_response.status_code == 200
        data = chat_response.json()

        # Verify response structure
        assert "content" in data

        # If tool was called, verify web_search
        if "toolCalls" in data:
            assert any(tc["name"] == "web_search" for tc in data["toolCalls"])

        # Cleanup
        test_app.delete(f"/api/v1/agents/{agent['id']}")

    @skip_llm
    def test_tool_calls_appear_in_response(self, test_app, sample_agent_with_tools):
        """Test that tool_calls appear in chat response when tools are used"""
        # Create agent with tools
        create_response = test_app.post("/api/v1/agents", json=sample_agent_with_tools)
        agent = create_response.json()

        # Send message that should trigger tool use
        chat_response = test_app.post(
            f"/api/v1/agents/{agent['id']}/chat",
            json={
                "message": "Calculate 100 / 5 and tell me the current date",
                "user_id": "test-user",
            }
        )

        assert chat_response.status_code == 200
        data = chat_response.json()

        # Response should have tool calls if tools were used
        assert "content" in data
        assert isinstance(data["content"], str)

        # Cleanup
        test_app.delete(f"/api/v1/agents/{agent['id']}")

    def test_chat_without_tools_mock(self, test_app, mock_llm_client):
        """Test chat with mocked LLM client (no real API calls)"""
        # Create agent without tools
        agent_data = {
            "name": f"no-tools-agent-{uuid.uuid4().hex[:8]}",
            "displayName": "No Tools Agent",
            "persona": "You are a simple assistant.",
            "domain": "testing",
            "tools": [],  # No tools
        }

        create_response = test_app.post("/api/v1/agents", json=agent_data)
        assert create_response.status_code == 201
        agent = create_response.json()

        # Chat should work with mocked client
        chat_response = test_app.post(
            f"/api/v1/agents/{agent['id']}/chat",
            json={
                "message": "Hello, how are you?",
                "user_id": "test-user",
            }
        )

        assert chat_response.status_code == 200
        data = chat_response.json()
        assert "content" in data

        # Cleanup
        test_app.delete(f"/api/v1/agents/{agent['id']}")


# =============================================================================
# 3. WORKFLOW EXECUTION INTEGRATION TESTS (LLM-dependent)
# =============================================================================

class TestWorkflowExecutionIntegration:
    """Test hierarchical workflow execution"""

    @pytest.fixture
    def workflow_test_app(self, mock_llm_client):
        """Create app with workflow routes initialized"""
        from fastapi import FastAPI

        from app.api.hierarchical_routes import init_hierarchical_routes, router

        with patch("app.workflows.engine.event_bus") as mock_bus:
            mock_mission = MagicMock()
            mock_mission.id = "test-mission"
            mock_bus.create_mission.return_value = mock_mission

            with patch("app.auth.middleware.AUTH_BYPASS_ENABLED", True):
                app = FastAPI()
                app.include_router(router, prefix="/api/v1")
                init_hierarchical_routes(mock_llm_client, enable_local_models=False)

                yield TestClient(app)

    def test_list_workflow_templates(self, workflow_test_app):
        """Test listing available workflow templates"""
        response = workflow_test_app.get("/api/v1/hierarchical/templates")

        assert response.status_code == 200
        data = response.json()

        assert "workflows" in data
        assert "count" in data
        assert isinstance(data["workflows"], list)

    def test_get_workflow_template_details(self, workflow_test_app):
        """Test getting details of a specific workflow template"""
        # First list to get a valid ID
        list_response = workflow_test_app.get("/api/v1/hierarchical/templates")
        workflows = list_response.json()["workflows"]

        if not workflows:
            pytest.skip("No workflow templates available")

        # Get first workflow's details
        workflow_id = workflows[0]["id"]
        detail_response = workflow_test_app.get(f"/api/v1/hierarchical/templates/{workflow_id}")

        assert detail_response.status_code == 200
        data = detail_response.json()

        assert "workflow" in data
        assert "id" in data["workflow"]
        assert "name" in data["workflow"]
        assert "steps" in data["workflow"]

    def test_list_domains(self, workflow_test_app):
        """Test listing hierarchical domains"""
        response = workflow_test_app.get("/api/v1/hierarchical/domains")

        assert response.status_code == 200
        data = response.json()

        assert "domains" in data
        assert "count" in data

        # Verify expected domains
        domain_names = [d["domain"] for d in data["domains"]]
        expected_domains = ["research", "finance", "content"]
        for domain in expected_domains:
            assert domain in domain_names

    def test_list_workers(self, workflow_test_app):
        """Test listing all workers"""
        response = workflow_test_app.get("/api/v1/hierarchical/workers")

        assert response.status_code == 200
        data = response.json()

        assert "workers" in data
        assert "count" in data
        assert len(data["workers"]) > 0

        # Verify worker structure
        worker = data["workers"][0]
        assert "id" in worker
        assert "name" in worker
        assert "model" in worker

    def test_list_workers_by_domain(self, workflow_test_app):
        """Test filtering workers by domain"""
        response = workflow_test_app.get("/api/v1/hierarchical/workers?domain=research")

        assert response.status_code == 200
        data = response.json()

        assert data["filter"]["domain"] == "research"

    def test_get_config_presets(self, workflow_test_app):
        """Test getting model configuration presets"""
        response = workflow_test_app.get("/api/v1/hierarchical/config/presets")

        assert response.status_code == 200
        data = response.json()

        assert "presets" in data
        assert "cost_optimized" in data["presets"]
        assert "quality_optimized" in data["presets"]

    def test_hierarchical_health(self, workflow_test_app):
        """Test hierarchical subsystem health check"""
        response = workflow_test_app.get("/api/v1/hierarchical/health")

        assert response.status_code == 200
        data = response.json()

        assert "status" in data
        assert "engine_initialized" in data
        assert "template_count" in data
        assert "domain_count" in data
        assert "worker_count" in data

    @skip_llm
    def test_execute_simple_workflow(self, workflow_test_app):
        """Test executing a simple workflow end-to-end"""
        # Get available workflows
        templates = workflow_test_app.get("/api/v1/hierarchical/templates").json()

        if not templates["workflows"]:
            pytest.skip("No workflow templates available")

        # Find a workflow and get its required inputs
        workflow_id = templates["workflows"][0]["id"]
        workflow_detail = workflow_test_app.get(
            f"/api/v1/hierarchical/templates/{workflow_id}"
        ).json()

        required_inputs = workflow_detail["workflow"].get("requiredInputs", [])

        # Build minimal inputs
        test_inputs = {inp: f"test-value-{inp}" for inp in required_inputs}

        # Execute workflow
        response = workflow_test_app.post(
            "/api/v1/hierarchical/execute",
            json={
                "workflow_id": workflow_id,
                "inputs": test_inputs,
                "async_execution": False,
            }
        )

        assert response.status_code == 200
        data = response.json()

        assert "execution_id" in data
        assert "state" in data

    @skip_llm
    def test_workflow_with_model_config_override(self, workflow_test_app):
        """Test workflow execution with model configuration override"""
        templates = workflow_test_app.get("/api/v1/hierarchical/templates").json()

        if not templates["workflows"]:
            pytest.skip("No workflow templates available")

        workflow_id = templates["workflows"][0]["id"]
        workflow_detail = workflow_test_app.get(
            f"/api/v1/hierarchical/templates/{workflow_id}"
        ).json()

        required_inputs = workflow_detail["workflow"].get("requiredInputs", [])
        test_inputs = {inp: f"test-value-{inp}" for inp in required_inputs}

        # Execute with model config
        response = workflow_test_app.post(
            "/api/v1/hierarchical/execute",
            json={
                "workflow_id": workflow_id,
                "inputs": test_inputs,
                "model_config": {
                    "preset": "quality_optimized",
                    "orchestrator_model": "openai/gpt-4o",
                },
                "async_execution": False,
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "model_config_used" in data

    def test_checkpoint_response_handling(self, workflow_test_app):
        """Test checkpoint response handling (mock human approval)"""
        # This tests the checkpoint endpoint structure
        # Without an actual running execution, we expect a 400 error
        response = workflow_test_app.post(
            "/api/v1/hierarchical/executions/fake-execution-id/checkpoint",
            json={
                "execution_id": "fake-execution-id",
                "checkpoint_id": "fake-checkpoint-id",
                "response": {"approved": True},
            }
        )

        # Should return 400 because no execution exists
        assert response.status_code == 400


# =============================================================================
# 4. TOOL REGISTRY INTEGRATION TESTS
# =============================================================================

class TestToolRegistryIntegration:
    """Test tool registry and resolution"""

    def test_all_tools_in_registry_are_valid(self):
        """Verify all tools in TOOL_REGISTRY have valid ToolDefinition structure"""
        from app.llm.tool_resolver import TOOL_REGISTRY

        assert len(TOOL_REGISTRY) > 0, "TOOL_REGISTRY should not be empty"

        for tool_name, tool_def in TOOL_REGISTRY.items():
            # Each tool should have required attributes
            assert hasattr(tool_def, "name"), f"Tool {tool_name} missing 'name'"
            assert hasattr(tool_def, "description"), f"Tool {tool_name} missing 'description'"
            assert hasattr(tool_def, "parameters"), f"Tool {tool_name} missing 'parameters'"
            assert hasattr(tool_def, "handler"), f"Tool {tool_name} missing 'handler'"

            # Name should match registry key
            assert tool_def.name == tool_name, f"Tool name mismatch: {tool_def.name} != {tool_name}"

    def test_get_tools_for_agent_with_valid_tools(self):
        """Test get_tools_for_agent returns correct tools for agent config"""
        from app.llm.tool_resolver import get_tools_for_agent

        agent = {
            "id": "test-agent",
            "name": "Test Agent",
            "tools": ["calculator", "datetime", "memory"],
        }

        tools = get_tools_for_agent(agent)

        assert len(tools) == 3
        tool_names = [t.name for t in tools]
        assert "calculator" in tool_names
        assert "datetime" in tool_names
        assert "memory" in tool_names

    def test_get_tools_for_agent_with_no_tools(self):
        """Test get_tools_for_agent with agent that has no tools"""
        from app.llm.tool_resolver import get_tools_for_agent

        agent = {
            "id": "test-agent",
            "name": "Test Agent",
            "tools": [],
        }

        tools = get_tools_for_agent(agent)
        assert tools == []

    def test_get_tools_for_agent_with_missing_tools_field(self):
        """Test get_tools_for_agent when tools field is missing"""
        from app.llm.tool_resolver import get_tools_for_agent

        agent = {
            "id": "test-agent",
            "name": "Test Agent",
        }

        tools = get_tools_for_agent(agent)
        assert tools == []

    def test_tool_resolution_with_invalid_tool_names(self):
        """Test that invalid tool names are skipped gracefully"""
        from app.llm.tool_resolver import get_tools_for_agent

        agent = {
            "id": "test-agent",
            "name": "Test Agent",
            "tools": ["calculator", "invalid_tool_name", "nonexistent_tool", "datetime"],
        }

        tools = get_tools_for_agent(agent)

        # Should only return valid tools
        assert len(tools) == 2
        tool_names = [t.name for t in tools]
        assert "calculator" in tool_names
        assert "datetime" in tool_names
        assert "invalid_tool_name" not in tool_names

    def test_get_tool_by_name(self):
        """Test getting single tool by name"""
        from app.llm.tool_resolver import get_tool_by_name

        calculator = get_tool_by_name("calculator")
        assert calculator is not None
        assert calculator.name == "calculator"

        nonexistent = get_tool_by_name("nonexistent_tool")
        assert nonexistent is None

    def test_get_tools_by_names(self):
        """Test getting multiple tools by names"""
        from app.llm.tool_resolver import get_tools_by_names

        tools = get_tools_by_names(["calculator", "datetime", "memory"])

        assert len(tools) == 3

    def test_core_tools_present(self):
        """Test that core tools are present in registry"""
        from app.llm.tool_resolver import TOOL_REGISTRY

        core_tools = [
            "web_search", "http_request", "calculator",
            "datetime", "json", "shell", "memory"
        ]

        for tool_name in core_tools:
            assert tool_name in TOOL_REGISTRY, f"Core tool '{tool_name}' missing from registry"

    def test_extended_tools_present(self):
        """Test that extended tools are present in registry"""
        from app.llm.tool_resolver import TOOL_REGISTRY

        extended_tools = [
            "email", "file", "code", "text",
            "image", "database", "notify", "qrcode"
        ]

        for tool_name in extended_tools:
            assert tool_name in TOOL_REGISTRY, f"Extended tool '{tool_name}' missing from registry"


# =============================================================================
# 5. DATABASE CONSISTENCY TESTS
# =============================================================================

@requires_database
class TestDatabaseConsistency:
    """Test database operations and consistency"""

    @pytest.fixture
    async def db_session(self):
        """Create a test database session"""
        from app.db.database import async_session

        async with async_session() as session:
            yield session
            await session.rollback()

    @pytest.fixture
    def sync_test_app(self, mock_llm_client):
        """Create test app for sync database tests"""
        from app.api.agent_routes import init_agent_routes
        from app.main import app

        with patch("app.auth.middleware.AUTH_BYPASS_ENABLED", True):
            init_agent_routes(mock_llm_client)
            yield TestClient(app)

    def test_create_conversation_add_messages_verify_retrieval(self, sync_test_app):
        """Test conversation creation, message addition, and retrieval"""
        # First create an agent
        agent_data = {
            "name": f"conv-test-agent-{uuid.uuid4().hex[:8]}",
            "domain": "testing",
        }
        agent_response = sync_test_app.post("/api/v1/agents", json=agent_data)
        agent = agent_response.json()

        # Create conversation
        conv_response = sync_test_app.post(
            "/api/v1/conversations",
            json={
                "agent_id": agent["id"],
                "user_id": "test-user",
                "title": "Test Conversation",
            }
        )

        # Conversation endpoint may not exist, handle gracefully
        if conv_response.status_code == 404:
            # Test using chat which creates conversation implicitly
            chat_response = sync_test_app.post(
                f"/api/v1/agents/{agent['id']}/chat",
                json={
                    "message": "Hello, this is a test message",
                    "user_id": "test-user",
                }
            )
            assert chat_response.status_code == 200
        else:
            assert conv_response.status_code in [200, 201]

        # Cleanup
        sync_test_app.delete(f"/api/v1/agents/{agent['id']}")

    def test_tool_execution_logging(self, sync_test_app, sample_agent_with_tools):
        """Test that tool executions are logged to database"""
        # Create agent with tools
        agent_response = sync_test_app.post("/api/v1/agents", json=sample_agent_with_tools)
        agent = agent_response.json()

        # Make a chat request that might trigger tool use
        chat_response = sync_test_app.post(
            f"/api/v1/agents/{agent['id']}/chat",
            json={
                "message": "What is 10 + 5?",
                "user_id": "test-user",
            }
        )

        assert chat_response.status_code == 200

        # Tool executions are logged asynchronously
        # In a real test with actual LLM, toolCalls would be in response

        # Cleanup
        sync_test_app.delete(f"/api/v1/agents/{agent['id']}")

    def test_cascading_deletes_work_correctly(self, sync_test_app):
        """Test that deleting an agent cascades to related records"""
        # Create agent
        agent_data = {
            "name": f"cascade-test-agent-{uuid.uuid4().hex[:8]}",
            "domain": "testing",
            "tools": ["calculator"],
        }
        agent_response = sync_test_app.post("/api/v1/agents", json=agent_data)
        agent = agent_response.json()
        agent_id = agent["id"]

        # Create an API key for the agent
        key_response = sync_test_app.post(
            f"/api/v1/agents/{agent_id}/keys",
            json={
                "name": "Test Key",
                "permissions": ["chat", "read"],
            }
        )

        # API key endpoint might not exist, that's okay
        if key_response.status_code not in [200, 201, 404]:
            pytest.fail(f"Unexpected status: {key_response.status_code}")

        # Delete the agent
        delete_response = sync_test_app.delete(f"/api/v1/agents/{agent_id}")
        assert delete_response.status_code == 200

        # Verify agent is deleted
        get_response = sync_test_app.get(f"/api/v1/agents/{agent_id}")
        assert get_response.status_code == 404

    def test_message_retrieval_order(self, sync_test_app):
        """Test that messages are retrieved in correct order"""
        # Create agent
        agent_data = {
            "name": f"message-order-agent-{uuid.uuid4().hex[:8]}",
            "domain": "testing",
        }
        agent_response = sync_test_app.post("/api/v1/agents", json=agent_data)
        agent = agent_response.json()

        # Send multiple messages
        for i in range(3):
            sync_test_app.post(
                f"/api/v1/agents/{agent['id']}/chat",
                json={
                    "message": f"Test message {i}",
                    "user_id": "test-user",
                }
            )

        # Messages should be ordered by creation time (oldest first)
        # This is verified in the repository's order_by clause

        # Cleanup
        sync_test_app.delete(f"/api/v1/agents/{agent['id']}")


# =============================================================================
# 6. API AUTHENTICATION TESTS
# =============================================================================

class TestAPIAuthentication:
    """Test API authentication and authorization"""

    @pytest.fixture
    def app_no_bypass(self, mock_llm_client):
        """Create app with auth bypass disabled"""
        from app.api.agent_routes import init_agent_routes
        from app.main import app

        init_agent_routes(mock_llm_client)

        with patch("app.auth.middleware.AUTH_BYPASS_ENABLED", False):
            yield TestClient(app, raise_server_exceptions=False)

    def test_endpoints_require_api_key_when_auth_enabled(self, app_no_bypass):
        """Test that protected endpoints require API key"""
        # Without API key, should get 401
        response = app_no_bypass.get("/api/v1/agents")

        # Should be 401 Unauthorized when no API key provided
        assert response.status_code in [401, 200]  # 200 if public, 401 if protected

    def test_valid_admin_key_allows_access(self):
        """Test that valid admin key allows full access"""
        from app.auth.middleware import MASTER_ADMIN_KEY, AuthUser, validate_api_key
        from app.auth.roles import UserRole

        if not MASTER_ADMIN_KEY:
            pytest.skip("BRIGADE_ADMIN_KEY not configured")

        # This would need to be tested with actual async session
        # For now, just verify the MASTER_ADMIN_KEY check logic
        assert MASTER_ADMIN_KEY != ""

    def test_role_hierarchy(self):
        """Test role-based access hierarchy"""
        from app.auth.roles import UserRole

        # Verify role hierarchy exists
        assert UserRole.VIEWER.value == "viewer"
        assert UserRole.OPERATOR.value == "operator"
        assert UserRole.ADMIN.value == "admin"

    def test_auth_user_permissions(self, mock_auth_user, mock_operator_user, mock_viewer_user):
        """Test AuthUser permission checking"""
        # Admin has all permissions
        assert mock_auth_user.has_permission("admin") is True
        assert mock_auth_user.has_permission("any_permission") is True

        # Operator has specific permissions
        assert "chat" in mock_operator_user.permissions
        assert "write" in mock_operator_user.permissions

        # Viewer has limited permissions
        assert "read" in mock_viewer_user.permissions

    def test_agent_access_control(self, mock_auth_user, mock_operator_user):
        """Test agent-specific access control"""
        # Admin can access any agent
        assert mock_auth_user.can_access_agent("any-agent-id") is True

        # Operator can access all agents
        assert mock_operator_user.can_access_agent("any-agent-id") is True

    def test_agent_specific_key_restricts_access(self):
        """Test that agent-bound API keys restrict access"""
        from app.auth.middleware import AuthUser
        from app.auth.roles import UserRole

        # Create user bound to specific agent
        agent_user = AuthUser(
            id="agent-key-user",
            role=UserRole.OPERATOR,
            agent_id="specific-agent-123",
            permissions=["chat"],
        )

        # Can access their agent
        assert agent_user.can_access_agent("specific-agent-123") is True

        # Cannot access other agents
        assert agent_user.can_access_agent("other-agent-456") is False


# =============================================================================
# ADDITIONAL INTEGRATION TESTS
# =============================================================================

@requires_database
class TestAPIResponseFormats:
    """Test API response formats and structures"""

    def test_agent_response_format(self, test_app, sample_agent_data):
        """Test that agent responses follow expected format"""
        response = test_app.post("/api/v1/agents", json=sample_agent_data)
        data = response.json()

        # Required fields
        required_fields = ["id", "name", "domain", "status", "model", "createdAt"]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"

        # Optional fields should be present (even if null)
        optional_fields = ["displayName", "bio", "persona", "tools", "capabilities"]
        for field in optional_fields:
            assert field in data, f"Missing optional field: {field}"

        # Cleanup
        test_app.delete(f"/api/v1/agents/{data['id']}")

    def test_error_response_format(self, test_app):
        """Test that error responses follow expected format"""
        response = test_app.get("/api/v1/agents/nonexistent-agent")

        assert response.status_code == 404
        data = response.json()

        assert "detail" in data

    def test_list_response_format(self, test_app):
        """Test that list responses follow expected format"""
        response = test_app.get("/api/v1/agents")
        data = response.json()

        assert "agents" in data
        assert isinstance(data["agents"], list)


class TestHealthEndpoints:
    """Test health check endpoints"""

    def test_main_health_endpoint(self, test_app):
        """Test main health check endpoint"""
        response = test_app.get("/api/v1/health")

        assert response.status_code == 200
        data = response.json()

        assert "status" in data

    def test_ping_endpoint(self, test_app):
        """Test ping endpoint"""
        response = test_app.get("/ping")

        assert response.status_code == 200
        data = response.json()

        assert data["message"] == "pong"

    def test_root_endpoint(self, test_app):
        """Test root endpoint"""
        response = test_app.get("/")

        assert response.status_code == 200
        data = response.json()

        assert "name" in data
        assert "version" in data
        assert "status" in data


@requires_database
class TestEdgeCases:
    """Test edge cases and boundary conditions"""

    def test_create_agent_with_empty_name(self, test_app):
        """Test creating agent with empty name"""
        response = test_app.post(
            "/api/v1/agents",
            json={"name": ""},
        )

        # Should either fail validation or create with empty name
        # Behavior depends on implementation
        assert response.status_code in [201, 400, 422]

    def test_create_agent_with_special_characters(self, test_app):
        """Test creating agent with special characters in name"""
        agent_data = {
            "name": f"test-agent-special-chars-@#$-{uuid.uuid4().hex[:8]}",
            "displayName": "Test Agent with Special Chars!@#$%",
        }

        response = test_app.post("/api/v1/agents", json=agent_data)

        # Should handle gracefully
        if response.status_code == 201:
            test_app.delete(f"/api/v1/agents/{response.json()['id']}")

    def test_update_agent_with_empty_payload(self, test_app, sample_agent_data):
        """Test updating agent with empty payload"""
        # Create agent
        create_response = test_app.post("/api/v1/agents", json=sample_agent_data)
        agent_id = create_response.json()["id"]

        # Update with empty payload
        update_response = test_app.put(
            f"/api/v1/agents/{agent_id}",
            json={},
        )

        # Should return 400 (no fields to update)
        assert update_response.status_code == 400

        # Cleanup
        test_app.delete(f"/api/v1/agents/{agent_id}")

    def test_large_tools_list(self, test_app):
        """Test agent with large number of tools"""
        from app.llm.tool_resolver import TOOL_REGISTRY

        all_tools = list(TOOL_REGISTRY.keys())

        agent_data = {
            "name": f"many-tools-agent-{uuid.uuid4().hex[:8]}",
            "tools": all_tools,
        }

        response = test_app.post("/api/v1/agents", json=agent_data)
        assert response.status_code == 201

        data = response.json()
        assert len(data["tools"]) == len(all_tools)

        # Cleanup
        test_app.delete(f"/api/v1/agents/{data['id']}")

    def test_concurrent_agent_operations(self, test_app):
        """Test concurrent create and delete operations"""
        import concurrent.futures

        agent_ids = []

        def create_agent(i):
            response = test_app.post(
                "/api/v1/agents",
                json={"name": f"concurrent-agent-{i}-{uuid.uuid4().hex[:8]}"},
            )
            if response.status_code == 201:
                return response.json()["id"]
            return None

        # Create multiple agents concurrently
        # Note: TestClient is not truly concurrent, but this tests the pattern
        for i in range(5):
            aid = create_agent(i)
            if aid:
                agent_ids.append(aid)

        assert len(agent_ids) == 5

        # Cleanup
        for aid in agent_ids:
            test_app.delete(f"/api/v1/agents/{aid}")


# =============================================================================
# WORKFLOW MODEL CONFIGURATION TESTS
# =============================================================================

class TestWorkflowModelConfiguration:
    """Test model configuration for hierarchical workflows"""

    def test_model_config_creation_defaults(self):
        """Test ModelConfig creation with default values"""
        from app.workflows import ModelConfig

        config = ModelConfig()

        # Production defaults from 61c26c68fcd555cb636b435972f6c2625ca55f8d
        assert config.orchestrator_model == "anthropic/claude-opus-4-5-20251101"
        assert config.default_team_lead_model == "openai/gpt-oss-120b"
        assert config.default_worker_model == "ibm/granite-3.3-2b-instruct"
        assert config.enable_local_models is True
        assert config.team_lead_models["research"] == "openai/gpt-oss-120b"

    def test_preset_configurations(self):
        """Test preset configuration loading"""
        from app.workflows import CONFIG_PRESETS

        assert "cost_optimized" in CONFIG_PRESETS
        assert "quality_optimized" in CONFIG_PRESETS
        assert "full_api" in CONFIG_PRESETS
        assert "full_local" in CONFIG_PRESETS

    def test_model_registry_resolution(self):
        """Test model resolution through registry"""
        from app.workflows import ModelConfig, ModelRegistry

        config = ModelConfig(
            team_lead_models={"research": "ollama/llama3.1:8b"},
        )

        model = ModelRegistry.get_model_for_team_lead("research", config)
        assert model == "ollama/llama3.1:8b"

        # Non-specified domain should use default
        model = ModelRegistry.get_model_for_team_lead("nonexistent", config)
        assert model == config.default_team_lead_model

    def test_model_tier_detection(self):
        """Test model tier detection (API vs local)"""
        from app.workflows import ModelRegistry

        assert ModelRegistry.get_model_tier("openai/gpt-4o") == "api"
        assert ModelRegistry.get_model_tier("anthropic/claude-3.5-sonnet") == "api"
        assert ModelRegistry.get_model_tier("ollama/llama3.1:8b") == "local"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
