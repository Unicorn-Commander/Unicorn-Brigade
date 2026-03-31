"""
Federation Registry Routes

Allows edge nodes (e.g., HA-HQ, remote Raspberry Pis) to register their agents
with Brigade so the orchestrator knows where to find them.

In-memory registry — no database needed. Agents are evicted if their node
misses a heartbeat for more than 60 seconds.

Endpoints:
- POST   /federation/register            — Edge node registers its agents
- GET    /federation/agents              — List all registered remote agents
- DELETE /federation/agents/{agent_id}   — Unregister a single agent
- GET    /federation/health              — Show all nodes and last heartbeat
- POST   /federation/heartbeat           — Edge node heartbeat (keeps agents alive)
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, List, Any, Optional
import logging
import time

logger = logging.getLogger(__name__)
router = APIRouter()

# ---------------------------------------------------------------------------
# In-memory registry
# ---------------------------------------------------------------------------

# agent_id -> full registration record
_agents: Dict[str, Dict[str, Any]] = {}

# node_name -> last heartbeat timestamp
_nodes: Dict[str, float] = {}

# How long before a node's agents are considered stale (seconds)
HEARTBEAT_TTL = 60.0


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class AgentInfo(BaseModel):
    """Minimal description of a remote agent."""
    id: str
    display_name: Optional[str] = None
    rank: Optional[str] = None
    tools: List[str] = []
    scope: Dict[str, Any] = {}


class RegisterRequest(BaseModel):
    """Payload an edge node sends to register its agents."""
    node: str
    endpoint: str  # e.g. "http://192.168.10.138:8200"
    agents: List[AgentInfo]


class HeartbeatRequest(BaseModel):
    """Payload for a heartbeat ping."""
    node: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _prune_stale_nodes() -> List[str]:
    """Remove agents whose node hasn't sent a heartbeat within the TTL.
    Returns list of pruned agent IDs."""
    now = time.time()
    stale_nodes = [
        node for node, ts in _nodes.items()
        if (now - ts) > HEARTBEAT_TTL
    ]
    pruned: List[str] = []
    for node in stale_nodes:
        # Remove all agents belonging to this node
        to_remove = [
            aid for aid, rec in _agents.items()
            if rec.get("node") == node
        ]
        for aid in to_remove:
            del _agents[aid]
            pruned.append(aid)
        del _nodes[node]
        logger.info(f"Federation: pruned stale node '{node}' ({len(to_remove)} agents)")
    return pruned


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/federation/register")
async def register_node(request: RegisterRequest):
    """
    Edge node registers (or re-registers) its agents.

    Overwrites any previous registration for the same agent IDs.
    Also counts as a heartbeat for the node.
    """
    now = time.time()
    _nodes[request.node] = now

    registered = []
    for agent in request.agents:
        _agents[agent.id] = {
            "agent_id": agent.id,
            "display_name": agent.display_name,
            "rank": agent.rank,
            "tools": agent.tools,
            "scope": agent.scope,
            "node": request.node,
            "endpoint": request.endpoint,
            "registered_at": now,
        }
        registered.append(agent.id)

    logger.info(
        f"Federation: node '{request.node}' registered {len(registered)} agents "
        f"at {request.endpoint}"
    )

    return {
        "status": "ok",
        "node": request.node,
        "registered": registered,
        "agent_count": len(registered),
    }


@router.get("/federation/agents")
async def list_agents():
    """List all registered remote agents (prunes stale nodes first)."""
    _prune_stale_nodes()

    agents = []
    for rec in _agents.values():
        agents.append({
            "agent_id": rec["agent_id"],
            "display_name": rec.get("display_name"),
            "rank": rec.get("rank"),
            "tools": rec.get("tools", []),
            "scope": rec.get("scope", {}),
            "node": rec["node"],
            "endpoint": rec["endpoint"],
            "registered_at": rec["registered_at"],
        })

    return {
        "agents": agents,
        "count": len(agents),
    }


@router.delete("/federation/agents/{agent_id}")
async def unregister_agent(agent_id: str):
    """Remove a single agent from the registry."""
    if agent_id not in _agents:
        raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")

    rec = _agents.pop(agent_id)
    logger.info(f"Federation: unregistered agent '{agent_id}' from node '{rec['node']}'")

    # If this was the last agent for the node, clean up the node entry too
    remaining = [a for a in _agents.values() if a["node"] == rec["node"]]
    if not remaining and rec["node"] in _nodes:
        del _nodes[rec["node"]]

    return {"status": "ok", "removed": agent_id}


@router.get("/federation/health")
async def federation_health():
    """Show all nodes and their last heartbeat, plus any stale ones pruned."""
    pruned = _prune_stale_nodes()
    now = time.time()

    nodes = []
    for node, last_hb in _nodes.items():
        agent_count = sum(1 for a in _agents.values() if a["node"] == node)
        nodes.append({
            "node": node,
            "last_heartbeat": last_hb,
            "seconds_ago": round(now - last_hb, 1),
            "agent_count": agent_count,
            "status": "alive",
        })

    return {
        "nodes": nodes,
        "total_nodes": len(nodes),
        "total_agents": len(_agents),
        "pruned": pruned,
        "heartbeat_ttl_seconds": HEARTBEAT_TTL,
    }


@router.post("/federation/heartbeat")
async def heartbeat(request: HeartbeatRequest):
    """
    Edge node pings to stay alive.

    If the node has no registered agents, this is a no-op but still records
    the heartbeat (useful if agents will be registered shortly after).
    """
    now = time.time()
    previous = _nodes.get(request.node)
    _nodes[request.node] = now

    agent_count = sum(1 for a in _agents.values() if a["node"] == request.node)

    return {
        "status": "ok",
        "node": request.node,
        "agent_count": agent_count,
        "previous_heartbeat": previous,
    }
