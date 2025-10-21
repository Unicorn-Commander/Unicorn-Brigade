"""Tests for agents"""

import pytest
from app.agents import ResearchAgent, CodeAgent, AnalysisAgent
from app.memory.manager import MemoryManager

@pytest.mark.asyncio
async def test_research_agent_initialization():
    """Test research agent initialization"""
    memory = MemoryManager()
    agent = ResearchAgent(memory)

    assert agent.name == "ResearchAgent"
    assert agent.memory_manager == memory

    status = agent.get_status()
    assert status["name"] == "ResearchAgent"
    assert status["status"] == "ready"

@pytest.mark.asyncio
async def test_code_agent_initialization():
    """Test code agent initialization"""
    memory = MemoryManager()
    agent = CodeAgent(memory)

    assert agent.name == "CodeAgent"
    status = agent.get_status()
    assert status["name"] == "CodeAgent"

@pytest.mark.asyncio
async def test_analysis_agent_initialization():
    """Test analysis agent initialization"""
    memory = MemoryManager()
    agent = AnalysisAgent(memory)

    assert agent.name == "AnalysisAgent"
    status = agent.get_status()
    assert status["name"] == "AnalysisAgent"

@pytest.mark.asyncio
@pytest.mark.skipif(not pytest.config.getoption("--run-llm-tests", default=False), reason="LLM tests disabled")
async def test_research_agent_execution(test_task):
    """Test research agent execution with real LLM call"""
    memory = MemoryManager()
    agent = ResearchAgent(memory)

    result = await agent.execute(test_task)

    assert "status" in result
    assert "tokens" in result
    assert result["agent"] == "ResearchAgent"

    if result["status"] == "completed":
        assert result["tokens"]["input"] > 0
        assert result["tokens"]["output"] > 0

@pytest.mark.asyncio
async def test_agent_memory_storage(test_task):
    """Test agent memory storage"""
    memory = MemoryManager()
    agent = ResearchAgent(memory)

    success = await agent.store_memory("test-key", {"test": "data"})
    assert isinstance(success, bool)

@pytest.mark.asyncio
async def test_agent_memory_retrieval(test_user_id):
    """Test agent memory retrieval"""
    memory = MemoryManager()
    agent = ResearchAgent(memory)

    memories = await agent.retrieve_memory(test_user_id, "test query")
    assert isinstance(memories, list)
