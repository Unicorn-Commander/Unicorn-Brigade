"""
Trace Repository - Query and Compliance Reports for Code Attribution

Provides efficient querying of code attribution records for audit trails,
compliance reporting, and code lineage tracking.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import select, func, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class TraceRepository:
    """
    Repository for querying code attribution records.

    Provides methods for compliance reports, audit trails, and
    code lineage tracking.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize repository.

        Args:
            session: Async database session
        """
        self.session = session

    async def get_by_file(
        self,
        file_path: str,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Get all attributions for a specific file.

        Args:
            file_path: Path to file
            limit: Maximum records to return
            offset: Number of records to skip

        Returns:
            List of attribution records
        """
        try:
            from app.db.models import CodeAttribution

            stmt = (
                select(CodeAttribution)
                .where(CodeAttribution.file_path == file_path)
                .order_by(desc(CodeAttribution.created_at))
                .limit(limit)
                .offset(offset)
            )

            result = await self.session.execute(stmt)
            attributions = result.scalars().all()

            return [attr.to_dict() for attr in attributions]

        except Exception as e:
            logger.error(f"Error querying attributions by file: {e}", exc_info=True)
            return []

    async def get_by_agent(
        self,
        agent_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Get all attributions for a specific agent.

        Args:
            agent_id: Agent identifier
            limit: Maximum records to return
            offset: Number of records to skip

        Returns:
            List of attribution records
        """
        try:
            from app.db.models import CodeAttribution

            stmt = (
                select(CodeAttribution)
                .where(CodeAttribution.agent_id == agent_id)
                .order_by(desc(CodeAttribution.created_at))
                .limit(limit)
                .offset(offset)
            )

            result = await self.session.execute(stmt)
            attributions = result.scalars().all()

            return [attr.to_dict() for attr in attributions]

        except Exception as e:
            logger.error(f"Error querying attributions by agent: {e}", exc_info=True)
            return []

    async def get_by_session(
        self,
        session_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Get all attributions for a specific session.

        Args:
            session_id: Session identifier
            limit: Maximum records to return
            offset: Number of records to skip

        Returns:
            List of attribution records
        """
        try:
            from app.db.models import CodeAttribution

            stmt = (
                select(CodeAttribution)
                .where(CodeAttribution.session_id == session_id)
                .order_by(desc(CodeAttribution.created_at))
                .limit(limit)
                .offset(offset)
            )

            result = await self.session.execute(stmt)
            attributions = result.scalars().all()

            return [attr.to_dict() for attr in attributions]

        except Exception as e:
            logger.error(f"Error querying attributions by session: {e}", exc_info=True)
            return []

    async def get_by_date_range(
        self,
        start_date: datetime,
        end_date: Optional[datetime] = None,
        agent_id: Optional[str] = None,
        file_path: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Get attributions within a date range with optional filters.

        Args:
            start_date: Start of date range
            end_date: End of date range (defaults to now)
            agent_id: Optional agent filter
            file_path: Optional file path filter
            limit: Maximum records to return
            offset: Number of records to skip

        Returns:
            List of attribution records
        """
        try:
            from app.db.models import CodeAttribution

            if end_date is None:
                end_date = datetime.utcnow()

            # Build query with filters
            conditions = [
                CodeAttribution.created_at >= start_date,
                CodeAttribution.created_at <= end_date,
            ]

            if agent_id:
                conditions.append(CodeAttribution.agent_id == agent_id)

            if file_path:
                conditions.append(CodeAttribution.file_path == file_path)

            stmt = (
                select(CodeAttribution)
                .where(and_(*conditions))
                .order_by(desc(CodeAttribution.created_at))
                .limit(limit)
                .offset(offset)
            )

            result = await self.session.execute(stmt)
            attributions = result.scalars().all()

            return [attr.to_dict() for attr in attributions]

        except Exception as e:
            logger.error(f"Error querying attributions by date range: {e}", exc_info=True)
            return []

    async def get_by_code_hash(
        self,
        code_hash: str,
    ) -> List[Dict[str, Any]]:
        """
        Find all attributions for code with a specific hash.

        Useful for tracking code duplication or reuse across files.

        Args:
            code_hash: Code hash to search for

        Returns:
            List of attribution records
        """
        try:
            from app.db.models import CodeAttribution

            stmt = (
                select(CodeAttribution)
                .where(CodeAttribution.code_hash == code_hash)
                .order_by(desc(CodeAttribution.created_at))
            )

            result = await self.session.execute(stmt)
            attributions = result.scalars().all()

            return [attr.to_dict() for attr in attributions]

        except Exception as e:
            logger.error(f"Error querying attributions by code hash: {e}", exc_info=True)
            return []

    async def get_file_history(
        self,
        file_path: str,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """
        Get complete modification history for a file.

        Returns a detailed history showing all agents that modified
        the file and when.

        Args:
            file_path: Path to file
            limit: Maximum history entries

        Returns:
            Dictionary with file history
        """
        try:
            from app.db.models import CodeAttribution

            # Get all attributions for file
            stmt = (
                select(CodeAttribution)
                .where(CodeAttribution.file_path == file_path)
                .order_by(CodeAttribution.created_at)
                .limit(limit)
            )

            result = await self.session.execute(stmt)
            attributions = result.scalars().all()

            # Build history
            history = []
            agents_involved = set()
            models_used = set()

            for attr in attributions:
                agents_involved.add(attr.agent_name)
                models_used.add(attr.model)

                history.append({
                    "timestamp": attr.created_at.isoformat() + "Z",
                    "agent_id": attr.agent_id,
                    "agent_name": attr.agent_name,
                    "model": attr.model,
                    "change_type": attr.change_type,
                    "line_range": f"{attr.start_line}-{attr.end_line}",
                    "code_hash": attr.code_hash,
                    "prompt": attr.prompt,
                })

            return {
                "file_path": file_path,
                "total_modifications": len(attributions),
                "agents_involved": sorted(list(agents_involved)),
                "models_used": sorted(list(models_used)),
                "first_created": attributions[0].created_at.isoformat() + "Z" if attributions else None,
                "last_modified": attributions[-1].created_at.isoformat() + "Z" if attributions else None,
                "history": history,
            }

        except Exception as e:
            logger.error(f"Error getting file history: {e}", exc_info=True)
            return {
                "file_path": file_path,
                "error": str(e),
            }

    async def get_agent_statistics(
        self,
        agent_id: str,
        days: int = 30,
    ) -> Dict[str, Any]:
        """
        Get statistics for an agent's code contributions.

        Args:
            agent_id: Agent identifier
            days: Number of days to analyze (default 30)

        Returns:
            Dictionary with agent statistics
        """
        try:
            from app.db.models import CodeAttribution

            since_date = datetime.utcnow() - timedelta(days=days)

            # Get all attributions for agent in time period
            stmt = (
                select(CodeAttribution)
                .where(
                    and_(
                        CodeAttribution.agent_id == agent_id,
                        CodeAttribution.created_at >= since_date,
                    )
                )
            )

            result = await self.session.execute(stmt)
            attributions = result.scalars().all()

            # Calculate statistics
            files_modified = set()
            models_used = {}
            change_types = {}
            total_lines = 0

            for attr in attributions:
                files_modified.add(attr.file_path)

                # Count by model
                models_used[attr.model] = models_used.get(attr.model, 0) + 1

                # Count by change type
                change_types[attr.change_type] = change_types.get(attr.change_type, 0) + 1

                # Sum lines modified
                lines = attr.end_line - attr.start_line + 1
                total_lines += lines

            return {
                "agent_id": agent_id,
                "period_days": days,
                "total_contributions": len(attributions),
                "files_modified": len(files_modified),
                "total_lines_modified": total_lines,
                "models_used": models_used,
                "change_types": change_types,
                "files": sorted(list(files_modified)),
            }

        except Exception as e:
            logger.error(f"Error getting agent statistics: {e}", exc_info=True)
            return {
                "agent_id": agent_id,
                "error": str(e),
            }

    async def generate_compliance_report(
        self,
        start_date: datetime,
        end_date: Optional[datetime] = None,
        format: str = "summary",  # "summary" or "detailed"
    ) -> Dict[str, Any]:
        """
        Generate a compliance report for code attribution.

        Provides audit trail information for regulatory compliance
        and code governance.

        Args:
            start_date: Start of reporting period
            end_date: End of reporting period (defaults to now)
            format: Report format ("summary" or "detailed")

        Returns:
            Compliance report dictionary
        """
        try:
            from app.db.models import CodeAttribution

            if end_date is None:
                end_date = datetime.utcnow()

            # Get all attributions in period
            stmt = (
                select(CodeAttribution)
                .where(
                    and_(
                        CodeAttribution.created_at >= start_date,
                        CodeAttribution.created_at <= end_date,
                    )
                )
                .order_by(CodeAttribution.created_at)
            )

            result = await self.session.execute(stmt)
            attributions = result.scalars().all()

            # Aggregate data
            agents = {}
            files = set()
            models = {}
            sessions = set()

            for attr in attributions:
                # Track agents
                if attr.agent_id not in agents:
                    agents[attr.agent_id] = {
                        "name": attr.agent_name,
                        "contributions": 0,
                        "files_modified": set(),
                    }
                agents[attr.agent_id]["contributions"] += 1
                agents[attr.agent_id]["files_modified"].add(attr.file_path)

                # Track files
                files.add(attr.file_path)

                # Track models
                models[attr.model] = models.get(attr.model, 0) + 1

                # Track sessions
                sessions.add(attr.session_id)

            # Build summary
            report = {
                "report_type": "code_attribution_compliance",
                "period": {
                    "start": start_date.isoformat() + "Z",
                    "end": end_date.isoformat() + "Z",
                    "days": (end_date - start_date).days,
                },
                "summary": {
                    "total_contributions": len(attributions),
                    "unique_agents": len(agents),
                    "files_modified": len(files),
                    "unique_sessions": len(sessions),
                    "models_used": len(models),
                },
                "agents": {
                    agent_id: {
                        "name": data["name"],
                        "contributions": data["contributions"],
                        "files_modified": len(data["files_modified"]),
                    }
                    for agent_id, data in agents.items()
                },
                "models": models,
                "generated_at": datetime.utcnow().isoformat() + "Z",
            }

            # Add detailed records if requested
            if format == "detailed":
                report["detailed_records"] = [
                    {
                        "timestamp": attr.created_at.isoformat() + "Z",
                        "session_id": attr.session_id,
                        "agent_id": attr.agent_id,
                        "agent_name": attr.agent_name,
                        "model": attr.model,
                        "file_path": attr.file_path,
                        "line_range": f"{attr.start_line}-{attr.end_line}",
                        "change_type": attr.change_type,
                        "code_hash": attr.code_hash,
                    }
                    for attr in attributions
                ]

            return report

        except Exception as e:
            logger.error(f"Error generating compliance report: {e}", exc_info=True)
            return {
                "error": str(e),
                "generated_at": datetime.utcnow().isoformat() + "Z",
            }

    async def search_by_prompt(
        self,
        search_term: str,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Search attributions by prompt content.

        Useful for finding code generated from specific user requests.

        Args:
            search_term: Term to search for in prompts
            limit: Maximum records to return

        Returns:
            List of matching attribution records
        """
        try:
            from app.db.models import CodeAttribution

            stmt = (
                select(CodeAttribution)
                .where(CodeAttribution.prompt.ilike(f"%{search_term}%"))
                .order_by(desc(CodeAttribution.created_at))
                .limit(limit)
            )

            result = await self.session.execute(stmt)
            attributions = result.scalars().all()

            return [attr.to_dict() for attr in attributions]

        except Exception as e:
            logger.error(f"Error searching attributions by prompt: {e}", exc_info=True)
            return []

    async def get_session_summary(
        self,
        session_id: str,
    ) -> Dict[str, Any]:
        """
        Get complete summary of a tracing session.

        Args:
            session_id: Session identifier

        Returns:
            Session summary with all contributions
        """
        try:
            from app.db.models import CodeAttribution

            stmt = (
                select(CodeAttribution)
                .where(CodeAttribution.session_id == session_id)
                .order_by(CodeAttribution.created_at)
            )

            result = await self.session.execute(stmt)
            attributions = result.scalars().all()

            if not attributions:
                return {
                    "session_id": session_id,
                    "found": False,
                }

            # Aggregate session data
            agents = set()
            files = set()
            models = set()

            for attr in attributions:
                agents.add(attr.agent_name)
                files.add(attr.file_path)
                models.add(attr.model)

            return {
                "session_id": session_id,
                "found": True,
                "total_contributions": len(attributions),
                "agents_involved": sorted(list(agents)),
                "files_modified": sorted(list(files)),
                "models_used": sorted(list(models)),
                "started_at": attributions[0].created_at.isoformat() + "Z",
                "ended_at": attributions[-1].created_at.isoformat() + "Z",
                "contributions": [attr.to_dict() for attr in attributions],
            }

        except Exception as e:
            logger.error(f"Error getting session summary: {e}", exc_info=True)
            return {
                "session_id": session_id,
                "error": str(e),
            }
