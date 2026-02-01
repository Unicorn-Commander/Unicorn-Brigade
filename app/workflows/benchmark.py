"""
Benchmarking and A/B Testing System for Hierarchical Workflows

This module provides:
- BenchmarkRun: Individual benchmark execution record
- BenchmarkComparison: A/B test comparing multiple model configurations
- BenchmarkEngine: Core engine for running benchmarks and quality scoring

Quality scoring uses LLM-as-judge pattern to evaluate:
- Accuracy (0-100)
- Completeness (0-100)
- Relevance (0-100)
- Overall weighted score
"""

import asyncio
import json
import logging
import re
import time
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from pydantic import BaseModel, Field
import uuid

from app.llm.ops_center_client import OpsCenterLLMClient
from app.workflows.schema import WorkflowDefinition, WorkflowExecution, WorkflowExecutionState
from app.workflows.engine import WorkflowEngine, get_workflow_engine
from app.workflows.templates import get_workflow, ALL_WORKFLOWS

logger = logging.getLogger(__name__)


# =============================================================================
# Model Configurations
# =============================================================================

# Pre-defined model configurations for A/B testing
MODEL_CONFIGS = {
    "cost_optimized": {
        "name": "cost_optimized",
        "description": "Minimize cost using local models wherever possible",
        "orchestrator_model": "openai/gpt-4o-mini",
        "team_lead_model": "ollama/llama3.1:8b",
        "worker_model": "ollama/llama3.2:3b",
        "enable_local_models": True,
    },
    "quality_optimized": {
        "name": "quality_optimized",
        "description": "Maximize quality using premium API models",
        "orchestrator_model": "openai/gpt-4o",
        "team_lead_model": "openai/gpt-4o-mini",
        "worker_model": "openai/gpt-4o-mini",
        "enable_local_models": False,
    },
    "balanced": {
        "name": "balanced",
        "description": "Balance cost and quality with tiered approach",
        "orchestrator_model": "openai/gpt-4o-mini",
        "team_lead_model": "openai/gpt-4o-mini",
        "worker_model": "ollama/llama3.2:3b",
        "enable_local_models": True,
    },
    "anthropic_quality": {
        "name": "anthropic_quality",
        "description": "Use Claude models for highest quality",
        "orchestrator_model": "anthropic/claude-3-sonnet",
        "team_lead_model": "anthropic/claude-3-haiku",
        "worker_model": "anthropic/claude-3-haiku",
        "enable_local_models": False,
    },
    "local_only": {
        "name": "local_only",
        "description": "Use only local models for maximum privacy and zero API cost",
        "orchestrator_model": "ollama/llama3.1:8b",
        "team_lead_model": "ollama/llama3.1:8b",
        "worker_model": "ollama/llama3.2:3b",
        "enable_local_models": True,
    },
}


# =============================================================================
# Pydantic Models
# =============================================================================

class StepMetric(BaseModel):
    """Per-step timing and cost metrics"""
    step_id: str
    step_name: str
    executor: str
    model_used: str
    execution_time_ms: int
    tokens_used: int
    estimated_cost: float
    status: str
    error: Optional[str] = None


class BenchmarkRun(BaseModel):
    """Single benchmark execution record"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    workflow_id: str
    model_config_name: str  # e.g., "cost_optimized", "quality_optimized"
    model_configuration: Dict[str, Any]  # actual model assignments (renamed from model_config)
    inputs: Dict[str, Any]
    outputs: Optional[Dict[str, Any]] = None
    execution_time_ms: int = 0
    total_cost: float = 0.0
    total_tokens: int = 0
    step_metrics: List[StepMetric] = Field(default_factory=list)
    quality_score: Optional[float] = None  # 0-100, from LLM judge
    quality_feedback: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    status: str = "pending"  # "pending", "running", "completed", "failed"
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "workflowId": self.workflow_id,
            "modelConfigName": self.model_config_name,
            "modelConfig": self.model_configuration,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "executionTimeMs": self.execution_time_ms,
            "totalCost": self.total_cost,
            "totalTokens": self.total_tokens,
            "stepMetrics": [sm.model_dump() for sm in self.step_metrics],
            "qualityScore": self.quality_score,
            "qualityFeedback": self.quality_feedback,
            "createdAt": self.created_at.isoformat(),
            "status": self.status,
            "error": self.error,
        }


class BenchmarkComparison(BaseModel):
    """A/B test comparison of multiple benchmark runs"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    workflow_id: str
    workflow_name: str = ""
    inputs: Dict[str, Any]
    runs: List[BenchmarkRun] = Field(default_factory=list)
    winner: Optional[str] = None  # run_id of best result
    comparison_metrics: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    status: str = "pending"  # "pending", "running", "completed", "failed"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "workflowId": self.workflow_id,
            "workflowName": self.workflow_name,
            "inputs": self.inputs,
            "runs": [r.to_dict() for r in self.runs],
            "winner": self.winner,
            "comparisonMetrics": self.comparison_metrics,
            "createdAt": self.created_at.isoformat(),
            "status": self.status,
        }


class LeaderboardEntry(BaseModel):
    """Leaderboard entry for best model per workflow"""
    workflow_id: str
    workflow_name: str
    model_config_name: str
    avg_quality_score: float
    avg_execution_time_ms: float
    avg_cost: float
    sample_count: int
    last_updated: datetime


# =============================================================================
# Quality Scoring Prompt (LLM-as-Judge)
# =============================================================================

QUALITY_SCORING_PROMPT = """You are an expert evaluator for AI agent workflow outputs.

Your task is to evaluate the quality of the following workflow output.

WORKFLOW TASK DESCRIPTION:
{task_description}

WORKFLOW INPUTS:
{inputs}

WORKFLOW OUTPUT:
{output}

Evaluate the output on these criteria:

1. ACCURACY (0-100): How factually correct and error-free is the output?
   - 90-100: Highly accurate, no factual errors
   - 70-89: Mostly accurate, minor errors
   - 50-69: Some accuracy issues
   - 0-49: Significant inaccuracies

2. COMPLETENESS (0-100): Does the output address all aspects of the task?
   - 90-100: Comprehensive, addresses all requirements
   - 70-89: Mostly complete, minor gaps
   - 50-69: Partial completion
   - 0-49: Significant gaps

3. RELEVANCE (0-100): How relevant is the output to the original task?
   - 90-100: Highly relevant, directly addresses the task
   - 70-89: Mostly relevant
   - 50-69: Somewhat relevant
   - 0-49: Off-topic or irrelevant

Respond with ONLY valid JSON in this exact format:
{{
  "accuracy": <number 0-100>,
  "completeness": <number 0-100>,
  "relevance": <number 0-100>,
  "overall_score": <weighted average: 40% accuracy + 35% completeness + 25% relevance>,
  "feedback": "<brief 1-2 sentence explanation of the scores>"
}}

Be objective and consistent in your scoring."""


# =============================================================================
# Benchmark Engine
# =============================================================================

class BenchmarkEngine:
    """
    Engine for benchmarking and A/B testing workflows.

    Features:
    - Run single benchmarks with specific model configurations
    - Compare multiple configurations on the same inputs
    - LLM-as-judge quality scoring
    - In-memory storage for benchmark results
    - Leaderboard tracking
    """

    def __init__(
        self,
        llm_client: Optional[OpsCenterLLMClient] = None,
        judge_model: str = "openai/gpt-4o-mini",
    ):
        self.llm_client = llm_client or OpsCenterLLMClient()
        self.judge_model = judge_model

        # In-memory storage
        self._benchmarks: Dict[str, BenchmarkComparison] = {}
        self._runs: Dict[str, BenchmarkRun] = {}
        self._leaderboard: Dict[str, List[BenchmarkRun]] = {}  # workflow_id -> runs

        logger.info("BenchmarkEngine initialized")

    # =========================================================================
    # Run Benchmarks
    # =========================================================================

    async def run_benchmark(
        self,
        workflow_id: str,
        inputs: Dict[str, Any],
        model_configs: List[str],  # config names or custom configs
        run_quality_scoring: bool = True,
    ) -> BenchmarkComparison:
        """
        Run A/B test comparing multiple model configurations.

        Args:
            workflow_id: Workflow template ID
            inputs: Inputs for the workflow
            model_configs: List of config names (e.g., ["cost_optimized", "quality_optimized"])
                          or list of custom config dicts
            run_quality_scoring: Whether to run LLM judge scoring

        Returns:
            BenchmarkComparison with all runs and comparison metrics
        """
        # Get workflow
        workflow = get_workflow(workflow_id)
        if not workflow:
            raise ValueError(f"Unknown workflow: {workflow_id}")

        # Create comparison record
        comparison = BenchmarkComparison(
            workflow_id=workflow_id,
            workflow_name=workflow.name,
            inputs=inputs,
            status="running",
        )
        self._benchmarks[comparison.id] = comparison

        try:
            # Run each configuration
            runs: List[BenchmarkRun] = []
            for config in model_configs:
                # Resolve config name to config dict
                if isinstance(config, str):
                    if config not in MODEL_CONFIGS:
                        raise ValueError(f"Unknown model config: {config}")
                    config_dict = MODEL_CONFIGS[config]
                    config_name = config
                else:
                    config_dict = config
                    config_name = config.get("name", "custom")

                # Run single benchmark
                run = await self.run_single(
                    workflow_id=workflow_id,
                    inputs=inputs,
                    model_config=config_dict,
                    model_config_name=config_name,
                    run_quality_scoring=run_quality_scoring,
                )
                runs.append(run)

            comparison.runs = runs

            # Compare runs
            comparison.comparison_metrics = self._calculate_comparison_metrics(runs)

            # Determine winner (highest quality score, or lowest cost if no quality scores)
            if any(r.quality_score is not None for r in runs):
                scored_runs = [r for r in runs if r.quality_score is not None]
                if scored_runs:
                    best_run = max(scored_runs, key=lambda r: r.quality_score)
                    comparison.winner = best_run.id
            elif runs:
                # Fallback to lowest cost
                completed_runs = [r for r in runs if r.status == "completed"]
                if completed_runs:
                    best_run = min(completed_runs, key=lambda r: r.total_cost)
                    comparison.winner = best_run.id

            comparison.status = "completed"

        except Exception as e:
            logger.error(f"Benchmark comparison failed: {e}")
            comparison.status = "failed"
            raise

        return comparison

    async def run_single(
        self,
        workflow_id: str,
        inputs: Dict[str, Any],
        model_config: Dict[str, Any],
        model_config_name: str = "custom",
        run_quality_scoring: bool = True,
    ) -> BenchmarkRun:
        """
        Run a single benchmark with a specific model configuration.

        Args:
            workflow_id: Workflow template ID
            inputs: Inputs for the workflow
            model_config: Model configuration dict
            model_config_name: Name of the configuration
            run_quality_scoring: Whether to run LLM judge scoring

        Returns:
            BenchmarkRun with results and metrics
        """
        # Get workflow
        workflow = get_workflow(workflow_id)
        if not workflow:
            raise ValueError(f"Unknown workflow: {workflow_id}")

        # Create benchmark run record
        run = BenchmarkRun(
            workflow_id=workflow_id,
            model_config_name=model_config_name,
            model_configuration=model_config,
            inputs=inputs,
            status="running",
        )
        self._runs[run.id] = run

        try:
            # Create workflow engine with the specified model config
            engine = WorkflowEngine(
                llm_client=self.llm_client,
                orchestrator_model=model_config.get("orchestrator_model", "openai/gpt-4o-mini"),
                enable_local_models=model_config.get("enable_local_models", True),
            )

            # Track step metrics
            step_metrics: List[StepMetric] = []

            async def on_step_complete(step, step_exec):
                """Callback to capture step metrics"""
                step_metrics.append(StepMetric(
                    step_id=step.id,
                    step_name=step.name,
                    executor=step.executor,
                    model_used=step_exec.model_used,
                    execution_time_ms=int((step_exec.completed_at - step_exec.started_at).total_seconds() * 1000) if step_exec.completed_at and step_exec.started_at else 0,
                    tokens_used=step_exec.tokens_used,
                    estimated_cost=step_exec.estimated_cost,
                    status=step_exec.state.value,
                    error=step_exec.error,
                ))

            # Execute workflow
            start_time = time.time()
            execution = await engine.execute_workflow(
                workflow=workflow,
                inputs=inputs,
                on_step_complete=on_step_complete,
            )
            end_time = time.time()

            # Update run with results
            run.execution_time_ms = int((end_time - start_time) * 1000)
            run.outputs = execution.outputs
            run.total_tokens = execution.total_tokens
            run.total_cost = execution.total_cost
            run.step_metrics = step_metrics
            run.status = "completed" if execution.state == WorkflowExecutionState.COMPLETED else "failed"
            run.error = execution.error

            # Run quality scoring if enabled and execution was successful
            if run_quality_scoring and run.status == "completed" and run.outputs:
                try:
                    quality_score, feedback = await self.score_output_quality(
                        task_description=workflow.description,
                        inputs=inputs,
                        output=run.outputs,
                    )
                    run.quality_score = quality_score
                    run.quality_feedback = feedback
                except Exception as e:
                    logger.warning(f"Quality scoring failed: {e}")

            # Add to leaderboard tracking
            if workflow_id not in self._leaderboard:
                self._leaderboard[workflow_id] = []
            self._leaderboard[workflow_id].append(run)

        except Exception as e:
            logger.error(f"Benchmark run failed: {e}")
            run.status = "failed"
            run.error = str(e)

        return run

    # =========================================================================
    # Quality Scoring (LLM-as-Judge)
    # =========================================================================

    async def score_output_quality(
        self,
        task_description: str,
        inputs: Dict[str, Any],
        output: Dict[str, Any],
    ) -> Tuple[float, str]:
        """
        Score output quality using LLM-as-judge pattern.

        Args:
            task_description: Description of the workflow task
            inputs: Original inputs
            output: Workflow outputs to evaluate

        Returns:
            Tuple of (overall_score, feedback_text)
        """
        # Format the prompt
        prompt = QUALITY_SCORING_PROMPT.format(
            task_description=task_description,
            inputs=json.dumps(inputs, indent=2),
            output=json.dumps(output, indent=2),
        )

        # Call LLM judge
        response = await self.llm_client.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            model=self.judge_model,
            temperature=0.1,  # Low temperature for consistent scoring
            max_tokens=500,
        )

        # Parse response
        content = self._extract_content(response)
        scores = self._parse_scores(content)

        overall_score = scores.get("overall_score", 0)
        feedback = scores.get("feedback", "Unable to parse quality feedback")

        return overall_score, feedback

    def _extract_content(self, response: Dict[str, Any]) -> str:
        """Extract content from LLM response"""
        if "choices" in response and len(response["choices"]) > 0:
            choice = response["choices"][0]
            if "message" in choice and "content" in choice["message"]:
                return choice["message"]["content"] or ""
        if "content" in response:
            return response["content"] or ""
        return ""

    def _parse_scores(self, text: str) -> Dict[str, Any]:
        """Parse JSON scores from LLM response"""
        # Try to find JSON in code block
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # Try to find raw JSON object
        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        # Return default scores
        return {"overall_score": 50, "feedback": "Unable to parse scores"}

    # =========================================================================
    # Comparison Metrics
    # =========================================================================

    def _calculate_comparison_metrics(self, runs: List[BenchmarkRun]) -> Dict[str, Any]:
        """Calculate comparison metrics across runs"""
        metrics = {
            "run_count": len(runs),
            "completed_count": sum(1 for r in runs if r.status == "completed"),
            "failed_count": sum(1 for r in runs if r.status == "failed"),
        }

        completed_runs = [r for r in runs if r.status == "completed"]
        if not completed_runs:
            return metrics

        # Time comparison
        times = [r.execution_time_ms for r in completed_runs]
        metrics["time_min_ms"] = min(times)
        metrics["time_max_ms"] = max(times)
        metrics["time_avg_ms"] = sum(times) / len(times)
        metrics["time_diff_ms"] = max(times) - min(times)
        metrics["time_diff_pct"] = round((max(times) - min(times)) / min(times) * 100, 2) if min(times) > 0 else 0

        # Cost comparison
        costs = [r.total_cost for r in completed_runs]
        metrics["cost_min"] = min(costs)
        metrics["cost_max"] = max(costs)
        metrics["cost_avg"] = sum(costs) / len(costs)
        metrics["cost_diff"] = max(costs) - min(costs)
        metrics["cost_diff_pct"] = round((max(costs) - min(costs)) / min(costs) * 100, 2) if min(costs) > 0 else 0

        # Token comparison
        tokens = [r.total_tokens for r in completed_runs]
        metrics["tokens_min"] = min(tokens)
        metrics["tokens_max"] = max(tokens)
        metrics["tokens_avg"] = sum(tokens) / len(tokens)

        # Quality comparison
        scored_runs = [r for r in completed_runs if r.quality_score is not None]
        if scored_runs:
            scores = [r.quality_score for r in scored_runs]
            metrics["quality_min"] = min(scores)
            metrics["quality_max"] = max(scores)
            metrics["quality_avg"] = sum(scores) / len(scores)
            metrics["quality_diff"] = max(scores) - min(scores)

        # Per-config summary
        config_summary = {}
        for run in completed_runs:
            config_summary[run.model_config_name] = {
                "run_id": run.id,
                "time_ms": run.execution_time_ms,
                "cost": run.total_cost,
                "tokens": run.total_tokens,
                "quality_score": run.quality_score,
            }
        metrics["config_summary"] = config_summary

        return metrics

    def compare_runs(self, runs: List[BenchmarkRun]) -> BenchmarkComparison:
        """
        Compare a list of benchmark runs.

        Args:
            runs: List of BenchmarkRun objects to compare

        Returns:
            BenchmarkComparison with metrics
        """
        if not runs:
            raise ValueError("No runs to compare")

        comparison = BenchmarkComparison(
            workflow_id=runs[0].workflow_id,
            workflow_name="",
            inputs=runs[0].inputs,
            runs=runs,
            status="completed",
        )

        # Get workflow name
        workflow = get_workflow(runs[0].workflow_id)
        if workflow:
            comparison.workflow_name = workflow.name

        # Calculate comparison metrics
        comparison.comparison_metrics = self._calculate_comparison_metrics(runs)

        # Determine winner
        scored_runs = [r for r in runs if r.quality_score is not None]
        if scored_runs:
            best_run = max(scored_runs, key=lambda r: r.quality_score)
            comparison.winner = best_run.id
        elif runs:
            completed_runs = [r for r in runs if r.status == "completed"]
            if completed_runs:
                best_run = min(completed_runs, key=lambda r: r.total_cost)
                comparison.winner = best_run.id

        # Store comparison
        self._benchmarks[comparison.id] = comparison

        return comparison

    # =========================================================================
    # Storage and Retrieval
    # =========================================================================

    def list_benchmarks(
        self,
        workflow_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[BenchmarkComparison]:
        """
        List benchmark comparisons.

        Args:
            workflow_id: Optional filter by workflow ID
            limit: Maximum results

        Returns:
            List of BenchmarkComparison objects
        """
        comparisons = list(self._benchmarks.values())

        if workflow_id:
            comparisons = [c for c in comparisons if c.workflow_id == workflow_id]

        # Sort by created_at descending
        comparisons.sort(key=lambda c: c.created_at, reverse=True)

        return comparisons[:limit]

    def get_benchmark(self, benchmark_id: str) -> Optional[BenchmarkComparison]:
        """Get benchmark comparison by ID"""
        return self._benchmarks.get(benchmark_id)

    def get_run(self, run_id: str) -> Optional[BenchmarkRun]:
        """Get individual run by ID"""
        return self._runs.get(run_id)

    def list_runs(
        self,
        workflow_id: Optional[str] = None,
        model_config_name: Optional[str] = None,
        limit: int = 100,
    ) -> List[BenchmarkRun]:
        """
        List benchmark runs.

        Args:
            workflow_id: Optional filter by workflow ID
            model_config_name: Optional filter by model config
            limit: Maximum results

        Returns:
            List of BenchmarkRun objects
        """
        runs = list(self._runs.values())

        if workflow_id:
            runs = [r for r in runs if r.workflow_id == workflow_id]
        if model_config_name:
            runs = [r for r in runs if r.model_config_name == model_config_name]

        # Sort by created_at descending
        runs.sort(key=lambda r: r.created_at, reverse=True)

        return runs[:limit]

    # =========================================================================
    # Leaderboard
    # =========================================================================

    def get_leaderboard(
        self,
        workflow_id: Optional[str] = None,
        min_samples: int = 1,
    ) -> List[LeaderboardEntry]:
        """
        Get leaderboard of best model configurations per workflow.

        Args:
            workflow_id: Optional filter by workflow ID
            min_samples: Minimum sample count for inclusion

        Returns:
            List of LeaderboardEntry objects sorted by quality score
        """
        entries = []

        # Filter workflows
        if workflow_id:
            workflow_ids = [workflow_id] if workflow_id in self._leaderboard else []
        else:
            workflow_ids = list(self._leaderboard.keys())

        for wf_id in workflow_ids:
            runs = self._leaderboard.get(wf_id, [])
            if not runs:
                continue

            # Group by model config
            config_runs: Dict[str, List[BenchmarkRun]] = {}
            for run in runs:
                if run.status != "completed":
                    continue
                if run.model_config_name not in config_runs:
                    config_runs[run.model_config_name] = []
                config_runs[run.model_config_name].append(run)

            # Calculate averages per config
            for config_name, config_runs_list in config_runs.items():
                if len(config_runs_list) < min_samples:
                    continue

                scored_runs = [r for r in config_runs_list if r.quality_score is not None]
                if not scored_runs:
                    continue

                workflow = get_workflow(wf_id)

                entry = LeaderboardEntry(
                    workflow_id=wf_id,
                    workflow_name=workflow.name if workflow else wf_id,
                    model_config_name=config_name,
                    avg_quality_score=sum(r.quality_score for r in scored_runs) / len(scored_runs),
                    avg_execution_time_ms=sum(r.execution_time_ms for r in config_runs_list) / len(config_runs_list),
                    avg_cost=sum(r.total_cost for r in config_runs_list) / len(config_runs_list),
                    sample_count=len(config_runs_list),
                    last_updated=max(r.created_at for r in config_runs_list),
                )
                entries.append(entry)

        # Sort by quality score descending
        entries.sort(key=lambda e: e.avg_quality_score, reverse=True)

        return entries

    def get_model_configs(self) -> Dict[str, Dict[str, Any]]:
        """Get available model configurations"""
        return MODEL_CONFIGS.copy()


# =============================================================================
# Global Instance
# =============================================================================

_benchmark_engine: Optional[BenchmarkEngine] = None


def get_benchmark_engine() -> BenchmarkEngine:
    """Get or create the global benchmark engine"""
    global _benchmark_engine
    if _benchmark_engine is None:
        _benchmark_engine = BenchmarkEngine()
    return _benchmark_engine


def init_benchmark_engine(
    llm_client: OpsCenterLLMClient,
    judge_model: str = "openai/gpt-4o-mini",
) -> BenchmarkEngine:
    """Initialize the global benchmark engine"""
    global _benchmark_engine
    _benchmark_engine = BenchmarkEngine(
        llm_client=llm_client,
        judge_model=judge_model,
    )
    return _benchmark_engine
