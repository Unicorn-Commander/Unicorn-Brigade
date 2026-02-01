"""Tests for LangGraph workflows"""

import pytest
from app.graph.workflow import WorkflowManager
from app.graph.state import AgentState
from app.memory.manager import MemoryManager

@pytest.mark.asyncio
async def test_workflow_manager_initialization():
    """Test workflow manager initialization"""
    memory = MemoryManager()
    workflow = WorkflowManager(memory)

    assert workflow.memory_manager == memory
    assert len(workflow.agents) == 3
    assert "research" in workflow.agents
    assert "code" in workflow.agents
    assert "analysis" in workflow.agents

@pytest.mark.asyncio
async def test_workflow_stats():
    """Test workflow statistics"""
    memory = MemoryManager()
    workflow = WorkflowManager(memory)

    stats = workflow.get_workflow_stats()

    assert "available_agents" in stats
    assert "agents_status" in stats
    assert "memory_enabled" in stats
    assert len(stats["available_agents"]) == 3

@pytest.mark.asyncio
@pytest.mark.skipif(True, reason="LLM tests disabled by default - set RUN_LLM_TESTS=1 to enable")
async def test_workflow_execution():
    """Test complete workflow execution"""
    memory = MemoryManager()
    workflow = WorkflowManager(memory)

    initial_state = AgentState(
        task_id="test-workflow",
        agent_type="research",
        task="Test task for workflow",
        user_id="test-user",
        current_agent="",
        status="pending",
        context={},
        results=[],
        messages=[],
        input_tokens=0,
        output_tokens=0,
        tools_used=[],
        llm_route="openai:gpt-4o-mini",
        memory_keys=[],
        next=""
    )

    final_state = await workflow.execute_workflow(initial_state)

    assert final_state["status"] == "completed"
    assert len(final_state["results"]) > 0
    assert final_state["input_tokens"] >= 0
    assert final_state["output_tokens"] >= 0

@pytest.mark.asyncio
async def test_workflow_routing():
    """Test workflow routing logic"""
    memory = MemoryManager()
    workflow = WorkflowManager(memory)

    # Test initial routing
    state = AgentState(
        task_id="test",
        agent_type="research",
        task="Test",
        user_id="user",
        current_agent="",
        status="pending",
        context={},
        results=[],
        messages=[],
        input_tokens=0,
        output_tokens=0,
        tools_used=[],
        llm_route="openai",
        memory_keys=[],
        next=""
    )

    routed_state = workflow._route_agent(state)
    assert routed_state["current_agent"] == "research"

@pytest.mark.asyncio
async def test_workflow_finalization():
    """Test workflow finalization"""
    memory = MemoryManager()
    workflow = WorkflowManager(memory)

    state = AgentState(
        task_id="test",
        agent_type="research",
        task="Test",
        user_id="user",
        current_agent="research",
        status="executing",
        context={},
        results=[{"agent": "research", "status": "completed"}],
        messages=[],
        input_tokens=100,
        output_tokens=200,
        tools_used=[],
        llm_route="openai",
        memory_keys=[],
        next="end"
    )

    final_state = workflow._finalize(state)
    assert final_state["status"] == "completed"
    assert len(final_state["messages"]) > 0
