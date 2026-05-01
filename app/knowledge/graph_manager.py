"""
Knowledge Graph Manager using FalkorDB

Provides a persistent knowledge graph for storing and querying entities,
relationships, and facts learned by agents. Built on FalkorDB (AI-native graph database)
for high-performance GraphRAG and multi-agent knowledge sharing.

Key features:
- Entity management (people, companies, concepts)
- Relationship tracking between entities
- Temporal awareness (when facts were learned)
- Source attribution (which agent learned this)
- Cypher query support
- Multi-tenant graph isolation (per-agent or global)
- Natural language query parsing for Agentic RAG
- Path finding and graph traversal
"""

from typing import Any, Optional, List, Dict, Tuple
from datetime import datetime
import logging
import os
import json
import re

logger = logging.getLogger(__name__)

# FalkorDB client
try:
    from falkordb import FalkorDB
    FALKORDB_AVAILABLE = True
except ImportError:
    FALKORDB_AVAILABLE = False
    logger.warning("falkordb package not installed. Knowledge graph features disabled.")


class KnowledgeGraphManager:
    """Manages knowledge graphs using FalkorDB for relationship tracking and GraphRAG"""

    # Default graph names
    GLOBAL_GRAPH = "brigade_global"
    AGENT_GRAPH_PREFIX = "agent_"

    def __init__(self):
        """Initialize FalkorDB connection"""
        self.host = os.getenv("FALKORDB_HOST", "localhost")
        self.port = int(os.getenv("FALKORDB_PORT", "6380"))
        self.password = os.getenv("FALKORDB_PASSWORD", None)
        self.enabled = os.getenv("FALKORDB_ENABLED", "false").lower() == "true"

        self.db: Optional[FalkorDB] = None
        self._graphs: Dict[str, Any] = {}  # Cache for graph instances

        if self.enabled and FALKORDB_AVAILABLE:
            try:
                self.db = FalkorDB(
                    host=self.host,
                    port=self.port,
                    password=self.password if self.password else None
                )
                logger.info(f"KnowledgeGraphManager connected to FalkorDB at {self.host}:{self.port}")
                # Initialize global graph with schema
                self._ensure_graph_schema(self.GLOBAL_GRAPH)
            except Exception as e:
                logger.error(f"Failed to connect to FalkorDB: {e}")
                self.db = None
        elif not FALKORDB_AVAILABLE:
            logger.warning("FalkorDB client not available. Install with: pip install falkordb")
        else:
            logger.info("KnowledgeGraphManager disabled (FALKORDB_ENABLED=false)")

    def _get_graph(self, graph_name: str):
        """Get or create a graph instance"""
        if not self.db:
            return None

        if graph_name not in self._graphs:
            self._graphs[graph_name] = self.db.select_graph(graph_name)

        return self._graphs[graph_name]

    def _get_agent_graph_name(self, agent_id: str) -> str:
        """Get the graph name for a specific agent"""
        return f"{self.AGENT_GRAPH_PREFIX}{agent_id.replace('-', '_')}"

    def _ensure_graph_schema(self, graph_name: str) -> bool:
        """Ensure the graph has the required indexes for performance"""
        graph = self._get_graph(graph_name)
        if not graph:
            return False

        # FalkorDB does not support 'CREATE INDEX IF NOT EXISTS' (Neo4j syntax) —
        # raises 'Attribute X is already indexed' on duplicate. Each index runs
        # in its own try/except so a missing or pre-existing index never blocks
        # the others, and 'already indexed' is logged at debug, not warn.
        indexes = [
            ("CREATE INDEX FOR (e:Entity) ON (e.name)", "Entity.name"),
            ("CREATE INDEX FOR (e:Entity) ON (e.type)", "Entity.type"),
            ("CREATE INDEX FOR (f:Fact) ON (f.learned_at)", "Fact.learned_at"),
            ("CREATE INDEX FOR (f:Fact) ON (f.source_agent)", "Fact.source_agent"),
        ]
        for ddl, label in indexes:
            try:
                graph.query(ddl)
            except Exception as e:
                msg = str(e).lower()
                if "already indexed" in msg:
                    logger.debug(f"Index {label} already exists in {graph_name}")
                else:
                    logger.warning(f"Could not create index {label} in {graph_name}: {e}")
        logger.info(f"Graph schema ensured for: {graph_name}")
        return True

    async def store_entity(
        self,
        name: str,
        entity_type: str,
        properties: Optional[Dict[str, Any]] = None,
        agent_id: Optional[str] = None,
        use_global: bool = True
    ) -> Dict[str, Any]:
        """
        Store an entity in the knowledge graph.

        Args:
            name: Entity name (e.g., "John Doe", "Acme Corp")
            entity_type: Type of entity (Person, Company, Concept, Location, etc.)
            properties: Additional properties for the entity
            agent_id: Optional agent ID for agent-specific graph
            use_global: Whether to also store in global graph (default True)

        Returns:
            Dict with success status and entity info
        """
        if not self.db:
            return {"success": False, "error": "FalkorDB not connected"}

        try:
            # Prepare properties
            props = properties or {}
            props["name"] = name
            props["type"] = entity_type
            props["created_at"] = datetime.utcnow().isoformat()
            if agent_id:
                props["created_by"] = agent_id

            # Build property string for Cypher
            prop_str = ", ".join([f"{k}: ${k}" for k in props.keys()])

            # MERGE to avoid duplicates (match on name and type)
            query = f"""
                MERGE (e:Entity:{entity_type} {{name: $name, type: $type}})
                ON CREATE SET {", ".join([f"e.{k} = ${k}" for k in props.keys()])}
                ON MATCH SET e.updated_at = $updated_at
                RETURN e
            """
            props["updated_at"] = datetime.utcnow().isoformat()

            results = []

            # Store in agent-specific graph if agent_id provided
            if agent_id:
                agent_graph_name = self._get_agent_graph_name(agent_id)
                self._ensure_graph_schema(agent_graph_name)
                graph = self._get_graph(agent_graph_name)
                if graph:
                    result = graph.query(query, props)
                    results.append({"graph": agent_graph_name, "result": "stored"})

            # Store in global graph
            if use_global:
                global_graph = self._get_graph(self.GLOBAL_GRAPH)
                if global_graph:
                    result = global_graph.query(query, props)
                    results.append({"graph": self.GLOBAL_GRAPH, "result": "stored"})

            return {
                "success": True,
                "entity": {"name": name, "type": entity_type, "properties": properties},
                "graphs": results
            }

        except Exception as e:
            logger.error(f"Error storing entity: {e}")
            return {"success": False, "error": str(e)}

    async def store_relationship(
        self,
        from_entity: str,
        from_type: str,
        relationship: str,
        to_entity: str,
        to_type: str,
        properties: Optional[Dict[str, Any]] = None,
        agent_id: Optional[str] = None,
        use_global: bool = True
    ) -> Dict[str, Any]:
        """
        Store a relationship between two entities.

        Args:
            from_entity: Source entity name
            from_type: Source entity type
            relationship: Relationship type (e.g., WORKS_AT, KNOWS, LOCATED_IN)
            to_entity: Target entity name
            to_type: Target entity type
            properties: Additional relationship properties
            agent_id: Optional agent ID for agent-specific graph
            use_global: Whether to also store in global graph

        Returns:
            Dict with success status and relationship info
        """
        if not self.db:
            return {"success": False, "error": "FalkorDB not connected"}

        try:
            # Prepare properties
            props = properties or {}
            props["learned_at"] = datetime.utcnow().isoformat()
            if agent_id:
                props["source_agent"] = agent_id

            # Build property string
            rel_props = ", ".join([f"{k}: ${k}" for k in props.keys()])
            rel_props_str = f" {{{rel_props}}}" if rel_props else ""

            # Normalize relationship name
            rel_type = relationship.upper().replace(" ", "_")

            query = f"""
                MERGE (a:Entity:{from_type} {{name: $from_name, type: $from_type}})
                MERGE (b:Entity:{to_type} {{name: $to_name, type: $to_type}})
                MERGE (a)-[r:{rel_type}]->(b)
                SET r.learned_at = $learned_at
                {"SET r.source_agent = $source_agent" if agent_id else ""}
                RETURN a.name, type(r), b.name
            """

            params = {
                "from_name": from_entity,
                "from_type": from_type,
                "to_name": to_entity,
                "to_type": to_type,
                **props
            }

            results = []

            # Store in agent-specific graph
            if agent_id:
                agent_graph_name = self._get_agent_graph_name(agent_id)
                self._ensure_graph_schema(agent_graph_name)
                graph = self._get_graph(agent_graph_name)
                if graph:
                    graph.query(query, params)
                    results.append({"graph": agent_graph_name, "result": "stored"})

            # Store in global graph
            if use_global:
                global_graph = self._get_graph(self.GLOBAL_GRAPH)
                if global_graph:
                    global_graph.query(query, params)
                    results.append({"graph": self.GLOBAL_GRAPH, "result": "stored"})

            return {
                "success": True,
                "relationship": {
                    "from": {"name": from_entity, "type": from_type},
                    "relationship": rel_type,
                    "to": {"name": to_entity, "type": to_type},
                    "properties": props
                },
                "graphs": results
            }

        except Exception as e:
            logger.error(f"Error storing relationship: {e}")
            return {"success": False, "error": str(e)}

    async def store_fact(
        self,
        subject: str,
        subject_type: str,
        predicate: str,
        obj: str,
        obj_type: str,
        confidence: float = 1.0,
        source: Optional[str] = None,
        agent_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Store a fact as a triple (subject-predicate-object) with metadata.

        This is a convenience method that creates entities and relationship together.

        Args:
            subject: Subject entity name
            subject_type: Subject entity type
            predicate: Relationship/predicate
            obj: Object entity name
            obj_type: Object entity type
            confidence: Confidence score (0-1)
            source: Source of the information
            agent_id: Which agent learned this fact

        Returns:
            Dict with success status
        """
        properties = {
            "confidence": confidence,
            "source": source or "agent_conversation"
        }

        return await self.store_relationship(
            from_entity=subject,
            from_type=subject_type,
            relationship=predicate,
            to_entity=obj,
            to_type=obj_type,
            properties=properties,
            agent_id=agent_id
        )

    async def query_entities(
        self,
        entity_type: Optional[str] = None,
        name_pattern: Optional[str] = None,
        agent_id: Optional[str] = None,
        use_global: bool = True,
        limit: int = 50
    ) -> Dict[str, Any]:
        """
        Query entities from the knowledge graph.

        Args:
            entity_type: Filter by entity type
            name_pattern: Filter by name (supports partial match)
            agent_id: Query agent-specific graph
            use_global: Query global graph
            limit: Maximum results

        Returns:
            Dict with entities found
        """
        if not self.db:
            return {"success": False, "error": "FalkorDB not connected", "entities": []}

        try:
            # Build query
            where_clauses = []
            params = {"limit": limit}

            if entity_type:
                where_clauses.append("e.type = $entity_type")
                params["entity_type"] = entity_type

            if name_pattern:
                where_clauses.append("e.name CONTAINS $name_pattern")
                params["name_pattern"] = name_pattern

            where_str = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

            query = f"""
                MATCH (e:Entity)
                {where_str}
                RETURN e.name AS name, e.type AS type, e.created_at AS created_at,
                       e.created_by AS created_by
                LIMIT $limit
            """

            all_entities = []

            # Query agent-specific graph
            if agent_id:
                graph = self._get_graph(self._get_agent_graph_name(agent_id))
                if graph:
                    result = graph.query(query, params)
                    for record in result.result_set:
                        all_entities.append({
                            "name": record[0],
                            "type": record[1],
                            "created_at": record[2],
                            "created_by": record[3],
                            "graph": "agent"
                        })

            # Query global graph
            if use_global:
                graph = self._get_graph(self.GLOBAL_GRAPH)
                if graph:
                    result = graph.query(query, params)
                    for record in result.result_set:
                        all_entities.append({
                            "name": record[0],
                            "type": record[1],
                            "created_at": record[2],
                            "created_by": record[3],
                            "graph": "global"
                        })

            # Deduplicate by name
            seen = set()
            unique_entities = []
            for entity in all_entities:
                key = (entity["name"], entity["type"])
                if key not in seen:
                    seen.add(key)
                    unique_entities.append(entity)

            return {
                "success": True,
                "entities": unique_entities,
                "count": len(unique_entities)
            }

        except Exception as e:
            logger.error(f"Error querying entities: {e}")
            return {"success": False, "error": str(e), "entities": []}

    async def query_relationships(
        self,
        entity_name: Optional[str] = None,
        relationship_type: Optional[str] = None,
        direction: str = "both",
        agent_id: Optional[str] = None,
        use_global: bool = True,
        limit: int = 50
    ) -> Dict[str, Any]:
        """
        Query relationships from the knowledge graph.

        Args:
            entity_name: Entity to find relationships for
            relationship_type: Filter by relationship type
            direction: "outgoing", "incoming", or "both"
            agent_id: Query agent-specific graph
            use_global: Query global graph
            limit: Maximum results

        Returns:
            Dict with relationships found
        """
        if not self.db:
            return {"success": False, "error": "FalkorDB not connected", "relationships": []}

        try:
            params = {"limit": limit}

            # Build match pattern based on direction
            if entity_name:
                params["entity_name"] = entity_name
                if direction == "outgoing":
                    match = "MATCH (a:Entity {name: $entity_name})-[r]->(b:Entity)"
                elif direction == "incoming":
                    match = "MATCH (a:Entity)-[r]->(b:Entity {name: $entity_name})"
                else:
                    match = "MATCH (a:Entity)-[r]-(b:Entity) WHERE a.name = $entity_name"
            else:
                match = "MATCH (a:Entity)-[r]->(b:Entity)"

            # Add relationship type filter
            if relationship_type:
                rel_type = relationship_type.upper().replace(" ", "_")
                # Need to modify match for specific relationship type
                if entity_name:
                    if direction == "outgoing":
                        match = f"MATCH (a:Entity {{name: $entity_name}})-[r:{rel_type}]->(b:Entity)"
                    elif direction == "incoming":
                        match = f"MATCH (a:Entity)-[r:{rel_type}]->(b:Entity {{name: $entity_name}})"
                    else:
                        match = f"MATCH (a:Entity)-[r:{rel_type}]-(b:Entity) WHERE a.name = $entity_name"
                else:
                    match = f"MATCH (a:Entity)-[r:{rel_type}]->(b:Entity)"

            query = f"""
                {match}
                RETURN a.name AS from_name, a.type AS from_type,
                       type(r) AS relationship, r.learned_at AS learned_at,
                       r.source_agent AS source_agent, r.confidence AS confidence,
                       b.name AS to_name, b.type AS to_type
                LIMIT $limit
            """

            all_relationships = []

            # Query agent-specific graph
            if agent_id:
                graph = self._get_graph(self._get_agent_graph_name(agent_id))
                if graph:
                    result = graph.query(query, params)
                    for record in result.result_set:
                        all_relationships.append({
                            "from": {"name": record[0], "type": record[1]},
                            "relationship": record[2],
                            "learned_at": record[3],
                            "source_agent": record[4],
                            "confidence": record[5],
                            "to": {"name": record[6], "type": record[7]},
                            "graph": "agent"
                        })

            # Query global graph
            if use_global:
                graph = self._get_graph(self.GLOBAL_GRAPH)
                if graph:
                    result = graph.query(query, params)
                    for record in result.result_set:
                        all_relationships.append({
                            "from": {"name": record[0], "type": record[1]},
                            "relationship": record[2],
                            "learned_at": record[3],
                            "source_agent": record[4],
                            "confidence": record[5],
                            "to": {"name": record[6], "type": record[7]},
                            "graph": "global"
                        })

            return {
                "success": True,
                "relationships": all_relationships,
                "count": len(all_relationships)
            }

        except Exception as e:
            logger.error(f"Error querying relationships: {e}")
            return {"success": False, "error": str(e), "relationships": []}

    async def query_related(
        self,
        entity_name: str,
        max_depth: int = 2,
        agent_id: Optional[str] = None,
        use_global: bool = True
    ) -> Dict[str, Any]:
        """
        Find all entities related to a given entity within N hops.

        Args:
            entity_name: Starting entity
            max_depth: Maximum relationship hops (default 2)
            agent_id: Query agent-specific graph
            use_global: Query global graph

        Returns:
            Dict with related entities and their paths
        """
        if not self.db:
            return {"success": False, "error": "FalkorDB not connected", "related": []}

        try:
            query = f"""
                MATCH path = (start:Entity {{name: $entity_name}})-[*1..{max_depth}]-(related:Entity)
                WHERE start <> related
                RETURN DISTINCT related.name AS name, related.type AS type,
                       length(path) AS distance
                ORDER BY distance
                LIMIT 50
            """
            params = {"entity_name": entity_name}

            all_related = []

            # Query agent-specific graph
            if agent_id:
                graph = self._get_graph(self._get_agent_graph_name(agent_id))
                if graph:
                    result = graph.query(query, params)
                    for record in result.result_set:
                        all_related.append({
                            "name": record[0],
                            "type": record[1],
                            "distance": record[2],
                            "graph": "agent"
                        })

            # Query global graph
            if use_global:
                graph = self._get_graph(self.GLOBAL_GRAPH)
                if graph:
                    result = graph.query(query, params)
                    for record in result.result_set:
                        all_related.append({
                            "name": record[0],
                            "type": record[1],
                            "distance": record[2],
                            "graph": "global"
                        })

            # Deduplicate
            seen = set()
            unique_related = []
            for item in all_related:
                key = (item["name"], item["type"])
                if key not in seen:
                    seen.add(key)
                    unique_related.append(item)

            # Sort by distance
            unique_related.sort(key=lambda x: x["distance"])

            return {
                "success": True,
                "entity": entity_name,
                "related": unique_related,
                "count": len(unique_related)
            }

        except Exception as e:
            logger.error(f"Error finding related entities: {e}")
            return {"success": False, "error": str(e), "related": []}

    async def execute_cypher(
        self,
        query: str,
        params: Optional[Dict[str, Any]] = None,
        agent_id: Optional[str] = None,
        use_global: bool = True
    ) -> Dict[str, Any]:
        """
        Execute a raw Cypher query.

        Args:
            query: Cypher query string
            params: Query parameters
            agent_id: Execute on agent-specific graph
            use_global: Execute on global graph

        Returns:
            Dict with query results
        """
        if not self.db:
            return {"success": False, "error": "FalkorDB not connected"}

        try:
            results = []

            # Execute on agent graph
            if agent_id:
                graph = self._get_graph(self._get_agent_graph_name(agent_id))
                if graph:
                    result = graph.query(query, params or {})
                    results.append({
                        "graph": "agent",
                        "result_set": [list(record) for record in result.result_set],
                        "stats": {
                            "nodes_created": result.nodes_created,
                            "relationships_created": result.relationships_created,
                            "nodes_deleted": result.nodes_deleted,
                            "relationships_deleted": result.relationships_deleted
                        }
                    })

            # Execute on global graph
            if use_global:
                graph = self._get_graph(self.GLOBAL_GRAPH)
                if graph:
                    result = graph.query(query, params or {})
                    results.append({
                        "graph": "global",
                        "result_set": [list(record) for record in result.result_set],
                        "stats": {
                            "nodes_created": result.nodes_created,
                            "relationships_created": result.relationships_created,
                            "nodes_deleted": result.nodes_deleted,
                            "relationships_deleted": result.relationships_deleted
                        }
                    })

            return {
                "success": True,
                "results": results
            }

        except Exception as e:
            logger.error(f"Error executing Cypher query: {e}")
            return {"success": False, "error": str(e)}

    async def delete_entity(
        self,
        name: str,
        entity_type: Optional[str] = None,
        agent_id: Optional[str] = None,
        use_global: bool = True
    ) -> Dict[str, Any]:
        """
        Delete an entity and its relationships.

        Args:
            name: Entity name
            entity_type: Optional type filter
            agent_id: Delete from agent-specific graph
            use_global: Delete from global graph

        Returns:
            Dict with deletion status
        """
        if not self.db:
            return {"success": False, "error": "FalkorDB not connected"}

        try:
            if entity_type:
                query = """
                    MATCH (e:Entity {name: $name, type: $type})
                    DETACH DELETE e
                """
                params = {"name": name, "type": entity_type}
            else:
                query = """
                    MATCH (e:Entity {name: $name})
                    DETACH DELETE e
                """
                params = {"name": name}

            deleted_from = []

            if agent_id:
                graph = self._get_graph(self._get_agent_graph_name(agent_id))
                if graph:
                    graph.query(query, params)
                    deleted_from.append("agent")

            if use_global:
                graph = self._get_graph(self.GLOBAL_GRAPH)
                if graph:
                    graph.query(query, params)
                    deleted_from.append("global")

            return {
                "success": True,
                "entity": name,
                "deleted_from": deleted_from
            }

        except Exception as e:
            logger.error(f"Error deleting entity: {e}")
            return {"success": False, "error": str(e)}

    def get_stats(self) -> Dict[str, Any]:
        """Get knowledge graph statistics"""
        if not self.db:
            return {"status": "disconnected", "enabled": self.enabled}

        try:
            stats = {
                "status": "connected",
                "enabled": self.enabled,
                "host": self.host,
                "port": self.port,
                "graphs": {}
            }

            # Get stats for global graph
            global_graph = self._get_graph(self.GLOBAL_GRAPH)
            if global_graph:
                try:
                    # Count nodes
                    node_result = global_graph.query("MATCH (n) RETURN count(n) as count")
                    node_count = node_result.result_set[0][0] if node_result.result_set else 0

                    # Count relationships
                    rel_result = global_graph.query("MATCH ()-[r]->() RETURN count(r) as count")
                    rel_count = rel_result.result_set[0][0] if rel_result.result_set else 0

                    stats["graphs"][self.GLOBAL_GRAPH] = {
                        "nodes": node_count,
                        "relationships": rel_count
                    }
                except Exception as e:
                    stats["graphs"][self.GLOBAL_GRAPH] = {"error": str(e)}

            return stats

        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {"status": "error", "error": str(e)}

    # ==================== Agentic RAG Methods ====================

    def parse_natural_language_query(self, query: str) -> Dict[str, Any]:
        """
        Parse a natural language query to extract entities, relationships, and intent.

        This is a rule-based parser. For production, integrate with an LLM for
        more sophisticated understanding.

        Args:
            query: Natural language query (e.g., "What companies is John connected to?")

        Returns:
            Dict with parsed components:
            - intent: "find_connections", "find_entity", "find_path", "find_related"
            - entities: List of entity names mentioned
            - entity_types: List of entity types mentioned
            - relationship_types: List of relationship types mentioned
            - direction: "outgoing", "incoming", or "both"
            - max_depth: How deep to search
        """
        query_lower = query.lower()

        result = {
            "intent": "find_related",  # Default
            "entities": [],
            "entity_types": [],
            "relationship_types": [],
            "direction": "both",
            "max_depth": 2,
            "raw_query": query
        }

        # Detect entity types
        type_patterns = {
            "Person": [r'\bperson\b', r'\bpeople\b', r'\bsomeone\b', r'\bwho\b'],
            "Company": [r'\bcompan(?:y|ies)\b', r'\borganization\b', r'\bbusiness(?:es)?\b', r'\bcorporation\b'],
            "Location": [r'\blocation\b', r'\bplace\b', r'\bcity\b', r'\bcountry\b', r'\bwhere\b'],
            "Product": [r'\bproduct\b', r'\bitem\b', r'\bservice\b'],
            "Event": [r'\bevent\b', r'\bmeeting\b', r'\bconference\b'],
            "Concept": [r'\bconcept\b', r'\bidea\b', r'\btopic\b', r'\bsubject\b']
        }

        for entity_type, patterns in type_patterns.items():
            for pattern in patterns:
                if re.search(pattern, query_lower):
                    if entity_type not in result["entity_types"]:
                        result["entity_types"].append(entity_type)

        # Detect relationship types
        relationship_patterns = {
            "WORKS_AT": [r'\bwork(?:s|ed|ing)?\s+(?:at|for)\b', r'\bemploy(?:ed|ee)\b'],
            "KNOWS": [r'\bknow(?:s|n)?\b', r'\bacquaint(?:ed|ance)\b', r'\bconnect(?:ed|ion)\b'],
            "LOCATED_IN": [r'\blocated\s+(?:in|at)\b', r'\bbased\s+(?:in|at)\b', r'\bheadquarter(?:ed|s)?\b'],
            "OWNS": [r'\bown(?:s|ed)?\b', r'\bpossess(?:es|ed)?\b'],
            "PART_OF": [r'\bpart\s+of\b', r'\bbelong(?:s|ed)?\s+to\b', r'\bmember\s+of\b'],
            "FOUNDED": [r'\bfound(?:ed|er)\b', r'\bstart(?:ed)?\b', r'\bcreat(?:ed|or)\b'],
            "INVESTED_IN": [r'\binvest(?:ed|or|s)?\b', r'\bfund(?:ed|ing)?\b'],
            "PARTNERED_WITH": [r'\bpartner(?:ed|ship)?\b', r'\bcollaborat(?:ed|ion)\b'],
            "REPORTS_TO": [r'\breport(?:s|ed)?\s+to\b', r'\bmanag(?:ed|er)?\s+by\b']
        }

        for rel_type, patterns in relationship_patterns.items():
            for pattern in patterns:
                if re.search(pattern, query_lower):
                    if rel_type not in result["relationship_types"]:
                        result["relationship_types"].append(rel_type)

        # Detect intent
        if re.search(r'\bpath\b|\broute\b|\bhow.*connected\b|\brelationship.*between\b', query_lower):
            result["intent"] = "find_path"
        elif re.search(r'\bconnect(?:ed|ion)?\b|\brelated\b|\blink(?:ed)?\b', query_lower):
            result["intent"] = "find_connections"
        elif re.search(r'\bfind\b|\bsearch\b|\blook(?:ing)?\s+for\b|\bwhat\s+is\b', query_lower):
            result["intent"] = "find_entity"
        elif re.search(r'\ball\b.*\brelated\b|\beverything\b.*\bconnected\b', query_lower):
            result["intent"] = "find_related"
            result["max_depth"] = 3

        # Detect direction
        if re.search(r'\bfrom\b|\boutgoing\b|\bto\s+whom\b', query_lower):
            result["direction"] = "outgoing"
        elif re.search(r'\bto\b|\bincoming\b|\bwho\s+.*\s+to\b', query_lower):
            result["direction"] = "incoming"

        # Extract quoted entities
        quoted = re.findall(r'"([^"]+)"', query)
        result["entities"].extend(quoted)

        # Extract capitalized words as potential entities (basic heuristic)
        # Skip common words and words at sentence start
        skip_words = {'what', 'who', 'where', 'when', 'how', 'is', 'are', 'the', 'a', 'an',
                      'find', 'show', 'list', 'get', 'all', 'connected', 'related', 'to', 'from'}
        words = query.split()
        for i, word in enumerate(words):
            clean_word = re.sub(r'[^\w]', '', word)
            if (clean_word and clean_word[0].isupper() and
                clean_word.lower() not in skip_words and
                i > 0):  # Skip first word
                if clean_word not in result["entities"]:
                    result["entities"].append(clean_word)

        return result

    async def natural_language_query(
        self,
        query: str,
        agent_id: Optional[str] = None,
        use_global: bool = True,
        limit: int = 50
    ) -> Dict[str, Any]:
        """
        Execute a natural language query against the knowledge graph.

        Args:
            query: Natural language query
            agent_id: Optional agent-specific graph
            use_global: Whether to query global graph
            limit: Maximum results

        Returns:
            Dict with query results and provenance
        """
        if not self.db:
            return {"success": False, "error": "FalkorDB not connected", "results": []}

        try:
            # Parse the query
            parsed = self.parse_natural_language_query(query)
            logger.info(f"Parsed NL query: {parsed}")

            results = {
                "success": True,
                "query": query,
                "parsed": parsed,
                "entities": [],
                "relationships": [],
                "paths": []
            }

            # Execute based on intent
            if parsed["intent"] == "find_entity":
                # Search for entities matching the query
                if parsed["entities"]:
                    for entity_name in parsed["entities"]:
                        entity_result = await self.query_entities(
                            name_pattern=entity_name,
                            entity_type=parsed["entity_types"][0] if parsed["entity_types"] else None,
                            agent_id=agent_id,
                            use_global=use_global,
                            limit=limit
                        )
                        if entity_result.get("success"):
                            results["entities"].extend(entity_result.get("entities", []))
                elif parsed["entity_types"]:
                    for entity_type in parsed["entity_types"]:
                        entity_result = await self.query_entities(
                            entity_type=entity_type,
                            agent_id=agent_id,
                            use_global=use_global,
                            limit=limit
                        )
                        if entity_result.get("success"):
                            results["entities"].extend(entity_result.get("entities", []))

            elif parsed["intent"] == "find_connections":
                # Find connections for entities
                for entity_name in parsed["entities"]:
                    rel_result = await self.query_relationships(
                        entity_name=entity_name,
                        relationship_type=parsed["relationship_types"][0] if parsed["relationship_types"] else None,
                        direction=parsed["direction"],
                        agent_id=agent_id,
                        use_global=use_global,
                        limit=limit
                    )
                    if rel_result.get("success"):
                        results["relationships"].extend(rel_result.get("relationships", []))

            elif parsed["intent"] == "find_path":
                # Find paths between entities
                if len(parsed["entities"]) >= 2:
                    path_result = await self.find_shortest_path(
                        start_entity=parsed["entities"][0],
                        end_entity=parsed["entities"][1],
                        agent_id=agent_id,
                        use_global=use_global
                    )
                    if path_result.get("success"):
                        results["paths"].append(path_result)

            elif parsed["intent"] == "find_related":
                # Find all related entities
                for entity_name in parsed["entities"]:
                    related_result = await self.query_related(
                        entity_name=entity_name,
                        max_depth=parsed["max_depth"],
                        agent_id=agent_id,
                        use_global=use_global
                    )
                    if related_result.get("success"):
                        # Add related entities
                        for rel in related_result.get("related", []):
                            if rel not in results["entities"]:
                                results["entities"].append(rel)

            # Deduplicate results
            seen_entities = set()
            unique_entities = []
            for entity in results["entities"]:
                key = (entity.get("name"), entity.get("type"))
                if key not in seen_entities:
                    seen_entities.add(key)
                    unique_entities.append(entity)
            results["entities"] = unique_entities

            return results

        except Exception as e:
            logger.error(f"Error in natural language query: {e}")
            return {"success": False, "error": str(e), "results": []}

    async def find_shortest_path(
        self,
        start_entity: str,
        end_entity: str,
        max_depth: int = 5,
        agent_id: Optional[str] = None,
        use_global: bool = True
    ) -> Dict[str, Any]:
        """
        Find the shortest path between two entities.

        Args:
            start_entity: Starting entity name
            end_entity: Target entity name
            max_depth: Maximum path length
            agent_id: Optional agent-specific graph
            use_global: Whether to query global graph

        Returns:
            Dict with path information
        """
        if not self.db:
            return {"success": False, "error": "FalkorDB not connected"}

        try:
            query = f"""
                MATCH path = shortestPath(
                    (start:Entity {{name: $start_name}})-[*1..{max_depth}]-(end:Entity {{name: $end_name}})
                )
                RETURN
                    [n IN nodes(path) | {{name: n.name, type: n.type}}] AS nodes,
                    [r IN relationships(path) | type(r)] AS relationships,
                    length(path) AS path_length
                LIMIT 1
            """
            params = {"start_name": start_entity, "end_name": end_entity}

            paths = []

            # Query agent-specific graph
            if agent_id:
                graph = self._get_graph(self._get_agent_graph_name(agent_id))
                if graph:
                    result = graph.query(query, params)
                    for record in result.result_set:
                        paths.append({
                            "nodes": record[0],
                            "relationships": record[1],
                            "length": record[2],
                            "graph": "agent"
                        })

            # Query global graph
            if use_global:
                graph = self._get_graph(self.GLOBAL_GRAPH)
                if graph:
                    result = graph.query(query, params)
                    for record in result.result_set:
                        paths.append({
                            "nodes": record[0],
                            "relationships": record[1],
                            "length": record[2],
                            "graph": "global"
                        })

            if paths:
                # Return shortest path
                shortest = min(paths, key=lambda x: x["length"])
                return {
                    "success": True,
                    "start": start_entity,
                    "end": end_entity,
                    "path": shortest,
                    "all_paths": paths
                }
            else:
                return {
                    "success": True,
                    "start": start_entity,
                    "end": end_entity,
                    "path": None,
                    "message": "No path found between entities"
                }

        except Exception as e:
            logger.error(f"Error finding path: {e}")
            return {"success": False, "error": str(e)}

    async def get_entity_context(
        self,
        entity_name: str,
        include_relationships: bool = True,
        include_related: bool = True,
        max_depth: int = 1,
        agent_id: Optional[str] = None,
        use_global: bool = True
    ) -> Dict[str, Any]:
        """
        Get comprehensive context about an entity for RAG.

        Returns entity details, direct relationships, and optionally related entities.
        Formatted for use as context in LLM prompts.

        Args:
            entity_name: Name of the entity
            include_relationships: Include direct relationships
            include_related: Include related entities
            max_depth: How deep to look for related entities
            agent_id: Optional agent-specific graph
            use_global: Whether to query global graph

        Returns:
            Dict with entity context
        """
        if not self.db:
            return {"success": False, "error": "FalkorDB not connected"}

        try:
            context = {
                "success": True,
                "entity": None,
                "relationships": [],
                "related_entities": [],
                "context_text": ""
            }

            # Get entity
            entity_result = await self.query_entities(
                name_pattern=entity_name,
                agent_id=agent_id,
                use_global=use_global,
                limit=1
            )

            if entity_result.get("success") and entity_result.get("entities"):
                context["entity"] = entity_result["entities"][0]
            else:
                return {
                    "success": False,
                    "error": f"Entity '{entity_name}' not found"
                }

            # Get relationships
            if include_relationships:
                rel_result = await self.query_relationships(
                    entity_name=entity_name,
                    direction="both",
                    agent_id=agent_id,
                    use_global=use_global,
                    limit=50
                )
                if rel_result.get("success"):
                    context["relationships"] = rel_result.get("relationships", [])

            # Get related entities
            if include_related:
                related_result = await self.query_related(
                    entity_name=entity_name,
                    max_depth=max_depth,
                    agent_id=agent_id,
                    use_global=use_global
                )
                if related_result.get("success"):
                    context["related_entities"] = related_result.get("related", [])

            # Generate context text for LLM
            text_parts = []
            entity = context["entity"]
            text_parts.append(f"Entity: {entity['name']} (Type: {entity['type']})")

            if context["relationships"]:
                text_parts.append("\nRelationships:")
                for rel in context["relationships"][:20]:  # Limit for context window
                    from_name = rel.get("from", {}).get("name", "?")
                    to_name = rel.get("to", {}).get("name", "?")
                    rel_type = rel.get("relationship", "?")
                    text_parts.append(f"  - {from_name} --[{rel_type}]--> {to_name}")

            if context["related_entities"]:
                text_parts.append("\nRelated Entities:")
                for related in context["related_entities"][:10]:
                    text_parts.append(f"  - {related['name']} ({related['type']}, distance: {related.get('distance', '?')})")

            context["context_text"] = "\n".join(text_parts)

            return context

        except Exception as e:
            logger.error(f"Error getting entity context: {e}")
            return {"success": False, "error": str(e)}

    async def semantic_search_entities(
        self,
        search_terms: List[str],
        entity_types: Optional[List[str]] = None,
        agent_id: Optional[str] = None,
        use_global: bool = True,
        limit: int = 20
    ) -> Dict[str, Any]:
        """
        Search for entities that match any of the search terms.

        This provides fuzzy matching for RAG retrieval.

        Args:
            search_terms: List of terms to search for
            entity_types: Optional filter by entity types
            agent_id: Optional agent-specific graph
            use_global: Whether to query global graph
            limit: Maximum results

        Returns:
            Dict with matching entities
        """
        if not self.db:
            return {"success": False, "error": "FalkorDB not connected", "entities": []}

        try:
            all_entities = []

            for term in search_terms:
                result = await self.query_entities(
                    name_pattern=term,
                    entity_type=entity_types[0] if entity_types else None,
                    agent_id=agent_id,
                    use_global=use_global,
                    limit=limit
                )
                if result.get("success"):
                    all_entities.extend(result.get("entities", []))

            # Deduplicate by name
            seen = set()
            unique = []
            for entity in all_entities:
                key = (entity.get("name"), entity.get("type"))
                if key not in seen:
                    seen.add(key)
                    unique.append(entity)

            return {
                "success": True,
                "search_terms": search_terms,
                "entities": unique[:limit],
                "count": len(unique)
            }

        except Exception as e:
            logger.error(f"Error in semantic search: {e}")
            return {"success": False, "error": str(e), "entities": []}
