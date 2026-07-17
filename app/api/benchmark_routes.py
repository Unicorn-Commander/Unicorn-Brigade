"""
Benchmark API Routes

Provides endpoints for A/B testing and benchmarking hierarchical workflows:
- Compare multiple model configurations
- Run single benchmarks
- View benchmark history
- Access leaderboard data
"""

from fastapi import APIRouter, HTTPException, status, Query, BackgroundTasks, Depends
from pydantic import BaseModel, Field
from typing import Annotated, Optional, Dict, Any, List, Union
from datetime import datetime
import logging

from app.workflows.benchmark import (
    BenchmarkEngine,
    BenchmarkRun,
    BenchmarkComparison,
    LeaderboardEntry,
    MODEL_CONFIGS,
    get_benchmark_engine,
)
from app.workflows.templates import get_workflow, list_workflows, ALL_WORKFLOWS
from app.auth.middleware import require_operator, AuthUser

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/benchmarks", tags=["benchmarks"])


# =============================================================================
# Request/Response Models
# =============================================================================

class ModelConfigInput(BaseModel):
    """Custom model configuration input"""
    name: str = Field(..., description="Configuration name")
    description: str = Field("", description="Configuration description")
    orchestrator_model: str = Field("openai/gpt-4o-mini", description="Orchestrator model")
    team_lead_model: str = Field("ollama/llama3.1:8b", description="Team lead model")
    worker_model: str = Field("ollama/llama3.2:3b", description="Worker model")
    enable_local_models: bool = Field(True, description="Enable local model execution")


class BenchmarkCompareRequest(BaseModel):
    """Request to run A/B benchmark comparison"""
    workflow_id: str = Field(..., description="Workflow template ID")
    inputs: Dict[str, Any] = Field(..., description="Workflow inputs")
    model_configs: List[Union[str, ModelConfigInput]] = Field(
        ...,
        description="List of model config names (e.g., 'cost_optimized') or custom configs"
    )
    run_quality_scoring: bool = Field(True, description="Run LLM-as-judge quality scoring")


class BenchmarkRunRequest(BaseModel):
    """Request to run single benchmark"""
    workflow_id: str = Field(..., description="Workflow template ID")
    inputs: Dict[str, Any] = Field(..., description="Workflow inputs")
    config: Optional[Union[str, ModelConfigInput]] = Field(
        None,
        description="Model config name or custom config (defaults to 'balanced')"
    )
    run_quality_scoring: bool = Field(True, description="Run LLM-as-judge quality scoring")


class BenchmarkRunResponse(BaseModel):
    """Response for benchmark run"""
    id: str
    workflow_id: str
    model_config_name: str
    status: str
    execution_time_ms: int
    total_cost: float
    total_tokens: int
    quality_score: Optional[float]
    quality_feedback: Optional[str]
    created_at: datetime


class BenchmarkComparisonResponse(BaseModel):
    """Response for benchmark comparison"""
    id: str
    workflow_id: str
    workflow_name: str
    status: str
    winner: Optional[str]
    run_count: int
    comparison_metrics: Dict[str, Any]
    created_at: datetime


class LeaderboardResponse(BaseModel):
    """Response for leaderboard entry"""
    workflow_id: str
    workflow_name: str
    model_config_name: str
    avg_quality_score: float
    avg_execution_time_ms: float
    avg_cost: float
    sample_count: int
    last_updated: datetime


class ModelConfigResponse(BaseModel):
    """Response for model configuration"""
    name: str
    description: str
    orchestrator_model: str
    team_lead_model: str
    worker_model: str
    enable_local_models: bool


# =============================================================================
# Routes
# =============================================================================

@router.post("/compare", response_model=BenchmarkComparisonResponse)
async def run_benchmark_comparison(
    request: BenchmarkCompareRequest,
    background_tasks: BackgroundTasks,
    user: Annotated[AuthUser, Depends(require_operator)] = None,
):
    """
    Run A/B test comparing multiple model configurations.

    This executes the same workflow with different model configurations
    and compares the results for cost, speed, and quality.

    Example:
    ```
    POST /api/v1/benchmarks/compare
    {
      "workflow_id": "investment-due-diligence",
      "inputs": {
        "company_name": "Acme Corp",
        "investment_thesis": "Growth potential in AI sector",
        "investment_amount": 1000000
      },
      "model_configs": ["cost_optimized", "quality_optimized"]
    }
    ```
    """
    # Validate workflow exists
    workflow = get_workflow(request.workflow_id)
    if not workflow:
        available = list(ALL_WORKFLOWS.keys())
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow not found: {request.workflow_id}. Available: {available}"
        )

    # Validate model configs
    resolved_configs: List[str] = []
    for config in request.model_configs:
        if isinstance(config, str):
            if config not in MODEL_CONFIGS:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Unknown model config: {config}. Available: {list(MODEL_CONFIGS.keys())}"
                )
            resolved_configs.append(config)
        else:
            # Custom config - validate and add
            resolved_configs.append(config.model_dump())

    try:
        engine = get_benchmark_engine()
        comparison = await engine.run_benchmark(
            workflow_id=request.workflow_id,
            inputs=request.inputs,
            model_configs=resolved_configs,
            run_quality_scoring=request.run_quality_scoring,
        )

        return BenchmarkComparisonResponse(
            id=comparison.id,
            workflow_id=comparison.workflow_id,
            workflow_name=comparison.workflow_name,
            status=comparison.status,
            winner=comparison.winner,
            run_count=len(comparison.runs),
            comparison_metrics=comparison.comparison_metrics,
            created_at=comparison.created_at,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Benchmark comparison failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Benchmark comparison failed: {str(e)}"
        )


@router.post("/run", response_model=BenchmarkRunResponse)
async def run_single_benchmark(
    request: BenchmarkRunRequest,
    user: Annotated[AuthUser, Depends(require_operator)] = None,
):
    """
    Run a single benchmark with a specific model configuration.

    Example:
    ```
    POST /api/v1/benchmarks/run
    {
      "workflow_id": "content-production",
      "inputs": {
        "topic": "AI Agents in Enterprise",
        "target_keywords": ["AI agents", "enterprise automation"],
        "target_audience": "CTOs and Tech Leaders",
        "content_goals": "Educate and generate leads"
      },
      "config": "cost_optimized"
    }
    ```
    """
    # Validate workflow exists
    workflow = get_workflow(request.workflow_id)
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow not found: {request.workflow_id}"
        )

    # Resolve model config
    if request.config is None:
        config = MODEL_CONFIGS["balanced"]
        config_name = "balanced"
    elif isinstance(request.config, str):
        if request.config not in MODEL_CONFIGS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown model config: {request.config}"
            )
        config = MODEL_CONFIGS[request.config]
        config_name = request.config
    else:
        config = request.config.model_dump()
        config_name = request.config.name

    try:
        engine = get_benchmark_engine()
        run = await engine.run_single(
            workflow_id=request.workflow_id,
            inputs=request.inputs,
            model_config=config,
            model_config_name=config_name,
            run_quality_scoring=request.run_quality_scoring,
        )

        return BenchmarkRunResponse(
            id=run.id,
            workflow_id=run.workflow_id,
            model_config_name=run.model_config_name,
            status=run.status,
            execution_time_ms=run.execution_time_ms,
            total_cost=run.total_cost,
            total_tokens=run.total_tokens,
            quality_score=run.quality_score,
            quality_feedback=run.quality_feedback,
            created_at=run.created_at,
        )

    except Exception as e:
        logger.error(f"Benchmark run failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Benchmark run failed: {str(e)}"
        )


@router.get("", response_model=List[BenchmarkComparisonResponse])
async def list_benchmarks(
    workflow_id: Optional[str] = Query(None, description="Filter by workflow ID"),
    limit: int = Query(50, ge=1, le=200, description="Maximum results"),
):
    """
    List benchmark comparisons.

    Can filter by workflow ID.
    """
    engine = get_benchmark_engine()
    comparisons = engine.list_benchmarks(workflow_id=workflow_id, limit=limit)

    return [
        BenchmarkComparisonResponse(
            id=c.id,
            workflow_id=c.workflow_id,
            workflow_name=c.workflow_name,
            status=c.status,
            winner=c.winner,
            run_count=len(c.runs),
            comparison_metrics=c.comparison_metrics,
            created_at=c.created_at,
        )
        for c in comparisons
    ]


@router.get("/runs", response_model=List[BenchmarkRunResponse])
async def list_benchmark_runs(
    workflow_id: Optional[str] = Query(None, description="Filter by workflow ID"),
    model_config: Optional[str] = Query(None, description="Filter by model config name"),
    limit: int = Query(100, ge=1, le=500, description="Maximum results"),
):
    """
    List individual benchmark runs.

    Can filter by workflow ID and/or model configuration.
    """
    engine = get_benchmark_engine()
    runs = engine.list_runs(
        workflow_id=workflow_id,
        model_config_name=model_config,
        limit=limit,
    )

    return [
        BenchmarkRunResponse(
            id=r.id,
            workflow_id=r.workflow_id,
            model_config_name=r.model_config_name,
            status=r.status,
            execution_time_ms=r.execution_time_ms,
            total_cost=r.total_cost,
            total_tokens=r.total_tokens,
            quality_score=r.quality_score,
            quality_feedback=r.quality_feedback,
            created_at=r.created_at,
        )
        for r in runs
    ]


@router.get("/{benchmark_id}")
async def get_benchmark_details(benchmark_id: str):
    """
    Get detailed benchmark comparison by ID.

    Returns full comparison data including all runs and step-level metrics.
    """
    engine = get_benchmark_engine()
    comparison = engine.get_benchmark(benchmark_id)

    if not comparison:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Benchmark not found: {benchmark_id}"
        )

    return comparison.to_dict()


@router.get("/runs/{run_id}")
async def get_run_details(run_id: str):
    """
    Get detailed benchmark run by ID.

    Returns full run data including step-level metrics.
    """
    engine = get_benchmark_engine()
    run = engine.get_run(run_id)

    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run not found: {run_id}"
        )

    return run.to_dict()


@router.get("/leaderboard", response_model=List[LeaderboardResponse])
async def get_leaderboard(
    workflow_id: Optional[str] = Query(None, description="Filter by workflow ID"),
    min_samples: int = Query(1, ge=1, description="Minimum sample count for inclusion"),
):
    """
    Get leaderboard of best model configurations per workflow.

    Shows the best-performing model configurations ranked by quality score,
    with average metrics across all runs.
    """
    engine = get_benchmark_engine()
    entries = engine.get_leaderboard(
        workflow_id=workflow_id,
        min_samples=min_samples,
    )

    return [
        LeaderboardResponse(
            workflow_id=e.workflow_id,
            workflow_name=e.workflow_name,
            model_config_name=e.model_config_name,
            avg_quality_score=e.avg_quality_score,
            avg_execution_time_ms=e.avg_execution_time_ms,
            avg_cost=e.avg_cost,
            sample_count=e.sample_count,
            last_updated=e.last_updated,
        )
        for e in entries
    ]


@router.get("/configs", response_model=Dict[str, ModelConfigResponse])
async def get_model_configs():
    """
    Get available pre-defined model configurations.

    These can be used by name in benchmark requests.
    """
    return {
        name: ModelConfigResponse(
            name=name,
            description=config.get("description", ""),
            orchestrator_model=config["orchestrator_model"],
            team_lead_model=config["team_lead_model"],
            worker_model=config["worker_model"],
            enable_local_models=config["enable_local_models"],
        )
        for name, config in MODEL_CONFIGS.items()
    }


@router.get("/workflows")
async def get_available_workflows():
    """
    Get available workflows that can be benchmarked.
    """
    workflows = list_workflows()
    return {
        "workflows": workflows,
        "count": len(workflows),
    }


@router.post("/score-quality")
async def score_output_quality(
    task_description: str = Query(..., description="Task description"),
    inputs: Dict[str, Any] = None,
    output: Dict[str, Any] = None,
    user: Annotated[AuthUser, Depends(require_operator)] = None,
):
    """
    Manually score output quality using LLM-as-judge.

    Useful for testing the quality scoring system.
    """
    if inputs is None:
        inputs = {}
    if output is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Output is required"
        )

    try:
        engine = get_benchmark_engine()
        score, feedback = await engine.score_output_quality(
            task_description=task_description,
            inputs=inputs,
            output=output,
        )

        return {
            "quality_score": score,
            "feedback": feedback,
        }

    except Exception as e:
        logger.error(f"Quality scoring failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Quality scoring failed: {str(e)}"
        )


@router.get("/health")
async def benchmark_health():
    """
    Check benchmark subsystem health.
    """
    try:
        engine = get_benchmark_engine()
        return {
            "status": "healthy",
            "benchmark_count": len(engine._benchmarks),
            "run_count": len(engine._runs),
            "workflow_count": len(engine._leaderboard),
            "available_configs": list(MODEL_CONFIGS.keys()),
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "message": "Benchmark subsystem unhealthy",
                "error": str(e),
            },
        )
