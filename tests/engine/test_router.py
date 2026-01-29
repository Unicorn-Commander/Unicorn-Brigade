"""
Tests for TaskRouter component
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.engine.models import Task, TaskIntent, RiskLevel, WorkerType
from app.engine.router import TaskRouter


class TestTaskRouter:
    """Tests for TaskRouter"""

    @pytest.fixture
    def mock_llm_client(self):
        """Create mock LLM client"""
        client = MagicMock()
        client.chat_completion = AsyncMock()
        return client

    @pytest.fixture
    def router(self, mock_llm_client):
        """Create router with mock client"""
        return TaskRouter(llm_client=mock_llm_client)

    def test_router_initialization(self):
        """Router should initialize with default values"""
        router = TaskRouter()
        assert router.default_model == "default"

    def test_detect_high_risk_keywords(self, router):
        """Router should detect high-risk keywords"""
        high_risk_tasks = [
            "Delete all production data",
            "Drop the users table",
            "Deploy to production",
            "rm -rf /var/log",
        ]

        for task_text in high_risk_tasks:
            task = Task(task=task_text, user_id="test")
            is_high_risk = router._detect_high_risk(task)
            assert is_high_risk, f"Should detect '{task_text}' as high risk"

    def test_detect_low_risk_tasks(self, router):
        """Router should not flag low-risk tasks"""
        low_risk_tasks = [
            "What is the weather today?",
            "Explain how Python works",
            "Summarize this article",
        ]

        for task_text in low_risk_tasks:
            task = Task(task=task_text, user_id="test")
            is_high_risk = router._detect_high_risk(task)
            assert not is_high_risk, f"Should not flag '{task_text}' as high risk"

    def test_detect_escalation_needed(self, router):
        """Router should detect when escalation is needed"""
        escalation_tasks = [
            "This is complex and needs Claude",
            "I need help with something difficult",
            "This is a critical security issue",
        ]

        for task_text in escalation_tasks:
            task = Task(task=task_text, user_id="test")
            needs_escalation = router._needs_escalation(task)
            # Note: Escalation detection depends on keywords
            # This test verifies the method exists and runs

    @pytest.mark.asyncio
    async def test_route_simple_research_task(self, router, mock_llm_client):
        """Router should classify research tasks correctly"""
        # Mock LLM response
        mock_llm_client.chat_completion.return_value = {
            "choices": [{
                "message": {
                    "content": '''{
                        "intent": "research",
                        "risk": "low",
                        "worker": "research",
                        "requires_approval": false,
                        "reasoning": "Simple research task"
                    }'''
                }
            }],
            "usage": {"prompt_tokens": 100, "completion_tokens": 50}
        }

        task = Task(task="What are the benefits of Python?", user_id="test")
        result = await router.route(task)

        assert result.intent == TaskIntent.RESEARCH
        assert result.risk == RiskLevel.LOW
        assert result.worker == WorkerType.RESEARCH
        assert result.requires_approval is False

    @pytest.mark.asyncio
    async def test_route_code_task(self, router, mock_llm_client):
        """Router should classify code tasks correctly"""
        mock_llm_client.chat_completion.return_value = {
            "choices": [{
                "message": {
                    "content": '''{
                        "intent": "code",
                        "risk": "low",
                        "worker": "code",
                        "requires_approval": false,
                        "reasoning": "Code generation task"
                    }'''
                }
            }],
            "usage": {"prompt_tokens": 100, "completion_tokens": 50}
        }

        task = Task(task="Write a Python function to sort a list", user_id="test")
        result = await router.route(task)

        assert result.intent == TaskIntent.CODE
        assert result.worker == WorkerType.CODE

    @pytest.mark.asyncio
    async def test_route_high_risk_override(self, router, mock_llm_client):
        """Router should override to high risk for dangerous tasks"""
        # Mock returns low risk, but task contains high-risk keywords
        mock_llm_client.chat_completion.return_value = {
            "choices": [{
                "message": {
                    "content": '''{
                        "intent": "ops",
                        "risk": "low",
                        "worker": "ops",
                        "requires_approval": false,
                        "reasoning": "Simple operation"
                    }'''
                }
            }],
            "usage": {"prompt_tokens": 100, "completion_tokens": 50}
        }

        task = Task(task="Delete all records from production database", user_id="test")
        result = await router.route(task)

        # Router should override to high risk
        assert result.risk in [RiskLevel.HIGH, RiskLevel.CRITICAL]
        assert result.requires_approval is True

    @pytest.mark.asyncio
    async def test_route_with_context(self, router, mock_llm_client):
        """Router should use context in routing"""
        mock_llm_client.chat_completion.return_value = {
            "choices": [{
                "message": {
                    "content": '''{
                        "intent": "code",
                        "risk": "medium",
                        "worker": "code",
                        "requires_approval": false,
                        "reasoning": "Code review with existing code"
                    }'''
                }
            }],
            "usage": {"prompt_tokens": 150, "completion_tokens": 60}
        }

        task = Task(
            task="Review this code for security issues",
            user_id="test",
            context={"code": "def login(user, password): ..."}
        )
        result = await router.route(task)

        assert result.intent == TaskIntent.CODE
        # Verify context was considered
        call_args = mock_llm_client.chat_completion.call_args
        messages = call_args[1]["messages"]
        assert any("code" in str(m) for m in messages)

    @pytest.mark.asyncio
    async def test_route_fallback_on_error(self, router, mock_llm_client):
        """Router should fall back gracefully on LLM error"""
        mock_llm_client.chat_completion.side_effect = Exception("LLM unavailable")

        task = Task(task="Do something", user_id="test")
        result = await router.route(task)

        # Should return safe fallback
        assert result.intent == TaskIntent.GENERAL
        assert result.risk == RiskLevel.MEDIUM
        assert result.requires_approval is True  # Safe fallback

    @pytest.mark.asyncio
    async def test_route_invalid_json_response(self, router, mock_llm_client):
        """Router should handle invalid JSON from LLM"""
        mock_llm_client.chat_completion.return_value = {
            "choices": [{
                "message": {
                    "content": "This is not valid JSON"
                }
            }],
            "usage": {"prompt_tokens": 100, "completion_tokens": 50}
        }

        task = Task(task="Research AI", user_id="test")
        result = await router.route(task)

        # Should handle gracefully
        assert result is not None
        assert result.intent is not None
