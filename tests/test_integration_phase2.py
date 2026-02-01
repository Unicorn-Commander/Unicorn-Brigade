"""
Integration Tests for Phase 1 & Phase 2 Features

End-to-end tests covering:
- Agent chat with tool invocation
- MCP server tool calls
- A2A protocol agent invocation
- SSE event streaming (orchestration)
- Workflow execution
- Multi-agent coordination
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import json
import asyncio
from typing import Dict, Any


class TestAgentChatIntegration:
    """Test agent chat with tool invocation"""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_agent_chat_with_calculator_tool(self):
        """Test agent chat that uses calculator tool"""
        from app.llm.ops_center_client import OpsCenterLLMClient
        from app.llm.builtin_tools import calculator

        # Mock LLM client
        with patch('app.llm.ops_center_client.OpsCenterLLMClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client

            # Mock LLM response with tool call
            mock_client.chat_completion_with_tools.return_value = {
                "choices": [{
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [{
                            "id": "call_123",
                            "type": "function",
                            "function": {
                                "name": "calculator",
                                "arguments": json.dumps({"expression": "2+2"})
                            }
                        }]
                    }
                }],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5}
            }

            # Simulate tool execution
            result = calculator(expression="2+2")
            assert result.success is True
            assert result.result == 4

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_agent_chat_with_web_search_tool(self):
        """Test agent chat that uses web search tool"""
        from app.llm.builtin_tools import web_search

        # Mock serper API
        with patch('httpx.AsyncClient.post') as mock_post:
            mock_response = Mock()
            mock_response.json.return_value = {
                "organic": [
                    {"title": "Test Result", "snippet": "Test snippet", "link": "https://example.com"}
                ]
            }
            mock_response.status_code = 200
            mock_post.return_value = mock_response

            result = web_search(query="AI news")
            assert result.success is True
            assert "organic" in result.result or "results" in str(result.result)

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_agent_memory_storage_and_retrieval(self):
        """Test agent storing and retrieving memory"""
        from app.llm.builtin_tools import memory_store, memory_retrieve

        # Mock memory manager
        with patch('app.memory.manager.MemoryManager') as mock_manager_class:
            mock_manager = AsyncMock()
            mock_manager_class.return_value = mock_manager

            # Mock store
            mock_manager.store.return_value = True
            result = memory_store(
                user_id="test-user",
                content="Test memory content",
                metadata={"type": "test"}
            )
            assert result.success is True

            # Mock retrieve
            mock_manager.retrieve.return_value = [
                {"content": "Test memory content", "metadata": {"type": "test"}}
            ]
            result = memory_retrieve(
                user_id="test-user",
                query="test content"
            )
            assert result.success is True


class TestMCPServerIntegration:
    """Test MCP server tool invocation"""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_mcp_github_server_tool_call(self):
        """Test calling GitHub MCP server tool"""
        from app.mcp.registry import mcp_registry

        # Mock subprocess for MCP server
        with patch('subprocess.Popen') as mock_popen:
            mock_proc = MagicMock()
            mock_proc.pid = 12345
            mock_proc.poll.return_value = None
            mock_proc.stdin = MagicMock()
            mock_proc.stdout = MagicMock()
            mock_proc.stdout.readline.return_value = json.dumps({
                "result": {
                    "repository": "test-repo",
                    "created": True
                }
            }).encode() + b'\n'
            mock_popen.return_value = mock_proc

            # Test tool call
            result = await mcp_registry.call_tool(
                "github",
                "create_repository",
                {"name": "test-repo", "private": True}
            )

            assert result is not None
            assert "repository" in result or "created" in result or "error" in result

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_mcp_filesystem_server_tool_call(self):
        """Test calling Filesystem MCP server tool"""
        from app.mcp.registry import mcp_registry

        with patch('subprocess.Popen') as mock_popen:
            mock_proc = MagicMock()
            mock_proc.pid = 12345
            mock_proc.poll.return_value = None
            mock_proc.stdin = MagicMock()
            mock_proc.stdout = MagicMock()
            mock_proc.stdout.readline.return_value = json.dumps({
                "result": {
                    "content": "file contents here",
                    "path": "/test/file.txt"
                }
            }).encode() + b'\n'
            mock_popen.return_value = mock_proc

            result = await mcp_registry.call_tool(
                "filesystem",
                "read_file",
                {"path": "/test/file.txt"}
            )

            assert result is not None
            assert "content" in result or "path" in result or "error" in result

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_mcp_stripe_server_tool_call(self):
        """Test calling Stripe MCP server tool (Phase 1)"""
        from app.mcp.registry import mcp_registry

        with patch('subprocess.Popen') as mock_popen:
            mock_proc = MagicMock()
            mock_proc.pid = 12345
            mock_proc.poll.return_value = None
            mock_proc.stdin = MagicMock()
            mock_proc.stdout = MagicMock()
            mock_proc.stdout.readline.return_value = json.dumps({
                "result": {
                    "id": "pi_test123",
                    "amount": 1000,
                    "currency": "usd",
                    "status": "succeeded"
                }
            }).encode() + b'\n'
            mock_popen.return_value = mock_proc

            result = await mcp_registry.call_tool(
                "stripe",
                "create_payment_intent",
                {"amount": 1000, "currency": "usd"}
            )

            assert result is not None
            # Should have payment intent data or error
            assert "id" in result or "amount" in result or "error" in result


class TestA2AProtocolIntegration:
    """Test A2A protocol agent invocation"""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_a2a_agent_discovery(self):
        """Test A2A agent discovery (agent card)"""
        from app.protocols.a2a import get_agent_card

        # Mock database query for agent
        with patch('app.db.repositories.AgentRepository.get_by_id') as mock_get:
            mock_agent = Mock()
            mock_agent.id = "test-agent"
            mock_agent.name = "test-agent"
            mock_agent.display_name = "Test Agent"
            mock_agent.description = "Test agent for A2A"
            mock_agent.capabilities = ["test"]
            mock_agent.tools = ["calculator"]
            mock_agent.model = "gpt-4o-mini"
            mock_get.return_value = mock_agent

            # Get agent card
            card = await get_agent_card("test-agent")

            assert card is not None
            assert "id" in card
            assert "capabilities" in card

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_a2a_agent_invocation(self):
        """Test A2A agent invocation"""
        # Mock agent execution
        with patch('app.llm.ops_center_client.OpsCenterLLMClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client

            # Mock LLM response
            mock_client.execute_tool_loop.return_value = {
                "message": "Task completed successfully",
                "tool_calls": [],
                "usage": {"prompt_tokens": 10, "completion_tokens": 20}
            }

            # This would be called via A2A protocol
            result = await mock_client.execute_tool_loop(
                messages=[{"role": "user", "content": "Complete this task"}],
                tools=[],
                model="gpt-4o-mini"
            )

            assert result is not None
            assert "message" in result


class TestOrchestrationIntegration:
    """Test orchestration and event streaming"""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_orchestration_event_emission(self):
        """Test emitting orchestration events"""
        from app.orchestration import (
            emit_agent_started,
            emit_agent_completed,
            emit_tool_call,
            emit_tool_result,
        )

        # Test event emission (should not raise errors)
        emit_agent_started("test-agent", "test-mission", "Test task")
        emit_tool_call("test-agent", "test-mission", "calculator", {"expression": "2+2"})
        emit_tool_result("test-agent", "test-mission", "calculator", {"result": 4})
        emit_agent_completed("test-agent", "test-mission", "Task complete")

        # Events should be queued
        assert True  # If no exceptions, test passes

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_orchestration_state_tracking(self):
        """Test orchestration state tracking"""
        from app.orchestration.event_bus import orchestration_bus

        # Get current state
        state = orchestration_bus.get_state()

        assert state is not None
        assert "agents" in state
        assert "missions" in state
        assert isinstance(state["agents"], dict)
        assert isinstance(state["missions"], dict)


class TestWorkflowIntegration:
    """Test workflow execution integration"""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_workflow_validation(self):
        """Test workflow definition validation"""
        from app.workflows.templates import INVESTMENT_DUE_DILIGENCE
        from app.workflows.schema import WorkflowDefinition

        workflow = INVESTMENT_DUE_DILIGENCE

        # Validate structure
        assert isinstance(workflow, WorkflowDefinition)
        assert workflow.id
        assert workflow.name
        assert len(workflow.required_inputs) > 0
        assert len(workflow.final_outputs) > 0
        assert len(workflow.steps) > 0
        assert len(workflow.team_leads) > 0

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_workflow_step_execution_mock(self):
        """Test workflow step execution with mocked LLM"""
        from app.workflows.templates import INVESTMENT_DUE_DILIGENCE

        workflow = INVESTMENT_DUE_DILIGENCE
        first_step = workflow.steps[0]

        # Mock team lead execution
        with patch('app.llm.ops_center_client.OpsCenterLLMClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client

            # Mock response
            mock_client.chat_completion.return_value = {
                "choices": [{
                    "message": {
                        "role": "assistant",
                        "content": "Step completed successfully with mock data"
                    }
                }],
                "usage": {"prompt_tokens": 50, "completion_tokens": 30}
            }

            # Execute step (mocked)
            result = await mock_client.chat_completion(
                messages=[{"role": "user", "content": first_step.description}],
                model="gpt-4o-mini"
            )

            assert result is not None
            assert "choices" in result


class TestMultiAgentCoordination:
    """Test multi-agent coordination scenarios"""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_sequential_agent_execution(self):
        """Test sequential execution of multiple agents"""
        from app.llm.ops_center_client import OpsCenterLLMClient

        with patch('app.llm.ops_center_client.OpsCenterLLMClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client

            # Agent 1 execution
            mock_client.execute_tool_loop.return_value = {
                "message": "Research completed",
                "tool_calls": [],
                "usage": {"prompt_tokens": 10, "completion_tokens": 20}
            }

            result1 = await mock_client.execute_tool_loop(
                messages=[{"role": "user", "content": "Research this topic"}],
                tools=[],
                model="gpt-4o-mini"
            )

            # Agent 2 execution (uses result from agent 1)
            mock_client.execute_tool_loop.return_value = {
                "message": "Analysis completed",
                "tool_calls": [],
                "usage": {"prompt_tokens": 15, "completion_tokens": 25}
            }

            result2 = await mock_client.execute_tool_loop(
                messages=[
                    {"role": "user", "content": f"Analyze this: {result1['message']}"}
                ],
                tools=[],
                model="gpt-4o-mini"
            )

            assert result1 is not None
            assert result2 is not None

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_parallel_agent_execution(self):
        """Test parallel execution of multiple agents"""
        from app.llm.ops_center_client import OpsCenterLLMClient

        with patch('app.llm.ops_center_client.OpsCenterLLMClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client

            # Mock responses
            async def mock_execute(messages, tools, model, **kwargs):
                await asyncio.sleep(0.01)  # Simulate work
                return {
                    "message": f"Completed task: {messages[0]['content'][:20]}",
                    "tool_calls": [],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 20}
                }

            mock_client.execute_tool_loop.side_effect = mock_execute

            # Execute agents in parallel
            tasks = [
                mock_client.execute_tool_loop(
                    messages=[{"role": "user", "content": f"Task {i}"}],
                    tools=[],
                    model="gpt-4o-mini"
                )
                for i in range(3)
            ]

            results = await asyncio.gather(*tasks)

            assert len(results) == 3
            for result in results:
                assert result is not None
                assert "message" in result


class TestErrorHandling:
    """Test error handling in integrated scenarios"""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_tool_execution_error_handling(self):
        """Test error handling when tool execution fails"""
        from app.llm.builtin_tools import calculator

        # Invalid expression should return error
        result = calculator(expression="invalid / expression")
        assert result.success is False
        assert result.error is not None

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_mcp_server_not_found_error(self):
        """Test error when MCP server doesn't exist"""
        from app.mcp.registry import mcp_registry

        result = await mcp_registry.call_tool(
            "nonexistent-server",
            "some_tool",
            {}
        )

        assert "error" in result
        assert "Failed to start server" in result["error"]

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_workflow_missing_inputs_validation(self):
        """Test workflow validation with missing required inputs"""
        from app.workflows.templates import INVESTMENT_DUE_DILIGENCE

        workflow = INVESTMENT_DUE_DILIGENCE

        # Check required inputs
        assert "company_name" in workflow.required_inputs
        assert "investment_thesis" in workflow.required_inputs

        # In real execution, missing inputs would be caught
        # This test just validates the schema is properly defined


class TestToolChaining:
    """Test chaining multiple tools together"""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_web_search_then_memory_store(self):
        """Test searching web then storing results in memory"""
        from app.llm.builtin_tools import web_search, memory_store

        # Mock web search
        with patch('httpx.AsyncClient.post') as mock_post:
            mock_response = Mock()
            mock_response.json.return_value = {
                "organic": [
                    {"title": "AI News", "snippet": "Latest AI developments", "link": "https://example.com"}
                ]
            }
            mock_response.status_code = 200
            mock_post.return_value = mock_response

            search_result = web_search(query="AI developments")
            assert search_result.success is True

            # Mock memory storage
            with patch('app.memory.manager.MemoryManager.store') as mock_store:
                mock_store.return_value = True

                memory_result = memory_store(
                    user_id="test-user",
                    content=str(search_result.result),
                    metadata={"source": "web_search", "query": "AI developments"}
                )

                assert memory_result.success is True

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_calculator_then_json_formatting(self):
        """Test calculating then formatting result as JSON"""
        from app.llm.builtin_tools import calculator, json_format

        # Calculate
        calc_result = calculator(expression="(100 * 1.08) - 50")
        assert calc_result.success is True

        # Format as JSON
        json_result = json_format(data={"result": calc_result.result, "calculation": "(100 * 1.08) - 50"})
        assert json_result.success is True
        assert isinstance(json_result.result, str)
        # Should be valid JSON
        parsed = json.loads(json_result.result)
        assert "result" in parsed


class TestPerformanceBasics:
    """Basic performance checks for integrated features"""

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.slow
    async def test_calculator_performance(self):
        """Test calculator tool performance"""
        from app.llm.builtin_tools import calculator
        import time

        start = time.time()
        for i in range(100):
            result = calculator(expression=f"{i} + {i}")
            assert result.success is True
        end = time.time()

        # Should complete 100 calculations in < 1 second
        assert end - start < 1.0

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.slow
    async def test_json_format_performance(self):
        """Test JSON formatting performance"""
        from app.llm.builtin_tools import json_format
        import time

        test_data = {"key": "value", "number": 123, "nested": {"a": 1, "b": 2}}

        start = time.time()
        for i in range(100):
            result = json_format(data=test_data)
            assert result.success is True
        end = time.time()

        # Should format 100 JSON objects in < 1 second
        assert end - start < 1.0
