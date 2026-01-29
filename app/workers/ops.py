"""
Ops Worker - Operational tasks and system interactions

Capabilities:
- Shell command execution (sandboxed)
- API calls
- File operations
- System monitoring
- External service integration
"""

from typing import Dict, Any, List, Optional
from app.workers.base import BaseWorker, WorkerResult, WorkerStatus, WorkerArtifact
import logging
import asyncio
import subprocess
import json
import os

logger = logging.getLogger(__name__)


class OpsWorker(BaseWorker):
    """
    Worker for operational tasks requiring system interaction.

    Executes sandboxed operations with approval gates for risky commands.
    """

    name = "OpsWorker"
    description = "System operations and integrations"
    default_timeout = 60  # 1 minute for ops tasks

    # Commands that require approval
    RISKY_COMMANDS = [
        "rm", "delete", "drop", "truncate",
        "kill", "shutdown", "reboot",
        "chmod", "chown",
        "curl", "wget",  # Network access
        "pip install", "npm install",  # Package installation
    ]

    # Commands that are blocked entirely
    BLOCKED_COMMANDS = [
        "rm -rf /",
        "dd if=/dev/zero",
        ":(){ :|:& };:",
        "mkfs",
        "format",
        "> /dev/sda",
    ]

    def __init__(
        self,
        llm_client=None,
        timeout: Optional[int] = None,
        enable_shell: bool = True,
        enable_api: bool = True,
        sandbox_mode: bool = True,
    ):
        super().__init__(llm_client, timeout)
        self.enable_shell = enable_shell
        self.enable_api = enable_api
        self.sandbox_mode = sandbox_mode

    async def _execute_impl(
        self,
        task: str,
        context: Dict[str, Any],
        user_id: str,
        model: str,
    ) -> WorkerResult:
        """Execute operational task"""
        logger.info(f"{self.name}: Processing ops task - {task[:100]}...")

        op_type = context.get("operation_type", self._detect_op_type(task, context))

        if op_type == "shell":
            return await self._execute_shell(task, context, user_id)
        elif op_type == "api":
            return await self._execute_api(task, context, user_id)
        elif op_type == "file":
            return await self._execute_file_op(task, context, user_id)
        else:
            return await self._execute_generic(task, context, user_id, model)

    async def _execute_shell(
        self,
        task: str,
        context: Dict[str, Any],
        user_id: str,
    ) -> WorkerResult:
        """Execute shell command"""
        if not self.enable_shell:
            return WorkerResult(
                worker_name=self.name,
                status=WorkerStatus.FAILED,
                error="Shell execution is disabled",
                error_type="PermissionError",
            )

        command = context.get("command", "")
        if not command:
            return WorkerResult(
                worker_name=self.name,
                status=WorkerStatus.FAILED,
                error="No command provided",
                error_type="ValidationError",
            )

        # Security check
        security_result = self._check_command_security(command)
        if not security_result["allowed"]:
            return WorkerResult(
                worker_name=self.name,
                status=WorkerStatus.FAILED,
                error=security_result["reason"],
                error_type="SecurityError",
            )

        if security_result.get("requires_approval"):
            return WorkerResult(
                worker_name=self.name,
                status=WorkerStatus.ESCALATED,
                escalated=True,
                escalation_reason=f"Command requires approval: {security_result['reason']}",
                output=f"Approval required to execute: {command}",
            )

        # Execute command
        try:
            result = await asyncio.wait_for(
                self._run_command(command),
                timeout=self.timeout
            )

            artifacts = [
                self.create_artifact(
                    name="command_output",
                    content=result["stdout"],
                    artifact_type="text",
                    metadata={
                        "command": command,
                        "exit_code": result["exit_code"],
                        "stderr": result["stderr"],
                    },
                ),
            ]

            status = WorkerStatus.COMPLETED if result["exit_code"] == 0 else WorkerStatus.FAILED

            return WorkerResult(
                worker_name=self.name,
                status=status,
                output=result["stdout"],
                artifacts=artifacts,
                error=result["stderr"] if result["exit_code"] != 0 else None,
            )

        except asyncio.TimeoutError:
            return WorkerResult(
                worker_name=self.name,
                status=WorkerStatus.TIMEOUT,
                error=f"Command timed out after {self.timeout}s",
            )
        except Exception as e:
            return WorkerResult(
                worker_name=self.name,
                status=WorkerStatus.FAILED,
                error=str(e),
                error_type=type(e).__name__,
            )

    async def _run_command(self, command: str) -> Dict[str, Any]:
        """Run shell command with subprocess"""
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await process.communicate()

        return {
            "stdout": stdout.decode('utf-8', errors='replace'),
            "stderr": stderr.decode('utf-8', errors='replace'),
            "exit_code": process.returncode,
        }

    def _check_command_security(self, command: str) -> Dict[str, Any]:
        """Check command for security issues"""
        command_lower = command.lower()

        # Check for blocked commands
        for blocked in self.BLOCKED_COMMANDS:
            if blocked in command_lower:
                return {
                    "allowed": False,
                    "reason": f"Blocked command pattern: {blocked}",
                }

        # Check for risky commands
        for risky in self.RISKY_COMMANDS:
            if risky in command_lower:
                return {
                    "allowed": True,
                    "requires_approval": True,
                    "reason": f"Risky command: {risky}",
                }

        # Sandbox mode restrictions
        if self.sandbox_mode:
            # Restrict file system access
            if any(p in command for p in ['/etc/', '/var/', '/usr/', '/root/']):
                return {
                    "allowed": True,
                    "requires_approval": True,
                    "reason": "Access to system directories",
                }

        return {"allowed": True, "requires_approval": False}

    async def _execute_api(
        self,
        task: str,
        context: Dict[str, Any],
        user_id: str,
    ) -> WorkerResult:
        """Execute API call"""
        if not self.enable_api:
            return WorkerResult(
                worker_name=self.name,
                status=WorkerStatus.FAILED,
                error="API execution is disabled",
                error_type="PermissionError",
            )

        url = context.get("url", "")
        method = context.get("method", "GET").upper()
        headers = context.get("headers", {})
        body = context.get("body")

        if not url:
            return WorkerResult(
                worker_name=self.name,
                status=WorkerStatus.FAILED,
                error="No URL provided",
                error_type="ValidationError",
            )

        try:
            import httpx

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=body if body and method in ["POST", "PUT", "PATCH"] else None,
                    params=body if body and method == "GET" else None,
                )

                # Try to parse JSON response
                try:
                    response_data = response.json()
                    response_text = json.dumps(response_data, indent=2)
                except:
                    response_data = None
                    response_text = response.text

                artifacts = [
                    self.create_artifact(
                        name="api_response",
                        content=response_data or response_text,
                        artifact_type="json" if response_data else "text",
                        metadata={
                            "url": url,
                            "method": method,
                            "status_code": response.status_code,
                            "headers": dict(response.headers),
                        },
                    ),
                ]

                status = WorkerStatus.COMPLETED if response.is_success else WorkerStatus.FAILED

                return WorkerResult(
                    worker_name=self.name,
                    status=status,
                    output=response_text,
                    artifacts=artifacts,
                    error=f"HTTP {response.status_code}" if not response.is_success else None,
                )

        except Exception as e:
            return WorkerResult(
                worker_name=self.name,
                status=WorkerStatus.FAILED,
                error=str(e),
                error_type=type(e).__name__,
            )

    async def _execute_file_op(
        self,
        task: str,
        context: Dict[str, Any],
        user_id: str,
    ) -> WorkerResult:
        """Execute file operation"""
        operation = context.get("file_operation", "read")
        path = context.get("path", "")

        if not path:
            return WorkerResult(
                worker_name=self.name,
                status=WorkerStatus.FAILED,
                error="No file path provided",
                error_type="ValidationError",
            )

        # Security check for path
        abs_path = os.path.abspath(path)
        if self.sandbox_mode:
            # Restrict to current working directory
            cwd = os.getcwd()
            if not abs_path.startswith(cwd):
                return WorkerResult(
                    worker_name=self.name,
                    status=WorkerStatus.FAILED,
                    error="File access outside sandbox not allowed",
                    error_type="SecurityError",
                )

        try:
            if operation == "read":
                if not os.path.exists(abs_path):
                    return WorkerResult(
                        worker_name=self.name,
                        status=WorkerStatus.FAILED,
                        error=f"File not found: {path}",
                        error_type="FileNotFoundError",
                    )

                with open(abs_path, 'r') as f:
                    content = f.read()

                return WorkerResult(
                    worker_name=self.name,
                    status=WorkerStatus.COMPLETED,
                    output=content,
                    artifacts=[
                        self.create_artifact(
                            name="file_content",
                            content=content,
                            artifact_type="text" if not path.endswith('.json') else "json",
                            metadata={"path": path, "size": len(content)},
                        )
                    ],
                )

            elif operation == "write":
                content = context.get("content", "")
                with open(abs_path, 'w') as f:
                    f.write(content)

                return WorkerResult(
                    worker_name=self.name,
                    status=WorkerStatus.COMPLETED,
                    output=f"Written {len(content)} bytes to {path}",
                    artifacts=[
                        self.create_artifact(
                            name="write_result",
                            content={"path": path, "bytes_written": len(content)},
                            artifact_type="json",
                        )
                    ],
                )

            elif operation == "list":
                if not os.path.isdir(abs_path):
                    return WorkerResult(
                        worker_name=self.name,
                        status=WorkerStatus.FAILED,
                        error=f"Not a directory: {path}",
                        error_type="NotADirectoryError",
                    )

                entries = os.listdir(abs_path)

                return WorkerResult(
                    worker_name=self.name,
                    status=WorkerStatus.COMPLETED,
                    output="\n".join(entries),
                    artifacts=[
                        self.create_artifact(
                            name="directory_listing",
                            content=entries,
                            artifact_type="json",
                            metadata={"path": path, "count": len(entries)},
                        )
                    ],
                )

            else:
                return WorkerResult(
                    worker_name=self.name,
                    status=WorkerStatus.FAILED,
                    error=f"Unknown file operation: {operation}",
                    error_type="ValueError",
                )

        except Exception as e:
            return WorkerResult(
                worker_name=self.name,
                status=WorkerStatus.FAILED,
                error=str(e),
                error_type=type(e).__name__,
            )

    async def _execute_generic(
        self,
        task: str,
        context: Dict[str, Any],
        user_id: str,
        model: str,
    ) -> WorkerResult:
        """Execute generic ops task with LLM guidance"""
        ops_prompt = """You are an operations assistant. Analyze the task and suggest
the specific operation to perform. Output JSON with:
{
    "operation_type": "shell|api|file",
    "details": { ... specific parameters ... },
    "explanation": "Why this operation"
}"""

        try:
            response = await self.call_llm(
                messages=[
                    {"role": "system", "content": ops_prompt},
                    {"role": "user", "content": f"Task: {task}\nContext: {json.dumps(context)}"},
                ],
                model=model,
                temperature=0.3,
                max_tokens=500,
                user_id=user_id,
            )

            # Parse the suggestion
            content = response["content"]

            # For now, return the suggestion - actual execution would need approval
            return WorkerResult(
                worker_name=self.name,
                status=WorkerStatus.COMPLETED,
                output=content,
                artifacts=[
                    self.create_artifact(
                        name="ops_suggestion",
                        content=content,
                        artifact_type="text",
                    )
                ],
                tokens_input=response.get("usage", {}).get("prompt_tokens", 0),
                tokens_output=response.get("usage", {}).get("completion_tokens", 0),
            )

        except Exception as e:
            return WorkerResult(
                worker_name=self.name,
                status=WorkerStatus.FAILED,
                error=str(e),
                error_type=type(e).__name__,
            )

    def _detect_op_type(self, task: str, context: Dict[str, Any]) -> str:
        """Detect operation type from task description"""
        task_lower = task.lower()

        if any(k in context for k in ["command", "script", "shell"]):
            return "shell"
        if any(k in context for k in ["url", "endpoint", "api"]):
            return "api"
        if any(k in context for k in ["path", "file", "directory"]):
            return "file"

        if any(w in task_lower for w in ["run", "execute", "command", "script"]):
            return "shell"
        if any(w in task_lower for w in ["call", "request", "fetch", "api"]):
            return "api"
        if any(w in task_lower for w in ["read", "write", "file", "list"]):
            return "file"

        return "generic"


class DatabaseWorker(OpsWorker):
    """
    Worker for database operations.

    Executes SQL queries with safety checks.
    """

    name = "DatabaseWorker"
    description = "Database query execution"

    # Risky SQL patterns
    RISKY_SQL = [
        "DROP", "DELETE", "TRUNCATE",
        "ALTER", "CREATE", "UPDATE",
        "INSERT", "GRANT", "REVOKE",
    ]

    async def _execute_impl(
        self,
        task: str,
        context: Dict[str, Any],
        user_id: str,
        model: str,
    ) -> WorkerResult:
        """Execute database query"""
        query = context.get("query", "")
        connection_string = context.get("connection_string", "")

        if not query:
            return WorkerResult(
                worker_name=self.name,
                status=WorkerStatus.FAILED,
                error="No query provided",
                error_type="ValidationError",
            )

        # Check for risky operations
        query_upper = query.upper()
        for pattern in self.RISKY_SQL:
            if pattern in query_upper:
                return WorkerResult(
                    worker_name=self.name,
                    status=WorkerStatus.ESCALATED,
                    escalated=True,
                    escalation_reason=f"Query contains risky operation: {pattern}",
                    output=f"Approval required for query: {query}",
                )

        # For now, just validate and return - actual execution needs DB connection
        return WorkerResult(
            worker_name=self.name,
            status=WorkerStatus.COMPLETED,
            output=f"Query validated: {query}",
            artifacts=[
                self.create_artifact(
                    name="query",
                    content=query,
                    artifact_type="code",
                    metadata={"language": "sql"},
                )
            ],
        )
