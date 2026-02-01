"""Memory management module

Supports multiple memory backends:
- mem0: Original implementation with Qdrant vector store
- zep: Temporal knowledge graph with automatic fact extraction

Configure via MEMORY_PROVIDER environment variable:
- MEMORY_PROVIDER=mem0 (default)
- MEMORY_PROVIDER=zep
"""

import os
import logging
from typing import Union

from app.memory.manager import MemoryManager

logger = logging.getLogger(__name__)

# Lazy import ZepMemoryManager to avoid import errors if zep-python not installed
ZepMemoryManager = None


def _load_zep_manager():
    """Lazy load ZepMemoryManager"""
    global ZepMemoryManager
    if ZepMemoryManager is None:
        try:
            from app.memory.zep_manager import ZepMemoryManager as _ZepMemoryManager
            ZepMemoryManager = _ZepMemoryManager
        except ImportError as e:
            logger.warning(f"Failed to import ZepMemoryManager: {e}")
            ZepMemoryManager = None
    return ZepMemoryManager


def get_memory_manager() -> Union[MemoryManager, "ZepMemoryManager"]:
    """Factory function to get the configured memory manager

    Returns the appropriate memory manager based on MEMORY_PROVIDER env var:
    - "mem0" (default): Uses mem0 with Qdrant vector store
    - "zep": Uses Zep temporal knowledge graph

    Returns:
        Configured memory manager instance
    """
    provider = os.getenv("MEMORY_PROVIDER", "mem0").lower()

    if provider == "zep":
        ZepManager = _load_zep_manager()
        if ZepManager is not None:
            logger.info("Using Zep memory provider")
            return ZepManager()
        else:
            logger.warning("Zep not available, falling back to mem0")
            return MemoryManager()
    else:
        logger.info("Using mem0 memory provider")
        return MemoryManager()


__all__ = [
    "MemoryManager",
    "get_memory_manager",
]
