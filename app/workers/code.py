"""
Code Worker - Code generation, analysis, and refactoring

Capabilities:
- Code generation from specifications
- Code review and analysis
- Refactoring suggestions
- Bug fixing
- Documentation generation
"""

from typing import Dict, Any, List, Optional
from app.workers.base import BaseWorker, WorkerResult, WorkerStatus, WorkerArtifact
import logging
import re

logger = logging.getLogger(__name__)


CODE_SYSTEM_PROMPT = """You are an expert software engineer. Your task is to:

1. Write clean, well-documented, production-ready code
2. Follow best practices for the language/framework
3. Consider edge cases and error handling
4. Keep code simple and maintainable

Output Format:
- Brief explanation of the approach
- Complete code with comments
- Usage example
- Any assumptions or limitations

Be precise. Prefer clarity over cleverness. Test your logic mentally before providing code."""


CODE_REVIEW_PROMPT = """You are a senior code reviewer. Analyze the provided code for:

1. **Correctness**: Logic errors, edge cases, potential bugs
2. **Security**: Vulnerabilities, injection risks, data exposure
3. **Performance**: Inefficiencies, O(n) improvements possible
4. **Maintainability**: Readability, naming, structure
5. **Best Practices**: Language idioms, patterns, anti-patterns

Output Format:
- Summary (1-2 sentences)
- Issues Found (severity: critical/warning/info)
- Suggested Improvements
- Refactored Code (if applicable)

Be constructive. Focus on impactful issues."""


class CodeWorker(BaseWorker):
    """
    Worker for code generation and analysis tasks.

    Produces code artifacts with language detection and formatting.
    """

    name = "CodeWorker"
    description = "Code generation and analysis"
    default_timeout = 120  # 2 minutes

    async def _execute_impl(
        self,
        task: str,
        context: Dict[str, Any],
        user_id: str,
        model: str,
    ) -> WorkerResult:
        """Execute code task"""
        logger.info(f"{self.name}: Processing - {task[:100]}...")

        # Detect task type
        task_type = self._detect_task_type(task, context)

        if task_type == "review":
            return await self._execute_review(task, context, user_id, model)
        elif task_type == "refactor":
            return await self._execute_refactor(task, context, user_id, model)
        else:
            return await self._execute_generation(task, context, user_id, model)

    async def _execute_generation(
        self,
        task: str,
        context: Dict[str, Any],
        user_id: str,
        model: str,
    ) -> WorkerResult:
        """Generate code from specification"""
        context_text = self._build_context(context)

        user_prompt = f"""Code Task: {task}

{context_text}

Generate complete, working code following best practices."""

        try:
            response = await self.call_llm(
                messages=[
                    {"role": "system", "content": CODE_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                model=model,
                temperature=0.3,  # Lower for code generation
                max_tokens=3000,
                user_id=user_id,
            )

            content = response["content"]
            usage = response.get("usage", {})

            # Extract code blocks
            code_blocks = self._extract_code_blocks(content)
            primary_language = self._detect_language(content, code_blocks)

            # Create artifacts
            artifacts = [
                self.create_artifact(
                    name="code_response",
                    content=content,
                    artifact_type="text",
                ),
            ]

            # Add individual code blocks as artifacts
            for i, block in enumerate(code_blocks):
                artifacts.append(
                    self.create_artifact(
                        name=f"code_block_{i+1}",
                        content=block["code"],
                        artifact_type="code",
                        metadata={
                            "language": block["language"],
                            "index": i,
                        },
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
            logger.error(f"{self.name}: Code generation failed - {e}")
            raise

    async def _execute_review(
        self,
        task: str,
        context: Dict[str, Any],
        user_id: str,
        model: str,
    ) -> WorkerResult:
        """Review provided code"""
        code_to_review = context.get("code", "")

        user_prompt = f"""Review Request: {task}

Code to Review:
```
{code_to_review}
```

Provide a thorough code review."""

        try:
            response = await self.call_llm(
                messages=[
                    {"role": "system", "content": CODE_REVIEW_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                model=model,
                temperature=0.5,
                max_tokens=2500,
                user_id=user_id,
            )

            content = response["content"]
            usage = response.get("usage", {})

            # Extract issues
            issues = self._extract_issues(content)

            artifacts = [
                self.create_artifact(
                    name="review_report",
                    content=content,
                    artifact_type="text",
                ),
                self.create_artifact(
                    name="issues_found",
                    content=issues,
                    artifact_type="json",
                ),
            ]

            # Extract any refactored code
            code_blocks = self._extract_code_blocks(content)
            if code_blocks:
                artifacts.append(
                    self.create_artifact(
                        name="suggested_refactor",
                        content=code_blocks[0]["code"],
                        artifact_type="code",
                        metadata={"language": code_blocks[0]["language"]},
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
            logger.error(f"{self.name}: Code review failed - {e}")
            raise

    async def _execute_refactor(
        self,
        task: str,
        context: Dict[str, Any],
        user_id: str,
        model: str,
    ) -> WorkerResult:
        """Refactor provided code"""
        code_to_refactor = context.get("code", "")

        refactor_prompt = """You are refactoring code. Goals:
1. Improve readability and maintainability
2. Apply appropriate design patterns
3. Reduce complexity
4. Improve performance where obvious
5. Add/improve documentation

Provide the refactored code with explanations of changes."""

        user_prompt = f"""Refactor Request: {task}

Original Code:
```
{code_to_refactor}
```

Provide the refactored version with explanations."""

        try:
            response = await self.call_llm(
                messages=[
                    {"role": "system", "content": refactor_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                model=model,
                temperature=0.3,
                max_tokens=3000,
                user_id=user_id,
            )

            content = response["content"]
            usage = response.get("usage", {})
            code_blocks = self._extract_code_blocks(content)

            artifacts = [
                self.create_artifact(
                    name="refactor_explanation",
                    content=content,
                    artifact_type="text",
                ),
            ]

            if code_blocks:
                artifacts.append(
                    self.create_artifact(
                        name="refactored_code",
                        content=code_blocks[0]["code"],
                        artifact_type="code",
                        metadata={"language": code_blocks[0]["language"]},
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
            logger.error(f"{self.name}: Refactor failed - {e}")
            raise

    def _detect_task_type(self, task: str, context: Dict[str, Any]) -> str:
        """Detect whether this is generation, review, or refactor"""
        task_lower = task.lower()

        if "review" in task_lower or "analyze" in task_lower or "check" in task_lower:
            return "review"
        elif "refactor" in task_lower or "improve" in task_lower or "optimize" in task_lower:
            return "refactor"
        elif context.get("code") and ("fix" in task_lower or "bug" in task_lower):
            return "review"

        return "generate"

    def _build_context(self, context: Dict[str, Any]) -> str:
        """Build context section for prompt"""
        parts = []

        if context.get("language"):
            parts.append(f"Language: {context['language']}")

        if context.get("framework"):
            parts.append(f"Framework: {context['framework']}")

        if context.get("existing_code"):
            parts.append(f"Existing code:\n```\n{context['existing_code']}\n```")

        if context.get("requirements"):
            parts.append(f"Requirements:\n{context['requirements']}")

        return "\n\n".join(parts) if parts else ""

    def _extract_code_blocks(self, content: str) -> List[Dict[str, str]]:
        """Extract code blocks from markdown"""
        code_blocks = []
        pattern = r'```(\w*)\n(.*?)```'
        matches = re.findall(pattern, content, re.DOTALL)

        for lang, code in matches:
            code_blocks.append({
                "language": lang or "text",
                "code": code.strip(),
            })

        return code_blocks

    def _detect_language(
        self,
        content: str,
        code_blocks: List[Dict[str, str]],
    ) -> str:
        """Detect primary programming language"""
        # Check code blocks first
        for block in code_blocks:
            if block["language"] and block["language"] != "text":
                return block["language"]

        # Fallback to content analysis
        content_lower = content.lower()

        lang_indicators = {
            "python": ["python", "def ", "import ", "class ", ".py"],
            "javascript": ["javascript", "const ", "let ", "function ", ".js"],
            "typescript": ["typescript", "interface ", ": string", ": number", ".ts"],
            "rust": ["rust", "fn ", "let mut", "impl ", ".rs"],
            "go": ["golang", "func ", "package ", "go ", ".go"],
            "java": ["java", "public class", "private ", ".java"],
        }

        for lang, indicators in lang_indicators.items():
            if any(ind in content_lower for ind in indicators):
                return lang

        return "unknown"

    def _extract_issues(self, content: str) -> List[Dict[str, str]]:
        """Extract issues from code review"""
        issues = []
        lines = content.split('\n')

        current_severity = "info"

        for line in lines:
            line_lower = line.lower().strip()

            # Detect severity
            if 'critical' in line_lower:
                current_severity = "critical"
            elif 'warning' in line_lower:
                current_severity = "warning"
            elif 'info' in line_lower or 'note' in line_lower:
                current_severity = "info"

            # Extract issues (bullet points)
            if line.strip().startswith('-') or line.strip().startswith('•'):
                issue_text = line.strip()[1:].strip()
                if issue_text:
                    issues.append({
                        "severity": current_severity,
                        "issue": issue_text,
                    })

        return issues
