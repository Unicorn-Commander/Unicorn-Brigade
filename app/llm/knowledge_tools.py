"""
Knowledge Graph Tools for Agent Execution

Provides tools for agents to store and query knowledge graphs using FalkorDB.
Enables persistent relationship tracking across conversations.
"""

import logging
from typing import Any, Optional

from app.knowledge.graph_manager import KnowledgeGraphManager
from app.llm.ops_center_client import ToolDefinition, ToolParameter

logger = logging.getLogger(__name__)

# Singleton instance of the knowledge graph manager
_knowledge_graph_manager: Optional[KnowledgeGraphManager] = None


def get_knowledge_graph_manager() -> KnowledgeGraphManager:
    """Get or create the singleton KnowledgeGraphManager instance"""
    global _knowledge_graph_manager
    if _knowledge_graph_manager is None:
        _knowledge_graph_manager = KnowledgeGraphManager()
    return _knowledge_graph_manager


# ============== Knowledge Store Tool ==============

async def knowledge_store_handler(
    operation: str,
    subject: Optional[str] = None,
    subject_type: Optional[str] = None,
    predicate: Optional[str] = None,
    object: Optional[str] = None,
    object_type: Optional[str] = None,
    properties: Optional[dict[str, Any]] = None,
    confidence: float = 1.0,
    source: Optional[str] = None,
    agent_id: Optional[str] = None,
    caller_user_id: Optional[str] = None,
    caller_email: Optional[str] = None,  # injected for human callers; accepted, not used
) -> dict[str, Any]:
    # Per-user memory scoping. The injected caller_user_id (Brigade puts it
    # there because the ToolDefinition has needs_caller_context=True) wins
    # over a literal agent_id arg the LLM might pass. This keeps facts I
    # store about user A out of user B's recall.
    if caller_user_id:
        agent_id = f"user:{caller_user_id}"
    """
    Store facts, entities, and relationships in the knowledge graph.

    Operations:
    - store_fact: Store a fact as a triple (subject-predicate-object)
    - store_entity: Store a single entity
    - store_relationship: Store a relationship between two entities
    - delete_entity: Remove an entity and its relationships
    """
    logger.info(f"Knowledge store operation: {operation}")

    manager = get_knowledge_graph_manager()

    if operation == "store_fact":
        if not all([subject, subject_type, predicate, object, object_type]):
            return {
                "success": False,
                "error": "store_fact requires: subject, subject_type, predicate, object, object_type"
            }

        return await manager.store_fact(
            subject=subject,
            subject_type=subject_type,
            predicate=predicate,
            obj=object,
            obj_type=object_type,
            confidence=confidence,
            source=source,
            agent_id=agent_id
        )

    elif operation == "store_entity":
        if not all([subject, subject_type]):
            return {
                "success": False,
                "error": "store_entity requires: subject (entity name), subject_type (entity type)"
            }

        return await manager.store_entity(
            name=subject,
            entity_type=subject_type,
            properties=properties,
            agent_id=agent_id
        )

    elif operation == "store_relationship":
        if not all([subject, subject_type, predicate, object, object_type]):
            return {
                "success": False,
                "error": "store_relationship requires: subject, subject_type, predicate, object, object_type"
            }

        return await manager.store_relationship(
            from_entity=subject,
            from_type=subject_type,
            relationship=predicate,
            to_entity=object,
            to_type=object_type,
            properties=properties,
            agent_id=agent_id
        )

    elif operation == "delete_entity":
        if not subject:
            return {
                "success": False,
                "error": "delete_entity requires: subject (entity name)"
            }

        return await manager.delete_entity(
            name=subject,
            entity_type=subject_type,
            agent_id=agent_id
        )

    else:
        return {
            "success": False,
            "error": f"Unknown operation: {operation}. Valid: store_fact, store_entity, store_relationship, delete_entity"
        }


KNOWLEDGE_STORE_TOOL = ToolDefinition(
    name="knowledge_store",
    description="""Store facts and relationships in the knowledge graph. Use this to remember information about people, companies, concepts, and their relationships.

Examples:
- Store fact: "John works at Acme Corp" -> operation=store_fact, subject=John, subject_type=Person, predicate=WORKS_AT, object=Acme Corp, object_type=Company
- Store entity: "Remember Acme Corp is a company" -> operation=store_entity, subject=Acme Corp, subject_type=Company
- Store relationship: "John knows Jane" -> operation=store_relationship, subject=John, subject_type=Person, predicate=KNOWS, object=Jane, object_type=Person""",
    parameters=[
        ToolParameter(
            name="operation",
            type="string",
            description="Operation: store_fact, store_entity, store_relationship, delete_entity",
            required=True,
            enum=["store_fact", "store_entity", "store_relationship", "delete_entity"]
        ),
        ToolParameter(
            name="subject",
            type="string",
            description="Subject/source entity name (e.g., 'John Doe', 'Acme Corp')",
            required=False
        ),
        ToolParameter(
            name="subject_type",
            type="string",
            description="Subject entity type (Person, Company, Concept, Location, Product, Event)",
            required=False
        ),
        ToolParameter(
            name="predicate",
            type="string",
            description="Relationship type (e.g., WORKS_AT, KNOWS, LOCATED_IN, OWNS, PART_OF)",
            required=False
        ),
        ToolParameter(
            name="object",
            type="string",
            description="Object/target entity name",
            required=False
        ),
        ToolParameter(
            name="object_type",
            type="string",
            description="Object entity type (Person, Company, Concept, Location, Product, Event)",
            required=False
        ),
        ToolParameter(
            name="properties",
            type="object",
            description="Additional properties for the entity or relationship",
            required=False
        ),
        ToolParameter(
            name="confidence",
            type="number",
            description="Confidence score 0-1 (default 1.0)",
            required=False,
            default=1.0
        ),
        ToolParameter(
            name="source",
            type="string",
            description="Source of the information (e.g., 'user_conversation', 'web_search')",
            required=False
        ),
        ToolParameter(
            name="agent_id",
            type="string",
            description="Agent ID to store in agent-specific graph (optional)",
            required=False
        ),
    ],
    handler=knowledge_store_handler,
    needs_caller_context=True,
)


# ============== Knowledge Query Tool ==============

async def knowledge_query_handler(
    operation: str,
    entity_name: Optional[str] = None,
    entity_type: Optional[str] = None,
    relationship_type: Optional[str] = None,
    cypher_query: Optional[str] = None,
    cypher_params: Optional[dict[str, Any]] = None,
    direction: str = "both",
    max_depth: int = 2,
    agent_id: Optional[str] = None,
    limit: int = 20,
    caller_user_id: Optional[str] = None,
    caller_email: Optional[str] = None,  # injected for human callers; accepted, not used
) -> dict[str, Any]:
    # Per-user memory scoping (matches knowledge_store_handler). caller_user_id
    # is auto-injected by Brigade's tool dispatcher since the ToolDefinition
    # below has needs_caller_context=True.
    if caller_user_id:
        agent_id = f"user:{caller_user_id}"
    """
    Query the knowledge graph for entities, relationships, and patterns.

    Operations:
    - find_entities: Find entities by type or name pattern
    - find_relationships: Find relationships for an entity
    - find_related: Find all entities related to a given entity (multi-hop)
    - cypher: Execute a raw Cypher query
    - stats: Get knowledge graph statistics
    """
    logger.info(f"Knowledge query operation: {operation}")

    manager = get_knowledge_graph_manager()

    if operation == "find_entities":
        return await manager.query_entities(
            entity_type=entity_type,
            name_pattern=entity_name,
            agent_id=agent_id,
            limit=limit
        )

    elif operation == "find_relationships":
        return await manager.query_relationships(
            entity_name=entity_name,
            relationship_type=relationship_type,
            direction=direction,
            agent_id=agent_id,
            limit=limit
        )

    elif operation == "find_related":
        if not entity_name:
            return {
                "success": False,
                "error": "find_related requires: entity_name"
            }

        return await manager.query_related(
            entity_name=entity_name,
            max_depth=max_depth,
            agent_id=agent_id
        )

    elif operation == "cypher":
        if not cypher_query:
            return {
                "success": False,
                "error": "cypher operation requires: cypher_query"
            }

        return await manager.execute_cypher(
            query=cypher_query,
            params=cypher_params,
            agent_id=agent_id
        )

    elif operation == "stats":
        return manager.get_stats()

    else:
        return {
            "success": False,
            "error": f"Unknown operation: {operation}. Valid: find_entities, find_relationships, find_related, cypher, stats"
        }


KNOWLEDGE_QUERY_TOOL = ToolDefinition(
    name="knowledge_query",
    description="""Query the knowledge graph for entities, relationships, and patterns.

Examples:
- Find all people: operation=find_entities, entity_type=Person
- Find who works at Acme: operation=find_relationships, entity_name=Acme Corp, relationship_type=WORKS_AT, direction=incoming
- Find everyone connected to John: operation=find_related, entity_name=John, max_depth=2
- Custom Cypher: operation=cypher, cypher_query="MATCH (p:Person)-[:WORKS_AT]->(c:Company) RETURN p.name, c.name"
- Get stats: operation=stats""",
    parameters=[
        ToolParameter(
            name="operation",
            type="string",
            description="Operation: find_entities, find_relationships, find_related, cypher, stats",
            required=True,
            enum=["find_entities", "find_relationships", "find_related", "cypher", "stats"]
        ),
        ToolParameter(
            name="entity_name",
            type="string",
            description="Entity name to search for or find relationships of",
            required=False
        ),
        ToolParameter(
            name="entity_type",
            type="string",
            description="Filter by entity type (Person, Company, Concept, Location, Product, Event)",
            required=False
        ),
        ToolParameter(
            name="relationship_type",
            type="string",
            description="Filter by relationship type (e.g., WORKS_AT, KNOWS, LOCATED_IN)",
            required=False
        ),
        ToolParameter(
            name="cypher_query",
            type="string",
            description="Raw Cypher query (for advanced queries)",
            required=False
        ),
        ToolParameter(
            name="cypher_params",
            type="object",
            description="Parameters for Cypher query",
            required=False
        ),
        ToolParameter(
            name="direction",
            type="string",
            description="Relationship direction: outgoing, incoming, or both",
            required=False,
            default="both",
            enum=["outgoing", "incoming", "both"]
        ),
        ToolParameter(
            name="max_depth",
            type="number",
            description="Maximum hops for find_related (default 2)",
            required=False,
            default=2
        ),
        ToolParameter(
            name="agent_id",
            type="string",
            description="Query agent-specific graph (optional)",
            required=False
        ),
        ToolParameter(
            name="limit",
            type="number",
            description="Maximum results to return (default 20)",
            required=False,
            default=20
        ),
    ],
    handler=knowledge_query_handler,
    needs_caller_context=True,
)


# ============== Export all knowledge tools ==============

KNOWLEDGE_TOOLS = [
    KNOWLEDGE_STORE_TOOL,
    KNOWLEDGE_QUERY_TOOL,
]
