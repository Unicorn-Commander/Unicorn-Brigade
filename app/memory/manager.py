# Shim: retains import compatibility for agents/code.py etc.
# Real memory lives in graphiti_manager.GraphitiMemoryManager now.
from app.memory.graphiti_manager import GraphitiMemoryManager as MemoryManager  # noqa: F401
