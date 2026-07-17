# Shim: retains import compatibility for agents/code.py etc.
# Real memory lives in graphiti_manager.GraphitiMemoryManager now — including the
# BR-1.1 legacy-sub DUAL-READ alias: retrieve()/get_all() take an optional
# ``legacy_user_id`` and, when it differs from the canonical user_id, ALSO read
# the pre-cutover ``{legacy_user_id}__{agent}`` memory group so SSO users keep
# their pre-BR-1.1 memory. Writes stay canonical-only. Inherited verbatim here.
from app.memory.graphiti_manager import GraphitiMemoryManager as MemoryManager  # noqa: F401
