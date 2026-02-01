#!/usr/bin/env python3
"""
Test script for Agent Trace API endpoints.

This script demonstrates and tests all the Agent Trace endpoints:
- Recording code attributions
- Querying by file, agent, session
- Getting recent attributions
- Statistics
- Report generation
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.db.database import get_session
from app.db.repositories import CodeAttributionRepository


async def test_trace_api():
    """Test all trace API functionality"""
    print("=" * 80)
    print("Agent Trace API Test")
    print("=" * 80)

    # Get database session
    async for session in get_session():
        repo = CodeAttributionRepository(session)

        # Test 1: Create sample attributions
        print("\n1. Creating sample code attributions...")
        sample_attributions = [
            {
                "session_id": "test-session-001",
                "agent_id": "claude-sonnet",
                "agent_name": "Claude Sonnet 4.5",
                "model": "claude-sonnet-4-5-20250929",
                "file_path": "/app/api/trace_routes.py",
                "start_line": 1,
                "end_line": 50,
                "change_type": "generation",
                "prompt": "Create API routes for agent trace",
                "generated_code": "from fastapi import APIRouter\n\nrouter = APIRouter()\n",
                "metadata": {
                    "tokens": 1500,
                    "duration_ms": 2000,
                    "language": "python"
                }
            },
            {
                "session_id": "test-session-001",
                "agent_id": "claude-sonnet",
                "agent_name": "Claude Sonnet 4.5",
                "model": "claude-sonnet-4-5-20250929",
                "file_path": "/app/db/models.py",
                "start_line": 340,
                "end_line": 387,
                "change_type": "generation",
                "prompt": "Add CodeAttribution model",
                "generated_code": "class CodeAttribution(Base):\n    __tablename__ = 'code_attributions'\n",
                "metadata": {
                    "tokens": 2000,
                    "duration_ms": 3000,
                    "language": "python"
                }
            },
            {
                "session_id": "test-session-002",
                "agent_id": "gpt-4o",
                "agent_name": "GPT-4o",
                "model": "openai/gpt-4o",
                "file_path": "/app/api/trace_routes.py",
                "start_line": 51,
                "end_line": 75,
                "change_type": "edit",
                "prompt": "Update response model",
                "generated_code": "class AttributionResponse(BaseModel):\n    pass\n",
                "metadata": {
                    "tokens": 800,
                    "duration_ms": 1500,
                    "language": "python"
                }
            }
        ]

        created = []
        for attr_data in sample_attributions:
            attribution = await repo.create(attr_data)
            created.append(attribution)
            print(f"   Created: {attribution['filePath']} (lines {attribution['startLine']}-{attribution['endLine']})")

        print(f"\n   Total created: {len(created)}")

        # Test 2: Query by file
        print("\n2. Query attributions by file...")
        file_attributions = await repo.get_by_file("/app/api/trace_routes.py")
        print(f"   Found {len(file_attributions)} attribution(s) for /app/api/trace_routes.py")
        for attr in file_attributions:
            print(f"   - {attr['agentName']} ({attr['changeType']}): lines {attr['startLine']}-{attr['endLine']}")

        # Test 3: Query by agent
        print("\n3. Query attributions by agent...")
        agent_attributions = await repo.get_by_agent("claude-sonnet")
        print(f"   Found {len(agent_attributions)} attribution(s) for claude-sonnet")
        for attr in agent_attributions:
            print(f"   - {attr['filePath']}: lines {attr['startLine']}-{attr['endLine']}")

        # Test 4: Query by session
        print("\n4. Query attributions by session...")
        session_attributions = await repo.get_by_session("test-session-001")
        print(f"   Found {len(session_attributions)} attribution(s) for test-session-001")
        for attr in session_attributions:
            print(f"   - {attr['filePath']}: {attr['agentName']}")

        # Test 5: Get recent attributions
        print("\n5. Get recent attributions (last 1 day)...")
        recent = await repo.get_recent(days=1)
        print(f"   Found {len(recent)} recent attribution(s)")

        # Test 6: Get statistics
        print("\n6. Get attribution statistics...")
        stats = await repo.get_stats()
        print(f"   Total lines: {stats['totalLines']}")
        print(f"   Total attributions: {stats['totalAttributions']}")
        print(f"   Unique agents: {stats['uniqueAgents']}")
        print(f"   Unique files: {stats['uniqueFiles']}")
        print(f"   By operation: {stats['byOperation']}")
        print(f"\n   Top agents:")
        for agent in stats['topAgents']:
            print(f"   - {agent['agentName']}: {agent['totalLines']} lines ({agent['attributionCount']} attributions)")
        print(f"\n   Top files:")
        for file in stats['topFiles']:
            print(f"   - {file['filePath']}: {file['attributionCount']} attributions ({file['totalLines']} lines)")

        # Test 7: Search with filters
        print("\n7. Search with filters (agent + change type)...")
        search_results = await repo.search(
            agent_id="claude-sonnet",
            operation="generation"
        )
        print(f"   Found {len(search_results)} attribution(s) matching filters")

        print("\n" + "=" * 80)
        print("All tests completed successfully!")
        print("=" * 80)


async def test_http_endpoints():
    """Test HTTP endpoints using httpx"""
    import httpx

    print("\n" + "=" * 80)
    print("Testing HTTP Endpoints")
    print("=" * 80)

    base_url = "http://localhost:8100"
    headers = {
        "X-API-Key": "your-api-key-here"  # Replace with actual key
    }

    async with httpx.AsyncClient() as client:
        # Test health endpoint
        print("\n1. Testing /trace/health...")
        response = await client.get(f"{base_url}/api/v1/trace/health", headers=headers)
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            print(f"   Response: {response.json()}")

        # Test stats endpoint
        print("\n2. Testing /trace/stats...")
        response = await client.get(f"{base_url}/api/v1/trace/stats", headers=headers)
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            stats = response.json()
            print(f"   Total attributions: {stats.get('totalAttributions')}")
            print(f"   Total lines: {stats.get('totalLines')}")

        # Test recent endpoint
        print("\n3. Testing /trace/recent...")
        response = await client.get(f"{base_url}/api/v1/trace/recent?days=7", headers=headers)
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            recent = response.json()
            print(f"   Found {len(recent)} recent attributions")

        # Test report endpoint (JSON)
        print("\n4. Testing /trace/report (JSON)...")
        report_request = {
            "format": "json",
            "startDate": "2026-01-01"
        }
        response = await client.post(
            f"{base_url}/api/v1/trace/report",
            json=report_request,
            headers=headers
        )
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            report = response.json()
            print(f"   Report contains {report.get('totalAttributions')} attributions")

        # Test report endpoint (CSV)
        print("\n5. Testing /trace/report (CSV)...")
        report_request = {
            "format": "csv",
            "changeType": "generation"
        }
        response = await client.post(
            f"{base_url}/api/v1/trace/report",
            json=report_request,
            headers=headers
        )
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            csv_lines = response.text.split("\n")
            print(f"   CSV contains {len(csv_lines)} lines")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Test Agent Trace API")
    parser.add_argument(
        "--http",
        action="store_true",
        help="Test HTTP endpoints (requires running server)"
    )
    args = parser.parse_args()

    if args.http:
        asyncio.run(test_http_endpoints())
    else:
        asyncio.run(test_trace_api())
