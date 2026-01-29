"""
Control Flow for Workflow Engine

Implements advanced control flow constructs:
- Conditional execution (if/then/else)
- Loops (for, while, until)
- Parallel execution
- Branch/merge
- Dynamic step generation

These constructs enable complex, adaptive workflows.
"""

import asyncio
import json
import logging
import operator
from typing import (
    Dict, Any, List, Optional, Callable, Union,
    Awaitable, Literal
)
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field
import re

from app.engine.models import (
    WorkflowStep, WorkflowPlan, StepResult, ExecutionResult,
    ExecutionStatus, ToolType, RiskLevel
)

logger = logging.getLogger(__name__)


# ============== Condition Evaluation ==============

class ConditionOperator(str, Enum):
    """Operators for conditions"""
    EQ = "eq"  # ==
    NE = "ne"  # !=
    GT = "gt"  # >
    GE = "ge"  # >=
    LT = "lt"  # <
    LE = "le"  # <=
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"
    MATCHES = "matches"  # Regex
    EXISTS = "exists"
    NOT_EXISTS = "not_exists"
    AND = "and"
    OR = "or"
    NOT = "not"


@dataclass
class Condition:
    """
    A condition for control flow.

    Can be:
    - Simple comparison: {"left": "$step1.output", "op": "contains", "right": "success"}
    - Logical combination: {"op": "and", "conditions": [...]}
    - Expression: {"expr": "$step1.count > 10"}
    """
    left: Optional[str] = None
    op: ConditionOperator = ConditionOperator.EQ
    right: Optional[Any] = None
    conditions: List["Condition"] = field(default_factory=list)
    expr: Optional[str] = None

    def __post_init__(self):
        if isinstance(self.op, str):
            self.op = ConditionOperator(self.op)


class ConditionEvaluator:
    """Evaluates conditions against context"""

    OPERATORS = {
        ConditionOperator.EQ: operator.eq,
        ConditionOperator.NE: operator.ne,
        ConditionOperator.GT: operator.gt,
        ConditionOperator.GE: operator.ge,
        ConditionOperator.LT: operator.lt,
        ConditionOperator.LE: operator.le,
    }

    def __init__(self):
        pass

    def evaluate(self, condition: Condition, context: Dict[str, Any]) -> bool:
        """Evaluate a condition against context"""

        # Expression-based condition
        if condition.expr:
            return self._evaluate_expression(condition.expr, context)

        # Logical operators
        if condition.op == ConditionOperator.AND:
            return all(self.evaluate(c, context) for c in condition.conditions)

        if condition.op == ConditionOperator.OR:
            return any(self.evaluate(c, context) for c in condition.conditions)

        if condition.op == ConditionOperator.NOT:
            if condition.conditions:
                return not self.evaluate(condition.conditions[0], context)
            return False

        # Resolve left and right values
        left_val = self._resolve_value(condition.left, context)
        right_val = self._resolve_value(condition.right, context)

        # Comparison operators
        if condition.op in self.OPERATORS:
            try:
                return self.OPERATORS[condition.op](left_val, right_val)
            except TypeError:
                return False

        # String operators
        if condition.op == ConditionOperator.CONTAINS:
            return right_val in str(left_val) if left_val else False

        if condition.op == ConditionOperator.NOT_CONTAINS:
            return right_val not in str(left_val) if left_val else True

        if condition.op == ConditionOperator.MATCHES:
            try:
                return bool(re.search(str(right_val), str(left_val or "")))
            except re.error:
                return False

        # Existence operators
        if condition.op == ConditionOperator.EXISTS:
            return left_val is not None

        if condition.op == ConditionOperator.NOT_EXISTS:
            return left_val is None

        return False

    def _resolve_value(self, value: Any, context: Dict[str, Any]) -> Any:
        """Resolve a value that may be a reference"""
        if value is None:
            return None

        if not isinstance(value, str):
            return value

        # Reference like $step1.output or ${steps.step1.output}
        if value.startswith("$"):
            return self._resolve_reference(value, context)

        return value

    def _resolve_reference(self, ref: str, context: Dict[str, Any]) -> Any:
        """Resolve a reference like $step1.output or ${result}"""
        # Handle ${...} syntax
        if ref.startswith("${") and ref.endswith("}"):
            ref = "$" + ref[2:-1]

        if not ref.startswith("$"):
            return ref

        # Remove $ prefix
        path = ref[1:]

        # Handle step references
        if path.startswith("step"):
            # $step1.output -> context["steps"]["step1"]["output"]
            parts = path.split(".", 1)
            if len(parts) == 2:
                step_key = parts[0]
                field = parts[1]
                return context.get("steps", {}).get(step_key, {}).get(field)

        # Handle direct context lookup
        parts = path.split(".")
        result = context
        for part in parts:
            if isinstance(result, dict):
                result = result.get(part)
            else:
                return None
        return result

    def _evaluate_expression(self, expr: str, context: Dict[str, Any]) -> bool:
        """Evaluate a simple expression"""
        # Replace references with values
        resolved_expr = expr
        for match in re.finditer(r'\$[\w.]+', expr):
            ref = match.group()
            value = self._resolve_reference(ref, context)
            if isinstance(value, str):
                resolved_expr = resolved_expr.replace(ref, f'"{value}"')
            elif value is None:
                resolved_expr = resolved_expr.replace(ref, 'None')
            else:
                resolved_expr = resolved_expr.replace(ref, str(value))

        # Safe evaluation
        try:
            # Only allow safe operations
            allowed_names = {
                "True": True, "False": False, "None": None,
                "len": len, "str": str, "int": int, "float": float,
            }
            return bool(eval(resolved_expr, {"__builtins__": {}}, allowed_names))
        except Exception as e:
            logger.warning(f"Expression evaluation failed: {expr} -> {e}")
            return False


# ============== Control Flow Constructs ==============

class ConditionalStep(BaseModel):
    """
    Conditional step (if/then/else).

    condition: The condition to evaluate
    then_steps: Steps to execute if condition is true
    else_steps: Steps to execute if condition is false
    """
    model_config = {"protected_namespaces": ()}

    condition: Dict[str, Any]  # Condition as dict
    then_steps: List[Dict[str, Any]] = Field(default_factory=list)
    else_steps: List[Dict[str, Any]] = Field(default_factory=list)

    def to_condition(self) -> Condition:
        """Convert dict to Condition"""
        return Condition(
            left=self.condition.get("left"),
            op=ConditionOperator(self.condition.get("op", "eq")),
            right=self.condition.get("right"),
            conditions=[
                Condition(
                    left=c.get("left"),
                    op=ConditionOperator(c.get("op", "eq")),
                    right=c.get("right"),
                )
                for c in self.condition.get("conditions", [])
            ],
            expr=self.condition.get("expr"),
        )


class LoopStep(BaseModel):
    """
    Loop step (for/while/until).

    loop_type: "for", "while", or "until"
    items: For "for" loops - reference to list or inline list
    condition: For "while"/"until" - condition to check
    body_steps: Steps to execute in each iteration
    max_iterations: Safety limit
    """
    model_config = {"protected_namespaces": ()}

    loop_type: Literal["for", "while", "until"] = "for"
    items: Optional[Union[str, List[Any]]] = None  # For "for" loops
    item_var: str = "item"  # Variable name for current item
    index_var: str = "index"  # Variable name for index
    condition: Optional[Dict[str, Any]] = None  # For while/until
    body_steps: List[Dict[str, Any]] = Field(default_factory=list)
    max_iterations: int = 100


class ParallelStep(BaseModel):
    """
    Parallel execution step.

    branches: List of step sequences to run in parallel
    wait_for: "all" (wait for all), "any" (wait for first), or "n" (wait for n)
    """
    branches: List[List[Dict[str, Any]]] = Field(default_factory=list)
    wait_for: Union[Literal["all", "any"], int] = "all"


class BranchStep(BaseModel):
    """
    Multi-branch conditional (switch/case).

    value: Value to match against
    cases: Dict of value -> steps
    default: Default steps if no match
    """
    value: str  # Reference to value to match
    cases: Dict[str, List[Dict[str, Any]]] = Field(default_factory=dict)
    default: List[Dict[str, Any]] = Field(default_factory=list)


# ============== Control Flow Executor ==============

class ControlFlowExecutor:
    """
    Executes workflow steps with control flow constructs.
    """

    def __init__(
        self,
        step_executor,  # StepExecutor instance
        llm_client=None,
    ):
        self.step_executor = step_executor
        self.llm_client = llm_client
        self.condition_evaluator = ConditionEvaluator()

    async def execute_step_with_control_flow(
        self,
        step_dict: Dict[str, Any],
        context: Dict[str, Any],
        user_id: str = "anonymous",
        model: str = "local",
        on_step_complete: Optional[Callable] = None,
    ) -> List[StepResult]:
        """
        Execute a step that may have control flow constructs.

        Returns a list of StepResults (multiple for loops/parallel).
        """
        step_type = step_dict.get("type", "step")

        if step_type == "conditional":
            return await self._execute_conditional(
                ConditionalStep(**step_dict),
                context, user_id, model, on_step_complete
            )

        elif step_type == "loop":
            return await self._execute_loop(
                LoopStep(**step_dict),
                context, user_id, model, on_step_complete
            )

        elif step_type == "parallel":
            return await self._execute_parallel(
                ParallelStep(**step_dict),
                context, user_id, model, on_step_complete
            )

        elif step_type == "branch":
            return await self._execute_branch(
                BranchStep(**step_dict),
                context, user_id, model, on_step_complete
            )

        else:
            # Regular step
            step = self._dict_to_step(step_dict)
            result = await self.step_executor.execute_step(
                step, context, user_id, model
            )
            if on_step_complete:
                await on_step_complete(step, result)
            return [result]

    async def _execute_conditional(
        self,
        conditional: ConditionalStep,
        context: Dict[str, Any],
        user_id: str,
        model: str,
        on_step_complete: Optional[Callable],
    ) -> List[StepResult]:
        """Execute conditional (if/then/else)"""
        condition = conditional.to_condition()
        result = self.condition_evaluator.evaluate(condition, context)

        logger.info(f"Conditional evaluated to: {result}")

        steps_to_execute = (
            conditional.then_steps if result else conditional.else_steps
        )

        results = []
        for step_dict in steps_to_execute:
            step_results = await self.execute_step_with_control_flow(
                step_dict, context, user_id, model, on_step_complete
            )
            results.extend(step_results)

            # Update context with results
            for r in step_results:
                context.setdefault("steps", {})[f"step{r.step_id}"] = {
                    "output": r.output,
                    "artifacts": r.artifacts,
                    "status": r.status.value,
                }

            # Stop if failed/blocked
            if any(r.status in [ExecutionStatus.FAILED, ExecutionStatus.BLOCKED] for r in step_results):
                break

        return results

    async def _execute_loop(
        self,
        loop: LoopStep,
        context: Dict[str, Any],
        user_id: str,
        model: str,
        on_step_complete: Optional[Callable],
    ) -> List[StepResult]:
        """Execute loop (for/while/until)"""
        results = []
        iteration = 0

        # Determine items for "for" loop
        items = []
        if loop.loop_type == "for":
            if isinstance(loop.items, list):
                items = loop.items
            elif isinstance(loop.items, str) and loop.items.startswith("$"):
                items = self.condition_evaluator._resolve_reference(loop.items, context)
                if not isinstance(items, list):
                    items = [items] if items else []

        while iteration < loop.max_iterations:
            # Check loop condition
            should_continue = False

            if loop.loop_type == "for":
                should_continue = iteration < len(items)
                if should_continue:
                    # Set loop variables
                    context[loop.item_var] = items[iteration]
                    context[loop.index_var] = iteration

            elif loop.loop_type == "while":
                if loop.condition:
                    condition = Condition(
                        left=loop.condition.get("left"),
                        op=ConditionOperator(loop.condition.get("op", "eq")),
                        right=loop.condition.get("right"),
                        expr=loop.condition.get("expr"),
                    )
                    should_continue = self.condition_evaluator.evaluate(condition, context)

            elif loop.loop_type == "until":
                if loop.condition:
                    condition = Condition(
                        left=loop.condition.get("left"),
                        op=ConditionOperator(loop.condition.get("op", "eq")),
                        right=loop.condition.get("right"),
                        expr=loop.condition.get("expr"),
                    )
                    should_continue = not self.condition_evaluator.evaluate(condition, context)

            if not should_continue:
                break

            logger.info(f"Loop iteration {iteration + 1}")

            # Execute body steps
            for step_dict in loop.body_steps:
                step_results = await self.execute_step_with_control_flow(
                    step_dict, context, user_id, model, on_step_complete
                )
                results.extend(step_results)

                # Update context
                for r in step_results:
                    context.setdefault("steps", {})[f"step{r.step_id}"] = {
                        "output": r.output,
                        "artifacts": r.artifacts,
                        "status": r.status.value,
                    }

                # Break on failure
                if any(r.status in [ExecutionStatus.FAILED, ExecutionStatus.BLOCKED] for r in step_results):
                    return results

            iteration += 1

        if iteration >= loop.max_iterations:
            logger.warning(f"Loop hit max iterations: {loop.max_iterations}")

        return results

    async def _execute_parallel(
        self,
        parallel: ParallelStep,
        context: Dict[str, Any],
        user_id: str,
        model: str,
        on_step_complete: Optional[Callable],
    ) -> List[StepResult]:
        """Execute parallel branches"""

        async def execute_branch(branch_steps: List[Dict[str, Any]], branch_idx: int) -> List[StepResult]:
            """Execute a single branch"""
            branch_results = []
            branch_context = context.copy()
            branch_context["branch_index"] = branch_idx

            for step_dict in branch_steps:
                step_results = await self.execute_step_with_control_flow(
                    step_dict, branch_context, user_id, model, on_step_complete
                )
                branch_results.extend(step_results)

                # Update branch context
                for r in step_results:
                    branch_context.setdefault("steps", {})[f"step{r.step_id}"] = {
                        "output": r.output,
                        "artifacts": r.artifacts,
                        "status": r.status.value,
                    }

                # Break on failure
                if any(r.status in [ExecutionStatus.FAILED, ExecutionStatus.BLOCKED] for r in step_results):
                    break

            return branch_results

        # Launch all branches
        tasks = [
            asyncio.create_task(execute_branch(branch, idx))
            for idx, branch in enumerate(parallel.branches)
        ]

        # Wait based on wait_for
        all_results = []

        if parallel.wait_for == "all":
            branch_results_list = await asyncio.gather(*tasks, return_exceptions=True)
            for br in branch_results_list:
                if isinstance(br, list):
                    all_results.extend(br)

        elif parallel.wait_for == "any":
            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                result = task.result()
                if isinstance(result, list):
                    all_results.extend(result)
            # Cancel pending
            for task in pending:
                task.cancel()

        elif isinstance(parallel.wait_for, int):
            n = parallel.wait_for
            completed = 0
            for coro in asyncio.as_completed(tasks):
                try:
                    result = await coro
                    if isinstance(result, list):
                        all_results.extend(result)
                    completed += 1
                    if completed >= n:
                        break
                except Exception:
                    pass

        return all_results

    async def _execute_branch(
        self,
        branch: BranchStep,
        context: Dict[str, Any],
        user_id: str,
        model: str,
        on_step_complete: Optional[Callable],
    ) -> List[StepResult]:
        """Execute multi-branch (switch/case)"""
        value = self.condition_evaluator._resolve_reference(branch.value, context)
        value_str = str(value) if value is not None else ""

        # Find matching case
        steps_to_execute = branch.cases.get(value_str, branch.default)

        logger.info(f"Branch matched: {value_str} -> {len(steps_to_execute)} steps")

        results = []
        for step_dict in steps_to_execute:
            step_results = await self.execute_step_with_control_flow(
                step_dict, context, user_id, model, on_step_complete
            )
            results.extend(step_results)

            # Update context
            for r in step_results:
                context.setdefault("steps", {})[f"step{r.step_id}"] = {
                    "output": r.output,
                    "artifacts": r.artifacts,
                    "status": r.status.value,
                }

            if any(r.status in [ExecutionStatus.FAILED, ExecutionStatus.BLOCKED] for r in step_results):
                break

        return results

    def _dict_to_step(self, step_dict: Dict[str, Any]) -> WorkflowStep:
        """Convert step dict to WorkflowStep"""
        return WorkflowStep(
            id=step_dict.get("id", 0),
            action=step_dict.get("action", ""),
            tool=ToolType(step_dict.get("tool", "llm")),
            inputs=step_dict.get("inputs", []),
            outputs=step_dict.get("outputs", []),
            success_criteria=step_dict.get("success_criteria", []),
            risk=RiskLevel(step_dict.get("risk", "low")),
            approval_required=step_dict.get("approval_required", False),
            timeout_seconds=step_dict.get("timeout_seconds", 60),
            stdin_from=step_dict.get("stdin_from"),
        )


# ============== Dynamic Step Generator ==============

class DynamicStepGenerator:
    """
    Generates steps dynamically based on context and LLM.
    """

    def __init__(self, llm_client):
        self.llm_client = llm_client

    async def generate_steps(
        self,
        objective: str,
        context: Dict[str, Any],
        constraints: Optional[List[str]] = None,
        user_id: str = "anonymous",
    ) -> List[Dict[str, Any]]:
        """
        Generate workflow steps dynamically for an objective.
        """
        prompt = f"""Generate workflow steps to achieve this objective:

Objective: {objective}

Context:
{json.dumps(context, indent=2, default=str)[:3000]}

Constraints:
{chr(10).join(f'- {c}' for c in (constraints or []))}

Return a JSON array of steps with this format:
[
  {{
    "id": 1,
    "action": "description of what to do",
    "tool": "llm|shell|python|api|browser|filesystem|database",
    "inputs": ["list", "of", "inputs"],
    "outputs": ["expected", "outputs"],
    "success_criteria": ["how to verify success"]
  }}
]

You can also use control flow constructs:
- "type": "conditional" with condition, then_steps, else_steps
- "type": "loop" with loop_type, items/condition, body_steps
- "type": "parallel" with branches
- "type": "branch" with value, cases, default

Return ONLY the JSON array, no other text."""

        response = await self.llm_client.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            model="ops-center",
            temperature=0.3,
            max_tokens=4000,
            user_id=user_id,
        )

        content = response["choices"][0]["message"]["content"]

        # Parse JSON
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            # Try extracting from markdown
            if "```json" in content:
                start = content.find("```json") + 7
                end = content.find("```", start)
                if end > start:
                    return json.loads(content[start:end].strip())
            # Try finding array
            start = content.find("[")
            end = content.rfind("]") + 1
            if start >= 0 and end > start:
                return json.loads(content[start:end])

        return []


# ============== Helper Functions ==============

def parse_workflow_with_control_flow(workflow_dict: Dict[str, Any]) -> WorkflowPlan:
    """
    Parse a workflow definition that may include control flow constructs.
    """
    steps = []
    for idx, step_dict in enumerate(workflow_dict.get("steps", [])):
        if "type" in step_dict and step_dict["type"] != "step":
            # Control flow construct - wrap as a meta-step
            meta_step = WorkflowStep(
                id=step_dict.get("id", idx + 1),
                action=f"[{step_dict['type']}]",
                tool=ToolType.LLM,
                inputs=[],
                outputs=[],
            )
            # Store the full control flow dict in result for later processing
            meta_step.result = step_dict
            steps.append(meta_step)
        else:
            # Regular step
            steps.append(WorkflowStep(
                id=step_dict.get("id", idx + 1),
                action=step_dict.get("action", ""),
                tool=ToolType(step_dict.get("tool", "llm")),
                inputs=step_dict.get("inputs", []),
                outputs=step_dict.get("outputs", []),
                success_criteria=step_dict.get("success_criteria", []),
                risk=RiskLevel(step_dict.get("risk", "low")),
                approval_required=step_dict.get("approval_required", False),
                timeout_seconds=step_dict.get("timeout_seconds", 60),
                stdin_from=step_dict.get("stdin_from"),
            ))

    return WorkflowPlan(
        name=workflow_dict.get("name", "dynamic_workflow"),
        objective=workflow_dict.get("objective", ""),
        assumptions=workflow_dict.get("assumptions", []),
        steps=steps,
        stop_conditions=workflow_dict.get("stop_conditions", []),
    )
