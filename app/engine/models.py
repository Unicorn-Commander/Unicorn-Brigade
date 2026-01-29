"""
Data models for the Unicorn Brigade Workflow Engine

These models define the structured data flowing through the
Router → Planner → Executor → Verifier pipeline.
"""

from typing import Dict, Any, List, Optional, Literal
from enum import Enum
from pydantic import BaseModel, Field
from datetime import datetime
import uuid


class TaskIntent(str, Enum):
    """Task intent categories for routing"""
    RESEARCH = "research"
    CODING = "coding"
    SCRAPE = "scrape"
    OUTREACH = "outreach"
    REPORT = "report"
    OPS = "ops"
    QA = "qa"
    EXTRACTION = "extraction"
    UNKNOWN = "unknown"


class RiskLevel(str, Enum):
    """Risk levels for tasks"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Priority(str, Enum):
    """Task priority levels"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class WorkerType(str, Enum):
    """Available worker types"""
    RESEARCH = "ResearchWorker"
    CODE = "CodeWorker"
    EXTRACTOR = "ExtractorWorker"
    REPORT = "ReportWorker"
    OPS = "OpsWorker"
    SCRAPE = "ScrapeWorker"
    OUTREACH = "OutreachWorker"


class ToolType(str, Enum):
    """Tool types for execution"""
    SHELL = "shell"
    PYTHON = "python"
    BROWSER = "browser"
    FILESYSTEM = "filesystem"
    LLM = "llm"
    API = "api"
    DATABASE = "database"


class ApprovalState(str, Enum):
    """State of approval for a step"""
    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ExecutionStatus(str, Enum):
    """Status of step/workflow execution"""
    PENDING = "pending"
    RUNNING = "running"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"
    APPROVAL_REQUIRED = "approval_required"


# ============== Routing Models ==============

class RoutingResult(BaseModel):
    """Result from the TaskRouter"""
    intent: TaskIntent
    priority: Priority = Priority.NORMAL
    risk: RiskLevel
    needs_human_approval: bool = False
    suggested_worker: WorkerType
    suggested_model: str = "local"  # "local", "ops-center", "claude-burst"
    reason: str
    confidence: float = Field(ge=0.0, le=1.0)

    # Escalation flags
    escalate_to_cloud: bool = False
    escalation_reason: Optional[str] = None


# ============== Planning Models ==============

class WorkflowStep(BaseModel):
    """A single step in a workflow"""
    id: int
    action: str
    tool: ToolType
    worker: Optional[WorkerType] = None
    inputs: List[str] = Field(default_factory=list)
    outputs: List[str] = Field(default_factory=list)
    success_criteria: List[str] = Field(default_factory=list)
    risk: RiskLevel = RiskLevel.LOW
    approval_required: bool = False
    timeout_seconds: int = 60

    # For referencing previous step outputs
    stdin_from: Optional[str] = None  # e.g., "$step1.stdout"

    # Runtime state (not part of spec)
    status: ExecutionStatus = ExecutionStatus.PENDING
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class WorkflowPlan(BaseModel):
    """A complete workflow plan"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    objective: str
    assumptions: List[str] = Field(default_factory=list)
    steps: List[WorkflowStep]
    stop_conditions: List[str] = Field(default_factory=list)
    questions_for_user: List[str] = Field(default_factory=list)

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    estimated_duration_seconds: Optional[int] = None
    total_risk: RiskLevel = RiskLevel.LOW
    requires_approval: bool = False


# ============== Execution Models ==============

class StepResult(BaseModel):
    """Result from executing a single step"""
    step_id: int
    status: ExecutionStatus
    output: Optional[str] = None
    artifacts: List[str] = Field(default_factory=list)
    error: Optional[str] = None
    duration_seconds: float = 0.0
    tokens_used: Dict[str, int] = Field(default_factory=lambda: {"input": 0, "output": 0})

    # For blocked status
    blocker: Optional[str] = None
    needed: Optional[str] = None


class ExecutionResult(BaseModel):
    """Result from executing a complete workflow"""
    workflow_id: str
    status: ExecutionStatus
    step_results: List[StepResult] = Field(default_factory=list)
    artifacts: List[str] = Field(default_factory=list)
    total_duration_seconds: float = 0.0
    total_tokens: Dict[str, int] = Field(default_factory=lambda: {"input": 0, "output": 0})

    # Final output
    final_output: Optional[str] = None
    error: Optional[str] = None

    # Resume capability
    resume_token: Optional[str] = None
    current_step: int = 0


# ============== Verification Models ==============

class VerificationResult(BaseModel):
    """Result from the Verifier"""
    confidence: float = Field(ge=0.0, le=1.0)
    issues: List[str] = Field(default_factory=list)
    hallucination_risk: RiskLevel = RiskLevel.LOW
    security_risk: RiskLevel = RiskLevel.LOW
    retry_recommended: bool = False
    next_action: Literal["continue", "retry", "escalate_to_strong_model", "ask_user"]

    # Escalation details
    escalation_model: Optional[str] = None
    escalation_reason: Optional[str] = None


# ============== Resume Token Models ==============

class ResumeToken(BaseModel):
    """Token for resuming paused workflows"""
    token_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    workflow_id: str
    step_id: int
    state: Dict[str, Any] = Field(default_factory=dict)
    approval_state: ApprovalState = ApprovalState.PENDING
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None

    # Context for approval
    step_description: str = ""
    risk_level: RiskLevel = RiskLevel.LOW
    artifacts_pending: List[str] = Field(default_factory=list)

    # Extended checkpoint context for full resume capability
    task_id: Optional[str] = None
    task_content: Optional[str] = None
    user_id: Optional[str] = None
    model: str = "local"
    workflow_plan_json: Optional[str] = None  # Serialized WorkflowPlan
    routing_json: Optional[str] = None  # Serialized RoutingResult
    step_results_json: Optional[str] = None  # Serialized completed step results
    execution_context: Dict[str, Any] = Field(default_factory=dict)  # Accumulated context


# ============== Task Models ==============

class Task(BaseModel):
    """Incoming task to be processed"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    content: str
    context: Dict[str, Any] = Field(default_factory=dict)

    # Optional hints
    suggested_intent: Optional[TaskIntent] = None
    suggested_workflow: Optional[str] = None

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    source: str = "api"  # "api", "chat", "webhook", "scheduled"


class TaskResult(BaseModel):
    """Final result for a task"""
    model_config = {"protected_namespaces": ()}

    task_id: str
    status: ExecutionStatus
    routing: Optional[RoutingResult] = None
    plan: Optional[WorkflowPlan] = None
    execution: Optional[ExecutionResult] = None
    verification: Optional[VerificationResult] = None

    # Final output
    output: Optional[str] = None
    artifacts: List[str] = Field(default_factory=list)

    # Metrics
    total_duration_seconds: float = 0.0
    total_tokens: Dict[str, int] = Field(default_factory=lambda: {"input": 0, "output": 0})
    model_used: str = "local"
    escalated: bool = False

    # Resume
    resume_token: Optional[str] = None
