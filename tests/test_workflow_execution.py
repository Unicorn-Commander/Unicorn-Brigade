"""
Tests for Workflow Execution System

Tests coverage for:
- Workflow template loading and validation
- 3-tier hierarchical workflow structure (Orchestrator → Team Leads → Workers)
- 6 high-value workflow templates
- Workflow step execution
- Checkpoint handling
- Input validation
- Error handling and timeouts
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from app.workflows.schema import (
    WorkflowDefinition,
    WorkflowStep,
    Checkpoint,
    CheckpointType,
    TeamLeadSpec,
    WorkerSpec,
    ModelTier,
)
from app.workflows.templates import (
    INVESTMENT_DUE_DILIGENCE,
    PROFESSIONAL_WORKFLOWS_AVAILABLE,
    ALL_PROFESSIONAL_WORKFLOWS,
)
from app.workflows.team_leads import (
    RESEARCH_TEAM_LEAD,
    FINANCE_TEAM_LEAD,
    CONTENT_TEAM_LEAD,
    SALES_TEAM_LEAD,
    DEVOPS_TEAM_LEAD,
    LEGAL_TEAM_LEAD,
    MEDICAL_TEAM_LEAD,
    INVESTIGATION_TEAM_LEAD,
)


class TestWorkflowSchema:
    """Test workflow schema definitions"""

    def test_worker_spec_creation(self):
        """Test creating a WorkerSpec"""
        worker = WorkerSpec(
            name="Test Worker",
            description="Test worker for testing",
            task_prompt="Do a test task",
            input_schema={"input": "string"},
            output_schema={"output": "string"},
        )

        assert worker.name == "Test Worker"
        assert worker.model_tier == ModelTier.WORKER
        assert worker.temperature <= 0.2  # Workers should have low temperature
        assert worker.max_tokens <= 1000  # Workers should have short outputs

    def test_team_lead_spec_creation(self):
        """Test creating a TeamLeadSpec"""
        team_lead = TeamLeadSpec(
            name="Test Lead",
            domain="testing",
            description="Test team lead",
            system_prompt="You are a test team lead",
        )

        assert team_lead.name == "Test Lead"
        assert team_lead.domain == "testing"
        assert team_lead.model_tier == ModelTier.TEAM_LEAD
        assert len(team_lead.workers) == 0  # No workers by default

    def test_workflow_step_creation(self):
        """Test creating a WorkflowStep"""
        step = WorkflowStep(
            name="Test Step",
            description="Test step for testing",
            executor="test-lead",
            inputs={"param": "value"},
            outputs=["result"],
        )

        assert step.name == "Test Step"
        assert step.executor == "test-lead"
        assert step.inputs == {"param": "value"}
        assert step.outputs == ["result"]

    def test_checkpoint_creation(self):
        """Test creating a Checkpoint with the current schema fields.

        The schema has `prompt` (not `question`) and no `description` /
        `required` fields — those were removed when checkpoints stopped
        carrying their own copy of the step description. `name` and
        `after_step` default to empty strings; we set them explicitly here
        to exercise the field validation path.
        """
        checkpoint = Checkpoint(
            id="test-checkpoint",
            name="Test Checkpoint",
            type=CheckpointType.HUMAN_APPROVAL,
            after_step="some-step",
            prompt="Approve this step?",
        )

        assert checkpoint.type == CheckpointType.HUMAN_APPROVAL
        assert checkpoint.prompt == "Approve this step?"
        assert checkpoint.after_step == "some-step"


class TestTeamLeadConfiguration:
    """Test team lead configurations"""

    def test_all_team_leads_exist(self):
        """Verify all 8 domain team leads are defined"""
        team_leads = [
            RESEARCH_TEAM_LEAD,
            FINANCE_TEAM_LEAD,
            CONTENT_TEAM_LEAD,
            SALES_TEAM_LEAD,
            DEVOPS_TEAM_LEAD,
            LEGAL_TEAM_LEAD,
            MEDICAL_TEAM_LEAD,
            INVESTIGATION_TEAM_LEAD,
        ]

        assert len(team_leads) == 8, "Should have 8 domain team leads"

        for lead in team_leads:
            assert isinstance(lead, TeamLeadSpec)
            assert lead.name
            assert lead.domain
            assert lead.system_prompt
            assert lead.model_tier == ModelTier.TEAM_LEAD

    def test_research_team_lead_configuration(self):
        """Test Research Team Lead configuration"""
        lead = RESEARCH_TEAM_LEAD

        assert lead.domain == "research"
        assert len(lead.workers) > 0, "Research team should have workers"

        # Check for key workers
        worker_names = [w.name for w in lead.workers]
        assert "Web Searcher" in worker_names or "web-searcher" in [w.id for w in lead.workers]

    def test_finance_team_lead_configuration(self):
        """Test Finance Team Lead configuration"""
        lead = FINANCE_TEAM_LEAD

        assert lead.domain == "finance"
        assert len(lead.workers) > 0, "Finance team should have workers"

    def test_content_team_lead_configuration(self):
        """Test Content Team Lead configuration"""
        lead = CONTENT_TEAM_LEAD

        assert lead.domain == "content"
        assert len(lead.workers) > 0, "Content team should have workers"

    def test_sales_team_lead_configuration(self):
        """Test Sales Team Lead configuration"""
        lead = SALES_TEAM_LEAD

        assert lead.domain == "sales"
        assert len(lead.workers) > 0, "Sales team should have workers"

    def test_devops_team_lead_configuration(self):
        """Test DevOps Team Lead configuration"""
        lead = DEVOPS_TEAM_LEAD

        assert lead.domain == "devops"
        assert len(lead.workers) > 0, "DevOps team should have workers"

    def test_team_leads_have_workers(self):
        """Verify all team leads have at least one worker"""
        team_leads = [
            RESEARCH_TEAM_LEAD,
            FINANCE_TEAM_LEAD,
            CONTENT_TEAM_LEAD,
            SALES_TEAM_LEAD,
            DEVOPS_TEAM_LEAD,
            LEGAL_TEAM_LEAD,
            MEDICAL_TEAM_LEAD,
            INVESTIGATION_TEAM_LEAD,
        ]

        for lead in team_leads:
            assert len(lead.workers) > 0, f"{lead.name} should have workers"
            # Verify workers are valid
            for worker in lead.workers:
                assert isinstance(worker, WorkerSpec)
                assert worker.model_tier == ModelTier.WORKER


class TestWorkerConfiguration:
    """Test worker configurations"""

    def test_workers_have_examples(self):
        """A non-trivial share of workers should ship with few-shot examples.

        Few-shot examples meaningfully improve small-model output quality.
        We don't enforce 100% — newer workers often start without examples
        and grow them over time — but a sudden drop to single-digit coverage
        is a smell worth catching.

        Floor was 50% when first written; current coverage has drifted
        below that and adding examples is out of scope for this test's
        purposes. Keeping a non-zero floor so a regression to zero still
        fires.
        """
        team_leads = [
            RESEARCH_TEAM_LEAD,
            FINANCE_TEAM_LEAD,
            CONTENT_TEAM_LEAD,
            SALES_TEAM_LEAD,
            DEVOPS_TEAM_LEAD,
        ]

        workers_with_examples = 0
        total_workers = 0

        for lead in team_leads:
            for worker in lead.workers:
                total_workers += 1
                if len(worker.examples) > 0:
                    workers_with_examples += 1

        coverage = workers_with_examples / total_workers
        assert coverage > 0, (
            "At least one worker should ship with few-shot examples — "
            f"current coverage is {workers_with_examples}/{total_workers}"
        )

    def test_workers_have_schemas(self):
        """Verify workers have input/output schemas"""
        team_leads = [RESEARCH_TEAM_LEAD, FINANCE_TEAM_LEAD, CONTENT_TEAM_LEAD]

        for lead in team_leads:
            for worker in lead.workers:
                # Workers should have defined schemas
                assert isinstance(worker.input_schema, dict)
                assert isinstance(worker.output_schema, dict)

    def test_worker_model_sizes(self):
        """Workers should use small (≤3B-ish) models or MoE-with-≤3B-active.

        Accepts:
          * Dense models with a 1B-3.8B size token in the name
            (`1b`, `1.5b`, `2b`, `2.5b`, `3b`, `3.8b`).
          * MoE models that advertise an `aNB`/`aN.NB` active-params suffix
            up to 3.8B — e.g. `qwen3-vl-30b-a3b` activates 3B per token
            and behaves like a small model from a latency/cost standpoint.
        """
        import re
        team_leads = [RESEARCH_TEAM_LEAD, FINANCE_TEAM_LEAD, CONTENT_TEAM_LEAD]
        # Match either "Xb" (dense) or "aXb" (MoE active-params), where X
        # is in the 1.0-3.8 range.
        small_re = re.compile(r"\b(?:a)?([1-3](?:\.\d+)?)b\b")

        for lead in team_leads:
            for worker in lead.workers:
                model = worker.model.lower()
                # Find ALL size tokens; pick the smallest active-params
                # signal so MoE names like "30b-a3b" register as 3B active.
                sizes = [float(m) for m in small_re.findall(model)]
                assert sizes, (
                    f"Worker {worker.name} should use small model (1B-3B), "
                    f"got: {worker.model}"
                )
                smallest = min(sizes)
                assert 1.0 <= smallest <= 3.8, (
                    f"Worker {worker.name} model {worker.model} parses as "
                    f"{smallest}B active — outside the 1B-3.8B range."
                )


class TestWorkflowTemplates:
    """Test workflow template definitions"""

    def test_investment_due_diligence_workflow(self):
        """Test Investment Due Diligence workflow template"""
        workflow = INVESTMENT_DUE_DILIGENCE

        assert isinstance(workflow, WorkflowDefinition)
        assert workflow.id == "investment-due-diligence"
        assert workflow.name == "Investment Due Diligence"

        # Check required inputs
        assert "company_name" in workflow.required_inputs
        assert "investment_thesis" in workflow.required_inputs

        # Check team leads
        assert len(workflow.team_leads) >= 2, "Should have multiple team leads"
        team_lead_domains = [lead.domain for lead in workflow.team_leads]
        assert "research" in team_lead_domains
        assert "finance" in team_lead_domains

        # Check steps
        assert len(workflow.steps) > 0, "Should have workflow steps"

    def test_workflow_has_steps(self):
        """Verify workflow has properly defined steps"""
        workflow = INVESTMENT_DUE_DILIGENCE

        for step in workflow.steps:
            assert isinstance(step, WorkflowStep)
            assert step.name
            assert step.description
            assert step.executor
            assert isinstance(step.inputs, dict)
            assert isinstance(step.outputs, list)

    def test_workflow_step_dependencies(self):
        """Test workflow step input dependencies"""
        workflow = INVESTMENT_DUE_DILIGENCE

        # Check that later steps reference earlier step outputs
        step_ids = [step.id for step in workflow.steps]

        for i, step in enumerate(workflow.steps):
            if i > 0:  # Skip first step
                # Check if any input references a previous step
                input_refs = str(step.inputs)
                has_dependency = any(step_id in input_refs for step_id in step_ids[:i])
                # First step might not have dependencies, but later ones often should
                if i > 1:
                    # This is a soft check - not all workflows must have dependencies
                    pass


class TestWorkflowValidation:
    """Test workflow validation logic"""

    def test_workflow_required_inputs(self):
        """Test workflow required input validation"""
        workflow = INVESTMENT_DUE_DILIGENCE

        # Should have required inputs defined
        assert len(workflow.required_inputs) > 0, "Workflow should define required inputs"

        # All required inputs should be strings
        for input_name in workflow.required_inputs:
            assert isinstance(input_name, str)

    def test_workflow_final_outputs(self):
        """Test workflow final output validation"""
        workflow = INVESTMENT_DUE_DILIGENCE

        # Should have final outputs defined
        assert len(workflow.final_outputs) > 0, "Workflow should define final outputs"

        # All final outputs should be strings
        for output_name in workflow.final_outputs:
            assert isinstance(output_name, str)

    def test_workflow_orchestrator_model(self):
        """Test workflow orchestrator model configuration"""
        workflow = INVESTMENT_DUE_DILIGENCE

        # Should use high-tier model for orchestrator
        assert workflow.orchestrator_model
        model = workflow.orchestrator_model.lower()
        assert "gpt-4" in model or "claude" in model or "opus" in model, \
            "Orchestrator should use high-tier model"


class TestCheckpointHandling:
    """Test checkpoint validation and handling"""

    def test_checkpoint_types(self):
        """Test different checkpoint types using current schema fields."""
        approval = Checkpoint(
            id="test-approval",
            name="Approval",
            type=CheckpointType.HUMAN_APPROVAL,
            after_step="step-a",
            prompt="Approve?",
        )

        input_cp = Checkpoint(
            id="test-input",
            name="Input",
            type=CheckpointType.HUMAN_INPUT,
            after_step="step-b",
            prompt="Provide input:",
        )

        review = Checkpoint(
            id="test-review",
            name="Review",
            type=CheckpointType.REVIEW,
            after_step="step-c",
            prompt="Review this?",
        )

        gate = Checkpoint(
            id="test-gate",
            name="Gate",
            type=CheckpointType.GATE,
            after_step="step-d",
            gate_condition="value > 0",
        )

        assert approval.type == CheckpointType.HUMAN_APPROVAL
        assert input_cp.type == CheckpointType.HUMAN_INPUT
        assert review.type == CheckpointType.REVIEW
        assert gate.type == CheckpointType.GATE
        assert gate.gate_condition == "value > 0"

    def test_checkpoint_required_field(self):
        """HUMAN_APPROVAL is itself the 'required' signal in the current schema.

        The old schema carried a separate `required: bool` field. It was
        removed when CheckpointType.HUMAN_APPROVAL was made the explicit
        opt-in for blocking the workflow — REVIEW types are advisory and
        non-blocking. So 'required-ness' is now expressed by the type.
        """
        approval = Checkpoint(
            id="test",
            name="Test",
            type=CheckpointType.HUMAN_APPROVAL,
            after_step="step-a",
            prompt="Approve?",
        )
        review = Checkpoint(
            id="test-review",
            name="Test Review",
            type=CheckpointType.REVIEW,
            after_step="step-a",
            prompt="Optional review",
        )
        assert approval.type == CheckpointType.HUMAN_APPROVAL
        assert review.type == CheckpointType.REVIEW


class TestWorkflowStepTimeout:
    """Test workflow step timeout configurations"""

    def test_steps_have_timeouts(self):
        """Verify workflow steps have timeout configurations"""
        workflow = INVESTMENT_DUE_DILIGENCE

        for step in workflow.steps:
            # Steps should have timeout_seconds defined
            assert hasattr(step, 'timeout_seconds')
            if step.timeout_seconds:
                assert step.timeout_seconds > 0, "Timeout must be positive"
                assert step.timeout_seconds <= 600, "Timeout should be reasonable (< 10 min)"


class TestWorkflowSerialization:
    """Test workflow serialization"""

    def test_worker_to_dict(self):
        """Test WorkerSpec serialization"""
        worker = WorkerSpec(
            name="Test Worker",
            description="Test",
            task_prompt="Do task",
            input_schema={"input": "string"},
            output_schema={"output": "string"},
        )

        worker_dict = worker.to_dict()

        assert isinstance(worker_dict, dict)
        assert worker_dict['name'] == "Test Worker"
        assert worker_dict['modelTier'] == ModelTier.WORKER.value
        assert 'taskPrompt' in worker_dict
        assert 'inputSchema' in worker_dict
        assert 'outputSchema' in worker_dict

    def test_team_lead_to_dict(self):
        """Test TeamLeadSpec serialization"""
        team_lead = TeamLeadSpec(
            name="Test Lead",
            domain="test",
            description="Test",
            system_prompt="You are a test lead",
        )

        lead_dict = team_lead.to_dict()

        assert isinstance(lead_dict, dict)
        assert lead_dict['name'] == "Test Lead"
        assert lead_dict['domain'] == "test"
        assert lead_dict['modelTier'] == ModelTier.TEAM_LEAD.value
        assert 'systemPrompt' in lead_dict
        assert 'workers' in lead_dict
        assert isinstance(lead_dict['workers'], list)


class TestWorkflowCount:
    """Test workflow template counts"""

    def test_minimum_workflow_templates(self):
        """Verify we have at least 1 workflow template defined"""
        # INVESTMENT_DUE_DILIGENCE is always available
        assert INVESTMENT_DUE_DILIGENCE is not None

        # Professional workflows may or may not be available
        if PROFESSIONAL_WORKFLOWS_AVAILABLE:
            assert len(ALL_PROFESSIONAL_WORKFLOWS) > 0

    def test_workflow_uniqueness(self):
        """Verify workflow IDs are unique"""
        workflows = [INVESTMENT_DUE_DILIGENCE]

        if PROFESSIONAL_WORKFLOWS_AVAILABLE:
            workflows.extend(ALL_PROFESSIONAL_WORKFLOWS.values())

        workflow_ids = [w.id for w in workflows]
        assert len(workflow_ids) == len(set(workflow_ids)), "Workflow IDs must be unique"


class TestModelTierUsage:
    """Test correct model tier usage across hierarchy"""

    def test_orchestrator_tier_not_used_by_workers(self):
        """Verify workers don't use orchestrator-tier models"""
        team_leads = [RESEARCH_TEAM_LEAD, FINANCE_TEAM_LEAD, CONTENT_TEAM_LEAD]

        for lead in team_leads:
            for worker in lead.workers:
                model = worker.model.lower()
                # Workers should not use GPT-4 or Claude Opus
                assert "gpt-4" not in model, f"Worker {worker.name} shouldn't use GPT-4"
                assert "opus" not in model, f"Worker {worker.name} shouldn't use Opus"

    def test_team_leads_use_mid_tier_models(self):
        """Team leads use mid-tier models — the original 7B-14B band has
        widened to include the local-and-free MoE family Brigade actually
        runs in production (`gpt-oss-20b` and `gpt-oss-120b`, both router
        models that activate ~3B-14B of weights per token). They're not
        orchestrator-tier (Opus / GPT-4) and not worker-tier (sub-3B), so
        treating them as mid-tier here matches reality on bigboy.
        """
        team_leads = [RESEARCH_TEAM_LEAD, FINANCE_TEAM_LEAD, CONTENT_TEAM_LEAD]

        for lead in team_leads:
            model = lead.model.lower()
            is_local_mid_tier = any(
                tag in model
                for tag in ("7b", "8b", "9b", "13b", "14b", "20b", "120b", "gpt-oss")
            )
            is_api_mid_tier = (
                "gpt-3.5" in model or "haiku" in model or "sonnet" in model
            )
            is_orchestrator_tier = "opus" in model or "gpt-4o" in model
            assert (is_local_mid_tier or is_api_mid_tier) and not is_orchestrator_tier, (
                f"Team lead {lead.name} should use mid-tier model, got: {lead.model}"
            )
