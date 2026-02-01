"""
Code Review Bot Agent

Automatically reviews GitHub pull requests for:
- Bugs: Logic errors, null checks, edge cases
- Security: SQL injection, XSS, secrets in code
- Performance: N+1 queries, unnecessary loops
- Style: Naming, documentation, complexity
- Tests: Missing test coverage

Uses the MCP GitHub server or direct GitHub API via httpx.
"""

import os
import re
import asyncio
import logging
import hashlib
import hmac
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Any, Optional, Tuple

import httpx

from app.agents.base import BaseAgent
from app.llm.ops_center_client import OpsCenterLLMClient

logger = logging.getLogger(__name__)


# -------------------------------------------------------------------
# Configuration
# -------------------------------------------------------------------

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET", "")
CODE_REVIEW_ENABLED = os.getenv("CODE_REVIEW_ENABLED", "true").lower() == "true"

# Review thresholds
MAX_FILES_PER_REVIEW = int(os.getenv("MAX_FILES_PER_REVIEW", "50"))
MAX_DIFF_LINES = int(os.getenv("MAX_DIFF_LINES", "5000"))


# -------------------------------------------------------------------
# Data Models
# -------------------------------------------------------------------

class ReviewSeverity(Enum):
    """Severity levels for review comments"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ReviewCategory(Enum):
    """Categories of review findings"""
    BUG = "bug"
    SECURITY = "security"
    PERFORMANCE = "performance"
    STYLE = "style"
    TEST = "test"
    DOCUMENTATION = "documentation"


@dataclass
class ReviewComment:
    """A single review comment on a code change"""
    path: str
    line: int
    body: str
    category: ReviewCategory
    severity: ReviewSeverity
    suggestion: Optional[str] = None
    side: str = "RIGHT"  # LEFT (old) or RIGHT (new)

    def to_github_comment(self) -> Dict[str, Any]:
        """Convert to GitHub PR review comment format"""
        emoji_map = {
            ReviewCategory.BUG: "bug",
            ReviewCategory.SECURITY: "lock",
            ReviewCategory.PERFORMANCE: "zap",
            ReviewCategory.STYLE: "memo",
            ReviewCategory.TEST: "white_check_mark",
            ReviewCategory.DOCUMENTATION: "book",
        }
        emoji = emoji_map.get(self.category, "bulb")

        severity_prefix = {
            ReviewSeverity.CRITICAL: "**CRITICAL**",
            ReviewSeverity.ERROR: "**Error**",
            ReviewSeverity.WARNING: "Warning",
            ReviewSeverity.INFO: "Note",
        }
        prefix = severity_prefix.get(self.severity, "")

        body = f":{emoji}: {prefix}: {self.body}"
        if self.suggestion:
            body += f"\n\n**Suggestion:**\n```suggestion\n{self.suggestion}\n```"

        return {
            "path": self.path,
            "line": self.line,
            "body": body,
            "side": self.side,
        }


@dataclass
class FileChange:
    """Represents changes to a single file in a PR"""
    filename: str
    status: str  # added, modified, removed, renamed
    additions: int
    deletions: int
    patch: str
    language: str = ""

    @property
    def is_test_file(self) -> bool:
        """Check if this is a test file"""
        return any(pattern in self.filename.lower() for pattern in [
            "test_", "_test.", "tests/", "test/", ".spec.", ".test."
        ])


@dataclass
class ReviewResult:
    """Complete review result for a PR"""
    repo: str
    pr_number: int
    title: str
    comments: List[ReviewComment] = field(default_factory=list)
    summary: str = ""
    overall_status: str = "pending"  # approved, changes_requested, commented
    stats: Dict[str, int] = field(default_factory=dict)
    reviewed_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response"""
        return {
            "repo": self.repo,
            "pr_number": self.pr_number,
            "title": self.title,
            "comments": [
                {
                    "path": c.path,
                    "line": c.line,
                    "body": c.body,
                    "category": c.category.value,
                    "severity": c.severity.value,
                    "suggestion": c.suggestion,
                }
                for c in self.comments
            ],
            "summary": self.summary,
            "overall_status": self.overall_status,
            "stats": self.stats,
            "reviewed_at": self.reviewed_at.isoformat(),
        }


# -------------------------------------------------------------------
# Security Patterns
# -------------------------------------------------------------------

SECURITY_PATTERNS = {
    "sql_injection": [
        (r'execute\s*\(\s*["\'].*%s', "Potential SQL injection via string formatting"),
        (r'cursor\.execute\s*\(\s*f["\']', "Potential SQL injection via f-string"),
        (r'\.raw\s*\(\s*["\'].*\+', "Potential SQL injection in raw query"),
        (r'query\s*=\s*["\'].*\+.*["\'].*\+', "SQL query built with string concatenation"),
    ],
    "xss": [
        (r'innerHTML\s*=', "Direct innerHTML assignment - XSS risk"),
        (r'document\.write\s*\(', "document.write usage - XSS risk"),
        (r'dangerouslySetInnerHTML', "dangerouslySetInnerHTML usage - ensure sanitization"),
        (r'v-html\s*=', "Vue v-html directive - XSS risk if not sanitized"),
    ],
    "secrets": [
        (r'(?i)(password|secret|api_key|apikey|token|auth)\s*=\s*["\'][^"\']+["\']', "Hardcoded secret detected"),
        (r'(?i)bearer\s+[a-zA-Z0-9_\-\.]+', "Hardcoded bearer token"),
        (r'ghp_[a-zA-Z0-9]{36}', "GitHub personal access token"),
        (r'sk-[a-zA-Z0-9]{48}', "OpenAI API key pattern"),
        (r'-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY-----', "Private key in code"),
    ],
    "command_injection": [
        (r'subprocess\.\w+\s*\([^)]*shell\s*=\s*True', "Shell=True in subprocess - command injection risk"),
        (r'os\.system\s*\(', "os.system usage - prefer subprocess with shell=False"),
        (r'eval\s*\(', "eval() usage - code injection risk"),
        (r'exec\s*\(', "exec() usage - code injection risk"),
    ],
    "path_traversal": [
        (r'open\s*\([^)]*\+[^)]*\)', "File path built with concatenation - traversal risk"),
        (r'os\.path\.join\s*\([^)]*request', "User input in file path"),
    ],
}

# Performance anti-patterns
PERFORMANCE_PATTERNS = {
    "n_plus_1": [
        (r'for\s+\w+\s+in\s+.*\.objects\.all\(\)', "Potential N+1 query in loop"),
        (r'for\s+\w+\s+in\s+.*\.query\.all\(\)', "Potential N+1 query in loop"),
    ],
    "inefficient_loops": [
        (r'for\s+\w+\s+in\s+range\s*\(\s*len\s*\(', "Use enumerate() instead of range(len())"),
        (r'\+\s*=\s*\[', "List concatenation in loop - use extend()"),
    ],
    "blocking_calls": [
        (r'time\.sleep\s*\(', "Blocking sleep - consider async"),
        (r'requests\.(get|post|put|delete)\s*\(', "Blocking HTTP call - consider httpx async"),
    ],
}

# Style patterns by language
STYLE_PATTERNS = {
    "python": [
        (r'^import \*$', "Wildcard import - be explicit"),
        (r'except\s*:', "Bare except clause - specify exception type"),
        (r'print\s*\(', "Print statement - use logging"),
        (r'TODO|FIXME|HACK|XXX', "TODO/FIXME comment found"),
    ],
    "javascript": [
        (r'var\s+', "Use let/const instead of var"),
        (r'==\s+null|null\s+==', "Use === for null comparison"),
        (r'console\.log\s*\(', "console.log in code - remove or use proper logging"),
    ],
    "typescript": [
        (r':\s*any\b', "Avoid 'any' type - be more specific"),
        (r'@ts-ignore', "@ts-ignore comment - fix the type issue"),
        (r'as\s+any', "Type assertion to any - be more specific"),
    ],
}


# -------------------------------------------------------------------
# Language Detection
# -------------------------------------------------------------------

LANGUAGE_EXTENSIONS = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".jsx": "javascript",
    ".java": "java",
    ".go": "go",
    ".rs": "rust",
    ".rb": "ruby",
    ".php": "php",
    ".cs": "csharp",
    ".cpp": "cpp",
    ".c": "c",
    ".swift": "swift",
    ".kt": "kotlin",
    ".scala": "scala",
    ".sql": "sql",
    ".sh": "bash",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".json": "json",
    ".md": "markdown",
    ".html": "html",
    ".css": "css",
    ".scss": "scss",
}


def detect_language(filename: str) -> str:
    """Detect programming language from filename"""
    for ext, lang in LANGUAGE_EXTENSIONS.items():
        if filename.endswith(ext):
            return lang
    return "unknown"


# -------------------------------------------------------------------
# Code Reviewer Agent
# -------------------------------------------------------------------

class CodeReviewer(BaseAgent):
    """
    Automated Code Review Bot

    Reviews GitHub pull requests for bugs, security issues,
    performance problems, style violations, and test coverage.
    """

    def __init__(
        self,
        memory_manager=None,
        llm_client: Optional[OpsCenterLLMClient] = None,
        github_token: Optional[str] = None,
    ):
        super().__init__("CodeReviewer", memory_manager)
        self.llm_client = llm_client or OpsCenterLLMClient()
        self.github_token = github_token or GITHUB_TOKEN
        self.http_client = httpx.AsyncClient(
            timeout=60.0,
            headers={
                "Authorization": f"Bearer {self.github_token}",
                "Accept": "application/vnd.github.v3+json",
                "X-GitHub-Api-Version": "2022-11-28",
            }
        )

        # Review history (in-memory cache)
        self._review_cache: Dict[str, ReviewResult] = {}

    async def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute code review task"""
        repo = task.get("repo", "")
        pr_number = task.get("pr_number", 0)

        if not repo or not pr_number:
            return {
                "agent": self.name,
                "status": "error",
                "error": "Missing repo or pr_number",
            }

        try:
            result = await self.review_pr(repo, pr_number)
            return {
                "agent": self.name,
                "status": "completed",
                "result": result.to_dict(),
            }
        except Exception as e:
            logger.error(f"Code review failed: {e}")
            return {
                "agent": self.name,
                "status": "error",
                "error": str(e),
            }

    # -------------------------------------------------------------------
    # Main Review Entry Point
    # -------------------------------------------------------------------

    async def review_pr(self, repo: str, pr_number: int) -> ReviewResult:
        """
        Main entry point for reviewing a pull request.

        Args:
            repo: Repository in format "owner/repo"
            pr_number: Pull request number

        Returns:
            ReviewResult with all findings
        """
        if not CODE_REVIEW_ENABLED:
            raise ValueError("Code review is disabled")

        logger.info(f"Starting review for {repo}#{pr_number}")

        # Get PR details
        pr_info = await self._get_pr_info(repo, pr_number)

        # Get file changes
        diff_files = await self.get_pr_diff(repo, pr_number)

        if len(diff_files) > MAX_FILES_PER_REVIEW:
            logger.warning(f"PR has {len(diff_files)} files, limiting to {MAX_FILES_PER_REVIEW}")
            diff_files = diff_files[:MAX_FILES_PER_REVIEW]

        # Analyze changes
        comments = await self.analyze_changes(diff_files)

        # Run additional checks
        for file_change in diff_files:
            # Security checks
            security_comments = await self.check_security(file_change)
            comments.extend(security_comments)

            # Style checks
            style_comments = await self.check_style(file_change)
            comments.extend(style_comments)

        # Check for missing tests
        test_comments = self._check_test_coverage(diff_files)
        comments.extend(test_comments)

        # Generate summary using LLM
        summary = await self._generate_summary(pr_info, diff_files, comments)

        # Determine overall status
        overall_status = self._determine_status(comments)

        # Build result
        result = ReviewResult(
            repo=repo,
            pr_number=pr_number,
            title=pr_info.get("title", ""),
            comments=comments,
            summary=summary,
            overall_status=overall_status,
            stats={
                "files_reviewed": len(diff_files),
                "total_additions": sum(f.additions for f in diff_files),
                "total_deletions": sum(f.deletions for f in diff_files),
                "comments_count": len(comments),
                "critical_count": sum(1 for c in comments if c.severity == ReviewSeverity.CRITICAL),
                "error_count": sum(1 for c in comments if c.severity == ReviewSeverity.ERROR),
                "warning_count": sum(1 for c in comments if c.severity == ReviewSeverity.WARNING),
            }
        )

        # Cache result
        cache_key = f"{repo}#{pr_number}"
        self._review_cache[cache_key] = result

        logger.info(f"Review complete: {len(comments)} comments, status: {overall_status}")

        return result

    # -------------------------------------------------------------------
    # GitHub API Methods
    # -------------------------------------------------------------------

    async def _get_pr_info(self, repo: str, pr_number: int) -> Dict[str, Any]:
        """Get pull request information"""
        url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}"
        response = await self.http_client.get(url)
        response.raise_for_status()
        return response.json()

    async def get_pr_diff(self, repo: str, pr_number: int) -> List[FileChange]:
        """
        Fetch PR changes from GitHub.

        Args:
            repo: Repository in format "owner/repo"
            pr_number: Pull request number

        Returns:
            List of FileChange objects
        """
        url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}/files"
        response = await self.http_client.get(url)
        response.raise_for_status()

        files_data = response.json()
        changes = []

        total_lines = 0
        for file_data in files_data:
            patch = file_data.get("patch", "")
            lines = patch.count("\n") if patch else 0
            total_lines += lines

            if total_lines > MAX_DIFF_LINES:
                logger.warning(f"Reached max diff lines ({MAX_DIFF_LINES})")
                break

            change = FileChange(
                filename=file_data["filename"],
                status=file_data["status"],
                additions=file_data["additions"],
                deletions=file_data["deletions"],
                patch=patch,
                language=detect_language(file_data["filename"]),
            )
            changes.append(change)

        return changes

    async def post_review(
        self,
        repo: str,
        pr_number: int,
        comments: List[ReviewComment],
        summary: str = "",
        event: str = "COMMENT",  # APPROVE, REQUEST_CHANGES, COMMENT
    ) -> Dict[str, Any]:
        """
        Post review comments to GitHub PR.

        Args:
            repo: Repository in format "owner/repo"
            pr_number: Pull request number
            comments: List of review comments
            summary: Overall review summary
            event: Review event type

        Returns:
            GitHub API response
        """
        if not self.github_token:
            raise ValueError("GitHub token not configured")

        url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}/reviews"

        # Convert comments to GitHub format
        github_comments = [c.to_github_comment() for c in comments if c.line > 0]

        body = {
            "body": summary or "Automated code review completed.",
            "event": event,
        }

        if github_comments:
            body["comments"] = github_comments

        response = await self.http_client.post(url, json=body)
        response.raise_for_status()

        logger.info(f"Posted review to {repo}#{pr_number}: {len(github_comments)} comments")
        return response.json()

    # -------------------------------------------------------------------
    # Code Analysis Methods
    # -------------------------------------------------------------------

    async def analyze_changes(self, diff_files: List[FileChange]) -> List[ReviewComment]:
        """
        Analyze code changes using LLM for deeper analysis.

        Args:
            diff_files: List of file changes

        Returns:
            List of review comments
        """
        comments = []

        # Group files by language for batch analysis
        files_by_lang: Dict[str, List[FileChange]] = {}
        for file_change in diff_files:
            if file_change.patch and file_change.language != "unknown":
                files_by_lang.setdefault(file_change.language, []).append(file_change)

        # Analyze each language group
        for language, files in files_by_lang.items():
            batch_comments = await self._analyze_file_batch(files, language)
            comments.extend(batch_comments)

        return comments

    async def _analyze_file_batch(
        self,
        files: List[FileChange],
        language: str,
    ) -> List[ReviewComment]:
        """Analyze a batch of files using LLM"""
        if not files:
            return []

        # Build context for LLM
        file_summaries = []
        for f in files[:10]:  # Limit to 10 files per batch
            file_summaries.append(f"""
### {f.filename}
Status: {f.status} (+{f.additions}/-{f.deletions})
```{language}
{f.patch[:2000]}  # Truncate long patches
```
""")

        prompt = f"""You are an expert code reviewer. Analyze the following {language} code changes and identify issues.

Focus on:
1. Logic bugs, edge cases, null/undefined handling
2. Error handling gaps
3. Code clarity and maintainability
4. Potential race conditions or async issues

For each issue found, respond in this exact JSON format:
{{
    "issues": [
        {{
            "file": "filename.py",
            "line": 42,
            "category": "bug|security|performance|style|test|documentation",
            "severity": "info|warning|error|critical",
            "message": "Description of the issue",
            "suggestion": "Optional code suggestion"
        }}
    ]
}}

Files to review:
{"".join(file_summaries)}
"""

        try:
            response = await self.llm_client.chat_completion(
                messages=[
                    {"role": "system", "content": "You are an expert code reviewer. Respond only with valid JSON."},
                    {"role": "user", "content": prompt},
                ],
                model="openai/gpt-4o-mini",
                temperature=0.3,
                max_tokens=2000,
            )

            content = response.get("choices", [{}])[0].get("message", {}).get("content", "")

            # Parse JSON from response
            import json
            # Try to extract JSON from the response
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                data = json.loads(json_match.group())
                issues = data.get("issues", [])

                comments = []
                for issue in issues:
                    try:
                        category = ReviewCategory(issue.get("category", "style"))
                    except ValueError:
                        category = ReviewCategory.STYLE

                    try:
                        severity = ReviewSeverity(issue.get("severity", "info"))
                    except ValueError:
                        severity = ReviewSeverity.INFO

                    comments.append(ReviewComment(
                        path=issue.get("file", ""),
                        line=issue.get("line", 0),
                        body=issue.get("message", ""),
                        category=category,
                        severity=severity,
                        suggestion=issue.get("suggestion"),
                    ))

                return comments
        except Exception as e:
            logger.error(f"LLM analysis failed: {e}")

        return []

    async def check_security(self, file_change: FileChange) -> List[ReviewComment]:
        """
        Security vulnerability scan.

        Args:
            file_change: File change to analyze

        Returns:
            List of security-related comments
        """
        comments = []

        if not file_change.patch:
            return comments

        # Parse patch to get added lines with line numbers
        added_lines = self._parse_patch_lines(file_change.patch)

        # Check all security patterns
        for category, patterns in SECURITY_PATTERNS.items():
            for pattern, message in patterns:
                for line_num, line_content in added_lines:
                    if re.search(pattern, line_content):
                        severity = ReviewSeverity.CRITICAL if category in ["secrets", "command_injection"] else ReviewSeverity.ERROR

                        comments.append(ReviewComment(
                            path=file_change.filename,
                            line=line_num,
                            body=f"[Security/{category}] {message}",
                            category=ReviewCategory.SECURITY,
                            severity=severity,
                        ))

        return comments

    async def check_style(self, file_change: FileChange) -> List[ReviewComment]:
        """
        Check style and best practices.

        Args:
            file_change: File change to analyze

        Returns:
            List of style-related comments
        """
        comments = []

        if not file_change.patch or file_change.language == "unknown":
            return comments

        # Get language-specific patterns
        patterns = STYLE_PATTERNS.get(file_change.language, [])

        # Also check performance patterns
        all_patterns = patterns + [
            p for patterns_list in PERFORMANCE_PATTERNS.values()
            for p in patterns_list
        ]

        added_lines = self._parse_patch_lines(file_change.patch)

        for pattern, message in all_patterns:
            for line_num, line_content in added_lines:
                if re.search(pattern, line_content):
                    # Determine if this is performance or style
                    is_perf = any(
                        pattern in [p[0] for p in patterns_list]
                        for patterns_list in PERFORMANCE_PATTERNS.values()
                    )

                    comments.append(ReviewComment(
                        path=file_change.filename,
                        line=line_num,
                        body=message,
                        category=ReviewCategory.PERFORMANCE if is_perf else ReviewCategory.STYLE,
                        severity=ReviewSeverity.WARNING,
                    ))

        return comments

    def _check_test_coverage(self, diff_files: List[FileChange]) -> List[ReviewComment]:
        """Check for missing test coverage"""
        comments = []

        # Find source files that were modified
        source_files = [f for f in diff_files if not f.is_test_file and f.language in ["python", "javascript", "typescript"]]
        test_files = [f for f in diff_files if f.is_test_file]

        # If source files were changed but no test files, suggest adding tests
        if source_files and not test_files:
            # Add a general comment (line 0 means PR-level comment)
            significant_changes = [f for f in source_files if f.additions > 10]
            if significant_changes:
                files_list = ", ".join(f.filename for f in significant_changes[:5])
                comments.append(ReviewComment(
                    path=significant_changes[0].filename,
                    line=1,  # First line as we can't do PR-level
                    body=f"Consider adding tests for the changes in: {files_list}",
                    category=ReviewCategory.TEST,
                    severity=ReviewSeverity.INFO,
                ))

        return comments

    def _parse_patch_lines(self, patch: str) -> List[Tuple[int, str]]:
        """
        Parse a unified diff patch to extract added lines with their line numbers.

        Returns:
            List of (line_number, line_content) tuples for added lines
        """
        added_lines = []
        current_line = 0

        for line in patch.split("\n"):
            # Parse hunk header: @@ -start,count +start,count @@
            hunk_match = re.match(r'^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@', line)
            if hunk_match:
                current_line = int(hunk_match.group(1)) - 1
                continue

            if line.startswith("+") and not line.startswith("+++"):
                current_line += 1
                added_lines.append((current_line, line[1:]))
            elif line.startswith("-") and not line.startswith("---"):
                # Deleted line, don't increment
                pass
            elif not line.startswith("\\"):
                # Context line
                current_line += 1

        return added_lines

    async def _generate_summary(
        self,
        pr_info: Dict[str, Any],
        diff_files: List[FileChange],
        comments: List[ReviewComment],
    ) -> str:
        """Generate a review summary using LLM"""

        # Count issues by category
        by_category = {}
        by_severity = {}
        for c in comments:
            by_category[c.category.value] = by_category.get(c.category.value, 0) + 1
            by_severity[c.severity.value] = by_severity.get(c.severity.value, 0) + 1

        # Build summary prompt
        prompt = f"""Generate a brief code review summary for this pull request.

PR Title: {pr_info.get('title', 'Unknown')}
Files Changed: {len(diff_files)}
Total Additions: {sum(f.additions for f in diff_files)}
Total Deletions: {sum(f.deletions for f in diff_files)}

Issues Found:
- By Category: {by_category}
- By Severity: {by_severity}

Sample Issues:
{chr(10).join(f"- [{c.category.value}/{c.severity.value}] {c.path}: {c.body[:100]}" for c in comments[:5])}

Write a 2-3 sentence summary that:
1. Highlights the most important issues found
2. Notes any security concerns if present
3. Provides an overall assessment
"""

        try:
            response = await self.llm_client.chat_completion(
                messages=[
                    {"role": "system", "content": "You are a helpful code reviewer. Be concise and constructive."},
                    {"role": "user", "content": prompt},
                ],
                model="openai/gpt-4o-mini",
                temperature=0.5,
                max_tokens=300,
            )

            return response.get("choices", [{}])[0].get("message", {}).get("content", "Review completed.")
        except Exception as e:
            logger.error(f"Summary generation failed: {e}")
            return f"Review completed. Found {len(comments)} issues across {len(diff_files)} files."

    def _determine_status(self, comments: List[ReviewComment]) -> str:
        """Determine overall review status based on findings"""
        critical_count = sum(1 for c in comments if c.severity == ReviewSeverity.CRITICAL)
        error_count = sum(1 for c in comments if c.severity == ReviewSeverity.ERROR)

        if critical_count > 0:
            return "changes_requested"
        elif error_count > 2:
            return "changes_requested"
        elif error_count > 0:
            return "commented"
        else:
            return "approved"

    # -------------------------------------------------------------------
    # Webhook Handling
    # -------------------------------------------------------------------

    @staticmethod
    def verify_webhook_signature(payload: bytes, signature: str) -> bool:
        """
        Verify GitHub webhook signature.

        Args:
            payload: Raw request body
            signature: X-Hub-Signature-256 header value

        Returns:
            True if signature is valid
        """
        if not GITHUB_WEBHOOK_SECRET:
            logger.warning("Webhook secret not configured")
            return False

        expected = "sha256=" + hmac.new(
            GITHUB_WEBHOOK_SECRET.encode(),
            payload,
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(signature, expected)

    async def handle_webhook(self, event_type: str, payload: Dict[str, Any]) -> Optional[ReviewResult]:
        """
        Handle GitHub webhook event.

        Args:
            event_type: GitHub event type (e.g., "pull_request")
            payload: Webhook payload

        Returns:
            ReviewResult if review was triggered, None otherwise
        """
        if event_type != "pull_request":
            logger.debug(f"Ignoring event type: {event_type}")
            return None

        action = payload.get("action")
        if action not in ["opened", "synchronize", "reopened"]:
            logger.debug(f"Ignoring PR action: {action}")
            return None

        pr = payload.get("pull_request", {})
        repo = payload.get("repository", {}).get("full_name", "")
        pr_number = pr.get("number")

        if not repo or not pr_number:
            logger.error("Missing repo or PR number in webhook payload")
            return None

        logger.info(f"Webhook triggered review for {repo}#{pr_number} (action: {action})")

        return await self.review_pr(repo, pr_number)

    # -------------------------------------------------------------------
    # Utility Methods
    # -------------------------------------------------------------------

    def get_cached_review(self, repo: str, pr_number: int) -> Optional[ReviewResult]:
        """Get cached review result"""
        cache_key = f"{repo}#{pr_number}"
        return self._review_cache.get(cache_key)

    def get_recent_reviews(self, limit: int = 10) -> List[ReviewResult]:
        """Get recent reviews"""
        reviews = list(self._review_cache.values())
        reviews.sort(key=lambda r: r.reviewed_at, reverse=True)
        return reviews[:limit]

    async def close(self):
        """Close HTTP client"""
        await self.http_client.aclose()
        await self.llm_client.close()


# -------------------------------------------------------------------
# Factory Function
# -------------------------------------------------------------------

def create_code_reviewer(
    memory_manager=None,
    github_token: Optional[str] = None,
) -> CodeReviewer:
    """
    Factory function to create a CodeReviewer instance.

    Args:
        memory_manager: Optional memory manager for persistence
        github_token: Optional GitHub token (defaults to env var)

    Returns:
        Configured CodeReviewer instance
    """
    return CodeReviewer(
        memory_manager=memory_manager,
        github_token=github_token,
    )
