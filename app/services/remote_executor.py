"""
Remote Code Execution Service for Unicorn Brigade

Executes code on user-configured servers (SSH, Docker, or local MagiCode instances)
"""

from typing import Dict, Any, Optional, List
import asyncio
import uuid
import logging
import tempfile
import os
from datetime import datetime
import httpx
import asyncssh
from asyncssh import SSHClientConnectionOptions
import docker
from docker.errors import DockerException
from pathlib import Path

logger = logging.getLogger(__name__)


def get_known_hosts_path(config: Dict[str, Any]) -> str:
    """
    Get the known_hosts file path for SSH connections.

    Priority:
    1. User-specified path in config
    2. Environment variable SSH_KNOWN_HOSTS
    3. Default system paths (~/.ssh/known_hosts)

    Returns path string or None if trust_first_connect is enabled.
    """
    conn_config = config.get("connection", {})

    # Check if user wants to trust on first connect (less secure but convenient)
    if conn_config.get("trust_first_connect", False):
        logger.warning(
            "SSH trust_first_connect is enabled - host key verification disabled. "
            "This is less secure and should only be used in trusted environments."
        )
        return None

    # User-specified known_hosts file
    if conn_config.get("known_hosts_file"):
        path = Path(conn_config["known_hosts_file"]).expanduser()
        if path.exists():
            return str(path)
        logger.warning(f"Specified known_hosts file not found: {path}")

    # Environment variable
    env_path = os.getenv("SSH_KNOWN_HOSTS")
    if env_path:
        path = Path(env_path).expanduser()
        if path.exists():
            return str(path)
        logger.warning(f"SSH_KNOWN_HOSTS file not found: {path}")

    # Default system paths
    default_paths = [
        Path.home() / ".ssh" / "known_hosts",
        Path("/etc/ssh/ssh_known_hosts"),
    ]

    for path in default_paths:
        if path.exists():
            return str(path)

    # No known_hosts found - require explicit trust_first_connect or fail
    raise ValueError(
        "No known_hosts file found. Either:\n"
        "1. Add the host to ~/.ssh/known_hosts (ssh-keyscan hostname >> ~/.ssh/known_hosts)\n"
        "2. Specify a known_hosts_file in your server config\n"
        "3. Set trust_first_connect: true in config (less secure)"
    )


class RemoteExecutor:
    """Execute code on remote servers configured by users"""

    # Language command mappings
    LANGUAGE_COMMANDS = {
        "python": {"ext": "py", "cmd": "python3 {file}"},
        "javascript": {"ext": "js", "cmd": "node {file}"},
        "typescript": {"ext": "ts", "cmd": "ts-node {file}"},
        "bash": {"ext": "sh", "cmd": "bash {file}"},
        "shell": {"ext": "sh", "cmd": "bash {file}"},
        "ruby": {"ext": "rb", "cmd": "ruby {file}"},
        "go": {"ext": "go", "cmd": "go run {file}"},
        "rust": {"ext": "rs", "cmd": "rustc {file} -o /tmp/output && /tmp/output"},
        "java": {"ext": "java", "cmd": "javac {file} && java $(basename {file} .java)"},
        "php": {"ext": "php", "cmd": "php {file}"},
        "perl": {"ext": "pl", "cmd": "perl {file}"},
        "r": {"ext": "r", "cmd": "Rscript {file}"},
        "julia": {"ext": "jl", "cmd": "julia {file}"},
    }

    def __init__(self, user_id: str, ops_center_url: str = None):
        """
        Initialize remote executor for a user

        Args:
            user_id: User ID to fetch execution server config
            ops_center_url: Ops-Center URL for fetching user config
        """
        self.user_id = user_id
        self.ops_center_url = ops_center_url or os.getenv(
            "OPS_CENTER_URL", "http://localhost:8000"
        )
        self.server_config: Optional[Dict[str, Any]] = None
        self.timeout = 30  # Default execution timeout in seconds

    async def get_server_config(self) -> Dict[str, Any]:
        """Fetch user's execution server configuration from Ops-Center"""
        if self.server_config:
            return self.server_config

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.ops_center_url}/api/v1/execution-servers/default",
                    headers={"X-User-ID": self.user_id},
                    timeout=10.0
                )

                if response.status_code == 404:
                    # No server configured, use local fallback
                    logger.info(f"No execution server configured for user {self.user_id}, using local")
                    self.server_config = {"type": "local", "enabled": True}
                    return self.server_config

                response.raise_for_status()
                self.server_config = response.json()
                return self.server_config

        except Exception as e:
            logger.warning(f"Failed to fetch execution server config: {e}. Using local fallback.")
            self.server_config = {"type": "local", "enabled": True}
            return self.server_config

    async def execute_code(
        self,
        language: str,
        code: str,
        timeout: Optional[int] = None,
        workspace: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute code on configured server

        Args:
            language: Programming language (python, javascript, etc.)
            code: Source code to execute
            timeout: Execution timeout in seconds (default: 30)
            workspace: Optional workspace directory path

        Returns:
            Dict with execution results
        """
        timeout = timeout or self.timeout
        config = await self.get_server_config()

        execution_id = str(uuid.uuid4())[:8]
        start_time = datetime.utcnow()

        try:
            if config["type"] == "ssh":
                result = await self._execute_ssh(language, code, config, timeout, workspace)
            elif config["type"] == "docker":
                result = await self._execute_docker(language, code, config, timeout, workspace)
            elif config["type"] == "local":
                result = await self._execute_local(language, code, timeout, workspace)
            else:
                raise ValueError(f"Unknown execution type: {config['type']}")

            duration = (datetime.utcnow() - start_time).total_seconds()

            return {
                "success": result.get("success", False),
                "execution_id": execution_id,
                "language": language,
                "output": result.get("output", ""),
                "error": result.get("error", ""),
                "exit_code": result.get("exit_code", 0),
                "execution_type": config["type"],
                "duration_seconds": duration,
                "timeout": timeout,
                "timestamp": start_time.isoformat()
            }

        except asyncio.TimeoutError:
            return {
                "success": False,
                "execution_id": execution_id,
                "language": language,
                "output": "",
                "error": f"Execution timeout after {timeout} seconds",
                "exit_code": -1,
                "execution_type": config.get("type", "unknown"),
                "duration_seconds": timeout,
                "timeout": timeout,
                "timestamp": start_time.isoformat()
            }
        except Exception as e:
            logger.error(f"Execution error: {e}")
            return {
                "success": False,
                "execution_id": execution_id,
                "language": language,
                "output": "",
                "error": str(e),
                "exit_code": -1,
                "execution_type": config.get("type", "unknown"),
                "duration_seconds": (datetime.utcnow() - start_time).total_seconds(),
                "timeout": timeout,
                "timestamp": start_time.isoformat()
            }

    async def _execute_ssh(
        self,
        language: str,
        code: str,
        config: Dict[str, Any],
        timeout: int,
        workspace: Optional[str]
    ) -> Dict[str, Any]:
        """Execute code on remote server via SSH"""

        if language not in self.LANGUAGE_COMMANDS:
            raise ValueError(f"Unsupported language: {language}")

        lang_config = self.LANGUAGE_COMMANDS[language]
        conn_config = config.get("connection", {})

        # Validate path security
        if workspace:
            workspace = self._sanitize_path(workspace, conn_config.get("workspaceRoot", "/tmp"))
        else:
            workspace = conn_config.get("workspaceRoot", "/tmp")

        temp_filename = f"magicode_{uuid.uuid4().hex[:8]}.{lang_config['ext']}"
        remote_file = f"{workspace}/{temp_filename}"

        try:
            # Get known_hosts path for host key verification
            known_hosts_path = get_known_hosts_path(config)

            # Connect via SSH with proper host key verification
            async with asyncssh.connect(
                host=conn_config.get("host"),
                port=conn_config.get("port", 22),
                username=conn_config.get("username"),
                client_keys=[conn_config.get("keyPath")] if conn_config.get("keyPath") else None,
                password=conn_config.get("password") if not conn_config.get("keyPath") else None,
                known_hosts=known_hosts_path  # Properly verify host keys
            ) as conn:

                # Create workspace if needed
                await conn.run(f"mkdir -p {workspace}", check=False)

                # Write code to remote file
                async with conn.start_sftp_client() as sftp:
                    async with sftp.open(remote_file, 'w') as f:
                        await f.write(code)

                # Execute the code
                command = lang_config["cmd"].format(file=remote_file)
                result = await asyncio.wait_for(
                    conn.run(f"cd {workspace} && {command}", check=False),
                    timeout=timeout
                )

                # Cleanup
                await conn.run(f"rm -f {remote_file}", check=False)

                return {
                    "success": result.exit_status == 0,
                    "output": result.stdout,
                    "error": result.stderr,
                    "exit_code": result.exit_status
                }

        except asyncio.TimeoutError:
            # Try to cleanup on timeout
            try:
                async with asyncssh.connect(
                    host=conn_config.get("host"),
                    port=conn_config.get("port", 22),
                    username=conn_config.get("username"),
                    client_keys=[conn_config.get("keyPath")] if conn_config.get("keyPath") else None,
                    password=conn_config.get("password"),
                    known_hosts=known_hosts_path  # Reuse the same host key verification
                ) as conn:
                    await conn.run(f"rm -f {remote_file}", check=False)
            except Exception:
                pass  # Cleanup is best-effort
            raise

    async def _execute_docker(
        self,
        language: str,
        code: str,
        config: Dict[str, Any],
        timeout: int,
        workspace: Optional[str]
    ) -> Dict[str, Any]:
        """Execute code in Docker container"""

        if language not in self.LANGUAGE_COMMANDS:
            raise ValueError(f"Unsupported language: {language}")

        lang_config = self.LANGUAGE_COMMANDS[language]
        docker_config = config.get("connection", {})

        # Language to Docker image mapping
        image_map = {
            "python": "python:3.11-slim",
            "javascript": "node:20-slim",
            "typescript": "node:20-slim",
            "bash": "bash:latest",
            "shell": "bash:latest",
            "ruby": "ruby:3.2-slim",
            "go": "golang:1.21-alpine",
            "rust": "rust:1.75-slim",
            "java": "openjdk:21-slim",
            "php": "php:8.2-cli",
            "perl": "perl:5.38",
            "r": "r-base:latest",
            "julia": "julia:1.10",
        }

        image = docker_config.get("image", image_map.get(language, "python:3.11-slim"))

        try:
            # Connect to Docker
            if docker_config.get("host"):
                client = docker.DockerClient(base_url=docker_config["host"])
            else:
                client = docker.from_env()

            # Create temp file with code
            temp_filename = f"magicode_{uuid.uuid4().hex[:8]}.{lang_config['ext']}"

            with tempfile.TemporaryDirectory() as tmpdir:
                file_path = os.path.join(tmpdir, temp_filename)

                with open(file_path, 'w') as f:
                    f.write(code)

                # Prepare command
                command = lang_config["cmd"].format(file=f"/workspace/{temp_filename}")

                # Run container
                container = client.containers.run(
                    image,
                    command=["sh", "-c", command],
                    volumes={tmpdir: {"bind": "/workspace", "mode": "ro"}},
                    working_dir="/workspace",
                    remove=True,
                    detach=True,
                    mem_limit=docker_config.get("memoryLimit", "512m"),
                    cpu_quota=docker_config.get("cpuQuota", 100000),
                    network_mode="none"  # No network access for security
                )

                # Wait for completion with timeout
                result = await asyncio.wait_for(
                    asyncio.to_thread(container.wait),
                    timeout=timeout
                )

                # Get logs
                logs = container.logs().decode('utf-8')

                return {
                    "success": result["StatusCode"] == 0,
                    "output": logs,
                    "error": logs if result["StatusCode"] != 0 else "",
                    "exit_code": result["StatusCode"]
                }

        except asyncio.TimeoutError:
            # Stop container on timeout
            try:
                container.stop(timeout=0)
            except:
                pass
            raise
        except DockerException as e:
            logger.error(f"Docker execution error: {e}")
            raise

    async def _execute_local(
        self,
        language: str,
        code: str,
        timeout: int,
        workspace: Optional[str]
    ) -> Dict[str, Any]:
        """Execute code locally on Brigade's server (sandboxed in Docker)"""

        if language not in self.LANGUAGE_COMMANDS:
            raise ValueError(f"Unsupported language: {language}")

        lang_config = self.LANGUAGE_COMMANDS[language]

        # For local execution, we still use Docker for security
        image_map = {
            "python": "python:3.11-slim",
            "javascript": "node:20-slim",
            "typescript": "node:20-slim",
            "bash": "bash:latest",
            "shell": "bash:latest",
            "ruby": "ruby:3.2-slim",
            "go": "golang:1.21-alpine",
            "rust": "rust:1.75-slim",
            "java": "openjdk:21-slim",
            "php": "php:8.2-cli",
        }

        image = image_map.get(language, "python:3.11-slim")

        try:
            client = docker.from_env()

            temp_filename = f"magicode_{uuid.uuid4().hex[:8]}.{lang_config['ext']}"

            with tempfile.TemporaryDirectory() as tmpdir:
                file_path = os.path.join(tmpdir, temp_filename)

                with open(file_path, 'w') as f:
                    f.write(code)

                command = lang_config["cmd"].format(file=f"/workspace/{temp_filename}")

                container = client.containers.run(
                    image,
                    command=["sh", "-c", command],
                    volumes={tmpdir: {"bind": "/workspace", "mode": "ro"}},
                    working_dir="/workspace",
                    remove=True,
                    detach=True,
                    mem_limit="256m",
                    cpu_quota=50000,
                    network_mode="none"
                )

                result = await asyncio.wait_for(
                    asyncio.to_thread(container.wait),
                    timeout=timeout
                )

                logs = container.logs().decode('utf-8')

                return {
                    "success": result["StatusCode"] == 0,
                    "output": logs,
                    "error": logs if result["StatusCode"] != 0 else "",
                    "exit_code": result["StatusCode"]
                }

        except asyncio.TimeoutError:
            try:
                container.stop(timeout=0)
            except:
                pass
            raise
        except DockerException as e:
            logger.error(f"Local Docker execution error: {e}")
            raise

    def _sanitize_path(self, path: str, allowed_root: str) -> str:
        """Sanitize and validate file paths to prevent directory traversal"""
        # Remove any ".." or other suspicious patterns
        clean_path = os.path.normpath(path)

        # Ensure path is within allowed root
        if not clean_path.startswith(allowed_root):
            raise ValueError(f"Path {path} is outside allowed workspace {allowed_root}")

        return clean_path

    async def read_file(self, path: str) -> str:
        """Read file from remote server"""
        config = await self.get_server_config()

        if config["type"] == "ssh":
            return await self._read_file_ssh(path, config)
        elif config["type"] == "local":
            return await self._read_file_local(path)
        else:
            raise ValueError(f"File operations not supported for {config['type']}")

    async def write_file(self, path: str, content: str) -> bool:
        """Write file to remote server"""
        config = await self.get_server_config()

        if config["type"] == "ssh":
            return await self._write_file_ssh(path, content, config)
        elif config["type"] == "local":
            return await self._write_file_local(path, content)
        else:
            raise ValueError(f"File operations not supported for {config['type']}")

    async def _read_file_ssh(self, path: str, config: Dict[str, Any]) -> str:
        """Read file via SSH"""
        conn_config = config.get("connection", {})
        workspace = conn_config.get("workspaceRoot", "/tmp")
        safe_path = self._sanitize_path(path, workspace)
        known_hosts_path = get_known_hosts_path(config)

        async with asyncssh.connect(
            host=conn_config.get("host"),
            port=conn_config.get("port", 22),
            username=conn_config.get("username"),
            client_keys=[conn_config.get("keyPath")] if conn_config.get("keyPath") else None,
            password=conn_config.get("password"),
            known_hosts=known_hosts_path
        ) as conn:
            async with conn.start_sftp_client() as sftp:
                async with sftp.open(safe_path, 'r') as f:
                    return await f.read()

    async def _write_file_ssh(self, path: str, content: str, config: Dict[str, Any]) -> bool:
        """Write file via SSH"""
        conn_config = config.get("connection", {})
        workspace = conn_config.get("workspaceRoot", "/tmp")
        safe_path = self._sanitize_path(path, workspace)
        known_hosts_path = get_known_hosts_path(config)

        async with asyncssh.connect(
            host=conn_config.get("host"),
            port=conn_config.get("port", 22),
            username=conn_config.get("username"),
            client_keys=[conn_config.get("keyPath")] if conn_config.get("keyPath") else None,
            password=conn_config.get("password"),
            known_hosts=known_hosts_path
        ) as conn:
            # Ensure directory exists
            dir_path = os.path.dirname(safe_path)
            await conn.run(f"mkdir -p {dir_path}", check=False)

            async with conn.start_sftp_client() as sftp:
                async with sftp.open(safe_path, 'w') as f:
                    await f.write(content)

        return True

    async def _read_file_local(self, path: str) -> str:
        """Read file locally (with security restrictions)"""
        # For local, we restrict to /tmp for security
        safe_path = self._sanitize_path(path, "/tmp/brigade_workspace")

        with open(safe_path, 'r') as f:
            return f.read()

    async def _write_file_local(self, path: str, content: str) -> bool:
        """Write file locally (with security restrictions)"""
        safe_path = self._sanitize_path(path, "/tmp/brigade_workspace")

        os.makedirs(os.path.dirname(safe_path), exist_ok=True)

        with open(safe_path, 'w') as f:
            f.write(content)

        return True
