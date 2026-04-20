"""Brigade memory package — Graphiti+FalkorDB is the live implementation."""

from app.memory.graphiti_manager import GraphitiMemoryManager

# Backwards-compat alias: older code imports MemoryManager.
MemoryManager = GraphitiMemoryManager

__all__ = ["GraphitiMemoryManager", "MemoryManager"]
