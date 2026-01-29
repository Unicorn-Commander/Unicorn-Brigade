"""
Pytest configuration and fixtures for engine tests
"""

import pytest
from unittest.mock import MagicMock, AsyncMock


@pytest.fixture
def mock_llm_response():
    """Factory for creating mock LLM responses"""
    def _create(content, tokens=None):
        return {
            "choices": [{
                "message": {
                    "content": content
                }
            }],
            "usage": tokens or {"prompt_tokens": 100, "completion_tokens": 50},
            "model": "test-model",
            "provider": "test",
        }
    return _create


@pytest.fixture
def mock_memory_manager():
    """Create a mock MemoryManager"""
    manager = MagicMock()
    manager.store = AsyncMock(return_value=True)
    manager.retrieve = AsyncMock(return_value=[])
    manager.get_stats = MagicMock(return_value={"total": 0})
    return manager


@pytest.fixture
def mock_workflow_memory(mock_memory_manager):
    """Create a WorkflowMemory with mocked manager"""
    from app.engine.memory_integration import WorkflowMemory
    return WorkflowMemory(memory_manager=mock_memory_manager)


@pytest.fixture
def model_selector():
    """Create a ModelSelector for testing"""
    from app.engine.model_benchmarks import ModelSelector
    return ModelSelector()


@pytest.fixture
def agent_worker_bridge(mock_llm_client, mock_memory_manager):
    """Create an AgentWorkerBridge with mocks"""
    from app.engine.agent_bridge import AgentWorkerBridge
    bridge = AgentWorkerBridge(
        memory_manager=mock_memory_manager,
        llm_client=mock_llm_client,
    )
    return bridge


@pytest.fixture
def meta_agent(mock_llm_client):
    """Create a MetaAgent with mocked LLM client"""
    from app.engine.meta_agent import MetaAgent
    return MetaAgent(llm_client=mock_llm_client)


@pytest.fixture
def approval_ui_generator():
    """Create an ApprovalUIGenerator"""
    from app.engine.approval_ui import ApprovalUIGenerator
    return ApprovalUIGenerator(agent_id="test_agent")


@pytest.fixture
def mock_llm_client(mock_llm_response):
    """Create a reusable mock LLM client"""
    client = MagicMock()
    client.chat_completion = AsyncMock(return_value=mock_llm_response("Test response"))
    return client


@pytest.fixture
def sample_task():
    """Create a sample task for testing"""
    from app.engine.models import Task
    return Task(
        task="Test task",
        user_id="test_user",
        context={"test": True},
    )


@pytest.fixture
def sample_workflow_steps():
    """Create sample workflow steps"""
    from app.engine.models import WorkflowStep, WorkerType, ToolType

    return [
        WorkflowStep(
            id="step_1",
            name="Research",
            description="Gather information",
            worker_type=WorkerType.RESEARCH,
            tool=ToolType.LLM,
            timeout=60,
            expected_outputs=["findings"],
        ),
        WorkflowStep(
            id="step_2",
            name="Analyze",
            description="Analyze findings",
            worker_type=WorkerType.REPORT,
            tool=ToolType.LLM,
            timeout=60,
            depends_on=["step_1"],
            expected_outputs=["analysis"],
        ),
        WorkflowStep(
            id="step_3",
            name="Report",
            description="Generate report",
            worker_type=WorkerType.REPORT,
            tool=ToolType.LLM,
            timeout=60,
            depends_on=["step_2"],
            expected_outputs=["report"],
        ),
    ]


@pytest.fixture
def sample_workflow_plan(sample_workflow_steps):
    """Create a sample workflow plan"""
    from app.engine.models import WorkflowPlan

    return WorkflowPlan(
        task_id="test_task_123",
        steps=sample_workflow_steps,
        estimated_time=180,
    )
