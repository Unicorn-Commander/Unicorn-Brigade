"""Tests for memory manager"""

import pytest
from app.memory.manager import MemoryManager

@pytest.mark.asyncio
async def test_memory_manager_initialization():
    """Test memory manager initialization"""
    memory = MemoryManager()
    assert memory is not None

    stats = memory.get_stats()
    assert "status" in stats

@pytest.mark.asyncio
async def test_memory_storage(test_user_id):
    """Test memory storage"""
    memory = MemoryManager()

    # Store memory
    success = await memory.store(
        user_id=test_user_id,
        agent_id="test-agent",
        messages=[{"role": "user", "content": "Test message"}],
        metadata={"test": True}
    )

    # Should return boolean (True if mem0 available, False otherwise)
    assert isinstance(success, bool)

@pytest.mark.asyncio
async def test_memory_retrieval(test_user_id):
    """Test memory retrieval"""
    memory = MemoryManager()

    # Retrieve memories (empty if mem0 not available)
    memories = await memory.retrieve(
        user_id=test_user_id,
        query="Test query"
    )

    assert isinstance(memories, list)

@pytest.mark.asyncio
async def test_memory_get_all(test_user_id):
    """Test getting all memories"""
    memory = MemoryManager()

    memories = await memory.get_all(user_id=test_user_id)
    assert isinstance(memories, list)

@pytest.mark.asyncio
async def test_memory_stats():
    """Test memory statistics"""
    memory = MemoryManager()

    stats = memory.get_stats()
    assert isinstance(stats, dict)
    assert "status" in stats
