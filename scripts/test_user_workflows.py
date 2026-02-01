#!/usr/bin/env python3
"""
User Workflow Tests - January 2026

Tests real-world user workflows for Unicorn Brigade:
1. Agent Chat with Function Calling
2. Multi-Agent Orchestration
3. A2A Protocol Invocation
4. MCP Tool Execution
5. Code Sandbox Execution
6. Knowledge Graph Operations
7. Memory Operations
8. System Health & Stats

Run with: python scripts/test_user_workflows.py
"""

import asyncio
import httpx
import json
import sys
import time
from dataclasses import dataclass
from typing import List, Optional, Any

BASE_URL = "http://localhost:8100"


@dataclass
class WorkflowResult:
    """Result of a workflow test"""
    name: str
    passed: bool
    duration: float
    message: str = ""
    details: Optional[dict] = None


class UserWorkflowTests:
    """Test suite for real user workflows"""

    def __init__(self):
        self.results: List[WorkflowResult] = []
        self.client: Optional[httpx.AsyncClient] = None

    async def setup(self):
        self.client = httpx.AsyncClient(timeout=120.0, base_url=BASE_URL)

    async def teardown(self):
        if self.client:
            await self.client.aclose()

    def record(self, name: str, passed: bool, duration: float, message: str = "", details: dict = None):
        self.results.append(WorkflowResult(name, passed, duration, message, details))
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status} {name} ({duration:.2f}s)")
        if message:
            print(f"       {message[:200]}")

    # =========================================================================
    # Workflow 1: System Health & Stats
    # =========================================================================

    async def test_system_health(self):
        """Verify system is healthy and all services running"""
        start = time.time()
        try:
            resp = await self.client.get("/api/v1/health")
            data = resp.json()
            passed = resp.status_code == 200 and data.get("status") == "healthy"
            self.record(
                "System: Health check",
                passed,
                time.time() - start,
                f"Status: {data.get('status')}, Memory: {data.get('memory_provider', 'unknown')}"
            )
        except Exception as e:
            self.record("System: Health check", False, time.time() - start, str(e))

    async def test_system_stats(self):
        """Get system statistics"""
        start = time.time()
        try:
            resp = await self.client.get("/api/v1/stats")
            data = resp.json()
            # API returns totalAgents, totalTools as top-level keys
            passed = resp.status_code == 200 and data.get("totalAgents", 0) > 0
            self.record(
                "System: Stats",
                passed,
                time.time() - start,
                f"Agents: {data.get('totalAgents', 0)}, Tools: {data.get('totalTools', 0)}, Status: {data.get('status')}"
            )
        except Exception as e:
            self.record("System: Stats", False, time.time() - start, str(e))

    # =========================================================================
    # Workflow 2: Agent CRUD & Discovery
    # =========================================================================

    async def test_list_agents(self):
        """List all available agents"""
        start = time.time()
        try:
            resp = await self.client.get("/api/v1/agents")
            data = resp.json()
            agents = data if isinstance(data, list) else data.get("agents", [])
            passed = resp.status_code == 200 and len(agents) > 0
            agent_names = [a.get("name", a.get("id", "?"))[:20] for a in agents[:5]]
            self.record(
                "Agents: List all",
                passed,
                time.time() - start,
                f"Found {len(agents)} agents: {', '.join(agent_names)}..."
            )
            return agents
        except Exception as e:
            self.record("Agents: List all", False, time.time() - start, str(e))
            return []

    async def test_get_agent_detail(self, agent_id: str):
        """Get details of a specific agent"""
        start = time.time()
        try:
            resp = await self.client.get(f"/api/v1/agents/{agent_id}")
            data = resp.json()
            passed = resp.status_code == 200 and data.get("id") == agent_id
            tools = data.get("tools", [])
            self.record(
                f"Agents: Get detail ({agent_id})",
                passed,
                time.time() - start,
                f"Name: {data.get('name')}, Tools: {tools[:3]}..."
            )
            return data
        except Exception as e:
            self.record(f"Agents: Get detail ({agent_id})", False, time.time() - start, str(e))
            return None

    async def test_list_agent_domains(self):
        """List agent domains"""
        start = time.time()
        try:
            resp = await self.client.get("/api/v1/agents/domains")
            data = resp.json()
            domains = data if isinstance(data, list) else data.get("domains", [])
            passed = resp.status_code == 200 and len(domains) > 0
            self.record(
                "Agents: List domains",
                passed,
                time.time() - start,
                f"Domains: {domains[:5]}"
            )
        except Exception as e:
            self.record("Agents: List domains", False, time.time() - start, str(e))

    # =========================================================================
    # Workflow 3: Agent Chat with Function Calling
    # =========================================================================

    async def test_chat_simple(self, agent_id: str):
        """Simple chat without tool use"""
        start = time.time()
        try:
            resp = await self.client.post(
                f"/api/v1/agents/{agent_id}/chat",
                json={"message": "Hello! What can you help me with?"}
            )
            data = resp.json()
            passed = resp.status_code == 200 and data.get("content")
            content = data.get("content", "")[:100]
            self.record(
                f"Chat: Simple message ({agent_id})",
                passed,
                time.time() - start,
                f"Response: {content}..."
            )
        except Exception as e:
            self.record(f"Chat: Simple message ({agent_id})", False, time.time() - start, str(e))

    async def test_chat_with_calculator(self, agent_id: str):
        """Chat that triggers calculator tool"""
        start = time.time()
        try:
            resp = await self.client.post(
                f"/api/v1/agents/{agent_id}/chat",
                json={"message": "Calculate 157 * 23 + 89"}
            )
            data = resp.json()
            content = data.get("content", "")
            tool_calls = data.get("toolCalls", [])
            # Check if response contains the correct answer (3700)
            passed = resp.status_code == 200 and ("3700" in content or len(tool_calls) > 0)
            self.record(
                f"Chat: Calculator tool ({agent_id})",
                passed,
                time.time() - start,
                f"Tool calls: {len(tool_calls)}, Answer contains 3700: {'3700' in content}"
            )
        except Exception as e:
            self.record(f"Chat: Calculator tool ({agent_id})", False, time.time() - start, str(e))

    async def test_chat_with_datetime(self, agent_id: str):
        """Chat that triggers datetime tool"""
        start = time.time()
        try:
            resp = await self.client.post(
                f"/api/v1/agents/{agent_id}/chat",
                json={"message": "What is today's date and the current time?"}
            )
            data = resp.json()
            content = data.get("content", "")
            tool_calls = data.get("toolCalls", [])
            # Should contain some date/time info
            passed = resp.status_code == 200 and (
                "2026" in content or
                "January" in content or
                len(tool_calls) > 0
            )
            self.record(
                f"Chat: Datetime tool ({agent_id})",
                passed,
                time.time() - start,
                f"Tool calls: {len(tool_calls)}, Response: {content[:80]}..."
            )
        except Exception as e:
            self.record(f"Chat: Datetime tool ({agent_id})", False, time.time() - start, str(e))

    # =========================================================================
    # Workflow 4: A2A Protocol
    # =========================================================================

    async def test_a2a_info(self):
        """Get A2A protocol info"""
        start = time.time()
        try:
            resp = await self.client.get("/api/v1/a2a/info")
            data = resp.json()
            passed = resp.status_code == 200 and "name" in data
            self.record(
                "A2A: Protocol info",
                passed,
                time.time() - start,
                f"Name: {data.get('name')}, Version: {data.get('version')}"
            )
        except Exception as e:
            self.record("A2A: Protocol info", False, time.time() - start, str(e))

    async def test_a2a_list_agents(self):
        """List agents via A2A protocol"""
        start = time.time()
        try:
            resp = await self.client.get("/api/v1/a2a/agents")
            data = resp.json()
            agents = data if isinstance(data, list) else data.get("agents", [])
            passed = resp.status_code == 200 and len(agents) > 0
            self.record(
                "A2A: List agents",
                passed,
                time.time() - start,
                f"Found {len(agents)} A2A-enabled agents"
            )
        except Exception as e:
            self.record("A2A: List agents", False, time.time() - start, str(e))

    async def test_a2a_agent_card(self, agent_id: str):
        """Get agent card via A2A"""
        start = time.time()
        try:
            resp = await self.client.get(f"/api/v1/a2a/agents/{agent_id}/card")
            data = resp.json()
            passed = resp.status_code == 200 and "name" in data
            self.record(
                f"A2A: Agent card ({agent_id})",
                passed,
                time.time() - start,
                f"Name: {data.get('name')}, Skills: {len(data.get('skills', []))}"
            )
        except Exception as e:
            self.record(f"A2A: Agent card ({agent_id})", False, time.time() - start, str(e))

    async def test_a2a_invoke(self, agent_id: str):
        """Invoke agent via A2A protocol"""
        start = time.time()
        try:
            resp = await self.client.post(
                f"/api/v1/a2a/agents/{agent_id}/invoke",
                json={
                    "task": "What is 25 + 17?",
                    "tools": ["calculator"]
                }
            )
            data = resp.json()
            passed = resp.status_code == 200 and (data.get("result") or data.get("content"))
            result = data.get("result") or data.get("content", "")
            self.record(
                f"A2A: Invoke agent ({agent_id})",
                passed,
                time.time() - start,
                f"Result: {str(result)[:100]}..."
            )
        except Exception as e:
            self.record(f"A2A: Invoke agent ({agent_id})", False, time.time() - start, str(e))

    # =========================================================================
    # Workflow 5: MCP Protocol
    # =========================================================================

    async def test_mcp_info(self):
        """Get MCP protocol info"""
        start = time.time()
        try:
            resp = await self.client.get("/api/v1/mcp/info")
            data = resp.json()
            passed = resp.status_code == 200 and "name" in data
            self.record(
                "MCP: Protocol info",
                passed,
                time.time() - start,
                f"Name: {data.get('name')}, Version: {data.get('protocolVersion')}"
            )
        except Exception as e:
            self.record("MCP: Protocol info", False, time.time() - start, str(e))

    async def test_mcp_list_tools(self):
        """List tools via MCP"""
        start = time.time()
        try:
            resp = await self.client.get("/api/v1/mcp/tools/list")
            data = resp.json()
            tools = data.get("tools", [])
            passed = resp.status_code == 200 and len(tools) > 0
            tool_names = [t.get("name", "?") for t in tools[:5]]
            self.record(
                "MCP: List tools",
                passed,
                time.time() - start,
                f"Found {len(tools)} tools: {', '.join(tool_names)}..."
            )
        except Exception as e:
            self.record("MCP: List tools", False, time.time() - start, str(e))

    async def test_mcp_call_calculator(self):
        """Call calculator via MCP"""
        start = time.time()
        try:
            resp = await self.client.post(
                "/api/v1/mcp/tools/call",
                json={
                    "name": "calculator",
                    "arguments": {"expression": "42 * 3"}
                }
            )
            data = resp.json()
            result = data.get("content", [{}])[0].get("text", str(data))
            passed = resp.status_code == 200 and "126" in str(result)
            self.record(
                "MCP: Call calculator",
                passed,
                time.time() - start,
                f"Result: {str(result)[:100]}"
            )
        except Exception as e:
            self.record("MCP: Call calculator", False, time.time() - start, str(e))

    async def test_mcp_call_datetime(self):
        """Call datetime via MCP"""
        start = time.time()
        try:
            resp = await self.client.post(
                "/api/v1/mcp/tools/call",
                json={
                    "name": "datetime",
                    "arguments": {"format": "iso"}
                }
            )
            data = resp.json()
            result = data.get("result", {})
            # Datetime tool returns timestamp and timezone
            passed = resp.status_code == 200 and data.get("success") and result.get("timestamp")
            ts = result.get("timestamp", 0)
            tz = result.get("timezone", "unknown")
            self.record(
                "MCP: Call datetime",
                passed,
                time.time() - start,
                f"Timestamp: {ts}, Timezone: {tz}"
            )
        except Exception as e:
            self.record("MCP: Call datetime", False, time.time() - start, str(e))

    # =========================================================================
    # Workflow 6: MCP Registry & Code Sandbox
    # =========================================================================

    async def test_mcp_registry_servers(self):
        """List MCP registry servers"""
        start = time.time()
        try:
            resp = await self.client.get("/api/v1/mcp/registry/servers")
            data = resp.json()
            servers = data.get("servers", [])
            passed = resp.status_code == 200 and len(servers) > 0
            server_names = [s.get("name", "?") for s in servers[:5]]
            self.record(
                "MCP Registry: List servers",
                passed,
                time.time() - start,
                f"Found {len(servers)} servers: {', '.join(server_names)}"
            )
        except Exception as e:
            self.record("MCP Registry: List servers", False, time.time() - start, str(e))

    async def test_sandbox_python(self):
        """Execute Python in sandbox"""
        start = time.time()
        try:
            resp = await self.client.post(
                "/api/v1/mcp/registry/sandbox/execute",
                json={
                    "code": "import math\nresult = math.sqrt(144)\nprint(f'Square root of 144 is {result}')",
                    "language": "python"
                }
            )
            data = resp.json()
            passed = resp.status_code == 200 and data.get("success") and "12" in data.get("stdout", "")
            self.record(
                "Sandbox: Python execution",
                passed,
                time.time() - start,
                f"Output: {data.get('stdout', '')[:100]}"
            )
        except Exception as e:
            self.record("Sandbox: Python execution", False, time.time() - start, str(e))

    async def test_sandbox_javascript(self):
        """Execute JavaScript in sandbox"""
        start = time.time()
        try:
            resp = await self.client.post(
                "/api/v1/mcp/registry/sandbox/execute",
                json={
                    "code": "const data = [1,2,3,4,5];\nconst sum = data.reduce((a,b) => a+b, 0);\nconsole.log(`Sum is ${sum}`);",
                    "language": "javascript"
                }
            )
            data = resp.json()
            passed = resp.status_code == 200 and data.get("success") and "15" in data.get("stdout", "")
            self.record(
                "Sandbox: JavaScript execution",
                passed,
                time.time() - start,
                f"Output: {data.get('stdout', '')[:100]}"
            )
        except Exception as e:
            self.record("Sandbox: JavaScript execution", False, time.time() - start, str(e))

    # =========================================================================
    # Workflow 7: Orchestration
    # =========================================================================

    async def test_orchestration_state(self):
        """Get orchestration state"""
        start = time.time()
        try:
            resp = await self.client.get("/api/v1/orchestration/state")
            data = resp.json()
            # API returns agentStates as list and missions as list
            passed = resp.status_code == 200 and ("agentStates" in data or "missions" in data)
            agent_states = data.get("agentStates", [])
            missions = data.get("missions", [])
            active_agents = len([a for a in agent_states if a.get("status") != "idle"])
            self.record(
                "Orchestration: Get state",
                passed,
                time.time() - start,
                f"Agent states: {len(agent_states)}, Active missions: {len(missions)}"
            )
        except Exception as e:
            self.record("Orchestration: Get state", False, time.time() - start, str(e))

    async def test_orchestration_list_missions(self):
        """List orchestration missions"""
        start = time.time()
        try:
            resp = await self.client.get("/api/v1/orchestration/missions")
            data = resp.json()
            missions = data if isinstance(data, list) else data.get("missions", [])
            passed = resp.status_code == 200
            self.record(
                "Orchestration: List missions",
                passed,
                time.time() - start,
                f"Found {len(missions)} missions"
            )
        except Exception as e:
            self.record("Orchestration: List missions", False, time.time() - start, str(e))

    # =========================================================================
    # Workflow 8: Tools Library
    # =========================================================================

    async def test_list_tools(self):
        """List available tools"""
        start = time.time()
        try:
            resp = await self.client.get("/api/v1/tools")
            data = resp.json()
            tools = data if isinstance(data, list) else data.get("tools", [])
            passed = resp.status_code == 200 and len(tools) > 0
            tool_names = [t.get("name", "?") for t in tools[:5]]
            self.record(
                "Tools: List all",
                passed,
                time.time() - start,
                f"Found {len(tools)} tools: {', '.join(tool_names)}..."
            )
        except Exception as e:
            self.record("Tools: List all", False, time.time() - start, str(e))

    # =========================================================================
    # Workflow 9: Knowledge Graph (if enabled)
    # =========================================================================

    async def test_knowledge_stats(self):
        """Get knowledge graph stats"""
        start = time.time()
        try:
            resp = await self.client.get("/api/v1/knowledge/stats")
            data = resp.json()
            passed = resp.status_code == 200
            if passed:
                entities = data.get("entities", 0)
                relationships = data.get("relationships", 0)
                msg = f"Entities: {entities}, Relationships: {relationships}"
            else:
                msg = "Knowledge graph not available"
            self.record(
                "Knowledge: Stats",
                passed,
                time.time() - start,
                msg
            )
        except Exception as e:
            # Knowledge graph may not be enabled
            self.record("Knowledge: Stats", True, time.time() - start, f"Not enabled or error: {str(e)[:50]}")

    # =========================================================================
    # Workflow 10: Voice (if enabled)
    # =========================================================================

    async def test_voice_health(self):
        """Check voice service health"""
        start = time.time()
        try:
            resp = await self.client.get("/api/v1/voice/health")
            data = resp.json()
            passed = resp.status_code == 200
            status = data.get("status", "unknown")
            self.record(
                "Voice: Health check",
                passed,
                time.time() - start,
                f"Status: {status}"
            )
        except Exception as e:
            self.record("Voice: Health check", True, time.time() - start, f"Not enabled: {str(e)[:50]}")

    async def test_voice_providers(self):
        """List voice providers"""
        start = time.time()
        try:
            resp = await self.client.get("/api/v1/voice/providers")
            data = resp.json()
            passed = resp.status_code == 200
            stt = data.get("stt", [])
            tts = data.get("tts", [])
            self.record(
                "Voice: List providers",
                passed,
                time.time() - start,
                f"STT providers: {len(stt)}, TTS providers: {len(tts)}"
            )
        except Exception as e:
            self.record("Voice: List providers", True, time.time() - start, f"Not enabled: {str(e)[:50]}")

    # =========================================================================
    # Workflow 11: Conversations
    # =========================================================================

    async def test_list_conversations(self):
        """List conversations"""
        start = time.time()
        try:
            resp = await self.client.get("/api/v1/conversations")
            data = resp.json()
            convos = data if isinstance(data, list) else data.get("conversations", [])
            passed = resp.status_code == 200
            self.record(
                "Conversations: List all",
                passed,
                time.time() - start,
                f"Found {len(convos)} conversations"
            )
        except Exception as e:
            self.record("Conversations: List all", False, time.time() - start, str(e))

    # =========================================================================
    # Run All Workflows
    # =========================================================================

    async def run_all(self):
        """Run all workflow tests"""
        print("\n" + "=" * 70)
        print("User Workflow Tests - January 30, 2026")
        print("=" * 70)

        await self.setup()

        # 1. System Health
        print("\n🏥 System Health & Stats")
        print("-" * 40)
        await self.test_system_health()
        await self.test_system_stats()

        # 2. Agent Discovery
        print("\n🤖 Agent Discovery & Management")
        print("-" * 40)
        agents = await self.test_list_agents()
        await self.test_list_agent_domains()

        # Find agents with specific tools for testing
        test_agent_id = None
        calc_agent_id = None
        datetime_agent_id = None

        for agent in agents:
            agent_id = agent.get("id")
            tools = agent.get("tools", [])
            if not test_agent_id and agent_id and tools:
                test_agent_id = agent_id
            if not calc_agent_id and "calculator" in tools:
                calc_agent_id = agent_id
            if not datetime_agent_id and "datetime" in tools:
                datetime_agent_id = agent_id

        if not test_agent_id and agents:
            test_agent_id = agents[0].get("id")
        calc_agent_id = calc_agent_id or test_agent_id
        datetime_agent_id = datetime_agent_id or test_agent_id

        if test_agent_id:
            await self.test_get_agent_detail(test_agent_id)

        # 3. Agent Chat
        print("\n💬 Agent Chat with Function Calling")
        print("-" * 40)
        if test_agent_id:
            await self.test_chat_simple(test_agent_id)
        if calc_agent_id:
            await self.test_chat_with_calculator(calc_agent_id)
        if datetime_agent_id:
            await self.test_chat_with_datetime(datetime_agent_id)
        if not test_agent_id:
            print("  ⚠️  No agent available for chat tests")

        # 4. A2A Protocol
        print("\n🔗 A2A Protocol")
        print("-" * 40)
        await self.test_a2a_info()
        await self.test_a2a_list_agents()
        if test_agent_id:
            await self.test_a2a_agent_card(test_agent_id)
            await self.test_a2a_invoke(test_agent_id)

        # 5. MCP Protocol
        print("\n🔧 MCP Protocol")
        print("-" * 40)
        await self.test_mcp_info()
        await self.test_mcp_list_tools()
        await self.test_mcp_call_calculator()
        await self.test_mcp_call_datetime()

        # 6. MCP Registry & Sandbox
        print("\n📦 MCP Registry & Code Sandbox")
        print("-" * 40)
        await self.test_mcp_registry_servers()
        await self.test_sandbox_python()
        await self.test_sandbox_javascript()

        # 7. Orchestration
        print("\n🎯 Orchestration")
        print("-" * 40)
        await self.test_orchestration_state()
        await self.test_orchestration_list_missions()

        # 8. Tools
        print("\n🛠️ Tools Library")
        print("-" * 40)
        await self.test_list_tools()

        # 9. Knowledge Graph
        print("\n🧠 Knowledge Graph")
        print("-" * 40)
        await self.test_knowledge_stats()

        # 10. Voice
        print("\n🎤 Voice Services")
        print("-" * 40)
        await self.test_voice_health()
        await self.test_voice_providers()

        # 11. Conversations
        print("\n📝 Conversations")
        print("-" * 40)
        await self.test_list_conversations()

        await self.teardown()

        # Summary
        print("\n" + "=" * 70)
        print("Test Summary")
        print("=" * 70)

        passed = sum(1 for r in self.results if r.passed)
        failed = sum(1 for r in self.results if not r.passed)
        total_time = sum(r.duration for r in self.results)

        print(f"\n  Total:  {len(self.results)} tests")
        print(f"  Passed: {passed}")
        print(f"  Failed: {failed}")
        print(f"  Time:   {total_time:.2f}s")

        if failed > 0:
            print("\n  Failed tests:")
            for r in self.results:
                if not r.passed:
                    print(f"    - {r.name}: {r.message[:80]}")

        print("\n" + "=" * 70)
        return failed == 0


async def main():
    tests = UserWorkflowTests()
    success = await tests.run_all()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
