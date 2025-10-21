"""Base agent class"""

from typing import Dict, Any, Optional
from abc import ABC, abstractmethod
import logging

logger = logging.getLogger(__name__)

class BaseAgent(ABC):
    """Base class for all agents"""

    def __init__(self, name: str, memory_manager=None):
        self.name = name
        self.memory_manager = memory_manager
        logger.info(f"Initialized agent: {name}")

    @abstractmethod
    async def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the agent's task"""
        pass

    async def store_memory(self, key: str, value: Any) -> bool:
        """Store result in memory"""
        try:
            if not self.memory_manager:
                logger.warning(f"{self.name}: No memory manager available")
                return False

            # Store as a simple memory entry
            return await self.memory_manager.store(
                user_id=value.get("user_id", "system"),
                agent_id=self.name,
                messages=[{"role": "assistant", "content": str(value)}],
                metadata={"key": key, "agent": self.name}
            )
        except Exception as e:
            logger.error(f"{self.name}: Error storing memory: {e}")
            return False

    async def retrieve_memory(self, user_id: str, query: str) -> list:
        """Retrieve from memory"""
        try:
            if not self.memory_manager:
                return []

            return await self.memory_manager.retrieve(
                user_id=user_id,
                query=query,
                agent_id=self.name
            )
        except Exception as e:
            logger.error(f"{self.name}: Error retrieving memory: {e}")
            return []

    def get_status(self) -> Dict[str, Any]:
        """Get agent status"""
        return {
            "name": self.name,
            "status": "ready",
            "memory_enabled": self.memory_manager is not None
        }
