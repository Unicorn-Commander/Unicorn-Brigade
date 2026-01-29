"""
Unicorn Brigade Workflow Engine

A Lobster-style deterministic workflow engine with:
- Router: Intent/risk/worker classification
- Planner: Step sequence generation for ad-hoc tasks
- Executor: Bounded step-by-step execution
- Verifier: Confidence scoring and escalation
- Approval Gates: HITL with resume tokens
- Memory Integration: mem0 for learning from past executions
- Meta Agent: Dynamic agent creation (Clawdbot-style)
- Model Benchmarks: Automatic model selection for OpenRouter
- Agent-Worker Bridge: Integration with existing agents
- Resilience: Circuit breakers, retry, bulkhead patterns
- Collaboration: Multi-agent coordination patterns
- Control Flow: Conditionals, loops, parallel, branches
- Observability: Metrics, tracing, health checks
"""

from app.engine.models import (
    TaskIntent,
    RiskLevel,
    RoutingResult,
    WorkflowStep,
    WorkflowPlan,
    ExecutionResult,
    VerificationResult,
    ApprovalState,
    ResumeToken,
)
from app.engine.router import TaskRouter
from app.engine.planner import TaskPlanner
from app.engine.executor import StepExecutor
from app.engine.verifier import ResultVerifier
from app.engine.approval import ApprovalGate
from app.engine.workflow import WorkflowEngine, WorkflowLoader

# Memory integration (optional - requires mem0)
try:
    from app.engine.memory_integration import WorkflowMemory, MemoryEnhancedRouter
except ImportError:
    WorkflowMemory = None
    MemoryEnhancedRouter = None

# Meta agent (Clawdbot-style dynamic agent creation)
from app.engine.meta_agent import MetaAgent, AgentDefinition, AgentFactory

# A2UI approval integration
from app.engine.approval_ui import ApprovalUIGenerator, create_approval_ui, create_progress_ui

# Model benchmarks and selection
from app.engine.model_benchmarks import (
    ModelCapability,
    ModelSelector,
    select_best_model,
    get_model_capabilities,
)

# Agent-Worker bridge
from app.engine.agent_bridge import AgentWorkerBridge, UnifiedExecutor

# Resilience patterns
from app.engine.resilience import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitState,
    RetryStrategy,
    RetryConfig,
    Bulkhead,
    ResiliencePolicy,
    ErrorClassifier,
    ErrorCategory,
    CircuitBreakerRegistry,
    create_llm_policy,
    create_http_policy,
    create_database_policy,
    with_resilience,
)

# Multi-agent collaboration
from app.engine.collaboration import (
    CollaborationAgent,
    AgentRole,
    HandoffContext,
    AgentMessage,
    CollaborationState,
    SupervisorPattern,
    SwarmPattern,
    AgentTeamFactory,
    SharedMemoryManager,
)

# Control flow constructs
from app.engine.control_flow import (
    Condition,
    ConditionOperator,
    ConditionEvaluator,
    ConditionalStep,
    LoopStep,
    ParallelStep,
    BranchStep,
    ControlFlowExecutor,
    DynamicStepGenerator,
    parse_workflow_with_control_flow,
)

# Observability (metrics, tracing, health)
from app.engine.observability import (
    MetricsRegistry,
    Counter,
    Gauge,
    Histogram,
    metrics,
    Tracer,
    Span,
    SpanContext,
    tracer,
    StructuredLogger,
    LogContext,
    HealthChecker,
    HealthCheckResult,
    HealthStatus,
    health_checker,
    trace,
    timed,
    counted,
    # Pre-defined metrics
    llm_requests_total,
    llm_request_duration,
    llm_tokens_total,
    workflow_executions_total,
    workflow_duration,
    workflow_steps_total,
    agent_tasks_total,
    active_agents,
    tool_executions_total,
    tool_execution_duration,
)

__all__ = [
    # Models
    "TaskIntent",
    "RiskLevel",
    "RoutingResult",
    "WorkflowStep",
    "WorkflowPlan",
    "ExecutionResult",
    "VerificationResult",
    "ApprovalState",
    "ResumeToken",
    # Core Components
    "TaskRouter",
    "TaskPlanner",
    "StepExecutor",
    "ResultVerifier",
    "ApprovalGate",
    "WorkflowEngine",
    "WorkflowLoader",
    # Memory Integration
    "WorkflowMemory",
    "MemoryEnhancedRouter",
    # Meta Agent
    "MetaAgent",
    "AgentDefinition",
    "AgentFactory",
    # Approval UI
    "ApprovalUIGenerator",
    "create_approval_ui",
    "create_progress_ui",
    # Model Selection
    "ModelCapability",
    "ModelSelector",
    "select_best_model",
    "get_model_capabilities",
    # Agent-Worker Bridge
    "AgentWorkerBridge",
    "UnifiedExecutor",
    # Resilience
    "CircuitBreaker",
    "CircuitBreakerConfig",
    "CircuitState",
    "RetryStrategy",
    "RetryConfig",
    "Bulkhead",
    "ResiliencePolicy",
    "ErrorClassifier",
    "ErrorCategory",
    "CircuitBreakerRegistry",
    "create_llm_policy",
    "create_http_policy",
    "create_database_policy",
    "with_resilience",
    # Collaboration
    "CollaborationAgent",
    "AgentRole",
    "HandoffContext",
    "AgentMessage",
    "CollaborationState",
    "SupervisorPattern",
    "SwarmPattern",
    "AgentTeamFactory",
    "SharedMemoryManager",
    # Control Flow
    "Condition",
    "ConditionOperator",
    "ConditionEvaluator",
    "ConditionalStep",
    "LoopStep",
    "ParallelStep",
    "BranchStep",
    "ControlFlowExecutor",
    "DynamicStepGenerator",
    "parse_workflow_with_control_flow",
    # Observability
    "MetricsRegistry",
    "Counter",
    "Gauge",
    "Histogram",
    "metrics",
    "Tracer",
    "Span",
    "SpanContext",
    "tracer",
    "StructuredLogger",
    "LogContext",
    "HealthChecker",
    "HealthCheckResult",
    "HealthStatus",
    "health_checker",
    "trace",
    "timed",
    "counted",
    "llm_requests_total",
    "llm_request_duration",
    "llm_tokens_total",
    "workflow_executions_total",
    "workflow_duration",
    "workflow_steps_total",
    "agent_tasks_total",
    "active_agents",
    "tool_executions_total",
    "tool_execution_duration",
]
