"""
Workflows Module - 3-Tier Hierarchical Agent Orchestration

This module provides:
- WorkflowDefinition schema for defining multi-agent workflows
- TeamLeadSpec and WorkerSpec for the agent hierarchy
- WorkflowEngine for executing workflows
- Pre-defined high-value workflow templates

Architecture:
┌─────────────────────────────────────────────────────────────────┐
│              THE GENERAL (Orchestrator)                         │
│              Model: GPT-4o / Claude                             │
└─────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌───────────────┐     ┌───────────────┐     ┌───────────────┐
│  TEAM LEAD    │     │  TEAM LEAD    │     │  TEAM LEAD    │
│  (7B-14B)     │     │  (7B-14B)     │     │  (7B-14B)     │
└───────────────┘     └───────────────┘     └───────────────┘
        │                     │                     │
   ┌────┴────┐           ┌────┴────┐           ┌────┴────┐
   ▼    ▼    ▼           ▼    ▼    ▼           ▼    ▼    ▼
┌─────┐┌─────┐┌─────┐ ┌─────┐┌─────┐┌─────┐ ┌─────┐┌─────┐┌─────┐
│Work-││Work-││Work-│ │Work-││Work-││Work-│ │Work-││Work-││Work-│
│er   ││er   ││er   │ │er   ││er   ││er   │ │er   ││er   ││er   │
│(1-3B││(1-3B││(1-3B│ │(1-3B││(1-3B││(1-3B│ │(1-3B││(1-3B││(1-3B│
└─────┘└─────┘└─────┘ └─────┘└─────┘└─────┘ └─────┘└─────┘└─────┘

Domains:
- research: Deep research, OSINT, fact verification
- finance: Financial analysis, calculations, projections
- content: Writing, editing, SEO, social media
- sales: Lead research, outreach, CRM operations
- devops: Monitoring, incident response, deployments
- legal: Case analysis, document drafting, FOIA
- medical: Clinical analysis, compliance, documentation
- investigation: Evidence collection, timeline, patterns
"""

from app.workflows.schema import (
    # Core types
    ModelTier,
    WorkerSpec,
    TeamLeadSpec,
    CheckpointType,
    WorkflowStep,
    Checkpoint,
    WorkflowDefinition,
    # Execution types
    WorkflowExecutionState,
    StepExecutionState,
    StepExecution,
    WorkflowExecution,
)

from app.workflows.team_leads import (
    # All team leads
    ALL_TEAM_LEADS,
    ALL_WORKERS,
    RESEARCH_TEAM_LEAD,
    FINANCE_TEAM_LEAD,
    CONTENT_TEAM_LEAD,
    SALES_TEAM_LEAD,
    DEVOPS_TEAM_LEAD,
    LEGAL_TEAM_LEAD,
    MEDICAL_TEAM_LEAD,
    INVESTIGATION_TEAM_LEAD,
    # Lookup functions
    get_team_lead,
    get_worker,
    get_workers_for_domain,
    list_domains,
    get_model_summary,
)

from app.workflows.engine import (
    WorkflowEngine,
    get_workflow_engine,
    init_workflow_engine,
)

from app.workflows.model_config import (
    # Model configuration
    ModelConfig,
    ModelRegistry,
    MODEL_CATALOG,
    MODEL_ALIASES,
    # Preset configurations
    COST_OPTIMIZED_CONFIG,
    QUALITY_OPTIMIZED_CONFIG,
    FULL_API_CONFIG,
    FULL_LOCAL_CONFIG,
    FINANCE_SPECIALIZED_CONFIG,
    LEGAL_SPECIALIZED_CONFIG,
    CONFIG_PRESETS,
    # Helper functions
    estimate_workflow_cost,
    merge_configs,
    get_config_from_preset,
    create_config_from_request,
    list_available_presets,
)

from app.workflows.benchmark import (
    # Benchmark Models
    StepMetric,
    BenchmarkRun,
    BenchmarkComparison,
    LeaderboardEntry,
    # Benchmark Engine
    BenchmarkEngine,
    get_benchmark_engine,
    init_benchmark_engine,
    # Model Configs for Benchmarking
    MODEL_CONFIGS,
)

from app.workflows.templates import (
    # Workflow Registry
    ALL_WORKFLOWS,
    get_workflow,
    list_workflows,
    get_workflows_by_tag,
    # Original Workflows
    INVESTMENT_DUE_DILIGENCE,
    AUTONOMOUS_SALES_PIPELINE,
    INCIDENT_RESPONSE,
    CONTENT_PRODUCTION,
    LEGAL_CASE_ANALYSIS,
    MEDICAL_DOCUMENTATION_REVIEW,
    COMPETITIVE_INTELLIGENCE,
    CUSTOMER_SUPPORT_ESCALATION,
    TECHNICAL_DOCUMENTATION,
    RISK_ASSESSMENT,
    # New Workflows (Jan 2026) - Code/Support/Analytics
    CODE_REVIEW_PIPELINE,
    CUSTOMER_SUPPORT_RESOLUTION,
    COMPETITIVE_INTELLIGENCE_REPORT,
    AUTOMATED_DATA_REPORT,
    # New Workflows (Jan 2026) - Business Tools Integration
    NEWS_INTELLIGENCE_BRIEFING,
    DATA_PROCESSING_REPORT,
    GLOBAL_CONTENT_LOCALIZATION,
)

from app.workflows.ralph_engine import (
    # Ralph Self-Correction Engine
    RalphWorkflowEngine,
    RalphWorkflowState,
    RalphTask,
    TaskStatus,
    Iteration,
    IterationOutcome,
)

__all__ = [
    # Schema
    "ModelTier",
    "WorkerSpec",
    "TeamLeadSpec",
    "CheckpointType",
    "WorkflowStep",
    "Checkpoint",
    "WorkflowDefinition",
    "WorkflowExecutionState",
    "StepExecutionState",
    "StepExecution",
    "WorkflowExecution",
    # Team Leads
    "ALL_TEAM_LEADS",
    "ALL_WORKERS",
    "RESEARCH_TEAM_LEAD",
    "FINANCE_TEAM_LEAD",
    "CONTENT_TEAM_LEAD",
    "SALES_TEAM_LEAD",
    "DEVOPS_TEAM_LEAD",
    "LEGAL_TEAM_LEAD",
    "MEDICAL_TEAM_LEAD",
    "INVESTIGATION_TEAM_LEAD",
    "get_team_lead",
    "get_worker",
    "get_workers_for_domain",
    "list_domains",
    "get_model_summary",
    # Engine
    "WorkflowEngine",
    "get_workflow_engine",
    "init_workflow_engine",
    # Model Configuration
    "ModelConfig",
    "ModelRegistry",
    "MODEL_CATALOG",
    "MODEL_ALIASES",
    "COST_OPTIMIZED_CONFIG",
    "QUALITY_OPTIMIZED_CONFIG",
    "FULL_API_CONFIG",
    "FULL_LOCAL_CONFIG",
    "FINANCE_SPECIALIZED_CONFIG",
    "LEGAL_SPECIALIZED_CONFIG",
    "CONFIG_PRESETS",
    "estimate_workflow_cost",
    "merge_configs",
    "get_config_from_preset",
    "create_config_from_request",
    "list_available_presets",
    # Benchmarking
    "StepMetric",
    "BenchmarkRun",
    "BenchmarkComparison",
    "LeaderboardEntry",
    "BenchmarkEngine",
    "get_benchmark_engine",
    "init_benchmark_engine",
    "MODEL_CONFIGS",
    # Workflow Templates - Registry
    "ALL_WORKFLOWS",
    "get_workflow",
    "list_workflows",
    "get_workflows_by_tag",
    # Workflow Templates - Original
    "INVESTMENT_DUE_DILIGENCE",
    "AUTONOMOUS_SALES_PIPELINE",
    "INCIDENT_RESPONSE",
    "CONTENT_PRODUCTION",
    "LEGAL_CASE_ANALYSIS",
    "MEDICAL_DOCUMENTATION_REVIEW",
    "COMPETITIVE_INTELLIGENCE",
    "CUSTOMER_SUPPORT_ESCALATION",
    "TECHNICAL_DOCUMENTATION",
    "RISK_ASSESSMENT",
    # Workflow Templates - New (Jan 2026) - Code/Support/Analytics
    "CODE_REVIEW_PIPELINE",
    "CUSTOMER_SUPPORT_RESOLUTION",
    "COMPETITIVE_INTELLIGENCE_REPORT",
    "AUTOMATED_DATA_REPORT",
    # Workflow Templates - New (Jan 2026) - Business Tools Integration
    "NEWS_INTELLIGENCE_BRIEFING",
    "DATA_PROCESSING_REPORT",
    "GLOBAL_CONTENT_LOCALIZATION",
    # Ralph Self-Correction Engine
    "RalphWorkflowEngine",
    "RalphWorkflowState",
    "RalphTask",
    "TaskStatus",
    "Iteration",
    "IterationOutcome",
]
