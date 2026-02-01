"""
Integration tests for the Hierarchical Workflow System.

Tests the 3-tier agent hierarchy:
- Orchestrator (The General)
- Team Leads (7B-14B local models)
- Workers (1B-3B local models)

Run with: pytest tests/test_hierarchical_workflows.py -v
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
import json

from fastapi.testclient import TestClient


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def mock_llm_client():
    """Create mock LLM client for testing"""
    client = MagicMock()
    client.chat_completion = AsyncMock(return_value={
        "choices": [{
            "message": {
                "content": json.dumps({
                    "delegations": [
                        {"worker_id": "web-searcher", "task": "Search for company info", "priority": 1}
                    ],
                    "aggregation_strategy": "sequential"
                })
            }
        }],
        "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
        "model": "test-model",
    })
    client.execute_tool_loop = AsyncMock(return_value={
        "content": json.dumps({"result": "test output"}),
        "usage": {"prompt_tokens": 50, "completion_tokens": 25, "total_tokens": 75},
    })
    return client


@pytest.fixture
def mock_llm_response():
    """Factory for creating mock LLM responses"""
    def _create(content, tokens=None):
        return {
            "choices": [{
                "message": {
                    "content": content if isinstance(content, str) else json.dumps(content)
                }
            }],
            "usage": tokens or {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
            "model": "test-model",
        }
    return _create


# =============================================================================
# MODEL CONFIGURATION TESTS
# =============================================================================

class TestModelConfig:
    """Tests for ModelConfig creation and configuration"""

    def test_model_config_creation_with_defaults(self):
        """Test ModelConfig creation with default values"""
        from app.workflows import ModelConfig

        config = ModelConfig()

        assert config.orchestrator_model == "openai/gpt-4o-mini"
        assert config.default_team_lead_model == "ollama/llama3.1:8b"
        assert config.default_worker_model == "ollama/llama3.2:3b"
        assert config.enable_local_models is True
        assert "research" in config.team_lead_models
        assert "finance" in config.team_lead_models

    def test_model_config_with_custom_values(self):
        """Test ModelConfig with custom model assignments"""
        from app.workflows import ModelConfig

        config = ModelConfig(
            orchestrator_model="openai/gpt-4o",
            team_lead_models={
                "research": "anthropic/claude-3.5-sonnet",
                "finance": "openai/gpt-4o-mini",
            },
            worker_models={
                "web-searcher": "ollama/phi3:3.8b",
            },
            enable_local_models=False,
        )

        assert config.orchestrator_model == "openai/gpt-4o"
        assert config.team_lead_models["research"] == "anthropic/claude-3.5-sonnet"
        assert config.worker_models["web-searcher"] == "ollama/phi3:3.8b"
        assert config.enable_local_models is False

    def test_preset_configurations_load_correctly(self):
        """Test that preset configurations are properly defined"""
        from app.workflows import (
            COST_OPTIMIZED_CONFIG,
            QUALITY_OPTIMIZED_CONFIG,
            FULL_API_CONFIG,
            FULL_LOCAL_CONFIG,
            FINANCE_SPECIALIZED_CONFIG,
            LEGAL_SPECIALIZED_CONFIG,
            CONFIG_PRESETS,
        )

        # Check all presets exist
        assert "cost_optimized" in CONFIG_PRESETS
        assert "quality_optimized" in CONFIG_PRESETS
        assert "full_api" in CONFIG_PRESETS
        assert "full_local" in CONFIG_PRESETS
        assert "finance_specialized" in CONFIG_PRESETS
        assert "legal_specialized" in CONFIG_PRESETS

        # Cost optimized uses local models
        assert COST_OPTIMIZED_CONFIG.enable_local_models is True
        assert "ollama/" in COST_OPTIMIZED_CONFIG.default_team_lead_model

        # Full API disables local models
        assert FULL_API_CONFIG.enable_local_models is False

        # Quality optimized uses API for orchestrator
        assert "openai/" in QUALITY_OPTIMIZED_CONFIG.orchestrator_model or \
               "anthropic/" in QUALITY_OPTIMIZED_CONFIG.orchestrator_model

    def test_model_resolution_for_orchestrator(self):
        """Test model resolution for orchestrator role"""
        from app.workflows import ModelConfig, ModelRegistry

        config = ModelConfig(orchestrator_model="openai/gpt-4o")
        model = ModelRegistry.get_model_for_orchestrator(config)

        assert model == "openai/gpt-4o"

    def test_model_resolution_for_team_leads(self):
        """Test model resolution for team lead by domain"""
        from app.workflows import ModelConfig, ModelRegistry

        config = ModelConfig(
            team_lead_models={
                "research": "ollama/llama3.1:8b",
                "finance": "openai/gpt-4o-mini",
            }
        )

        research_model = ModelRegistry.get_model_for_team_lead("research", config)
        finance_model = ModelRegistry.get_model_for_team_lead("finance", config)
        devops_model = ModelRegistry.get_model_for_team_lead("devops", config)

        assert research_model == "ollama/llama3.1:8b"
        assert finance_model == "openai/gpt-4o-mini"
        assert devops_model == config.default_team_lead_model  # Falls back to default

    def test_model_resolution_for_workers(self):
        """Test model resolution for workers with fallbacks"""
        from app.workflows import ModelConfig, ModelRegistry

        config = ModelConfig(
            worker_models={
                "web-searcher": "ollama/phi3:3.8b",
            },
            default_worker_model="ollama/llama3.2:3b",
        )

        # Worker with explicit override
        web_searcher_model = ModelRegistry.get_model_for_worker("web-searcher", config)
        assert web_searcher_model == "ollama/phi3:3.8b"

        # Worker without override, with default from spec
        doc_parser_model = ModelRegistry.get_model_for_worker(
            "doc-parser", config, default_model="ollama/phi3:3.8b"
        )
        assert doc_parser_model == "ollama/phi3:3.8b"

        # Worker without override, no spec default
        other_model = ModelRegistry.get_model_for_worker("unknown-worker", config)
        assert other_model == "ollama/llama3.2:3b"

    def test_model_resolution_with_local_models_disabled(self):
        """Test fallback to API models when local models are disabled"""
        from app.workflows import ModelConfig, ModelRegistry

        config = ModelConfig(
            team_lead_models={"research": "ollama/llama3.1:8b"},
            enable_local_models=False,
            api_fallback_team_lead="openai/gpt-4o-mini",
            api_fallback_worker="openai/gpt-4o-mini",
        )

        # Should fall back to API model
        model = ModelRegistry.get_model_for_team_lead("research", config)
        assert model == "openai/gpt-4o-mini"

        worker_model = ModelRegistry.get_model_for_worker("web-searcher", config, "ollama/llama3.2:3b")
        assert worker_model == "openai/gpt-4o-mini"

    def test_cost_estimation_function(self):
        """Test workflow cost estimation"""
        from app.workflows import (
            ModelConfig,
            estimate_workflow_cost,
        )
        from app.workflows.templates import get_workflow

        workflow = get_workflow("investment-due-diligence")
        if workflow is None:
            pytest.skip("investment-due-diligence workflow not available")

        config = ModelConfig()
        estimate = estimate_workflow_cost(
            workflow=workflow,
            config=config,
            avg_tokens_per_step=2000,
            avg_worker_tokens=500,
        )

        assert "orchestrator_cost" in estimate
        assert "team_lead_cost" in estimate
        assert "worker_cost" in estimate
        assert "total_cost" in estimate
        assert "model_usage" in estimate
        assert estimate["total_cost"] >= 0
        assert isinstance(estimate["model_usage"], dict)

    def test_cost_estimation_with_full_api_config(self):
        """Test that full API config has higher costs than local"""
        from app.workflows import (
            COST_OPTIMIZED_CONFIG,
            FULL_API_CONFIG,
            estimate_workflow_cost,
        )
        from app.workflows.templates import get_workflow

        workflow = get_workflow("investment-due-diligence")
        if workflow is None:
            pytest.skip("investment-due-diligence workflow not available")

        local_estimate = estimate_workflow_cost(workflow, COST_OPTIMIZED_CONFIG)
        api_estimate = estimate_workflow_cost(workflow, FULL_API_CONFIG)

        # API config should cost more (or equal if both have $0 local models)
        assert api_estimate["total_cost"] >= local_estimate["total_cost"]

    def test_config_merging_with_overrides(self):
        """Test merging configurations with overrides"""
        from app.workflows import ModelConfig, merge_configs

        base_config = ModelConfig(
            orchestrator_model="openai/gpt-4o-mini",
            team_lead_models={"research": "ollama/llama3.1:8b"},
        )

        overrides = {
            "orchestrator_model": "openai/gpt-4o",
            "team_lead_models": {"finance": "anthropic/claude-3.5-sonnet"},
        }

        merged = merge_configs(base_config, overrides)

        assert merged.orchestrator_model == "openai/gpt-4o"
        assert merged.team_lead_models["research"] == "ollama/llama3.1:8b"  # Preserved
        assert merged.team_lead_models["finance"] == "anthropic/claude-3.5-sonnet"  # Added

    def test_get_config_from_preset(self):
        """Test getting preset configuration by name"""
        from app.workflows import get_config_from_preset

        config = get_config_from_preset("cost_optimized")
        assert config.enable_local_models is True

        config = get_config_from_preset("full_api")
        assert config.enable_local_models is False

        with pytest.raises(ValueError) as exc_info:
            get_config_from_preset("nonexistent_preset")
        assert "Unknown preset" in str(exc_info.value)

    def test_create_config_from_request(self):
        """Test creating config from API request parameters"""
        from app.workflows import create_config_from_request

        # From preset
        config = create_config_from_request(preset="quality_optimized")
        assert "gpt-4o" in config.orchestrator_model

        # With overrides
        config = create_config_from_request(
            preset="cost_optimized",
            overrides={"orchestrator_model": "anthropic/claude-3.5-sonnet"}
        )
        assert config.orchestrator_model == "anthropic/claude-3.5-sonnet"

        # Default config
        config = create_config_from_request()
        assert config.orchestrator_model == "openai/gpt-4o-mini"

    def test_list_available_presets(self):
        """Test listing all available presets"""
        from app.workflows import list_available_presets

        presets = list_available_presets()

        assert isinstance(presets, dict)
        assert len(presets) >= 4  # At least cost, quality, full_api, full_local

        for name, info in presets.items():
            assert "orchestrator_model" in info
            assert "enable_local_models" in info
            assert "description" in info

    def test_model_alias_resolution(self):
        """Test that model aliases are resolved correctly"""
        from app.workflows import ModelConfig, MODEL_ALIASES

        # Use alias in config
        config = ModelConfig(orchestrator_model="gpt-4o")

        # Should be resolved to full name
        assert config.orchestrator_model == MODEL_ALIASES.get("gpt-4o", "gpt-4o")

    def test_model_tier_detection(self):
        """Test detection of model tier (api vs local)"""
        from app.workflows import ModelRegistry

        assert ModelRegistry.get_model_tier("openai/gpt-4o") == "api"
        assert ModelRegistry.get_model_tier("anthropic/claude-3.5-sonnet") == "api"
        assert ModelRegistry.get_model_tier("ollama/llama3.1:8b") == "local"
        assert ModelRegistry.get_model_tier("ollama/phi3:3.8b") == "local"

    def test_model_cost_calculation(self):
        """Test model cost calculation"""
        from app.workflows import ModelRegistry

        # API model should have cost
        cost = ModelRegistry.get_model_cost("openai/gpt-4o-mini", 1000, 500)
        assert cost > 0

        # Local model should be free
        cost = ModelRegistry.get_model_cost("ollama/llama3.1:8b", 1000, 500)
        assert cost == 0


# =============================================================================
# WORKFLOW ENGINE TESTS
# =============================================================================

class TestWorkflowEngine:
    """Tests for WorkflowEngine initialization and configuration"""

    @pytest.fixture
    def mock_event_bus(self):
        """Mock the orchestration event bus"""
        with patch("app.workflows.engine.event_bus") as mock_bus:
            mock_mission = MagicMock()
            mock_mission.id = "test-mission-123"
            mock_bus.create_mission.return_value = mock_mission
            yield mock_bus

    @pytest.fixture
    def mock_emitters(self):
        """Mock all event emitter functions"""
        with patch("app.workflows.engine.emit_agent_started", new_callable=AsyncMock) as mock_started, \
             patch("app.workflows.engine.emit_agent_completed", new_callable=AsyncMock) as mock_completed, \
             patch("app.workflows.engine.emit_agent_thinking", new_callable=AsyncMock) as mock_thinking, \
             patch("app.workflows.engine.emit_tool_call", new_callable=AsyncMock) as mock_tool_call, \
             patch("app.workflows.engine.emit_tool_result", new_callable=AsyncMock) as mock_tool_result, \
             patch("app.workflows.engine.emit_agent_message", new_callable=AsyncMock) as mock_message:
            yield {
                "started": mock_started,
                "completed": mock_completed,
                "thinking": mock_thinking,
                "tool_call": mock_tool_call,
                "tool_result": mock_tool_result,
                "message": mock_message,
            }

    def test_workflow_engine_initialization_default(self, mock_llm_client, mock_event_bus):
        """Test WorkflowEngine initialization with defaults"""
        from app.workflows import WorkflowEngine

        engine = WorkflowEngine(llm_client=mock_llm_client)

        assert engine.orchestrator_model == "openai/gpt-4o-mini"
        assert engine.enable_local_models is True
        assert engine.llm_client is mock_llm_client

    def test_workflow_engine_initialization_with_model_config(self, mock_llm_client, mock_event_bus):
        """Test WorkflowEngine initialization with ModelConfig"""
        from app.workflows import WorkflowEngine, ModelConfig

        config = ModelConfig(
            orchestrator_model="openai/gpt-4o",
            enable_local_models=False,
        )

        engine = WorkflowEngine(llm_client=mock_llm_client, model_config=config)

        assert engine.orchestrator_model == "openai/gpt-4o"
        assert engine.enable_local_models is False

    def test_get_model_config_returns_correct_config(self, mock_llm_client, mock_event_bus):
        """Test get_model_config() returns the current configuration"""
        from app.workflows import WorkflowEngine, ModelConfig

        config = ModelConfig(orchestrator_model="anthropic/claude-3.5-sonnet")
        engine = WorkflowEngine(llm_client=mock_llm_client, model_config=config)

        retrieved_config = engine.get_model_config()

        assert retrieved_config.orchestrator_model == "anthropic/claude-3.5-sonnet"

    def test_update_model_config(self, mock_llm_client, mock_event_bus):
        """Test update_model_config() updates the configuration"""
        from app.workflows import WorkflowEngine, ModelConfig

        engine = WorkflowEngine(llm_client=mock_llm_client)
        assert engine.orchestrator_model == "openai/gpt-4o-mini"

        new_config = ModelConfig(
            orchestrator_model="openai/gpt-4o",
            enable_local_models=False,
        )
        engine.update_model_config(new_config)

        assert engine.orchestrator_model == "openai/gpt-4o"
        assert engine.enable_local_models is False
        assert engine.get_model_config().orchestrator_model == "openai/gpt-4o"

    def test_get_execution_returns_none_for_unknown(self, mock_llm_client, mock_event_bus):
        """Test get_execution returns None for unknown execution ID"""
        from app.workflows import WorkflowEngine

        engine = WorkflowEngine(llm_client=mock_llm_client)

        result = engine.get_execution("nonexistent-id")
        assert result is None

    def test_list_executions_empty_initially(self, mock_llm_client, mock_event_bus):
        """Test list_executions returns empty list initially"""
        from app.workflows import WorkflowEngine

        engine = WorkflowEngine(llm_client=mock_llm_client)

        executions = engine.list_executions()
        assert executions == []


# =============================================================================
# SCHEMA TESTS
# =============================================================================

class TestSchemas:
    """Tests for workflow schema models"""

    def test_workflow_execution_includes_model_config_used(self):
        """Test WorkflowExecution includes model_config_used field"""
        from app.workflows import WorkflowExecution

        execution = WorkflowExecution(
            workflow_id="test-workflow",
            workflow_name="Test Workflow",
            model_config_used={"orchestrator_model": "openai/gpt-4o"},
        )

        assert execution.model_config_used == {"orchestrator_model": "openai/gpt-4o"}

        # Test serialization
        data = execution.to_dict()
        assert "modelConfigUsed" in data
        assert data["modelConfigUsed"]["orchestrator_model"] == "openai/gpt-4o"

    def test_step_execution_serialization(self):
        """Test StepExecution serialization"""
        from app.workflows import StepExecution, StepExecutionState

        step = StepExecution(
            step_id="step-1",
            state=StepExecutionState.COMPLETED,
            executor_id="research-lead",
            model_used="ollama/llama3.1:8b",
            tokens_used=150,
            estimated_cost=0.0,
            outputs={"result": "test output"},
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
        )

        data = step.to_dict()

        assert data["stepId"] == "step-1"
        assert data["state"] == "completed"
        assert data["executorId"] == "research-lead"
        assert data["modelUsed"] == "ollama/llama3.1:8b"
        assert data["tokensUsed"] == 150
        assert data["outputs"] == {"result": "test output"}
        assert "startedAt" in data
        assert "completedAt" in data

    def test_step_execution_with_worker_calls(self):
        """Test StepExecution with worker call tracking"""
        from app.workflows import StepExecution, StepExecutionState

        step = StepExecution(
            step_id="step-1",
            state=StepExecutionState.COMPLETED,
            worker_calls=[
                {"worker_id": "web-searcher", "task": "Search task", "result": {"data": "result"}},
                {"worker_id": "doc-parser", "task": "Parse task", "result": {"data": "result"}},
            ],
        )

        data = step.to_dict()

        assert len(data["workerCalls"]) == 2
        assert data["workerCalls"][0]["worker_id"] == "web-searcher"

    def test_workflow_definition_to_dict(self):
        """Test WorkflowDefinition serialization"""
        from app.workflows import (
            WorkflowDefinition,
            WorkflowStep,
            Checkpoint,
            CheckpointType,
        )

        workflow = WorkflowDefinition(
            id="test-workflow",
            name="Test Workflow",
            description="A test workflow",
            version="1.0.0",
            orchestrator_model="openai/gpt-4o-mini",
            steps=[
                WorkflowStep(
                    id="step-1",
                    name="Step 1",
                    description="First step",
                    executor="research-lead",
                    outputs=["result"],
                ),
            ],
            checkpoints=[
                Checkpoint(
                    id="checkpoint-1",
                    name="Review Checkpoint",
                    type=CheckpointType.HUMAN_APPROVAL,
                    after_step="step-1",
                ),
            ],
            required_inputs=["input1"],
            final_outputs=["output1"],
            tags=["test"],
        )

        data = workflow.to_dict()

        assert data["id"] == "test-workflow"
        assert data["name"] == "Test Workflow"
        assert data["orchestratorModel"] == "openai/gpt-4o-mini"
        assert len(data["steps"]) == 1
        assert data["steps"][0]["name"] == "Step 1"
        assert len(data["checkpoints"]) == 1
        assert data["checkpoints"][0]["type"] == "human_approval"
        assert data["requiredInputs"] == ["input1"]
        assert data["tags"] == ["test"]

    def test_worker_spec_to_dict(self):
        """Test WorkerSpec serialization"""
        from app.workflows import WorkerSpec, ModelTier

        worker = WorkerSpec(
            id="test-worker",
            name="Test Worker",
            description="A test worker",
            model="ollama/llama3.2:3b",
            task_prompt="Do the task",
            input_schema={"input": "string"},
            output_schema={"output": "string"},
            tool="calculator",
            examples=[{"input": {"x": 1}, "output": {"y": 2}}],
        )

        data = worker.to_dict()

        assert data["id"] == "test-worker"
        assert data["name"] == "Test Worker"
        assert data["model"] == "ollama/llama3.2:3b"
        assert data["modelTier"] == "worker"
        assert data["taskPrompt"] == "Do the task"
        assert data["tool"] == "calculator"
        assert len(data["examples"]) == 1

    def test_team_lead_spec_to_dict(self):
        """Test TeamLeadSpec serialization"""
        from app.workflows import TeamLeadSpec, WorkerSpec

        lead = TeamLeadSpec(
            id="test-lead",
            name="Test Lead",
            domain="research",
            description="A test team lead",
            model="ollama/llama3.1:8b",
            system_prompt="You are a test lead",
            workers=[
                WorkerSpec(
                    id="worker-1",
                    name="Worker 1",
                    description="First worker",
                    task_prompt="Do task 1",
                ),
            ],
        )

        data = lead.to_dict()

        assert data["id"] == "test-lead"
        assert data["domain"] == "research"
        assert data["modelTier"] == "team_lead"
        assert len(data["workers"]) == 1
        assert data["workers"][0]["id"] == "worker-1"


# =============================================================================
# API ROUTE TESTS
# =============================================================================

class TestAPIRoutes:
    """Tests for hierarchical workflow API routes"""

    @pytest.fixture
    def test_app(self, mock_llm_client):
        """Create test FastAPI app with mocked dependencies"""
        from fastapi import FastAPI
        from app.api.hierarchical_routes import router, init_hierarchical_routes

        # Mock the event bus
        with patch("app.workflows.engine.event_bus") as mock_bus:
            mock_mission = MagicMock()
            mock_mission.id = "test-mission-123"
            mock_bus.create_mission.return_value = mock_mission

            # Mock auth middleware
            with patch("app.api.hierarchical_routes.require_api_key") as mock_api_key, \
                 patch("app.api.hierarchical_routes.require_operator") as mock_operator, \
                 patch("app.api.hierarchical_routes.require_admin") as mock_admin:

                # Make auth return a mock user
                mock_user = MagicMock()
                mock_user.user_id = "test-user"
                mock_user.role = "admin"

                async def mock_auth():
                    return mock_user

                mock_api_key.return_value = mock_auth
                mock_operator.return_value = mock_auth
                mock_admin.return_value = mock_auth

                app = FastAPI()
                app.include_router(router, prefix="/api/v1")

                # Initialize with mock LLM client
                init_hierarchical_routes(mock_llm_client, enable_local_models=True)

                yield TestClient(app)

    def test_get_templates_lists_workflows(self, test_app):
        """Test GET /hierarchical/templates lists workflows"""
        response = test_app.get("/api/v1/hierarchical/templates")

        assert response.status_code == 200
        data = response.json()
        assert "workflows" in data
        assert "count" in data
        assert isinstance(data["workflows"], list)

    def test_get_templates_filter_by_tag(self, test_app):
        """Test GET /hierarchical/templates with tag filter"""
        response = test_app.get("/api/v1/hierarchical/templates?tag=finance")

        assert response.status_code == 200
        data = response.json()
        assert "filter" in data
        assert data["filter"]["tag"] == "finance"

    def test_get_domains_lists_all_domains(self, test_app):
        """Test GET /hierarchical/domains lists all domains"""
        response = test_app.get("/api/v1/hierarchical/domains")

        assert response.status_code == 200
        data = response.json()
        assert "domains" in data
        assert "count" in data

        # Check expected domains exist
        domain_names = [d["domain"] for d in data["domains"]]
        assert "research" in domain_names
        assert "finance" in domain_names
        assert "content" in domain_names

    def test_get_domain_details(self, test_app):
        """Test GET /hierarchical/domains/{domain} returns domain details"""
        response = test_app.get("/api/v1/hierarchical/domains/research")

        assert response.status_code == 200
        data = response.json()
        assert "domain" in data
        assert "teamLead" in data
        assert data["domain"] == "research"
        assert "workers" in data["teamLead"]

    def test_get_domain_not_found(self, test_app):
        """Test GET /hierarchical/domains/{domain} with invalid domain"""
        response = test_app.get("/api/v1/hierarchical/domains/nonexistent")

        assert response.status_code == 404

    def test_get_workers_lists_all_workers(self, test_app):
        """Test GET /hierarchical/workers lists all workers"""
        response = test_app.get("/api/v1/hierarchical/workers")

        assert response.status_code == 200
        data = response.json()
        assert "workers" in data
        assert "count" in data
        assert len(data["workers"]) > 0

        # Check worker structure
        worker = data["workers"][0]
        assert "id" in worker
        assert "name" in worker
        assert "description" in worker
        assert "model" in worker

    def test_get_workers_filter_by_domain(self, test_app):
        """Test GET /hierarchical/workers with domain filter"""
        response = test_app.get("/api/v1/hierarchical/workers?domain=research")

        assert response.status_code == 200
        data = response.json()
        assert "filter" in data
        assert data["filter"]["domain"] == "research"

    def test_get_worker_details(self, test_app):
        """Test GET /hierarchical/workers/{worker_id} returns worker details"""
        response = test_app.get("/api/v1/hierarchical/workers/web-searcher")

        assert response.status_code == 200
        data = response.json()
        assert "worker" in data
        assert data["worker"]["id"] == "web-searcher"

    def test_get_worker_not_found(self, test_app):
        """Test GET /hierarchical/workers/{worker_id} with invalid worker"""
        response = test_app.get("/api/v1/hierarchical/workers/nonexistent")

        assert response.status_code == 404

    def test_get_config_presets(self, test_app):
        """Test GET /hierarchical/config/presets returns all presets"""
        response = test_app.get("/api/v1/hierarchical/config/presets")

        assert response.status_code == 200
        data = response.json()
        assert "presets" in data
        assert "count" in data
        assert "cost_optimized" in data["presets"]
        assert "quality_optimized" in data["presets"]

    def test_get_config_preset_by_name(self, test_app):
        """Test GET /hierarchical/config/presets/{name} returns preset details"""
        response = test_app.get("/api/v1/hierarchical/config/presets/cost_optimized")

        assert response.status_code == 200
        data = response.json()
        assert "presetName" in data
        assert "configuration" in data
        assert data["presetName"] == "cost_optimized"

    def test_get_config_preset_not_found(self, test_app):
        """Test GET /hierarchical/config/presets/{name} with invalid preset"""
        response = test_app.get("/api/v1/hierarchical/config/presets/nonexistent")

        assert response.status_code == 404

    def test_post_estimate_cost(self, test_app):
        """Test POST /hierarchical/config/estimate-cost returns estimate"""
        from app.workflows.templates import ALL_WORKFLOWS

        if not ALL_WORKFLOWS:
            pytest.skip("No workflows available for testing")

        workflow_id = list(ALL_WORKFLOWS.keys())[0]

        response = test_app.post(
            "/api/v1/hierarchical/config/estimate-cost",
            json={
                "workflow_id": workflow_id,
                "model_config": {"preset": "cost_optimized"},
                "avg_tokens_per_step": 2000,
                "avg_worker_tokens": 500,
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "workflowId" in data
        assert "costEstimate" in data
        assert "total_cost" in data["costEstimate"]

    def test_post_estimate_cost_workflow_not_found(self, test_app):
        """Test POST /hierarchical/config/estimate-cost with invalid workflow"""
        response = test_app.post(
            "/api/v1/hierarchical/config/estimate-cost",
            json={
                "workflow_id": "nonexistent-workflow",
            }
        )

        assert response.status_code == 404

    def test_get_template_by_id(self, test_app):
        """Test GET /hierarchical/templates/{id} returns template details"""
        from app.workflows.templates import ALL_WORKFLOWS

        if not ALL_WORKFLOWS:
            pytest.skip("No workflows available for testing")

        workflow_id = list(ALL_WORKFLOWS.keys())[0]

        response = test_app.get(f"/api/v1/hierarchical/templates/{workflow_id}")

        assert response.status_code == 200
        data = response.json()
        assert "workflow" in data
        assert "id" in data["workflow"]

    def test_get_template_not_found(self, test_app):
        """Test GET /hierarchical/templates/{id} with invalid template"""
        response = test_app.get("/api/v1/hierarchical/templates/nonexistent")

        assert response.status_code == 404

    def test_get_models_summary(self, test_app):
        """Test GET /hierarchical/models returns model summary"""
        response = test_app.get("/api/v1/hierarchical/models")

        assert response.status_code == 200
        data = response.json()
        assert "costEstimates" in data
        assert "requiredModels" in data

    def test_get_health(self, test_app):
        """Test GET /hierarchical/health returns health status"""
        response = test_app.get("/api/v1/hierarchical/health")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "engine_initialized" in data
        assert "template_count" in data
        assert "domain_count" in data
        assert "worker_count" in data


# =============================================================================
# TEAM LEADS AND WORKERS TESTS
# =============================================================================

class TestTeamLeadsAndWorkers:
    """Tests for team leads and workers configuration"""

    def test_all_team_leads_defined(self):
        """Test all expected team leads are defined"""
        from app.workflows import ALL_TEAM_LEADS

        expected_domains = [
            "research", "finance", "content", "sales",
            "devops", "legal", "medical", "investigation"
        ]

        for domain in expected_domains:
            assert any(
                lead.domain == domain for lead in ALL_TEAM_LEADS.values()
            ), f"Missing team lead for domain: {domain}"

    def test_all_workers_have_required_fields(self):
        """Test all workers have required configuration"""
        from app.workflows import ALL_WORKERS

        for worker_id, worker in ALL_WORKERS.items():
            assert worker.id, f"Worker {worker_id} missing id"
            assert worker.name, f"Worker {worker_id} missing name"
            assert worker.description, f"Worker {worker_id} missing description"
            assert worker.model, f"Worker {worker_id} missing model"
            assert worker.task_prompt, f"Worker {worker_id} missing task_prompt"

    def test_get_team_lead_function(self):
        """Test get_team_lead helper function"""
        from app.workflows import get_team_lead

        lead = get_team_lead("research")
        assert lead is not None
        assert lead.domain == "research"

        lead = get_team_lead("nonexistent")
        assert lead is None

    def test_get_worker_function(self):
        """Test get_worker helper function"""
        from app.workflows import get_worker

        worker = get_worker("web-searcher")
        assert worker is not None
        assert worker.id == "web-searcher"

        worker = get_worker("nonexistent")
        assert worker is None

    def test_get_workers_for_domain_function(self):
        """Test get_workers_for_domain helper function"""
        from app.workflows import get_workers_for_domain

        workers = get_workers_for_domain("research")
        assert workers is not None
        assert len(workers) > 0
        assert all(hasattr(w, "id") for w in workers)

    def test_workers_have_valid_model_references(self):
        """Test all workers reference valid local models"""
        from app.workflows import ALL_WORKERS

        valid_prefixes = ["ollama/", "openai/", "anthropic/", "google/"]

        for worker_id, worker in ALL_WORKERS.items():
            has_valid_prefix = any(worker.model.startswith(prefix) for prefix in valid_prefixes)
            assert has_valid_prefix, f"Worker {worker_id} has invalid model: {worker.model}"


# =============================================================================
# WORKFLOW TEMPLATES TESTS
# =============================================================================

class TestWorkflowTemplates:
    """Tests for workflow templates"""

    def test_all_workflows_have_required_fields(self):
        """Test all workflow templates have required configuration"""
        from app.workflows.templates import ALL_WORKFLOWS

        for workflow_id, workflow in ALL_WORKFLOWS.items():
            assert workflow.id, f"Workflow {workflow_id} missing id"
            assert workflow.name, f"Workflow {workflow_id} missing name"
            assert workflow.description, f"Workflow {workflow_id} missing description"
            assert len(workflow.steps) > 0, f"Workflow {workflow_id} has no steps"
            assert len(workflow.required_inputs) > 0, f"Workflow {workflow_id} has no required inputs"

    def test_list_workflows_function(self):
        """Test list_workflows helper function"""
        from app.workflows.templates import list_workflows

        workflows = list_workflows()
        assert isinstance(workflows, list)

    def test_get_workflow_function(self):
        """Test get_workflow helper function"""
        from app.workflows.templates import get_workflow, ALL_WORKFLOWS

        if not ALL_WORKFLOWS:
            pytest.skip("No workflows available for testing")

        workflow_id = list(ALL_WORKFLOWS.keys())[0]
        workflow = get_workflow(workflow_id)
        assert workflow is not None
        assert workflow.id == workflow_id

        workflow = get_workflow("nonexistent")
        assert workflow is None

    def test_get_workflows_by_tag(self):
        """Test filtering workflows by tag"""
        from app.workflows.templates import get_workflows_by_tag

        # Test with a common tag
        finance_workflows = get_workflows_by_tag("finance")
        assert isinstance(finance_workflows, list)

        # Test with nonexistent tag
        empty_workflows = get_workflows_by_tag("nonexistent-tag-12345")
        assert len(empty_workflows) == 0

    def test_workflow_steps_reference_valid_executors(self):
        """Test workflow steps reference valid team leads or orchestrator"""
        from app.workflows.templates import ALL_WORKFLOWS
        from app.workflows import ALL_TEAM_LEADS

        valid_executors = set(ALL_TEAM_LEADS.keys())
        valid_executors.add("orchestrator")

        # Also add domain-lead variants
        for lead in ALL_TEAM_LEADS.values():
            valid_executors.add(f"{lead.domain}-lead")

        for workflow_id, workflow in ALL_WORKFLOWS.items():
            for step in workflow.steps:
                # Normalize executor name for comparison
                executor = step.executor
                is_valid = (
                    executor in valid_executors or
                    executor == "orchestrator" or
                    executor.replace("-lead", "") in [l.domain for l in ALL_TEAM_LEADS.values()]
                )
                assert is_valid, f"Workflow {workflow_id} step {step.id} has invalid executor: {executor}"


# =============================================================================
# ERROR HANDLING TESTS
# =============================================================================

class TestErrorHandling:
    """Tests for error handling in workflows"""

    def test_invalid_preset_raises_error(self):
        """Test that invalid preset name raises ValueError"""
        from app.workflows import get_config_from_preset

        with pytest.raises(ValueError) as exc_info:
            get_config_from_preset("invalid_preset_name")

        assert "Unknown preset" in str(exc_info.value)

    def test_workflow_execution_state_enum(self):
        """Test WorkflowExecutionState enum values"""
        from app.workflows import WorkflowExecutionState

        assert WorkflowExecutionState.PENDING.value == "pending"
        assert WorkflowExecutionState.RUNNING.value == "running"
        assert WorkflowExecutionState.COMPLETED.value == "completed"
        assert WorkflowExecutionState.FAILED.value == "failed"
        assert WorkflowExecutionState.CANCELLED.value == "cancelled"
        assert WorkflowExecutionState.WAITING_CHECKPOINT.value == "waiting_checkpoint"

    def test_step_execution_state_enum(self):
        """Test StepExecutionState enum values"""
        from app.workflows import StepExecutionState

        assert StepExecutionState.PENDING.value == "pending"
        assert StepExecutionState.RUNNING.value == "running"
        assert StepExecutionState.COMPLETED.value == "completed"
        assert StepExecutionState.FAILED.value == "failed"
        assert StepExecutionState.SKIPPED.value == "skipped"
        assert StepExecutionState.DELEGATING.value == "delegating"

    def test_checkpoint_type_enum(self):
        """Test CheckpointType enum values"""
        from app.workflows import CheckpointType

        assert CheckpointType.HUMAN_APPROVAL.value == "human_approval"
        assert CheckpointType.HUMAN_INPUT.value == "human_input"
        assert CheckpointType.REVIEW.value == "review"
        assert CheckpointType.GATE.value == "gate"

    def test_model_tier_enum(self):
        """Test ModelTier enum values"""
        from app.workflows import ModelTier

        assert ModelTier.ORCHESTRATOR.value == "orchestrator"
        assert ModelTier.TEAM_LEAD.value == "team_lead"
        assert ModelTier.WORKER.value == "worker"
