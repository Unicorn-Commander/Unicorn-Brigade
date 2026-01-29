"""
Pytest configuration and fixtures for Unicorn Brigade integration tests.

Provides:
- Mock LLM client for deterministic tests
- Test fixtures for resilience, collaboration, and control flow
- Async support with pytest-asyncio
"""

import pytest
import asyncio
import json
import sys
import os
from typing import Dict, Any, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass, field

# Add app to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


# ============== Mock LLM Client ==============

class MockOpsCenterLLMClient:
    """
    Mock LLM client for deterministic testing.

    Allows configuring responses for specific inputs.
    """

    def __init__(self):
        self.responses: List[Dict[str, Any]] = []
        self.response_index = 0
        self.call_history: List[Dict[str, Any]] = []
        self.default_response = {
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": "Mock LLM response"
                },
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 20,
                "total_tokens": 30
            }
        }

    def set_responses(self, responses: List[Dict[str, Any]]):
        """Set a sequence of responses to return"""
        self.responses = responses
        self.response_index = 0

    def add_response(self, content: str, tool_calls: List[Dict] = None):
        """Add a response to the queue"""
        message = {
            "role": "assistant",
            "content": content
        }
        if tool_calls:
            message["tool_calls"] = tool_calls

        self.responses.append({
            "choices": [{
                "message": message,
                "finish_reason": "stop" if not tool_calls else "tool_calls"
            }],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}
        })

    def _get_next_response(self) -> Dict[str, Any]:
        """Get the next response from the queue"""
        if self.response_index < len(self.responses):
            response = self.responses[self.response_index]
            self.response_index += 1
            return response
        return self.default_response

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str = "default",
        temperature: float = 0.7,
        max_tokens: int = 2000,
        stream: bool = False,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Mock chat completion"""
        self.call_history.append({
            "method": "chat_completion",
            "messages": messages,
            "model": model,
            "temperature": temperature,
            "max_tokens": max_tokens
        })
        return self._get_next_response()

    async def chat_completion_with_tools(
        self,
        messages: List[Dict[str, Any]],
        tools: List,
        model: str = "default",
        temperature: float = 0.7,
        max_tokens: int = 2000,
        tool_choice: str = "auto",
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Mock chat completion with tools"""
        self.call_history.append({
            "method": "chat_completion_with_tools",
            "messages": messages,
            "tools": [t.name if hasattr(t, 'name') else str(t) for t in tools],
            "model": model
        })
        return self._get_next_response()

    def parse_tool_calls(self, response: Dict[str, Any]) -> List:
        """Parse tool calls from response"""
        from app.llm.ops_center_client import ToolCall
        tool_calls = []

        choices = response.get("choices", [])
        if choices:
            message = choices[0].get("message", {})
            if "tool_calls" in message:
                for tc in message["tool_calls"]:
                    try:
                        arguments = json.loads(tc["function"]["arguments"]) if isinstance(tc["function"]["arguments"], str) else tc["function"]["arguments"]
                    except (json.JSONDecodeError, KeyError):
                        arguments = {}

                    tool_calls.append(ToolCall(
                        id=tc.get("id", "tc_1"),
                        name=tc["function"]["name"],
                        arguments=arguments,
                    ))

        return tool_calls

    def has_tool_calls(self, response: Dict[str, Any]) -> bool:
        """Check if response has tool calls"""
        choices = response.get("choices", [])
        if choices:
            message = choices[0].get("message", {})
            return bool(message.get("tool_calls"))
        return False

    def get_response_content(self, response: Dict[str, Any]) -> str:
        """Extract content from response"""
        choices = response.get("choices", [])
        if choices:
            message = choices[0].get("message", {})
            return message.get("content", "")
        return ""

    async def close(self):
        """Close the client"""
        pass


@pytest.fixture
def mock_llm_client():
    """Fixture providing a mock LLM client"""
    return MockOpsCenterLLMClient()


# ============== Mock Step Executor ==============

class MockStepExecutor:
    """Mock step executor for control flow tests"""

    def __init__(self):
        self.execution_history = []
        self.results = {}  # step_id -> result

    def set_result(self, step_id: int, output: str, status: str = "completed"):
        """Set result for a specific step"""
        from app.engine.models import StepResult, ExecutionStatus
        self.results[step_id] = StepResult(
            step_id=step_id,
            status=ExecutionStatus(status),
            output=output,
            artifacts=[],
        )

    async def execute_step(self, step, context, user_id, model):
        """Execute a single step"""
        from app.engine.models import StepResult, ExecutionStatus
        self.execution_history.append({
            "step_id": step.id,
            "action": step.action,
            "context": context.copy()
        })

        if step.id in self.results:
            return self.results[step.id]

        return StepResult(
            step_id=step.id,
            status=ExecutionStatus.COMPLETED,
            output=f"Output for step {step.id}",
            artifacts=[],
        )


@pytest.fixture
def mock_step_executor():
    """Fixture providing a mock step executor"""
    return MockStepExecutor()


# ============== Circuit Breaker Fixtures ==============

@pytest.fixture
def circuit_breaker_config():
    """Default circuit breaker config for testing"""
    from app.engine.resilience import CircuitBreakerConfig
    return CircuitBreakerConfig(
        failure_threshold=3,
        success_threshold=2,
        timeout_seconds=1.0,  # Short timeout for tests
    )


@pytest.fixture
def circuit_breaker(circuit_breaker_config):
    """Circuit breaker fixture"""
    from app.engine.resilience import CircuitBreaker
    return CircuitBreaker("test_breaker", circuit_breaker_config)


# ============== Retry Fixtures ==============

@pytest.fixture
def retry_config():
    """Default retry config for testing"""
    from app.engine.resilience import RetryConfig
    return RetryConfig(
        max_retries=3,
        base_delay=0.01,  # Fast for tests
        max_delay=0.1,
        jitter=False,  # Deterministic for tests
    )


@pytest.fixture
def retry_strategy(retry_config):
    """Retry strategy fixture"""
    from app.engine.resilience import RetryStrategy
    return RetryStrategy(retry_config)


# ============== Bulkhead Fixtures ==============

@pytest.fixture
def bulkhead():
    """Bulkhead fixture"""
    from app.engine.resilience import Bulkhead
    return Bulkhead("test_bulkhead", max_concurrent=3, max_wait_seconds=1.0)


# ============== Collaboration Fixtures ==============

@pytest.fixture
def test_supervisor_agent():
    """Test supervisor agent"""
    from app.engine.collaboration import CollaborationAgent, AgentRole
    return CollaborationAgent(
        id="supervisor",
        name="Test Supervisor",
        role=AgentRole.SUPERVISOR,
        description="Test supervisor agent",
        system_prompt="You are a test supervisor. Coordinate the specialists.",
        model="default",
    )


@pytest.fixture
def test_specialist_agents():
    """Test specialist agents"""
    from app.engine.collaboration import CollaborationAgent, AgentRole
    return [
        CollaborationAgent(
            id="specialist_a",
            name="Specialist A",
            role=AgentRole.SPECIALIST,
            description="Handles task type A",
            system_prompt="You are specialist A.",
            model="default",
        ),
        CollaborationAgent(
            id="specialist_b",
            name="Specialist B",
            role=AgentRole.SPECIALIST,
            description="Handles task type B",
            system_prompt="You are specialist B.",
            model="default",
        ),
    ]


# ============== Control Flow Fixtures ==============

@pytest.fixture
def simple_condition():
    """Simple condition for testing"""
    return {
        "left": "$result",
        "op": "eq",
        "right": "success"
    }


@pytest.fixture
def complex_condition():
    """Complex AND/OR condition"""
    return {
        "op": "and",
        "conditions": [
            {"left": "$count", "op": "gt", "right": 5},
            {"left": "$status", "op": "eq", "right": "active"}
        ]
    }


@pytest.fixture
def for_loop_step():
    """For loop step definition"""
    return {
        "type": "loop",
        "loop_type": "for",
        "items": ["item1", "item2", "item3"],
        "item_var": "current_item",
        "index_var": "i",
        "body_steps": [
            {
                "id": 1,
                "action": "Process item",
                "tool": "llm",
                "inputs": ["$current_item"]
            }
        ],
        "max_iterations": 10
    }


@pytest.fixture
def while_loop_step():
    """While loop step definition"""
    return {
        "type": "loop",
        "loop_type": "while",
        "condition": {
            "left": "$counter",
            "op": "lt",
            "right": 5
        },
        "body_steps": [
            {
                "id": 1,
                "action": "Increment counter",
                "tool": "llm"
            }
        ],
        "max_iterations": 10
    }


@pytest.fixture
def parallel_step():
    """Parallel execution step definition"""
    return {
        "type": "parallel",
        "branches": [
            [
                {"id": 1, "action": "Branch 1 step 1", "tool": "llm"},
                {"id": 2, "action": "Branch 1 step 2", "tool": "llm"}
            ],
            [
                {"id": 3, "action": "Branch 2 step 1", "tool": "llm"}
            ]
        ],
        "wait_for": "all"
    }


@pytest.fixture
def conditional_step():
    """Conditional step definition"""
    return {
        "type": "conditional",
        "condition": {
            "left": "$status",
            "op": "eq",
            "right": "ready"
        },
        "then_steps": [
            {"id": 1, "action": "Process ready", "tool": "llm"}
        ],
        "else_steps": [
            {"id": 2, "action": "Wait for ready", "tool": "llm"}
        ]
    }


# ============== Observability Fixtures ==============

@pytest.fixture
def metrics_registry():
    """Fresh metrics registry for testing"""
    from app.engine.observability import MetricsRegistry
    # Create a new instance (bypass singleton for tests)
    registry = object.__new__(MetricsRegistry)
    registry._metrics = {}
    return registry


@pytest.fixture
def tracer():
    """Fresh tracer for testing"""
    from app.engine.observability import Tracer
    # Create a new instance (bypass singleton for tests)
    tracer_instance = object.__new__(Tracer)
    tracer_instance._spans = []
    tracer_instance._exporters = []
    tracer_instance._local = __import__('threading').local()
    return tracer_instance


@pytest.fixture
def health_checker():
    """Fresh health checker for testing"""
    from app.engine.observability import HealthChecker
    return HealthChecker()


# ============== Test Data Fixtures ==============

@pytest.fixture
def sample_workflow_plan():
    """Sample workflow plan for integration tests"""
    from app.engine.models import WorkflowPlan, WorkflowStep, ToolType, RiskLevel
    return WorkflowPlan(
        name="test_workflow",
        objective="Test the workflow engine",
        assumptions=["Environment is configured"],
        steps=[
            WorkflowStep(
                id=1,
                action="Initialize",
                tool=ToolType.LLM,
                inputs=["context"],
                outputs=["initialized"],
                risk=RiskLevel.LOW,
            ),
            WorkflowStep(
                id=2,
                action="Process",
                tool=ToolType.PYTHON,
                inputs=["$step1.output"],
                outputs=["result"],
                risk=RiskLevel.MEDIUM,
            ),
            WorkflowStep(
                id=3,
                action="Finalize",
                tool=ToolType.LLM,
                inputs=["$step2.output"],
                outputs=["final"],
                risk=RiskLevel.LOW,
            ),
        ],
        stop_conditions=["error", "max_steps_exceeded"],
    )


@pytest.fixture
def sample_context():
    """Sample execution context"""
    return {
        "user_id": "test-user",
        "task_id": "test-task-123",
        "steps": {},
        "artifacts": [],
    }


# ============== Async Helpers ==============

@pytest.fixture
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ============== Error Simulation ==============

class TransientError(Exception):
    """Simulated transient error for testing"""
    pass


class PermanentError(Exception):
    """Simulated permanent error for testing"""
    pass


@pytest.fixture
def transient_error():
    """Fixture for transient error"""
    return TransientError("Connection timeout")


@pytest.fixture
def permanent_error():
    """Fixture for permanent error"""
    return PermanentError("Resource not found - 404")
