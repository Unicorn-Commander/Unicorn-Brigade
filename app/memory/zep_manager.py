"""Memory manager using Zep - temporal knowledge graph for AI agents

Zep provides:
- Automatic fact extraction and relationship tracking
- Temporal knowledge graphs (Graphiti)
- Session-based conversation memory
- Semantic search with vector embeddings
- User-scoped memory management
"""

from typing import Any, Optional, List, Dict
import logging
import os
import uuid
from datetime import datetime

logger = logging.getLogger(__name__)

# Import Zep SDK - supports both sync and async clients
try:
    from zep_python import ZepClient
    from zep_python.memory import Memory, Message, Session, MemorySearchPayload
    from zep_python.user import User
    ZEP_AVAILABLE = True
except ImportError:
    logger.warning("zep-python not installed. Install with: pip install zep-python")
    ZEP_AVAILABLE = False
    ZepClient = None
    Memory = None
    Message = None
    Session = None
    MemorySearchPayload = None
    User = None


class ZepMemoryManager:
    """Manages persistent memory using Zep with temporal knowledge graph

    Key Zep concepts:
    - Users: Top-level entity for organizing memories
    - Sessions: Conversations belonging to a user
    - Messages: Individual messages within a session
    - Facts: Automatically extracted relationships and entities
    - Memory: Combined context including messages, summaries, and facts
    """

    def __init__(self):
        """Initialize Zep client with configuration from environment

        Connection defaults:
        - In Docker: http://brigade-zep:8000 (container-to-container)
        - Local dev: Set ZEP_API_URL=http://localhost:8001 in .env
        """
        # Check if running in Docker (ENVIRONMENT=production or container hostname)
        in_docker = os.getenv("ENVIRONMENT") == "production" or os.path.exists("/.dockerenv")
        default_url = "http://brigade-zep:8000" if in_docker else "http://localhost:8001"

        self.api_url = os.getenv("ZEP_API_URL", default_url)
        self.api_key = os.getenv("ZEP_API_KEY", "")  # Optional for self-hosted

        if not ZEP_AVAILABLE:
            logger.error("Zep SDK not available - install zep-python")
            self.client = None
            return

        try:
            # Initialize Zep client
            # For self-hosted: api_url is required, api_key may be optional
            # For Zep Cloud: api_key is required (starts with 'z_')
            client_kwargs = {"api_url": self.api_url}
            if self.api_key:
                client_kwargs["api_key"] = self.api_key

            self.client = ZepClient(**client_kwargs)
            logger.info(f"ZepMemoryManager initialized with URL: {self.api_url}")
        except Exception as e:
            logger.error(f"Failed to initialize Zep client: {e}")
            self.client = None

    def _ensure_client(self) -> bool:
        """Check if client is available"""
        if not self.client:
            logger.warning("Zep client not initialized")
            return False
        return True

    async def ensure_user(self, user_id: str, metadata: Optional[Dict] = None) -> bool:
        """Ensure a user exists in Zep, create if not exists

        Args:
            user_id: Unique user identifier
            metadata: Optional user metadata

        Returns:
            True if user exists or was created successfully
        """
        if not self._ensure_client():
            return False

        try:
            # Try to get existing user
            try:
                self.client.user.get(user_id)
                return True
            except Exception:
                # User doesn't exist, create it
                pass

            # Create new user
            user_data = {
                "user_id": user_id,
                "metadata": metadata or {}
            }
            self.client.user.add(**user_data)
            logger.info(f"Created Zep user: {user_id}")
            return True
        except Exception as e:
            logger.error(f"Error ensuring user {user_id}: {e}")
            return False

    async def ensure_session(
        self,
        session_id: str,
        user_id: str,
        metadata: Optional[Dict] = None
    ) -> bool:
        """Ensure a session exists in Zep, create if not exists

        Args:
            session_id: Unique session identifier
            user_id: User this session belongs to
            metadata: Optional session metadata

        Returns:
            True if session exists or was created successfully
        """
        if not self._ensure_client():
            return False

        try:
            # Ensure user exists first
            await self.ensure_user(user_id)

            # Try to get existing session
            try:
                self.client.memory.get_session(session_id)
                return True
            except Exception:
                # Session doesn't exist, create it
                pass

            # Create new session
            session = Session(
                session_id=session_id,
                user_id=user_id,
                metadata=metadata or {}
            )
            self.client.memory.add_session(session)
            logger.info(f"Created Zep session: {session_id} for user: {user_id}")
            return True
        except Exception as e:
            logger.error(f"Error ensuring session {session_id}: {e}")
            return False

    async def store(
        self,
        user_id: str,
        agent_id: str,
        messages: List[Dict],
        metadata: Optional[Dict] = None,
        session_id: Optional[str] = None
    ) -> bool:
        """Store conversation messages in Zep memory

        Args:
            user_id: User identifier
            agent_id: Agent that participated in the conversation
            messages: List of message dicts with 'role' and 'content' keys
            metadata: Optional metadata to attach to the memory
            session_id: Optional session ID (auto-generated if not provided)

        Returns:
            True if stored successfully
        """
        if not self._ensure_client():
            return False

        try:
            # Generate session_id if not provided
            if not session_id:
                session_id = f"{user_id}_{agent_id}_{uuid.uuid4().hex[:8]}"

            # Ensure session exists
            session_metadata = {
                "agent_id": agent_id,
                **(metadata or {})
            }
            await self.ensure_session(session_id, user_id, session_metadata)

            # Convert messages to Zep Message format
            zep_messages = []
            for msg in messages:
                role = msg.get("role", "user").lower()
                content = msg.get("content", "")

                # Map common role names to Zep role_type
                role_type_map = {
                    "user": "user",
                    "human": "user",
                    "assistant": "assistant",
                    "ai": "assistant",
                    "system": "system",
                    "function": "function",
                    "tool": "tool"
                }
                role_type = role_type_map.get(role, "user")

                zep_messages.append(Message(
                    role=role,
                    role_type=role_type,
                    content=content,
                    metadata=msg.get("metadata", {})
                ))

            # Add memory to Zep
            memory = Memory(messages=zep_messages)
            self.client.memory.add_memory(session_id, memory)

            logger.info(f"Stored {len(zep_messages)} messages for user {user_id}, session {session_id}")
            return True
        except Exception as e:
            logger.error(f"Error storing memory: {e}")
            return False

    async def retrieve(
        self,
        user_id: str,
        query: str,
        agent_id: Optional[str] = None,
        limit: int = 10,
        session_id: Optional[str] = None
    ) -> List[Dict]:
        """Retrieve relevant memories using semantic search

        Args:
            user_id: User identifier
            query: Search query text
            agent_id: Optional agent filter
            limit: Maximum number of results
            session_id: Optional specific session to search

        Returns:
            List of relevant memories with scores
        """
        if not self._ensure_client():
            return []

        try:
            results = []

            if session_id:
                # Search within specific session
                search_payload = MemorySearchPayload(
                    text=query,
                    metadata={"agent_id": agent_id} if agent_id else None
                )
                search_results = self.client.memory.search_memory(
                    session_id,
                    search_payload,
                    limit=limit
                )

                for result in search_results:
                    results.append({
                        "content": result.message.content if result.message else (result.summary.content if result.summary else ""),
                        "score": result.score,
                        "metadata": result.metadata or {},
                        "session_id": session_id,
                        "type": "message" if result.message else "summary"
                    })
            else:
                # Search across all user sessions
                # Get all sessions for user and search each
                sessions = self.client.user.get_sessions(user_id)

                for session in sessions:
                    # Filter by agent if specified
                    if agent_id and session.metadata:
                        if session.metadata.get("agent_id") != agent_id:
                            continue

                    try:
                        search_payload = MemorySearchPayload(text=query)
                        session_results = self.client.memory.search_memory(
                            session.session_id,
                            search_payload,
                            limit=limit
                        )

                        for result in session_results:
                            results.append({
                                "content": result.message.content if result.message else (result.summary.content if result.summary else ""),
                                "score": result.score,
                                "metadata": result.metadata or {},
                                "session_id": session.session_id,
                                "type": "message" if result.message else "summary"
                            })
                    except Exception as e:
                        logger.warning(f"Error searching session {session.session_id}: {e}")

            # Sort by score and limit results
            results.sort(key=lambda x: x.get("score", 0), reverse=True)
            results = results[:limit]

            logger.info(f"Retrieved {len(results)} memories for user {user_id}, query: {query[:50]}...")
            return results
        except Exception as e:
            logger.error(f"Error retrieving memory: {e}")
            return []

    async def get_memory_context(
        self,
        session_id: str,
        last_n: Optional[int] = None
    ) -> Dict[str, Any]:
        """Get memory context for a session including facts and summaries

        This is Zep's high-level API that returns the most relevant context
        based on the session's recent messages and knowledge graph.

        Args:
            session_id: Session identifier
            last_n: Optional number of recent messages to consider

        Returns:
            Dict with messages, facts, summary, and context
        """
        if not self._ensure_client():
            return {}

        try:
            memory = self.client.memory.get_memory(session_id, lastn=last_n)

            return {
                "messages": [
                    {
                        "role": msg.role,
                        "role_type": msg.role_type,
                        "content": msg.content,
                        "created_at": str(msg.created_at) if msg.created_at else None
                    }
                    for msg in (memory.messages or [])
                ],
                "facts": memory.facts or [],
                "summary": memory.summary.content if memory.summary else None,
                "token_count": memory.token_count or 0
            }
        except Exception as e:
            logger.error(f"Error getting memory context: {e}")
            return {}

    async def get_all(
        self,
        user_id: str,
        agent_id: Optional[str] = None
    ) -> List[Dict]:
        """Get all memories for a user

        Args:
            user_id: User identifier
            agent_id: Optional agent filter

        Returns:
            List of all memories across sessions
        """
        if not self._ensure_client():
            return []

        try:
            memories = []
            sessions = self.client.user.get_sessions(user_id)

            for session in sessions:
                # Filter by agent if specified
                if agent_id and session.metadata:
                    if session.metadata.get("agent_id") != agent_id:
                        continue

                try:
                    memory = self.client.memory.get_memory(session.session_id)
                    memories.append({
                        "session_id": session.session_id,
                        "user_id": user_id,
                        "agent_id": session.metadata.get("agent_id") if session.metadata else None,
                        "messages": [
                            {"role": msg.role, "content": msg.content}
                            for msg in (memory.messages or [])
                        ],
                        "facts": memory.facts or [],
                        "summary": memory.summary.content if memory.summary else None,
                        "created_at": str(session.created_at) if session.created_at else None
                    })
                except Exception as e:
                    logger.warning(f"Error getting memory for session {session.session_id}: {e}")

            return memories
        except Exception as e:
            logger.error(f"Error getting all memories: {e}")
            return []

    async def get_user_facts(self, user_id: str) -> List[str]:
        """Get all extracted facts about a user from their knowledge graph

        Zep automatically extracts facts and relationships from conversations.
        This returns the accumulated knowledge about the user.

        Args:
            user_id: User identifier

        Returns:
            List of fact strings
        """
        if not self._ensure_client():
            return []

        try:
            # Get user's sessions and aggregate facts
            facts = set()
            sessions = self.client.user.get_sessions(user_id)

            for session in sessions:
                try:
                    memory = self.client.memory.get_memory(session.session_id)
                    if memory.facts:
                        facts.update(memory.facts)
                except Exception:
                    pass

            return list(facts)
        except Exception as e:
            logger.error(f"Error getting user facts: {e}")
            return []

    async def delete(self, memory_id: str) -> bool:
        """Delete a specific session/memory

        Args:
            memory_id: Session ID to delete

        Returns:
            True if deleted successfully
        """
        if not self._ensure_client():
            return False

        try:
            self.client.memory.delete_memory(memory_id)
            logger.info(f"Deleted memory/session: {memory_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting memory: {e}")
            return False

    async def delete_user(self, user_id: str) -> bool:
        """Delete a user and all their memories

        Args:
            user_id: User identifier to delete

        Returns:
            True if deleted successfully
        """
        if not self._ensure_client():
            return False

        try:
            self.client.user.delete(user_id)
            logger.info(f"Deleted user and all memories: {user_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting user: {e}")
            return False

    async def update(self, memory_id: str, data: str) -> bool:
        """Update is not directly supported in Zep - add new messages instead

        Zep's model is append-only for messages. To "update" context,
        add new messages that provide the updated information.

        Args:
            memory_id: Session ID
            data: New data to add

        Returns:
            True if added successfully
        """
        if not self._ensure_client():
            return False

        try:
            # Add as a new system message with the update
            memory = Memory(messages=[
                Message(
                    role="system",
                    role_type="system",
                    content=f"Context update: {data}"
                )
            ])
            self.client.memory.add_memory(memory_id, memory)
            logger.info(f"Added update to session: {memory_id}")
            return True
        except Exception as e:
            logger.error(f"Error updating memory: {e}")
            return False

    def get_stats(self) -> Dict[str, Any]:
        """Get memory system statistics

        Returns:
            Dict with status and configuration info
        """
        try:
            if not self.client:
                return {"status": "unavailable", "error": "Client not initialized"}

            return {
                "status": "operational",
                "provider": "zep",
                "api_url": self.api_url,
                "features": [
                    "temporal_knowledge_graph",
                    "fact_extraction",
                    "semantic_search",
                    "conversation_summaries",
                    "user_memory_scoping"
                ]
            }
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {"status": "error", "error": str(e)}

    async def close(self):
        """Close the Zep client connection"""
        if self.client:
            try:
                self.client.close()
                logger.info("Zep client closed")
            except Exception as e:
                logger.warning(f"Error closing Zep client: {e}")
