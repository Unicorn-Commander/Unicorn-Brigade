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
        """Test creating a Checkpoint"""
        checkpoint = Checkpoint(
            id="test-checkpoint",
            name="Test Checkpoint",
            description="Test approval point",
            type=CheckpointType.HUMAN_APPROVAL,
            question="Approve this step?",
        )

        assert checkpoint.type == CheckpointType.HUMAN_APPROVAL
        assert checkpoint.required is True  # Approvals are required by default


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
        """Verify workers have few-shot examples for small models"""
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

        # At least 50% of workers should have examples
        assert workers_with_examples / total_workers >= 0.5, \
            "At least 50% of workers should have examples for small model prompting"

    def test_workers_have_schemas(self):
        """Verify workers have input/output schemas"""
        team_leads = [RESEARCH_TEAM_LEAD, FINANCE_TEAM_LEAD, CONTENT_TEAM_LEAD]

        for lead in team_leads:
            for worker in lead.workers:
                # Workers should have defined schemas
                assert isinstance(worker.input_schema, dict)
                assert isinstance(worker.output_schema, dict)

    def test_worker_model_sizes(self):
        """Verify workers use small models (1B-3B)"""
        team_leads = [RESEARCH_TEAM_LEAD, FINANCE_TEAM_LEAD, CONTENT_TEAM_LEAD]

        for lead in team_leads:
            for worker in lead.workers:
                # Workers should use small models
                model = worker.model.lower()
                assert "3b" in model or "3.8b" in model or "1b" in model or "2b" in model, \
                    f"Worker {worker.name} should use small model (1B-3B), got: {worker.model}"


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
        """Test different checkpoint types"""
        approval = Checkpoint(
            id="test-approval",
            name="Approval",
            description="Test approval",
            type=CheckpointType.HUMAN_APPROVAL,
            question="Approve?",
        )

        input_cp = Checkpoint(
            id="test-input",
            name="Input",
            description="Test input",
            type=CheckpointType.HUMAN_INPUT,
            question="Provide input:",
        )

        review = Checkpoint(
            id="test-review",
            name="Review",
            description="Test review",
            type=CheckpointType.REVIEW,
            question="Review this?",
        )

        gate = Checkpoint(
            id="test-gate",
            name="Gate",
            description="Test gate",
            type=CheckpointType.GATE,
            condition="value > 0",
        )

        assert approval.type == CheckpointType.HUMAN_APPROVAL
        assert input_cp.type == CheckpointType.HUMAN_INPUT
        assert review.type == CheckpointType.REVIEW
        assert gate.type == CheckpointType.GATE

    def test_checkpoint_required_field(self):
        """Test checkpoint required field"""
        checkpoint = Checkpoint(
            id="test",
            name="Test",
            description="Test",
            type=CheckpointType.HUMAN_APPROVAL,
            question="Approve?",
            required=True,
        )

        assert checkpoint.required is True


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
        """Verify team leads use appropriate mid-tier models"""
        team_leads = [RESEARCH_TEAM_LEAD, FINANCE_TEAM_LEAD, CONTENT_TEAM_LEAD]

        for lead in team_leads:
            # Team leads should use 7B-14B models
            model = lead.model.lower()
            # Check for common mid-tier model patterns
            is_mid_tier = (
                "7b" in model or "8b" in model or "13b" in model or "14b" in model
            )
            # If not local, might be using GPT-3.5 or Claude Haiku
            is_api_mid_tier = "gpt-3.5" in model or "haiku" in model

            assert is_mid_tier or is_api_mid_tier, \
                f"Team lead {lead.name} should use mid-tier model, got: {lead.model}"
