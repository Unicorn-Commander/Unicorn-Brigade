#!/usr/bin/env python3
"""
Real Inference Test Script

Tests the Unicorn Brigade workflow engine with actual Ops-Center inference.
Uses the Brigade service key for authentication.
"""

import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.llm.ops_center_client import OpsCenterLLMClient


async def test_basic_completion():
    """Test basic chat completion"""
    print("\n" + "=" * 60)
    print("TEST 1: Basic Chat Completion")
    print("=" * 60)

    client = OpsCenterLLMClient()
    print(f"Using URL: {client.ops_center_url}")

    try:
        # Use a reliable paid model (OpenRouter)
        response = await client.chat_completion(
            messages=[
                {"role": "system", "content": "You are a helpful assistant. Be concise."},
                {"role": "user", "content": "What is 2 + 2? Answer with just the number."},
            ],
            model="anthropic/claude-3-haiku",  # Fast and reliable paid model
            temperature=0.3,
            max_tokens=50,
        )

        content = response["choices"][0]["message"]["content"]
        usage = response.get("usage", {})

        print(f"Response: {content}")
        print(f"Tokens - Input: {usage.get('prompt_tokens', 'N/A')}, Output: {usage.get('completion_tokens', 'N/A')}")
        print("SUCCESS")
        return True

    except Exception as e:
        print(f"ERROR: {e}")
        # Try alternate model
        print("\nTrying alternate model...")
        try:
            response = await client.chat_completion(
                messages=[
                    {"role": "user", "content": "Say hello"},
                ],
                model="openai/gpt-4o-mini",  # Another reliable option
                temperature=0.3,
                max_tokens=20,
            )
            content = response["choices"][0]["message"]["content"]
            print(f"Alternate response: {content}")
            print("SUCCESS (alternate model)")
            return True
        except Exception as e2:
            print(f"Alternate also failed: {e2}")
            return False


async def test_list_models():
    """Test listing available models"""
    print("\n" + "=" * 60)
    print("TEST 2: List Available Models")
    print("=" * 60)

    client = OpsCenterLLMClient()

    try:
        models = await client.get_available_models()
        print(f"Found {len(models)} models")

        # Show first 5 free models
        free_models = [m for m in models if ":free" in m.get("id", "")]
        print(f"\nFree models available: {len(free_models)}")
        for m in free_models[:5]:
            print(f"  - {m['id']}")

        print("SUCCESS")
        return True

    except Exception as e:
        print(f"ERROR: {e}")
        return False


async def test_router():
    """Test the task router with real inference"""
    print("\n" + "=" * 60)
    print("TEST 3: Task Router")
    print("=" * 60)

    from app.engine.router import TaskRouter
    from app.engine.models import Task

    client = OpsCenterLLMClient()
    router = TaskRouter(llm_client=client)

    task = Task(
        content="Research the best practices for Python async programming",
        user_id="test-user",
    )

    try:
        result = await router.route(task)
        print(f"Intent: {result.intent}")
        print(f"Risk: {result.risk}")
        print(f"Suggested Worker: {result.suggested_worker}")
        print(f"Confidence: {result.confidence}")
        print("SUCCESS")
        return True

    except Exception as e:
        print(f"ERROR: {e}")
        return False


async def test_meta_agent():
    """Test the meta agent creating a new agent"""
    print("\n" + "=" * 60)
    print("TEST 4: Meta Agent (Dynamic Agent Creation)")
    print("=" * 60)

    from app.engine.meta_agent import MetaAgent

    client = OpsCenterLLMClient()
    meta = MetaAgent(llm_client=client)

    try:
        agent = await meta.create_agent(
            description="An agent that helps users write unit tests for Python code",
            user_id="test-user",
        )

        print(f"Created Agent: {agent.name}")
        print(f"Description: {agent.description}")
        print(f"Capabilities: {agent.capabilities}")
        print(f"Tools: {agent.tools}")
        print("SUCCESS")
        return True

    except Exception as e:
        print(f"ERROR: {e}")
        return False


async def test_model_selector():
    """Test the model selector"""
    print("\n" + "=" * 60)
    print("TEST 5: Model Selector")
    print("=" * 60)

    from app.engine.model_benchmarks import ModelSelector

    selector = ModelSelector()

    test_cases = [
        ("research", "budget"),
        ("code", "standard"),
        ("extraction", "premium"),
    ]

    for task_type, budget in test_cases:
        model = selector.select_model(task_type, budget)
        print(f"  {task_type} ({budget}): {model}")

    print("SUCCESS")
    return True


async def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("UNICORN BRIGADE - REAL INFERENCE TESTS")
    print("=" * 60)

    results = []

    # Test 1: Basic completion
    results.append(("Basic Completion", await test_basic_completion()))

    # Test 2: List models
    results.append(("List Models", await test_list_models()))

    # Test 3: Router (requires working LLM)
    results.append(("Task Router", await test_router()))

    # Test 4: Meta Agent (requires working LLM)
    results.append(("Meta Agent", await test_meta_agent()))

    # Test 5: Model Selector (local, no LLM needed)
    results.append(("Model Selector", await test_model_selector()))

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    passed = sum(1 for _, r in results if r)
    total = len(results)

    for name, result in results:
        status = "PASS" if result else "FAIL"
        print(f"  {name}: {status}")

    print(f"\nTotal: {passed}/{total} passed")

    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
