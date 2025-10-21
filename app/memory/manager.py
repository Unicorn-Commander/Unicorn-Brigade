"""Memory manager using mem0"""

from typing import Any, Optional, List, Dict
import logging
import os
from mem0 import Memory
import json

logger = logging.getLogger(__name__)

class MemoryManager:
    """Manages persistent memory using mem0 with PostgreSQL + Qdrant backend"""

    def __init__(self):
        self.config = {
            "vector_store": {
                "provider": "qdrant",
                "config": {
                    "url": os.getenv("QDRANT_URL", "http://brigade-qdrant:6333"),
                    "collection_name": os.getenv("QDRANT_COLLECTION", "brigade_memories")
                }
            },
            "llm": {
                "provider": "openai",
                "config": {
                    "model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                    "temperature": 0,
                    "api_key": os.getenv("OPENAI_API_KEY")
                }
            },
            "embedder": {
                "provider": "openai",
                "config": {
                    "model": "text-embedding-3-small"
                }
            }
        }

        try:
            self.memory = Memory.from_config(self.config)
            logger.info("MemoryManager initialized with mem0")
        except Exception as e:
            logger.error(f"Failed to initialize mem0: {e}")
            self.memory = None

    async def store(self, user_id: str, agent_id: str, messages: List[Dict], metadata: Optional[Dict] = None) -> bool:
        """Store conversation in memory"""
        try:
            if not self.memory:
                logger.warning("mem0 not initialized, skipping storage")
                return False

            # Convert messages to string for mem0
            conversation_text = "\n".join([
                f"{msg.get('role', 'unknown')}: {msg.get('content', '')}"
                for msg in messages
            ])

            # Prepare metadata
            full_metadata = metadata or {}
            full_metadata.update({
                "user_id": user_id,
                "agent_id": agent_id
            })

            # Add to mem0
            self.memory.add(
                conversation_text,
                user_id=user_id,
                agent_id=agent_id,
                metadata=full_metadata
            )

            logger.info(f"Stored memory for user {user_id}, agent {agent_id}")
            return True
        except Exception as e:
            logger.error(f"Error storing memory: {e}")
            return False

    async def retrieve(self, user_id: str, query: str, agent_id: Optional[str] = None, limit: int = 10) -> List[Dict]:
        """Retrieve relevant memories"""
        try:
            if not self.memory:
                logger.warning("mem0 not initialized, returning empty")
                return []

            # Search memories
            filters = {"user_id": user_id}
            if agent_id:
                filters["agent_id"] = agent_id

            memories = self.memory.search(query, user_id=user_id, limit=limit)

            logger.info(f"Retrieved {len(memories)} memories for user {user_id}")
            return memories
        except Exception as e:
            logger.error(f"Error retrieving memory: {e}")
            return []

    async def get_all(self, user_id: str, agent_id: Optional[str] = None) -> List[Dict]:
        """Get all memories for user"""
        try:
            if not self.memory:
                return []

            memories = self.memory.get_all(user_id=user_id)

            if agent_id:
                memories = [m for m in memories if m.get("agent_id") == agent_id]

            return memories
        except Exception as e:
            logger.error(f"Error getting memories: {e}")
            return []

    async def delete(self, memory_id: str) -> bool:
        """Delete specific memory"""
        try:
            if not self.memory:
                return False

            self.memory.delete(memory_id)
            logger.info(f"Deleted memory: {memory_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting memory: {e}")
            return False

    async def update(self, memory_id: str, data: str) -> bool:
        """Update existing memory"""
        try:
            if not self.memory:
                return False

            self.memory.update(memory_id, data)
            logger.info(f"Updated memory: {memory_id}")
            return True
        except Exception as e:
            logger.error(f"Error updating memory: {e}")
            return False

    def get_stats(self) -> Dict[str, Any]:
        """Get memory statistics"""
        try:
            if not self.memory:
                return {"status": "unavailable"}

            return {
                "status": "operational",
                "provider": "mem0",
                "vector_store": "qdrant",
                "embedder": "openai"
            }
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {"status": "error", "error": str(e)}
