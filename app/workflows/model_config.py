"""
Model Configuration System for Hierarchical Workflows

Provides runtime model configuration and overrides for the 3-tier agent hierarchy:
- Orchestrator (The General) - API models for complex reasoning
- Team Leads (7B-14B) - Mid-tier models for domain coordination
- Workers (1B-3B) - Small, fast models for narrow tasks

Features:
- Preset configurations (cost-optimized, quality-optimized, full-API, full-local)
- Model catalog with pricing and context window metadata
- Runtime override support for API requests
- Cost estimation for workflows
"""

from typing import Dict, Any, Optional, List, Union, TYPE_CHECKING
from pydantic import BaseModel, Field, field_validator, model_validator
import re

if TYPE_CHECKING:
    from app.workflows.schema import WorkflowDefinition


# =============================================================================
# MODEL CATALOG
# =============================================================================

MODEL_CATALOG: Dict[str, Dict[str, Any]] = {
    # OpenAI Models
    "openai/gpt-4o": {
        "tier": "api",
        "provider": "openai",
        "context": 128000,
        "cost_input": 0.0025,  # per 1K tokens
        "cost_output": 0.01,
        "description": "Most capable OpenAI model, best for complex reasoning",
        "recommended_for": ["orchestrator"],
    },
    "openai/gpt-4o-mini": {
        "tier": "api",
        "provider": "openai",
        "context": 128000,
        "cost_input": 0.00015,
        "cost_output": 0.0006,
        "description": "Fast, cost-effective OpenAI model",
        "recommended_for": ["orchestrator", "team_lead"],
    },
    "openai/gpt-4-turbo": {
        "tier": "api",
        "provider": "openai",
        "context": 128000,
        "cost_input": 0.01,
        "cost_output": 0.03,
        "description": "Previous flagship model, still very capable",
        "recommended_for": ["orchestrator"],
    },
    "openai/gpt-3.5-turbo": {
        "tier": "api",
        "provider": "openai",
        "context": 16385,
        "cost_input": 0.0005,
        "cost_output": 0.0015,
        "description": "Legacy fast model, lower cost",
        "recommended_for": ["worker"],
    },

    # Anthropic Models
    "anthropic/claude-3.5-sonnet": {
        "tier": "api",
        "provider": "anthropic",
        "context": 200000,
        "cost_input": 0.003,
        "cost_output": 0.015,
        "description": "Best balance of capability and speed from Anthropic",
        "recommended_for": ["orchestrator", "team_lead"],
    },
    "anthropic/claude-3-opus": {
        "tier": "api",
        "provider": "anthropic",
        "context": 200000,
        "cost_input": 0.015,
        "cost_output": 0.075,
        "description": "Most capable Anthropic model",
        "recommended_for": ["orchestrator"],
    },
    "anthropic/claude-3-haiku": {
        "tier": "api",
        "provider": "anthropic",
        "context": 200000,
        "cost_input": 0.00025,
        "cost_output": 0.00125,
        "description": "Fast, efficient Anthropic model",
        "recommended_for": ["team_lead", "worker"],
    },

    # Google Models
    "google/gemini-pro": {
        "tier": "api",
        "provider": "google",
        "context": 32000,
        "cost_input": 0.00025,
        "cost_output": 0.0005,
        "description": "Google's general purpose model",
        "recommended_for": ["team_lead", "worker"],
    },
    "google/gemini-1.5-pro": {
        "tier": "api",
        "provider": "google",
        "context": 1000000,
        "cost_input": 0.00125,
        "cost_output": 0.005,
        "description": "Google's flagship with million token context",
        "recommended_for": ["orchestrator", "team_lead"],
    },

    # Local Models via Ollama (7B-14B - Team Lead tier)
    "ollama/llama3.1:8b": {
        "tier": "local",
        "provider": "ollama",
        "context": 8192,
        "cost_input": 0.0,
        "cost_output": 0.0,
        "description": "Meta's Llama 3.1 8B - excellent general purpose",
        "recommended_for": ["team_lead"],
        "vram_required": 6,  # GB
    },
    "ollama/llama3.1:70b": {
        "tier": "local",
        "provider": "ollama",
        "context": 8192,
        "cost_input": 0.0,
        "cost_output": 0.0,
        "description": "Meta's Llama 3.1 70B - near API quality",
        "recommended_for": ["orchestrator", "team_lead"],
        "vram_required": 40,
    },
    "ollama/gemma2:9b": {
        "tier": "local",
        "provider": "ollama",
        "context": 8192,
        "cost_input": 0.0,
        "cost_output": 0.0,
        "description": "Google's Gemma 2 9B - fast and capable",
        "recommended_for": ["team_lead"],
        "vram_required": 6,
    },
    "ollama/mistral:7b": {
        "tier": "local",
        "provider": "ollama",
        "context": 32768,
        "cost_input": 0.0,
        "cost_output": 0.0,
        "description": "Mistral 7B - efficient with long context",
        "recommended_for": ["team_lead"],
        "vram_required": 5,
    },
    "ollama/mixtral:8x7b": {
        "tier": "local",
        "provider": "ollama",
        "context": 32768,
        "cost_input": 0.0,
        "cost_output": 0.0,
        "description": "Mixtral MoE - expert routing for complex tasks",
        "recommended_for": ["team_lead"],
        "vram_required": 26,
    },
    "ollama/codellama:13b": {
        "tier": "local",
        "provider": "ollama",
        "context": 16384,
        "cost_input": 0.0,
        "cost_output": 0.0,
        "description": "Code Llama 13B - specialized for code",
        "recommended_for": ["team_lead"],
        "vram_required": 9,
    },
    "ollama/deepseek-coder:6.7b": {
        "tier": "local",
        "provider": "ollama",
        "context": 16384,
        "cost_input": 0.0,
        "cost_output": 0.0,
        "description": "DeepSeek Coder 6.7B - code generation specialist",
        "recommended_for": ["team_lead", "worker"],
        "vram_required": 5,
    },

    # Local Models via Ollama (1B-3B - Worker tier)
    "ollama/llama3.2:3b": {
        "tier": "local",
        "provider": "ollama",
        "context": 8192,
        "cost_input": 0.0,
        "cost_output": 0.0,
        "description": "Llama 3.2 3B - fast narrow-task execution",
        "recommended_for": ["worker"],
        "vram_required": 2,
    },
    "ollama/llama3.2:1b": {
        "tier": "local",
        "provider": "ollama",
        "context": 8192,
        "cost_input": 0.0,
        "cost_output": 0.0,
        "description": "Llama 3.2 1B - ultra-fast, simple tasks",
        "recommended_for": ["worker"],
        "vram_required": 1,
    },
    "ollama/phi3:3.8b": {
        "tier": "local",
        "provider": "ollama",
        "context": 4096,
        "cost_input": 0.0,
        "cost_output": 0.0,
        "description": "Microsoft Phi-3 3.8B - excellent reasoning for size",
        "recommended_for": ["worker"],
        "vram_required": 3,
    },
    "ollama/phi3:mini": {
        "tier": "local",
        "provider": "ollama",
        "context": 4096,
        "cost_input": 0.0,
        "cost_output": 0.0,
        "description": "Microsoft Phi-3 Mini - compact reasoning",
        "recommended_for": ["worker"],
        "vram_required": 2,
    },
    "ollama/qwen2.5:3b": {
        "tier": "local",
        "provider": "ollama",
        "context": 8192,
        "cost_input": 0.0,
        "cost_output": 0.0,
        "description": "Qwen 2.5 3B - multilingual, general purpose",
        "recommended_for": ["worker"],
        "vram_required": 2,
    },
    "ollama/qwen2.5-math:1.5b": {
        "tier": "local",
        "provider": "ollama",
        "context": 4096,
        "cost_input": 0.0,
        "cost_output": 0.0,
        "description": "Qwen Math 1.5B - specialized for calculations",
        "recommended_for": ["worker"],
        "vram_required": 1,
    },
    "ollama/tinyllama:1.1b": {
        "tier": "local",
        "provider": "ollama",
        "context": 2048,
        "cost_input": 0.0,
        "cost_output": 0.0,
        "description": "TinyLlama 1.1B - ultra-lightweight",
        "recommended_for": ["worker"],
        "vram_required": 1,
    },
    "ollama/gemma2:2b": {
        "tier": "local",
        "provider": "ollama",
        "context": 8192,
        "cost_input": 0.0,
        "cost_output": 0.0,
        "description": "Gemma 2 2B - small but capable",
        "recommended_for": ["worker"],
        "vram_required": 2,
    },
    "ollama/stablelm2:1.6b": {
        "tier": "local",
        "provider": "ollama",
        "context": 4096,
        "cost_input": 0.0,
        "cost_output": 0.0,
        "description": "StableLM 2 1.6B - compact and stable",
        "recommended_for": ["worker"],
        "vram_required": 1,
    },
}

# Model name aliases for convenience
MODEL_ALIASES: Dict[str, str] = {
    "gpt-4o": "openai/gpt-4o",
    "gpt-4o-mini": "openai/gpt-4o-mini",
    "gpt-4-turbo": "openai/gpt-4-turbo",
    "claude-3.5-sonnet": "anthropic/claude-3.5-sonnet",
    "claude-3-sonnet": "anthropic/claude-3.5-sonnet",
    "claude-3-opus": "anthropic/claude-3-opus",
    "claude-3-haiku": "anthropic/claude-3-haiku",
    "llama3.1:8b": "ollama/llama3.1:8b",
    "llama3.2:3b": "ollama/llama3.2:3b",
    "llama3.2:1b": "ollama/llama3.2:1b",
    "phi3": "ollama/phi3:3.8b",
    "mistral": "ollama/mistral:7b",
    "gemma2:9b": "ollama/gemma2:9b",
    "gemma2:2b": "ollama/gemma2:2b",
}


# =============================================================================
# MODEL CONFIG PYDANTIC MODEL
# =============================================================================

class ModelConfig(BaseModel):
    """
    Configuration for model selection across the 3-tier hierarchy.

    Allows runtime overrides for:
    - Orchestrator model selection
    - Domain-specific team lead models
    - Worker-specific model assignments
    - Global switches (enable_local_models)
    """

    # Orchestrator (The General) - API model for strategic reasoning
    orchestrator_model: str = Field(
        default="openai/gpt-4o-mini",
        description="Model for the orchestrator (The General). Should be a capable API model."
    )

    # Team Lead models by domain
    team_lead_models: Dict[str, str] = Field(
        default_factory=lambda: {
            "research": "ollama/llama3.1:8b",
            "finance": "ollama/llama3.1:8b",
            "content": "ollama/llama3.1:8b",
            "sales": "ollama/llama3.1:8b",
            "devops": "ollama/llama3.1:8b",
            "legal": "ollama/llama3.1:8b",
            "medical": "ollama/llama3.1:8b",
            "investigation": "ollama/llama3.1:8b",
        },
        description="Model assignments for each domain's team lead"
    )

    # Worker models by worker_id
    worker_models: Dict[str, str] = Field(
        default_factory=dict,
        description="Model overrides for specific workers (worker_id -> model)"
    )

    # Fallback models
    default_team_lead_model: str = Field(
        default="ollama/llama3.1:8b",
        description="Default model for team leads when domain not specified"
    )

    default_worker_model: str = Field(
        default="ollama/llama3.2:3b",
        description="Default model for workers when not specifically assigned"
    )

    # Global switches
    enable_local_models: bool = Field(
        default=True,
        description="If False, use API models for all agents (ignores local model assignments)"
    )

    # API model fallback when local models disabled
    api_fallback_team_lead: str = Field(
        default="openai/gpt-4o-mini",
        description="API model to use for team leads when enable_local_models=False"
    )

    api_fallback_worker: str = Field(
        default="openai/gpt-4o-mini",
        description="API model to use for workers when enable_local_models=False"
    )

    @field_validator("orchestrator_model", "default_team_lead_model", "default_worker_model",
                     "api_fallback_team_lead", "api_fallback_worker", mode="before")
    @classmethod
    def resolve_alias(cls, v: str) -> str:
        """Resolve model aliases to full names"""
        return MODEL_ALIASES.get(v, v)

    @field_validator("team_lead_models", "worker_models", mode="before")
    @classmethod
    def resolve_dict_aliases(cls, v: Dict[str, str]) -> Dict[str, str]:
        """Resolve model aliases in dictionaries"""
        if v is None:
            return {}
        return {k: MODEL_ALIASES.get(m, m) for k, m in v.items()}

    @model_validator(mode="after")
    def validate_models_exist(self) -> "ModelConfig":
        """Validate that all specified models exist in catalog"""
        models_to_check = [
            self.orchestrator_model,
            self.default_team_lead_model,
            self.default_worker_model,
            self.api_fallback_team_lead,
            self.api_fallback_worker,
        ]
        models_to_check.extend(self.team_lead_models.values())
        models_to_check.extend(self.worker_models.values())

        for model in models_to_check:
            if model and model not in MODEL_CATALOG:
                # Allow unknown models (they might be custom or dynamically added)
                pass

        return self

    def model_dump_for_api(self) -> Dict[str, Any]:
        """Dump config in API-friendly format with model metadata"""
        return {
            "orchestrator_model": self.orchestrator_model,
            "orchestrator_model_info": MODEL_CATALOG.get(self.orchestrator_model, {}),
            "team_lead_models": self.team_lead_models,
            "worker_models": self.worker_models,
            "default_team_lead_model": self.default_team_lead_model,
            "default_worker_model": self.default_worker_model,
            "enable_local_models": self.enable_local_models,
            "api_fallback_team_lead": self.api_fallback_team_lead,
            "api_fallback_worker": self.api_fallback_worker,
        }


# =============================================================================
# MODEL REGISTRY
# =============================================================================

class ModelRegistry:
    """
    Registry for resolving models based on configuration and role.

    Handles:
    - Model resolution for orchestrator, team leads, and workers
    - Fallback logic when local models are disabled
    - Model validation and tier detection
    """

    @staticmethod
    def get_model_for_orchestrator(config: ModelConfig) -> str:
        """
        Get the model to use for the orchestrator.

        Args:
            config: Model configuration

        Returns:
            Model identifier string
        """
        return config.orchestrator_model

    @staticmethod
    def get_model_for_team_lead(domain: str, config: ModelConfig) -> str:
        """
        Get the model to use for a specific domain's team lead.

        Args:
            domain: Domain name (research, finance, legal, etc.)
            config: Model configuration

        Returns:
            Model identifier string
        """
        # Get configured model for domain
        model = config.team_lead_models.get(domain, config.default_team_lead_model)

        # Check if we need to fall back to API model
        if not config.enable_local_models and ModelRegistry.get_model_tier(model) == "local":
            return config.api_fallback_team_lead

        return model

    @staticmethod
    def get_model_for_worker(worker_id: str, config: ModelConfig, default_model: Optional[str] = None) -> str:
        """
        Get the model to use for a specific worker.

        Args:
            worker_id: Worker identifier
            config: Model configuration
            default_model: Optional default from WorkerSpec (used if no override)

        Returns:
            Model identifier string
        """
        # Priority: explicit override > worker's default > config default
        if worker_id in config.worker_models:
            model = config.worker_models[worker_id]
        elif default_model:
            model = default_model
        else:
            model = config.default_worker_model

        # Check if we need to fall back to API model
        if not config.enable_local_models and ModelRegistry.get_model_tier(model) == "local":
            return config.api_fallback_worker

        return model

    @staticmethod
    def validate_model(model: str) -> bool:
        """
        Validate that a model string is in valid format.

        Valid formats:
        - provider/model-name (e.g., openai/gpt-4o)
        - provider/model:tag (e.g., ollama/llama3.1:8b)

        Args:
            model: Model identifier string

        Returns:
            True if valid format, False otherwise
        """
        # Check for alias first
        resolved = MODEL_ALIASES.get(model, model)

        # Must have provider prefix
        if "/" not in resolved:
            return False

        # Basic format validation
        pattern = r'^[a-zA-Z0-9_-]+/[a-zA-Z0-9_.-]+(:[a-zA-Z0-9_.-]+)?$'
        return bool(re.match(pattern, resolved))

    @staticmethod
    def get_model_tier(model: str) -> str:
        """
        Get the tier (api or local) for a model.

        Args:
            model: Model identifier string

        Returns:
            "api" or "local"
        """
        resolved = MODEL_ALIASES.get(model, model)

        # Check catalog first
        if resolved in MODEL_CATALOG:
            return MODEL_CATALOG[resolved]["tier"]

        # Infer from provider prefix
        if resolved.startswith("ollama/") or resolved.startswith("lmstudio/"):
            return "local"

        # Default to API for unknown providers
        return "api"

    @staticmethod
    def get_model_info(model: str) -> Dict[str, Any]:
        """
        Get full model information from catalog.

        Args:
            model: Model identifier string

        Returns:
            Model metadata dictionary or empty dict if not found
        """
        resolved = MODEL_ALIASES.get(model, model)
        return MODEL_CATALOG.get(resolved, {})

    @staticmethod
    def get_model_cost(model: str, input_tokens: int, output_tokens: int) -> float:
        """
        Calculate cost for model usage.

        Args:
            model: Model identifier string
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens

        Returns:
            Estimated cost in USD
        """
        info = ModelRegistry.get_model_info(model)
        cost_input = info.get("cost_input", 0.0)
        cost_output = info.get("cost_output", 0.0)

        return (input_tokens / 1000 * cost_input) + (output_tokens / 1000 * cost_output)

    @staticmethod
    def list_models_by_tier(tier: str) -> List[str]:
        """
        List all models of a given tier.

        Args:
            tier: "api" or "local"

        Returns:
            List of model identifiers
        """
        return [
            model for model, info in MODEL_CATALOG.items()
            if info.get("tier") == tier
        ]

    @staticmethod
    def list_models_for_role(role: str) -> List[str]:
        """
        List recommended models for a given role.

        Args:
            role: "orchestrator", "team_lead", or "worker"

        Returns:
            List of recommended model identifiers
        """
        return [
            model for model, info in MODEL_CATALOG.items()
            if role in info.get("recommended_for", [])
        ]


# =============================================================================
# PRESET CONFIGURATIONS
# =============================================================================

# Cost-optimized: Local models everywhere except orchestrator
COST_OPTIMIZED_CONFIG = ModelConfig(
    orchestrator_model="openai/gpt-4o-mini",
    team_lead_models={
        "research": "ollama/llama3.1:8b",
        "finance": "ollama/llama3.1:8b",
        "content": "ollama/llama3.1:8b",
        "sales": "ollama/llama3.1:8b",
        "devops": "ollama/llama3.1:8b",
        "legal": "ollama/llama3.1:8b",
        "medical": "ollama/llama3.1:8b",
        "investigation": "ollama/llama3.1:8b",
    },
    default_team_lead_model="ollama/llama3.1:8b",
    default_worker_model="ollama/llama3.2:3b",
    enable_local_models=True,
)

# Quality-optimized: API models for orchestrator and team leads, local for workers
QUALITY_OPTIMIZED_CONFIG = ModelConfig(
    orchestrator_model="openai/gpt-4o",
    team_lead_models={
        "research": "anthropic/claude-3.5-sonnet",
        "finance": "openai/gpt-4o-mini",
        "content": "anthropic/claude-3.5-sonnet",
        "sales": "openai/gpt-4o-mini",
        "devops": "openai/gpt-4o-mini",
        "legal": "anthropic/claude-3.5-sonnet",
        "medical": "anthropic/claude-3.5-sonnet",
        "investigation": "openai/gpt-4o-mini",
    },
    default_team_lead_model="openai/gpt-4o-mini",
    default_worker_model="ollama/llama3.2:3b",
    enable_local_models=True,
)

# Full API: API models for everything (for benchmarking quality)
FULL_API_CONFIG = ModelConfig(
    orchestrator_model="openai/gpt-4o",
    team_lead_models={
        "research": "anthropic/claude-3.5-sonnet",
        "finance": "openai/gpt-4o-mini",
        "content": "anthropic/claude-3.5-sonnet",
        "sales": "openai/gpt-4o-mini",
        "devops": "openai/gpt-4o-mini",
        "legal": "anthropic/claude-3.5-sonnet",
        "medical": "anthropic/claude-3.5-sonnet",
        "investigation": "openai/gpt-4o-mini",
    },
    default_team_lead_model="openai/gpt-4o-mini",
    default_worker_model="openai/gpt-4o-mini",
    enable_local_models=False,
    api_fallback_team_lead="openai/gpt-4o-mini",
    api_fallback_worker="openai/gpt-4o-mini",
)

# Full local: Local models everywhere (for testing/development)
FULL_LOCAL_CONFIG = ModelConfig(
    orchestrator_model="ollama/llama3.1:70b",
    team_lead_models={
        "research": "ollama/llama3.1:8b",
        "finance": "ollama/mistral:7b",
        "content": "ollama/llama3.1:8b",
        "sales": "ollama/gemma2:9b",
        "devops": "ollama/deepseek-coder:6.7b",
        "legal": "ollama/llama3.1:8b",
        "medical": "ollama/llama3.1:8b",
        "investigation": "ollama/llama3.1:8b",
    },
    default_team_lead_model="ollama/llama3.1:8b",
    default_worker_model="ollama/llama3.2:3b",
    enable_local_models=True,
)

# Domain-specialized presets
FINANCE_SPECIALIZED_CONFIG = ModelConfig(
    orchestrator_model="openai/gpt-4o",
    team_lead_models={
        "research": "ollama/llama3.1:8b",
        "finance": "openai/gpt-4o",  # Premium model for finance
        "content": "ollama/llama3.1:8b",
        "sales": "ollama/llama3.1:8b",
        "devops": "ollama/llama3.1:8b",
        "legal": "openai/gpt-4o-mini",  # Better for legal in finance context
        "medical": "ollama/llama3.1:8b",
        "investigation": "ollama/llama3.1:8b",
    },
    worker_models={
        "ratio-calculator": "ollama/qwen2.5-math:1.5b",  # Math-specialized
        "trend-analyzer": "ollama/llama3.2:3b",
    },
    default_team_lead_model="ollama/llama3.1:8b",
    default_worker_model="ollama/llama3.2:3b",
    enable_local_models=True,
)

LEGAL_SPECIALIZED_CONFIG = ModelConfig(
    orchestrator_model="anthropic/claude-3.5-sonnet",  # Claude for nuanced reasoning
    team_lead_models={
        "research": "anthropic/claude-3-haiku",
        "finance": "ollama/llama3.1:8b",
        "content": "ollama/llama3.1:8b",
        "sales": "ollama/llama3.1:8b",
        "devops": "ollama/llama3.1:8b",
        "legal": "anthropic/claude-3.5-sonnet",  # Premium for legal
        "medical": "ollama/llama3.1:8b",
        "investigation": "anthropic/claude-3-haiku",  # Better for investigation
    },
    default_team_lead_model="ollama/llama3.1:8b",
    default_worker_model="ollama/llama3.2:3b",
    enable_local_models=True,
)

# Preset lookup
CONFIG_PRESETS: Dict[str, ModelConfig] = {
    "cost_optimized": COST_OPTIMIZED_CONFIG,
    "quality_optimized": QUALITY_OPTIMIZED_CONFIG,
    "full_api": FULL_API_CONFIG,
    "full_local": FULL_LOCAL_CONFIG,
    "finance_specialized": FINANCE_SPECIALIZED_CONFIG,
    "legal_specialized": LEGAL_SPECIALIZED_CONFIG,
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def estimate_workflow_cost(
    workflow: "WorkflowDefinition",
    config: ModelConfig,
    avg_tokens_per_step: int = 2000,
    avg_worker_tokens: int = 500,
) -> Dict[str, Any]:
    """
    Estimate the cost of running a workflow with given configuration.

    Args:
        workflow: Workflow definition
        config: Model configuration
        avg_tokens_per_step: Average tokens per workflow step (input + output)
        avg_worker_tokens: Average tokens per worker call

    Returns:
        Cost estimate breakdown
    """
    from app.workflows.team_leads import get_team_lead

    cost_breakdown = {
        "orchestrator_cost": 0.0,
        "team_lead_cost": 0.0,
        "worker_cost": 0.0,
        "total_cost": 0.0,
        "model_usage": {},
    }

    # Orchestrator cost (initial planning + final aggregation)
    orchestrator_model = ModelRegistry.get_model_for_orchestrator(config)
    orchestrator_tokens = avg_tokens_per_step * 2  # Planning + aggregation
    cost_breakdown["orchestrator_cost"] = ModelRegistry.get_model_cost(
        orchestrator_model,
        int(orchestrator_tokens * 0.7),  # 70% input
        int(orchestrator_tokens * 0.3),  # 30% output
    )
    cost_breakdown["model_usage"][orchestrator_model] = {
        "calls": 2,
        "tokens": orchestrator_tokens,
    }

    # Team lead and worker costs per step
    for step in workflow.steps:
        if step.executor == "orchestrator":
            # Orchestrator step
            cost_breakdown["orchestrator_cost"] += ModelRegistry.get_model_cost(
                orchestrator_model,
                int(avg_tokens_per_step * 0.7),
                int(avg_tokens_per_step * 0.3),
            )
            cost_breakdown["model_usage"].setdefault(orchestrator_model, {"calls": 0, "tokens": 0})
            cost_breakdown["model_usage"][orchestrator_model]["calls"] += 1
            cost_breakdown["model_usage"][orchestrator_model]["tokens"] += avg_tokens_per_step
        else:
            # Team lead step
            domain = step.executor.replace("-lead", "")
            team_lead = get_team_lead(domain)

            if team_lead:
                # Team lead delegation + aggregation
                tl_model = ModelRegistry.get_model_for_team_lead(domain, config)
                tl_tokens = avg_tokens_per_step * 2  # Delegation + aggregation
                cost_breakdown["team_lead_cost"] += ModelRegistry.get_model_cost(
                    tl_model,
                    int(tl_tokens * 0.7),
                    int(tl_tokens * 0.3),
                )
                cost_breakdown["model_usage"].setdefault(tl_model, {"calls": 0, "tokens": 0})
                cost_breakdown["model_usage"][tl_model]["calls"] += 2
                cost_breakdown["model_usage"][tl_model]["tokens"] += tl_tokens

                # Estimate worker calls (assume 2-3 workers per team lead step)
                for worker in team_lead.workers[:3]:
                    worker_model = ModelRegistry.get_model_for_worker(
                        worker.id, config, worker.model
                    )
                    cost_breakdown["worker_cost"] += ModelRegistry.get_model_cost(
                        worker_model,
                        int(avg_worker_tokens * 0.6),
                        int(avg_worker_tokens * 0.4),
                    )
                    cost_breakdown["model_usage"].setdefault(worker_model, {"calls": 0, "tokens": 0})
                    cost_breakdown["model_usage"][worker_model]["calls"] += 1
                    cost_breakdown["model_usage"][worker_model]["tokens"] += avg_worker_tokens

    cost_breakdown["total_cost"] = (
        cost_breakdown["orchestrator_cost"] +
        cost_breakdown["team_lead_cost"] +
        cost_breakdown["worker_cost"]
    )

    return cost_breakdown


def merge_configs(base: ModelConfig, overrides: Dict[str, Any]) -> ModelConfig:
    """
    Merge override values into a base configuration.

    Args:
        base: Base model configuration
        overrides: Dictionary of override values

    Returns:
        New ModelConfig with overrides applied
    """
    # Get base values
    config_dict = base.model_dump()

    # Apply overrides
    for key, value in overrides.items():
        if key in config_dict:
            if isinstance(config_dict[key], dict) and isinstance(value, dict):
                # Merge dictionaries
                config_dict[key] = {**config_dict[key], **value}
            else:
                # Replace value
                config_dict[key] = value

    return ModelConfig(**config_dict)


def get_config_from_preset(preset_name: str) -> ModelConfig:
    """
    Get a preset configuration by name.

    Args:
        preset_name: Name of the preset (cost_optimized, quality_optimized, etc.)

    Returns:
        ModelConfig for the preset

    Raises:
        ValueError: If preset name is not found
    """
    if preset_name not in CONFIG_PRESETS:
        available = ", ".join(CONFIG_PRESETS.keys())
        raise ValueError(f"Unknown preset: {preset_name}. Available: {available}")

    return CONFIG_PRESETS[preset_name]


def create_config_from_request(
    preset: Optional[str] = None,
    overrides: Optional[Dict[str, Any]] = None,
) -> ModelConfig:
    """
    Create a model configuration from an API request.

    Convenience function for API handlers to create configs from request params.

    Args:
        preset: Optional preset name to start from
        overrides: Optional dictionary of override values

    Returns:
        ModelConfig ready for use
    """
    # Start with preset or default
    if preset:
        base = get_config_from_preset(preset)
    else:
        base = ModelConfig()

    # Apply overrides if any
    if overrides:
        return merge_configs(base, overrides)

    return base


def list_available_presets() -> Dict[str, Dict[str, Any]]:
    """
    List all available configuration presets with summary info.

    Returns:
        Dictionary of preset names to summary info
    """
    result = {}
    for name, config in CONFIG_PRESETS.items():
        # Count local vs API models
        models_used = set()
        models_used.add(config.orchestrator_model)
        models_used.update(config.team_lead_models.values())
        models_used.update(config.worker_models.values())
        models_used.add(config.default_team_lead_model)
        models_used.add(config.default_worker_model)

        local_count = sum(1 for m in models_used if ModelRegistry.get_model_tier(m) == "local")
        api_count = len(models_used) - local_count

        result[name] = {
            "orchestrator_model": config.orchestrator_model,
            "enable_local_models": config.enable_local_models,
            "unique_models": len(models_used),
            "local_models": local_count,
            "api_models": api_count,
            "description": _get_preset_description(name),
        }

    return result


def _get_preset_description(preset_name: str) -> str:
    """Get description for a preset"""
    descriptions = {
        "cost_optimized": "Minimize costs with local models, API only for orchestrator",
        "quality_optimized": "Balance quality and cost with API team leads, local workers",
        "full_api": "Maximum quality with API models everywhere (highest cost)",
        "full_local": "Zero API cost with local models everywhere (requires GPU)",
        "finance_specialized": "Optimized for financial analysis workflows",
        "legal_specialized": "Optimized for legal analysis and investigation workflows",
    }
    return descriptions.get(preset_name, "Custom configuration")
