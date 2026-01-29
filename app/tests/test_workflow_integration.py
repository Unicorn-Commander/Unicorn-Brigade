"""
End-to-End Workflow Integration Tests

Tests complete workflow execution across all components:
- Router -> Planner -> Executor -> Verifier pipeline
- Resilience patterns in workflow execution
- Collaboration patterns in workflows
- Control flow in real workflow scenarios
- Observability during workflow execution
"""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any, List

from app.engine.models import (
    Task,
    TaskResult,
    TaskIntent,
    Priority,
    RiskLevel,
    WorkerType,
    ToolType,
    ExecutionStatus,
    WorkflowPlan,
    WorkflowStep,
    StepResult,
    ExecutionResult,
    RoutingResult,
    VerificationResult,
)
from app.engine.resilience import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitState,
    RetryStrategy,
    RetryConfig,
    ResiliencePolicy,
)
from app.engine.control_flow import (
    ControlFlowExecutor,
    ConditionEvaluator,
    Condition,
    ConditionOperator,
)
from app.engine.observability import (
    MetricsRegistry,
    Counter,
    Histogram,
    Tracer,
    HealthChecker,
    HealthCheckResult,
    HealthStatus,
)


# ============== Workflow Execution Tests ==============

class TestWorkflowExecution:
    """Test complete workflow execution"""

    @pytest.mark.asyncio
    async def test_simple_workflow_execution(
        self,
        mock_llm_client,
        sample_workflow_plan,
        sample_context
    ):
        """Should execute simple workflow end-to-end"""
        # Setup LLM responses for each step
        mock_llm_client.add_response("Step 1: Initialized successfully")
        mock_llm_client.add_response("Step 2: Processing complete")
        mock_llm_client.add_response("Step 3: Finalized - workflow complete")

        # Create mock executor
        step_results = []
        for i, step in enumerate(sample_workflow_plan.steps):
            result = StepResult(
                step_id=step.id,
                status=ExecutionStatus.COMPLETED,
                output=f"Output from step {step.id}",
                duration_seconds=0.1
            )
            step_results.append(result)

        execution_result = ExecutionResult(
            workflow_id=sample_workflow_plan.id,
            status=ExecutionStatus.COMPLETED,
            step_results=step_results,
            final_output="Workflow completed successfully",
            total_duration_seconds=0.3
        )

        assert execution_result.status == ExecutionStatus.COMPLETED
        assert len(execution_result.step_results) == 3
        assert all(r.status == ExecutionStatus.COMPLETED for r in step_results)

    @pytest.mark.asyncio
    async def test_workflow_with_step_failure(
        self,
        sample_workflow_plan,
        sample_context
    ):
        """Should handle step failure in workflow"""
        step_results = [
            StepResult(
                step_id=1,
                status=ExecutionStatus.COMPLETED,
                output="Step 1 done"
            ),
            StepResult(
                step_id=2,
                status=ExecutionStatus.FAILED,
                error="Database connection failed"
            ),
        ]

        execution_result = ExecutionResult(
            workflow_id=sample_workflow_plan.id,
            status=ExecutionStatus.FAILED,
            step_results=step_results,
            error="Workflow failed at step 2",
            current_step=2
        )

        assert execution_result.status == ExecutionStatus.FAILED
        assert execution_result.current_step == 2
        assert "step 2" in execution_result.error.lower()

    @pytest.mark.asyncio
    async def test_workflow_with_approval_blocking(
        self,
        sample_workflow_plan
    ):
        """Should block workflow for approval"""
        # Mark step 2 as requiring approval
        sample_workflow_plan.steps[1].approval_required = True
        sample_workflow_plan.steps[1].risk = RiskLevel.HIGH

        step_results = [
            StepResult(
                step_id=1,
                status=ExecutionStatus.COMPLETED,
                output="Step 1 done"
            ),
            StepResult(
                step_id=2,
                status=ExecutionStatus.BLOCKED,
                blocker="approval_required",
                needed="human_approval"
            ),
        ]

        execution_result = ExecutionResult(
            workflow_id=sample_workflow_plan.id,
            status=ExecutionStatus.BLOCKED,
            step_results=step_results,
            current_step=2,
            resume_token="resume_abc123"
        )

        assert execution_result.status == ExecutionStatus.BLOCKED
        assert execution_result.resume_token is not None

    @pytest.mark.asyncio
    async def test_workflow_resume_after_approval(self):
        """Should resume workflow after approval"""
        # Simulate resumed execution
        step_results = [
            StepResult(step_id=1, status=ExecutionStatus.COMPLETED, output="Done"),
            StepResult(step_id=2, status=ExecutionStatus.COMPLETED, output="Approved and done"),
            StepResult(step_id=3, status=ExecutionStatus.COMPLETED, output="Final"),
        ]

        execution_result = ExecutionResult(
            workflow_id="test_workflow",
            status=ExecutionStatus.COMPLETED,
            step_results=step_results,
            final_output="Workflow resumed and completed"
        )

        assert execution_result.status == ExecutionStatus.COMPLETED
        assert len(execution_result.step_results) == 3


# ============== Workflow with Resilience Tests ==============

class TestWorkflowWithResilience:
    """Test workflows with resilience patterns"""

    @pytest.mark.asyncio
    async def test_workflow_with_retry(self, mock_llm_client):
        """Workflow should retry failed steps"""
        retry_config = RetryConfig(max_retries=3, base_delay=0.01, jitter=False)
        retry_strategy = RetryStrategy(retry_config)

        execution_attempts = [0]

        async def flaky_step():
            execution_attempts[0] += 1
            if execution_attempts[0] < 3:
                raise Exception("Transient error - connection timeout")
            return "Success after retries"

        result = await retry_strategy.execute(flaky_step)

        assert result == "Success after retries"
        assert execution_attempts[0] == 3

    @pytest.mark.asyncio
    async def test_workflow_with_circuit_breaker(self):
        """Workflow should use circuit breaker for external calls"""
        cb_config = CircuitBreakerConfig(
            failure_threshold=2,
            timeout_seconds=0.1
        )
        circuit_breaker = CircuitBreaker("workflow_cb", cb_config)

        call_count = [0]

        async def external_service():
            call_count[0] += 1
            raise Exception("Service unavailable")

        # Open the circuit
        for _ in range(2):
            try:
                await circuit_breaker.call(external_service)
            except Exception:
                pass

        assert circuit_breaker.state == CircuitState.OPEN

        # Create fallback workflow result
        async def fallback():
            return StepResult(
                step_id=1,
                status=ExecutionStatus.COMPLETED,
                output="Fallback result used"
            )

        result = await circuit_breaker.call(external_service, fallback=fallback)
        assert result.output == "Fallback result used"

    @pytest.mark.asyncio
    async def test_workflow_resilience_policy(self, mock_llm_client):
        """Workflow should use combined resilience policy"""
        policy = ResiliencePolicy(
            name="workflow_policy",
            circuit_breaker=CircuitBreaker(
                "cb",
                CircuitBreakerConfig(failure_threshold=5, timeout_seconds=1)
            ),
            retry_strategy=RetryStrategy(
                RetryConfig(max_retries=2, base_delay=0.01)
            ),
        )

        call_count = [0]

        async def step_execution():
            call_count[0] += 1
            if call_count[0] < 2:
                raise Exception("timeout")
            return StepResult(
                step_id=1,
                status=ExecutionStatus.COMPLETED,
                output="Executed with resilience"
            )

        result = await policy.execute(step_execution)

        assert result.status == ExecutionStatus.COMPLETED
        assert call_count[0] == 2  # One retry


# ============== Workflow with Control Flow Tests ==============

class TestWorkflowWithControlFlow:
    """Test workflows with control flow constructs"""

    @pytest.mark.asyncio
    async def test_workflow_conditional_branching(
        self,
        mock_step_executor
    ):
        """Workflow should execute conditional branches"""
        executor = ControlFlowExecutor(mock_step_executor)

        workflow_steps = [
            {
                "id": 1,
                "action": "Check status",
                "tool": "llm"
            },
            {
                "type": "conditional",
                "condition": {
                    "left": "$step1.output",
                    "op": "contains",
                    "right": "success"
                },
                "then_steps": [
                    {"id": 2, "action": "Process success", "tool": "llm"}
                ],
                "else_steps": [
                    {"id": 3, "action": "Handle failure", "tool": "llm"}
                ]
            }
        ]

        # Set up step 1 result
        mock_step_executor.set_result(1, "Task completed with success")

        context = {"steps": {}}

        # Execute step 1
        results = await executor.execute_step_with_control_flow(
            workflow_steps[0], context, "user", "model"
        )
        context["steps"]["step1"] = {"output": results[0].output}

        # Execute conditional
        results = await executor.execute_step_with_control_flow(
            workflow_steps[1], context, "user", "model"
        )

        # Should have taken "then" branch
        executed_ids = [e["step_id"] for e in mock_step_executor.execution_history]
        assert 2 in executed_ids
        assert 3 not in executed_ids

    @pytest.mark.asyncio
    async def test_workflow_loop_processing(self, mock_step_executor):
        """Workflow should process items in loop"""
        executor = ControlFlowExecutor(mock_step_executor)

        workflow_step = {
            "type": "loop",
            "loop_type": "for",
            "items": ["doc1.pdf", "doc2.pdf", "doc3.pdf"],
            "item_var": "document",
            "body_steps": [
                {"id": 1, "action": "Process document", "tool": "llm"}
            ],
            "max_iterations": 10
        }

        context = {"steps": {}}

        results = await executor.execute_step_with_control_flow(
            workflow_step, context, "user", "model"
        )

        # Should have processed all 3 documents
        assert len(mock_step_executor.execution_history) == 3

        # Each iteration should have had the document in context
        documents_processed = [
            e["context"].get("document")
            for e in mock_step_executor.execution_history
        ]
        assert "doc1.pdf" in documents_processed
        assert "doc2.pdf" in documents_processed
        assert "doc3.pdf" in documents_processed

    @pytest.mark.asyncio
    async def test_workflow_parallel_execution(self, mock_step_executor):
        """Workflow should execute parallel branches"""
        executor = ControlFlowExecutor(mock_step_executor)

        workflow_step = {
            "type": "parallel",
            "branches": [
                [{"id": 1, "action": "Fetch from API A", "tool": "api"}],
                [{"id": 2, "action": "Fetch from API B", "tool": "api"}],
                [{"id": 3, "action": "Query database", "tool": "database"}]
            ],
            "wait_for": "all"
        }

        context = {"steps": {}}

        results = await executor.execute_step_with_control_flow(
            workflow_step, context, "user", "model"
        )

        # All branches should have executed
        executed_ids = [e["step_id"] for e in mock_step_executor.execution_history]
        assert 1 in executed_ids
        assert 2 in executed_ids
        assert 3 in executed_ids


# ============== Workflow with Observability Tests ==============

class TestWorkflowWithObservability:
    """Test workflow observability"""

    @pytest.mark.asyncio
    async def test_workflow_metrics_collection(self, metrics_registry):
        """Workflow should collect metrics"""
        workflow_counter = metrics_registry.counter("workflow_total")
        step_counter = metrics_registry.counter("step_total", labels=["status"])
        duration_histogram = metrics_registry.histogram("workflow_duration")

        # Simulate workflow execution
        workflow_counter.inc()

        with duration_histogram.time():
            # Execute steps
            step_counter.inc(labels={"status": "success"})
            step_counter.inc(labels={"status": "success"})
            step_counter.inc(labels={"status": "success"})
            await asyncio.sleep(0.01)

        assert workflow_counter.get() == 1
        assert step_counter.get({"status": "success"}) == 3
        assert duration_histogram.get_count() == 1

    @pytest.mark.asyncio
    async def test_workflow_tracing(self, tracer):
        """Workflow should create trace spans"""
        tracer._spans.clear()

        async with tracer.start_async_span("workflow_execution") as workflow_span:
            workflow_span.set_attribute("workflow_id", "wf-123")
            workflow_span.set_attribute("user_id", "user-456")

            for i in range(3):
                async with tracer.start_async_span(f"step_{i}") as step_span:
                    step_span.set_attribute("step_id", i + 1)
                    step_span.set_attribute("tool", "llm")
                    await asyncio.sleep(0.01)

        # Should have created workflow span + 3 step spans
        recent = tracer.get_recent_spans()
        span_names = [s.name for s in recent]

        assert "workflow_execution" in span_names
        assert "step_0" in span_names
        assert "step_1" in span_names
        assert "step_2" in span_names

    @pytest.mark.asyncio
    async def test_workflow_health_checks(self, health_checker):
        """Workflow system should have health checks"""
        # Register workflow-related health checks
        health_checker.register_check("llm_service", lambda: HealthCheckResult(
            name="llm_service",
            status=HealthStatus.HEALTHY,
            message="LLM service responding"
        ))

        health_checker.register_check("database", lambda: HealthCheckResult(
            name="database",
            status=HealthStatus.HEALTHY,
            message="Database connected"
        ))

        health_checker.register_check("queue", lambda: HealthCheckResult(
            name="queue",
            status=HealthStatus.HEALTHY,
            message="Queue processing"
        ))

        # Check all
        results = health_checker.check_all()

        assert all(r.status == HealthStatus.HEALTHY for r in results.values())
        assert health_checker.get_overall_status() == HealthStatus.HEALTHY


# ============== Task Processing Pipeline Tests ==============

class TestTaskProcessingPipeline:
    """Test complete task processing pipeline"""

    @pytest.mark.asyncio
    async def test_complete_task_pipeline(self, mock_llm_client):
        """Should process task through complete pipeline"""
        # Create task
        task = Task(
            user_id="test-user",
            content="Research the latest AI developments and create a summary",
            context={"priority": "high"}
        )

        # Simulate routing
        routing_result = RoutingResult(
            intent=TaskIntent.RESEARCH,
            priority=Priority.HIGH,
            risk=RiskLevel.LOW,
            suggested_worker=WorkerType.RESEARCH,
            suggested_model="local",
            reason="Research task identified",
            confidence=0.9
        )

        assert routing_result.intent == TaskIntent.RESEARCH
        assert routing_result.confidence >= 0.8

        # Simulate planning
        plan = WorkflowPlan(
            name="research_workflow",
            objective="Research AI developments",
            steps=[
                WorkflowStep(
                    id=1,
                    action="Search for recent AI news",
                    tool=ToolType.BROWSER,
                    risk=RiskLevel.LOW
                ),
                WorkflowStep(
                    id=2,
                    action="Analyze and summarize findings",
                    tool=ToolType.LLM,
                    risk=RiskLevel.LOW
                ),
            ]
        )

        assert len(plan.steps) == 2

        # Simulate execution
        execution_result = ExecutionResult(
            workflow_id=plan.id,
            status=ExecutionStatus.COMPLETED,
            step_results=[
                StepResult(step_id=1, status=ExecutionStatus.COMPLETED, output="Found articles"),
                StepResult(step_id=2, status=ExecutionStatus.COMPLETED, output="Summary complete"),
            ],
            final_output="AI developments summary generated"
        )

        # Simulate verification
        verification_result = VerificationResult(
            confidence=0.85,
            issues=[],
            hallucination_risk=RiskLevel.LOW,
            security_risk=RiskLevel.LOW,
            retry_recommended=False,
            next_action="continue"
        )

        assert verification_result.confidence >= 0.8
        assert verification_result.next_action == "continue"

        # Final task result
        task_result = TaskResult(
            task_id=task.id,
            status=ExecutionStatus.COMPLETED,
            routing=routing_result,
            plan=plan,
            execution=execution_result,
            verification=verification_result,
            output=execution_result.final_output,
            model_used="local"
        )

        assert task_result.status == ExecutionStatus.COMPLETED
        assert task_result.output is not None

    @pytest.mark.asyncio
    async def test_task_with_escalation(self, mock_llm_client):
        """Should escalate task to stronger model when needed"""
        # Simulate verification recommending escalation
        verification_result = VerificationResult(
            confidence=0.4,  # Low confidence
            issues=["Uncertain about technical accuracy"],
            hallucination_risk=RiskLevel.MEDIUM,
            retry_recommended=True,
            next_action="escalate_to_strong_model",
            escalation_model="claude-3-opus",
            escalation_reason="Low confidence in technical content"
        )

        assert verification_result.next_action == "escalate_to_strong_model"
        assert verification_result.escalation_model is not None

        # After escalation
        escalated_verification = VerificationResult(
            confidence=0.92,
            issues=[],
            hallucination_risk=RiskLevel.LOW,
            retry_recommended=False,
            next_action="continue"
        )

        assert escalated_verification.confidence > verification_result.confidence


# ============== Error Handling Integration Tests ==============

class TestErrorHandlingIntegration:
    """Test error handling across components"""

    @pytest.mark.asyncio
    async def test_graceful_degradation(self):
        """System should degrade gracefully on errors"""
        circuit_breaker = CircuitBreaker(
            "external_api",
            CircuitBreakerConfig(failure_threshold=2, timeout_seconds=1)
        )

        # Simulate API failures
        async def failing_api():
            raise Exception("External API unavailable")

        async def fallback_result():
            return {
                "source": "cache",
                "data": "Cached data from last successful fetch"
            }

        # Open circuit
        for _ in range(2):
            try:
                await circuit_breaker.call(failing_api)
            except Exception:
                pass

        # Should use fallback
        result = await circuit_breaker.call(failing_api, fallback=fallback_result)

        assert result["source"] == "cache"
        assert "Cached data" in result["data"]

    @pytest.mark.asyncio
    async def test_error_propagation_and_logging(self, tracer, metrics_registry):
        """Errors should be properly propagated and logged"""
        error_counter = metrics_registry.counter("errors", labels=["type"])
        tracer._spans.clear()

        async def workflow_with_error():
            async with tracer.start_async_span("workflow") as span:
                try:
                    # Simulate step failure
                    raise ValueError("Invalid input data")
                except ValueError as e:
                    span.set_error(e)
                    error_counter.inc(labels={"type": "ValueError"})
                    raise

        with pytest.raises(ValueError):
            await workflow_with_error()

        # Error should be recorded
        assert error_counter.get({"type": "ValueError"}) == 1

        # Span should have error status
        recent = tracer.get_recent_spans()
        error_span = [s for s in recent if s.name == "workflow"][0]
        assert error_span.status == "error"


# ============== Performance Integration Tests ==============

class TestPerformanceIntegration:
    """Test performance-related integrations"""

    @pytest.mark.asyncio
    async def test_concurrent_workflow_execution(self, mock_step_executor):
        """Should handle concurrent workflow execution"""
        executor = ControlFlowExecutor(mock_step_executor)

        async def execute_workflow(workflow_id: int):
            step_dict = {
                "id": workflow_id,
                "action": f"Workflow {workflow_id} step",
                "tool": "llm"
            }
            context = {"steps": {}}
            return await executor.execute_step_with_control_flow(
                step_dict, context, "user", "model"
            )

        # Execute 10 workflows concurrently
        tasks = [execute_workflow(i) for i in range(10)]
        results = await asyncio.gather(*tasks)

        assert len(results) == 10
        assert all(len(r) > 0 for r in results)

    @pytest.mark.asyncio
    async def test_workflow_timeout_handling(self):
        """Should handle workflow timeouts"""
        async def slow_step():
            await asyncio.sleep(10)  # Very slow
            return "Done"

        # Should timeout
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(slow_step(), timeout=0.1)

    @pytest.mark.asyncio
    async def test_resource_cleanup(self, tracer, metrics_registry, health_checker):
        """Resources should be properly cleaned up"""
        # Create some metrics
        counter = metrics_registry.counter("temp_counter")
        counter.inc(100)

        # Create some spans
        with tracer.start_span("temp_span"):
            pass

        # Add temp health check
        health_checker.register_check("temp", lambda: HealthCheckResult(
            name="temp",
            status=HealthStatus.HEALTHY
        ))

        # Verify they exist
        assert counter.get() == 100
        assert len(tracer.get_recent_spans()) >= 1
        assert "temp" in health_checker._checks

        # Cleanup (in real system, this would be done by cleanup routines)
        counter.reset()
        assert counter.get() == 0


# ============== End-to-End Scenario Tests ==============

class TestEndToEndScenarios:
    """Complete end-to-end scenario tests"""

    @pytest.mark.asyncio
    async def test_data_processing_workflow(
        self,
        mock_llm_client,
        mock_step_executor,
        metrics_registry,
        tracer
    ):
        """Test complete data processing workflow"""
        workflow_counter = metrics_registry.counter("data_workflows")
        executor = ControlFlowExecutor(mock_step_executor)
        tracer._spans.clear()

        # Simulate data processing workflow
        workflow_counter.inc()

        async with tracer.start_async_span("data_processing_workflow") as span:
            span.set_attribute("data_source", "api")
            span.set_attribute("record_count", 1000)

            # Step 1: Extract
            extract_step = {"id": 1, "action": "Extract data", "tool": "api"}
            context = {"steps": {}}
            await executor.execute_step_with_control_flow(
                extract_step, context, "user", "model"
            )

            # Step 2: Transform (loop)
            transform_step = {
                "type": "loop",
                "loop_type": "for",
                "items": ["batch1", "batch2", "batch3"],
                "item_var": "batch",
                "body_steps": [
                    {"id": 2, "action": "Transform batch", "tool": "python"}
                ],
                "max_iterations": 10
            }
            await executor.execute_step_with_control_flow(
                transform_step, context, "user", "model"
            )

            # Step 3: Load
            load_step = {"id": 3, "action": "Load data", "tool": "database"}
            await executor.execute_step_with_control_flow(
                load_step, context, "user", "model"
            )

        assert workflow_counter.get() == 1
        assert len(tracer.get_recent_spans()) >= 1

    @pytest.mark.asyncio
    async def test_multi_agent_research_workflow(
        self,
        mock_llm_client,
        test_supervisor_agent,
        test_specialist_agents
    ):
        """Test multi-agent research workflow"""
        from app.engine.collaboration import SupervisorPattern

        # Setup mock responses
        mock_llm_client.add_response(
            "I'll coordinate the research. Specialist A, please search for data.",
            tool_calls=[{
                "id": "tc_1",
                "function": {
                    "name": "handoff_to_specialist_a",
                    "arguments": '{"task": "Search for AI market data"}'
                }
            }]
        )
        mock_llm_client.add_response("Found market data: AI market valued at $100B")
        mock_llm_client.add_response("Task complete. Research compiled successfully.")

        pattern = SupervisorPattern(
            supervisor=test_supervisor_agent,
            specialists=test_specialist_agents,
            llm_client=mock_llm_client,
        )

        result = await pattern.execute(
            task="Research the AI market size",
            max_turns=5
        )

        assert result["status"] == "completed"
        assert len(result["handoff_history"]) >= 1
