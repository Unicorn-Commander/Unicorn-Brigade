#!/usr/bin/env python3
"""
Example: Remote Code Execution with Unicorn Brigade

This example demonstrates how to:
1. Configure execution servers in Ops-Center
2. Execute code remotely via Brigade
3. Read/write files on remote servers
"""

import asyncio
import httpx
import json
from typing import Dict, Any


# Configuration
OPS_CENTER_URL = "http://localhost:8000"
BRIGADE_URL = "http://localhost:8100"
USER_EMAIL = "user@example.com"
SESSION_COOKIE = "your-session-cookie-here"  # Get from browser after login


async def configure_ssh_server(session_cookie: str) -> Dict[str, Any]:
    """Configure an SSH execution server in Ops-Center"""
    print("📡 Configuring SSH execution server...")

    server_config = {
        "name": "My Development Server",
        "server_type": "ssh",
        "connection_config": {
            "host": "dev.example.com",
            "port": 22,
            "username": "developer",
            "auth_method": "key",
            "private_key": """-----BEGIN OPENSSH PRIVATE KEY-----
... your SSH private key here ...
-----END OPENSSH PRIVATE KEY-----""",
            "workspaceRoot": "/home/developer/magicode"
        },
        "workspace_path": "/home/developer/magicode",
        "is_default": True
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{OPS_CENTER_URL}/api/v1/execution-servers",
            json=server_config,
            cookies={"session": session_cookie}
        )

        if response.status_code == 200:
            result = response.json()
            print(f"✅ SSH server configured: {result['id']}")
            return result
        else:
            print(f"❌ Failed to configure server: {response.status_code}")
            print(response.text)
            return None


async def configure_docker_server(session_cookie: str) -> Dict[str, Any]:
    """Configure a Docker execution server in Ops-Center"""
    print("🐳 Configuring Docker execution server...")

    server_config = {
        "name": "Local Docker",
        "server_type": "docker",
        "connection_config": {
            "image": "python:3.11-slim",
            "memoryLimit": "512m",
            "cpuQuota": 100000
        },
        "is_default": True
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{OPS_CENTER_URL}/api/v1/execution-servers",
            json=server_config,
            cookies={"session": session_cookie}
        )

        if response.status_code == 200:
            result = response.json()
            print(f"✅ Docker server configured: {result['id']}")
            return result
        else:
            print(f"❌ Failed to configure server: {response.status_code}")
            return None


async def list_execution_servers(session_cookie: str):
    """List all configured execution servers"""
    print("\n📋 Listing execution servers...")

    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{OPS_CENTER_URL}/api/v1/execution-servers",
            cookies={"session": session_cookie}
        )

        if response.status_code == 200:
            servers = response.json()
            print(f"Found {len(servers)} server(s):")
            for server in servers:
                print(f"  - {server['name']} ({server['server_type']}) - Default: {server['is_default']}")
            return servers
        else:
            print(f"❌ Failed to list servers: {response.status_code}")
            return []


async def test_server_connection(server_id: str, session_cookie: str):
    """Test connection to an execution server"""
    print(f"\n🔍 Testing server connection: {server_id}...")

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{OPS_CENTER_URL}/api/v1/execution-servers/{server_id}/test",
            cookies={"session": session_cookie}
        )

        if response.status_code == 200:
            result = response.json()
            if result["status"] == "success":
                print(f"✅ Connection successful: {result['message']}")
            else:
                print(f"❌ Connection failed: {result['message']}")
            return result
        else:
            print(f"❌ Test failed: {response.status_code}")
            return None


async def execute_python_code(user_id: str):
    """Execute Python code via Brigade"""
    print("\n🐍 Executing Python code...")

    code = """
import sys
import platform

print(f"Python version: {sys.version}")
print(f"Platform: {platform.platform()}")
print(f"Hello from remote execution!")

# Simple calculation
result = sum(range(1, 101))
print(f"Sum of 1-100: {result}")
"""

    request = {
        "code": code,
        "language": "python",
        "timeout": 30
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BRIGADE_URL}/api/v1/execution/execute",
            json=request,
            headers={"X-User-ID": user_id}
        )

        if response.status_code == 200:
            result = response.json()
            print(f"✅ Execution successful ({result['execution_type']}):")
            print(f"   Duration: {result['duration_seconds']:.2f}s")
            print(f"   Output:")
            print(result['output'])
            return result
        else:
            print(f"❌ Execution failed: {response.status_code}")
            print(response.text)
            return None


async def execute_javascript_code(user_id: str):
    """Execute JavaScript code via Brigade"""
    print("\n📜 Executing JavaScript code...")

    code = """
console.log('Hello from Node.js!');
console.log('Node version:', process.version);

const numbers = [1, 2, 3, 4, 5];
const sum = numbers.reduce((a, b) => a + b, 0);
console.log('Sum:', sum);

// Async example
async function fetchData() {
    return new Promise(resolve => {
        setTimeout(() => resolve('Data fetched!'), 100);
    });
}

fetchData().then(data => console.log(data));
"""

    request = {
        "code": code,
        "language": "javascript",
        "timeout": 30
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BRIGADE_URL}/api/v1/execution/execute",
            json=request,
            headers={"X-User-ID": user_id}
        )

        if response.status_code == 200:
            result = response.json()
            print(f"✅ Execution successful ({result['execution_type']}):")
            print(f"   Output:")
            print(result['output'])
            return result
        else:
            print(f"❌ Execution failed: {response.status_code}")
            return None


async def write_remote_file(user_id: str):
    """Write a file to remote server"""
    print("\n📝 Writing file to remote server...")

    request = {
        "path": "/workspace/hello.py",
        "content": "print('Hello from file!')\nprint('This was written remotely')\n"
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BRIGADE_URL}/api/v1/execution/files/write",
            json=request,
            headers={"X-User-ID": user_id}
        )

        if response.status_code == 200:
            result = response.json()
            print(f"✅ File written: {result['path']}")
            return result
        else:
            print(f"❌ Write failed: {response.status_code}")
            return None


async def read_remote_file(user_id: str):
    """Read a file from remote server"""
    print("\n📖 Reading file from remote server...")

    request = {
        "path": "/workspace/hello.py"
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BRIGADE_URL}/api/v1/execution/files/read",
            json=request,
            headers={"X-User-ID": user_id}
        )

        if response.status_code == 200:
            result = response.json()
            print(f"✅ File read: {result['path']}")
            print(f"   Content:")
            print(result['content'])
            return result
        else:
            print(f"❌ Read failed: {response.status_code}")
            return None


async def list_supported_languages():
    """List all supported programming languages"""
    print("\n🔤 Supported programming languages:")

    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{BRIGADE_URL}/api/v1/execution/languages"
        )

        if response.status_code == 200:
            result = response.json()
            print(f"Total: {result['count']} languages")
            for lang in result['languages']:
                print(f"  - {lang['language']:12} (.{lang['extension']:4}) → {lang['command']}")
            return result
        else:
            print(f"❌ Failed to list languages: {response.status_code}")
            return None


async def execute_with_error_handling(user_id: str):
    """Example of handling execution errors"""
    print("\n⚠️  Testing error handling...")

    # This code will fail
    code = """
print("Before error")
undefined_variable  # This will cause a NameError
print("After error - won't be reached")
"""

    request = {
        "code": code,
        "language": "python",
        "timeout": 30
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BRIGADE_URL}/api/v1/execution/execute",
            json=request,
            headers={"X-User-ID": user_id}
        )

        result = response.json()

        if not result['success']:
            print(f"❌ Execution failed (as expected):")
            print(f"   Exit code: {result['exit_code']}")
            print(f"   Error output:")
            print(result['output'])
        else:
            print(f"✅ Unexpected success")

        return result


async def main():
    """Main example workflow"""
    print("=" * 60)
    print("Unicorn Brigade - Remote Code Execution Example")
    print("=" * 60)

    # Note: In production, you'd authenticate and get a real session cookie
    session_cookie = SESSION_COOKIE
    user_id = "example-user-123"  # Would come from authentication

    # Step 1: List supported languages
    await list_supported_languages()

    # Step 2: Configure execution server (uncomment to use)
    # server = await configure_docker_server(session_cookie)
    # if server:
    #     await test_server_connection(server['id'], session_cookie)

    # Step 3: List configured servers
    # await list_execution_servers(session_cookie)

    # Step 4: Execute Python code
    await execute_python_code(user_id)

    # Step 5: Execute JavaScript code
    await execute_javascript_code(user_id)

    # Step 6: File operations
    await write_remote_file(user_id)
    await read_remote_file(user_id)

    # Step 7: Error handling
    await execute_with_error_handling(user_id)

    print("\n" + "=" * 60)
    print("✅ Example completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
