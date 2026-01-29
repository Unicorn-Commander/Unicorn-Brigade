"""
Base Worker Class for Lobster-style Workflow Engine

Workers are bounded, single-purpose execution units that:
- Have timeout enforcement
- Produce typed artifacts
- Report structured results
- Can escalate to cloud services
"""

from typing import Dict, Any, List, Optional, TypeVar, Generic
from abc import ABC, abstractmethod
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum
import asyncio
import logging

logger = logging.getLogger(__name__)


class WorkerStatus(str, Enum):
    """Worker execution status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    ESCALATED = "escalated"


class WorkerArtifact(BaseModel):
    """Output artifact from a worker"""
    name: str
    type: str  # "text", "code", "json", "file", "table", "chart"
    content: Any
    metadata: Dict[str, Any] = Field(default_factory=dict)


class WorkerResult(BaseModel):
    """Standard result from worker execution"""
    model_config = {"protected_namespaces": ()}

    worker_name: str
    status: WorkerStatus

    # Outputs
    output: Optional[str] = None
    artifacts: List[WorkerArtifact] = Field(default_factory=list)

    # Metrics
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: float = 0.0

    # Token usage
    tokens_input: int = 0
    tokens_output: int = 0

    # Error handling
    error: Optional[str] = None
    error_type: Optional[str] = None

    # Escalation
    escalated: bool = False
    escalation_reason: Optional[str] = None

    # Model info
    model_used: Optional[str] = None
    provider: Optional[str] = None


T = TypeVar('T')


class BaseWorker(ABC, Generic[T]):
    """
    Base class for all workers in the workflow engine.

    Workers are specialized execution units with:
    - Bounded execution time (timeouts)
    - Typed artifact production
    - Escalation capability
    - Standard result format
    """

    # Class-level config
    name: str = "BaseWorker"
    description: str = "Base worker class"
    default_timeout: int = 120  # 2 minutes
    max_retries: int = 2

    def __init__(
        self,
        llm_client=None,
        timeout: Optional[int] = None,
        enable_escalation: bool = True,
    ):
        self.llm_client = llm_client
        self.timeout = timeout or self.default_timeout
        self.enable_escalation = enable_escalation
        self._retries = 0

        logger.info(f"Initialized worker: {self.name} (timeout={self.timeout}s)")

    @abstractmethod
    async def _execute_impl(
        self,
        task: str,
        context: Dict[str, Any],
        user_id: str,
        model: str,
    ) -> WorkerResult:
        """
        Implementation-specific execution logic.

        Override this in subclasses to define worker behavior.
        """
        pass

    async def execute(
        self,
        task: str,
        context: Optional[Dict[str, Any]] = None,
        user_id: str = "system",
        model: str = "default",
    ) -> WorkerResult:
        """
        Execute the worker with timeout enforcement.

        This wraps the implementation with timeout handling and error recovery.
        """
        context = context or {}
        started_at = datetime.utcnow()

        try:
            # Execute with timeout
            result = await asyncio.wait_for(
                self._execute_impl(task, context, user_id, model),
                timeout=self.timeout
            )

            # Update timing
            completed_at = datetime.utcnow()
            result.started_at = started_at
            result.completed_at = completed_at
            result.duration_seconds = (completed_at - started_at).total_seconds()

            return result

        except asyncio.TimeoutError:
            logger.warning(f"{self.name}: Execution timed out after {self.timeout}s")

            # Check if we should escalate
            if self.enable_escalation and self._should_escalate(task, context):
                return await self._escalate(task, context, user_id, "timeout")

            return WorkerResult(
                worker_name=self.name,
                status=WorkerStatus.TIMEOUT,
                error=f"Execution timed out after {self.timeout} seconds",
                error_type="TimeoutError",
                started_at=started_at,
                completed_at=datetime.utcnow(),
                duration_seconds=self.timeout,
            )

        except Exception as e:
            logger.error(f"{self.name}: Execution failed - {e}")

            # Retry logic
            if self._retries < self.max_retries:
                self._retries += 1
                logger.info(f"{self.name}: Retry {self._retries}/{self.max_retries}")
                return await self.execute(task, context, user_id, model)

            # Check if we should escalate
            if self.enable_escalation and self._should_escalate(task, context):
                return await self._escalate(task, context, user_id, str(e))

            return WorkerResult(
                worker_name=self.name,
                status=WorkerStatus.FAILED,
                error=str(e),
                error_type=type(e).__name__,
                started_at=started_at,
                completed_at=datetime.utcnow(),
            )

    def _should_escalate(self, task: str, context: Dict[str, Any]) -> bool:
        """
        Determine if execution should escalate to cloud/premium model.

        Override in subclasses for custom escalation logic.
        """
        # Default: escalate on retry exhaustion
        return self._retries >= self.max_retries

    async def _escalate(
        self,
        task: str,
        context: Dict[str, Any],
        user_id: str,
        reason: str,
    ) -> WorkerResult:
        """
        Escalate execution to a more capable model (e.g., Claude).

        This is called when local execution fails or times out.
        """
        logger.info(f"{self.name}: Escalating to cloud model. Reason: {reason}")

        # Mark as escalated - the workflow engine will route to Unicorn Brigade
        return WorkerResult(
            worker_name=self.name,
            status=WorkerStatus.ESCALATED,
            escalated=True,
            escalation_reason=reason,
            output=f"Task escalated to cloud service. Reason: {reason}",
        )

    def create_artifact(
        self,
        name: str,
        content: Any,
        artifact_type: str = "text",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> WorkerArtifact:
        """Helper to create typed artifacts"""
        return WorkerArtifact(
            name=name,
            type=artifact_type,
            content=content,
            metadata=metadata or {},
        )

    async def call_llm(
        self,
        messages: List[Dict[str, str]],
        model: str = "default",
        temperature: float = 0.7,
        max_tokens: int = 2000,
        user_id: str = "system",
    ) -> Dict[str, Any]:
        """
        Call LLM through Ops-Center.

        Returns response dict with 'content', 'usage', and metadata.
        """
        if not self.llm_client:
            raise ValueError(f"{self.name}: No LLM client configured")

        response = await self.llm_client.chat_completion(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            user_id=user_id,
        )

        return {
            "content": response["choices"][0]["message"]["content"],
            "usage": response.get("usage", {}),
            "model": response.get("model", model),
            "provider": response.get("provider", "ops-center"),
        }

    def get_info(self) -> Dict[str, Any]:
        """Get worker info for introspection"""
        return {
            "name": self.name,
            "description": self.description,
            "timeout": self.timeout,
            "max_retries": self.max_retries,
            "escalation_enabled": self.enable_escalation,
        }
