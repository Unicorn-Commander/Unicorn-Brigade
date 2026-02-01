"""Knowledge Graph API Routes

Provides endpoints for browsing and querying the FalkorDB knowledge graph.
Used by the frontend KnowledgeGraph page for visualization.
"""

from fastapi import APIRouter, HTTPException, Query, Depends
from typing import Optional, List, Dict, Any, Annotated
from pydantic import BaseModel
import logging

from app.knowledge.graph_manager import KnowledgeGraphManager
from app.auth.middleware import require_api_key, AuthUser

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/knowledge", tags=["knowledge"])

# Singleton instance
_knowledge_manager: Optional[KnowledgeGraphManager] = None


def get_knowledge_manager() -> KnowledgeGraphManager:
    """Get or create the singleton KnowledgeGraphManager instance"""
    global _knowledge_manager
    if _knowledge_manager is None:
        _knowledge_manager = KnowledgeGraphManager()
    return _knowledge_manager


# ============== Response Models ==============

class EntityResponse(BaseModel):
    name: str
    type: str
    created_at: Optional[str] = None
    created_by: Optional[str] = None
    graph: Optional[str] = None


class RelationshipResponse(BaseModel):
    from_entity: Dict[str, str]
    relationship: str
    to_entity: Dict[str, str]
    learned_at: Optional[str] = None
    source_agent: Optional[str] = None
    confidence: Optional[float] = None
    graph: Optional[str] = None


class GraphDataResponse(BaseModel):
    """Response format for graph visualization"""
    nodes: List[Dict[str, Any]]
    links: List[Dict[str, Any]]


class StatsResponse(BaseModel):
    status: str
    enabled: bool
    host: Optional[str] = None
    port: Optional[int] = None
    graphs: Dict[str, Any] = {}
    entity_types: List[str] = []
    relationship_types: List[str] = []
    total_entities: int = 0
    total_relationships: int = 0


# ============== Endpoints ==============

@router.get("/entities", response_model=Dict[str, Any])
async def list_entities(
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
    name_pattern: Optional[str] = Query(None, description="Filter by name (partial match)"),
    limit: int = Query(100, ge=1, le=500, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    user: Annotated[AuthUser, Depends(require_api_key)] = None,
):
    """
    List entities from the knowledge graph with optional filtering.

    Returns paginated list of entities with their properties.
    """
    manager = get_knowledge_manager()

    # Get entities (use limit + offset for pagination simulation)
    result = await manager.query_entities(
        entity_type=entity_type,
        name_pattern=name_pattern,
        limit=limit + offset,  # Fetch extra for offset
        use_global=True
    )

    if not result.get("success"):
        return {
            "success": False,
            "error": result.get("error", "Failed to query entities"),
            "entities": [],
            "total": 0
        }

    entities = result.get("entities", [])

    # Apply offset
    paginated = entities[offset:offset + limit] if offset < len(entities) else []

    return {
        "success": True,
        "entities": paginated,
        "total": len(entities),
        "limit": limit,
        "offset": offset
    }


@router.get("/relationships", response_model=Dict[str, Any])
async def list_relationships(
    entity_name: Optional[str] = Query(None, description="Filter by entity name"),
    relationship_type: Optional[str] = Query(None, description="Filter by relationship type"),
    direction: str = Query("both", description="Direction: outgoing, incoming, or both"),
    limit: int = Query(100, ge=1, le=500, description="Maximum results"),
    user: Annotated[AuthUser, Depends(require_api_key)] = None,
):
    """
    List relationships from the knowledge graph with optional filtering.

    Returns relationships with source and target entity information.
    """
    manager = get_knowledge_manager()

    result = await manager.query_relationships(
        entity_name=entity_name,
        relationship_type=relationship_type,
        direction=direction,
        limit=limit,
        use_global=True
    )

    if not result.get("success"):
        return {
            "success": False,
            "error": result.get("error", "Failed to query relationships"),
            "relationships": [],
            "total": 0
        }

    relationships = result.get("relationships", [])

    # Transform to consistent format
    formatted = []
    for rel in relationships:
        formatted.append({
            "from_entity": rel.get("from", {}),
            "relationship": rel.get("relationship"),
            "to_entity": rel.get("to", {}),
            "learned_at": rel.get("learned_at"),
            "source_agent": rel.get("source_agent"),
            "confidence": rel.get("confidence"),
            "graph": rel.get("graph")
        })

    return {
        "success": True,
        "relationships": formatted,
        "total": len(formatted)
    }


@router.get("/graph", response_model=Dict[str, Any])
async def get_graph_data(
    entity_type: Optional[str] = Query(None, description="Filter nodes by entity type"),
    name_pattern: Optional[str] = Query(None, description="Filter nodes by name pattern"),
    limit: int = Query(200, ge=1, le=1000, description="Maximum nodes"),
    user: Annotated[AuthUser, Depends(require_api_key)] = None,
):
    """
    Get graph data formatted for visualization (nodes and links).

    Returns data compatible with react-force-graph-3d.
    """
    manager = get_knowledge_manager()

    # Get entities (nodes)
    entity_result = await manager.query_entities(
        entity_type=entity_type,
        name_pattern=name_pattern,
        limit=limit,
        use_global=True
    )

    if not entity_result.get("success"):
        return {
            "success": False,
            "error": entity_result.get("error", "Failed to query entities"),
            "nodes": [],
            "links": []
        }

    entities = entity_result.get("entities", [])

    # Create node lookup for filtering relationships
    entity_names = {e["name"] for e in entities}

    # Get relationships (links) - only between entities we have
    rel_result = await manager.query_relationships(
        limit=limit * 2,  # Get more relationships to find connections
        use_global=True
    )

    relationships = rel_result.get("relationships", []) if rel_result.get("success") else []

    # Build nodes with unique IDs
    nodes = []
    node_ids = {}

    for i, entity in enumerate(entities):
        node_id = f"node-{i}"
        node_ids[entity["name"]] = node_id
        nodes.append({
            "id": node_id,
            "name": entity["name"],
            "type": entity["type"],
            "created_at": entity.get("created_at"),
            "created_by": entity.get("created_by"),
            "val": 10,  # Node size
        })

    # Build links (only between existing nodes)
    links = []
    seen_links = set()

    for rel in relationships:
        from_name = rel.get("from", {}).get("name")
        to_name = rel.get("to", {}).get("name")

        if from_name in node_ids and to_name in node_ids:
            link_key = f"{from_name}-{rel.get('relationship')}-{to_name}"
            if link_key not in seen_links:
                seen_links.add(link_key)
                links.append({
                    "id": f"link-{len(links)}",
                    "source": node_ids[from_name],
                    "target": node_ids[to_name],
                    "label": rel.get("relationship"),
                    "confidence": rel.get("confidence"),
                    "learned_at": rel.get("learned_at")
                })

    return {
        "success": True,
        "nodes": nodes,
        "links": links,
        "total_nodes": len(nodes),
        "total_links": len(links)
    }


@router.get("/stats", response_model=Dict[str, Any])
async def get_stats(
    user: Annotated[AuthUser, Depends(require_api_key)] = None,
):
    """
    Get knowledge graph statistics.

    Returns counts, connection status, and metadata about the graph.
    """
    manager = get_knowledge_manager()

    # Get basic stats from manager
    stats = manager.get_stats()

    # Get entity types and relationship types
    entity_types = []
    relationship_types = []
    total_entities = 0
    total_relationships = 0

    if stats.get("status") == "connected":
        # Query for unique entity types
        try:
            type_result = await manager.execute_cypher(
                "MATCH (e:Entity) RETURN DISTINCT e.type AS type",
                use_global=True
            )
            if type_result.get("success"):
                for result in type_result.get("results", []):
                    for record in result.get("result_set", []):
                        if record[0]:
                            entity_types.append(record[0])
        except Exception as e:
            logger.warning(f"Could not get entity types: {e}")

        # Query for unique relationship types
        try:
            rel_type_result = await manager.execute_cypher(
                "MATCH ()-[r]->() RETURN DISTINCT type(r) AS rel_type",
                use_global=True
            )
            if rel_type_result.get("success"):
                for result in rel_type_result.get("results", []):
                    for record in result.get("result_set", []):
                        if record[0]:
                            relationship_types.append(record[0])
        except Exception as e:
            logger.warning(f"Could not get relationship types: {e}")

        # Get counts from graph stats
        graphs = stats.get("graphs", {})
        for graph_name, graph_stats in graphs.items():
            if isinstance(graph_stats, dict):
                total_entities += graph_stats.get("nodes", 0)
                total_relationships += graph_stats.get("relationships", 0)

    return {
        "success": True,
        "status": stats.get("status", "unknown"),
        "enabled": stats.get("enabled", False),
        "host": stats.get("host"),
        "port": stats.get("port"),
        "graphs": stats.get("graphs", {}),
        "entity_types": sorted(set(entity_types)),
        "relationship_types": sorted(set(relationship_types)),
        "total_entities": total_entities,
        "total_relationships": total_relationships
    }


@router.get("/entity/{entity_name}", response_model=Dict[str, Any])
async def get_entity_details(
    entity_name: str,
    user: Annotated[AuthUser, Depends(require_api_key)] = None,
):
    """
    Get detailed information about a specific entity.

    Returns entity properties and all its relationships.
    """
    manager = get_knowledge_manager()

    # Get the entity
    entity_result = await manager.query_entities(
        name_pattern=entity_name,
        limit=1,
        use_global=True
    )

    if not entity_result.get("success") or not entity_result.get("entities"):
        raise HTTPException(status_code=404, detail=f"Entity '{entity_name}' not found")

    entity = entity_result["entities"][0]

    # Get related entities
    related_result = await manager.query_related(
        entity_name=entity_name,
        max_depth=2,
        use_global=True
    )

    # Get direct relationships
    rel_result = await manager.query_relationships(
        entity_name=entity_name,
        direction="both",
        limit=50,
        use_global=True
    )

    return {
        "success": True,
        "entity": entity,
        "relationships": rel_result.get("relationships", []),
        "related_entities": related_result.get("related", [])
    }


@router.get("/search", response_model=Dict[str, Any])
async def search_graph(
    query: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(50, ge=1, le=200, description="Maximum results"),
    user: Annotated[AuthUser, Depends(require_api_key)] = None,
):
    """
    Search the knowledge graph by entity name.

    Returns matching entities and their immediate relationships.
    """
    manager = get_knowledge_manager()

    # Search entities by name pattern
    result = await manager.query_entities(
        name_pattern=query,
        limit=limit,
        use_global=True
    )

    if not result.get("success"):
        return {
            "success": False,
            "error": result.get("error", "Search failed"),
            "entities": [],
            "total": 0
        }

    return {
        "success": True,
        "query": query,
        "entities": result.get("entities", []),
        "total": result.get("count", 0)
    }


# ============== Agentic RAG Endpoints ==============

class NaturalLanguageQueryRequest(BaseModel):
    """Request model for natural language queries"""
    query: str
    limit: int = 50


class RAGQueryRequest(BaseModel):
    """Request model for RAG queries"""
    query: str
    mode: str = "agentic"  # "agentic", "simple", "retrieve"
    user_id: str = "system"
    max_iterations: int = 5
    include_graph: bool = True
    include_memory: bool = True
    model: str = "default"


class StoreEntityRequest(BaseModel):
    """Request model for storing entities"""
    name: str
    entity_type: str
    properties: Optional[Dict[str, Any]] = None
    agent_id: Optional[str] = None


class StoreRelationshipRequest(BaseModel):
    """Request model for storing relationships"""
    from_entity: str
    from_type: str
    relationship: str
    to_entity: str
    to_type: str
    properties: Optional[Dict[str, Any]] = None
    confidence: float = 1.0
    source: Optional[str] = None
    agent_id: Optional[str] = None


class StoreFactRequest(BaseModel):
    """Request model for storing facts (subject-predicate-object)"""
    subject: str
    subject_type: str
    predicate: str
    object: str
    object_type: str
    confidence: float = 1.0
    source: Optional[str] = None
    agent_id: Optional[str] = None


class FindPathRequest(BaseModel):
    """Request model for finding paths between entities"""
    start_entity: str
    end_entity: str
    max_depth: int = 5


@router.post("/query", response_model=Dict[str, Any])
async def natural_language_query(
    request: NaturalLanguageQueryRequest,
    user: Annotated[AuthUser, Depends(require_api_key)] = None,
):
    """
    Execute a natural language query against the knowledge graph.

    This endpoint parses the query to understand intent and entities,
    then queries the graph accordingly.

    Examples:
    - "What companies is John connected to?"
    - "Find all entities related to Project X"
    - "Show me people who work at Acme Corp"
    """
    manager = get_knowledge_manager()

    result = await manager.natural_language_query(
        query=request.query,
        limit=request.limit,
        use_global=True
    )

    return result


@router.post("/rag", response_model=Dict[str, Any])
async def rag_query(
    request: RAGQueryRequest,
    user: Annotated[AuthUser, Depends(require_api_key)] = None,
):
    """
    Execute an Agentic RAG query combining knowledge graph and vector retrieval.

    This endpoint provides comprehensive question answering by:
    1. Parsing the query to understand intent and entities
    2. Querying FalkorDB knowledge graph for structured relationships
    3. Querying Qdrant (via mem0) for semantically similar content
    4. Fusing results to generate an answer with provenance

    Modes:
    - "agentic": Full iterative tool use (thorough, slower)
    - "simple": Direct retrieval and answer generation (faster)
    - "retrieve": Only retrieve context, no answer generation
    """
    from app.agents.agentic_rag import get_agentic_rag

    try:
        rag = get_agentic_rag()

        if request.mode == "agentic":
            response = await rag.query(
                query=request.query,
                user_id=request.user_id,
                model=request.model,
                max_iterations=request.max_iterations
            )
            return {
                "success": True,
                **response.to_dict()
            }

        elif request.mode == "simple":
            result = await rag.simple_query(
                query=request.query,
                user_id=request.user_id
            )
            return result

        elif request.mode == "retrieve":
            context = await rag.retrieve_context(
                query=request.query,
                user_id=request.user_id,
                include_graph=request.include_graph,
                include_memory=request.include_memory
            )
            return {
                "success": True,
                "context": {
                    "entities": context.graph_entities,
                    "relationships": context.graph_relationships,
                    "paths": context.graph_paths,
                    "memories": context.vector_memories,
                    "context_text": context.context_text,
                    "sources": context.sources
                }
            }

        else:
            return {
                "success": False,
                "error": f"Unknown mode: {request.mode}. Use 'agentic', 'simple', or 'retrieve'"
            }

    except Exception as e:
        logger.error(f"RAG query error: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@router.post("/store/entity", response_model=Dict[str, Any])
async def store_entity(
    request: StoreEntityRequest,
    user: Annotated[AuthUser, Depends(require_api_key)] = None,
):
    """
    Store an entity in the knowledge graph.

    Entities are the nodes in the graph (people, companies, locations, etc.)
    """
    manager = get_knowledge_manager()

    result = await manager.store_entity(
        name=request.name,
        entity_type=request.entity_type,
        properties=request.properties,
        agent_id=request.agent_id,
        use_global=True
    )

    return result


@router.post("/store/relationship", response_model=Dict[str, Any])
async def store_relationship(
    request: StoreRelationshipRequest,
    user: Annotated[AuthUser, Depends(require_api_key)] = None,
):
    """
    Store a relationship between two entities.

    Relationships are the edges in the graph (WORKS_AT, KNOWS, LOCATED_IN, etc.)
    """
    manager = get_knowledge_manager()

    result = await manager.store_relationship(
        from_entity=request.from_entity,
        from_type=request.from_type,
        relationship=request.relationship,
        to_entity=request.to_entity,
        to_type=request.to_type,
        properties=request.properties,
        agent_id=request.agent_id,
        use_global=True
    )

    return result


@router.post("/store/fact", response_model=Dict[str, Any])
async def store_fact(
    request: StoreFactRequest,
    user: Annotated[AuthUser, Depends(require_api_key)] = None,
):
    """
    Store a fact as a subject-predicate-object triple.

    This is a convenience endpoint that creates entities and relationships together.
    Example: "John (Person) WORKS_AT Acme Corp (Company)"
    """
    manager = get_knowledge_manager()

    result = await manager.store_fact(
        subject=request.subject,
        subject_type=request.subject_type,
        predicate=request.predicate,
        obj=request.object,
        obj_type=request.object_type,
        confidence=request.confidence,
        source=request.source,
        agent_id=request.agent_id
    )

    return result


@router.post("/path", response_model=Dict[str, Any])
async def find_path(
    request: FindPathRequest,
    user: Annotated[AuthUser, Depends(require_api_key)] = None,
):
    """
    Find the shortest path between two entities.

    Returns the entities and relationships along the path.
    """
    manager = get_knowledge_manager()

    result = await manager.find_shortest_path(
        start_entity=request.start_entity,
        end_entity=request.end_entity,
        max_depth=request.max_depth,
        use_global=True
    )

    return result


@router.get("/context/{entity_name}", response_model=Dict[str, Any])
async def get_entity_context(
    entity_name: str,
    include_relationships: bool = Query(True, description="Include direct relationships"),
    include_related: bool = Query(True, description="Include related entities"),
    max_depth: int = Query(1, ge=1, le=5, description="Max depth for related entities"),
    user: Annotated[AuthUser, Depends(require_api_key)] = None,
):
    """
    Get comprehensive context about an entity for RAG.

    Returns entity details, relationships, and related entities formatted
    for use as context in LLM prompts.
    """
    manager = get_knowledge_manager()

    result = await manager.get_entity_context(
        entity_name=entity_name,
        include_relationships=include_relationships,
        include_related=include_related,
        max_depth=max_depth,
        use_global=True
    )

    return result


def init_knowledge_routes():
    """Initialize knowledge routes - called from main.py"""
    # Force initialization of the manager to check connection
    manager = get_knowledge_manager()
    logger.info(f"Knowledge graph routes initialized. Status: {manager.get_stats().get('status', 'unknown')}")
