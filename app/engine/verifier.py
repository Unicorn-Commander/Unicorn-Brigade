"""
Result Verifier - Confidence Scoring and Escalation

The Verifier analyzes execution results and determines:
- Confidence score (0-1)
- Hallucination risk
- Security risk
- Whether to retry, escalate, or continue
"""

import json
import logging
from typing import Optional
from pathlib import Path

from app.engine.models import (
    StepResult,
    ExecutionResult,
    VerificationResult,
    RiskLevel,
    ExecutionStatus,
)
from app.llm.ops_center_client import OpsCenterLLMClient

logger = logging.getLogger(__name__)


DEFAULT_VERIFIER_PROMPT = """You are a result verifier for an AI agent system. Analyze the execution result and assess quality.

Output ONLY valid JSON with this exact schema:
{
    "confidence": 0.0 to 1.0,
    "issues": ["list of any issues found"],
    "hallucination_risk": "low|medium|high",
    "security_risk": "low|medium|high",
    "retry_recommended": true|false,
    "next_action": "continue|retry|escalate_to_strong_model|ask_user"
}

VERIFICATION RULES:
- Missing expected artifact => confidence <= 0.6
- Web-influenced decisions => hallucination_risk >= medium
- Credentials/secrets in output => security_risk = high
- Vague or incomplete response => confidence <= 0.5
- Error or exception in output => confidence <= 0.3
- High risk + low confidence => next_action = escalate_to_strong_model
- Security risk high => next_action = ask_user
- JSON only, no markdown, no explanation
"""


class ResultVerifier:
    """Verifies execution results and recommends next actions"""

    # Keywords indicating potential issues
    HALLUCINATION_INDICATORS = [
        "i think", "probably", "maybe", "not sure", "assume",
        "hypothetically", "in theory", "could be", "might be",
    ]

    SECURITY_RISK_INDICATORS = [
        "password", "api_key", "secret", "token", "credential",
        "private_key", "auth", "bearer", "jwt", "session_id",
    ]

    INCOMPLETE_INDICATORS = [
        "todo", "not implemented", "placeholder", "coming soon",
        "work in progress", "incomplete", "partial",
    ]

    def __init__(
        self,
        llm_client: Optional[OpsCenterLLMClient] = None,
        prompt_path: Optional[Path] = None,
        confidence_threshold: float = 0.7,
        use_llm_verification: bool = True,
    ):
        self.llm_client = llm_client or OpsCenterLLMClient()
        self.confidence_threshold = confidence_threshold
        self.use_llm_verification = use_llm_verification
        self.prompt = self._load_prompt(prompt_path)

    def _load_prompt(self, prompt_path: Optional[Path]) -> str:
        """Load verifier prompt from file or use default"""
        if prompt_path and prompt_path.exists():
            return prompt_path.read_text()

        default_path = Path(__file__).parent.parent.parent / "prompts" / "verifier.md"
        if default_path.exists():
            return default_path.read_text()

        return DEFAULT_VERIFIER_PROMPT

    async def verify(
        self,
        result: ExecutionResult,
        expected_outputs: list[str] = None,
        user_id: str = "anonymous",
    ) -> VerificationResult:
        """
        Verify an execution result.

        Args:
            result: The execution result to verify
            expected_outputs: List of expected artifacts/outputs
            user_id: User ID for LLM calls

        Returns:
            VerificationResult with confidence and recommendations
        """
        logger.info(f"Verifying workflow {result.workflow_id}")

        # Start with heuristic verification
        heuristic_result = self._heuristic_verify(result, expected_outputs)

        # If heuristics indicate issues or we want LLM verification
        if self.use_llm_verification and (
            heuristic_result.confidence < self.confidence_threshold or
            heuristic_result.hallucination_risk != RiskLevel.LOW or
            heuristic_result.security_risk != RiskLevel.LOW
        ):
            # Use LLM for deeper verification
            llm_result = await self._llm_verify(result, expected_outputs, user_id)

            # Combine results (take the more conservative)
            return self._combine_results(heuristic_result, llm_result)

        return heuristic_result

    def _heuristic_verify(
        self,
        result: ExecutionResult,
        expected_outputs: list[str] = None,
    ) -> VerificationResult:
        """Quick heuristic verification without LLM"""
        issues = []
        confidence = 1.0
        hallucination_risk = RiskLevel.LOW
        security_risk = RiskLevel.LOW

        # Check execution status
        if result.status == ExecutionStatus.FAILED:
            confidence = 0.2
            issues.append("Execution failed")
        elif result.status == ExecutionStatus.BLOCKED:
            confidence = 0.4
            issues.append("Execution blocked")

        # Check for errors in step results
        for step_result in result.step_results:
            if step_result.error:
                confidence -= 0.2
                issues.append(f"Step {step_result.step_id} error: {step_result.error}")

        # Check expected outputs
        if expected_outputs:
            missing = set(expected_outputs) - set(result.artifacts)
            if missing:
                confidence -= 0.3
                issues.append(f"Missing expected outputs: {', '.join(missing)}")

        # Check output content for issues
        output_text = result.final_output or ""
        output_lower = output_text.lower()

        # Check for hallucination indicators
        hallucination_count = sum(
            1 for indicator in self.HALLUCINATION_INDICATORS
            if indicator in output_lower
        )
        if hallucination_count > 2:
            hallucination_risk = RiskLevel.HIGH
            confidence -= 0.2
            issues.append("Multiple uncertainty indicators in output")
        elif hallucination_count > 0:
            hallucination_risk = RiskLevel.MEDIUM

        # Check for security risks
        security_count = sum(
            1 for indicator in self.SECURITY_RISK_INDICATORS
            if indicator in output_lower
        )
        if security_count > 0:
            security_risk = RiskLevel.HIGH
            issues.append("Potential credentials/secrets in output")

        # Check for incomplete indicators
        if any(ind in output_lower for ind in self.INCOMPLETE_INDICATORS):
            confidence -= 0.2
            issues.append("Output appears incomplete")

        # Clamp confidence
        confidence = max(0.0, min(1.0, confidence))

        # Determine next action
        if security_risk == RiskLevel.HIGH:
            next_action = "ask_user"
        elif confidence < 0.5:
            next_action = "escalate_to_strong_model"
        elif confidence < self.confidence_threshold:
            next_action = "retry"
        else:
            next_action = "continue"

        return VerificationResult(
            confidence=confidence,
            issues=issues,
            hallucination_risk=hallucination_risk,
            security_risk=security_risk,
            retry_recommended=confidence < self.confidence_threshold,
            next_action=next_action,
        )

    async def _llm_verify(
        self,
        result: ExecutionResult,
        expected_outputs: list[str] = None,
        user_id: str = "anonymous",
    ) -> VerificationResult:
        """Use LLM for deeper verification"""
        try:
            # Build context for LLM
            context = {
                "status": result.status.value,
                "step_count": len(result.step_results),
                "artifacts": result.artifacts,
                "expected_outputs": expected_outputs or [],
                "output_preview": (result.final_output or "")[:2000],
                "errors": [
                    r.error for r in result.step_results if r.error
                ],
            }

            response = await self.llm_client.chat_completion(
                messages=[
                    {"role": "system", "content": self.prompt},
                    {"role": "user", "content": f"Verify this result:\n{json.dumps(context, indent=2)}"}
                ],
                model="local",  # Use local model for verification
                temperature=0.1,
                max_tokens=500,
                user_id=user_id
            )

            result_text = response["choices"][0]["message"]["content"]
            result_json = self._parse_json_response(result_text)

            return VerificationResult(
                confidence=float(result_json.get("confidence", 0.5)),
                issues=result_json.get("issues", []),
                hallucination_risk=RiskLevel(result_json.get("hallucination_risk", "low")),
                security_risk=RiskLevel(result_json.get("security_risk", "low")),
                retry_recommended=result_json.get("retry_recommended", False),
                next_action=result_json.get("next_action", "continue"),
            )

        except Exception as e:
            logger.error(f"LLM verification failed: {e}")
            # Return neutral result on failure
            return VerificationResult(
                confidence=0.5,
                issues=[f"LLM verification failed: {str(e)}"],
                hallucination_risk=RiskLevel.MEDIUM,
                security_risk=RiskLevel.LOW,
                retry_recommended=True,
                next_action="retry",
            )

    def _parse_json_response(self, text: str) -> dict:
        """Parse JSON from verifier response"""
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            if end > start:
                try:
                    return json.loads(text[start:end].strip())
                except json.JSONDecodeError:
                    pass

        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError:
                pass

        return {}

    def _combine_results(
        self,
        heuristic: VerificationResult,
        llm: VerificationResult,
    ) -> VerificationResult:
        """Combine heuristic and LLM verification results (conservative)"""
        return VerificationResult(
            # Take lower confidence
            confidence=min(heuristic.confidence, llm.confidence),
            # Combine issues
            issues=list(set(heuristic.issues + llm.issues)),
            # Take higher risk
            hallucination_risk=max(
                heuristic.hallucination_risk,
                llm.hallucination_risk,
                key=lambda r: ["low", "medium", "high"].index(r.value)
            ),
            security_risk=max(
                heuristic.security_risk,
                llm.security_risk,
                key=lambda r: ["low", "medium", "high"].index(r.value)
            ),
            # Either recommends retry
            retry_recommended=heuristic.retry_recommended or llm.retry_recommended,
            # Take more conservative action
            next_action=self._more_conservative_action(
                heuristic.next_action,
                llm.next_action
            ),
        )

    def _more_conservative_action(self, a1: str, a2: str) -> str:
        """Return the more conservative of two actions"""
        priority = ["continue", "retry", "escalate_to_strong_model", "ask_user"]
        return a1 if priority.index(a1) > priority.index(a2) else a2

    async def verify_step(
        self,
        step_result: StepResult,
        expected_output: Optional[str] = None,
    ) -> VerificationResult:
        """Quick verification of a single step result"""
        # Create a minimal execution result for verification
        exec_result = ExecutionResult(
            workflow_id="step_verification",
            status=step_result.status,
            step_results=[step_result],
            artifacts=step_result.artifacts,
            final_output=step_result.output,
        )

        expected = [expected_output] if expected_output else None
        return await self.verify(exec_result, expected)
