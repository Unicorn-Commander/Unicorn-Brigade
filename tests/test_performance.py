"""
Performance Benchmark Suite for Unicorn Brigade

This module provides comprehensive performance benchmarks for:
- Tool resolution performance
- Agent loading performance
- Workflow step execution baseline
- Model config resolution
- Memory operations
- API response times

Each benchmark includes:
- Mean time (ms)
- P95 time (ms)
- Operations per second
- Pass/fail against target

Usage:
    pytest tests/test_performance.py -q  # Run deterministic correctness checks
    BRIGADE_BENCHMARK=1 pytest tests/test_performance.py -v -m perf -s

Requires:
    pip install pytest-benchmark httpx pytest-asyncio
"""

import asyncio
import json
import os
import statistics
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BENCHMARK_ENV = "BRIGADE_BENCHMARK"
BENCHMARK_ONLY = pytest.mark.skipif(
    os.getenv(BENCHMARK_ENV) != "1",
    reason=f"set {BENCHMARK_ENV}=1 to run wall-clock benchmarks",
)


# =============================================================================
# BENCHMARK INFRASTRUCTURE
# =============================================================================


@dataclass
class BenchmarkResult:
    """Result of a single benchmark run"""

    name: str
    operation: str
    samples: list[float] = field(default_factory=list)
    target_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def mean_ms(self) -> float:
        """Mean execution time in milliseconds"""
        return statistics.mean(self.samples) * 1000 if self.samples else 0.0

    @property
    def p95_ms(self) -> float:
        """95th percentile execution time in milliseconds"""
        if not self.samples:
            return 0.0
        sorted_samples = sorted(self.samples)
        idx = int(len(sorted_samples) * 0.95)
        return sorted_samples[min(idx, len(sorted_samples) - 1)] * 1000

    @property
    def min_ms(self) -> float:
        """Minimum execution time in milliseconds"""
        return min(self.samples) * 1000 if self.samples else 0.0

    @property
    def max_ms(self) -> float:
        """Maximum execution time in milliseconds"""
        return max(self.samples) * 1000 if self.samples else 0.0

    @property
    def std_dev_ms(self) -> float:
        """Standard deviation in milliseconds"""
        if len(self.samples) < 2:
            return 0.0
        return statistics.stdev(self.samples) * 1000

    @property
    def ops_per_second(self) -> float:
        """Operations per second"""
        if not self.samples or self.mean_ms == 0:
            return 0.0
        return 1000 / self.mean_ms

    @property
    def passed(self) -> bool:
        """Whether benchmark passed target"""
        if self.target_ms <= 0:
            return True
        return self.mean_ms <= self.target_ms

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for reporting"""
        return {
            "name": self.name,
            "operation": self.operation,
            "sample_count": len(self.samples),
            "mean_ms": round(self.mean_ms, 3),
            "p95_ms": round(self.p95_ms, 3),
            "min_ms": round(self.min_ms, 3),
            "max_ms": round(self.max_ms, 3),
            "std_dev_ms": round(self.std_dev_ms, 3),
            "ops_per_second": round(self.ops_per_second, 1),
            "target_ms": self.target_ms,
            "passed": self.passed,
            "status": "PASS" if self.passed else "FAIL",
            "metadata": self.metadata,
        }


class BenchmarkRunner:
    """
    Runs benchmarks with timing, warmup, and reporting.

    Provides a consistent interface for all benchmark types.
    """

    def __init__(self, warmup_runs: int = 3, sample_runs: int = 100):
        self.warmup_runs = warmup_runs
        self.sample_runs = sample_runs
        self.results: list[BenchmarkResult] = []

    def run_sync(
        self,
        name: str,
        operation: str,
        func: Callable[[], Any],
        target_ms: float = 0.0,
        metadata: Optional[dict[str, Any]] = None,
    ) -> BenchmarkResult:
        """
        Run a synchronous benchmark.

        Args:
            name: Benchmark category name
            operation: Specific operation being measured
            func: Function to benchmark (no args)
            target_ms: Target time in milliseconds (0 = no target)
            metadata: Additional metadata for the result

        Returns:
            BenchmarkResult with timing data
        """
        result = BenchmarkResult(
            name=name,
            operation=operation,
            target_ms=target_ms,
            metadata=metadata or {},
        )

        # Warmup
        for _ in range(self.warmup_runs):
            func()

        # Measure
        for _ in range(self.sample_runs):
            start = time.perf_counter()
            func()
            elapsed = time.perf_counter() - start
            result.samples.append(elapsed)

        self.results.append(result)
        return result

    async def run_async(
        self,
        name: str,
        operation: str,
        func: Callable[[], Any],
        target_ms: float = 0.0,
        metadata: Optional[dict[str, Any]] = None,
    ) -> BenchmarkResult:
        """
        Run an async benchmark.

        Args:
            name: Benchmark category name
            operation: Specific operation being measured
            func: Async function to benchmark (no args)
            target_ms: Target time in milliseconds (0 = no target)
            metadata: Additional metadata for the result

        Returns:
            BenchmarkResult with timing data
        """
        result = BenchmarkResult(
            name=name,
            operation=operation,
            target_ms=target_ms,
            metadata=metadata or {},
        )

        # Warmup
        for _ in range(self.warmup_runs):
            await func()

        # Measure
        for _ in range(self.sample_runs):
            start = time.perf_counter()
            await func()
            elapsed = time.perf_counter() - start
            result.samples.append(elapsed)

        self.results.append(result)
        return result

    def generate_report(self) -> str:
        """Generate a formatted benchmark report"""
        lines = [
            "",
            "=" * 80,
            "PERFORMANCE BENCHMARK REPORT",
            "=" * 80,
            "",
        ]

        # Group by name
        grouped: dict[str, list[BenchmarkResult]] = {}
        for result in self.results:
            if result.name not in grouped:
                grouped[result.name] = []
            grouped[result.name].append(result)

        all_passed = True
        for name, results in grouped.items():
            lines.append(f"\n{name}")
            lines.append("-" * len(name))

            for result in results:
                status = "[PASS]" if result.passed else "[FAIL]"
                if not result.passed:
                    all_passed = False

                lines.append(
                    f"  {result.operation:40} "
                    f"Mean: {result.mean_ms:8.3f}ms  "
                    f"P95: {result.p95_ms:8.3f}ms  "
                    f"Ops/s: {result.ops_per_second:8.1f}  "
                    f"Target: {result.target_ms:6.1f}ms  "
                    f"{status}"
                )

        lines.append("")
        lines.append("=" * 80)
        summary_status = "ALL BENCHMARKS PASSED" if all_passed else "SOME BENCHMARKS FAILED"
        lines.append(f"SUMMARY: {summary_status}")
        lines.append("=" * 80)
        lines.append("")

        return "\n".join(lines)

    def get_json_report(self) -> dict[str, Any]:
        """Get benchmark results as JSON-serializable dict"""
        return {
            "benchmarks": [r.to_dict() for r in self.results],
            "summary": {
                "total": len(self.results),
                "passed": sum(1 for r in self.results if r.passed),
                "failed": sum(1 for r in self.results if not r.passed),
                "all_passed": all(r.passed for r in self.results),
            },
        }


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def benchmark_runner():
    """Provide a fresh benchmark runner for each test"""
    runner = BenchmarkRunner(warmup_runs=3, sample_runs=100)
    yield runner

    if os.getenv(BENCHMARK_ENV) == "1" and runner.results:
        print(runner.generate_report())


@pytest.fixture
def mock_db_session():
    """Mock async database session"""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    return session


@pytest.fixture
def sample_agents():
    """Sample agent data for testing"""
    return [
        {
            "id": f"agent-{i}",
            "name": f"Agent {i}",
            "displayName": f"Agent {i}",
            "domain": "general",
            "status": "active",
            "tools": ["calculator", "web_search", "memory"][: min(i + 1, 3)],
            "model": "openai/gpt-4o-mini",
            "temperature": 0.7,
            "maxTokens": 2000,
        }
        for i in range(20)
    ]


@pytest.fixture
def sample_agent_with_tools():
    """Sample agent with multiple tools"""
    return {
        "id": "test-agent-1",
        "name": "Test Agent",
        "displayName": "Test Agent",
        "domain": "general",
        "status": "active",
        "tools": [
            "web_search",
            "calculator",
            "memory",
            "datetime",
            "json",
            "http_request",
            "email",
            "file",
            "code",
            "text",
        ],
        "model": "openai/gpt-4o-mini",
        "temperature": 0.7,
        "maxTokens": 2000,
    }


# =============================================================================
# 1. TOOL RESOLUTION PERFORMANCE
# =============================================================================


@pytest.mark.perf
@BENCHMARK_ONLY
class TestToolResolutionPerformance:
    """
    Benchmark tool resolution performance.

    Measures:
    - Time to resolve tools for agents with 1, 5, 10, 20 tools
    - TOOL_REGISTRY lookup speed

    Target: < 1ms per resolution
    """

    TARGET_MS = 1.0  # 1ms per resolution

    def test_tool_registry_lookup(self, benchmark_runner: BenchmarkRunner):
        """Benchmark single tool lookup from registry"""
        from app.llm.tool_resolver import TOOL_REGISTRY, get_tool_by_name

        tool_names = list(TOOL_REGISTRY.keys())
        idx = 0

        def lookup_tool():
            nonlocal idx
            name = tool_names[idx % len(tool_names)]
            idx += 1
            return get_tool_by_name(name)

        result = benchmark_runner.run_sync(
            name="Tool Resolution Performance",
            operation="TOOL_REGISTRY single lookup",
            func=lookup_tool,
            target_ms=self.TARGET_MS,
            metadata={"registry_size": len(TOOL_REGISTRY)},
        )

        assert result.passed, f"Tool lookup too slow: {result.mean_ms:.3f}ms > {self.TARGET_MS}ms"

    def test_resolve_tools_1_tool(self, benchmark_runner: BenchmarkRunner):
        """Benchmark resolving 1 tool for an agent"""
        from app.llm.tool_resolver import get_tools_for_agent

        agent = {"tools": ["calculator"]}

        result = benchmark_runner.run_sync(
            name="Tool Resolution Performance",
            operation="Resolve 1 tool",
            func=lambda: get_tools_for_agent(agent),
            target_ms=self.TARGET_MS,
            metadata={"tool_count": 1},
        )

        assert result.passed, f"1-tool resolution too slow: {result.mean_ms:.3f}ms"

    def test_resolve_tools_5_tools(self, benchmark_runner: BenchmarkRunner):
        """Benchmark resolving 5 tools for an agent"""
        from app.llm.tool_resolver import get_tools_for_agent

        agent = {"tools": ["calculator", "web_search", "memory", "datetime", "json"]}

        result = benchmark_runner.run_sync(
            name="Tool Resolution Performance",
            operation="Resolve 5 tools",
            func=lambda: get_tools_for_agent(agent),
            target_ms=self.TARGET_MS,
            metadata={"tool_count": 5},
        )

        assert result.passed, f"5-tool resolution too slow: {result.mean_ms:.3f}ms"

    def test_resolve_tools_10_tools(self, benchmark_runner: BenchmarkRunner):
        """Benchmark resolving 10 tools for an agent"""
        from app.llm.tool_resolver import get_tools_for_agent

        agent = {
            "tools": [
                "calculator",
                "web_search",
                "memory",
                "datetime",
                "json",
                "http_request",
                "email",
                "file",
                "code",
                "text",
            ]
        }

        result = benchmark_runner.run_sync(
            name="Tool Resolution Performance",
            operation="Resolve 10 tools",
            func=lambda: get_tools_for_agent(agent),
            target_ms=self.TARGET_MS,
            metadata={"tool_count": 10},
        )

        assert result.passed, f"10-tool resolution too slow: {result.mean_ms:.3f}ms"

    def test_resolve_tools_20_tools(self, benchmark_runner: BenchmarkRunner):
        """Benchmark resolving 20 tools for an agent (all available)"""
        from app.llm.tool_resolver import TOOL_REGISTRY, get_tools_for_agent

        # Use all available tools (up to 20)
        all_tools = list(TOOL_REGISTRY.keys())[:20]
        agent = {"tools": all_tools}

        result = benchmark_runner.run_sync(
            name="Tool Resolution Performance",
            operation="Resolve 20 tools",
            func=lambda: get_tools_for_agent(agent),
            target_ms=self.TARGET_MS,
            metadata={"tool_count": len(all_tools)},
        )

        assert result.passed, f"20-tool resolution too slow: {result.mean_ms:.3f}ms"

    def test_get_tools_by_names(self, benchmark_runner: BenchmarkRunner):
        """Benchmark get_tools_by_names function"""
        from app.llm.tool_resolver import get_tools_by_names

        tool_names = ["web_search", "calculator", "memory", "datetime", "json"]

        result = benchmark_runner.run_sync(
            name="Tool Resolution Performance",
            operation="get_tools_by_names (5 tools)",
            func=lambda: get_tools_by_names(tool_names),
            target_ms=self.TARGET_MS,
            metadata={"tool_count": len(tool_names)},
        )

        assert result.passed, f"get_tools_by_names too slow: {result.mean_ms:.3f}ms"


# =============================================================================
# 2. AGENT LOADING PERFORMANCE
# =============================================================================


@pytest.mark.perf
@BENCHMARK_ONLY
class TestAgentLoadingPerformance:
    """
    Benchmark agent loading performance.

    Measures:
    - Time to load agent from database
    - In-memory lookup comparison
    - Agent serialization (to_dict) time

    Target: < 10ms per agent load
    """

    TARGET_MS = 10.0  # 10ms per agent load

    def test_agent_to_dict_serialization(self, benchmark_runner: BenchmarkRunner):
        """Benchmark Agent.to_dict() serialization"""
        from datetime import datetime

        from app.db.models import Agent

        # Create a mock agent instance
        agent = Agent(
            id="test-agent",
            name="Test Agent",
            display_name="Test Agent Display",
            title="Senior Agent",
            rank="Colonel",
            avatar="🤖",
            bio="A test agent for benchmarking",
            persona="Professional and efficient",
            system_prompt="You are a helpful assistant.",
            domain="general",
            subdomain="testing",
            status="active",
            type="individual",
            agent_type="analysis",
            capabilities=["research", "analysis", "reporting"],
            model="openai/gpt-4o-mini",
            temperature=0.7,
            max_tokens=2000,
            tools=["web_search", "calculator", "memory"],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        result = benchmark_runner.run_sync(
            name="Agent Loading Performance",
            operation="Agent.to_dict() serialization",
            func=lambda: agent.to_dict(),
            target_ms=1.0,  # Serialization should be very fast
            metadata={"fields": 18},
        )

        assert result.passed, f"Agent serialization too slow: {result.mean_ms:.3f}ms"

    def test_in_memory_agent_lookup(self, benchmark_runner: BenchmarkRunner, sample_agents):
        """Benchmark in-memory agent lookup (dict-based)"""
        agent_dict = {a["id"]: a for a in sample_agents}
        agent_ids = list(agent_dict.keys())
        idx = 0

        def lookup_agent():
            nonlocal idx
            agent_id = agent_ids[idx % len(agent_ids)]
            idx += 1
            return agent_dict.get(agent_id)

        result = benchmark_runner.run_sync(
            name="Agent Loading Performance",
            operation="In-memory dict lookup",
            func=lookup_agent,
            target_ms=0.01,  # Dict lookup should be sub-microsecond
            metadata={"agent_count": len(sample_agents)},
        )

        assert result.passed, f"In-memory lookup too slow: {result.mean_ms:.3f}ms"

    @pytest.mark.asyncio
    async def test_agent_repository_list_all_mock(
        self, benchmark_runner: BenchmarkRunner, sample_agents
    ):
        """Benchmark AgentRepository.list_all with mocked DB"""
        from unittest.mock import MagicMock

        from app.db.repositories import AgentRepository

        # Mock the session and result
        mock_session = AsyncMock()
        mock_result = MagicMock()

        # Create mock Agent objects
        mock_agents = []
        for agent_data in sample_agents:
            mock_agent = MagicMock()
            mock_agent.to_dict.return_value = agent_data
            mock_agents.append(mock_agent)

        mock_result.scalars.return_value.all.return_value = mock_agents
        mock_session.execute.return_value = mock_result

        repo = AgentRepository(mock_session)

        result = await benchmark_runner.run_async(
            name="Agent Loading Performance",
            operation="AgentRepository.list_all (mocked)",
            func=lambda: repo.list_all(),
            target_ms=self.TARGET_MS,
            metadata={"agent_count": len(sample_agents)},
        )

        assert result.passed, f"Agent list_all too slow: {result.mean_ms:.3f}ms"

    @pytest.mark.asyncio
    async def test_agent_repository_get_mock(
        self, benchmark_runner: BenchmarkRunner, sample_agents
    ):
        """Benchmark AgentRepository.get with mocked DB"""
        from unittest.mock import MagicMock

        from app.db.repositories import AgentRepository

        mock_session = AsyncMock()
        mock_result = MagicMock()

        mock_agent = MagicMock()
        mock_agent.to_dict.return_value = sample_agents[0]
        mock_result.scalar_one_or_none.return_value = mock_agent
        mock_session.execute.return_value = mock_result

        repo = AgentRepository(mock_session)
        idx = 0
        agent_ids = [a["id"] for a in sample_agents]

        async def get_agent():
            nonlocal idx
            agent_id = agent_ids[idx % len(agent_ids)]
            idx += 1
            return await repo.get(agent_id)

        result = await benchmark_runner.run_async(
            name="Agent Loading Performance",
            operation="AgentRepository.get (mocked)",
            func=get_agent,
            target_ms=self.TARGET_MS,
            metadata={"agent_count": len(sample_agents)},
        )

        assert result.passed, f"Agent get too slow: {result.mean_ms:.3f}ms"


# =============================================================================
# 3. WORKFLOW STEP EXECUTION BASELINE
# =============================================================================


@pytest.mark.perf
@BENCHMARK_ONLY
class TestWorkflowStepExecutionBaseline:
    """
    Benchmark workflow engine overhead (excluding LLM calls).

    Measures:
    - Step setup time
    - Input mapping time
    - Output collection time

    Target: < 50ms overhead per step
    """

    TARGET_MS = 50.0  # 50ms per step overhead

    def test_workflow_input_resolution(self, benchmark_runner: BenchmarkRunner):
        """Benchmark workflow input resolution"""
        from app.workflows.engine import WorkflowEngine

        engine = WorkflowEngine()

        # Sample step outputs
        step_outputs = {
            "inputs": {"company_name": "Acme Corp", "amount": 1000000},
            "step-1": {"analysis": "Positive outlook", "score": 85},
            "step-2": {"summary": "Good investment", "risks": ["market", "competition"]},
        }

        # Sample input mapping
        input_mapping = {
            "company": "inputs.company_name",
            "previous_analysis": "step-1.analysis",
            "previous_score": "step-1.score",
        }

        result = benchmark_runner.run_sync(
            name="Workflow Step Execution Baseline",
            operation="Input resolution (_resolve_inputs)",
            func=lambda: engine._resolve_inputs(input_mapping, step_outputs),
            target_ms=1.0,  # Input resolution should be very fast
            metadata={"input_count": len(input_mapping)},
        )

        assert result.passed, f"Input resolution too slow: {result.mean_ms:.3f}ms"

    def test_workflow_condition_evaluation(self, benchmark_runner: BenchmarkRunner):
        """Benchmark workflow condition evaluation"""
        from app.workflows.engine import WorkflowEngine

        engine = WorkflowEngine()

        step_outputs = {
            "step-1": {"score": 85, "passed": True},
            "step-2": {"amount": 1000000},
        }

        conditions = [
            "True",
            "step-1.score > 50",
            "step-1.passed == True",
        ]
        idx = 0

        def evaluate_condition():
            nonlocal idx
            condition = conditions[idx % len(conditions)]
            idx += 1
            return engine._evaluate_condition(condition, step_outputs)

        result = benchmark_runner.run_sync(
            name="Workflow Step Execution Baseline",
            operation="Condition evaluation",
            func=evaluate_condition,
            target_ms=1.0,
            metadata={"condition_count": len(conditions)},
        )

        assert result.passed, f"Condition evaluation too slow: {result.mean_ms:.3f}ms"

    def test_workflow_json_parsing(self, benchmark_runner: BenchmarkRunner):
        """Benchmark JSON parsing from LLM responses"""
        from app.workflows.engine import WorkflowEngine

        engine = WorkflowEngine()

        # Typical LLM responses with JSON
        responses = [
            '{"result": "success", "score": 85}',
            '```json\n{"analysis": "positive", "confidence": 0.92}\n```',
            'Based on my analysis, the result is: {"status": "approved", "amount": 50000}',
            '{"items": [1, 2, 3], "total": 6, "metadata": {"source": "calculation"}}',
        ]
        idx = 0

        def parse_json():
            nonlocal idx
            response = responses[idx % len(responses)]
            idx += 1
            return engine._parse_json_from_response(response)

        result = benchmark_runner.run_sync(
            name="Workflow Step Execution Baseline",
            operation="JSON parsing from response",
            func=parse_json,
            target_ms=1.0,
            metadata={"response_count": len(responses)},
        )

        assert result.passed, f"JSON parsing too slow: {result.mean_ms:.3f}ms"

    def test_workflow_content_extraction(self, benchmark_runner: BenchmarkRunner):
        """Benchmark content extraction from LLM response"""
        from app.workflows.engine import WorkflowEngine

        engine = WorkflowEngine()

        # Typical LLM response structures
        responses = [
            {"choices": [{"message": {"content": "This is the response content"}}]},
            {"content": "Direct content response"},
            {"choices": [{"message": {"content": None}}]},
        ]
        idx = 0

        def extract_content():
            nonlocal idx
            response = responses[idx % len(responses)]
            idx += 1
            return engine._extract_content(response)

        result = benchmark_runner.run_sync(
            name="Workflow Step Execution Baseline",
            operation="Content extraction",
            func=extract_content,
            target_ms=0.1,
            metadata={"response_count": len(responses)},
        )

        assert result.passed, f"Content extraction too slow: {result.mean_ms:.3f}ms"

    def test_step_execution_object_creation(self, benchmark_runner: BenchmarkRunner):
        """Benchmark StepExecution object creation"""
        from datetime import datetime

        from app.workflows.schema import StepExecution, StepExecutionState

        def create_step_execution():
            return StepExecution(
                step_id="test-step",
                state=StepExecutionState.RUNNING,
                started_at=datetime.utcnow(),
                inputs_received={"key1": "value1", "key2": "value2"},
            )

        result = benchmark_runner.run_sync(
            name="Workflow Step Execution Baseline",
            operation="StepExecution object creation",
            func=create_step_execution,
            target_ms=1.0,
            metadata={},
        )

        assert result.passed, f"StepExecution creation too slow: {result.mean_ms:.3f}ms"


# =============================================================================
# 4. MODEL CONFIG RESOLUTION
# =============================================================================


@pytest.mark.perf
@BENCHMARK_ONLY
class TestModelConfigResolution:
    """
    Benchmark ModelRegistry.get_model_for_* methods.

    Measures:
    - Orchestrator model resolution
    - Team lead model resolution (with domain)
    - Worker model resolution (with fallbacks)
    - Preset config loading

    Target: < 1ms per resolution
    """

    TARGET_MS = 1.0  # 1ms per resolution

    def test_get_model_for_orchestrator(self, benchmark_runner: BenchmarkRunner):
        """Benchmark orchestrator model resolution"""
        from app.workflows.model_config import ModelConfig, ModelRegistry

        config = ModelConfig()

        result = benchmark_runner.run_sync(
            name="Model Config Resolution",
            operation="get_model_for_orchestrator",
            func=lambda: ModelRegistry.get_model_for_orchestrator(config),
            target_ms=self.TARGET_MS,
            metadata={},
        )

        assert result.passed, f"Orchestrator resolution too slow: {result.mean_ms:.3f}ms"

    def test_get_model_for_team_lead(self, benchmark_runner: BenchmarkRunner):
        """Benchmark team lead model resolution"""
        from app.workflows.model_config import ModelConfig, ModelRegistry

        config = ModelConfig()
        domains = [
            "research",
            "finance",
            "content",
            "sales",
            "devops",
            "legal",
            "medical",
            "investigation",
        ]
        idx = 0

        def get_team_lead_model():
            nonlocal idx
            domain = domains[idx % len(domains)]
            idx += 1
            return ModelRegistry.get_model_for_team_lead(domain, config)

        result = benchmark_runner.run_sync(
            name="Model Config Resolution",
            operation="get_model_for_team_lead (8 domains)",
            func=get_team_lead_model,
            target_ms=self.TARGET_MS,
            metadata={"domain_count": len(domains)},
        )

        assert result.passed, f"Team lead resolution too slow: {result.mean_ms:.3f}ms"

    def test_get_model_for_worker(self, benchmark_runner: BenchmarkRunner):
        """Benchmark worker model resolution"""
        from app.workflows.model_config import ModelConfig, ModelRegistry

        config = ModelConfig()
        worker_ids = [
            "web-researcher",
            "academic-researcher",
            "trend-analyzer",
            "ratio-calculator",
            "risk-assessor",
            "blog-writer",
        ]
        idx = 0

        def get_worker_model():
            nonlocal idx
            worker_id = worker_ids[idx % len(worker_ids)]
            idx += 1
            return ModelRegistry.get_model_for_worker(worker_id, config, "ollama/llama3.2:3b")

        result = benchmark_runner.run_sync(
            name="Model Config Resolution",
            operation="get_model_for_worker (6 workers)",
            func=get_worker_model,
            target_ms=self.TARGET_MS,
            metadata={"worker_count": len(worker_ids)},
        )

        assert result.passed, f"Worker resolution too slow: {result.mean_ms:.3f}ms"

    def test_model_tier_detection(self, benchmark_runner: BenchmarkRunner):
        """Benchmark model tier detection"""
        from app.workflows.model_config import ModelRegistry

        models = [
            "openai/gpt-4o",
            "openai/gpt-4o-mini",
            "anthropic/claude-3.5-sonnet",
            "ollama/llama3.1:8b",
            "ollama/llama3.2:3b",
            "google/gemini-pro",
        ]
        idx = 0

        def get_tier():
            nonlocal idx
            model = models[idx % len(models)]
            idx += 1
            return ModelRegistry.get_model_tier(model)

        result = benchmark_runner.run_sync(
            name="Model Config Resolution",
            operation="get_model_tier (6 models)",
            func=get_tier,
            target_ms=self.TARGET_MS,
            metadata={"model_count": len(models)},
        )

        assert result.passed, f"Tier detection too slow: {result.mean_ms:.3f}ms"

    def test_preset_config_loading(self, benchmark_runner: BenchmarkRunner):
        """Benchmark preset configuration loading"""
        from app.workflows.model_config import CONFIG_PRESETS, get_config_from_preset

        presets = list(CONFIG_PRESETS.keys())
        idx = 0

        def load_preset():
            nonlocal idx
            preset = presets[idx % len(presets)]
            idx += 1
            return get_config_from_preset(preset)

        result = benchmark_runner.run_sync(
            name="Model Config Resolution",
            operation="get_config_from_preset (6 presets)",
            func=load_preset,
            target_ms=self.TARGET_MS,
            metadata={"preset_count": len(presets)},
        )

        assert result.passed, f"Preset loading too slow: {result.mean_ms:.3f}ms"

    def test_model_cost_calculation(self, benchmark_runner: BenchmarkRunner):
        """Benchmark model cost calculation"""
        from app.workflows.model_config import ModelRegistry

        models = ["openai/gpt-4o", "openai/gpt-4o-mini", "anthropic/claude-3.5-sonnet"]
        idx = 0

        def calculate_cost():
            nonlocal idx
            model = models[idx % len(models)]
            idx += 1
            return ModelRegistry.get_model_cost(model, 1000, 500)

        result = benchmark_runner.run_sync(
            name="Model Config Resolution",
            operation="get_model_cost calculation",
            func=calculate_cost,
            target_ms=self.TARGET_MS,
            metadata={"model_count": len(models)},
        )

        assert result.passed, f"Cost calculation too slow: {result.mean_ms:.3f}ms"

    def test_config_merge(self, benchmark_runner: BenchmarkRunner):
        """Benchmark config merging"""
        from app.workflows.model_config import ModelConfig, merge_configs

        base = ModelConfig()
        overrides = {
            "orchestrator_model": "openai/gpt-4o",
            "team_lead_models": {"research": "anthropic/claude-3.5-sonnet"},
        }

        result = benchmark_runner.run_sync(
            name="Model Config Resolution",
            operation="merge_configs",
            func=lambda: merge_configs(base, overrides),
            target_ms=self.TARGET_MS,
            metadata={},
        )

        assert result.passed, f"Config merge too slow: {result.mean_ms:.3f}ms"


# =============================================================================
# 5. MEMORY OPERATIONS (if Qdrant available)
# =============================================================================


@pytest.mark.perf
@BENCHMARK_ONLY
class TestMemoryOperations:
    """
    Benchmark memory operations.

    Uses mocked Qdrant client when Qdrant is not available.

    Measures:
    - Memory store operation
    - Memory query operation

    Target: < 100ms for vector search
    """

    TARGET_MS = 100.0  # 100ms for vector operations

    @pytest.mark.asyncio
    async def test_memory_store_mock(self, benchmark_runner: BenchmarkRunner):
        """Benchmark memory store with mocked backend"""
        from app.memory.manager import MemoryManager

        # Create manager with mocked memory
        manager = MemoryManager.__new__(MemoryManager)
        manager.memory = MagicMock()
        manager.memory.add = MagicMock(return_value=True)

        messages = [
            {"role": "user", "content": "What is AI?"},
            {"role": "assistant", "content": "AI stands for Artificial Intelligence..."},
        ]

        result = await benchmark_runner.run_async(
            name="Memory Operations",
            operation="Memory store (mocked)",
            func=lambda: manager.store("user-1", "agent-1", messages, {}),
            target_ms=self.TARGET_MS,
            metadata={"message_count": len(messages)},
        )

        assert result.passed, f"Memory store too slow: {result.mean_ms:.3f}ms"

    @pytest.mark.asyncio
    async def test_memory_retrieve_mock(self, benchmark_runner: BenchmarkRunner):
        """Benchmark memory retrieval with mocked backend"""
        from app.memory.manager import MemoryManager

        # Create manager with mocked memory
        manager = MemoryManager.__new__(MemoryManager)
        manager.memory = MagicMock()
        manager.memory.search = MagicMock(
            return_value=[
                {"id": "mem-1", "content": "Previous conversation about AI", "score": 0.95},
                {"id": "mem-2", "content": "Discussion about machine learning", "score": 0.85},
            ]
        )

        result = await benchmark_runner.run_async(
            name="Memory Operations",
            operation="Memory retrieve (mocked)",
            func=lambda: manager.retrieve("user-1", "Tell me about AI", limit=10),
            target_ms=self.TARGET_MS,
            metadata={},
        )

        assert result.passed, f"Memory retrieve too slow: {result.mean_ms:.3f}ms"

    @pytest.mark.asyncio
    async def test_memory_get_all_mock(self, benchmark_runner: BenchmarkRunner):
        """Benchmark memory get_all with mocked backend"""
        from app.memory.manager import MemoryManager

        # Create manager with mocked memory
        manager = MemoryManager.__new__(MemoryManager)
        manager.memory = MagicMock()
        manager.memory.get_all = MagicMock(
            return_value=[
                {"id": f"mem-{i}", "content": f"Memory {i}", "agent_id": "agent-1"}
                for i in range(20)
            ]
        )

        result = await benchmark_runner.run_async(
            name="Memory Operations",
            operation="Memory get_all (mocked, 20 memories)",
            func=lambda: manager.get_all("user-1", "agent-1"),
            target_ms=self.TARGET_MS,
            metadata={"memory_count": 20},
        )

        assert result.passed, f"Memory get_all too slow: {result.mean_ms:.3f}ms"


# =============================================================================
# 6. API RESPONSE TIME (using TestClient)
# =============================================================================


class TestAPIResponseTime:
    """
    Benchmark API response times.

    Uses FastAPI TestClient with mocked dependencies.

    Measures:
    - GET /api/v1/agents (list all)
    - GET /api/v1/agents/{id}
    - GET /api/v1/hierarchical/templates

    Target: < 50ms for read operations
    """

    TARGET_MS = 50.0  # 50ms for read operations

    @pytest.fixture
    def agent_api_sessions(self):
        """Sessions used by the mocked agent API, including query counts."""
        return []

    @pytest.fixture
    def test_client(self, sample_agents, agent_api_sessions):
        """Create a test client with mocked database"""
        from unittest.mock import MagicMock

        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from app.api.agent_routes import router as agent_router
        from app.api.hierarchical_routes import router as hierarchical_router
        from app.auth.middleware import require_api_key
        from app.db.database import get_session

        # Create a minimal app for testing
        app = FastAPI()

        # Create mock session that returns our sample agents
        async def mock_get_session():
            session = AsyncMock()
            mock_result = MagicMock()

            # Mirror AgentRepository.list_all's stable ORDER BY domain, name.
            mock_agents = []
            for agent_data in sorted(
                sample_agents, key=lambda agent: (agent["domain"], agent["name"])
            ):
                mock_agent = MagicMock()
                mock_agent.to_dict.side_effect = lambda data=agent_data: dict(data)
                mock_agents.append(mock_agent)

            mock_result.scalars.return_value.all.return_value = mock_agents
            mock_result.scalar_one_or_none.return_value = mock_agents[0] if mock_agents else None
            session.query_count = 0

            async def execute(*args, **kwargs):
                session.query_count += 1
                return mock_result

            session.execute = AsyncMock(side_effect=execute)
            agent_api_sessions.append(session)
            yield session

        # Mock auth
        async def mock_require_api_key():
            mock_user = MagicMock()
            mock_user.role = "admin"
            mock_user.agent_id = None
            return mock_user

        app.dependency_overrides[get_session] = mock_get_session
        app.dependency_overrides[require_api_key] = mock_require_api_key

        app.include_router(agent_router, prefix="/api/v1")
        app.include_router(hierarchical_router, prefix="/api/v1")

        return TestClient(app)

    def test_list_agents_api(self, test_client, sample_agents, agent_api_sessions):
        """GET /api/v1/agents returns the complete, ordered roster without N+1."""
        response = test_client.get("/api/v1/agents")
        assert response.status_code == 200

        payload = response.json()
        assert set(payload) == {"agents"}
        returned_agents = payload["agents"]
        assert isinstance(returned_agents, list)
        assert all(isinstance(agent, dict) for agent in returned_agents)
        assert len(returned_agents) == len(sample_agents)

        expected_agents = sorted(sample_agents, key=lambda agent: (agent["domain"], agent["name"]))
        expected_ids = [agent["id"] for agent in expected_agents]
        assert [agent["id"] for agent in returned_agents] == expected_ids
        for expected, actual in zip(expected_agents, returned_agents):
            for field, value in expected.items():
                assert actual[field] == value

        max_list_queries = 2  # one agent query plus one tool-catalog query
        query_count = sum(session.query_count for session in agent_api_sessions)
        assert query_count <= max_list_queries, (
            f"GET /api/v1/agents used {query_count} SQL statements for "
            f"{len(returned_agents)} agents; expected <= {max_list_queries} "
            "independent of roster size"
        )

    @pytest.mark.perf
    @BENCHMARK_ONLY
    def test_list_agents_api_benchmark(
        self, benchmark_runner: BenchmarkRunner, test_client, sample_agents
    ):
        """Opt-in benchmark for GET /api/v1/agents latency."""

        def make_request():
            response = test_client.get("/api/v1/agents")
            assert response.status_code == 200
            return response.json()

        result = benchmark_runner.run_sync(
            name="API Response Time",
            operation="GET /api/v1/agents (list all)",
            func=make_request,
            target_ms=self.TARGET_MS,
            metadata={"agent_count": len(sample_agents)},
        )

        assert result.passed, (
            f"List agents API too slow: mean={result.mean_ms:.3f}ms, "
            f"p95={result.p95_ms:.3f}ms > {self.TARGET_MS}ms"
        )

    @pytest.mark.perf
    @BENCHMARK_ONLY
    def test_get_agent_api(self, benchmark_runner: BenchmarkRunner, test_client, sample_agents):
        """Benchmark GET /api/v1/agents/{id}"""
        agent_ids = [a["id"] for a in sample_agents]
        idx = 0

        def make_request():
            nonlocal idx
            agent_id = agent_ids[idx % len(agent_ids)]
            idx += 1
            response = test_client.get(f"/api/v1/agents/{agent_id}")
            # May return 404 due to mock, but we're measuring response time
            return response

        result = benchmark_runner.run_sync(
            name="API Response Time",
            operation="GET /api/v1/agents/{id}",
            func=make_request,
            target_ms=self.TARGET_MS,
            metadata={"agent_count": len(sample_agents)},
        )

        assert result.passed, f"Get agent API too slow: {result.mean_ms:.3f}ms"

    @pytest.mark.perf
    @BENCHMARK_ONLY
    def test_list_templates_api(self, benchmark_runner: BenchmarkRunner, test_client):
        """Benchmark GET /api/v1/hierarchical/templates"""

        def make_request():
            response = test_client.get("/api/v1/hierarchical/templates")
            # May return 503 if engine not initialized, but we're measuring response time
            return response

        result = benchmark_runner.run_sync(
            name="API Response Time",
            operation="GET /api/v1/hierarchical/templates",
            func=make_request,
            target_ms=self.TARGET_MS,
            metadata={},
        )

        assert result.passed, f"List templates API too slow: {result.mean_ms:.3f}ms"


# =============================================================================
# COMPREHENSIVE BENCHMARK REPORT
# =============================================================================


@pytest.mark.perf
@BENCHMARK_ONLY
class TestBenchmarkReport:
    """Generate a comprehensive benchmark report"""

    @pytest.fixture
    def full_runner(self):
        """Runner with more samples for final report"""
        return BenchmarkRunner(warmup_runs=5, sample_runs=200)

    def test_generate_full_report(self, full_runner: BenchmarkRunner):
        """Run all benchmarks and generate a comprehensive report"""
        from app.llm.tool_resolver import TOOL_REGISTRY, get_tool_by_name, get_tools_for_agent
        from app.workflows.engine import WorkflowEngine
        from app.workflows.model_config import (
            CONFIG_PRESETS,
            ModelConfig,
            ModelRegistry,
            get_config_from_preset,
            merge_configs,
        )

        # 1. Tool Resolution
        tool_names = list(TOOL_REGISTRY.keys())
        full_runner.run_sync(
            "Tool Resolution",
            "Single tool lookup",
            lambda: get_tool_by_name(tool_names[0]),
            target_ms=1.0,
        )
        full_runner.run_sync(
            "Tool Resolution",
            "Resolve 10 tools",
            lambda: get_tools_for_agent({"tools": tool_names[:10]}),
            target_ms=1.0,
        )

        # 2. Model Config
        config = ModelConfig()
        full_runner.run_sync(
            "Model Config",
            "Orchestrator model",
            lambda: ModelRegistry.get_model_for_orchestrator(config),
            target_ms=1.0,
        )
        full_runner.run_sync(
            "Model Config",
            "Team lead model",
            lambda: ModelRegistry.get_model_for_team_lead("research", config),
            target_ms=1.0,
        )
        full_runner.run_sync(
            "Model Config",
            "Worker model",
            lambda: ModelRegistry.get_model_for_worker("web-researcher", config, None),
            target_ms=1.0,
        )
        full_runner.run_sync(
            "Model Config",
            "Preset loading",
            lambda: get_config_from_preset("cost_optimized"),
            target_ms=1.0,
        )

        # 3. Workflow Engine
        engine = WorkflowEngine()
        step_outputs = {
            "inputs": {"company": "Acme"},
            "step-1": {"score": 85},
        }
        full_runner.run_sync(
            "Workflow Engine",
            "Input resolution",
            lambda: engine._resolve_inputs({"prev": "step-1.score"}, step_outputs),
            target_ms=1.0,
        )
        full_runner.run_sync(
            "Workflow Engine",
            "JSON parsing",
            lambda: engine._parse_json_from_response('{"result": 42}'),
            target_ms=1.0,
        )

        # Generate and print report
        report = full_runner.generate_report()
        print(report)

        # Also save JSON report
        json_report = full_runner.get_json_report()
        print("\nJSON Report:")
        print(json.dumps(json_report, indent=2))

        # Assert all passed
        assert json_report["summary"]["all_passed"], "Some benchmarks failed!"


# =============================================================================
# MAIN ENTRYPOINT
# =============================================================================

if __name__ == "__main__":
    """Run benchmarks directly"""
    import subprocess

    subprocess.run(
        [
            "pytest",
            __file__,
            "-v",
            "--tb=short",
            "-x",  # Stop on first failure
        ]
    )
