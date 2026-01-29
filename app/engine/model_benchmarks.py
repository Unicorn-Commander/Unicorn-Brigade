"""
Model Capability Benchmarks

Tests and benchmarks model capabilities to determine:
- Best model for each task type
- Cost/performance tradeoffs
- Automatic model selection for OpenRouter
"""

from typing import Dict, Any, List, Optional, Tuple
from pydantic import BaseModel, Field
from datetime import datetime
import asyncio
import logging
import json

from app.llm.ops_center_client import OpsCenterLLMClient

logger = logging.getLogger(__name__)


class ModelCapability(BaseModel):
    """Capability scores for a model"""
    model_config = {"protected_namespaces": ()}

    model_id: str
    provider: str

    # Task type scores (0-1)
    research: float = 0.5
    code: float = 0.5
    extraction: float = 0.5
    creative: float = 0.5
    reasoning: float = 0.5
    following_instructions: float = 0.5

    # Performance metrics
    avg_latency_ms: float = 0.0
    avg_tokens_per_second: float = 0.0
    reliability: float = 0.95  # Success rate

    # Cost (per 1M tokens)
    input_cost: float = 0.0
    output_cost: float = 0.0

    # Metadata
    context_window: int = 4096
    supports_tools: bool = True
    supports_vision: bool = False
    supports_streaming: bool = True

    # Benchmark date
    last_benchmarked: Optional[datetime] = None


class BenchmarkResult(BaseModel):
    """Result from a single benchmark test"""
    model_config = {"protected_namespaces": ()}

    model_id: str
    task_type: str
    prompt: str
    response: str
    latency_ms: float
    tokens_in: int
    tokens_out: int
    score: float  # 0-1 quality score
    passed: bool
    error: Optional[str] = None


# Default model capabilities (from research)
DEFAULT_CAPABILITIES: Dict[str, ModelCapability] = {
    # Claude models
    "claude-3-opus": ModelCapability(
        model_id="claude-3-opus",
        provider="anthropic",
        research=0.95,
        code=0.92,
        extraction=0.90,
        creative=0.95,
        reasoning=0.98,
        following_instructions=0.95,
        input_cost=15.0,
        output_cost=75.0,
        context_window=200000,
        supports_vision=True,
    ),
    "claude-3-5-sonnet": ModelCapability(
        model_id="claude-3-5-sonnet",
        provider="anthropic",
        research=0.92,
        code=0.95,
        extraction=0.90,
        creative=0.90,
        reasoning=0.93,
        following_instructions=0.94,
        input_cost=3.0,
        output_cost=15.0,
        context_window=200000,
        supports_vision=True,
    ),
    "claude-3-haiku": ModelCapability(
        model_id="claude-3-haiku",
        provider="anthropic",
        research=0.80,
        code=0.82,
        extraction=0.85,
        creative=0.78,
        reasoning=0.80,
        following_instructions=0.85,
        input_cost=0.25,
        output_cost=1.25,
        context_window=200000,
        supports_vision=True,
    ),

    # GPT models
    "gpt-4-turbo": ModelCapability(
        model_id="gpt-4-turbo",
        provider="openai",
        research=0.92,
        code=0.90,
        extraction=0.88,
        creative=0.90,
        reasoning=0.92,
        following_instructions=0.90,
        input_cost=10.0,
        output_cost=30.0,
        context_window=128000,
        supports_vision=True,
    ),
    "gpt-4o": ModelCapability(
        model_id="gpt-4o",
        provider="openai",
        research=0.90,
        code=0.88,
        extraction=0.88,
        creative=0.88,
        reasoning=0.90,
        following_instructions=0.92,
        input_cost=5.0,
        output_cost=15.0,
        context_window=128000,
        supports_vision=True,
    ),
    "gpt-4o-mini": ModelCapability(
        model_id="gpt-4o-mini",
        provider="openai",
        research=0.78,
        code=0.80,
        extraction=0.82,
        creative=0.75,
        reasoning=0.78,
        following_instructions=0.85,
        input_cost=0.15,
        output_cost=0.60,
        context_window=128000,
        supports_vision=True,
    ),

    # Open source models (via OpenRouter)
    "llama-3.1-70b": ModelCapability(
        model_id="meta-llama/llama-3.1-70b-instruct",
        provider="openrouter",
        research=0.82,
        code=0.85,
        extraction=0.80,
        creative=0.78,
        reasoning=0.82,
        following_instructions=0.80,
        input_cost=0.59,
        output_cost=0.79,
        context_window=131072,
    ),
    "llama-3.1-8b": ModelCapability(
        model_id="meta-llama/llama-3.1-8b-instruct",
        provider="openrouter",
        research=0.70,
        code=0.72,
        extraction=0.72,
        creative=0.68,
        reasoning=0.70,
        following_instructions=0.75,
        input_cost=0.055,
        output_cost=0.055,
        context_window=131072,
    ),
    "mixtral-8x7b": ModelCapability(
        model_id="mistralai/mixtral-8x7b-instruct",
        provider="openrouter",
        research=0.78,
        code=0.80,
        extraction=0.78,
        creative=0.75,
        reasoning=0.78,
        following_instructions=0.78,
        input_cost=0.24,
        output_cost=0.24,
        context_window=32768,
    ),
    "qwen-2.5-72b": ModelCapability(
        model_id="qwen/qwen-2.5-72b-instruct",
        provider="openrouter",
        research=0.85,
        code=0.88,
        extraction=0.82,
        creative=0.80,
        reasoning=0.85,
        following_instructions=0.85,
        input_cost=0.35,
        output_cost=0.40,
        context_window=131072,
    ),
    "deepseek-v2.5": ModelCapability(
        model_id="deepseek/deepseek-chat",
        provider="openrouter",
        research=0.82,
        code=0.90,
        extraction=0.80,
        creative=0.78,
        reasoning=0.85,
        following_instructions=0.82,
        input_cost=0.14,
        output_cost=0.28,
        context_window=65536,
    ),
}


# Task-to-capability mapping
TASK_TYPE_CAPABILITIES = {
    "research": "research",
    "code": "code",
    "extraction": "extraction",
    "report": "creative",
    "ops": "following_instructions",
    "general": "reasoning",
}


class ModelSelector:
    """
    Selects the best model for a given task based on:
    - Task type and complexity
    - Budget constraints
    - Latency requirements
    - Reliability needs
    """

    def __init__(
        self,
        capabilities: Optional[Dict[str, ModelCapability]] = None,
        llm_client: Optional[OpsCenterLLMClient] = None,
    ):
        self.capabilities = capabilities or DEFAULT_CAPABILITIES
        self.llm_client = llm_client or OpsCenterLLMClient()
        self.benchmark_results: List[BenchmarkResult] = []

    def select_model(
        self,
        task_type: str,
        budget_tier: str = "standard",  # "budget", "standard", "premium"
        require_tools: bool = False,
        require_vision: bool = False,
        min_reliability: float = 0.9,
        max_latency_ms: Optional[float] = None,
    ) -> str:
        """
        Select the best model for a task.

        Args:
            task_type: Type of task (research, code, extraction, etc.)
            budget_tier: Budget constraint
            require_tools: Whether tool use is required
            require_vision: Whether vision is required
            min_reliability: Minimum acceptable reliability
            max_latency_ms: Maximum acceptable latency

        Returns:
            Model ID to use
        """
        capability_key = TASK_TYPE_CAPABILITIES.get(task_type, "reasoning")

        # Filter models by requirements
        candidates = []
        for model_id, cap in self.capabilities.items():
            # Check requirements
            if require_tools and not cap.supports_tools:
                continue
            if require_vision and not cap.supports_vision:
                continue
            if cap.reliability < min_reliability:
                continue
            if max_latency_ms and cap.avg_latency_ms > max_latency_ms:
                continue

            # Check budget
            total_cost = cap.input_cost + cap.output_cost
            if budget_tier == "budget" and total_cost > 1.0:
                continue
            elif budget_tier == "standard" and total_cost > 20.0:
                continue
            # "premium" has no cost limit

            # Get capability score for task type
            task_score = getattr(cap, capability_key, 0.5)

            candidates.append((model_id, cap, task_score))

        if not candidates:
            # Fallback to default
            logger.warning(f"No suitable model found for {task_type}, using default")
            return "gpt-4o-mini"

        # Sort by task score, then by cost-effectiveness
        candidates.sort(
            key=lambda x: (x[2], -x[1].input_cost - x[1].output_cost),
            reverse=True,
        )

        best_model = candidates[0][0]
        logger.info(f"Selected model {best_model} for {task_type} (score={candidates[0][2]:.2f})")

        return best_model

    def get_recommendations(
        self,
        task_type: str,
        top_n: int = 3,
    ) -> List[Tuple[str, ModelCapability, float]]:
        """Get top N model recommendations for a task type"""
        capability_key = TASK_TYPE_CAPABILITIES.get(task_type, "reasoning")

        scored = []
        for model_id, cap in self.capabilities.items():
            task_score = getattr(cap, capability_key, 0.5)
            # Factor in cost-effectiveness
            cost = cap.input_cost + cap.output_cost
            cost_factor = 1 / (1 + cost / 10)  # Normalize cost
            final_score = task_score * 0.8 + cost_factor * 0.2

            scored.append((model_id, cap, final_score))

        scored.sort(key=lambda x: x[2], reverse=True)
        return scored[:top_n]

    async def benchmark_model(
        self,
        model_id: str,
        task_type: str,
        test_prompts: Optional[List[Dict[str, str]]] = None,
    ) -> List[BenchmarkResult]:
        """
        Run benchmark tests on a specific model.
        """
        if test_prompts is None:
            test_prompts = self._get_default_prompts(task_type)

        results = []

        for prompt_data in test_prompts:
            try:
                start_time = datetime.utcnow()

                response = await self.llm_client.chat_completion(
                    messages=[
                        {"role": "system", "content": prompt_data.get("system", "")},
                        {"role": "user", "content": prompt_data["user"]},
                    ],
                    model=model_id,
                    temperature=0.3,
                )

                end_time = datetime.utcnow()
                latency = (end_time - start_time).total_seconds() * 1000

                content = response["choices"][0]["message"]["content"]
                usage = response.get("usage", {})

                # Score the response
                score = self._score_response(
                    task_type,
                    prompt_data,
                    content,
                    prompt_data.get("expected_contains", []),
                )

                result = BenchmarkResult(
                    model_id=model_id,
                    task_type=task_type,
                    prompt=prompt_data["user"][:100],
                    response=content[:200],
                    latency_ms=latency,
                    tokens_in=usage.get("prompt_tokens", 0),
                    tokens_out=usage.get("completion_tokens", 0),
                    score=score,
                    passed=score > 0.6,
                )
                results.append(result)

            except Exception as e:
                results.append(BenchmarkResult(
                    model_id=model_id,
                    task_type=task_type,
                    prompt=prompt_data["user"][:100],
                    response="",
                    latency_ms=0,
                    tokens_in=0,
                    tokens_out=0,
                    score=0,
                    passed=False,
                    error=str(e),
                ))

        self.benchmark_results.extend(results)
        return results

    def _get_default_prompts(self, task_type: str) -> List[Dict[str, str]]:
        """Get default benchmark prompts for a task type"""
        prompts = {
            "research": [
                {
                    "user": "What are the key principles of REST API design?",
                    "expected_contains": ["stateless", "resource", "HTTP"],
                },
                {
                    "user": "Explain the difference between SQL and NoSQL databases.",
                    "expected_contains": ["relational", "schema", "scalability"],
                },
            ],
            "code": [
                {
                    "user": "Write a Python function to check if a string is a palindrome.",
                    "expected_contains": ["def", "return", "=="],
                },
                {
                    "user": "Write a JavaScript function to deep clone an object.",
                    "expected_contains": ["function", "return", "JSON"],
                },
            ],
            "extraction": [
                {
                    "system": "Extract structured data as JSON.",
                    "user": "Extract name and email: John Doe, john@example.com",
                    "expected_contains": ["John", "john@example.com"],
                },
            ],
        }
        return prompts.get(task_type, prompts["research"])

    def _score_response(
        self,
        task_type: str,
        prompt_data: Dict[str, str],
        response: str,
        expected_contains: List[str],
    ) -> float:
        """Score a response based on quality criteria"""
        score = 0.5  # Base score

        # Check for expected content
        if expected_contains:
            matches = sum(1 for exp in expected_contains if exp.lower() in response.lower())
            score += 0.3 * (matches / len(expected_contains))

        # Check response length (not too short, not too long)
        if 50 < len(response) < 2000:
            score += 0.1

        # Check for code blocks in code tasks
        if task_type == "code" and "```" in response:
            score += 0.1

        return min(1.0, score)

    def update_capability(
        self,
        model_id: str,
        task_type: str,
        new_score: float,
    ):
        """Update capability score based on benchmark results"""
        if model_id not in self.capabilities:
            return

        cap = self.capabilities[model_id]
        capability_key = TASK_TYPE_CAPABILITIES.get(task_type, "reasoning")

        # Weighted average with existing score
        old_score = getattr(cap, capability_key, 0.5)
        updated_score = old_score * 0.7 + new_score * 0.3

        setattr(cap, capability_key, updated_score)
        cap.last_benchmarked = datetime.utcnow()

        logger.info(f"Updated {model_id} {capability_key}: {old_score:.2f} -> {updated_score:.2f}")


# Global model selector instance
model_selector = ModelSelector()


def select_best_model(
    task_type: str,
    budget: str = "standard",
    **kwargs,
) -> str:
    """Convenience function to select best model"""
    return model_selector.select_model(task_type, budget, **kwargs)


def get_model_capabilities(model_id: str) -> Optional[ModelCapability]:
    """Get capabilities for a specific model"""
    return model_selector.capabilities.get(model_id)
