"""
Brigade federated-apps registry.

Stores the UC apps Brigade brokers to (Meeting-Ops, Project-Ops, ...). Each row
is built from the app's /.well-known/mcps.json manifest: the tool namespace, the
expected audience Brigade signs JWTs for, the app's MCP/REST endpoint, and the
validated tool list. The namespaced tool catalog and the JWT mint both read from
here.

The model lives on the shared Base, so app.db.database.Base.metadata.create_all
(how Brigade creates tables; there is no Alembic) picks it up at startup as long
as this module is imported, which main.py guarantees by importing the federation
registration router.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, Column, DateTime, String, Text, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import Base


class FederatedApp(Base):
    __tablename__ = "federated_apps"

    # Canonical app name. This is also the JWT audience; stable, never changes.
    name = Column(String(255), primary_key=True)
    namespace = Column(String(64), nullable=False)          # tool_namespace prefix
    expected_audience = Column(String(255), nullable=False)
    manifest_url = Column(String(1024), nullable=False)
    mcp_endpoint = Column(String(1024), nullable=False)
    version = Column(String(64))
    tools = Column(JSON, default=list)                       # validated tool entries
    manifest_raw = Column(JSON, default=dict)                # full manifest snapshot
    status = Column(String(32), default="active")            # active | disabled | error
    last_error = Column(Text)
    registered_at = Column(DateTime, default=datetime.utcnow)
    refreshed_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "namespace": self.namespace,
            "expected_audience": self.expected_audience,
            "manifest_url": self.manifest_url,
            "mcp_endpoint": self.mcp_endpoint,
            "version": self.version,
            "tools": self.tools or [],
            "tool_count": len(self.tools or []),
            "status": self.status,
            "last_error": self.last_error,
            "registered_at": self.registered_at.isoformat() if self.registered_at else None,
            "refreshed_at": self.refreshed_at.isoformat() if self.refreshed_at else None,
        }


class FederatedAppRepository:
    """Async CRUD for federated apps. Mirrors Brigade's existing repository style."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def upsert(
        self,
        *,
        name: str,
        namespace: str,
        expected_audience: str,
        manifest_url: str,
        mcp_endpoint: str,
        version: Optional[str],
        tools: list,
        manifest_raw: dict,
    ) -> dict:
        row = await self.session.get(FederatedApp, name)
        if row is None:
            row = FederatedApp(name=name)
            self.session.add(row)
        row.namespace = namespace
        row.expected_audience = expected_audience
        row.manifest_url = manifest_url
        row.mcp_endpoint = mcp_endpoint
        row.version = version
        row.tools = tools
        row.manifest_raw = manifest_raw
        row.status = "active"
        row.last_error = None
        row.refreshed_at = datetime.utcnow()
        await self.session.commit()
        await self.session.refresh(row)
        return row.to_dict()

    async def get(self, name: str) -> Optional[FederatedApp]:
        return await self.session.get(FederatedApp, name)

    async def list_all(self) -> list[dict]:
        res = await self.session.execute(select(FederatedApp).order_by(FederatedApp.name))
        return [a.to_dict() for a in res.scalars().all()]

    async def list_active(self) -> list[FederatedApp]:
        res = await self.session.execute(
            select(FederatedApp).where(FederatedApp.status == "active")
        )
        return list(res.scalars().all())

    async def delete(self, name: str) -> bool:
        row = await self.session.get(FederatedApp, name)
        if row is None:
            return False
        await self.session.delete(row)
        await self.session.commit()
        return True

    async def mark_error(self, name: str, error: str) -> None:
        row = await self.session.get(FederatedApp, name)
        if row is not None:
            row.status = "error"
            row.last_error = (error or "")[:2000]
            await self.session.commit()
