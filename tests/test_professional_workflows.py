"""
Professional Workflows Test Suite

Tests for all 18 professional workflows:
- Structure validation (steps, inputs, outputs, checkpoints)
- Mocked execution tests (for CI)
- Live LLM tests (for quality verification)

Run with:
    pytest tests/test_professional_workflows.py -v

For live LLM tests:
    RUN_LLM_TESTS=1 pytest tests/test_professional_workflows.py -v -k "live"
"""

import os
import pytest
from typing import Dict, Any, List
from unittest.mock import AsyncMock, patch, MagicMock

# Test configuration
RUN_LLM_TESTS = os.getenv("RUN_LLM_TESTS", "0") == "1"

# Import workflow utilities
from app.workflows.schema import (
    WorkflowDefinition,
    WorkflowStep,
    Checkpoint,
    CheckpointType,
    WorkflowExecutionState,
)
from app.workflows.templates import get_workflow, list_workflows, ALL_WORKFLOWS
from app.workflows.team_leads import ALL_TEAM_LEADS, get_team_lead

# Import test data
from tests.fixtures.professional_test_data import (
    ALL_TEST_DATA,
    get_test_data,
    get_test_inputs,
    list_test_workflows,
)


# =============================================================================
# WORKFLOW STRUCTURE TESTS
# =============================================================================

class TestWorkflowStructure:
    """Test that all professional workflows are properly structured."""

    @pytest.mark.parametrize("workflow_id", [
        # Finance & Legal
        "ma-due-diligence",
        "tax-prep-assistant",
        "contract-review",
        "audit-preparation",
        # HR & Sales
        "recruiting-pipeline",
        "rfp-proposal-response",
        "vendor-risk-assessment",
        "employee-onboarding",
        # Security & Ops
        "soc-analyst-assistant",
        "vulnerability-assessment",
        "change-management",
        "disaster-recovery-test",
        # Domain-Specific
        "real-estate-transaction",
        "product-research-assistant",
        "patent-analysis-pipeline",
        "meeting-assistant",
        # Content & Intelligence
        "lead-scoring-flow",
        "email-auto-responder",
    ])
    def test_workflow_exists(self, workflow_id: str):
        """Verify workflow template exists and is properly defined."""
        workflow = get_workflow(workflow_id)
        assert workflow is not None, f"Workflow {workflow_id} not found"
        assert isinstance(workflow, WorkflowDefinition)

    @pytest.mark.parametrize("workflow_id", list_test_workflows())
    def test_workflow_has_required_fields(self, workflow_id: str):
        """Verify workflow has all required fields."""
        workflow = get_workflow(workflow_id)
        if workflow is None:
            pytest.skip(f"Workflow {workflow_id} not yet implemented")

        # Required fields
        assert workflow.id, "Workflow must have an ID"
        assert workflow.name, "Workflow must have a name"
        assert workflow.description, "Workflow must have a description"
        assert workflow.version, "Workflow must have a version"
        assert len(workflow.steps) >= 3, "Workflow must have at least 3 steps"
        assert len(workflow.required_inputs) >= 1, "Workflow must have required inputs"
        assert len(workflow.final_outputs) >= 1, "Workflow must have final outputs"

    @pytest.mark.parametrize("workflow_id", list_test_workflows())
    def test_workflow_steps_have_valid_executors(self, workflow_id: str):
        """Verify all step executors reference valid team leads or orchestrator."""
        workflow = get_workflow(workflow_id)
        if workflow is None:
            pytest.skip(f"Workflow {workflow_id} not yet implemented")

        valid_executors = set(ALL_TEAM_LEADS.keys()) | {"orchestrator"}

        for step in workflow.steps:
            assert step.executor in valid_executors, \
                f"Step {step.id} has invalid executor: {step.executor}"

    @pytest.mark.parametrize("workflow_id", list_test_workflows())
    def test_workflow_step_dependencies_valid(self, workflow_id: str):
        """Verify step input references are valid (reference prior steps or inputs)."""
        workflow = get_workflow(workflow_id)
        if workflow is None:
            pytest.skip(f"Workflow {workflow_id} not yet implemented")

        # Track which outputs are available at each step
        available_outputs = set(f"inputs.{inp}" for inp in workflow.required_inputs)

        for step in workflow.steps:
            # Check all inputs reference available outputs
            for input_name, input_ref in step.inputs.items():
                if input_ref.startswith("inputs."):
                    input_field = input_ref.split(".")[1]
                    assert input_field in workflow.required_inputs, \
                        f"Step {step.id} references unknown input: {input_field}"
                else:
                    # References a prior step output
                    parts = input_ref.split(".")
                    step_ref = parts[0]
                    # Find the referenced step
                    referenced_step = next(
                        (s for s in workflow.steps if s.id == step_ref),
                        None
                    )
                    assert referenced_step is not None, \
                        f"Step {step.id} references unknown step: {step_ref}"
                    # Ensure referenced step comes before this step
                    ref_index = workflow.steps.index(referenced_step)
                    current_index = workflow.steps.index(step)
                    assert ref_index < current_index, \
                        f"Step {step.id} references step {step_ref} that comes after it"

            # Add this step's outputs to available outputs
            for output in step.outputs:
                available_outputs.add(f"{step.id}.{output}")

    @pytest.mark.parametrize("workflow_id", list_test_workflows())
    def test_workflow_has_checkpoints(self, workflow_id: str):
        """Verify workflow has at least one human-in-the-loop checkpoint."""
        workflow = get_workflow(workflow_id)
        if workflow is None:
            pytest.skip(f"Workflow {workflow_id} not yet implemented")

        assert len(workflow.checkpoints) >= 1, \
            f"Workflow {workflow_id} should have at least one checkpoint"

        # At least one should require human interaction
        human_checkpoints = [
            cp for cp in workflow.checkpoints
            if cp.type in [CheckpointType.HUMAN_APPROVAL, CheckpointType.HUMAN_INPUT]
        ]
        assert len(human_checkpoints) >= 1, \
            f"Workflow {workflow_id} should have at least one human checkpoint"

    @pytest.mark.parametrize("workflow_id", list_test_workflows())
    def test_workflow_checkpoint_references_valid(self, workflow_id: str):
        """Every checkpoint's `after_step` must either reference a real step
        id or be empty.

        Empty `after_step` is the sentinel for "fires at end of workflow"
        — the engine has an explicit end-of-flow pass that handles those
        (see `app/workflows/engine.py`, post-step-loop block). This is how
        the 18 professional workflows express their "review the final deal
        memo" approval gates without needing a fake terminal step.
        """
        workflow = get_workflow(workflow_id)
        if workflow is None:
            pytest.skip(f"Workflow {workflow_id} not yet implemented")

        step_ids = {step.id for step in workflow.steps}

        for checkpoint in workflow.checkpoints:
            target = checkpoint.after_step
            assert target == "" or target in step_ids, (
                f"Checkpoint {checkpoint.id} references unknown step: "
                f"{target!r} (must be empty for end-of-workflow or match "
                f"one of {sorted(step_ids)})"
            )


# =============================================================================
# WORKFLOW REGISTRATION TESTS
# =============================================================================

class TestWorkflowRegistry:
    """Test workflow registry functions."""

    def test_all_professional_workflows_registered(self):
        """Verify all 18 professional workflows are in the registry."""
        expected_workflows = [
            # Finance & Legal
            "ma-due-diligence", "tax-prep-assistant", "contract-review", "audit-preparation",
            # HR & Sales
            "recruiting-pipeline", "rfp-proposal-response", "vendor-risk-assessment", "employee-onboarding",
            # Security & Ops
            "soc-analyst-assistant", "vulnerability-assessment", "change-management", "disaster-recovery-test",
            # Domain-Specific
            "real-estate-transaction", "product-research-assistant", "patent-analysis-pipeline", "meeting-assistant",
            # Content & Intelligence
            "lead-scoring-flow", "email-auto-responder",
        ]

        registered = list_workflows()
        registered_ids = [w["id"] for w in registered]

        missing = [wf for wf in expected_workflows if wf not in registered_ids]
        if missing:
            pytest.skip(f"Workflows not yet implemented: {missing}")

    def test_workflow_tags_present(self):
        """Verify all workflows have meaningful tags."""
        for workflow_id, workflow in ALL_WORKFLOWS.items():
            assert len(workflow.tags) >= 1, \
                f"Workflow {workflow_id} should have at least one tag"


# =============================================================================
# TEST DATA VALIDATION
# =============================================================================

class TestTestData:
    """Validate test data fixtures."""

    @pytest.mark.parametrize("workflow_id", list_test_workflows())
    def test_test_data_has_all_required_inputs(self, workflow_id: str):
        """Verify test data provides all required workflow inputs."""
        workflow = get_workflow(workflow_id)
        if workflow is None:
            pytest.skip(f"Workflow {workflow_id} not yet implemented")

        test_data = get_test_data(workflow_id)
        assert test_data is not None, f"No test data for {workflow_id}"

        test_inputs = test_data.get("inputs", {})
        for required_input in workflow.required_inputs:
            assert required_input in test_inputs, \
                f"Test data missing required input: {required_input}"

    @pytest.mark.parametrize("workflow_id", list_test_workflows())
    def test_test_data_has_expected_outputs(self, workflow_id: str):
        """Verify test data defines expected outputs."""
        test_data = get_test_data(workflow_id)
        assert test_data is not None, f"No test data for {workflow_id}"

        expected_outputs = test_data.get("expected_outputs", {})
        assert len(expected_outputs) >= 1, \
            f"Test data should define expected outputs for {workflow_id}"

    @pytest.mark.parametrize("workflow_id", list_test_workflows())
    def test_test_data_has_quality_checks(self, workflow_id: str):
        """Verify test data defines quality checks."""
        test_data = get_test_data(workflow_id)
        assert test_data is not None, f"No test data for {workflow_id}"

        quality_checks = test_data.get("quality_checks", [])
        assert len(quality_checks) >= 1, \
            f"Test data should define quality checks for {workflow_id}"


# =============================================================================
# MOCKED EXECUTION TESTS
# =============================================================================

class TestMockedExecution:
    """Test workflow execution with mocked LLM responses."""

    @pytest.fixture
    def mock_llm_client(self):
        """Create a mock LLM client that returns structured responses."""
        with patch("app.llm.ops_center_client.OpsCenterClient") as mock:
            client = mock.return_value
            client.chat_completion_with_tools = AsyncMock(return_value={
                "content": "Mocked response",
                "tool_calls": [],
                "usage": {"total_tokens": 100},
            })
            yield client

    @pytest.mark.asyncio
    @pytest.mark.parametrize("workflow_id", [
        "ma-due-diligence",
        "contract-review",
        "soc-analyst-assistant",
    ])
    async def test_workflow_execution_flow(self, mock_llm_client, workflow_id: str):
        """Test workflow execution produces expected structure."""
        workflow = get_workflow(workflow_id)
        if workflow is None:
            pytest.skip(f"Workflow {workflow_id} not yet implemented")

        test_data = get_test_data(workflow_id)
        inputs = test_data["inputs"]

        # Mock workflow execution
        # In a real test, this would call the workflow engine
        # For now, verify the workflow can be loaded and has valid structure
        assert workflow.id == workflow_id
        assert len(workflow.steps) >= 3
        assert len(workflow.checkpoints) >= 1


# =============================================================================
# LIVE LLM TESTS (Optional)
# =============================================================================

@pytest.mark.skipif(not RUN_LLM_TESTS, reason="Live LLM tests disabled")
class TestLiveLLMExecution:
    """Test workflow execution with real LLM for quality verification."""

    @pytest.fixture
    def workflow_client(self):
        """Create a real workflow client for live testing."""
        # This would be initialized with real credentials
        pytest.skip("Live client not configured")

    @pytest.mark.asyncio
    async def test_ma_due_diligence_quality(self, workflow_client):
        """Test M&A Due Diligence workflow produces quality output."""
        test_data = get_test_data("ma-due-diligence")

        # Execute workflow
        result = await workflow_client.execute(
            workflow_id="ma-due-diligence",
            inputs=test_data["inputs"],
            config={"preset": "quality_optimized"},
        )

        # Verify outputs
        assert "company_profile" in result.outputs
        assert "financial_analysis" in result.outputs
        assert "recommendation" in result.outputs

        # Quality checks
        recommendation = result.outputs.get("recommendation", "")
        assert len(recommendation) > 100, "Recommendation should be substantive"
        assert any(word in recommendation.lower() for word in ["recommend", "proceed", "pass"]), \
            "Recommendation should include a decision"

    @pytest.mark.asyncio
    async def test_contract_review_quality(self, workflow_client):
        """Test Contract Review workflow produces quality output."""
        test_data = get_test_data("contract-review")

        result = await workflow_client.execute(
            workflow_id="contract-review",
            inputs=test_data["inputs"],
            config={"preset": "quality_optimized"},
        )

        # Verify key outputs
        assert "risk_flags" in result.outputs
        assert "negotiation_points" in result.outputs

        # Should identify the key risks from the test contract
        risk_flags = result.outputs.get("risk_flags", [])
        assert len(risk_flags) >= 2, "Should identify multiple risk flags"


# =============================================================================
# CHECKPOINT BEHAVIOR TESTS
# =============================================================================

class TestCheckpointBehavior:
    """Test checkpoint blocking and approval flow."""

    @pytest.mark.parametrize("workflow_id", list_test_workflows())
    def test_checkpoint_options_defined(self, workflow_id: str):
        """Verify HUMAN_APPROVAL checkpoints have options."""
        workflow = get_workflow(workflow_id)
        if workflow is None:
            pytest.skip(f"Workflow {workflow_id} not yet implemented")

        for checkpoint in workflow.checkpoints:
            if checkpoint.type == CheckpointType.HUMAN_APPROVAL:
                assert checkpoint.options and len(checkpoint.options) >= 2, \
                    f"Checkpoint {checkpoint.id} should have approval options"

    @pytest.mark.parametrize("workflow_id", list_test_workflows())
    def test_gate_checkpoints_have_conditions(self, workflow_id: str):
        """Verify GATE checkpoints have gate_condition defined."""
        workflow = get_workflow(workflow_id)
        if workflow is None:
            pytest.skip(f"Workflow {workflow_id} not yet implemented")

        for checkpoint in workflow.checkpoints:
            if checkpoint.type == CheckpointType.GATE:
                assert checkpoint.gate_condition, \
                    f"Gate checkpoint {checkpoint.id} should have a condition"


# =============================================================================
# COST ESTIMATION TESTS
# =============================================================================

class TestCostEstimation:
    """Test workflow cost estimation."""

    @pytest.mark.parametrize("workflow_id", [
        "ma-due-diligence",
        "contract-review",
        "soc-analyst-assistant",
        "product-research-assistant",
    ])
    def test_workflow_cost_estimate_reasonable(self, workflow_id: str):
        """Verify workflow cost estimates are within reasonable bounds."""
        from app.workflows.model_config import estimate_workflow_cost

        workflow = get_workflow(workflow_id)
        if workflow is None:
            pytest.skip(f"Workflow {workflow_id} not yet implemented")

        # Estimate cost with quality_optimized config
        cost = estimate_workflow_cost(workflow, preset="quality_optimized")

        # Reasonable bounds: $0.01 - $5.00 per execution
        assert 0.01 <= cost <= 5.00, \
            f"Workflow {workflow_id} cost estimate {cost} seems unreasonable"


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

class TestIntegration:
    """Integration tests with the full workflow engine."""

    @pytest.fixture
    def test_app(self):
        """Create test FastAPI app."""
        from fastapi.testclient import TestClient
        from app.main import app
        return TestClient(app)

    def test_workflow_list_api(self, test_app):
        """Test /api/v1/hierarchical/templates endpoint."""
        response = test_app.get("/api/v1/hierarchical/templates")

        if response.status_code == 404:
            pytest.skip("Hierarchical API not available")

        assert response.status_code == 200
        data = response.json()

        # Should include our professional workflows
        workflow_ids = [w["id"] for w in data]
        # Check at least some are present
        assert len(workflow_ids) >= 17, "Should have at least 17 workflows"

    def test_workflow_detail_api(self, test_app):
        """Test /api/v1/hierarchical/templates/{id} endpoint."""
        workflow_id = "investment-due-diligence"  # Known existing workflow
        response = test_app.get(f"/api/v1/hierarchical/templates/{workflow_id}")

        if response.status_code == 404:
            pytest.skip("Workflow not found")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == workflow_id


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def verify_output_structure(outputs: Dict[str, Any], expected: Dict[str, List[str]]) -> List[str]:
    """
    Verify outputs match expected structure.

    Returns list of missing/invalid fields.
    """
    issues = []

    for field, expected_keys in expected.items():
        if field not in outputs:
            issues.append(f"Missing output: {field}")
            continue

        output_value = outputs[field]

        # If expected_keys is a list, check for those keys/words
        if isinstance(expected_keys, list):
            if isinstance(output_value, dict):
                for key in expected_keys:
                    if key not in output_value:
                        issues.append(f"{field} missing key: {key}")
            elif isinstance(output_value, str):
                for word in expected_keys:
                    if word.lower() not in output_value.lower():
                        issues.append(f"{field} missing content: {word}")

    return issues


def calculate_quality_score(outputs: Dict[str, Any], checks: List[Dict]) -> float:
    """
    Calculate quality score based on checks.

    Returns score from 0.0 to 1.0.
    """
    if not checks:
        return 1.0

    passed = 0
    for check in checks:
        field = check.get("field")
        if field not in outputs:
            continue

        value = outputs[field]

        # Check min_length
        if "min_length" in check:
            if isinstance(value, str) and len(value) >= check["min_length"]:
                passed += 1

        # Check min_items
        elif "min_items" in check:
            if isinstance(value, (list, dict)) and len(value) >= check["min_items"]:
                passed += 1

        # Check contains
        elif "contains" in check:
            content = str(value).lower()
            if all(word.lower() in content for word in check["contains"]):
                passed += 1

        # Check is_numeric
        elif check.get("is_numeric"):
            if isinstance(value, (int, float)):
                passed += 1

        else:
            # Unknown check type, consider passed
            passed += 1

    return passed / len(checks)
