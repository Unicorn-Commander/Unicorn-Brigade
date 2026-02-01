#!/usr/bin/env python3
"""
Unicorn Brigade - Quick Demo

Interactive demo showing the main capabilities:
1. Chat with agents
2. Use tools (calculator, web search, datetime)
3. Memory operations
4. Protocol invocations (MCP, A2A)

Run: python scripts/demo.py
"""

import asyncio
import httpx
import json
from datetime import datetime

API_BASE = "http://localhost:8100"
API_V1 = f"{API_BASE}/api/v1"


def print_header(title: str):
    """Print a section header"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def print_response(data: dict, indent: int = 2):
    """Pretty print a response"""
    print(json.dumps(data, indent=indent, default=str)[:1000])


async def demo_chat(client: httpx.AsyncClient):
    """Demo basic chat with an agent"""
    print_header("1. Chat with Agent (pvt-assist)")

    response = await client.post(
        f"{API_V1}/agents/pvt-assist/chat",
        json={
            "message": "Hello! What can you help me with?",
            "userId": "demo-user"
        }
    )
    data = response.json()
    print(f"User: Hello! What can you help me with?")
    print(f"\nAgent: {data.get('content', data)[:500]}...")
    return True


async def demo_calculator(client: httpx.AsyncClient):
    """Demo calculator tool"""
    print_header("2. Calculator Tool (col-finance)")

    response = await client.post(
        f"{API_V1}/agents/col-finance/chat",
        json={
            "message": "Calculate 15% of $2,500 using your calculator tool",
            "userId": "demo-user"
        }
    )
    data = response.json()
    print(f"User: Calculate 15% of $2,500 using your calculator tool")
    print(f"\nAgent: {data.get('content', data)[:500]}")

    tool_calls = data.get("toolCalls", [])
    if tool_calls:
        print(f"\nTool Used: {tool_calls[0].get('name', 'calculator')}")
        print(f"Result: {tool_calls[0].get('result', {})}")
    return True


async def demo_web_search(client: httpx.AsyncClient):
    """Demo web search tool"""
    print_header("3. Web Search Tool (col-finance)")

    response = await client.post(
        f"{API_V1}/agents/col-finance/chat",
        json={
            "message": "Search for the latest S&P 500 performance news",
            "userId": "demo-user"
        }
    )
    data = response.json()
    print(f"User: Search for the latest S&P 500 performance news")
    print(f"\nAgent: {data.get('content', data)[:600]}...")

    tool_calls = data.get("toolCalls", [])
    if tool_calls:
        print(f"\nTool Used: web_search")
    return True


async def demo_datetime(client: httpx.AsyncClient):
    """Demo datetime tool"""
    print_header("4. Datetime Tool (pvt-assist)")

    response = await client.post(
        f"{API_V1}/agents/pvt-assist/chat",
        json={
            "message": "What's the current date and time? Use your datetime tool.",
            "userId": "demo-user"
        }
    )
    data = response.json()
    print(f"User: What's the current date and time?")
    print(f"\nAgent: {data.get('content', data)[:300]}")
    return True


async def demo_mcp_tool(client: httpx.AsyncClient):
    """Demo MCP protocol tool call"""
    print_header("5. MCP Protocol - Direct Tool Call")

    response = await client.post(
        f"{API_V1}/mcp/request",
        json={
            "method": "tools/call",
            "params": {
                "name": "calculator",
                "arguments": {"expression": "100 * 1.15"}
            }
        }
    )
    data = response.json()
    print(f"MCP tools/call: calculator(100 * 1.15)")
    print(f"Result: {data.get('result', data)}")
    return True


async def demo_a2a_invoke(client: httpx.AsyncClient):
    """Demo A2A protocol agent invocation"""
    print_header("6. A2A Protocol - Agent Invocation")

    response = await client.post(
        f"{API_V1}/a2a/agents/col-finance/invoke",
        json={
            "task": "What are the key metrics to evaluate a stock's performance?",
            "tools": []
        }
    )
    data = response.json()
    print(f"A2A invoke col-finance: Key stock metrics question")
    print(f"\nResponse: {data.get('result', data.get('content', data))[:500]}...")
    return True


async def demo_list_agents(client: httpx.AsyncClient):
    """Demo listing all available agents"""
    print_header("7. Available Agents")

    response = await client.get(f"{API_V1}/agents")
    data = response.json()
    agents = data.get("agents", data)

    print(f"Found {len(agents)} agents:\n")
    for agent in agents[:10]:
        print(f"  - {agent.get('id')}: {agent.get('title', agent.get('name'))}")
        print(f"    Domain: {agent.get('domain')} | Tools: {', '.join(agent.get('tools', [])[:3])}")

    if len(agents) > 10:
        print(f"  ... and {len(agents) - 10} more")
    return True


async def demo_orchestration(client: httpx.AsyncClient):
    """Demo orchestration state"""
    print_header("8. Orchestration State")

    response = await client.get(f"{API_V1}/orchestration/state")
    data = response.json()

    states = data.get("agentStates", [])
    missions = data.get("missions", [])

    print(f"Active agent states: {len(states)}")
    print(f"Active missions: {len(missions)}")

    if states:
        for state in states[:3]:
            print(f"\n  Agent: {state.get('agentName', state.get('agentId'))}")
            print(f"  Status: {state.get('status')}")
            print(f"  Last Activity: {state.get('lastActivity')}")
    return True


async def run_demo():
    """Run all demo sections"""
    print("\n" + "="*60)
    print("       UNICORN BRIGADE - INTERACTIVE DEMO")
    print("="*60)
    print(f"\nStarted at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"API Base: {API_BASE}")

    async with httpx.AsyncClient(timeout=60.0) as client:
        # Check health first
        try:
            r = await client.get(f"{API_V1}/health")
            if r.status_code != 200:
                print("\nERROR: Backend not healthy. Start with: uvicorn app.main:app --port 8100")
                return
        except Exception as e:
            print(f"\nERROR: Cannot connect to backend: {e}")
            print("Start with: uvicorn app.main:app --port 8100")
            return

        demos = [
            ("Chat", demo_chat),
            ("Calculator", demo_calculator),
            ("Datetime", demo_datetime),
            ("Web Search", demo_web_search),
            ("MCP", demo_mcp_tool),
            ("A2A", demo_a2a_invoke),
            ("Agents", demo_list_agents),
            ("Orchestration", demo_orchestration),
        ]

        for name, demo_func in demos:
            try:
                await demo_func(client)
            except Exception as e:
                print(f"\nDemo '{name}' failed: {e}")

    print_header("DEMO COMPLETE")
    print("The Unicorn Brigade is ready for action!")
    print("\nNext steps:")
    print("  - Frontend: cd frontend && npm run dev")
    print("  - API Docs: http://localhost:8100/docs")
    print("  - Run tests: python scripts/test_workflows.py")


if __name__ == "__main__":
    asyncio.run(run_demo())
