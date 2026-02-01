#!/usr/bin/env python3
"""
Collect MCP Server Test Results
Gathers comprehensive test data for all running MCP servers.
"""

import requests
import json
import time
from typing import Dict, List, Any

API_BASE = "http://localhost:8100/api/v1/mcp/registry"

def get_server_details(server_name: str) -> Dict[str, Any]:
    """Get details for a specific server"""
    try:
        response = requests.get(f"{API_BASE}/servers/{server_name}", timeout=5)
        if response.status_code == 200:
            return response.json()
        else:
            return {"error": f"HTTP {response.status_code}"}
    except Exception as e:
        return {"error": str(e)}

def test_servers(server_list: List[str]) -> List[Dict[str, Any]]:
    """Test multiple servers and collect results"""
    results = []

    for server_name in server_list:
        print(f"\nTesting {server_name}...")

        details = get_server_details(server_name)

        if "error" in details:
            results.append({
                "server": server_name,
                "status": "error",
                "error": details["error"],
                "running": False,
                "tool_count": 0
            })
        else:
            results.append({
                "server": server_name,
                "display_name": details.get("display_name", ""),
                "description": details.get("description", ""),
                "running": details.get("running", False),
                "tool_count": len(details.get("capabilities", [])),
                "tools": details.get("capabilities", [])[:5],  # First 5 tools
                "transport": details.get("transport", ""),
                "status": "success" if details.get("running") else "not_running"
            })

        time.sleep(0.5)  # Rate limiting

    return results

def main():
    # List of servers to test
    servers_to_test = [
        # Baseline servers
        "github", "slack", "postgres", "playwright", "brave-search",
        "memory", "fetch", "filesystem", "google-drive", "puppeteer",

        # Phase 1 servers
        "stripe", "linear", "git", "notion",

        # Phase 2 servers
        "airtable", "vercel", "cloudflare", "supabase"
    ]

    print("="*60)
    print("MCP Server Registry Test Report")
    print("="*60)

    results = test_servers(servers_to_test)

    # Summary statistics
    total = len(results)
    running = sum(1 for r in results if r["running"])
    total_tools = sum(r["tool_count"] for r in results)

    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"Total servers tested: {total}")
    print(f"Running servers: {running}")
    print(f"Failed servers: {total - running}")
    print(f"Total tools available: {total_tools}")

    # Save full results
    output = {
        "test_timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "summary": {
            "total_servers": total,
            "running_servers": running,
            "failed_servers": total - running,
            "total_tools": total_tools
        },
        "servers": results
    }

    with open("mcp_test_results.json", "w") as f:
        json.dump(output, f, indent=2)

    print(f"\nFull results saved to: mcp_test_results.json")

    # Print detailed table
    print(f"\n{'='*60}")
    print("DETAILED RESULTS")
    print(f"{'='*60}")
    print(f"{'Server':<20} {'Status':<12} {'Tools':<8} {'Transport':<10}")
    print("-"*60)

    for r in results:
        status = "RUNNING" if r["running"] else "NOT_RUNNING"
        print(f"{r['server']:<20} {status:<12} {r['tool_count']:<8} {r.get('transport', 'N/A'):<10}")

if __name__ == "__main__":
    main()
