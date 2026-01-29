"""
Task Router - Intent/Risk/Worker Classification

The Router analyzes incoming tasks and determines:
- Intent category (research, coding, scrape, etc.)
- Risk level (low, medium, high)
- Whether human approval is needed
- Which worker should handle it
- Whether to escalate to cloud models
"""

import json
import logging
from typing import Optional
from pathlib import Path

from app.engine.models import (
    Task,
    RoutingResult,
    TaskIntent,
    RiskLevel,
    Priority,
    WorkerType,
)
from app.llm.ops_center_client import OpsCenterLLMClient

logger = logging.getLogger(__name__)


# Default routing prompt - can be overridden via prompts/router.md
DEFAULT_ROUTER_PROMPT = """You are a task router for an AI agent system. Analyze the user's request and classify it.

Output ONLY valid JSON with this exact schema:
{
    "intent": "research|coding|scrape|outreach|report|ops|qa|extraction",
    "priority": "low|normal|high|urgent",
    "risk": "low|medium|high",
    "needs_human_approval": true|false,
    "suggested_worker": "ResearchWorker|CodeWorker|ExtractorWorker|ReportWorker|OpsWorker|ScrapeWorker|OutreachWorker",
    "reason": "one sentence explanation"
}

ROUTING RULES:
- money/credentials/bulk outreach/deletes => risk=high & needs_human_approval=true
- vague or unclear request => intent=research
- code generation/modification => intent=coding, worker=CodeWorker
- data extraction from text => intent=extraction, worker=ExtractorWorker
- file/shell operations => intent=ops, worker=OpsWorker, risk=medium minimum
- web scraping => intent=scrape, worker=ScrapeWorker
- email/message drafting => intent=outreach, worker=OutreachWorker, needs_human_approval=true
- summarization/reports => intent=report, worker=ReportWorker
- be conservative with risk levels
- JSON only, no markdown, no explanation outside JSON
"""


class TaskRouter:
    """Routes tasks to appropriate workers with risk assessment"""

    # High-risk keywords that trigger approval requirements
    HIGH_RISK_KEYWORDS = [
        "delete", "remove", "drop", "password", "credential", "secret",
        "api key", "token", "money", "payment", "transfer", "send email",
        "bulk", "mass", "all users", "production", "deploy", "execute",
        "sudo", "root", "admin", "chmod", "rm -rf"
    ]

    # Escalation triggers
    ESCALATION_TRIGGERS = [
        "analyze this website",
        "scrape",
        "external api",
        "multi-file refactor",
        "complex analysis",
        "legal",
        "medical",
        "financial advice",
    ]

    def __init__(
        self,
        llm_client: Optional[OpsCenterLLMClient] = None,
        prompt_path: Optional[Path] = None,
        confidence_threshold: float = 0.7,
    ):
        self.llm_client = llm_client or OpsCenterLLMClient()
        self.confidence_threshold = confidence_threshold
        self.prompt = self._load_prompt(prompt_path)

    def _load_prompt(self, prompt_path: Optional[Path]) -> str:
        """Load router prompt from file or use default"""
        if prompt_path and prompt_path.exists():
            return prompt_path.read_text()

        # Try default location
        default_path = Path(__file__).parent.parent.parent / "prompts" / "router.md"
        if default_path.exists():
            return default_path.read_text()

        return DEFAULT_ROUTER_PROMPT

    def _detect_high_risk(self, content: str) -> bool:
        """Detect high-risk keywords in content"""
        content_lower = content.lower()
        return any(kw in content_lower for kw in self.HIGH_RISK_KEYWORDS)

    def _detect_escalation_needed(self, content: str) -> tuple[bool, str]:
        """Detect if task needs cloud escalation"""
        content_lower = content.lower()
        for trigger in self.ESCALATION_TRIGGERS:
            if trigger in content_lower:
                return True, f"Task involves: {trigger}"
        return False, ""

    async def route(self, task: Task) -> RoutingResult:
        """
        Route a task to the appropriate worker.

        Returns RoutingResult with intent, risk, worker, and escalation info.
        """
        logger.info(f"Routing task {task.id}: {task.content[:100]}...")

        try:
            # Call LLM for classification
            response = await self.llm_client.chat_completion(
                messages=[
                    {"role": "system", "content": self.prompt},
                    {"role": "user", "content": f"Task: {task.content}"}
                ],
                model="local",  # Use local model for routing (fast/cheap)
                temperature=0.1,  # Low temperature for deterministic output
                max_tokens=500,
                user_id=task.user_id
            )

            # Parse JSON response
            result_text = response["choices"][0]["message"]["content"]
            result_json = self._parse_json_response(result_text)

            # Build routing result
            routing = RoutingResult(
                intent=TaskIntent(result_json.get("intent", "unknown")),
                priority=Priority(result_json.get("priority", "normal")),
                risk=RiskLevel(result_json.get("risk", "low")),
                needs_human_approval=result_json.get("needs_human_approval", False),
                suggested_worker=WorkerType(result_json.get("suggested_worker", "ResearchWorker")),
                reason=result_json.get("reason", ""),
                confidence=0.85,  # Base confidence from LLM
            )

            # Apply safety overrides
            routing = self._apply_safety_overrides(task, routing)

            # Check for escalation
            routing = self._check_escalation(task, routing)

            logger.info(
                f"Routed task {task.id}: intent={routing.intent}, "
                f"risk={routing.risk}, worker={routing.suggested_worker}, "
                f"escalate={routing.escalate_to_cloud}"
            )

            return routing

        except Exception as e:
            logger.error(f"Routing error for task {task.id}: {e}")
            # Return safe defaults on error
            return RoutingResult(
                intent=TaskIntent.UNKNOWN,
                priority=Priority.NORMAL,
                risk=RiskLevel.MEDIUM,
                needs_human_approval=True,
                suggested_worker=WorkerType.RESEARCH,
                reason=f"Routing failed: {str(e)}",
                confidence=0.3,
                escalate_to_cloud=True,
                escalation_reason="Routing error - escalating for safety"
            )

    def _parse_json_response(self, text: str) -> dict:
        """Parse JSON from LLM response, handling common issues"""
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

        logger.warning(f"Could not parse JSON from response: {text[:200]}")
        return {}

    def _apply_safety_overrides(self, task: Task, routing: RoutingResult) -> RoutingResult:
        """Apply safety overrides based on content analysis"""
        # Check for high-risk keywords
        if self._detect_high_risk(task.content):
            routing.risk = RiskLevel.HIGH
            routing.needs_human_approval = True
            routing.confidence = min(routing.confidence, 0.6)
            logger.info(f"Task {task.id}: High-risk keywords detected, requiring approval")

        # Ops tasks always require at least medium risk
        if routing.suggested_worker == WorkerType.OPS:
            if routing.risk == RiskLevel.LOW:
                routing.risk = RiskLevel.MEDIUM

        # Outreach always requires approval
        if routing.suggested_worker == WorkerType.OUTREACH:
            routing.needs_human_approval = True

        return routing

    def _check_escalation(self, task: Task, routing: RoutingResult) -> RoutingResult:
        """Check if task should escalate to cloud models"""
        needs_escalation, reason = self._detect_escalation_needed(task.content)

        if needs_escalation:
            routing.escalate_to_cloud = True
            routing.escalation_reason = reason
            routing.suggested_model = "claude-burst"

        # Low confidence triggers escalation
        if routing.confidence < self.confidence_threshold:
            routing.escalate_to_cloud = True
            routing.escalation_reason = f"Low confidence: {routing.confidence}"
            routing.suggested_model = "ops-center"

        # High risk with external data triggers escalation
        if routing.risk == RiskLevel.HIGH and routing.intent in [TaskIntent.SCRAPE, TaskIntent.RESEARCH]:
            routing.escalate_to_cloud = True
            routing.escalation_reason = "High-risk task with external data"
            routing.suggested_model = "claude-burst"

        return routing

    async def route_quick(self, content: str, user_id: str = "anonymous") -> RoutingResult:
        """Quick routing without creating a full Task object"""
        task = Task(user_id=user_id, content=content)
        return await self.route(task)
