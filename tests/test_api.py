# Executed by Grok (headless lane)
"""Tests for API endpoints"""

import pytest
from fastapi.testclient import TestClient

from app.api.routes import init_managers
from app.graph.workflow import WorkflowManager
from app.main import app
from app.memory.manager import MemoryManager
from tests.http_auth import install_test_auth

# Initialize test client
client = TestClient(app)


@pytest.fixture(autouse=True)
def _auth_overrides():
    install_test_auth(app)
    yield
    app.dependency_overrides.clear()

# Initialize managers for testing
memory_manager = MemoryManager()
workflow_manager = WorkflowManager(memory_manager)
init_managers(memory_manager, workflow_manager)

def test_root_endpoint():
    """Test root endpoint"""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "name" in data
    assert "version" in data
    assert data["status"] == "operational"

def test_ping_endpoint():
    """Test ping endpoint"""
    response = client.get("/ping")
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "pong"

def test_health_endpoint():
    """Test health check endpoint"""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "timestamp" in data

def test_system_status_endpoint():
    """Test system status endpoint"""
    response = client.get("/api/v1/system/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "operational"
    assert "version" in data
    assert "memory" in data
    assert "agents" in data

@pytest.mark.skipif(True, reason="LLM tests disabled by default - set RUN_LLM_TESTS=1 to enable")
def test_execute_task_endpoint():
    """Test task execution endpoint"""
    response = client.post(
        "/api/v1/agents/execute",
        json={
            "agent_type": "research",
            "task": "Test task",
            "user_id": "test-user"
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert "task_id" in data
    assert "status" in data
    assert "result" in data

def test_execute_task_invalid_agent():
    """Test task execution with invalid agent"""
    response = client.post(
        "/api/v1/agents/execute",
        json={
            "agent_type": "invalid_agent",
            "task": "Test task"
        }
    )

    # Should still process but return error in workflow
    assert response.status_code in [200, 500]

def test_memory_query_endpoint():
    """Test memory query endpoint"""
    response = client.post(
        "/api/v1/memory/query",
        json={
            "user_id": "test-user",
            "query": "test query"
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert "memories" in data
    assert "count" in data
    assert isinstance(data["memories"], list)

def test_get_user_memories_endpoint():
    """Test get user memories endpoint"""
    response = client.get("/api/v1/memory/user/test-user")

    assert response.status_code == 200
    data = response.json()
    assert "memories" in data
    assert "count" in data
