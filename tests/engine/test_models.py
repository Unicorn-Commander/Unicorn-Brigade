"""
Tests for workflow engine models
"""

import pytest
from datetime import datetime, timedelta
from app.engine.models import (
    TaskIntent, RiskLevel, Priority, WorkerType, ToolType,
    ApprovalState, ExecutionStatus,
    RoutingResult, WorkflowStep, WorkflowPlan,
    StepResult, ExecutionResult,
    VerificationResult, ResumeToken, Task, TaskResult,
)


class TestTaskIntent:
    """Tests for TaskIntent enum"""

    def test_all_intents_exist(self):
        """Verify all expected intents are defined"""
        assert TaskIntent.RESEARCH
        assert TaskIntent.CODING
        assert TaskIntent.EXTRACTION
        assert TaskIntent.REPORT
        assert TaskIntent.OPS
        assert TaskIntent.SCRAPE
        assert TaskIntent.OUTREACH
        assert TaskIntent.QA
        assert TaskIntent.UNKNOWN

    def test_intent_values(self):
        """Verify intent string values"""
        assert TaskIntent.RESEARCH.value == "research"
        assert TaskIntent.CODING.value == "coding"


class TestRiskLevel:
    """Tests for RiskLevel enum"""

    def test_risk_levels_exist(self):
        """Risk levels should exist"""
        assert RiskLevel.LOW
        assert RiskLevel.MEDIUM
        assert RiskLevel.HIGH

    def test_risk_values(self):
        """Verify risk string values"""
        assert RiskLevel.LOW.value == "low"
        assert RiskLevel.HIGH.value == "high"


class TestExecutionStatus:
    """Tests for ExecutionStatus enum"""

    def test_all_statuses_exist(self):
        """Verify all execution statuses exist"""
        assert ExecutionStatus.PENDING
        assert ExecutionStatus.RUNNING
        assert ExecutionStatus.BLOCKED
        assert ExecutionStatus.COMPLETED
        assert ExecutionStatus.FAILED
        assert ExecutionStatus.APPROVAL_REQUIRED


class TestRoutingResult:
    """Tests for RoutingResult model"""

    def test_create_routing_result(self):
        """Create a basic routing result"""
        result = RoutingResult(
            intent=TaskIntent.RESEARCH,
            risk=RiskLevel.LOW,
            suggested_worker=WorkerType.RESEARCH,
            needs_human_approval=False,
            reason="Simple research task",
            confidence=0.9,
        )

        assert result.intent == TaskIntent.RESEARCH
        assert result.risk == RiskLevel.LOW
        assert result.needs_human_approval is False
        assert result.confidence == 0.9

    def test_high_risk_requires_approval(self):
        """High risk tasks should typically require approval"""
        result = RoutingResult(
            intent=TaskIntent.OPS,
            risk=RiskLevel.HIGH,
            suggested_worker=WorkerType.OPS,
            needs_human_approval=True,
            reason="Risky operation",
            confidence=0.85,
        )

        assert result.needs_human_approval is True


class TestWorkflowStep:
    """Tests for WorkflowStep model"""

    def test_create_step(self):
        """Create a basic workflow step"""
        step = WorkflowStep(
            id=1,
            action="Research AI trends",
            tool=ToolType.LLM,
            worker=WorkerType.RESEARCH,
            timeout_seconds=120,
        )

        assert step.id == 1
        assert step.timeout_seconds == 120
        assert step.approval_required is False
        assert step.status == ExecutionStatus.PENDING

    def test_step_with_inputs_outputs(self):
        """Create step with inputs and outputs"""
        step = WorkflowStep(
            id=2,
            action="Analyze results",
            tool=ToolType.LLM,
            worker=WorkerType.REPORT,
            inputs=["research_data"],
            outputs=["analysis_report"],
            success_criteria=["report_generated"],
        )

        assert "research_data" in step.inputs
        assert "analysis_report" in step.outputs


class TestWorkflowPlan:
    """Tests for WorkflowPlan model"""

    def test_create_plan(self):
        """Create a basic workflow plan"""
        steps = [
            WorkflowStep(
                id=1,
                action="Step 1",
                tool=ToolType.LLM,
                worker=WorkerType.RESEARCH,
            ),
            WorkflowStep(
                id=2,
                action="Step 2",
                tool=ToolType.LLM,
                worker=WorkerType.REPORT,
            ),
        ]

        plan = WorkflowPlan(
            name="Test Plan",
            objective="Test objective",
            steps=steps,
        )

        assert plan.name == "Test Plan"
        assert len(plan.steps) == 2
        assert plan.id is not None  # Auto-generated UUID

    def test_plan_with_assumptions(self):
        """Create plan with assumptions"""
        steps = [
            WorkflowStep(id=1, action="Step 1", tool=ToolType.LLM),
        ]

        plan = WorkflowPlan(
            name="Test Plan",
            objective="Test objective",
            steps=steps,
            assumptions=["User has access", "API is available"],
            stop_conditions=["Error rate > 50%"],
        )

        assert len(plan.assumptions) == 2
        assert len(plan.stop_conditions) == 1


class TestStepResult:
    """Tests for StepResult model"""

    def test_successful_result(self):
        """Create a successful step result"""
        result = StepResult(
            step_id=1,
            status=ExecutionStatus.COMPLETED,
            output="Research complete",
            artifacts=["findings.txt"],
        )

        assert result.status == ExecutionStatus.COMPLETED
        assert len(result.artifacts) == 1

    def test_failed_result(self):
        """Create a failed step result"""
        result = StepResult(
            step_id=1,
            status=ExecutionStatus.FAILED,
            error="Timeout exceeded",
        )

        assert result.status == ExecutionStatus.FAILED
        assert result.error == "Timeout exceeded"

    def test_blocked_result(self):
        """Create a blocked step result"""
        result = StepResult(
            step_id=1,
            status=ExecutionStatus.BLOCKED,
            blocker="Missing API key",
            needed="OPENAI_API_KEY environment variable",
        )

        assert result.status == ExecutionStatus.BLOCKED
        assert result.blocker == "Missing API key"


class TestTask:
    """Tests for Task model"""

    def test_create_task(self):
        """Create a basic task"""
        task = Task(
            content="Research AI trends",
            user_id="user_123",
        )

        assert task.content == "Research AI trends"
        assert task.user_id == "user_123"
        assert task.id is not None  # Auto-generated

    def test_task_with_context(self):
        """Create task with context"""
        task = Task(
            content="Analyze code",
            user_id="user_123",
            context={"language": "python", "file": "main.py"},
        )

        assert task.context["language"] == "python"

    def test_task_with_hints(self):
        """Create task with suggested intent"""
        task = Task(
            content="Write a Python script",
            user_id="user_123",
            suggested_intent=TaskIntent.CODING,
        )

        assert task.suggested_intent == TaskIntent.CODING


class TestResumeToken:
    """Tests for ResumeToken model"""

    def test_create_token(self):
        """Create a resume token"""
        token = ResumeToken(
            workflow_id="wf_123",
            step_id=5,
            step_description="Deploy to production",
            state={"version": "1.0.0"},
        )

        assert token.workflow_id == "wf_123"
        assert token.step_id == 5
        assert token.approval_state == ApprovalState.PENDING

    def test_token_expiration(self):
        """Token should have expiration"""
        token = ResumeToken(
            workflow_id="wf_123",
            step_id=5,
            step_description="Deploy",
            expires_at=datetime.utcnow() + timedelta(hours=1),
        )

        assert token.expires_at is not None


class TestExecutionResult:
    """Tests for ExecutionResult model"""

    def test_create_execution_result(self):
        """Create an execution result"""
        step_results = [
            StepResult(step_id=1, status=ExecutionStatus.COMPLETED, output="Done"),
            StepResult(step_id=2, status=ExecutionStatus.COMPLETED, output="Done"),
        ]

        result = ExecutionResult(
            workflow_id="wf_123",
            status=ExecutionStatus.COMPLETED,
            step_results=step_results,
            final_output="Workflow completed successfully",
        )

        assert result.status == ExecutionStatus.COMPLETED
        assert len(result.step_results) == 2
        assert result.final_output is not None


class TestVerificationResult:
    """Tests for VerificationResult model"""

    def test_create_verification_result(self):
        """Create a verification result"""
        result = VerificationResult(
            confidence=0.92,
            issues=[],
            hallucination_risk=RiskLevel.LOW,
            security_risk=RiskLevel.LOW,
            next_action="continue",
        )

        assert result.confidence == 0.92
        assert result.next_action == "continue"
        assert result.retry_recommended is False

    def test_verification_with_issues(self):
        """Create verification with issues"""
        result = VerificationResult(
            confidence=0.65,
            issues=["Output contains unverified claims", "Missing citations"],
            hallucination_risk=RiskLevel.MEDIUM,
            security_risk=RiskLevel.LOW,
            retry_recommended=True,
            next_action="retry",
        )

        assert len(result.issues) == 2
        assert result.retry_recommended is True


class TestTaskResult:
    """Tests for TaskResult model"""

    def test_successful_task_result(self):
        """Create a successful task result"""
        result = TaskResult(
            task_id="task_123",
            status=ExecutionStatus.COMPLETED,
            output="Task completed successfully",
            total_tokens={"input": 100, "output": 50},
        )

        assert result.status == ExecutionStatus.COMPLETED
        assert result.output is not None

    def test_task_result_with_verification(self):
        """Create task result with verification"""
        verification = VerificationResult(
            confidence=0.92,
            issues=[],
            next_action="continue",
        )

        result = TaskResult(
            task_id="task_123",
            status=ExecutionStatus.COMPLETED,
            output="Task completed",
            verification=verification,
        )

        assert result.verification.confidence == 0.92
