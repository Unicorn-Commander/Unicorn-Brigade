"""Organization availability shared by tool discovery and the caller guard.

Catalog scopes are read for each request; only the ID/slug directory is cached
(60 seconds, per database bind). No request identity or access decision is
cached. Explicit scopes intersect, so neither source can widen the other.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Iterable
from dataclasses import dataclass, field
from uuid import UUID
from weakref import WeakKeyDictionary

from sqlalchemy import text

logger = logging.getLogger(__name__)
ORG_CACHE_SECONDS = 60.0


def parse_orgs(value: object, *, source: str) -> tuple[str, ...] | None:
    """NULL/omitted is global; an empty or malformed list allows nobody."""
    if value is None:
        return None
    if not isinstance(value, list | tuple):
        logger.warning("Invalid orgs scope for %s; denying all organizations", source)
        return ()
    orgs = []
    for item in value:
        if isinstance(item, str) and item.strip():
            orgs.append(item.strip())
        else:
            logger.warning("Invalid organization in orgs scope for %s; ignored", source)
    return tuple(orgs)


def _org_key(value: object) -> str:
    value = str(value).strip()
    try:
        return str(UUID(value))
    except ValueError:
        return value


@dataclass
class _OrgDirectory:
    identities: dict[str, str]
    expires_at: float
    warned: set[str] = field(default_factory=set)

    def resolve(self, scope: tuple[str, ...]) -> frozenset[str]:
        ids = set()
        for name in scope:
            org_id = self.identities.get(_org_key(name))
            if org_id is not None:
                ids.add(org_id)
            elif name not in self.warned:
                logger.warning("Unknown organization %r in tool orgs scope; ignored", name)
                self.warned.add(name)
        return frozenset(ids)


_ORG_CACHE: WeakKeyDictionary = WeakKeyDictionary()


def clear_org_scope_cache() -> None:
    """Invalidate the directory after an administrative change or in tests."""
    _ORG_CACHE.clear()


async def _organization_directory(session) -> _OrgDirectory:
    if session is None:
        return _OrgDirectory({}, 0)
    try:
        bind = session.get_bind()
        cached = _ORG_CACHE.get(bind)
        if cached is not None and cached.expires_at > time.monotonic():
            return cached
        rows = await session.execute(text("SELECT id, slug FROM organizations"))
        identities = {}
        for org_id, slug in rows:
            org_id = _org_key(org_id)
            identities[org_id] = org_id
            identities[str(slug)] = org_id
    except Exception:  # directory failures must never turn a scope global
        logger.warning("Organization directory unavailable; scoped tools are denied")
        return _OrgDirectory({}, 0)
    cached = _OrgDirectory(identities, time.monotonic() + ORG_CACHE_SECONDS)
    _ORG_CACHE[bind] = cached
    return cached


@dataclass(frozen=True)
class ToolOrgScope:
    org_id: str | None = None
    allowed_orgs: dict[str, frozenset[str]] = field(default_factory=dict)
    aliases: dict[str, str] = field(default_factory=dict)
    catalog_available: bool = True

    def allows(self, tool_name: str) -> bool:
        """The single availability decision for listing and execution."""
        if not self.catalog_available:
            return False
        scope = self.allowed_orgs.get(self.aliases.get(tool_name, tool_name))
        return scope is None or self.org_id in scope

    def check(self, tool_name: str) -> str | None:
        if not self.allows(tool_name):
            return f"Tool {tool_name} is not available in this organization."
        return None


async def load_tool_org_scope(
    session, org_id: str | None, *, catalog_rows: Iterable[tuple[str, object]] | None = None,
) -> ToolOrgScope:
    """Build a request snapshot using AuthUser.org_id, never the agent's org."""
    # Lazy import: sibling transport imports ToolDefinition from the LLM client.
    from app.llm.sibling_app_tools import SIBLING_APPS

    aliases = {alias: name for app in SIBLING_APPS for alias, name in app.aliases.items()}
    raw_scopes: dict[str, list[tuple[str, ...]]] = {}

    def add(name: str, scope: tuple[str, ...] | None) -> None:
        if scope is not None:
            raw_scopes.setdefault(aliases.get(name, name), []).append(scope)

    for app in SIBLING_APPS:
        for name in app.tools:
            add(name, app.orgs)

    if catalog_rows is None and session is not None:
        try:
            # JSON projection also works before the additive migration: an
            # absent orgs column is NULL, preserving old global catalog rows.
            catalog_rows = await session.execute(text(
                "SELECT name, to_jsonb(tool_catalog)->'orgs' AS orgs FROM tool_catalog"
            ))
        except Exception:
            logger.warning("Tool org scopes unavailable; tool access is denied")
            return ToolOrgScope(org_id=org_id, catalog_available=False)

    for name, scope in catalog_rows or ():
        add(name, parse_orgs(scope, source=f"tool_catalog:{name}"))

    if not raw_scopes:
        return ToolOrgScope(org_id=org_id, aliases=aliases)
    directory = await _organization_directory(session)
    allowed_orgs = {}
    for name, scopes in raw_scopes.items():
        resolved = [directory.resolve(scope) for scope in scopes]
        allowed_orgs[name] = frozenset.intersection(*resolved)
    return ToolOrgScope(
        org_id=directory.identities.get(_org_key(org_id)) if org_id else None,
        allowed_orgs=allowed_orgs,
        aliases=aliases,
    )
