"""
Memory Integration for Workflow Engine

Integrates mem0 memory with the workflow engine for:
- Storing workflow execution history
- Retrieving relevant context for tasks
- Learning from past executions
"""

from typing import Dict, Any, List, Optional
import logging
from datetime import datetime

from app.memory.manager import MemoryManager
from app.engine.models import Task, TaskResult, WorkflowPlan, ExecutionResult

logger = logging.getLogger(__name__)


class WorkflowMemory:
    """
    Memory layer for the workflow engine.

    Uses mem0 to persist and retrieve:
    - Task execution history
    - Successful workflow patterns
    - User preferences and context
    - Agent performance data
    """

    def __init__(self, memory_manager: Optional[MemoryManager] = None):
        self.memory = memory_manager or MemoryManager()
        logger.info("WorkflowMemory initialized")

    async def store_execution(
        self,
        task: Task,
        result: TaskResult,
        user_id: str,
    ) -> bool:
        """
        Store task execution in memory for future reference.

        This enables:
        - Learning from successful patterns
        - Avoiding repeated failures
        - Personalization per user
        """
        try:
            # Build memory content
            content = {
                "task": task.content,
                "intent": result.routing.intent.value if result.routing else "unknown",
                "status": result.status.value if hasattr(result.status, 'value') else str(result.status),
                "output_summary": result.output[:500] if result.output else "",
                "confidence": result.verification.confidence if result.verification else None,
                "model_used": result.model_used,
                "duration_seconds": result.total_duration_seconds,
                "steps_count": len(result.plan.steps) if result.plan else 0,
                "timestamp": datetime.utcnow().isoformat(),
            }

            # Add artifacts summary
            if result.artifacts:
                content["artifacts"] = [
                    {"name": a.get("name"), "type": a.get("type")}
                    for a in result.artifacts[:5]
                ]

            # Store in mem0
            messages = [
                {"role": "system", "content": f"Task execution record: {task.content[:100]}"},
                {"role": "assistant", "content": str(content)},
            ]

            return await self.memory.store(
                user_id=user_id,
                agent_id="workflow_engine",
                messages=messages,
                metadata={
                    "type": "execution_history",
                    "task_id": task.id,
                    "intent": content["intent"],
                    "status": content["status"],
                    "confidence": content["confidence"],
                }
            )

        except Exception as e:
            logger.error(f"Error storing execution memory: {e}")
            return False

    async def retrieve_context(
        self,
        task: Task,
        user_id: str,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant context for a task.

        This helps the router and planner make better decisions
        based on past similar tasks.
        """
        try:
            # Search for similar tasks
            memories = await self.memory.retrieve(
                user_id=user_id,
                query=task.content,
                agent_id="workflow_engine",
                limit=limit,
            )

            # Parse and return relevant info
            context = []
            for mem in memories:
                memory_data = mem.get("memory", "")
                if isinstance(memory_data, dict):
                    context.append(memory_data)
                else:
                    # Try to extract useful info
                    context.append({
                        "content": str(memory_data)[:200],
                        "score": mem.get("score", 0),
                    })

            logger.info(f"Retrieved {len(context)} context memories for task")
            return context

        except Exception as e:
            logger.error(f"Error retrieving context: {e}")
            return []

    async def get_successful_patterns(
        self,
        intent: str,
        user_id: str,
        limit: int = 3,
    ) -> List[Dict[str, Any]]:
        """
        Get successful workflow patterns for an intent.

        Helps the planner learn from past successes.
        """
        try:
            # Search for successful executions of this intent
            query = f"successful {intent} task high confidence"

            memories = await self.memory.retrieve(
                user_id=user_id,
                query=query,
                agent_id="workflow_engine",
                limit=limit,
            )

            # Filter for successful patterns
            patterns = []
            for mem in memories:
                memory_data = mem.get("memory", {})
                if isinstance(memory_data, dict):
                    if memory_data.get("status") == "completed":
                        confidence = memory_data.get("confidence")
                        if confidence and confidence > 0.7:
                            patterns.append(memory_data)

            return patterns

        except Exception as e:
            logger.error(f"Error getting patterns: {e}")
            return []

    async def store_workflow_template(
        self,
        name: str,
        plan: WorkflowPlan,
        user_id: str,
    ) -> bool:
        """
        Store a successful workflow as a template.

        This enables dynamic workflow creation based on past successes.
        """
        try:
            # Serialize workflow
            workflow_data = {
                "name": name,
                "objective": plan.objective,
                "steps_count": len(plan.steps),
                "steps": [
                    {
                        "id": s.id,
                        "action": s.action,
                        "tool": s.tool.value if hasattr(s.tool, 'value') else str(s.tool),
                        "worker": s.worker.value if s.worker and hasattr(s.worker, 'value') else None,
                    }
                    for s in plan.steps
                ],
                "total_risk": plan.total_risk.value if hasattr(plan.total_risk, 'value') else str(plan.total_risk),
                "created_at": datetime.utcnow().isoformat(),
            }

            messages = [
                {"role": "system", "content": f"Workflow template: {name}"},
                {"role": "assistant", "content": str(workflow_data)},
            ]

            return await self.memory.store(
                user_id=user_id,
                agent_id="workflow_templates",
                messages=messages,
                metadata={
                    "type": "workflow_template",
                    "name": name,
                    "steps_count": len(plan.steps),
                }
            )

        except Exception as e:
            logger.error(f"Error storing workflow template: {e}")
            return False

    async def get_user_preferences(self, user_id: str) -> Dict[str, Any]:
        """
        Get user preferences from memory.

        Includes preferred models, risk tolerance, etc.
        """
        try:
            memories = await self.memory.retrieve(
                user_id=user_id,
                query="user preferences settings configuration",
                agent_id="user_settings",
                limit=1,
            )

            if memories:
                return memories[0].get("memory", {})

            return {}

        except Exception as e:
            logger.error(f"Error getting preferences: {e}")
            return {}

    def get_stats(self) -> Dict[str, Any]:
        """Get memory statistics"""
        return self.memory.get_stats()


class MemoryEnhancedRouter:
    """
    Router enhancement that uses memory for better routing decisions.
    """

    def __init__(self, workflow_memory: WorkflowMemory):
        self.memory = workflow_memory

    async def enhance_routing(
        self,
        task: Task,
        base_routing: Dict[str, Any],
        user_id: str,
    ) -> Dict[str, Any]:
        """
        Enhance routing decision with memory context.
        """
        # Get past similar task results
        context = await self.memory.retrieve_context(task, user_id)

        # If we have similar tasks with low confidence, suggest escalation
        low_confidence_similar = [
            c for c in context
            if isinstance(c, dict) and c.get("confidence", 1.0) < 0.6
        ]

        if len(low_confidence_similar) >= 2:
            base_routing["escalate_suggested"] = True
            base_routing["escalation_reason"] = "Similar tasks had low confidence"

        # If similar tasks were successful, use same model
        successful = [
            c for c in context
            if isinstance(c, dict) and c.get("status") == "completed"
            and c.get("confidence", 0) > 0.8
        ]

        if successful and successful[0].get("model_used"):
            base_routing["suggested_model"] = successful[0]["model_used"]

        return base_routing
