"""
In-memory agent store with JSON seed loading and persistence.
Provides full CRUD for agent management.
"""
import json
import logging
import os
import uuid
from copy import deepcopy
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class AgentStore:
    """In-memory agent store backed by JSON seed data with optional persistence."""

    def __init__(self, seed_path: str = None):
        self._agents: Dict[str, Dict[str, Any]] = {}
        seed_path = seed_path or os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "data", "seed_agents.json"
        )
        self._seed_path = seed_path
        self._persistence_path = os.path.join(
            os.path.dirname(seed_path), "agents_state.json"
        )
        self._load()

    def _load(self):
        """Load agents from persistence file, falling back to seed data."""
        # Try persistence file first (contains user modifications)
        if os.path.exists(self._persistence_path):
            try:
                with open(self._persistence_path, "r") as f:
                    agents_list = json.load(f)
                for agent in agents_list:
                    self._agents[agent["id"]] = agent
                logger.info(f"Loaded {len(self._agents)} agents from persistence")
                return
            except Exception as e:
                logger.warning(f"Failed to load persistence file: {e}")

        # Fall back to seed data
        if os.path.exists(self._seed_path):
            try:
                with open(self._seed_path, "r") as f:
                    agents_list = json.load(f)
                for agent in agents_list:
                    self._agents[agent["id"]] = agent
                logger.info(f"Loaded {len(self._agents)} agents from seed data")
            except Exception as e:
                logger.error(f"Failed to load seed data: {e}")

    def _persist(self):
        """Save current state to JSON file."""
        try:
            agents_list = list(self._agents.values())
            os.makedirs(os.path.dirname(self._persistence_path), exist_ok=True)
            with open(self._persistence_path, "w") as f:
                json.dump(agents_list, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to persist agent store: {e}")

    def list_all(self) -> List[Dict[str, Any]]:
        """Return all agents."""
        return [deepcopy(a) for a in self._agents.values()]

    def get(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Get agent by ID."""
        agent = self._agents.get(agent_id)
        return deepcopy(agent) if agent else None

    def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new agent. Generates ID if not provided."""
        agent_id = data.get("id") or str(uuid.uuid4())
        data["id"] = agent_id
        data.setdefault("createdAt", datetime.utcnow().isoformat() + "Z")
        data.setdefault("updatedAt", datetime.utcnow().isoformat() + "Z")
        data.setdefault("status", "active")
        data.setdefault("agentType", "analysis")
        data.setdefault("avatar", "🦄")
        self._agents[agent_id] = data
        self._persist()
        return deepcopy(data)

    def update(self, agent_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update an existing agent. Returns None if not found."""
        if agent_id not in self._agents:
            return None
        self._agents[agent_id].update(updates)
        self._agents[agent_id]["updatedAt"] = datetime.utcnow().isoformat() + "Z"
        self._persist()
        return deepcopy(self._agents[agent_id])

    def delete(self, agent_id: str) -> bool:
        """Delete an agent. Returns False if not found."""
        if agent_id not in self._agents:
            return False
        del self._agents[agent_id]
        self._persist()
        return True

    def get_domains(self) -> List[Dict[str, Any]]:
        """Get domain summary with counts."""
        domain_counts: Dict[str, int] = {}
        for agent in self._agents.values():
            domain = agent.get("domain", "other")
            domain_counts[domain] = domain_counts.get(domain, 0) + 1
        return [
            {"name": name, "count": count}
            for name, count in sorted(domain_counts.items())
        ]

    def count(self) -> int:
        """Total number of agents."""
        return len(self._agents)

    def count_active(self) -> int:
        """Number of active agents."""
        return sum(1 for a in self._agents.values() if a.get("status") == "active")
