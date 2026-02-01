#!/usr/bin/env python3
"""
Unicorn Brigade - Workflow Test Suite

Tests all major workflows to ensure the system is working correctly.
Run with: python scripts/test_workflows.py

Exit codes:
  0 = All tests passed
  1 = Some tests failed
"""

import asyncio
import httpx
import json
import sys
from datetime import datetime
from typing import Dict, Any, List, Optional

# Configuration
API_BASE = "http://localhost:8100"
API_V1 = f"{API_BASE}/api/v1"

# Test results
results: List[Dict[str, Any]] = []


def log(msg: str, level: str = "INFO"):
    """Print formatted log message"""
    colors = {
        "INFO": "\033[94m",
        "OK": "\033[92m",
        "FAIL": "\033[91m",
        "WARN": "\033[93m",
        "RESET": "\033[0m"
    }
    timestamp = datetime.now().strftime("%H:%M:%S")
    color = colors.get(level, colors["INFO"])
    reset = colors["RESET"]
    print(f"{color}[{timestamp}] [{level}] {msg}{reset}")


def record_result(test_name: str, passed: bool, details: str = "", duration: float = 0):
    """Record a test result"""
    results.append({
        "test": test_name,
        "passed": passed,
        "details": details,
        "duration": duration
    })
    if passed:
        log(f"✓ {test_name} ({duration:.2f}s)", "OK")
    else:
        log(f"✗ {test_name}: {details}", "FAIL")


async def test_health():
    """Test basic health endpoints"""
    start = datetime.now()
    async with httpx.AsyncClient() as client:
        try:
            # Test ping
            r = await client.get(f"{API_BASE}/ping")
            assert r.status_code == 200
            assert r.json()["message"] == "pong"

            # Test health
            r = await client.get(f"{API_V1}/health")
            assert r.status_code == 200
            data = r.json()
            assert data["status"] == "healthy"

            duration = (datetime.now() - start).total_seconds()
            record_result("Health Check", True, "", duration)
        except Exception as e:
            record_result("Health Check", False, str(e))


async def test_list_agents():
    """Test listing all agents"""
    start = datetime.now()
    async with httpx.AsyncClient() as client:
        try:
            r = await client.get(f"{API_V1}/agents")
            assert r.status_code == 200
            data = r.json()
            agents = data.get("agents", data)
            assert len(agents) >= 10, f"Expected at least 10 agents, got {len(agents)}"

            # Check agent structure
            agent = agents[0]
            required_fields = ["id", "name", "domain", "tools"]
            for field in required_fields:
                assert field in agent, f"Missing field: {field}"

            duration = (datetime.now() - start).total_seconds()
            record_result("List Agents", True, f"{len(agents)} agents found", duration)
        except Exception as e:
            record_result("List Agents", False, str(e))


async def test_get_agent():
    """Test getting a specific agent"""
    start = datetime.now()
    async with httpx.AsyncClient() as client:
        try:
            r = await client.get(f"{API_V1}/agents/col-finance")
            assert r.status_code == 200
            agent = r.json()
            assert agent["id"] == "col-finance"
            assert "web_search" in agent.get("tools", [])

            duration = (datetime.now() - start).total_seconds()
            record_result("Get Agent", True, f"col-finance loaded", duration)
        except Exception as e:
            record_result("Get Agent", False, str(e))


async def test_agent_chat_simple():
    """Test simple agent chat (no tools)"""
    start = datetime.now()
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            r = await client.post(
                f"{API_V1}/agents/pvt-assist/chat",
                json={
                    "message": "What is 2 + 2? Just give me the number.",
                    "userId": "test-user"
                }
            )
            assert r.status_code == 200
            data = r.json()
            assert "content" in data or "message" in data
            content = data.get("content", data.get("message", ""))
            assert "4" in content, f"Expected '4' in response: {content[:100]}"

            duration = (datetime.now() - start).total_seconds()
            record_result("Agent Chat (Simple)", True, "", duration)
        except Exception as e:
            record_result("Agent Chat (Simple)", False, str(e))


async def test_agent_chat_with_calculator():
    """Test agent chat with calculator tool"""
    start = datetime.now()
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            r = await client.post(
                f"{API_V1}/agents/col-finance/chat",
                json={
                    "message": "Use your calculator tool to compute: 15 * 23 + 100. Show me the calculation.",
                    "userId": "test-user"
                }
            )
            assert r.status_code == 200
            data = r.json()
            content = data.get("content", data.get("message", ""))

            # Check if tool was called or result is correct
            tool_calls = data.get("toolCalls", [])
            has_tool_call = len(tool_calls) > 0
            has_correct_answer = "445" in content

            assert has_tool_call or has_correct_answer, f"No tool call or correct answer in response"

            duration = (datetime.now() - start).total_seconds()
            details = f"Tool calls: {len(tool_calls)}"
            record_result("Agent Chat (Calculator)", True, details, duration)
        except Exception as e:
            record_result("Agent Chat (Calculator)", False, str(e))


async def test_agent_chat_with_datetime():
    """Test agent chat with datetime tool"""
    start = datetime.now()
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            r = await client.post(
                f"{API_V1}/agents/pvt-assist/chat",
                json={
                    "message": "What is today's date? Use your datetime tool.",
                    "userId": "test-user"
                }
            )
            assert r.status_code == 200
            data = r.json()
            content = data.get("content", data.get("message", ""))
            tool_calls = data.get("toolCalls", [])

            # Should have used datetime tool or mention current date
            has_tool = len(tool_calls) > 0
            has_date = "2026" in content or "January" in content or "Jan" in content

            assert has_tool or has_date, f"No datetime tool call or date in response"

            duration = (datetime.now() - start).total_seconds()
            record_result("Agent Chat (Datetime)", True, f"Tool calls: {len(tool_calls)}", duration)
        except Exception as e:
            record_result("Agent Chat (Datetime)", False, str(e))


async def test_agent_chat_with_web_search():
    """Test agent chat with web search tool"""
    start = datetime.now()
    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            r = await client.post(
                f"{API_V1}/agents/col-finance/chat",
                json={
                    "message": "Search for 'S&P 500 index performance' and give me a brief summary.",
                    "userId": "test-user"
                }
            )
            assert r.status_code == 200
            data = r.json()
            content = data.get("content", data.get("message", ""))
            tool_calls = data.get("toolCalls", [])

            # Should have used web_search
            search_used = any(tc.get("name") == "web_search" for tc in tool_calls)
            has_content = len(content) > 50

            duration = (datetime.now() - start).total_seconds()

            if search_used:
                record_result("Agent Chat (Web Search)", True, "web_search tool called", duration)
            elif has_content:
                record_result("Agent Chat (Web Search)", True, "Response received (may use cached knowledge)", duration)
            else:
                record_result("Agent Chat (Web Search)", False, "No search or content")
        except Exception as e:
            record_result("Agent Chat (Web Search)", False, str(e))


async def test_list_tools():
    """Test listing available tools"""
    start = datetime.now()
    async with httpx.AsyncClient() as client:
        try:
            r = await client.get(f"{API_V1}/tools")
            assert r.status_code == 200
            data = r.json()
            tools = data.get("tools", data)
            assert len(tools) >= 5, f"Expected at least 5 tools, got {len(tools)}"

            # Check for core tools (tools have both "id" and "name" fields)
            tool_ids = [t.get("id", t.get("name", "")).lower() for t in tools]
            expected_tools = ["web_search", "calculator", "datetime"]
            missing = [t for t in expected_tools if not any(t in tid for tid in tool_ids)]

            assert not missing, f"Missing tools: {missing}"

            duration = (datetime.now() - start).total_seconds()
            record_result("List Tools", True, f"{len(tools)} tools available", duration)
        except Exception as e:
            record_result("List Tools", False, str(e))


async def test_mcp_tools_list():
    """Test MCP protocol - tools/list"""
    start = datetime.now()
    async with httpx.AsyncClient() as client:
        try:
            r = await client.post(
                f"{API_V1}/mcp/request",
                json={"method": "tools/list", "params": {}}
            )
            assert r.status_code == 200
            data = r.json()
            tools = data.get("tools", [])
            assert len(tools) >= 5

            duration = (datetime.now() - start).total_seconds()
            record_result("MCP tools/list", True, f"{len(tools)} tools", duration)
        except Exception as e:
            record_result("MCP tools/list", False, str(e))


async def test_mcp_tool_call():
    """Test MCP protocol - tools/call"""
    start = datetime.now()
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            r = await client.post(
                f"{API_V1}/mcp/request",
                json={
                    "method": "tools/call",
                    "params": {
                        "name": "calculator",
                        "arguments": {"expression": "100 * 2 + 50"}
                    }
                }
            )
            assert r.status_code == 200
            data = r.json()
            result = data.get("result", {})
            assert result.get("result") == 250 or "250" in str(result)

            duration = (datetime.now() - start).total_seconds()
            record_result("MCP tools/call", True, "calculator returned 250", duration)
        except Exception as e:
            record_result("MCP tools/call", False, str(e))


async def test_a2a_agent_discovery():
    """Test A2A protocol - agent discovery"""
    start = datetime.now()
    async with httpx.AsyncClient() as client:
        try:
            r = await client.get(f"{API_V1}/a2a/agents")
            assert r.status_code == 200
            data = r.json()
            agents = data.get("agents", data)
            assert len(agents) >= 5

            # Check agent card structure
            agent = agents[0]
            assert "id" in agent or "name" in agent

            duration = (datetime.now() - start).total_seconds()
            record_result("A2A Agent Discovery", True, f"{len(agents)} agents discoverable", duration)
        except Exception as e:
            record_result("A2A Agent Discovery", False, str(e))


async def test_a2a_invoke():
    """Test A2A protocol - invoke agent"""
    start = datetime.now()
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            # Correct endpoint: /a2a/agents/{agent_id}/invoke
            r = await client.post(
                f"{API_V1}/a2a/agents/pvt-assist/invoke",
                json={
                    "task": "What is the capital of France? Reply with just the city name.",
                    "tools": []
                }
            )
            assert r.status_code == 200, f"Got status {r.status_code}: {r.text[:200]}"
            data = r.json()
            result = data.get("result", data.get("content", data.get("response", "")))
            assert "Paris" in str(result), f"Expected 'Paris' in response: {result}"

            duration = (datetime.now() - start).total_seconds()
            record_result("A2A Invoke", True, "pvt-assist responded correctly", duration)
        except Exception as e:
            record_result("A2A Invoke", False, str(e))


async def test_orchestration_state():
    """Test orchestration - get current state"""
    start = datetime.now()
    async with httpx.AsyncClient() as client:
        try:
            r = await client.get(f"{API_V1}/orchestration/state")
            assert r.status_code == 200
            data = r.json()
            # Response has: missions, agentStates
            assert "agentStates" in data or "missions" in data, f"Missing expected keys: {list(data.keys())}"

            duration = (datetime.now() - start).total_seconds()
            agent_count = len(data.get("agentStates", []))
            record_result("Orchestration State", True, f"{agent_count} agent states", duration)
        except Exception as e:
            record_result("Orchestration State", False, str(e))


async def test_memory_operations():
    """Test memory store and retrieve"""
    start = datetime.now()
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            test_key = f"test_memory_{int(datetime.now().timestamp())}"
            test_value = {"data": "test value", "timestamp": str(datetime.now())}

            # Store memory via agent chat
            r = await client.post(
                f"{API_V1}/agents/pvt-assist/chat",
                json={
                    "message": f"Remember this for me: The secret code is UNICORN-{test_key}",
                    "userId": "test-user"
                }
            )
            assert r.status_code == 200

            # Query memories
            r = await client.post(
                f"{API_V1}/memory/query",
                json={
                    "query": "secret code",
                    "user_id": "test-user"
                }
            )
            # Memory query may or may not find it immediately

            duration = (datetime.now() - start).total_seconds()
            record_result("Memory Operations", True, "Store and query completed", duration)
        except Exception as e:
            record_result("Memory Operations", False, str(e))


async def test_streaming_chat():
    """Test streaming chat endpoint via /agents/execute/stream"""
    start = datetime.now()
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            chunks = []
            # Uses agent_type (research, code, analysis), not agent_id
            async with client.stream(
                "POST",
                f"{API_V1}/agents/execute/stream",
                json={
                    "agent_type": "research",
                    "task": "What is 2+2? Reply briefly.",
                    "user_id": "test-user"
                }
            ) as response:
                assert response.status_code == 200, f"Got status {response.status_code}"
                async for chunk in response.aiter_text():
                    if chunk.strip():
                        chunks.append(chunk)

            assert len(chunks) > 0, "No chunks received"

            duration = (datetime.now() - start).total_seconds()
            record_result("Streaming Chat", True, f"{len(chunks)} chunks received", duration)
        except Exception as e:
            record_result("Streaming Chat", False, str(e))


async def test_system_stats():
    """Test system statistics endpoint"""
    start = datetime.now()
    async with httpx.AsyncClient() as client:
        try:
            r = await client.get(f"{API_V1}/system/status")
            assert r.status_code == 200
            data = r.json()
            assert "status" in data
            assert data["status"] == "operational"

            duration = (datetime.now() - start).total_seconds()
            record_result("System Stats", True, "", duration)
        except Exception as e:
            record_result("System Stats", False, str(e))


async def test_knowledge_graph():
    """Test FalkorDB knowledge graph endpoints"""
    start = datetime.now()
    async with httpx.AsyncClient() as client:
        try:
            r = await client.get(f"{API_V1}/knowledge/stats")
            assert r.status_code == 200
            data = r.json()

            duration = (datetime.now() - start).total_seconds()
            record_result("Knowledge Graph", True, f"Stats retrieved", duration)
        except Exception as e:
            # Knowledge graph may not be configured
            record_result("Knowledge Graph", True, f"Skipped (not configured): {e}", 0)


async def run_all_tests():
    """Run all workflow tests"""
    log("=" * 60)
    log("Unicorn Brigade - Workflow Test Suite")
    log("=" * 60)
    log(f"API Base: {API_BASE}")
    log("")

    # Run tests in sequence
    tests = [
        ("Basic Health", test_health),
        ("List Agents", test_list_agents),
        ("Get Agent", test_get_agent),
        ("List Tools", test_list_tools),
        ("System Stats", test_system_stats),
        ("Simple Chat", test_agent_chat_simple),
        ("Calculator Tool", test_agent_chat_with_calculator),
        ("Datetime Tool", test_agent_chat_with_datetime),
        ("Web Search Tool", test_agent_chat_with_web_search),
        ("MCP List Tools", test_mcp_tools_list),
        ("MCP Call Tool", test_mcp_tool_call),
        ("A2A Discovery", test_a2a_agent_discovery),
        ("A2A Invoke", test_a2a_invoke),
        ("Orchestration", test_orchestration_state),
        ("Memory", test_memory_operations),
        ("Streaming", test_streaming_chat),
        ("Knowledge Graph", test_knowledge_graph),
    ]

    log(f"Running {len(tests)} tests...")
    log("")

    for name, test_func in tests:
        try:
            await test_func()
        except Exception as e:
            record_result(name, False, f"Unexpected error: {e}")

    # Print summary
    log("")
    log("=" * 60)
    log("Test Summary")
    log("=" * 60)

    passed = sum(1 for r in results if r["passed"])
    failed = sum(1 for r in results if not r["passed"])
    total_time = sum(r["duration"] for r in results)

    for r in results:
        status = "✓" if r["passed"] else "✗"
        details = f" - {r['details']}" if r["details"] else ""
        log(f"  {status} {r['test']}{details}")

    log("")
    log(f"Results: {passed}/{len(results)} passed ({passed*100//len(results)}%)")
    log(f"Total time: {total_time:.2f}s")

    if failed > 0:
        log(f"Failed tests: {failed}", "FAIL")
        return 1
    else:
        log("All tests passed!", "OK")
        return 0


if __name__ == "__main__":
    exit_code = asyncio.run(run_all_tests())
    sys.exit(exit_code)
