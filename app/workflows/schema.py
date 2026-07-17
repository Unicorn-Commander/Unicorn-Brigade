"""
Workflow Schema - 3-Tier Hierarchical Agent System

Architecture:
┌─────────────────────────────────────────────────────────────────┐
│              THE GENERAL (Orchestrator)                         │
│              Model: GPT-4o / Claude (complex reasoning)         │
└─────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌───────────────┐     ┌───────────────┐     ┌───────────────┐
│  TEAM LEAD    │     │  TEAM LEAD    │     │  TEAM LEAD    │
│  Model: 7B    │     │  Model: 7B    │     │  Model: 7B    │
│  (domain exp) │     │  (domain exp) │     │  (domain exp) │
└───────────────┘     └───────────────┘     └───────────────┘
        │                     │                     │
   ┌────┴────┐           ┌────┴────┐           ┌────┴────┐
   ▼    ▼    ▼           ▼    ▼    ▼           ▼    ▼    ▼
┌─────┐┌─────┐┌─────┐ ┌─────┐┌─────┐┌─────┐ ┌─────┐┌─────┐┌─────┐
│Work-││Work-││Work-│ │Work-││Work-││Work-│ │Work-││Work-││Work-│
│er 1 ││er 2 ││er 3 │ │er 1 ││er 2 ││er 3 │ │er 1 ││er 2 ││er 3 │
│ 1-3B││ 1-3B││ 1-3B│ │ 1-3B││ 1-3B││ 1-3B│ │ 1-3B││ 1-3B││ 1-3B│
└─────┘└─────┘└─────┘ └─────┘└─────┘└─────┘ └─────┘└─────┘└─────┘
"""

from typing import Dict, Any, List, Optional, Union, Literal
from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime
import uuid


class ModelTier(str, Enum):
    """Model tiers for different agent levels"""
    ORCHESTRATOR = "orchestrator"  # GPT-4o, Claude Sonnet - complex reasoning
    TEAM_LEAD = "team_lead"        # 7B-14B local - domain understanding
    WORKER = "worker"              # 1B-3B local - narrow tasks


class WorkerSpec(BaseModel):
    """
    Ultra-narrow task executor optimized for small local models.

    Workers have:
    - Single, well-defined purpose
    - Strict input/output schema
    - No delegation capability
    - Optimized prompt for small models
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str
    description: str

    # Model config - optimized for local
    model: str = "ollama/llama3.2:3b"  # Default to small local model
    model_tier: ModelTier = ModelTier.WORKER
    temperature: float = 0.1  # Low temp for consistency
    max_tokens: int = 500  # Short outputs

    # Task definition - VERY specific
    task_prompt: str  # The single task this worker does
    input_schema: Dict[str, Any] = Field(default_factory=dict)  # Expected input format
    output_schema: Dict[str, Any] = Field(default_factory=dict)  # Expected output format

    # Optional tool (usually just one)
    tool: Optional[str] = None  # e.g., "calculator", "web_search"

    # Examples for few-shot (critical for small models)
    examples: List[Dict[str, Any]] = Field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "model": self.model,
            "modelTier": self.model_tier.value,
            "temperature": self.temperature,
            "maxTokens": self.max_tokens,
            "taskPrompt": self.task_prompt,
            "inputSchema": self.input_schema,
            "outputSchema": self.output_schema,
            "tool": self.tool,
            "examples": self.examples,
        }


class TeamLeadSpec(BaseModel):
    """
    Domain expert that delegates to specialized workers.

    Team Leads:
    - Understand domain context
    - Decompose tasks for workers
    - Aggregate worker results
    - Make domain-specific decisions
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str
    domain: str  # research, finance, content, sales, devops
    description: str

    # Model config - mid-tier local
    model: str = "ollama/llama3.1:8b"  # 7B-14B for domain reasoning
    model_tier: ModelTier = ModelTier.TEAM_LEAD
    temperature: float = 0.3
    max_tokens: int = 1500

    # System prompt for domain expertise
    system_prompt: str

    # Workers under this team lead
    workers: List[WorkerSpec] = Field(default_factory=list)

    # Delegation rules
    delegation_prompt: str = ""  # How to decide which worker to use

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "domain": self.domain,
            "description": self.description,
            "model": self.model,
            "modelTier": self.model_tier.value,
            "temperature": self.temperature,
            "maxTokens": self.max_tokens,
            "systemPrompt": self.system_prompt,
            "workers": [w.to_dict() for w in self.workers],
            "delegationPrompt": self.delegation_prompt,
        }


class CheckpointType(str, Enum):
    """Types of workflow checkpoints"""
    HUMAN_APPROVAL = "human_approval"  # Requires human to approve
    HUMAN_INPUT = "human_input"        # Requires human input
    REVIEW = "review"                  # Optional review point
    GATE = "gate"                      # Conditional proceed/fail


class WorkflowStep(BaseModel):
    """A single step in a workflow"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str
    description: str

    # Who executes this step
    executor: str  # team_lead_id or "orchestrator"

    # Input mapping from previous steps
    inputs: Dict[str, str] = Field(default_factory=dict)  # {"local_name": "step_id.output_name"}

    # Output keys this step produces
    outputs: List[str] = Field(default_factory=list)

    # Conditional execution
    condition: Optional[str] = None  # Expression like "step1.success == true"

    # Retry config
    max_retries: int = 2
    retry_delay_seconds: int = 5

    # Timeout
    timeout_seconds: int = 120

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "executor": self.executor,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "condition": self.condition,
            "maxRetries": self.max_retries,
            "retryDelaySeconds": self.retry_delay_seconds,
            "timeoutSeconds": self.timeout_seconds,
        }


class Checkpoint(BaseModel):
    """Human-in-the-loop checkpoint"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    # `name` and `after_step` are optional with safe defaults so that
    # workflow definitions can construct checkpoints inline (where the
    # parent step provides ordering context) or at the workflow level
    # (where after_step is implicitly "after the last step"). The engine
    # only consults `after_step` to attach top-level checkpoints to
    # specific steps — when it's empty, the checkpoint simply never
    # matches mid-workflow, which is the right behavior for end-of-flow
    # approvals.
    name: str = ""
    type: CheckpointType
    after_step: str = ""  # Step ID after which this checkpoint occurs

    # For HUMAN_INPUT type
    prompt: str = ""  # Question to ask human
    options: List[str] = Field(default_factory=list)  # Optional predefined choices

    # For GATE type
    gate_condition: str = ""  # Expression that must be true to proceed
    failure_action: str = "abort"  # abort, retry, skip

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type.value,
            "afterStep": self.after_step,
            "prompt": self.prompt,
            "options": self.options,
            "gateCondition": self.gate_condition,
            "failureAction": self.failure_action,
        }


class WorkflowDefinition(BaseModel):
    """
    Complete workflow definition with 3-tier hierarchy.

    Example structure:
    - Orchestrator: The General (GPT-4o) - strategic coordination
    - Team Leads: Research Lead, Finance Lead (7B) - domain delegation
    - Workers: Web Searcher, Doc Parser, Ratio Calculator (1-3B) - narrow tasks
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str
    description: str
    version: str = "1.0.0"

    # Orchestrator config
    orchestrator_model: str = "openai/gpt-4o"
    orchestrator_prompt: str = ""  # Strategic coordination prompt

    # Team leads for this workflow
    team_leads: List[TeamLeadSpec] = Field(default_factory=list)

    # Workflow steps (executed in order unless conditions change flow)
    steps: List[WorkflowStep] = Field(default_factory=list)

    # Human checkpoints
    checkpoints: List[Checkpoint] = Field(default_factory=list)

    # Global inputs required to start workflow
    required_inputs: List[str] = Field(default_factory=list)

    # Final outputs produced
    final_outputs: List[str] = Field(default_factory=list)

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    tags: List[str] = Field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "orchestratorModel": self.orchestrator_model,
            "orchestratorPrompt": self.orchestrator_prompt,
            "teamLeads": [tl.to_dict() for tl in self.team_leads],
            "steps": [s.to_dict() for s in self.steps],
            "checkpoints": [c.to_dict() for c in self.checkpoints],
            "requiredInputs": self.required_inputs,
            "finalOutputs": self.final_outputs,
            "createdAt": self.created_at.isoformat(),
            "updatedAt": self.updated_at.isoformat(),
            "tags": self.tags,
        }


class WorkflowExecutionState(str, Enum):
    """State of a workflow execution"""
    PENDING = "pending"
    RUNNING = "running"
    WAITING_CHECKPOINT = "waiting_checkpoint"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StepExecutionState(str, Enum):
    """State of a step execution"""
    PENDING = "pending"
    RUNNING = "running"
    DELEGATING = "delegating"  # Team lead is delegating to workers
    WAITING_WORKERS = "waiting_workers"
    AGGREGATING = "aggregating"  # Team lead aggregating worker results
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class StepExecution(BaseModel):
    """Tracks execution of a single step"""
    step_id: str
    state: StepExecutionState = StepExecutionState.PENDING

    # Timing
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # Execution details
    executor_id: str = ""  # Which team lead/worker ran this
    model_used: str = ""

    # Results
    inputs_received: Dict[str, Any] = Field(default_factory=dict)
    outputs: Dict[str, Any] = Field(default_factory=dict)

    # Worker delegations (if team lead)
    worker_calls: List[Dict[str, Any]] = Field(default_factory=list)

    # Errors
    error: Optional[str] = None
    retries: int = 0

    # Token usage for cost tracking
    tokens_used: int = 0
    estimated_cost: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stepId": self.step_id,
            "state": self.state.value,
            "startedAt": self.started_at.isoformat() if self.started_at else None,
            "completedAt": self.completed_at.isoformat() if self.completed_at else None,
            "executorId": self.executor_id,
            "modelUsed": self.model_used,
            "inputsReceived": self.inputs_received,
            "outputs": self.outputs,
            "workerCalls": self.worker_calls,
            "error": self.error,
            "retries": self.retries,
            "tokensUsed": self.tokens_used,
            "estimatedCost": self.estimated_cost,
        }


class WorkflowExecution(BaseModel):
    """Tracks a complete workflow execution"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    workflow_id: str
    workflow_name: str

    # Owning organization (tenancy). Stamped at creation from the bound request
    # org (event_bus.current_org_id_var) so cache-backed reads can be org-scoped:
    # a non-admin caller only ever sees executions whose org_id equals their own.
    # None for executions created with no bound org (system/unbound) — those are
    # visible only to admins, never leaked to a tenant.
    org_id: Optional[str] = None

    # State
    state: WorkflowExecutionState = WorkflowExecutionState.PENDING
    current_step: Optional[str] = None

    # Timing
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # Inputs/Outputs
    inputs: Dict[str, Any] = Field(default_factory=dict)
    outputs: Dict[str, Any] = Field(default_factory=dict)

    # Step tracking
    step_executions: Dict[str, StepExecution] = Field(default_factory=dict)

    # Checkpoint state
    pending_checkpoint: Optional[str] = None  # Checkpoint ID waiting for input
    checkpoint_responses: Dict[str, Any] = Field(default_factory=dict)

    # Error handling
    error: Optional[str] = None

    # Aggregated stats
    total_tokens: int = 0
    total_cost: float = 0.0

    # Mission tracking (for orchestration UI)
    mission_id: Optional[str] = None

    # Model configuration used for this execution
    model_config_used: Dict[str, Any] = Field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "workflowId": self.workflow_id,
            "workflowName": self.workflow_name,
            "state": self.state.value,
            "currentStep": self.current_step,
            "startedAt": self.started_at.isoformat() if self.started_at else None,
            "completedAt": self.completed_at.isoformat() if self.completed_at else None,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "stepExecutions": {k: v.to_dict() for k, v in self.step_executions.items()},
            "pendingCheckpoint": self.pending_checkpoint,
            "checkpointResponses": self.checkpoint_responses,
            "error": self.error,
            "totalTokens": self.total_tokens,
            "totalCost": self.total_cost,
            "missionId": self.mission_id,
            "modelConfigUsed": self.model_config_used,
        }
