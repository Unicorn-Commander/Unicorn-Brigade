"""
Research Worker - Information gathering and synthesis

Capabilities:
- Web search and summarization
- Document analysis
- Multi-source research
- Citation tracking
"""

from typing import Dict, Any, List, Optional
from app.workers.base import BaseWorker, WorkerResult, WorkerStatus, WorkerArtifact
import logging

logger = logging.getLogger(__name__)


RESEARCH_SYSTEM_PROMPT = """You are an expert research assistant. Your task is to:

1. Gather and synthesize information on the given topic
2. Identify key findings and insights
3. Provide well-structured summaries with citations when available
4. Flag any uncertainties or areas needing verification

Output Format:
- Summary: Brief overview (2-3 sentences)
- Key Findings: Bullet points of main discoveries
- Details: In-depth analysis
- Sources: Any referenced materials
- Confidence: Your confidence level (high/medium/low) with reasoning

Be thorough but concise. Focus on accuracy over comprehensiveness."""


class ResearchWorker(BaseWorker):
    """
    Worker for research and information gathering tasks.

    Produces structured research reports with findings and citations.
    """

    name = "ResearchWorker"
    description = "Research and information synthesis"
    default_timeout = 180  # 3 minutes for research tasks

    async def _execute_impl(
        self,
        task: str,
        context: Dict[str, Any],
        user_id: str,
        model: str,
    ) -> WorkerResult:
        """Execute research task"""
        logger.info(f"{self.name}: Researching - {task[:100]}...")

        # Build context-aware prompt
        context_text = self._build_context(context)

        user_prompt = f"""Research Task: {task}

{context_text}

Please provide a comprehensive research summary following the output format specified."""

        try:
            # Call LLM
            response = await self.call_llm(
                messages=[
                    {"role": "system", "content": RESEARCH_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                model=model,
                temperature=0.7,
                max_tokens=2500,
                user_id=user_id,
            )

            content = response["content"]
            usage = response.get("usage", {})

            # Parse and structure the response
            findings = self._extract_findings(content)
            confidence = self._extract_confidence(content)

            # Create artifacts
            artifacts = [
                self.create_artifact(
                    name="research_summary",
                    content=content,
                    artifact_type="text",
                    metadata={"confidence": confidence},
                ),
                self.create_artifact(
                    name="key_findings",
                    content=findings,
                    artifact_type="json",
                ),
            ]

            return WorkerResult(
                worker_name=self.name,
                status=WorkerStatus.COMPLETED,
                output=content,
                artifacts=artifacts,
                tokens_input=usage.get("prompt_tokens", 0),
                tokens_output=usage.get("completion_tokens", 0),
                model_used=response.get("model"),
                provider=response.get("provider"),
            )

        except Exception as e:
            logger.error(f"{self.name}: Research failed - {e}")
            raise

    def _build_context(self, context: Dict[str, Any]) -> str:
        """Build context section for prompt"""
        parts = []

        if context.get("previous_findings"):
            parts.append(f"Previous findings:\n{context['previous_findings']}")

        if context.get("constraints"):
            parts.append(f"Constraints:\n{context['constraints']}")

        if context.get("focus_areas"):
            areas = context["focus_areas"]
            if isinstance(areas, list):
                areas = ", ".join(areas)
            parts.append(f"Focus areas: {areas}")

        return "\n\n".join(parts) if parts else ""

    def _extract_findings(self, content: str) -> List[str]:
        """Extract key findings from response"""
        findings = []
        lines = content.split('\n')
        in_findings = False

        for line in lines:
            line_lower = line.lower().strip()

            # Detect findings section
            if 'key findings' in line_lower or 'main findings' in line_lower:
                in_findings = True
                continue

            # Exit findings section on new section header
            if in_findings and line.strip() and line.strip().endswith(':'):
                if not line.lower().strip().startswith('-'):
                    in_findings = False
                    continue

            # Extract bullet points
            if in_findings:
                line = line.strip()
                if line.startswith('-') or line.startswith('•') or line.startswith('*'):
                    findings.append(line[1:].strip())
                elif len(line) > 0 and line[0].isdigit() and '.' in line[:4]:
                    findings.append(line.split('.', 1)[1].strip())

        return findings[:10]  # Cap at 10 findings

    def _extract_confidence(self, content: str) -> str:
        """Extract confidence level from response"""
        content_lower = content.lower()

        # Look for explicit confidence statement
        if 'confidence: high' in content_lower or 'high confidence' in content_lower:
            return "high"
        elif 'confidence: low' in content_lower or 'low confidence' in content_lower:
            return "low"
        elif 'confidence:' in content_lower or 'medium confidence' in content_lower:
            return "medium"

        # Default based on hedging language
        hedges = ['might', 'could', 'possibly', 'uncertain', 'unclear']
        hedge_count = sum(1 for h in hedges if h in content_lower)

        if hedge_count >= 3:
            return "low"
        elif hedge_count >= 1:
            return "medium"
        return "high"


class DeepResearchWorker(ResearchWorker):
    """
    Extended research worker for multi-source deep dives.

    Uses longer timeout and more comprehensive prompts.
    """

    name = "DeepResearchWorker"
    description = "Deep multi-source research"
    default_timeout = 300  # 5 minutes

    async def _execute_impl(
        self,
        task: str,
        context: Dict[str, Any],
        user_id: str,
        model: str,
    ) -> WorkerResult:
        """Execute deep research with multiple passes"""

        # First pass: broad research
        broad_result = await super()._execute_impl(
            task=f"Provide a broad overview of: {task}",
            context=context,
            user_id=user_id,
            model=model,
        )

        if broad_result.status != WorkerStatus.COMPLETED:
            return broad_result

        # Second pass: deep dive on key findings
        findings = []
        for artifact in broad_result.artifacts:
            if artifact.name == "key_findings":
                findings = artifact.content
                break

        if findings and len(findings) > 0:
            # Focus on top 3 findings for deep dive
            focus_areas = findings[:3]
            context_updated = {
                **context,
                "previous_findings": broad_result.output,
                "focus_areas": focus_areas,
            }

            deep_result = await super()._execute_impl(
                task=f"Deep dive into these aspects of {task}: {', '.join(focus_areas)}",
                context=context_updated,
                user_id=user_id,
                model=model,
            )

            # Merge artifacts
            all_artifacts = broad_result.artifacts + deep_result.artifacts

            return WorkerResult(
                worker_name=self.name,
                status=WorkerStatus.COMPLETED,
                output=f"## Broad Research\n\n{broad_result.output}\n\n## Deep Dive\n\n{deep_result.output}",
                artifacts=all_artifacts,
                tokens_input=broad_result.tokens_input + deep_result.tokens_input,
                tokens_output=broad_result.tokens_output + deep_result.tokens_output,
                model_used=deep_result.model_used,
                provider=deep_result.provider,
            )

        return broad_result
