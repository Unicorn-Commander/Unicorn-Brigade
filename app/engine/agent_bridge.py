"""
Agent-Worker Bridge

Bridges the existing agents (ResearchAgent, CodeAgent, etc.)
with the new Lobster-style workers, allowing them to work together.
"""

from typing import Dict, Any, Optional, Type
import logging

from app.agents.base import BaseAgent
from app.agents.research import ResearchAgent
from app.agents.code import CodeAgent
from app.agents.analysis import AnalysisAgent

from app.workers.base import BaseWorker, WorkerResult, WorkerStatus
from app.workers import (
    ResearchWorker, CodeWorker, ExtractorWorker,
    ReportWorker, OpsWorker, get_worker,
)
from app.engine.models import WorkerType
try:
    from app.memory.manager import MemoryManager
except ImportError:
    MemoryManager = None
from app.llm.ops_center_client import OpsCenterLLMClient

logger = logging.getLogger(__name__)


class AgentWorkerBridge:
    """
    Bridges existing agents with new workers.

    This allows:
    - Using agents as workers
    - Using workers as agents
    - Seamless integration between old and new systems
    """

    def __init__(
        self,
        memory_manager: Optional["MemoryManager"] = None,
        llm_client: Optional[OpsCenterLLMClient] = None,
    ):
        self.memory_manager = memory_manager or (MemoryManager() if MemoryManager else None)
        self.llm_client = llm_client or OpsCenterLLMClient()

        # Initialize agents
        self.agents: Dict[str, BaseAgent] = {
            "research": ResearchAgent(
                memory_manager=self.memory_manager,
                llm_client=self.llm_client,
            ),
            "code": CodeAgent(
                memory_manager=self.memory_manager,
                llm_client=self.llm_client,
            ),
            "analysis": AnalysisAgent(
                memory_manager=self.memory_manager,
                llm_client=self.llm_client,
            ),
        }

        # Initialize workers
        self.workers: Dict[str, BaseWorker] = {
            "research": ResearchWorker(llm_client=self.llm_client),
            "code": CodeWorker(llm_client=self.llm_client),
            "extractor": ExtractorWorker(llm_client=self.llm_client),
            "report": ReportWorker(llm_client=self.llm_client),
            "ops": OpsWorker(llm_client=self.llm_client),
        }

        logger.info("AgentWorkerBridge initialized")

    async def execute_via_agent(
        self,
        agent_type: str,
        task: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Execute a task using the original agent interface.

        Args:
            agent_type: Type of agent (research, code, analysis)
            task: Task dict with task, user_id, etc.

        Returns:
            Agent result dict
        """
        agent = self.agents.get(agent_type)
        if not agent:
            return {
                "status": "error",
                "error": f"Unknown agent type: {agent_type}",
            }

        return await agent.execute(task)

    async def execute_via_worker(
        self,
        worker_type: str,
        task: str,
        context: Dict[str, Any],
        user_id: str,
        model: str = "default",
    ) -> WorkerResult:
        """
        Execute a task using the new worker interface.

        Args:
            worker_type: Type of worker
            task: Task description string
            context: Context dict
            user_id: User ID
            model: Model to use

        Returns:
            WorkerResult
        """
        worker = self.workers.get(worker_type)
        if not worker:
            try:
                worker = get_worker(worker_type, llm_client=self.llm_client)
            except ValueError:
                return WorkerResult(
                    worker_name="unknown",
                    status=WorkerStatus.FAILED,
                    error=f"Unknown worker type: {worker_type}",
                )

        return await worker.execute(
            task=task,
            context=context,
            user_id=user_id,
            model=model,
        )

    async def agent_to_worker(
        self,
        agent_type: str,
        task: Dict[str, Any],
    ) -> WorkerResult:
        """
        Execute agent and convert result to WorkerResult format.

        This allows agents to be used in the workflow engine.
        """
        agent_result = await self.execute_via_agent(agent_type, task)

        # Convert agent result to WorkerResult
        if agent_result.get("status") == "completed":
            return WorkerResult(
                worker_name=agent_result.get("agent", agent_type),
                status=WorkerStatus.COMPLETED,
                output=str(agent_result.get("result", {})),
                artifacts=[],  # Agents don't produce typed artifacts
                tokens_input=agent_result.get("tokens", {}).get("input", 0),
                tokens_output=agent_result.get("tokens", {}).get("output", 0),
                model_used=agent_result.get("model"),
                provider=agent_result.get("provider"),
            )
        else:
            return WorkerResult(
                worker_name=agent_result.get("agent", agent_type),
                status=WorkerStatus.FAILED,
                error=agent_result.get("error", "Unknown error"),
            )

    async def worker_to_agent(
        self,
        worker_type: str,
        task: str,
        context: Dict[str, Any],
        user_id: str,
    ) -> Dict[str, Any]:
        """
        Execute worker and convert result to agent format.

        This allows workers to be used with the old agent interface.
        """
        worker_result = await self.execute_via_worker(
            worker_type=worker_type,
            task=task,
            context=context,
            user_id=user_id,
        )

        # Convert WorkerResult to agent format
        return {
            "agent": worker_result.worker_name,
            "task_id": context.get("task_id", ""),
            "status": "completed" if worker_result.status == WorkerStatus.COMPLETED else "error",
            "result": {
                "output": worker_result.output,
                "artifacts": [a.model_dump() for a in worker_result.artifacts],
            },
            "error": worker_result.error,
            "tokens": {
                "input": worker_result.tokens_input,
                "output": worker_result.tokens_output,
                "total": worker_result.tokens_input + worker_result.tokens_output,
            },
            "model": worker_result.model_used,
            "provider": worker_result.provider,
        }

    def get_worker_for_type(self, worker_type: WorkerType) -> Optional[BaseWorker]:
        """Get worker for a WorkerType enum"""
        type_map = {
            WorkerType.RESEARCH: "research",
            WorkerType.CODE: "code",
            WorkerType.EXTRACT: "extractor",
            WorkerType.REPORT: "report",
            WorkerType.OPS: "ops",
        }
        worker_key = type_map.get(worker_type)
        if worker_key:
            return self.workers.get(worker_key) or get_worker(worker_key, llm_client=self.llm_client)
        return None

    def get_agent_for_type(self, agent_type: str) -> Optional[BaseAgent]:
        """Get agent by type"""
        return self.agents.get(agent_type)

    def register_worker(self, name: str, worker: BaseWorker):
        """Register a custom worker"""
        self.workers[name] = worker
        logger.info(f"Registered worker: {name}")

    def register_agent(self, name: str, agent: BaseAgent):
        """Register a custom agent"""
        self.agents[name] = agent
        logger.info(f"Registered agent: {name}")

    def list_available(self) -> Dict[str, Any]:
        """List all available agents and workers"""
        return {
            "agents": list(self.agents.keys()),
            "workers": list(self.workers.keys()),
        }


class UnifiedExecutor:
    """
    Unified executor that can run tasks via either agents or workers.

    Automatically selects the best execution method.
    """

    def __init__(self, bridge: Optional[AgentWorkerBridge] = None):
        self.bridge = bridge or AgentWorkerBridge()

    async def execute(
        self,
        task: str,
        task_type: str,
        user_id: str,
        context: Optional[Dict[str, Any]] = None,
        prefer_worker: bool = True,
        model: str = "default",
    ) -> Dict[str, Any]:
        """
        Execute a task using the best available method.

        Args:
            task: Task description
            task_type: Type (research, code, etc.)
            user_id: User ID
            context: Additional context
            prefer_worker: Whether to prefer workers over agents
            model: Model to use

        Returns:
            Unified result dict
        """
        context = context or {}

        if prefer_worker and task_type in self.bridge.workers:
            # Use worker
            worker_result = await self.bridge.execute_via_worker(
                worker_type=task_type,
                task=task,
                context=context,
                user_id=user_id,
                model=model,
            )

            return {
                "executor": "worker",
                "executor_name": worker_result.worker_name,
                "status": worker_result.status.value,
                "output": worker_result.output,
                "artifacts": [a.model_dump() for a in worker_result.artifacts],
                "tokens": {
                    "input": worker_result.tokens_input,
                    "output": worker_result.tokens_output,
                },
                "model": worker_result.model_used,
                "duration_seconds": worker_result.duration_seconds,
            }

        elif task_type in self.bridge.agents:
            # Use agent
            agent_task = {
                "task": task,
                "task_id": context.get("task_id", ""),
                "user_id": user_id,
                "context": context,
            }

            agent_result = await self.bridge.execute_via_agent(task_type, agent_task)

            return {
                "executor": "agent",
                "executor_name": agent_result.get("agent"),
                "status": agent_result.get("status"),
                "output": str(agent_result.get("result", {})),
                "artifacts": [],
                "tokens": agent_result.get("tokens", {}),
                "model": agent_result.get("model"),
            }

        else:
            return {
                "executor": "none",
                "status": "error",
                "error": f"No executor available for task type: {task_type}",
            }


# Lazy global instances (initialized on first access)
_bridge: Optional[AgentWorkerBridge] = None
_unified_executor: Optional[UnifiedExecutor] = None


def get_bridge() -> AgentWorkerBridge:
    """Get or create the global AgentWorkerBridge instance"""
    global _bridge
    if _bridge is None:
        _bridge = AgentWorkerBridge()
    return _bridge


def get_unified_executor() -> UnifiedExecutor:
    """Get or create the global UnifiedExecutor instance"""
    global _unified_executor
    if _unified_executor is None:
        _unified_executor = UnifiedExecutor(get_bridge())
    return _unified_executor


