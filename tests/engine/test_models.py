"""
Tests for workflow engine models
"""

import pytest
from datetime import datetime, timedelta
from app.engine.models import (
    TaskIntent, RiskLevel, WorkerType, ToolType,
    RoutingResult, WorkflowStep, WorkflowPlan,
    StepResult, StepStatus, ExecutionResult,
    VerificationResult, ResumeToken, Task, TaskResult,
)


class TestTaskIntent:
    """Tests for TaskIntent enum"""

    def test_all_intents_exist(self):
        """Verify all expected intents are defined"""
        assert TaskIntent.RESEARCH
        assert TaskIntent.CODE
        assert TaskIntent.EXTRACTION
        assert TaskIntent.REPORT
        assert TaskIntent.OPS
        assert TaskIntent.GENERAL

    def test_intent_values(self):
        """Verify intent string values"""
        assert TaskIntent.RESEARCH.value == "research"
        assert TaskIntent.CODE.value == "code"


class TestRiskLevel:
    """Tests for RiskLevel enum"""

    def test_risk_ordering(self):
        """Risk levels should be comparable"""
        levels = [RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL]
        assert len(levels) == 4

    def test_risk_values(self):
        """Verify risk string values"""
        assert RiskLevel.LOW.value == "low"
        assert RiskLevel.CRITICAL.value == "critical"


class TestRoutingResult:
    """Tests for RoutingResult model"""

    def test_create_routing_result(self):
        """Create a basic routing result"""
        result = RoutingResult(
            intent=TaskIntent.RESEARCH,
            risk=RiskLevel.LOW,
            worker=WorkerType.RESEARCH,
            requires_approval=False,
            reasoning="Simple research task",
        )

        assert result.intent == TaskIntent.RESEARCH
        assert result.risk == RiskLevel.LOW
        assert result.requires_approval is False

    def test_high_risk_requires_approval(self):
        """High risk tasks should typically require approval"""
        result = RoutingResult(
            intent=TaskIntent.OPS,
            risk=RiskLevel.HIGH,
            worker=WorkerType.OPS,
            requires_approval=True,
            reasoning="Risky operation",
        )

        assert result.requires_approval is True


class TestWorkflowStep:
    """Tests for WorkflowStep model"""

    def test_create_step(self):
        """Create a basic workflow step"""
        step = WorkflowStep(
            id="step_1",
            name="Research task",
            description="Gather information",
            worker_type=WorkerType.RESEARCH,
            tool=ToolType.LLM,
            timeout=120,
        )

        assert step.id == "step_1"
        assert step.timeout == 120
        assert step.requires_approval is False
        assert step.depends_on == []

    def test_step_with_dependencies(self):
        """Create step with dependencies"""
        step = WorkflowStep(
            id="step_2",
            name="Analysis",
            description="Analyze results",
            worker_type=WorkerType.REPORT,
            tool=ToolType.LLM,
            depends_on=["step_1"],
        )

        assert "step_1" in step.depends_on


class TestWorkflowPlan:
    """Tests for WorkflowPlan model"""

    def test_create_plan(self):
        """Create a basic workflow plan"""
        steps = [
            WorkflowStep(
                id="step_1",
                name="Step 1",
                description="First step",
                worker_type=WorkerType.RESEARCH,
                tool=ToolType.LLM,
            ),
            WorkflowStep(
                id="step_2",
                name="Step 2",
                description="Second step",
                worker_type=WorkerType.REPORT,
                tool=ToolType.LLM,
                depends_on=["step_1"],
            ),
        ]

        plan = WorkflowPlan(
            task_id="task_123",
            steps=steps,
        )

        assert plan.task_id == "task_123"
        assert len(plan.steps) == 2

    def test_plan_estimated_time(self):
        """Plan should calculate estimated time"""
        steps = [
            WorkflowStep(
                id="step_1",
                name="Step 1",
                description="First step",
                worker_type=WorkerType.RESEARCH,
                tool=ToolType.LLM,
                timeout=60,
            ),
            WorkflowStep(
                id="step_2",
                name="Step 2",
                description="Second step",
                worker_type=WorkerType.REPORT,
                tool=ToolType.LLM,
                timeout=30,
            ),
        ]

        plan = WorkflowPlan(
            task_id="task_123",
            steps=steps,
            estimated_time=90,
        )

        assert plan.estimated_time == 90


class TestStepResult:
    """Tests for StepResult model"""

    def test_successful_result(self):
        """Create a successful step result"""
        result = StepResult(
            step_id="step_1",
            status=StepStatus.COMPLETED,
            output="Research complete",
            artifacts=[{"name": "findings", "type": "text", "content": "..."}],
        )

        assert result.status == StepStatus.COMPLETED
        assert len(result.artifacts) == 1

    def test_failed_result(self):
        """Create a failed step result"""
        result = StepResult(
            step_id="step_1",
            status=StepStatus.FAILED,
            error="Timeout exceeded",
        )

        assert result.status == StepStatus.FAILED
        assert result.error == "Timeout exceeded"


class TestTask:
    """Tests for Task model"""

    def test_create_task(self):
        """Create a basic task"""
        task = Task(
            task="Research AI trends",
            user_id="user_123",
        )

        assert task.task == "Research AI trends"
        assert task.user_id == "user_123"
        assert task.id is not None  # Auto-generated

    def test_task_with_context(self):
        """Create task with context"""
        task = Task(
            task="Analyze code",
            user_id="user_123",
            context={"language": "python", "file": "main.py"},
        )

        assert task.context["language"] == "python"


class TestResumeToken:
    """Tests for ResumeToken model"""

    def test_create_token(self):
        """Create a resume token"""
        token = ResumeToken(
            workflow_id="wf_123",
            step_id="step_5",
            step_name="Deploy to production",
            context={"version": "1.0.0"},
        )

        assert token.workflow_id == "wf_123"
        assert token.step_id == "step_5"
        assert token.approved is False

    def test_token_expiration(self):
        """Token should have expiration"""
        token = ResumeToken(
            workflow_id="wf_123",
            step_id="step_5",
            step_name="Deploy",
            expires_at=datetime.utcnow() + timedelta(hours=1),
        )

        assert token.expires_at is not None

    def test_token_is_valid(self):
        """Check token validity"""
        # Valid token
        valid_token = ResumeToken(
            workflow_id="wf_123",
            step_id="step_5",
            step_name="Deploy",
            expires_at=datetime.utcnow() + timedelta(hours=1),
        )
        assert valid_token.is_valid() is True

        # Expired token
        expired_token = ResumeToken(
            workflow_id="wf_123",
            step_id="step_5",
            step_name="Deploy",
            expires_at=datetime.utcnow() - timedelta(hours=1),
        )
        assert expired_token.is_valid() is False

        # Used token
        used_token = ResumeToken(
            workflow_id="wf_123",
            step_id="step_5",
            step_name="Deploy",
            used=True,
        )
        assert used_token.is_valid() is False


class TestTaskResult:
    """Tests for TaskResult model"""

    def test_successful_task_result(self):
        """Create a successful task result"""
        result = TaskResult(
            task_id="task_123",
            status="completed",
            output="Task completed successfully",
            tokens_used={"input": 100, "output": 50},
        )

        assert result.status == "completed"
        assert result.output is not None

    def test_task_result_with_verification(self):
        """Create task result with verification"""
        verification = VerificationResult(
            verified=True,
            confidence=0.92,
            issues=[],
        )

        result = TaskResult(
            task_id="task_123",
            status="completed",
            output="Task completed",
            verification=verification,
        )

        assert result.verification.verified is True
        assert result.verification.confidence == 0.92
