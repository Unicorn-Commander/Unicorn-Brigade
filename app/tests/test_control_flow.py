"""
Tests for Control Flow Constructs (app/engine/control_flow.py)

Tests:
- Condition evaluation (eq, gt, contains, expressions)
- Loop execution (for, while, until)
- Parallel branch execution
- Conditional step execution (if/then/else)
- Branch step execution (switch/case)
"""

import pytest
import asyncio
from typing import Dict, Any

from app.engine.control_flow import (
    Condition,
    ConditionOperator,
    ConditionEvaluator,
    ConditionalStep,
    LoopStep,
    ParallelStep,
    BranchStep,
    ControlFlowExecutor,
    DynamicStepGenerator,
    parse_workflow_with_control_flow,
)
from app.engine.models import (
    WorkflowStep,
    WorkflowPlan,
    StepResult,
    ExecutionStatus,
    ToolType,
    RiskLevel,
)


# ============== Condition Evaluation Tests ==============

class TestConditionEvaluator:
    """Test condition evaluation"""

    def test_equality_condition(self):
        """Should evaluate equality correctly"""
        evaluator = ConditionEvaluator()
        context = {"status": "success"}

        condition = Condition(
            left="$status",
            op=ConditionOperator.EQ,
            right="success"
        )

        assert evaluator.evaluate(condition, context) is True

        condition.right = "failure"
        assert evaluator.evaluate(condition, context) is False

    def test_inequality_condition(self):
        """Should evaluate inequality correctly"""
        evaluator = ConditionEvaluator()
        context = {"count": 5}

        condition = Condition(
            left="$count",
            op=ConditionOperator.NE,
            right=10
        )

        assert evaluator.evaluate(condition, context) is True

        condition.right = 5
        assert evaluator.evaluate(condition, context) is False

    def test_greater_than_condition(self):
        """Should evaluate greater than correctly"""
        evaluator = ConditionEvaluator()
        context = {"score": 85}

        condition = Condition(
            left="$score",
            op=ConditionOperator.GT,
            right=80
        )

        assert evaluator.evaluate(condition, context) is True

        condition.right = 85
        assert evaluator.evaluate(condition, context) is False

        condition.op = ConditionOperator.GE
        assert evaluator.evaluate(condition, context) is True

    def test_less_than_condition(self):
        """Should evaluate less than correctly"""
        evaluator = ConditionEvaluator()
        context = {"retries": 2}

        condition = Condition(
            left="$retries",
            op=ConditionOperator.LT,
            right=5
        )

        assert evaluator.evaluate(condition, context) is True

        condition.right = 2
        assert evaluator.evaluate(condition, context) is False

        condition.op = ConditionOperator.LE
        assert evaluator.evaluate(condition, context) is True

    def test_contains_condition(self):
        """Should evaluate contains correctly"""
        evaluator = ConditionEvaluator()
        context = {"message": "Task completed successfully"}

        condition = Condition(
            left="$message",
            op=ConditionOperator.CONTAINS,
            right="completed"
        )

        assert evaluator.evaluate(condition, context) is True

        condition.right = "failed"
        assert evaluator.evaluate(condition, context) is False

    def test_not_contains_condition(self):
        """Should evaluate not_contains correctly"""
        evaluator = ConditionEvaluator()
        context = {"output": "All tests passed"}

        condition = Condition(
            left="$output",
            op=ConditionOperator.NOT_CONTAINS,
            right="error"
        )

        assert evaluator.evaluate(condition, context) is True

        condition.right = "passed"
        assert evaluator.evaluate(condition, context) is False

    def test_matches_regex_condition(self):
        """Should evaluate regex matches correctly"""
        evaluator = ConditionEvaluator()
        context = {"email": "user@example.com"}

        condition = Condition(
            left="$email",
            op=ConditionOperator.MATCHES,
            right=r"^\w+@\w+\.\w+$"
        )

        assert evaluator.evaluate(condition, context) is True

        context["email"] = "invalid-email"
        assert evaluator.evaluate(condition, context) is False

    def test_exists_condition(self):
        """Should evaluate exists correctly"""
        evaluator = ConditionEvaluator()
        context = {"data": "value", "empty": None}

        # Exists
        condition = Condition(
            left="$data",
            op=ConditionOperator.EXISTS
        )
        assert evaluator.evaluate(condition, context) is True

        # Not exists
        condition = Condition(
            left="$missing",
            op=ConditionOperator.EXISTS
        )
        assert evaluator.evaluate(condition, context) is False

        # Not exists operator
        condition = Condition(
            left="$missing",
            op=ConditionOperator.NOT_EXISTS
        )
        assert evaluator.evaluate(condition, context) is True

    def test_and_condition(self):
        """Should evaluate AND conditions correctly"""
        evaluator = ConditionEvaluator()
        context = {"status": "active", "count": 10}

        condition = Condition(
            op=ConditionOperator.AND,
            conditions=[
                Condition(left="$status", op=ConditionOperator.EQ, right="active"),
                Condition(left="$count", op=ConditionOperator.GT, right=5),
            ]
        )

        assert evaluator.evaluate(condition, context) is True

        context["count"] = 3
        assert evaluator.evaluate(condition, context) is False

    def test_or_condition(self):
        """Should evaluate OR conditions correctly"""
        evaluator = ConditionEvaluator()
        context = {"status": "pending", "priority": "high"}

        condition = Condition(
            op=ConditionOperator.OR,
            conditions=[
                Condition(left="$status", op=ConditionOperator.EQ, right="urgent"),
                Condition(left="$priority", op=ConditionOperator.EQ, right="high"),
            ]
        )

        assert evaluator.evaluate(condition, context) is True

        context["priority"] = "low"
        assert evaluator.evaluate(condition, context) is False

    def test_not_condition(self):
        """Should evaluate NOT conditions correctly"""
        evaluator = ConditionEvaluator()
        context = {"blocked": False}

        condition = Condition(
            op=ConditionOperator.NOT,
            conditions=[
                Condition(left="$blocked", op=ConditionOperator.EQ, right=True),
            ]
        )

        assert evaluator.evaluate(condition, context) is True

    def test_expression_condition(self):
        """Should evaluate expression conditions"""
        evaluator = ConditionEvaluator()
        context = {"count": 10, "threshold": 5}

        condition = Condition(expr="$count > $threshold")

        assert evaluator.evaluate(condition, context) is True

        context["count"] = 3
        assert evaluator.evaluate(condition, context) is False

    def test_step_reference_resolution(self):
        """Should resolve step output references"""
        evaluator = ConditionEvaluator()
        context = {
            "steps": {
                "step1": {
                    "output": "success",
                    "count": 42
                }
            }
        }

        condition = Condition(
            left="$step1.output",
            op=ConditionOperator.EQ,
            right="success"
        )

        assert evaluator.evaluate(condition, context) is True

    def test_nested_context_resolution(self):
        """Should resolve nested context paths"""
        evaluator = ConditionEvaluator()
        context = {
            "user": {
                "profile": {
                    "role": "admin"
                }
            }
        }

        condition = Condition(
            left="$user.profile.role",
            op=ConditionOperator.EQ,
            right="admin"
        )

        assert evaluator.evaluate(condition, context) is True


# ============== Control Flow Executor Tests ==============

class TestControlFlowExecutor:
    """Test control flow execution"""

    @pytest.mark.asyncio
    async def test_conditional_then_branch(self, mock_step_executor):
        """Should execute then branch when condition is true"""
        executor = ControlFlowExecutor(mock_step_executor)

        step_dict = {
            "type": "conditional",
            "condition": {
                "left": "$status",
                "op": "eq",
                "right": "ready"
            },
            "then_steps": [
                {"id": 1, "action": "Process", "tool": "llm"}
            ],
            "else_steps": [
                {"id": 2, "action": "Wait", "tool": "llm"}
            ]
        }

        context = {"status": "ready", "steps": {}}

        results = await executor.execute_step_with_control_flow(
            step_dict, context, "user", "model"
        )

        assert len(results) >= 1
        # Should have executed step 1 (then branch)
        executed_ids = [e["step_id"] for e in mock_step_executor.execution_history]
        assert 1 in executed_ids
        assert 2 not in executed_ids

    @pytest.mark.asyncio
    async def test_conditional_else_branch(self, mock_step_executor):
        """Should execute else branch when condition is false"""
        executor = ControlFlowExecutor(mock_step_executor)

        step_dict = {
            "type": "conditional",
            "condition": {
                "left": "$status",
                "op": "eq",
                "right": "ready"
            },
            "then_steps": [
                {"id": 1, "action": "Process", "tool": "llm"}
            ],
            "else_steps": [
                {"id": 2, "action": "Wait", "tool": "llm"}
            ]
        }

        context = {"status": "pending", "steps": {}}

        results = await executor.execute_step_with_control_flow(
            step_dict, context, "user", "model"
        )

        # Should have executed step 2 (else branch)
        executed_ids = [e["step_id"] for e in mock_step_executor.execution_history]
        assert 2 in executed_ids
        assert 1 not in executed_ids

    @pytest.mark.asyncio
    async def test_for_loop_execution(self, mock_step_executor):
        """Should execute for loop over items"""
        executor = ControlFlowExecutor(mock_step_executor)

        step_dict = {
            "type": "loop",
            "loop_type": "for",
            "items": ["a", "b", "c"],
            "item_var": "item",
            "index_var": "idx",
            "body_steps": [
                {"id": 1, "action": "Process item", "tool": "llm"}
            ],
            "max_iterations": 10
        }

        context = {"steps": {}}

        results = await executor.execute_step_with_control_flow(
            step_dict, context, "user", "model"
        )

        # Should have executed 3 times
        assert len(mock_step_executor.execution_history) == 3

        # Should have set item variable in context
        items_processed = [
            e["context"].get("item")
            for e in mock_step_executor.execution_history
        ]
        assert "a" in items_processed
        assert "b" in items_processed
        assert "c" in items_processed

    @pytest.mark.asyncio
    async def test_for_loop_with_reference(self, mock_step_executor):
        """Should execute for loop with item reference"""
        executor = ControlFlowExecutor(mock_step_executor)

        step_dict = {
            "type": "loop",
            "loop_type": "for",
            "items": "$data_list",  # Reference to context
            "item_var": "current",
            "body_steps": [
                {"id": 1, "action": "Process", "tool": "llm"}
            ],
            "max_iterations": 10
        }

        context = {
            "data_list": [1, 2, 3, 4],
            "steps": {}
        }

        results = await executor.execute_step_with_control_flow(
            step_dict, context, "user", "model"
        )

        assert len(mock_step_executor.execution_history) == 4

    @pytest.mark.asyncio
    async def test_while_loop_execution(self, mock_step_executor):
        """Should execute while loop with condition"""
        executor = ControlFlowExecutor(mock_step_executor)

        # We need to simulate counter increment
        iteration_count = [0]

        async def mock_execute(step, ctx, user, model):
            iteration_count[0] += 1
            ctx["counter"] = iteration_count[0]
            return StepResult(
                step_id=step.id,
                status=ExecutionStatus.COMPLETED,
                output=f"Iteration {iteration_count[0]}"
            )

        mock_step_executor.execute_step = mock_execute

        step_dict = {
            "type": "loop",
            "loop_type": "while",
            "condition": {
                "left": "$counter",
                "op": "lt",
                "right": 3
            },
            "body_steps": [
                {"id": 1, "action": "Increment", "tool": "llm"}
            ],
            "max_iterations": 10
        }

        context = {"counter": 0, "steps": {}}

        results = await executor.execute_step_with_control_flow(
            step_dict, context, "user", "model"
        )

        # Should have executed until counter >= 3
        assert context["counter"] >= 3

    @pytest.mark.asyncio
    async def test_until_loop_execution(self, mock_step_executor):
        """Should execute until loop (inverse of while)"""
        executor = ControlFlowExecutor(mock_step_executor)

        iteration_count = [0]

        async def mock_execute(step, ctx, user, model):
            iteration_count[0] += 1
            ctx["done"] = iteration_count[0] >= 3
            return StepResult(
                step_id=step.id,
                status=ExecutionStatus.COMPLETED,
                output=f"Iteration {iteration_count[0]}"
            )

        mock_step_executor.execute_step = mock_execute

        step_dict = {
            "type": "loop",
            "loop_type": "until",
            "condition": {
                "left": "$done",
                "op": "eq",
                "right": True
            },
            "body_steps": [
                {"id": 1, "action": "Work", "tool": "llm"}
            ],
            "max_iterations": 10
        }

        context = {"done": False, "steps": {}}

        results = await executor.execute_step_with_control_flow(
            step_dict, context, "user", "model"
        )

        # Should have executed until done is True
        assert context["done"] is True

    @pytest.mark.asyncio
    async def test_loop_max_iterations(self, mock_step_executor):
        """Should respect max_iterations limit"""
        executor = ControlFlowExecutor(mock_step_executor)

        step_dict = {
            "type": "loop",
            "loop_type": "while",
            "condition": {
                "expr": "True"  # Always true
            },
            "body_steps": [
                {"id": 1, "action": "Forever", "tool": "llm"}
            ],
            "max_iterations": 5
        }

        context = {"steps": {}}

        results = await executor.execute_step_with_control_flow(
            step_dict, context, "user", "model"
        )

        # Should stop at max_iterations
        assert len(mock_step_executor.execution_history) == 5

    @pytest.mark.asyncio
    async def test_parallel_execution_wait_all(self, mock_step_executor):
        """Should execute branches in parallel and wait for all"""
        executor = ControlFlowExecutor(mock_step_executor)

        step_dict = {
            "type": "parallel",
            "branches": [
                [
                    {"id": 1, "action": "Branch 1 Step 1", "tool": "llm"},
                    {"id": 2, "action": "Branch 1 Step 2", "tool": "llm"}
                ],
                [
                    {"id": 3, "action": "Branch 2 Step 1", "tool": "llm"}
                ]
            ],
            "wait_for": "all"
        }

        context = {"steps": {}}

        results = await executor.execute_step_with_control_flow(
            step_dict, context, "user", "model"
        )

        # All steps should have been executed
        executed_ids = [e["step_id"] for e in mock_step_executor.execution_history]
        assert 1 in executed_ids
        assert 2 in executed_ids
        assert 3 in executed_ids

    @pytest.mark.asyncio
    async def test_parallel_execution_wait_any(self, mock_step_executor):
        """Should execute branches and return after first completes"""
        executor = ControlFlowExecutor(mock_step_executor)

        # Make one branch faster
        async def mock_execute(step, ctx, user, model):
            if step.id == 1:
                await asyncio.sleep(0.01)  # Fast
            else:
                await asyncio.sleep(0.5)  # Slow
            return StepResult(
                step_id=step.id,
                status=ExecutionStatus.COMPLETED,
                output=f"Step {step.id}"
            )

        mock_step_executor.execute_step = mock_execute

        step_dict = {
            "type": "parallel",
            "branches": [
                [{"id": 1, "action": "Fast", "tool": "llm"}],
                [{"id": 2, "action": "Slow", "tool": "llm"}]
            ],
            "wait_for": "any"
        }

        context = {"steps": {}}

        results = await executor.execute_step_with_control_flow(
            step_dict, context, "user", "model"
        )

        # Should have at least one result
        assert len(results) >= 1

    @pytest.mark.asyncio
    async def test_branch_step_execution(self, mock_step_executor):
        """Should execute correct case in branch step"""
        executor = ControlFlowExecutor(mock_step_executor)

        step_dict = {
            "type": "branch",
            "value": "$action",
            "cases": {
                "create": [{"id": 1, "action": "Create", "tool": "llm"}],
                "update": [{"id": 2, "action": "Update", "tool": "llm"}],
                "delete": [{"id": 3, "action": "Delete", "tool": "llm"}]
            },
            "default": [{"id": 4, "action": "Unknown", "tool": "llm"}]
        }

        # Test "update" case
        context = {"action": "update", "steps": {}}

        results = await executor.execute_step_with_control_flow(
            step_dict, context, "user", "model"
        )

        executed_ids = [e["step_id"] for e in mock_step_executor.execution_history]
        assert 2 in executed_ids  # Update case
        assert 1 not in executed_ids
        assert 3 not in executed_ids

    @pytest.mark.asyncio
    async def test_branch_step_default(self, mock_step_executor):
        """Should execute default case when no match"""
        executor = ControlFlowExecutor(mock_step_executor)

        step_dict = {
            "type": "branch",
            "value": "$action",
            "cases": {
                "create": [{"id": 1, "action": "Create", "tool": "llm"}],
            },
            "default": [{"id": 2, "action": "Default", "tool": "llm"}]
        }

        context = {"action": "unknown_action", "steps": {}}

        results = await executor.execute_step_with_control_flow(
            step_dict, context, "user", "model"
        )

        executed_ids = [e["step_id"] for e in mock_step_executor.execution_history]
        assert 2 in executed_ids  # Default case

    @pytest.mark.asyncio
    async def test_regular_step_execution(self, mock_step_executor):
        """Should execute regular steps correctly"""
        executor = ControlFlowExecutor(mock_step_executor)

        step_dict = {
            "id": 1,
            "action": "Regular step",
            "tool": "llm",
            "inputs": ["input1"],
            "outputs": ["output1"]
        }

        context = {"steps": {}}

        results = await executor.execute_step_with_control_flow(
            step_dict, context, "user", "model"
        )

        assert len(results) == 1
        assert results[0].step_id == 1


# ============== Conditional Step Model Tests ==============

class TestConditionalStep:
    """Test conditional step model"""

    def test_to_condition_conversion(self):
        """Should convert dict to Condition object"""
        step = ConditionalStep(
            condition={
                "left": "$status",
                "op": "eq",
                "right": "ready"
            },
            then_steps=[{"id": 1}],
            else_steps=[{"id": 2}]
        )

        condition = step.to_condition()

        assert condition.left == "$status"
        assert condition.op == ConditionOperator.EQ
        assert condition.right == "ready"

    def test_to_condition_with_nested(self):
        """Should convert nested conditions"""
        step = ConditionalStep(
            condition={
                "op": "and",
                "conditions": [
                    {"left": "$a", "op": "eq", "right": 1},
                    {"left": "$b", "op": "gt", "right": 5}
                ]
            },
            then_steps=[],
            else_steps=[]
        )

        condition = step.to_condition()

        assert condition.op == ConditionOperator.AND
        assert len(condition.conditions) == 2


# ============== Loop Step Model Tests ==============

class TestLoopStep:
    """Test loop step model"""

    def test_for_loop_model(self):
        """Should create for loop model"""
        loop = LoopStep(
            loop_type="for",
            items=["a", "b", "c"],
            item_var="letter",
            index_var="i",
            body_steps=[{"id": 1}],
            max_iterations=100
        )

        assert loop.loop_type == "for"
        assert len(loop.items) == 3
        assert loop.item_var == "letter"

    def test_while_loop_model(self):
        """Should create while loop model"""
        loop = LoopStep(
            loop_type="while",
            condition={"left": "$x", "op": "lt", "right": 10},
            body_steps=[{"id": 1}],
            max_iterations=50
        )

        assert loop.loop_type == "while"
        assert loop.condition is not None


# ============== Workflow Parsing Tests ==============

class TestWorkflowParsing:
    """Test workflow parsing with control flow"""

    def test_parse_workflow_with_control_flow(self):
        """Should parse workflow with control flow constructs"""
        workflow_dict = {
            "name": "test_workflow",
            "objective": "Test control flow",
            "steps": [
                {"id": 1, "action": "Start", "tool": "llm"},
                {
                    "id": 2,
                    "type": "conditional",
                    "condition": {"left": "$ok", "op": "eq", "right": True},
                    "then_steps": [{"id": 3, "action": "Continue", "tool": "llm"}],
                    "else_steps": []
                },
                {
                    "id": 4,
                    "type": "loop",
                    "loop_type": "for",
                    "items": [1, 2, 3],
                    "body_steps": [{"id": 5, "action": "Process", "tool": "llm"}]
                }
            ]
        }

        plan = parse_workflow_with_control_flow(workflow_dict)

        assert plan.name == "test_workflow"
        assert len(plan.steps) == 3

        # First step is regular
        assert plan.steps[0].action == "Start"

        # Second step is conditional (wrapped)
        assert "[conditional]" in plan.steps[1].action

        # Third step is loop (wrapped)
        assert "[loop]" in plan.steps[2].action


# ============== Dynamic Step Generator Tests ==============

class TestDynamicStepGenerator:
    """Test dynamic step generation"""

    @pytest.mark.asyncio
    async def test_generate_steps(self, mock_llm_client):
        """Should generate steps from objective"""
        # Mock LLM response with steps
        mock_llm_client.add_response('''[
            {"id": 1, "action": "Research topic", "tool": "llm"},
            {"id": 2, "action": "Analyze data", "tool": "python"},
            {"id": 3, "action": "Generate report", "tool": "llm"}
        ]''')

        generator = DynamicStepGenerator(mock_llm_client)

        steps = await generator.generate_steps(
            objective="Write a research report",
            context={"topic": "AI trends"},
            constraints=["Use only public data"]
        )

        assert len(steps) == 3
        assert steps[0]["action"] == "Research topic"
        assert steps[1]["tool"] == "python"

    @pytest.mark.asyncio
    async def test_generate_steps_with_markdown(self, mock_llm_client):
        """Should handle markdown-wrapped JSON"""
        mock_llm_client.add_response('''Here are the steps:

```json
[
    {"id": 1, "action": "Step 1", "tool": "llm"}
]
```

That should work!''')

        generator = DynamicStepGenerator(mock_llm_client)

        steps = await generator.generate_steps(
            objective="Simple task",
            context={}
        )

        assert len(steps) == 1

    @pytest.mark.asyncio
    async def test_generate_steps_with_control_flow(self, mock_llm_client):
        """Should generate control flow constructs"""
        mock_llm_client.add_response('''[
            {"id": 1, "action": "Check status", "tool": "llm"},
            {
                "id": 2,
                "type": "conditional",
                "condition": {"left": "$status", "op": "eq", "right": "ok"},
                "then_steps": [{"id": 3, "action": "Proceed", "tool": "llm"}],
                "else_steps": [{"id": 4, "action": "Retry", "tool": "llm"}]
            }
        ]''')

        generator = DynamicStepGenerator(mock_llm_client)

        steps = await generator.generate_steps(
            objective="Conditional workflow",
            context={}
        )

        assert len(steps) == 2
        assert steps[1]["type"] == "conditional"


# ============== Edge Cases and Error Handling ==============

class TestEdgeCases:
    """Test edge cases and error handling"""

    def test_condition_with_null_values(self):
        """Should handle null values gracefully"""
        evaluator = ConditionEvaluator()
        context = {"value": None}

        condition = Condition(
            left="$value",
            op=ConditionOperator.EQ,
            right=None
        )

        # Should not raise, should handle gracefully
        result = evaluator.evaluate(condition, context)
        assert result is True

    def test_condition_with_missing_reference(self):
        """Should handle missing references"""
        evaluator = ConditionEvaluator()
        context = {}

        condition = Condition(
            left="$missing.nested.value",
            op=ConditionOperator.EQ,
            right="something"
        )

        # Should not raise, should return False
        result = evaluator.evaluate(condition, context)
        assert result is False

    def test_invalid_regex_in_matches(self):
        """Should handle invalid regex gracefully"""
        evaluator = ConditionEvaluator()
        context = {"text": "test"}

        condition = Condition(
            left="$text",
            op=ConditionOperator.MATCHES,
            right="[invalid(regex"  # Invalid regex
        )

        # Should not raise, should return False
        result = evaluator.evaluate(condition, context)
        assert result is False

    def test_type_mismatch_in_comparison(self):
        """Should handle type mismatches"""
        evaluator = ConditionEvaluator()
        context = {"text": "not a number"}

        condition = Condition(
            left="$text",
            op=ConditionOperator.GT,
            right=10
        )

        # Should not raise, should return False
        result = evaluator.evaluate(condition, context)
        assert result is False

    @pytest.mark.asyncio
    async def test_loop_break_on_failure(self, mock_step_executor):
        """Loop should break on step failure"""
        executor = ControlFlowExecutor(mock_step_executor)

        # Make step 1 fail
        mock_step_executor.set_result(1, "Error", "failed")

        step_dict = {
            "type": "loop",
            "loop_type": "for",
            "items": [1, 2, 3],
            "body_steps": [{"id": 1, "action": "Fail", "tool": "llm"}],
            "max_iterations": 10
        }

        context = {"steps": {}}

        results = await executor.execute_step_with_control_flow(
            step_dict, context, "user", "model"
        )

        # Should stop after first failure
        assert len(results) == 1
        assert results[0].status == ExecutionStatus.FAILED
