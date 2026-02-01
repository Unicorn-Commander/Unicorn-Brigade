#!/usr/bin/env python3
"""
MCP Integration Tests

Tests the MCP Registry, Sandbox Executor, and MCP API endpoints.
Run with: python scripts/test_mcp_integration.py
"""

import asyncio
import os
import sys
import httpx
import time
from dataclasses import dataclass
from typing import List, Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.mcp.registry import mcp_registry, MCPTransport
from app.mcp.sandbox_executor import sandbox_executor, SandboxType


@dataclass
class TestResult:
    """Test result with timing"""
    name: str
    passed: bool
    duration: float
    message: str = ""
    details: Optional[dict] = None


class MCPIntegrationTests:
    """MCP Integration Test Suite"""

    def __init__(self, base_url: str = "http://localhost:8100"):
        self.base_url = base_url
        self.results: List[TestResult] = []
        self.client: Optional[httpx.AsyncClient] = None

    async def setup(self):
        """Initialize test client"""
        self.client = httpx.AsyncClient(timeout=60.0)

    async def teardown(self):
        """Cleanup"""
        if self.client:
            await self.client.aclose()

    def record(self, name: str, passed: bool, duration: float, message: str = "", details: dict = None):
        """Record a test result"""
        self.results.append(TestResult(name, passed, duration, message, details))
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status} {name} ({duration:.2f}s)")
        if message:
            print(f"       {message}")

    # =========================================================================
    # Sandbox Executor Tests (Direct Python)
    # =========================================================================

    async def test_sandbox_docker_available(self):
        """Test Docker availability check"""
        start = time.time()
        try:
            available = await sandbox_executor.check_docker()
            self.record(
                "Sandbox: Docker availability",
                True,  # Pass regardless - we just want to know the status
                time.time() - start,
                f"Docker available: {available}"
            )
            return available
        except Exception as e:
            self.record("Sandbox: Docker availability", False, time.time() - start, str(e))
            return False

    async def test_sandbox_e2b_available(self):
        """Test E2B availability check"""
        start = time.time()
        try:
            available = await sandbox_executor.check_e2b()
            self.record(
                "Sandbox: E2B availability",
                True,
                time.time() - start,
                f"E2B available: {available}"
            )
            return available
        except Exception as e:
            self.record("Sandbox: E2B availability", False, time.time() - start, str(e))
            return False

    async def test_sandbox_python_execution(self):
        """Test Python code execution in sandbox"""
        start = time.time()
        code = """
import sys
print(f"Python {sys.version}")
result = sum(range(10))
print(f"Sum of 0-9: {result}")
"""
        try:
            result = await sandbox_executor.execute(code, language="python", timeout=30)
            passed = result.success and "Sum of 0-9: 45" in result.stdout
            self.record(
                "Sandbox: Python execution",
                passed,
                time.time() - start,
                result.stdout[:200] if passed else result.stderr[:200],
                {"sandbox_type": result.sandbox_type}
            )
        except Exception as e:
            self.record("Sandbox: Python execution", False, time.time() - start, str(e))

    async def test_sandbox_javascript_execution(self):
        """Test JavaScript code execution in sandbox"""
        start = time.time()
        code = """
const arr = [1, 2, 3, 4, 5];
const sum = arr.reduce((a, b) => a + b, 0);
console.log(`Sum: ${sum}`);
console.log(`Node version: ${process.version}`);
"""
        try:
            result = await sandbox_executor.execute(code, language="javascript", timeout=30)
            passed = result.success and "Sum: 15" in result.stdout
            self.record(
                "Sandbox: JavaScript execution",
                passed,
                time.time() - start,
                result.stdout[:200] if passed else result.stderr[:200],
                {"sandbox_type": result.sandbox_type}
            )
        except Exception as e:
            self.record("Sandbox: JavaScript execution", False, time.time() - start, str(e))

    async def test_sandbox_bash_execution(self):
        """Test Bash code execution in sandbox"""
        start = time.time()
        code = """
echo "Hello from sandbox"
echo "Current date: $(date)"
echo "Files in /: $(ls / | wc -l)"
"""
        try:
            result = await sandbox_executor.execute(code, language="bash", timeout=30)
            passed = result.success and "Hello from sandbox" in result.stdout
            self.record(
                "Sandbox: Bash execution",
                passed,
                time.time() - start,
                result.stdout[:200] if passed else result.stderr[:200],
                {"sandbox_type": result.sandbox_type}
            )
        except Exception as e:
            self.record("Sandbox: Bash execution", False, time.time() - start, str(e))

    async def test_sandbox_timeout(self):
        """Test sandbox timeout handling"""
        start = time.time()
        code = """
import time
time.sleep(10)  # Should timeout
print("Should not reach here")
"""
        try:
            result = await sandbox_executor.execute(code, language="python", timeout=3)
            passed = not result.success and "timed out" in result.stderr.lower()
            self.record(
                "Sandbox: Timeout handling",
                passed,
                time.time() - start,
                "Timeout correctly enforced" if passed else f"Expected timeout, got: {result.stderr}"
            )
        except Exception as e:
            self.record("Sandbox: Timeout handling", False, time.time() - start, str(e))

    async def test_sandbox_with_packages(self):
        """Test sandbox with package installation (network disabled by default)"""
        start = time.time()
        code = """
import requests
print(f"requests version: {requests.__version__}")
"""
        try:
            result = await sandbox_executor.execute(
                code,
                language="python",
                timeout=60,
                packages=["requests"]
            )
            # Network is disabled by default for security, so packages can't install
            # This is expected behavior - the test passes if either:
            # 1. Package installs successfully (network enabled)
            # 2. Network error occurs (network disabled - expected)
            network_disabled = "connection" in result.stderr.lower() or "retrying" in result.stderr.lower()
            passed = result.success or network_disabled
            msg = result.stdout[:200] if result.success else "Network disabled (expected security behavior)"
            self.record(
                "Sandbox: Package installation (network isolated)",
                passed,
                time.time() - start,
                msg
            )
        except Exception as e:
            self.record("Sandbox: Package installation", False, time.time() - start, str(e))

    # =========================================================================
    # MCP Registry Tests (Direct Python)
    # =========================================================================

    async def test_registry_list_servers(self):
        """Test listing available MCP servers"""
        start = time.time()
        try:
            servers = mcp_registry.list_available()
            passed = len(servers) > 0
            server_names = [s["name"] for s in servers[:5]]
            self.record(
                "Registry: List servers",
                passed,
                time.time() - start,
                f"Found {len(servers)} servers: {', '.join(server_names)}..."
            )
        except Exception as e:
            self.record("Registry: List servers", False, time.time() - start, str(e))

    async def test_registry_get_server(self):
        """Test getting server configuration"""
        start = time.time()
        try:
            server = mcp_registry.get_server("github")
            passed = server is not None and server.name == "github"
            self.record(
                "Registry: Get server config",
                passed,
                time.time() - start,
                f"GitHub server: {server.display_name}" if passed else "Server not found"
            )
        except Exception as e:
            self.record("Registry: Get server config", False, time.time() - start, str(e))

    async def test_registry_server_capabilities(self):
        """Test server capabilities"""
        start = time.time()
        try:
            server = mcp_registry.get_server("playwright")
            passed = server is not None and "browser_navigate" in server.capabilities
            caps = server.capabilities[:5] if server else []
            self.record(
                "Registry: Server capabilities",
                passed,
                time.time() - start,
                f"Playwright capabilities: {caps}"
            )
        except Exception as e:
            self.record("Registry: Server capabilities", False, time.time() - start, str(e))

    # =========================================================================
    # API Endpoint Tests (via HTTP)
    # =========================================================================

    async def test_api_health(self):
        """Test API health endpoint"""
        start = time.time()
        try:
            resp = await self.client.get(f"{self.base_url}/api/v1/mcp/registry/health")
            data = resp.json()
            passed = resp.status_code == 200 and "status" in data
            self.record(
                "API: Health check",
                passed,
                time.time() - start,
                f"Status: {data.get('status')}, Docker: {data.get('docker_available')}"
            )
        except httpx.ConnectError:
            self.record("API: Health check", False, time.time() - start, "Cannot connect to API server")
        except Exception as e:
            self.record("API: Health check", False, time.time() - start, str(e))

    async def test_api_list_servers(self):
        """Test API list servers endpoint"""
        start = time.time()
        try:
            resp = await self.client.get(f"{self.base_url}/api/v1/mcp/registry/servers")
            data = resp.json()
            passed = resp.status_code == 200 and "servers" in data
            self.record(
                "API: List servers",
                passed,
                time.time() - start,
                f"Found {len(data.get('servers', []))} servers"
            )
        except httpx.ConnectError:
            self.record("API: List servers", False, time.time() - start, "Cannot connect to API server")
        except Exception as e:
            self.record("API: List servers", False, time.time() - start, str(e))

    async def test_api_sandbox_status(self):
        """Test API sandbox status endpoint"""
        start = time.time()
        try:
            resp = await self.client.get(f"{self.base_url}/api/v1/mcp/registry/sandbox/status")
            data = resp.json()
            passed = resp.status_code == 200 and "config" in data
            self.record(
                "API: Sandbox status",
                passed,
                time.time() - start,
                f"Docker: {data.get('docker_available')}, E2B: {data.get('e2b_available')}"
            )
        except httpx.ConnectError:
            self.record("API: Sandbox status", False, time.time() - start, "Cannot connect to API server")
        except Exception as e:
            self.record("API: Sandbox status", False, time.time() - start, str(e))

    async def test_api_execute_code(self):
        """Test API code execution endpoint"""
        start = time.time()
        try:
            resp = await self.client.post(
                f"{self.base_url}/api/v1/mcp/registry/sandbox/execute",
                json={
                    "code": "print('API test:', 2 + 2)",
                    "language": "python",
                    "timeout": 30
                }
            )
            data = resp.json()
            passed = resp.status_code == 200 and data.get("success") and "4" in data.get("stdout", "")
            self.record(
                "API: Execute code",
                passed,
                time.time() - start,
                data.get("stdout", "")[:100] if passed else data.get("stderr", str(data))[:100]
            )
        except httpx.ConnectError:
            self.record("API: Execute code", False, time.time() - start, "Cannot connect to API server")
        except Exception as e:
            self.record("API: Execute code", False, time.time() - start, str(e))

    async def test_api_get_server_detail(self):
        """Test API get server detail endpoint"""
        start = time.time()
        try:
            resp = await self.client.get(f"{self.base_url}/api/v1/mcp/registry/servers/github")
            data = resp.json()
            passed = resp.status_code == 200 and data.get("name") == "github"
            self.record(
                "API: Get server detail",
                passed,
                time.time() - start,
                f"Server: {data.get('display_name')}" if passed else str(data)[:100]
            )
        except httpx.ConnectError:
            self.record("API: Get server detail", False, time.time() - start, "Cannot connect to API server")
        except Exception as e:
            self.record("API: Get server detail", False, time.time() - start, str(e))

    # =========================================================================
    # Run All Tests
    # =========================================================================

    async def run_all(self):
        """Run all tests"""
        print("\n" + "=" * 70)
        print("MCP Integration Test Suite")
        print("=" * 70)

        await self.setup()

        # Sandbox Direct Tests
        print("\n📦 Sandbox Executor Tests (Direct)")
        print("-" * 40)
        docker_available = await self.test_sandbox_docker_available()
        await self.test_sandbox_e2b_available()

        if docker_available:
            await self.test_sandbox_python_execution()
            await self.test_sandbox_javascript_execution()
            await self.test_sandbox_bash_execution()
            await self.test_sandbox_timeout()
            await self.test_sandbox_with_packages()
        else:
            print("  ⚠️  Skipping execution tests - Docker not available")

        # Registry Direct Tests
        print("\n📚 MCP Registry Tests (Direct)")
        print("-" * 40)
        await self.test_registry_list_servers()
        await self.test_registry_get_server()
        await self.test_registry_server_capabilities()

        # API Tests
        print("\n🌐 API Endpoint Tests")
        print("-" * 40)
        await self.test_api_health()
        await self.test_api_list_servers()
        await self.test_api_sandbox_status()
        await self.test_api_get_server_detail()
        if docker_available:
            await self.test_api_execute_code()
        else:
            print("  ⚠️  Skipping API execute test - Docker not available")

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
                    print(f"    - {r.name}: {r.message}")

        print("\n" + "=" * 70)
        return failed == 0


async def main():
    """Main entry point"""
    tests = MCPIntegrationTests()
    success = await tests.run_all()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
