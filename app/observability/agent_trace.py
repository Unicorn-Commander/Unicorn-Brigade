"""
Agent Trace - Code Attribution Tracking for AI Agents

Implements the Agent Trace spec (https://agent-trace.dev/) for tracking which
AI agents/models generated which code. Provides enterprise audit trails and
compliance tracking for code generation.

Spec Version: 1.0
"""

import os
import hashlib
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)

# Configuration
AGENT_TRACE_ENABLED = os.getenv("AGENT_TRACE_ENABLED", "true").lower() == "true"


class CodeChangeType(str, Enum):
    """Type of code change"""
    GENERATION = "generation"  # New code generated
    EDIT = "edit"  # Existing code modified
    DELETION = "deletion"  # Code removed


@dataclass
class CodeLocation:
    """Location of code in a file"""
    file_path: str
    start_line: int
    end_line: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_path": self.file_path,
            "start_line": self.start_line,
            "end_line": self.end_line,
        }


@dataclass
class CodeContribution:
    """
    A single code contribution by an agent.

    Represents one unit of code generation/modification that can be
    attributed to a specific agent and model.
    """
    session_id: str
    agent_id: str
    agent_name: str
    model: str
    location: CodeLocation
    change_type: CodeChangeType
    code_content: str
    code_hash: str
    prompt: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage/API"""
        return {
            "session_id": self.session_id,
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "model": self.model,
            "location": self.location.to_dict(),
            "change_type": self.change_type.value,
            "code_content": self.code_content,
            "code_hash": self.code_hash,
            "prompt": self.prompt,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat() + "Z",
        }


@dataclass
class Attribution:
    """
    Complete attribution information for a code segment.

    Tracks the full history and lineage of a code segment across
    multiple agent interactions.
    """
    location: CodeLocation
    contributions: List[CodeContribution] = field(default_factory=list)

    @property
    def primary_agent(self) -> Optional[str]:
        """Get the agent that made the initial contribution"""
        if self.contributions:
            return self.contributions[0].agent_id
        return None

    @property
    def latest_contribution(self) -> Optional[CodeContribution]:
        """Get the most recent contribution"""
        if self.contributions:
            return sorted(self.contributions, key=lambda c: c.timestamp, reverse=True)[0]
        return None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage/API"""
        return {
            "location": self.location.to_dict(),
            "primary_agent": self.primary_agent,
            "latest_contribution": self.latest_contribution.to_dict() if self.latest_contribution else None,
            "contributions": [c.to_dict() for c in self.contributions],
        }


@dataclass
class TraceSession:
    """
    A tracing session tracking all code contributions.

    Represents a single agent conversation or workflow execution where
    code is being generated/modified.
    """
    session_id: str
    user_id: Optional[str] = None
    started_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)
    contributions: List[CodeContribution] = field(default_factory=list)

    def add_contribution(self, contribution: CodeContribution) -> None:
        """Add a contribution to this session"""
        contribution.session_id = self.session_id
        self.contributions.append(contribution)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage/API"""
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "started_at": self.started_at.isoformat() + "Z",
            "metadata": self.metadata,
            "contributions_count": len(self.contributions),
            "contributions": [c.to_dict() for c in self.contributions],
        }


class CodeExtractor:
    """
    Utility class to extract code blocks from LLM responses.

    Handles markdown code blocks and inline code detection.
    """

    # Pattern to match markdown code blocks with optional language
    CODE_BLOCK_PATTERN = re.compile(
        r'```(?P<language>\w+)?\n(?P<code>.*?)```',
        re.DOTALL
    )

    # Pattern to match file paths in responses
    FILE_PATH_PATTERN = re.compile(
        r'(?:file|path):\s*`?([^\s`]+\.[a-zA-Z]{1,4})`?',
        re.IGNORECASE
    )

    @classmethod
    def extract_code_blocks(cls, text: str) -> List[Tuple[Optional[str], str]]:
        """
        Extract code blocks from text.

        Args:
            text: Text containing potential code blocks

        Returns:
            List of (language, code) tuples
        """
        blocks = []
        for match in cls.CODE_BLOCK_PATTERN.finditer(text):
            language = match.group('language')
            code = match.group('code').strip()
            blocks.append((language, code))
        return blocks

    @classmethod
    def extract_file_paths(cls, text: str) -> List[str]:
        """
        Extract file paths mentioned in text.

        Args:
            text: Text potentially containing file paths

        Returns:
            List of file paths
        """
        return cls.FILE_PATH_PATTERN.findall(text)

    @classmethod
    def compute_code_hash(cls, code: str) -> str:
        """
        Compute a stable hash for code content.

        Uses SHA-256 hash of normalized code (whitespace-stripped).

        Args:
            code: Code content to hash

        Returns:
            Hex digest of hash
        """
        # Normalize whitespace for consistent hashing
        normalized = '\n'.join(line.rstrip() for line in code.splitlines())
        return hashlib.sha256(normalized.encode('utf-8')).hexdigest()[:16]


class AgentTraceRecorder:
    """
    Main recorder for agent code contributions.

    Tracks code generation events and stores attribution data.
    Integrates with Langfuse for observability correlation.
    """

    def __init__(
        self,
        session_id: str,
        db_session=None,  # AsyncSession for database storage
        langfuse_tracer=None,  # Optional Langfuse tracer for correlation
        user_id: Optional[str] = None,
    ):
        """
        Initialize trace recorder.

        Args:
            session_id: Unique session identifier
            db_session: Database session for persistence
            langfuse_tracer: Optional Langfuse tracer for correlation
            user_id: User ID for audit trails
        """
        self.session_id = session_id
        self.db_session = db_session
        self.langfuse_tracer = langfuse_tracer
        self.user_id = user_id
        self.session = TraceSession(
            session_id=session_id,
            user_id=user_id,
        )
        self.enabled = AGENT_TRACE_ENABLED

        if not self.enabled:
            logger.info(f"Agent Trace disabled for session {session_id}")

    async def record_code_generation(
        self,
        agent_id: str,
        agent_name: str,
        model: str,
        file_path: str,
        code_content: str,
        prompt: Optional[str] = None,
        start_line: int = 1,
        end_line: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[CodeContribution]:
        """
        Record a new code generation event.

        Args:
            agent_id: Unique agent identifier
            agent_name: Human-readable agent name
            model: Model used for generation
            file_path: Path to file being generated
            code_content: Generated code content
            prompt: Original prompt that triggered generation
            start_line: Starting line number
            end_line: Ending line number (computed if not provided)
            metadata: Additional metadata

        Returns:
            CodeContribution object or None if disabled
        """
        if not self.enabled:
            return None

        try:
            # Compute end line if not provided
            if end_line is None:
                line_count = len(code_content.splitlines())
                end_line = start_line + line_count - 1

            # Create location
            location = CodeLocation(
                file_path=file_path,
                start_line=start_line,
                end_line=end_line,
            )

            # Compute code hash
            code_hash = CodeExtractor.compute_code_hash(code_content)

            # Create contribution
            contribution = CodeContribution(
                session_id=self.session_id,
                agent_id=agent_id,
                agent_name=agent_name,
                model=model,
                location=location,
                change_type=CodeChangeType.GENERATION,
                code_content=code_content,
                code_hash=code_hash,
                prompt=prompt,
                metadata=metadata or {},
            )

            # Add to session
            self.session.add_contribution(contribution)

            # Store in database if available
            if self.db_session:
                await self._persist_contribution(contribution)

            # Log to Langfuse if available
            if self.langfuse_tracer:
                self._log_to_langfuse(contribution)

            logger.info(
                f"Recorded code generation: {agent_name} ({model}) -> {file_path}:{start_line}-{end_line}"
            )

            return contribution

        except Exception as e:
            logger.error(f"Error recording code generation: {e}", exc_info=True)
            return None

    async def record_edit(
        self,
        agent_id: str,
        agent_name: str,
        model: str,
        file_path: str,
        code_content: str,
        prompt: Optional[str] = None,
        start_line: int = 1,
        end_line: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[CodeContribution]:
        """
        Record a code edit event.

        Similar to record_code_generation but marks as edit type.
        """
        if not self.enabled:
            return None

        try:
            if end_line is None:
                line_count = len(code_content.splitlines())
                end_line = start_line + line_count - 1

            location = CodeLocation(
                file_path=file_path,
                start_line=start_line,
                end_line=end_line,
            )

            code_hash = CodeExtractor.compute_code_hash(code_content)

            contribution = CodeContribution(
                session_id=self.session_id,
                agent_id=agent_id,
                agent_name=agent_name,
                model=model,
                location=location,
                change_type=CodeChangeType.EDIT,
                code_content=code_content,
                code_hash=code_hash,
                prompt=prompt,
                metadata=metadata or {},
            )

            self.session.add_contribution(contribution)

            if self.db_session:
                await self._persist_contribution(contribution)

            if self.langfuse_tracer:
                self._log_to_langfuse(contribution)

            logger.info(
                f"Recorded code edit: {agent_name} ({model}) -> {file_path}:{start_line}-{end_line}"
            )

            return contribution

        except Exception as e:
            logger.error(f"Error recording code edit: {e}", exc_info=True)
            return None

    async def record_file_write(
        self,
        agent_id: str,
        agent_name: str,
        model: str,
        file_path: str,
        content: str,
        prompt: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[CodeContribution]:
        """
        Record a complete file write operation.

        Convenience method for tracking when an agent writes an entire file.
        """
        return await self.record_code_generation(
            agent_id=agent_id,
            agent_name=agent_name,
            model=model,
            file_path=file_path,
            code_content=content,
            prompt=prompt,
            start_line=1,
            end_line=len(content.splitlines()),
            metadata=metadata,
        )

    async def record_from_llm_response(
        self,
        agent_id: str,
        agent_name: str,
        model: str,
        prompt: str,
        response: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[CodeContribution]:
        """
        Automatically extract and record code from LLM response.

        Parses response for code blocks and file paths, creating
        contribution records for each detected code segment.

        Args:
            agent_id: Agent identifier
            agent_name: Agent name
            model: Model used
            prompt: Original prompt
            response: LLM response text
            metadata: Additional metadata

        Returns:
            List of recorded contributions
        """
        if not self.enabled:
            return []

        contributions = []

        try:
            # Extract code blocks
            code_blocks = CodeExtractor.extract_code_blocks(response)

            # Extract file paths mentioned in response
            file_paths = CodeExtractor.extract_file_paths(response)

            # If we have both code blocks and file paths, pair them up
            if code_blocks and file_paths:
                for (language, code), file_path in zip(code_blocks, file_paths):
                    contribution = await self.record_code_generation(
                        agent_id=agent_id,
                        agent_name=agent_name,
                        model=model,
                        file_path=file_path,
                        code_content=code,
                        prompt=prompt,
                        metadata={
                            **(metadata or {}),
                            "language": language,
                            "auto_extracted": True,
                        },
                    )
                    if contribution:
                        contributions.append(contribution)

            # If we only have code blocks without file paths
            elif code_blocks:
                for idx, (language, code) in enumerate(code_blocks):
                    # Use a generic file path
                    file_path = f"<code_block_{idx}>.{language or 'txt'}"
                    contribution = await self.record_code_generation(
                        agent_id=agent_id,
                        agent_name=agent_name,
                        model=model,
                        file_path=file_path,
                        code_content=code,
                        prompt=prompt,
                        metadata={
                            **(metadata or {}),
                            "language": language,
                            "auto_extracted": True,
                            "no_file_path": True,
                        },
                    )
                    if contribution:
                        contributions.append(contribution)

            logger.info(f"Auto-extracted {len(contributions)} code contributions from LLM response")

        except Exception as e:
            logger.error(f"Error extracting code from LLM response: {e}", exc_info=True)

        return contributions

    async def _persist_contribution(self, contribution: CodeContribution) -> None:
        """
        Persist contribution to database.

        Args:
            contribution: Contribution to store
        """
        try:
            from app.db.models import CodeAttribution

            attribution = CodeAttribution(
                session_id=contribution.session_id,
                agent_id=contribution.agent_id,
                agent_name=contribution.agent_name,
                model=contribution.model,
                file_path=contribution.location.file_path,
                start_line=contribution.location.start_line,
                end_line=contribution.location.end_line,
                change_type=contribution.change_type.value,
                code_hash=contribution.code_hash,
                prompt=contribution.prompt,
                generated_code=contribution.code_content,
                metadata_=contribution.metadata,
            )

            self.db_session.add(attribution)
            await self.db_session.commit()

            logger.debug(f"Persisted contribution to database: {contribution.code_hash}")

        except Exception as e:
            logger.error(f"Error persisting contribution: {e}", exc_info=True)
            # Don't raise - persistence failure shouldn't break the flow

    def _log_to_langfuse(self, contribution: CodeContribution) -> None:
        """
        Log contribution to Langfuse for correlation.

        Args:
            contribution: Contribution to log
        """
        try:
            if not self.langfuse_tracer:
                return

            self.langfuse_tracer.start_span(
                name="code_attribution",
                input_data={
                    "agent_id": contribution.agent_id,
                    "model": contribution.model,
                    "file_path": contribution.location.file_path,
                    "change_type": contribution.change_type.value,
                },
                metadata={
                    "code_hash": contribution.code_hash,
                    "line_range": f"{contribution.location.start_line}-{contribution.location.end_line}",
                    **contribution.metadata,
                },
            )

            self.langfuse_tracer.end_span(
                output={"recorded": True},
                level="DEFAULT",
            )

        except Exception as e:
            logger.warning(f"Error logging to Langfuse: {e}")

    def get_session_summary(self) -> Dict[str, Any]:
        """
        Get summary of current tracing session.

        Returns:
            Dictionary with session statistics
        """
        contributions = self.session.contributions

        # Group by agent
        by_agent = {}
        for contrib in contributions:
            agent = contrib.agent_name
            if agent not in by_agent:
                by_agent[agent] = []
            by_agent[agent].append(contrib)

        # Group by file
        by_file = {}
        for contrib in contributions:
            file_path = contrib.location.file_path
            if file_path not in by_file:
                by_file[file_path] = []
            by_file[file_path].append(contrib)

        return {
            "session_id": self.session_id,
            "total_contributions": len(contributions),
            "agents": list(by_agent.keys()),
            "files_modified": list(by_file.keys()),
            "contributions_by_agent": {
                agent: len(contribs) for agent, contribs in by_agent.items()
            },
            "contributions_by_file": {
                file: len(contribs) for file, contribs in by_file.items()
            },
            "started_at": self.session.started_at.isoformat() + "Z",
        }
