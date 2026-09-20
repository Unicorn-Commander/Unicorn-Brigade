# Executed by Grok (headless lane)
"""
Tests for Ralph Self-Correcting Workflow Engine

These tests demonstrate Ralph's key capabilities:
- Automatic task breakdown
- Iterative self-correction on failures
- Mid-execution guidance injection
- Progress tracking and state persistence
"""

import pytest
import asyncio
from pathlib import Path
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from app.workflows.ralph_engine import (
    RalphWorkflowEngine,
    RalphWorkflowState,
    RalphTask,
    TaskStatus,
    Iteration,
    IterationOutcome,
)


@pytest.fixture
def sample_workflow():
    """Sample workflow definition"""
    return {
        "id": "test_workflow",
        "name": "Test Workflow",
        "description": "A test workflow for Ralph",
        "steps": [
            {
                "id": "step_1",
                "description": "Research company background",
                "team_lead": "research",
                "max_retries": 3,
            },
            {
                "id": "step_2",
                "description": "Analyze financial data",
                "team_lead": "finance",
                "max_retries": 2,
            },
            {
                "id": "step_3",
                "description": "Generate summary report",
                "worker": "report-writer",
                "max_retries": 2,
            },
        ],
    }


@pytest.fixture
def temp_state_dir(tmp_path):
    """Temporary directory for Ralph state files"""
    state_dir = tmp_path / ".ralph"
    state_dir.mkdir()
    return state_dir


class TestRalphWorkflowEngine:
    """Test suite for Ralph Workflow Engine"""

    def test_initialization(self, sample_workflow, temp_state_dir):
        """Test Ralph engine initialization"""
        engine = RalphWorkflowEngine(
            workflow_id="test_workflow",
            workflow_definition=sample_workflow,
            state_dir=temp_state_dir,
        )

        assert engine.workflow_id == "test_workflow"
        assert engine.workflow_definition == sample_workflow
        assert engine.state_dir == temp_state_dir

    def test_task_breakdown(self, sample_workflow, temp_state_dir):
        """Test workflow is broken down into Ralph tasks"""
        engine = RalphWorkflowEngine(
            workflow_id="test_workflow",
            workflow_definition=sample_workflow,
            state_dir=temp_state_dir,
        )

        inputs = {"company_name": "Acme Corp"}
        engine._initialize_state(inputs)

        # Should have 3 tasks (one per step)
        assert len(engine.state.tasks) == 3

        # Check task properties
        task_1 = RalphTask(**engine.state.tasks["task_1"])
        assert task_1.description == "Research company background"
        assert task_1.assigned_to == "research"
        assert task_1.status == TaskStatus.PENDING
        assert task_1.max_attempts == 3

        # Check dependencies
        task_2 = RalphTask(**engine.state.tasks["task_2"])
        assert "task_1" in task_2.dependencies

        task_3 = RalphTask(**engine.state.tasks["task_3"])
        assert "task_2" in task_3.dependencies

    def test_task_can_execute(self):
        """Test task dependency checking"""
        task = RalphTask(
            id="task_2",
            description="Step 2",
            status=TaskStatus.PENDING,
            dependencies=["task_1"],
        )

        # Cannot execute without dependency
        assert not task.can_execute(set())
        assert not task.can_execute({"task_3"})

        # Can execute when dependency is satisfied
        assert task.can_execute({"task_1"})
        assert task.can_execute({"task_1", "task_3"})

    def test_task_retry_logic(self):
        """Test task retry behavior"""
        task = RalphTask(
            id="task_1",
            description="Test task",
            status=TaskStatus.PENDING,
            max_attempts=3,
        )

        # First attempt fails
        task.status = TaskStatus.FAILED
        task.record_attempt("Error: Connection timeout")
        assert task.should_retry()
        assert task.attempts == 1
        assert len(task.error_history) == 1

        # Second attempt fails
        task.record_attempt("Error: Still timing out")
        assert task.should_retry()
        assert task.attempts == 2

        # Third attempt fails
        task.record_attempt("Error: Persistent failure")
        assert not task.should_retry()  # Max attempts reached
        assert task.attempts == 3

    @pytest.mark.asyncio
    async def test_state_persistence(self, sample_workflow, temp_state_dir):
        """Test state is saved and loaded correctly"""
        engine = RalphWorkflowEngine(
            workflow_id="test_workflow",
            workflow_definition=sample_workflow,
            state_dir=temp_state_dir,
        )

        inputs = {"company_name": "Acme Corp"}
        execution_id = "test_exec_123"

        # Initialize state
        engine.execution_id = execution_id
        engine._initialize_state(inputs)

        # Modify a task
        task_1 = RalphTask(**engine.state.tasks["task_1"])
        task_1.status = TaskStatus.COMPLETED
        task_1.result = {"data": "test"}
        engine.state.tasks["task_1"] = vars(task_1)
        engine._save_state()

        # Create new engine and load state
        engine2 = RalphWorkflowEngine(
            workflow_id="test_workflow",
            workflow_definition=sample_workflow,
            state_dir=temp_state_dir,
        )
        engine2.execution_id = execution_id

        loaded = engine2._load_state()
        assert loaded
        assert engine2.state.workflow_id == "test_workflow"
        assert engine2.state.tasks["task_1"]["status"] == TaskStatus.COMPLETED.value
        assert engine2.state.tasks["task_1"]["result"] == {"data": "test"}

    @pytest.mark.asyncio
    async def test_guidance_injection(self, sample_workflow, temp_state_dir):
        """Test mid-execution guidance injection"""
        engine = RalphWorkflowEngine(
            workflow_id="test_workflow",
            workflow_definition=sample_workflow,
            state_dir=temp_state_dir,
        )

        inputs = {"company_name": "Acme Corp"}
        engine.execution_id = "test_exec_456"
        engine._initialize_state(inputs)

        # Inject guidance
        guidance_text = "Focus on Q4 2025 financial data only"
        engine.inject_guidance(guidance_text)

        assert engine.state.pending_guidance == guidance_text
        assert engine.state.is_paused == False

        # Verify state was saved
        state_file = temp_state_dir / f"{engine.execution_id}.json"
        assert state_file.exists()

    def test_progress_calculation(self, sample_workflow, temp_state_dir):
        """Test progress percentage calculation"""
        engine = RalphWorkflowEngine(
            workflow_id="test_workflow",
            workflow_definition=sample_workflow,
            state_dir=temp_state_dir,
        )

        inputs = {"company_name": "Acme Corp"}
        engine.execution_id = "test_exec_789"
        engine._initialize_state(inputs)

        # Initially 0% complete
        progress = engine.get_progress()
        assert progress["progress_percent"] == 0
        assert progress["tasks"]["total"] == 3
        assert progress["tasks"]["completed"] == 0

        # Complete one task (33%)
        task_1 = RalphTask(**engine.state.tasks["task_1"])
        task_1.status = TaskStatus.COMPLETED
        engine.state.tasks["task_1"] = vars(task_1)

        progress = engine.get_progress()
        assert progress["progress_percent"] == 33
        assert progress["tasks"]["completed"] == 1

        # Complete second task (66%)
        task_2 = RalphTask(**engine.state.tasks["task_2"])
        task_2.status = TaskStatus.COMPLETED
        engine.state.tasks["task_2"] = vars(task_2)

        progress = engine.get_progress()
        assert progress["progress_percent"] == 66
        assert progress["tasks"]["completed"] == 2

        # Complete third task (100%)
        task_3 = RalphTask(**engine.state.tasks["task_3"])
        task_3.status = TaskStatus.COMPLETED
        engine.state.tasks["task_3"] = vars(task_3)

        progress = engine.get_progress()
        assert progress["progress_percent"] == 100
        assert progress["tasks"]["completed"] == 3

    @pytest.mark.asyncio
    async def test_iteration_outcome_success(self, sample_workflow, temp_state_dir):
        """Test iteration ends with SUCCESS when all tasks complete"""
        engine = RalphWorkflowEngine(
            workflow_id="test_workflow",
            workflow_definition=sample_workflow,
            state_dir=temp_state_dir,
        )

        # Mock successful task execution
        async def mock_execute_task(task, iteration_num):
            return {"status": "completed"}

        engine._execute_task = mock_execute_task

        inputs = {"company_name": "Acme Corp"}
        engine.execution_id = "test_success"
        engine._initialize_state(inputs)

        # Run one iteration
        iteration = await engine._run_iteration()

        assert iteration.outcome == IterationOutcome.SUCCESS
        assert iteration.tasks_completed == 3
        assert iteration.tasks_failed == 0
        # Documented first-try success: attempts == 1
        assert all(
            engine.state.tasks[task_id]["attempts"] == 1
            for task_id in engine.state.tasks
        )

    @pytest.mark.asyncio
    async def test_iteration_outcome_retry(self, sample_workflow, temp_state_dir):
        """Test iteration ends with RETRY when tasks fail but can retry"""
        engine = RalphWorkflowEngine(
            workflow_id="test_workflow",
            workflow_definition=sample_workflow,
            state_dir=temp_state_dir,
        )

        # Mock task execution that fails
        call_count = 0

        async def mock_execute_task(task, iteration_num):
            nonlocal call_count
            call_count += 1
            if call_count == 1:  # First task fails
                raise Exception("Temporary failure")
            return {"status": "completed"}

        engine._execute_task = mock_execute_task

        inputs = {"company_name": "Acme Corp"}
        engine.execution_id = "test_retry"
        engine._initialize_state(inputs)

        # Run one iteration
        iteration = await engine._run_iteration()

        # Should retry because max_iterations not reached
        assert iteration.outcome == IterationOutcome.RETRY
        assert iteration.tasks_failed > 0
        assert iteration.error_summary is not None

    def test_result_building(self, sample_workflow, temp_state_dir):
        """Test final result includes complete history"""
        engine = RalphWorkflowEngine(
            workflow_id="test_workflow",
            workflow_definition=sample_workflow,
            state_dir=temp_state_dir,
        )

        inputs = {"company_name": "Acme Corp"}
        engine.execution_id = "test_result"
        engine._initialize_state(inputs)

        # Mark workflow complete
        engine.state.is_complete = True
        engine.state.final_outcome = "success"

        # Complete all tasks
        for task_id in engine.state.tasks:
            task = RalphTask(**engine.state.tasks[task_id])
            task.status = TaskStatus.COMPLETED
            task.result = {"data": f"result_{task_id}"}
            engine.state.tasks[task_id] = vars(task)

        # Add iteration history
        engine.state.iterations.append(
            vars(
                Iteration(
                    number=1,
                    started_at=datetime.now(),
                    completed_at=datetime.now(),
                    outcome=IterationOutcome.SUCCESS,
                    tasks_completed=3,
                    tasks_failed=0,
                )
            )
        )

        result = engine._build_result()

        assert result["workflow_id"] == "test_workflow"
        assert result["execution_id"] == "test_result"
        assert result["outcome"] == "success"
        assert result["iterations"] == 1
        assert len(result["tasks"]) == 3
        assert all(task["status"] == TaskStatus.COMPLETED.value for task in result["tasks"].values())


class TestRalphIntegration:
    """Integration tests for Ralph with hierarchical workflows"""

    @pytest.mark.asyncio
    async def test_full_execution_flow(self, sample_workflow, temp_state_dir):
        """Test complete execution flow with retries"""
        engine = RalphWorkflowEngine(
            workflow_id="test_workflow",
            workflow_definition=sample_workflow,
            state_dir=temp_state_dir,
        )

        # Track execution
        task_complete_calls = []
        iteration_complete_calls = []

        async def on_task_complete(task, result):
            task_complete_calls.append(task.id)

        async def on_iteration_complete(iteration):
            iteration_complete_calls.append(iteration.number)

        engine.on_task_complete = on_task_complete
        engine.on_iteration_complete = on_iteration_complete

        # Mock execution with one retry
        attempt_count = {}

        async def mock_execute_task(task, iteration_num):
            attempt_count[task.id] = attempt_count.get(task.id, 0) + 1

            # Fail task_2 on first attempt
            if task.id == "task_2" and attempt_count[task.id] == 1:
                raise Exception("Simulated failure for testing retry")

            return {"status": "completed", "attempt": attempt_count[task.id]}

        engine._execute_task = mock_execute_task

        # Execute
        result = await engine.execute({"company_name": "Acme Corp"})

        # Verify final result
        assert result["outcome"] == "success"
        assert result["iterations"] >= 1  # Should have at least 1 iteration

        # Verify callbacks were triggered
        assert len(task_complete_calls) == 3
        assert len(iteration_complete_calls) >= 1

        # Documented attempts: first-try success = 1, fail-then-succeed = 2
        assert result["tasks"]["task_1"]["attempts"] == 1
        assert result["tasks"]["task_2"]["attempts"] == 2
        assert result["tasks"]["task_3"]["attempts"] == 1

    @pytest.mark.asyncio
    async def test_success_callback_failure_does_not_count_a_second_execution(
        self, temp_state_dir
    ):
        """Astra c031f5b: one execution + raising callback → attempts == 1."""
        engine = RalphWorkflowEngine(
            workflow_id="synthetic",
            workflow_definition={"steps": [{"description": "synthetic"}]},
            state_dir=temp_state_dir,
        )
        engine.execution_id = "synthetic-counter-review"
        engine._initialize_state({})
        engine._execute_task = AsyncMock(return_value={"ok": True})
        engine.on_task_complete = AsyncMock(
            side_effect=RuntimeError("synthetic callback failure")
        )

        iteration = await engine._run_iteration()

        assert engine._execute_task.await_count == 1
        assert engine.state.tasks["task_1"]["attempts"] == 1
        # Callback error still surfaces as it did before ed92a93: recorded on
        # the task and in the iteration summary, not raised out of the loop.
        assert "synthetic callback failure" in engine.state.tasks["task_1"][
            "error_history"
        ]
        assert engine.state.tasks["task_1"]["status"] == TaskStatus.FAILED.value
        assert iteration.error_summary is not None
        assert "synthetic callback failure" in iteration.error_summary


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
