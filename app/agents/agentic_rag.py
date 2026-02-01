"""
Agentic RAG - Retrieval-Augmented Generation with Knowledge Graph and Vector Store

Combines FalkorDB knowledge graph traversal with Qdrant vector retrieval
for comprehensive, context-aware question answering with provenance tracking.

Key features:
- Query understanding: Parse natural language to identify entities and relationships
- Graph retrieval: Query FalkorDB for relevant nodes/edges
- Vector retrieval: Query Qdrant for semantically similar content
- Fusion: Combine both sources and generate response with provenance
- Agentic behavior: Use tools iteratively to gather information
"""

import logging
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime

from app.agents.base import BaseAgent
from app.knowledge.graph_manager import KnowledgeGraphManager
from app.memory.manager import MemoryManager
from app.llm.ops_center_client import (
    OpsCenterLLMClient,
    ToolDefinition,
    ToolParameter,
    ToolCall,
    ToolResult
)

logger = logging.getLogger(__name__)


@dataclass
class RAGContext:
    """Context gathered from knowledge graph and vector store"""
    graph_entities: List[Dict[str, Any]] = field(default_factory=list)
    graph_relationships: List[Dict[str, Any]] = field(default_factory=list)
    graph_paths: List[Dict[str, Any]] = field(default_factory=list)
    vector_memories: List[Dict[str, Any]] = field(default_factory=list)
    context_text: str = ""
    sources: List[Dict[str, Any]] = field(default_factory=list)

    def to_prompt_context(self, max_length: int = 4000) -> str:
        """Convert to context string for LLM prompt"""
        parts = []

        if self.graph_entities:
            parts.append("=== Knowledge Graph Entities ===")
            for entity in self.graph_entities[:10]:
                parts.append(f"- {entity.get('name')} ({entity.get('type')})")

        if self.graph_relationships:
            parts.append("\n=== Knowledge Graph Relationships ===")
            for rel in self.graph_relationships[:15]:
                from_name = rel.get("from", {}).get("name", "?")
                to_name = rel.get("to", {}).get("name", "?")
                rel_type = rel.get("relationship", "?")
                parts.append(f"- {from_name} --[{rel_type}]--> {to_name}")

        if self.graph_paths:
            parts.append("\n=== Connection Paths ===")
            for path in self.graph_paths[:5]:
                if path.get("path"):
                    nodes = path["path"].get("nodes", [])
                    rels = path["path"].get("relationships", [])
                    path_str = " -> ".join([n.get("name", "?") for n in nodes])
                    parts.append(f"- Path: {path_str}")

        if self.vector_memories:
            parts.append("\n=== Relevant Memories ===")
            for memory in self.vector_memories[:5]:
                content = memory.get("memory", memory.get("content", ""))
                if isinstance(content, str):
                    parts.append(f"- {content[:200]}...")

        context = "\n".join(parts)

        # Truncate if too long
        if len(context) > max_length:
            context = context[:max_length] + "\n[Context truncated...]"

        return context


@dataclass
class RAGResponse:
    """Response from AgenticRAG"""
    answer: str
    context: RAGContext
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    iterations: int = 0
    model: str = ""
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "answer": self.answer,
            "context": {
                "entities": self.context.graph_entities,
                "relationships": self.context.graph_relationships,
                "paths": self.context.graph_paths,
                "memories": self.context.vector_memories,
                "sources": self.context.sources
            },
            "tool_calls": self.tool_calls,
            "iterations": self.iterations,
            "model": self.model,
            "timestamp": self.timestamp
        }


class AgenticRAG(BaseAgent):
    """
    Agentic RAG combines knowledge graph traversal with vector retrieval.

    This agent can:
    1. Parse natural language queries to understand intent
    2. Query the FalkorDB knowledge graph for structured relationships
    3. Query Qdrant (via mem0) for semantically similar content
    4. Fuse results and generate answers with provenance
    5. Iteratively gather more context if needed
    """

    SYSTEM_PROMPT = """You are an intelligent assistant with access to a knowledge graph and memory system.

Your capabilities:
1. Query the knowledge graph to find entities and their relationships
2. Search memory for relevant past conversations and facts
3. Find paths between entities to understand connections
4. Store new facts and relationships you learn

When answering questions:
- First, identify what entities and relationships are relevant
- Use the knowledge_query tool to gather information from the graph
- Use the memory_search tool to find relevant memories
- Synthesize the information into a clear, accurate answer
- Always cite your sources (graph vs memory)

If you don't have enough information, say so clearly.
"""

    def __init__(
        self,
        knowledge_manager: Optional[KnowledgeGraphManager] = None,
        memory_manager: Optional[MemoryManager] = None,
        llm_client: Optional[OpsCenterLLMClient] = None,
        name: str = "agentic_rag"
    ):
        super().__init__(name=name, memory_manager=memory_manager)

        # Initialize components (lazy loading if not provided)
        self._knowledge_manager = knowledge_manager
        self._memory_manager = memory_manager
        self._llm_client = llm_client

        # Build tools
        self._tools = self._build_tools()

        logger.info(f"AgenticRAG initialized: {name}")

    @property
    def knowledge_manager(self) -> KnowledgeGraphManager:
        """Lazy-load knowledge manager"""
        if self._knowledge_manager is None:
            self._knowledge_manager = KnowledgeGraphManager()
        return self._knowledge_manager

    @property
    def llm_client(self) -> OpsCenterLLMClient:
        """Lazy-load LLM client"""
        if self._llm_client is None:
            self._llm_client = OpsCenterLLMClient()
        return self._llm_client

    def _build_tools(self) -> List[ToolDefinition]:
        """Build the tools available to the RAG agent"""
        tools = []

        # Knowledge Graph Query Tool
        async def kg_query_handler(
            operation: str,
            entity_name: Optional[str] = None,
            entity_type: Optional[str] = None,
            relationship_type: Optional[str] = None,
            natural_language_query: Optional[str] = None,
            start_entity: Optional[str] = None,
            end_entity: Optional[str] = None,
            max_depth: int = 2,
            limit: int = 20
        ) -> Dict[str, Any]:
            """Handle knowledge graph queries"""
            try:
                if operation == "natural_language":
                    if not natural_language_query:
                        return {"error": "natural_language_query required"}
                    return await self.knowledge_manager.natural_language_query(
                        query=natural_language_query,
                        limit=limit
                    )

                elif operation == "find_entities":
                    return await self.knowledge_manager.query_entities(
                        entity_type=entity_type,
                        name_pattern=entity_name,
                        limit=limit
                    )

                elif operation == "find_relationships":
                    return await self.knowledge_manager.query_relationships(
                        entity_name=entity_name,
                        relationship_type=relationship_type,
                        limit=limit
                    )

                elif operation == "find_related":
                    if not entity_name:
                        return {"error": "entity_name required for find_related"}
                    return await self.knowledge_manager.query_related(
                        entity_name=entity_name,
                        max_depth=max_depth
                    )

                elif operation == "find_path":
                    if not start_entity or not end_entity:
                        return {"error": "start_entity and end_entity required for find_path"}
                    return await self.knowledge_manager.find_shortest_path(
                        start_entity=start_entity,
                        end_entity=end_entity,
                        max_depth=max_depth
                    )

                elif operation == "get_context":
                    if not entity_name:
                        return {"error": "entity_name required for get_context"}
                    return await self.knowledge_manager.get_entity_context(
                        entity_name=entity_name,
                        max_depth=max_depth
                    )

                else:
                    return {"error": f"Unknown operation: {operation}"}

            except Exception as e:
                logger.error(f"KG query error: {e}")
                return {"error": str(e)}

        knowledge_query_tool = ToolDefinition(
            name="knowledge_query",
            description="""Query the knowledge graph for entities, relationships, and connections.

Operations:
- natural_language: Parse and execute a natural language query
- find_entities: Find entities by type or name pattern
- find_relationships: Find relationships for an entity
- find_related: Find all entities related to a given entity (multi-hop)
- find_path: Find the shortest path between two entities
- get_context: Get comprehensive context about an entity

Examples:
- "What companies is John connected to?" -> operation=natural_language, natural_language_query="What companies is John connected to?"
- Find all Person entities -> operation=find_entities, entity_type=Person
- Find who works at Acme -> operation=find_relationships, entity_name=Acme, relationship_type=WORKS_AT""",
            parameters=[
                ToolParameter(
                    name="operation",
                    type="string",
                    description="Query operation type",
                    required=True,
                    enum=["natural_language", "find_entities", "find_relationships",
                          "find_related", "find_path", "get_context"]
                ),
                ToolParameter(
                    name="natural_language_query",
                    type="string",
                    description="Natural language query (for natural_language operation)",
                    required=False
                ),
                ToolParameter(
                    name="entity_name",
                    type="string",
                    description="Entity name to search or query",
                    required=False
                ),
                ToolParameter(
                    name="entity_type",
                    type="string",
                    description="Entity type filter (Person, Company, Location, etc.)",
                    required=False
                ),
                ToolParameter(
                    name="relationship_type",
                    type="string",
                    description="Relationship type filter (WORKS_AT, KNOWS, etc.)",
                    required=False
                ),
                ToolParameter(
                    name="start_entity",
                    type="string",
                    description="Start entity for path finding",
                    required=False
                ),
                ToolParameter(
                    name="end_entity",
                    type="string",
                    description="End entity for path finding",
                    required=False
                ),
                ToolParameter(
                    name="max_depth",
                    type="number",
                    description="Maximum depth for traversal (default 2)",
                    required=False,
                    default=2
                ),
                ToolParameter(
                    name="limit",
                    type="number",
                    description="Maximum results (default 20)",
                    required=False,
                    default=20
                )
            ],
            handler=kg_query_handler
        )
        tools.append(knowledge_query_tool)

        # Memory Search Tool
        async def memory_search_handler(
            query: str,
            user_id: str = "system",
            limit: int = 10
        ) -> Dict[str, Any]:
            """Search memory for relevant information"""
            try:
                if not self._memory_manager:
                    return {"memories": [], "message": "Memory manager not available"}

                memories = await self._memory_manager.retrieve(
                    user_id=user_id,
                    query=query,
                    limit=limit
                )

                return {
                    "success": True,
                    "query": query,
                    "memories": memories,
                    "count": len(memories)
                }

            except Exception as e:
                logger.error(f"Memory search error: {e}")
                return {"error": str(e), "memories": []}

        memory_search_tool = ToolDefinition(
            name="memory_search",
            description="Search memory for relevant past conversations and information. Use this to find context from previous interactions.",
            parameters=[
                ToolParameter(
                    name="query",
                    type="string",
                    description="Search query",
                    required=True
                ),
                ToolParameter(
                    name="user_id",
                    type="string",
                    description="User ID to search memories for (default: system)",
                    required=False,
                    default="system"
                ),
                ToolParameter(
                    name="limit",
                    type="number",
                    description="Maximum results (default 10)",
                    required=False,
                    default=10
                )
            ],
            handler=memory_search_handler
        )
        tools.append(memory_search_tool)

        # Knowledge Store Tool
        async def kg_store_handler(
            operation: str,
            subject: Optional[str] = None,
            subject_type: Optional[str] = None,
            predicate: Optional[str] = None,
            object_name: Optional[str] = None,
            object_type: Optional[str] = None,
            properties: Optional[Dict[str, Any]] = None,
            confidence: float = 1.0,
            source: Optional[str] = None
        ) -> Dict[str, Any]:
            """Store information in the knowledge graph"""
            try:
                if operation == "store_fact":
                    if not all([subject, subject_type, predicate, object_name, object_type]):
                        return {"error": "store_fact requires: subject, subject_type, predicate, object_name, object_type"}
                    return await self.knowledge_manager.store_fact(
                        subject=subject,
                        subject_type=subject_type,
                        predicate=predicate,
                        obj=object_name,
                        obj_type=object_type,
                        confidence=confidence,
                        source=source or "agentic_rag"
                    )

                elif operation == "store_entity":
                    if not all([subject, subject_type]):
                        return {"error": "store_entity requires: subject (name), subject_type"}
                    return await self.knowledge_manager.store_entity(
                        name=subject,
                        entity_type=subject_type,
                        properties=properties
                    )

                elif operation == "store_relationship":
                    if not all([subject, subject_type, predicate, object_name, object_type]):
                        return {"error": "store_relationship requires all parameters"}
                    return await self.knowledge_manager.store_relationship(
                        from_entity=subject,
                        from_type=subject_type,
                        relationship=predicate,
                        to_entity=object_name,
                        to_type=object_type,
                        properties=properties
                    )

                else:
                    return {"error": f"Unknown operation: {operation}"}

            except Exception as e:
                logger.error(f"KG store error: {e}")
                return {"error": str(e)}

        knowledge_store_tool = ToolDefinition(
            name="knowledge_store",
            description="""Store facts and relationships in the knowledge graph.

Operations:
- store_fact: Store a fact as subject-predicate-object triple
- store_entity: Store a single entity
- store_relationship: Store a relationship between entities

Examples:
- Store "John works at Acme" -> operation=store_fact, subject=John, subject_type=Person, predicate=WORKS_AT, object_name=Acme, object_type=Company""",
            parameters=[
                ToolParameter(
                    name="operation",
                    type="string",
                    description="Operation type",
                    required=True,
                    enum=["store_fact", "store_entity", "store_relationship"]
                ),
                ToolParameter(
                    name="subject",
                    type="string",
                    description="Subject/source entity name",
                    required=False
                ),
                ToolParameter(
                    name="subject_type",
                    type="string",
                    description="Subject entity type",
                    required=False
                ),
                ToolParameter(
                    name="predicate",
                    type="string",
                    description="Relationship type (e.g., WORKS_AT, KNOWS)",
                    required=False
                ),
                ToolParameter(
                    name="object_name",
                    type="string",
                    description="Object/target entity name",
                    required=False
                ),
                ToolParameter(
                    name="object_type",
                    type="string",
                    description="Object entity type",
                    required=False
                ),
                ToolParameter(
                    name="properties",
                    type="object",
                    description="Additional properties",
                    required=False
                ),
                ToolParameter(
                    name="confidence",
                    type="number",
                    description="Confidence score 0-1",
                    required=False,
                    default=1.0
                ),
                ToolParameter(
                    name="source",
                    type="string",
                    description="Source of the information",
                    required=False
                )
            ],
            handler=kg_store_handler
        )
        tools.append(knowledge_store_tool)

        return tools

    async def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a RAG task"""
        query = task.get("query", task.get("message", ""))
        user_id = task.get("user_id", "system")
        model = task.get("model", "default")
        max_iterations = task.get("max_iterations", 5)

        if not query:
            return {"success": False, "error": "No query provided"}

        try:
            response = await self.query(
                query=query,
                user_id=user_id,
                model=model,
                max_iterations=max_iterations
            )
            return response.to_dict()

        except Exception as e:
            logger.error(f"RAG execution error: {e}")
            return {"success": False, "error": str(e)}

    async def query(
        self,
        query: str,
        user_id: str = "system",
        model: str = "default",
        max_iterations: int = 5,
        on_tool_call: Optional[Callable[[ToolCall], None]] = None,
        on_tool_result: Optional[Callable[[ToolResult], None]] = None
    ) -> RAGResponse:
        """
        Execute a RAG query with agentic tool use.

        Args:
            query: User's question
            user_id: User ID for memory context
            model: LLM model to use
            max_iterations: Maximum tool use iterations
            on_tool_call: Callback when a tool is called
            on_tool_result: Callback when a tool returns

        Returns:
            RAGResponse with answer and context
        """
        context = RAGContext()
        tool_calls_log = []

        # Build messages
        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": query}
        ]

        # Custom callbacks to capture context
        def capture_tool_call(tc: ToolCall):
            tool_calls_log.append({
                "name": tc.name,
                "arguments": tc.arguments,
                "timestamp": datetime.utcnow().isoformat()
            })
            if on_tool_call:
                on_tool_call(tc)

        def capture_tool_result(tr: ToolResult):
            # Capture results into context
            if tr.name == "knowledge_query" and not tr.error:
                result = tr.result
                if isinstance(result, dict):
                    if "entities" in result:
                        context.graph_entities.extend(result.get("entities", []))
                    if "relationships" in result:
                        context.graph_relationships.extend(result.get("relationships", []))
                    if "paths" in result:
                        context.graph_paths.extend(result.get("paths", []))
                    if result.get("path"):
                        context.graph_paths.append({"path": result["path"]})
                    # Track source
                    context.sources.append({
                        "type": "knowledge_graph",
                        "operation": tr.result.get("parsed", {}).get("intent", "query"),
                        "timestamp": datetime.utcnow().isoformat()
                    })

            elif tr.name == "memory_search" and not tr.error:
                result = tr.result
                if isinstance(result, dict) and "memories" in result:
                    context.vector_memories.extend(result.get("memories", []))
                    context.sources.append({
                        "type": "vector_memory",
                        "query": result.get("query", ""),
                        "count": result.get("count", 0),
                        "timestamp": datetime.utcnow().isoformat()
                    })

            if on_tool_result:
                on_tool_result(tr)

        # Execute tool loop
        try:
            response = await self.llm_client.execute_tool_loop(
                messages=messages,
                tools=self._tools,
                model=model,
                max_iterations=max_iterations,
                user_id=user_id,
                on_tool_call=capture_tool_call,
                on_tool_result=capture_tool_result
            )

            # Extract final answer
            answer = self.llm_client.get_response_content(response)

            # Generate context text
            context.context_text = context.to_prompt_context()

            return RAGResponse(
                answer=answer,
                context=context,
                tool_calls=tool_calls_log,
                iterations=len(tool_calls_log),
                model=model
            )

        except Exception as e:
            logger.error(f"RAG query error: {e}")
            return RAGResponse(
                answer=f"Error processing query: {str(e)}",
                context=context,
                tool_calls=tool_calls_log,
                iterations=len(tool_calls_log),
                model=model
            )

    async def simple_query(
        self,
        query: str,
        user_id: str = "system"
    ) -> Dict[str, Any]:
        """
        Execute a simple RAG query without agentic behavior.

        This directly queries both the knowledge graph and memory,
        then generates an answer. Faster but less flexible.

        Args:
            query: User's question
            user_id: User ID for memory context

        Returns:
            Dict with answer and context
        """
        context = RAGContext()

        try:
            # 1. Parse the query
            parsed = self.knowledge_manager.parse_natural_language_query(query)

            # 2. Query knowledge graph
            if parsed["entities"] or parsed["entity_types"]:
                kg_result = await self.knowledge_manager.natural_language_query(
                    query=query,
                    limit=20
                )
                if kg_result.get("success"):
                    context.graph_entities = kg_result.get("entities", [])
                    context.graph_relationships = kg_result.get("relationships", [])
                    context.graph_paths = kg_result.get("paths", [])
                    context.sources.append({"type": "knowledge_graph", "parsed": parsed})

            # 3. Query memory
            if self._memory_manager:
                memories = await self._memory_manager.retrieve(
                    user_id=user_id,
                    query=query,
                    limit=5
                )
                context.vector_memories = memories
                if memories:
                    context.sources.append({"type": "vector_memory", "count": len(memories)})

            # 4. Generate answer with context
            context_text = context.to_prompt_context()

            messages = [
                {
                    "role": "system",
                    "content": f"""Answer the user's question based on the following context from the knowledge graph and memory system.

{context_text}

If the context doesn't contain enough information to answer fully, say so. Always be accurate and cite whether information came from the knowledge graph or memory."""
                },
                {"role": "user", "content": query}
            ]

            response = await self.llm_client.chat_completion(
                messages=messages,
                model="default",
                temperature=0.7
            )

            answer = self.llm_client.get_response_content(response)

            return {
                "success": True,
                "answer": answer,
                "context": {
                    "entities": context.graph_entities,
                    "relationships": context.graph_relationships,
                    "paths": context.graph_paths,
                    "memories": context.vector_memories,
                    "sources": context.sources
                }
            }

        except Exception as e:
            logger.error(f"Simple RAG query error: {e}")
            return {
                "success": False,
                "error": str(e),
                "answer": None,
                "context": {}
            }

    async def retrieve_context(
        self,
        query: str,
        user_id: str = "system",
        include_graph: bool = True,
        include_memory: bool = True,
        max_entities: int = 20,
        max_memories: int = 5
    ) -> RAGContext:
        """
        Retrieve context without generating an answer.

        Useful for providing context to external systems or
        for more controlled RAG pipelines.

        Args:
            query: Search query
            user_id: User ID for memory
            include_graph: Include knowledge graph results
            include_memory: Include memory results
            max_entities: Maximum entities from graph
            max_memories: Maximum memories to retrieve

        Returns:
            RAGContext with retrieved information
        """
        context = RAGContext()

        try:
            if include_graph:
                kg_result = await self.knowledge_manager.natural_language_query(
                    query=query,
                    limit=max_entities
                )
                if kg_result.get("success"):
                    context.graph_entities = kg_result.get("entities", [])
                    context.graph_relationships = kg_result.get("relationships", [])
                    context.graph_paths = kg_result.get("paths", [])
                    context.sources.append({
                        "type": "knowledge_graph",
                        "parsed": kg_result.get("parsed", {})
                    })

            if include_memory and self._memory_manager:
                memories = await self._memory_manager.retrieve(
                    user_id=user_id,
                    query=query,
                    limit=max_memories
                )
                context.vector_memories = memories
                if memories:
                    context.sources.append({
                        "type": "vector_memory",
                        "count": len(memories)
                    })

            context.context_text = context.to_prompt_context()

        except Exception as e:
            logger.error(f"Context retrieval error: {e}")

        return context


# Singleton instance for global access
_agentic_rag_instance: Optional[AgenticRAG] = None


def get_agentic_rag(
    knowledge_manager: Optional[KnowledgeGraphManager] = None,
    memory_manager: Optional[MemoryManager] = None,
    llm_client: Optional[OpsCenterLLMClient] = None
) -> AgenticRAG:
    """Get or create the singleton AgenticRAG instance"""
    global _agentic_rag_instance

    if _agentic_rag_instance is None:
        _agentic_rag_instance = AgenticRAG(
            knowledge_manager=knowledge_manager,
            memory_manager=memory_manager,
            llm_client=llm_client
        )

    return _agentic_rag_instance
