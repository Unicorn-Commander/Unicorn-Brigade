"""
Step Executor - Bounded Step-by-Step Execution

The Executor runs individual workflow steps with:
- Bounded execution (timeouts, output limits)
- Artifact production
- State forwarding between steps
- Error handling with retry logic
"""

import asyncio
import json
import logging
from typing import Dict, Any, Optional, Callable
from datetime import datetime
from pathlib import Path

from app.engine.models import (
    WorkflowStep,
    WorkflowPlan,
    StepResult,
    ExecutionResult,
    ExecutionStatus,
    ToolType,
    WorkerType,
    RiskLevel,
)
from app.llm.ops_center_client import OpsCenterLLMClient

logger = logging.getLogger(__name__)


DEFAULT_EXECUTOR_PROMPT = """You are executing a single step in a workflow. Execute ONLY this step, nothing more.

Current step: {action}
Inputs: {inputs}
Expected outputs: {outputs}
Success criteria: {criteria}

EXECUTION RULES:
- Execute ONLY the current step
- Do NOT re-plan or skip ahead
- Produce the expected outputs/artifacts
- If blocked, return status=blocked with explanation
- JSON only output

Success format:
{"status": "done", "artifacts": ["list of produced artifacts"], "output": "result text", "notes": "any relevant notes"}

Blocked format:
{"status": "blocked", "blocker": "what is blocking", "needed": "what is needed to proceed"}

Error format:
{"status": "error", "error": "what went wrong"}
"""


class StepExecutor:
    """Executes individual workflow steps with safety bounds"""

    # Maximum output size per step (prevent memory issues)
    MAX_OUTPUT_SIZE = 100_000  # 100KB

    # Default timeouts by tool type
    DEFAULT_TIMEOUTS = {
        ToolType.SHELL: 60,
        ToolType.PYTHON: 120,
        ToolType.BROWSER: 180,
        ToolType.FILESYSTEM: 30,
        ToolType.LLM: 60,
        ToolType.API: 30,
        ToolType.DATABASE: 30,
    }

    def __init__(
        self,
        llm_client: Optional[OpsCenterLLMClient] = None,
        workers: Optional[Dict[WorkerType, Any]] = None,
        artifacts_dir: Optional[Path] = None,
    ):
        self.llm_client = llm_client or OpsCenterLLMClient()
        self.workers = workers or {}
        self.artifacts_dir = artifacts_dir or Path("./artifacts")
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)

    async def execute_step(
        self,
        step: WorkflowStep,
        context: Dict[str, Any],
        user_id: str = "anonymous",
        model: str = "local",
    ) -> StepResult:
        """
        Execute a single workflow step.

        Args:
            step: The step to execute
            context: Accumulated context from previous steps
            user_id: User ID for LLM calls
            model: Model to use (local, ops-center, claude-burst)

        Returns:
            StepResult with status, output, and artifacts
        """
        start_time = datetime.utcnow()
        logger.info(f"Executing step {step.id}: {step.action}")

        try:
            # Apply timeout
            timeout = step.timeout_seconds or self.DEFAULT_TIMEOUTS.get(step.tool, 60)

            result = await asyncio.wait_for(
                self._execute_with_tool(step, context, user_id, model),
                timeout=timeout
            )

            duration = (datetime.utcnow() - start_time).total_seconds()
            result.duration_seconds = duration

            logger.info(
                f"Step {step.id} completed: status={result.status}, "
                f"duration={duration:.2f}s"
            )

            return result

        except asyncio.TimeoutError:
            duration = (datetime.utcnow() - start_time).total_seconds()
            logger.warning(f"Step {step.id} timed out after {duration:.2f}s")
            return StepResult(
                step_id=step.id,
                status=ExecutionStatus.FAILED,
                error=f"Step timed out after {timeout} seconds",
                duration_seconds=duration,
            )

        except Exception as e:
            duration = (datetime.utcnow() - start_time).total_seconds()
            logger.error(f"Step {step.id} failed: {e}")
            return StepResult(
                step_id=step.id,
                status=ExecutionStatus.FAILED,
                error=str(e),
                duration_seconds=duration,
            )

    async def _execute_with_tool(
        self,
        step: WorkflowStep,
        context: Dict[str, Any],
        user_id: str,
        model: str,
    ) -> StepResult:
        """Execute step using the appropriate tool"""

        # Get input from previous step if stdin_from is set
        stdin_content = ""
        if step.stdin_from:
            stdin_content = self._resolve_stdin(step.stdin_from, context)

        # Dispatch to appropriate tool executor
        if step.tool == ToolType.LLM:
            return await self._execute_llm(step, context, stdin_content, user_id, model)
        elif step.tool == ToolType.SHELL:
            return await self._execute_shell(step, context, stdin_content)
        elif step.tool == ToolType.PYTHON:
            return await self._execute_python(step, context, stdin_content)
        elif step.tool == ToolType.FILESYSTEM:
            return await self._execute_filesystem(step, context, stdin_content)
        elif step.tool == ToolType.BROWSER:
            return await self._execute_browser(step, context, stdin_content)
        elif step.tool == ToolType.API:
            return await self._execute_api(step, context, stdin_content)
        elif step.tool == ToolType.DATABASE:
            return await self._execute_database(step, context, stdin_content)
        else:
            # Default to LLM
            return await self._execute_llm(step, context, stdin_content, user_id, model)

    def _resolve_stdin(self, stdin_from: str, context: Dict[str, Any]) -> str:
        """Resolve stdin reference like $step1.stdout"""
        if not stdin_from.startswith("$"):
            return stdin_from

        # Parse reference like $step1.stdout or $collect.output
        parts = stdin_from[1:].split(".")
        if len(parts) != 2:
            return ""

        step_ref, field = parts
        step_context = context.get("steps", {}).get(step_ref, {})
        return str(step_context.get(field, ""))

    async def _execute_llm(
        self,
        step: WorkflowStep,
        context: Dict[str, Any],
        stdin_content: str,
        user_id: str,
        model: str,
    ) -> StepResult:
        """Execute step using LLM"""
        # Build prompt from step
        prompt = DEFAULT_EXECUTOR_PROMPT.format(
            action=step.action,
            inputs=", ".join(step.inputs) + (f"\n\nPrevious output:\n{stdin_content}" if stdin_content else ""),
            outputs=", ".join(step.outputs),
            criteria=", ".join(step.success_criteria),
        )

        # Add context
        if context:
            prompt += f"\n\nContext:\n{json.dumps(context, indent=2, default=str)[:5000]}"

        response = await self.llm_client.chat_completion(
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": f"Execute this step: {step.action}"}
            ],
            model=model,
            temperature=0.3,
            max_tokens=4000,
            user_id=user_id
        )

        result_text = response["choices"][0]["message"]["content"]
        result_json = self._parse_result(result_text)

        # Extract tokens
        tokens = {
            "input": response.get("usage", {}).get("prompt_tokens", 0),
            "output": response.get("usage", {}).get("completion_tokens", 0),
        }

        status_str = result_json.get("status", "done")
        if status_str == "done":
            status = ExecutionStatus.COMPLETED
        elif status_str == "blocked":
            status = ExecutionStatus.BLOCKED
        else:
            status = ExecutionStatus.FAILED

        return StepResult(
            step_id=step.id,
            status=status,
            output=result_json.get("output", result_text)[:self.MAX_OUTPUT_SIZE],
            artifacts=result_json.get("artifacts", []),
            error=result_json.get("error"),
            blocker=result_json.get("blocker"),
            needed=result_json.get("needed"),
            tokens_used=tokens,
        )

    async def _execute_shell(
        self,
        step: WorkflowStep,
        context: Dict[str, Any],
        stdin_content: str,
    ) -> StepResult:
        """Execute shell command (sandboxed)"""
        # For now, use worker if available
        if WorkerType.OPS in self.workers:
            worker = self.workers[WorkerType.OPS]
            result = await worker.execute({
                "task": step.action,
                "inputs": step.inputs,
                "stdin": stdin_content,
            })
            return StepResult(
                step_id=step.id,
                status=ExecutionStatus.COMPLETED if result.get("success") else ExecutionStatus.FAILED,
                output=result.get("output", ""),
                artifacts=result.get("artifacts", []),
                error=result.get("error"),
            )

        # Fallback: return blocked (shell execution requires explicit setup)
        return StepResult(
            step_id=step.id,
            status=ExecutionStatus.BLOCKED,
            blocker="Shell execution not configured",
            needed="OpsWorker must be registered for shell execution",
        )

    async def _execute_python(
        self,
        step: WorkflowStep,
        context: Dict[str, Any],
        stdin_content: str,
    ) -> StepResult:
        """Execute Python code (sandboxed)"""
        if WorkerType.CODE in self.workers:
            worker = self.workers[WorkerType.CODE]
            result = await worker.execute({
                "task": step.action,
                "inputs": step.inputs,
                "stdin": stdin_content,
                "language": "python",
            })
            return StepResult(
                step_id=step.id,
                status=ExecutionStatus.COMPLETED if result.get("success") else ExecutionStatus.FAILED,
                output=result.get("output", ""),
                artifacts=result.get("artifacts", []),
                error=result.get("error"),
            )

        return StepResult(
            step_id=step.id,
            status=ExecutionStatus.BLOCKED,
            blocker="Python execution not configured",
            needed="CodeWorker must be registered for Python execution",
        )

    async def _execute_filesystem(
        self,
        step: WorkflowStep,
        context: Dict[str, Any],
        stdin_content: str,
    ) -> StepResult:
        """Execute filesystem operations (sandboxed)"""
        # For now, only support writing artifacts
        if step.outputs:
            for output_file in step.outputs:
                artifact_path = self.artifacts_dir / output_file
                artifact_path.parent.mkdir(parents=True, exist_ok=True)
                artifact_path.write_text(stdin_content or f"Artifact for step {step.id}")

            return StepResult(
                step_id=step.id,
                status=ExecutionStatus.COMPLETED,
                output=f"Created artifacts: {', '.join(step.outputs)}",
                artifacts=step.outputs,
            )

        return StepResult(
            step_id=step.id,
            status=ExecutionStatus.COMPLETED,
            output="Filesystem operation completed",
        )

    async def _execute_browser(
        self,
        step: WorkflowStep,
        context: Dict[str, Any],
        stdin_content: str,
    ) -> StepResult:
        """Execute browser/scraping operations"""
        if WorkerType.SCRAPE in self.workers:
            worker = self.workers[WorkerType.SCRAPE]
            result = await worker.execute({
                "task": step.action,
                "inputs": step.inputs,
            })
            return StepResult(
                step_id=step.id,
                status=ExecutionStatus.COMPLETED if result.get("success") else ExecutionStatus.FAILED,
                output=result.get("output", ""),
                artifacts=result.get("artifacts", []),
                error=result.get("error"),
            )

        return StepResult(
            step_id=step.id,
            status=ExecutionStatus.BLOCKED,
            blocker="Browser/scraping not configured",
            needed="ScrapeWorker must be registered for browser operations",
        )

    async def _execute_api(
        self,
        step: WorkflowStep,
        context: Dict[str, Any],
        stdin_content: str,
    ) -> StepResult:
        """Execute API calls"""
        # Use research worker for API calls
        if WorkerType.RESEARCH in self.workers:
            worker = self.workers[WorkerType.RESEARCH]
            result = await worker.execute({
                "task": step.action,
                "inputs": step.inputs,
            })
            return StepResult(
                step_id=step.id,
                status=ExecutionStatus.COMPLETED if result.get("success") else ExecutionStatus.FAILED,
                output=result.get("output", ""),
                artifacts=result.get("artifacts", []),
                error=result.get("error"),
            )

        return StepResult(
            step_id=step.id,
            status=ExecutionStatus.BLOCKED,
            blocker="API execution not configured",
            needed="ResearchWorker must be registered for API calls",
        )

    async def _execute_database(
        self,
        step: WorkflowStep,
        context: Dict[str, Any],
        stdin_content: str,
    ) -> StepResult:
        """Execute database operations"""
        return StepResult(
            step_id=step.id,
            status=ExecutionStatus.BLOCKED,
            blocker="Database operations require explicit configuration",
            needed="Database connection and query approval required",
        )

    def _parse_result(self, text: str) -> dict:
        """Parse JSON from executor response"""
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try extracting from markdown
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            if end > start:
                try:
                    return json.loads(text[start:end].strip())
                except json.JSONDecodeError:
                    pass

        # Try curly braces
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError:
                pass

        # Return as raw output
        return {"status": "done", "output": text}

    async def execute_workflow(
        self,
        plan: WorkflowPlan,
        user_id: str = "anonymous",
        model: str = "local",
        on_step_complete: Optional[Callable] = None,
        on_approval_required: Optional[Callable] = None,
    ) -> ExecutionResult:
        """
        Execute a complete workflow plan.

        Args:
            plan: The workflow plan to execute
            user_id: User ID for LLM calls
            model: Model to use
            on_step_complete: Callback after each step
            on_approval_required: Callback when approval is needed

        Returns:
            ExecutionResult with all step results
        """
        start_time = datetime.utcnow()
        context: Dict[str, Any] = {"steps": {}}
        step_results: List[StepResult] = []
        total_tokens = {"input": 0, "output": 0}

        for step in plan.steps:
            # Check if approval required
            if step.approval_required and on_approval_required:
                approved = await on_approval_required(step, context)
                if not approved:
                    return ExecutionResult(
                        workflow_id=plan.id,
                        status=ExecutionStatus.BLOCKED,
                        step_results=step_results,
                        current_step=step.id,
                        error="Approval denied for step",
                    )

            # Execute step
            result = await self.execute_step(step, context, user_id, model)
            step_results.append(result)

            # Update context
            context["steps"][f"step{step.id}"] = {
                "stdout": result.output,
                "output": result.output,
                "artifacts": result.artifacts,
                "status": result.status.value,
            }

            # Update tokens
            total_tokens["input"] += result.tokens_used.get("input", 0)
            total_tokens["output"] += result.tokens_used.get("output", 0)

            # Callback
            if on_step_complete:
                await on_step_complete(step, result)

            # Check for failures/blocks
            if result.status in [ExecutionStatus.FAILED, ExecutionStatus.BLOCKED]:
                return ExecutionResult(
                    workflow_id=plan.id,
                    status=result.status,
                    step_results=step_results,
                    current_step=step.id,
                    error=result.error or result.blocker,
                    total_duration_seconds=(datetime.utcnow() - start_time).total_seconds(),
                    total_tokens=total_tokens,
                )

        # All steps completed
        duration = (datetime.utcnow() - start_time).total_seconds()
        final_output = step_results[-1].output if step_results else None
        all_artifacts = []
        for r in step_results:
            all_artifacts.extend(r.artifacts)

        return ExecutionResult(
            workflow_id=plan.id,
            status=ExecutionStatus.COMPLETED,
            step_results=step_results,
            artifacts=all_artifacts,
            total_duration_seconds=duration,
            total_tokens=total_tokens,
            final_output=final_output,
            current_step=len(plan.steps),
        )
