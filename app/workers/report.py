"""
Report Worker - Report and document generation

Capabilities:
- Executive summaries
- Technical reports
- Analysis documents
- Formatted output (Markdown, HTML)
"""

from typing import Dict, Any, List, Optional
from app.workers.base import BaseWorker, WorkerResult, WorkerStatus, WorkerArtifact
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


REPORT_SYSTEM_PROMPT = """You are an expert report writer. Your task is to:

1. Create clear, well-structured reports
2. Adapt tone and depth to the audience (executive, technical, general)
3. Include relevant data and insights
4. Use proper formatting (headers, bullets, tables)

Report Structure:
- Executive Summary (key takeaways)
- Main Body (organized by sections)
- Conclusions & Recommendations
- Appendix (supporting data, if needed)

Be concise but comprehensive. Prioritize clarity and actionability."""


class ReportType:
    """Report type constants"""
    EXECUTIVE_SUMMARY = "executive_summary"
    TECHNICAL = "technical"
    ANALYSIS = "analysis"
    BRIEF = "brief"
    DETAILED = "detailed"


class ReportWorker(BaseWorker):
    """
    Worker for generating reports and documents.

    Produces formatted reports tailored to audience and purpose.
    """

    name = "ReportWorker"
    description = "Report and document generation"
    default_timeout = 180  # 3 minutes for comprehensive reports

    async def _execute_impl(
        self,
        task: str,
        context: Dict[str, Any],
        user_id: str,
        model: str,
    ) -> WorkerResult:
        """Generate report"""
        logger.info(f"{self.name}: Generating report - {task[:100]}...")

        report_type = context.get("report_type", ReportType.ANALYSIS)
        audience = context.get("audience", "general")
        format_type = context.get("format", "markdown")

        # Build report prompt based on type
        type_prompt = self._get_type_prompt(report_type, audience)
        source_data = self._format_source_data(context)

        user_prompt = f"""Report Request: {task}

{type_prompt}

Source Data/Inputs:
{source_data}

Generate a complete {report_type.replace('_', ' ')} report in {format_type} format."""

        try:
            response = await self.call_llm(
                messages=[
                    {"role": "system", "content": REPORT_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                model=model,
                temperature=0.6,
                max_tokens=4000,
                user_id=user_id,
            )

            content = response["content"]
            usage = response.get("usage", {})

            # Extract sections
            sections = self._extract_sections(content)

            # Create artifacts
            artifacts = [
                self.create_artifact(
                    name="full_report",
                    content=content,
                    artifact_type="text",
                    metadata={
                        "report_type": report_type,
                        "audience": audience,
                        "format": format_type,
                        "generated_at": datetime.utcnow().isoformat(),
                    },
                ),
                self.create_artifact(
                    name="sections",
                    content=sections,
                    artifact_type="json",
                ),
            ]

            # Extract executive summary if present
            exec_summary = self._extract_executive_summary(content)
            if exec_summary:
                artifacts.append(
                    self.create_artifact(
                        name="executive_summary",
                        content=exec_summary,
                        artifact_type="text",
                    )
                )

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
            logger.error(f"{self.name}: Report generation failed - {e}")
            raise

    def _get_type_prompt(self, report_type: str, audience: str) -> str:
        """Get specific instructions for report type"""
        prompts = {
            ReportType.EXECUTIVE_SUMMARY: """
Create a concise executive summary (1-2 pages max):
- Lead with key findings and recommendations
- Use bullet points for quick scanning
- Focus on business impact and decisions needed
- Avoid technical jargon""",

            ReportType.TECHNICAL: """
Create a detailed technical report:
- Include methodology and approach
- Show data, calculations, and evidence
- Use technical terminology appropriately
- Include diagrams/tables where helpful
- Add appendix for raw data""",

            ReportType.ANALYSIS: """
Create an analytical report:
- Present findings objectively
- Include supporting evidence
- Discuss limitations and assumptions
- Offer balanced recommendations""",

            ReportType.BRIEF: """
Create a brief memo (1 page max):
- Get to the point quickly
- Bullet points preferred
- Action items clearly marked
- No background unless essential""",

            ReportType.DETAILED: """
Create a comprehensive report:
- Full background and context
- Thorough analysis
- Multiple perspectives
- Detailed recommendations with rationale""",
        }

        base_prompt = prompts.get(report_type, prompts[ReportType.ANALYSIS])

        audience_adjustments = {
            "executive": "Use business language. Focus on ROI, risk, and strategic impact.",
            "technical": "Include technical details. Assume domain expertise.",
            "general": "Use accessible language. Define technical terms.",
            "legal": "Be precise and formal. Note caveats and limitations.",
        }

        adjustment = audience_adjustments.get(audience, "")
        if adjustment:
            base_prompt += f"\n\nAudience ({audience}): {adjustment}"

        return base_prompt

    def _format_source_data(self, context: Dict[str, Any]) -> str:
        """Format source data for the prompt"""
        parts = []

        if context.get("data"):
            data = context["data"]
            if isinstance(data, dict):
                import json
                parts.append(f"Data:\n```json\n{json.dumps(data, indent=2)}\n```")
            elif isinstance(data, list):
                import json
                parts.append(f"Data:\n```json\n{json.dumps(data, indent=2)}\n```")
            else:
                parts.append(f"Data:\n{data}")

        if context.get("findings"):
            findings = context["findings"]
            if isinstance(findings, list):
                findings = "\n".join(f"- {f}" for f in findings)
            parts.append(f"Findings:\n{findings}")

        if context.get("research"):
            parts.append(f"Research:\n{context['research']}")

        if context.get("previous_reports"):
            parts.append(f"Previous Reports:\n{context['previous_reports']}")

        if context.get("constraints"):
            parts.append(f"Constraints:\n{context['constraints']}")

        return "\n\n".join(parts) if parts else "No specific source data provided."

    def _extract_sections(self, content: str) -> List[Dict[str, str]]:
        """Extract sections from markdown report"""
        sections = []
        current_section = {"title": "Introduction", "content": "", "level": 0}
        lines = content.split('\n')

        for line in lines:
            # Detect headers
            if line.startswith('#'):
                # Save previous section
                if current_section["content"].strip():
                    sections.append(current_section)

                # Count header level
                level = len(line) - len(line.lstrip('#'))
                title = line.lstrip('#').strip()

                current_section = {
                    "title": title,
                    "content": "",
                    "level": level,
                }
            else:
                current_section["content"] += line + "\n"

        # Save last section
        if current_section["content"].strip():
            sections.append(current_section)

        return sections

    def _extract_executive_summary(self, content: str) -> Optional[str]:
        """Extract executive summary section"""
        content_lower = content.lower()

        # Find executive summary section
        patterns = [
            "executive summary",
            "summary",
            "key findings",
            "tldr",
            "overview",
        ]

        for pattern in patterns:
            start_idx = content_lower.find(pattern)
            if start_idx != -1:
                # Find the end of this section (next header or end)
                section_start = content.find('\n', start_idx)
                if section_start == -1:
                    continue

                # Find next section header
                remaining = content[section_start:]
                next_header = -1
                for i, char in enumerate(remaining):
                    if char == '#' and (i == 0 or remaining[i-1] == '\n'):
                        next_header = i
                        break

                if next_header != -1:
                    return remaining[:next_header].strip()
                else:
                    # Return first 500 chars if no next header
                    return remaining[:500].strip()

        return None


class SummaryWorker(ReportWorker):
    """
    Specialized worker for quick summaries.

    Optimized for speed and conciseness.
    """

    name = "SummaryWorker"
    description = "Quick summary generation"
    default_timeout = 60  # 1 minute for summaries

    async def _execute_impl(
        self,
        task: str,
        context: Dict[str, Any],
        user_id: str,
        model: str,
    ) -> WorkerResult:
        """Generate quick summary"""
        source_text = context.get("text", context.get("source", ""))
        max_length = context.get("max_length", 200)

        summary_prompt = f"""Summarize the following in {max_length} words or less.

Focus on:
- Main points only
- Key facts and figures
- Actionable insights

Be direct and concise."""

        user_prompt = f"""Summarize this:

{source_text}

Provide a clear, concise summary."""

        try:
            response = await self.call_llm(
                messages=[
                    {"role": "system", "content": summary_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                model=model,
                temperature=0.5,
                max_tokens=500,
                user_id=user_id,
            )

            content = response["content"]
            usage = response.get("usage", {})

            # Count words
            word_count = len(content.split())

            artifacts = [
                self.create_artifact(
                    name="summary",
                    content=content,
                    artifact_type="text",
                    metadata={
                        "word_count": word_count,
                        "max_length": max_length,
                    },
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
            logger.error(f"{self.name}: Summary generation failed - {e}")
            raise


class DigestWorker(ReportWorker):
    """
    Worker for daily/weekly digests.

    Aggregates multiple sources into formatted digest.
    """

    name = "DigestWorker"
    description = "Digest and newsletter generation"
    default_timeout = 240  # 4 minutes for comprehensive digests

    async def _execute_impl(
        self,
        task: str,
        context: Dict[str, Any],
        user_id: str,
        model: str,
    ) -> WorkerResult:
        """Generate digest"""
        items = context.get("items", [])
        digest_type = context.get("digest_type", "daily")

        if not items:
            return WorkerResult(
                worker_name=self.name,
                status=WorkerStatus.FAILED,
                error="No items provided for digest",
                error_type="ValidationError",
            )

        # Format items
        items_text = ""
        for i, item in enumerate(items, 1):
            if isinstance(item, dict):
                title = item.get("title", f"Item {i}")
                content = item.get("content", item.get("summary", ""))
                source = item.get("source", "")
                items_text += f"\n{i}. {title}\n{content}\n"
                if source:
                    items_text += f"Source: {source}\n"
            else:
                items_text += f"\n{i}. {item}\n"

        digest_prompt = f"""Create a {digest_type} digest from the following items.

Structure:
- Highlight: Top 1-2 most important items
- Quick Takes: Brief summary of each item (1-2 sentences)
- Key Takeaways: 3-5 bullet points
- Worth Watching: Items that may develop further

Keep it scannable and engaging."""

        user_prompt = f"""{task}

Items to include:
{items_text}

Generate the digest in markdown format."""

        try:
            response = await self.call_llm(
                messages=[
                    {"role": "system", "content": digest_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                model=model,
                temperature=0.7,
                max_tokens=3000,
                user_id=user_id,
            )

            content = response["content"]
            usage = response.get("usage", {})

            artifacts = [
                self.create_artifact(
                    name="digest",
                    content=content,
                    artifact_type="text",
                    metadata={
                        "digest_type": digest_type,
                        "item_count": len(items),
                        "generated_at": datetime.utcnow().isoformat(),
                    },
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
            logger.error(f"{self.name}: Digest generation failed - {e}")
            raise
