"""
Task Planner - Step Sequence Generation

The Planner generates a structured workflow plan for ad-hoc tasks.
For known workflows (loaded from YAML), this step is skipped.

Output: A deterministic sequence of steps with:
- Clear inputs/outputs per step
- Artifact production
- Approval gates for high-risk steps
"""

import json
import logging
from typing import Optional, List
from pathlib import Path

from app.engine.models import (
    Task,
    RoutingResult,
    WorkflowPlan,
    WorkflowStep,
    RiskLevel,
    ToolType,
    WorkerType,
)
from app.llm.ops_center_client import OpsCenterLLMClient

logger = logging.getLogger(__name__)


DEFAULT_PLANNER_PROMPT = """You are a workflow planner for an AI agent system. Generate a step-by-step plan for the given task.

Output ONLY valid JSON with this exact schema:
{
    "objective": "clear description of what we're accomplishing",
    "assumptions": ["list of assumptions we're making"],
    "steps": [
        {
            "id": 1,
            "action": "what this step does",
            "tool": "shell|python|browser|filesystem|llm|api|database",
            "inputs": ["what this step needs"],
            "outputs": ["artifact_name.ext or description of output"],
            "success_criteria": ["how we know this step succeeded"],
            "risk": "low|medium|high"
        }
    ],
    "stop_conditions": ["when to abort the workflow"],
    "questions_for_user": ["only if critical information is missing"]
}

PLANNING RULES:
- Minimal steps - prefer fewer, well-defined steps over many small ones
- Each step MUST produce an artifact or measurable outcome
- Do not leak secrets in any step
- High-risk steps MUST be marked as such
- File deletions, email sends, and financial operations are ALWAYS high-risk
- If you need user clarification, add to questions_for_user (max 2 questions)
- JSON only, no markdown, no explanation outside JSON
"""


class TaskPlanner:
    """Generates step-by-step execution plans for tasks"""

    # Tool mappings based on action keywords
    TOOL_HINTS = {
        "search": ToolType.BROWSER,
        "scrape": ToolType.BROWSER,
        "fetch": ToolType.BROWSER,
        "run": ToolType.SHELL,
        "execute": ToolType.SHELL,
        "install": ToolType.SHELL,
        "read": ToolType.FILESYSTEM,
        "write": ToolType.FILESYSTEM,
        "create file": ToolType.FILESYSTEM,
        "analyze": ToolType.LLM,
        "summarize": ToolType.LLM,
        "generate": ToolType.LLM,
        "query": ToolType.DATABASE,
        "call api": ToolType.API,
        "extract": ToolType.PYTHON,
        "parse": ToolType.PYTHON,
        "transform": ToolType.PYTHON,
    }

    def __init__(
        self,
        llm_client: Optional[OpsCenterLLMClient] = None,
        prompt_path: Optional[Path] = None,
        max_steps: int = 10,
    ):
        self.llm_client = llm_client or OpsCenterLLMClient()
        self.max_steps = max_steps
        self.prompt = self._load_prompt(prompt_path)

    def _load_prompt(self, prompt_path: Optional[Path]) -> str:
        """Load planner prompt from file or use default"""
        if prompt_path and prompt_path.exists():
            return prompt_path.read_text()

        default_path = Path(__file__).parent.parent.parent / "prompts" / "planner.md"
        if default_path.exists():
            return default_path.read_text()

        return DEFAULT_PLANNER_PROMPT

    async def plan(
        self,
        task: Task,
        routing: RoutingResult,
        context: Optional[dict] = None,
    ) -> WorkflowPlan:
        """
        Generate a workflow plan for the task.

        Args:
            task: The incoming task
            routing: Routing result from TaskRouter
            context: Additional context (previous results, user preferences, etc.)

        Returns:
            WorkflowPlan with steps to execute
        """
        logger.info(f"Planning task {task.id}: {task.content[:100]}...")

        try:
            # Build context string
            context_str = ""
            if context:
                context_str = f"\n\nContext:\n{json.dumps(context, indent=2)}"

            # Build routing info string
            routing_str = (
                f"\n\nRouting Info:\n"
                f"- Intent: {routing.intent}\n"
                f"- Risk: {routing.risk}\n"
                f"- Worker: {routing.suggested_worker}\n"
                f"- Approval needed: {routing.needs_human_approval}"
            )

            # Determine which model to use
            model = routing.suggested_model if routing.escalate_to_cloud else "local"

            # Call LLM for planning
            response = await self.llm_client.chat_completion(
                messages=[
                    {"role": "system", "content": self.prompt},
                    {"role": "user", "content": f"Task: {task.content}{routing_str}{context_str}"}
                ],
                model=model,
                temperature=0.2,  # Low temperature for structured output
                max_tokens=2000,
                user_id=task.user_id
            )

            # Parse JSON response
            result_text = response["choices"][0]["message"]["content"]
            result_json = self._parse_json_response(result_text)

            # Build workflow plan
            plan = self._build_plan(task, routing, result_json)

            logger.info(
                f"Planned task {task.id}: {len(plan.steps)} steps, "
                f"risk={plan.total_risk}, approval={plan.requires_approval}"
            )

            return plan

        except Exception as e:
            logger.error(f"Planning error for task {task.id}: {e}")
            # Return a minimal safe plan
            return self._create_fallback_plan(task, routing, str(e))

    def _parse_json_response(self, text: str) -> dict:
        """Parse JSON from LLM response"""
        # Try direct parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try extracting JSON from markdown code block
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            if end > start:
                try:
                    return json.loads(text[start:end].strip())
                except json.JSONDecodeError:
                    pass

        # Try extracting JSON from curly braces
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError:
                pass

        logger.warning(f"Could not parse JSON from planning response")
        return {}

    def _build_plan(
        self,
        task: Task,
        routing: RoutingResult,
        plan_json: dict,
    ) -> WorkflowPlan:
        """Build a WorkflowPlan from parsed JSON"""
        steps = []
        max_risk = RiskLevel.LOW
        requires_approval = routing.needs_human_approval

        for step_data in plan_json.get("steps", [])[:self.max_steps]:
            # Parse tool type
            tool_str = step_data.get("tool", "llm").lower()
            try:
                tool = ToolType(tool_str)
            except ValueError:
                tool = ToolType.LLM

            # Parse risk level
            risk_str = step_data.get("risk", "low").lower()
            try:
                risk = RiskLevel(risk_str)
            except ValueError:
                risk = RiskLevel.LOW

            # Update max risk
            if risk == RiskLevel.HIGH:
                max_risk = RiskLevel.HIGH
            elif risk == RiskLevel.MEDIUM and max_risk != RiskLevel.HIGH:
                max_risk = RiskLevel.MEDIUM

            # Check if step needs approval
            step_needs_approval = (
                risk == RiskLevel.HIGH or
                tool in [ToolType.SHELL, ToolType.DATABASE] and risk != RiskLevel.LOW
            )
            if step_needs_approval:
                requires_approval = True

            step = WorkflowStep(
                id=step_data.get("id", len(steps) + 1),
                action=step_data.get("action", ""),
                tool=tool,
                worker=self._infer_worker(tool, routing.suggested_worker),
                inputs=step_data.get("inputs", []),
                outputs=step_data.get("outputs", []),
                success_criteria=step_data.get("success_criteria", []),
                risk=risk,
                approval_required=step_needs_approval,
                timeout_seconds=self._estimate_timeout(tool),
            )
            steps.append(step)

        # If no steps generated, create a single LLM step
        if not steps:
            steps.append(WorkflowStep(
                id=1,
                action="Process task with LLM",
                tool=ToolType.LLM,
                worker=routing.suggested_worker,
                inputs=[task.content],
                outputs=["result.txt"],
                success_criteria=["LLM provides a response"],
                risk=routing.risk,
                approval_required=routing.needs_human_approval,
            ))

        return WorkflowPlan(
            name=f"plan_{task.id}",
            objective=plan_json.get("objective", task.content[:100]),
            assumptions=plan_json.get("assumptions", []),
            steps=steps,
            stop_conditions=plan_json.get("stop_conditions", []),
            questions_for_user=plan_json.get("questions_for_user", []),
            total_risk=max_risk,
            requires_approval=requires_approval,
            estimated_duration_seconds=sum(s.timeout_seconds for s in steps),
        )

    def _infer_worker(self, tool: ToolType, suggested: WorkerType) -> WorkerType:
        """Infer the best worker for a tool type"""
        tool_worker_map = {
            ToolType.SHELL: WorkerType.OPS,
            ToolType.PYTHON: WorkerType.CODE,
            ToolType.BROWSER: WorkerType.SCRAPE,
            ToolType.FILESYSTEM: WorkerType.OPS,
            ToolType.LLM: suggested,
            ToolType.API: WorkerType.RESEARCH,
            ToolType.DATABASE: WorkerType.OPS,
        }
        return tool_worker_map.get(tool, suggested)

    def _estimate_timeout(self, tool: ToolType) -> int:
        """Estimate timeout for a step based on tool type"""
        timeouts = {
            ToolType.SHELL: 60,
            ToolType.PYTHON: 120,
            ToolType.BROWSER: 180,
            ToolType.FILESYSTEM: 30,
            ToolType.LLM: 60,
            ToolType.API: 30,
            ToolType.DATABASE: 30,
        }
        return timeouts.get(tool, 60)

    def _create_fallback_plan(
        self,
        task: Task,
        routing: RoutingResult,
        error: str,
    ) -> WorkflowPlan:
        """Create a minimal fallback plan when planning fails"""
        return WorkflowPlan(
            name=f"fallback_{task.id}",
            objective=f"Process task (planning failed: {error})",
            assumptions=["Planning failed, using fallback single-step execution"],
            steps=[
                WorkflowStep(
                    id=1,
                    action="Execute task with worker",
                    tool=ToolType.LLM,
                    worker=routing.suggested_worker,
                    inputs=[task.content],
                    outputs=["result.txt"],
                    success_criteria=["Worker provides a response"],
                    risk=routing.risk,
                    approval_required=routing.needs_human_approval,
                )
            ],
            stop_conditions=["On any error"],
            total_risk=routing.risk,
            requires_approval=routing.needs_human_approval,
        )

    async def plan_quick(
        self,
        content: str,
        user_id: str = "anonymous",
        intent: str = "unknown",
    ) -> WorkflowPlan:
        """Quick planning without full routing"""
        task = Task(user_id=user_id, content=content)
        routing = RoutingResult(
            intent=TaskIntent(intent) if intent != "unknown" else TaskIntent.UNKNOWN,
            risk=RiskLevel.LOW,
            needs_human_approval=False,
            suggested_worker=WorkerType.RESEARCH,
            reason="Quick plan",
            confidence=0.7,
        )
        return await self.plan(task, routing)


# Import at bottom to avoid circular imports
from app.engine.models import TaskIntent
