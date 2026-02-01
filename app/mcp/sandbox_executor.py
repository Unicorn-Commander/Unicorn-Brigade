"""
Hybrid Code Sandbox Executor

Supports both self-hosted Docker and E2B cloud execution.
Self-hosted is preferred for privacy and cost control.
E2B is optional fallback for when Docker is unavailable.
"""

import os
import asyncio
import subprocess
import tempfile
import time
import logging
from dataclasses import dataclass
from typing import Optional, Literal, Dict, Any, List
from enum import Enum

logger = logging.getLogger(__name__)


class SandboxType(Enum):
    """Available sandbox backends"""
    DOCKER = "docker"
    E2B = "e2b"
    AUTO = "auto"  # Auto-detect best available


@dataclass
class SandboxConfig:
    """Sandbox configuration"""
    sandbox_type: SandboxType = SandboxType.AUTO
    prefer_docker: bool = True
    allow_e2b_fallback: bool = True
    docker_image_python: str = "python:3.11-slim"
    docker_image_node: str = "node:20-slim"
    docker_image_shell: str = "alpine:latest"
    timeout: int = 30
    max_memory: str = "512m"
    max_cpu: str = "1"
    network_enabled: bool = False
    e2b_api_key: Optional[str] = None

    @classmethod
    def from_env(cls) -> "SandboxConfig":
        """Create config from environment variables"""
        return cls(
            sandbox_type=SandboxType(os.getenv("SANDBOX_TYPE", "auto")),
            prefer_docker=os.getenv("SANDBOX_PREFER_DOCKER", "true").lower() == "true",
            allow_e2b_fallback=os.getenv("SANDBOX_ALLOW_E2B_FALLBACK", "true").lower() == "true",
            docker_image_python=os.getenv("SANDBOX_DOCKER_PYTHON", "python:3.11-slim"),
            docker_image_node=os.getenv("SANDBOX_DOCKER_NODE", "node:20-slim"),
            docker_image_shell=os.getenv("SANDBOX_DOCKER_SHELL", "alpine:latest"),
            timeout=int(os.getenv("SANDBOX_TIMEOUT", "30")),
            max_memory=os.getenv("SANDBOX_MAX_MEMORY", "512m"),
            max_cpu=os.getenv("SANDBOX_MAX_CPU", "1"),
            network_enabled=os.getenv("SANDBOX_NETWORK_ENABLED", "false").lower() == "true",
            e2b_api_key=os.getenv("E2B_API_KEY"),
        )


@dataclass
class ExecutionResult:
    """Result of code execution"""
    stdout: str
    stderr: str
    success: bool
    exit_code: int
    execution_time: float
    sandbox_type: str
    metadata: Dict[str, Any] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stdout": self.stdout,
            "stderr": self.stderr,
            "success": self.success,
            "exit_code": self.exit_code,
            "execution_time": self.execution_time,
            "sandbox_type": self.sandbox_type,
            "metadata": self.metadata or {},
        }


class SandboxExecutor:
    """
    Hybrid code sandbox executor.

    Supports:
    - Self-hosted Docker (preferred for privacy/cost)
    - E2B cloud (optional fallback)

    Usage:
        executor = SandboxExecutor()
        result = await executor.execute("print('hello')", language="python")
    """

    LANGUAGE_MAP = {
        "python": {"image_key": "docker_image_python", "command": "python3", "ext": ".py"},
        "python3": {"image_key": "docker_image_python", "command": "python3", "ext": ".py"},
        "javascript": {"image_key": "docker_image_node", "command": "node", "ext": ".js"},
        "js": {"image_key": "docker_image_node", "command": "node", "ext": ".js"},
        "typescript": {"image_key": "docker_image_node", "command": "npx ts-node", "ext": ".ts"},
        "ts": {"image_key": "docker_image_node", "command": "npx ts-node", "ext": ".ts"},
        "bash": {"image_key": "docker_image_shell", "command": "sh", "ext": ".sh"},
        "shell": {"image_key": "docker_image_shell", "command": "sh", "ext": ".sh"},
        "sh": {"image_key": "docker_image_shell", "command": "sh", "ext": ".sh"},
    }

    def __init__(self, config: Optional[SandboxConfig] = None):
        self.config = config or SandboxConfig.from_env()
        self._docker_available: Optional[bool] = None
        self._e2b_available: Optional[bool] = None

    async def check_docker(self) -> bool:
        """Check if Docker is available"""
        if self._docker_available is not None:
            return self._docker_available

        try:
            proc = await asyncio.create_subprocess_exec(
                "docker", "info",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(proc.wait(), timeout=5.0)
            self._docker_available = proc.returncode == 0
        except Exception:
            self._docker_available = False

        return self._docker_available

    async def check_e2b(self) -> bool:
        """Check if E2B is available"""
        if self._e2b_available is not None:
            return self._e2b_available

        self._e2b_available = bool(self.config.e2b_api_key)
        return self._e2b_available

    async def get_available_sandbox(self) -> SandboxType:
        """Determine which sandbox to use"""
        if self.config.sandbox_type == SandboxType.DOCKER:
            if await self.check_docker():
                return SandboxType.DOCKER
            raise RuntimeError("Docker sandbox requested but Docker not available")

        if self.config.sandbox_type == SandboxType.E2B:
            if await self.check_e2b():
                return SandboxType.E2B
            raise RuntimeError("E2B sandbox requested but E2B_API_KEY not set")

        # Auto mode: prefer Docker, fallback to E2B
        if self.config.prefer_docker and await self.check_docker():
            return SandboxType.DOCKER

        if self.config.allow_e2b_fallback and await self.check_e2b():
            logger.info("Docker unavailable, using E2B fallback")
            return SandboxType.E2B

        if await self.check_docker():
            return SandboxType.DOCKER

        raise RuntimeError(
            "No sandbox backend available. "
            "Install Docker or set E2B_API_KEY environment variable."
        )

    async def execute(
        self,
        code: str,
        language: str = "python",
        timeout: Optional[int] = None,
        env: Optional[Dict[str, str]] = None,
        packages: Optional[List[str]] = None,
    ) -> ExecutionResult:
        """
        Execute code in sandbox.

        Args:
            code: Code to execute
            language: Programming language (python, javascript, bash, etc.)
            timeout: Execution timeout in seconds
            env: Environment variables
            packages: Packages to install before execution

        Returns:
            ExecutionResult with stdout, stderr, success status
        """
        sandbox_type = await self.get_available_sandbox()
        timeout = timeout or self.config.timeout

        if sandbox_type == SandboxType.DOCKER:
            return await self._execute_docker(code, language, timeout, env, packages)
        elif sandbox_type == SandboxType.E2B:
            return await self._execute_e2b(code, language, timeout, env, packages)
        else:
            return ExecutionResult(
                stdout="",
                stderr=f"Unknown sandbox type: {sandbox_type}",
                success=False,
                exit_code=-1,
                execution_time=0,
                sandbox_type="unknown",
            )

    async def _execute_docker(
        self,
        code: str,
        language: str,
        timeout: int,
        env: Optional[Dict[str, str]] = None,
        packages: Optional[List[str]] = None,
    ) -> ExecutionResult:
        """Execute code in Docker container"""
        start_time = time.time()

        lang_config = self.LANGUAGE_MAP.get(language.lower())
        if not lang_config:
            return ExecutionResult(
                stdout="",
                stderr=f"Unsupported language: {language}",
                success=False,
                exit_code=-1,
                execution_time=0,
                sandbox_type="docker",
            )

        image = getattr(self.config, lang_config["image_key"])
        command = lang_config["command"]
        ext = lang_config["ext"]

        # Write code to temp file
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=ext, delete=False
        ) as f:
            f.write(code)
            code_file = f.name

        try:
            # Build Docker command
            docker_cmd = [
                "docker", "run",
                "--rm",
                f"--memory={self.config.max_memory}",
                f"--cpus={self.config.max_cpu}",
                "--security-opt=no-new-privileges",
                "--cap-drop=ALL",
            ]

            # Network isolation
            if not self.config.network_enabled:
                docker_cmd.append("--network=none")

            # Environment variables
            if env:
                for key, value in env.items():
                    docker_cmd.extend(["-e", f"{key}={value}"])

            # Mount code file
            docker_cmd.extend(["-v", f"{code_file}:/code{ext}:ro"])

            # Add image
            docker_cmd.append(image)

            # Build execution command
            if packages and language.lower() in ("python", "python3"):
                # Install packages first
                pip_install = " && ".join([f"pip install -q {p}" for p in packages])
                docker_cmd.extend(["sh", "-c", f"{pip_install} && {command} /code{ext}"])
            elif packages and language.lower() in ("javascript", "js"):
                npm_install = " && ".join([f"npm install -q {p}" for p in packages])
                docker_cmd.extend(["sh", "-c", f"{npm_install} && {command} /code{ext}"])
            else:
                docker_cmd.extend([command, f"/code{ext}"])

            # Execute
            proc = await asyncio.create_subprocess_exec(
                *docker_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=timeout
                )
                exit_code = proc.returncode
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                return ExecutionResult(
                    stdout="",
                    stderr=f"Execution timed out after {timeout}s",
                    success=False,
                    exit_code=-1,
                    execution_time=timeout,
                    sandbox_type="docker",
                )

            execution_time = time.time() - start_time

            return ExecutionResult(
                stdout=stdout.decode("utf-8", errors="replace"),
                stderr=stderr.decode("utf-8", errors="replace"),
                success=exit_code == 0,
                exit_code=exit_code,
                execution_time=execution_time,
                sandbox_type="docker",
                metadata={"image": image, "language": language},
            )

        except Exception as e:
            return ExecutionResult(
                stdout="",
                stderr=str(e),
                success=False,
                exit_code=-1,
                execution_time=time.time() - start_time,
                sandbox_type="docker",
            )
        finally:
            # Cleanup temp file
            try:
                os.unlink(code_file)
            except Exception:
                pass

    async def _execute_e2b(
        self,
        code: str,
        language: str,
        timeout: int,
        env: Optional[Dict[str, str]] = None,
        packages: Optional[List[str]] = None,
    ) -> ExecutionResult:
        """Execute code in E2B cloud sandbox"""
        start_time = time.time()

        try:
            import httpx
        except ImportError:
            return ExecutionResult(
                stdout="",
                stderr="httpx not installed for E2B support",
                success=False,
                exit_code=-1,
                execution_time=0,
                sandbox_type="e2b",
            )

        if not self.config.e2b_api_key:
            return ExecutionResult(
                stdout="",
                stderr="E2B_API_KEY not configured",
                success=False,
                exit_code=-1,
                execution_time=0,
                sandbox_type="e2b",
            )

        api_url = "https://api.e2b.dev/v1"
        headers = {
            "Authorization": f"Bearer {self.config.e2b_api_key}",
            "Content-Type": "application/json",
        }

        sandbox_id = None

        try:
            async with httpx.AsyncClient(timeout=timeout + 10) as client:
                # Create sandbox
                create_resp = await client.post(
                    f"{api_url}/sandboxes",
                    headers=headers,
                    json={"templateID": "base"},
                )
                create_resp.raise_for_status()
                sandbox_data = create_resp.json()
                sandbox_id = sandbox_data["sandboxID"]

                # Prepare code execution
                exec_payload = {
                    "code": code,
                    "language": language,
                }

                if env:
                    exec_payload["env"] = env

                # Execute code
                exec_resp = await client.post(
                    f"{api_url}/sandboxes/{sandbox_id}/code/run",
                    headers=headers,
                    json=exec_payload,
                )
                exec_resp.raise_for_status()
                result = exec_resp.json()

                execution_time = time.time() - start_time

                return ExecutionResult(
                    stdout=result.get("stdout", ""),
                    stderr=result.get("stderr", ""),
                    success=result.get("success", False),
                    exit_code=result.get("exitCode", 0),
                    execution_time=execution_time,
                    sandbox_type="e2b",
                    metadata={"sandbox_id": sandbox_id, "language": language},
                )

        except httpx.TimeoutException:
            return ExecutionResult(
                stdout="",
                stderr=f"E2B execution timed out after {timeout}s",
                success=False,
                exit_code=-1,
                execution_time=timeout,
                sandbox_type="e2b",
            )
        except Exception as e:
            return ExecutionResult(
                stdout="",
                stderr=f"E2B error: {str(e)}",
                success=False,
                exit_code=-1,
                execution_time=time.time() - start_time,
                sandbox_type="e2b",
            )
        finally:
            # Cleanup sandbox
            if sandbox_id:
                try:
                    async with httpx.AsyncClient(timeout=5) as client:
                        await client.delete(
                            f"{api_url}/sandboxes/{sandbox_id}",
                            headers=headers,
                        )
                except Exception:
                    pass

    async def execute_with_fallback(
        self,
        code: str,
        language: str = "python",
        **kwargs
    ) -> ExecutionResult:
        """
        Execute with automatic fallback.
        Tries Docker first, falls back to E2B if Docker fails.
        """
        # Try Docker first
        if await self.check_docker():
            try:
                result = await self._execute_docker(code, language, **kwargs)
                if result.success or "timed out" not in result.stderr.lower():
                    return result
            except Exception as e:
                logger.warning(f"Docker execution failed: {e}")

        # Fall back to E2B
        if await self.check_e2b():
            logger.info("Falling back to E2B sandbox")
            return await self._execute_e2b(code, language, **kwargs)

        return ExecutionResult(
            stdout="",
            stderr="No sandbox backend available",
            success=False,
            exit_code=-1,
            execution_time=0,
            sandbox_type="none",
        )

    def get_status(self) -> Dict[str, Any]:
        """Get sandbox status"""
        return {
            "config": {
                "sandbox_type": self.config.sandbox_type.value,
                "prefer_docker": self.config.prefer_docker,
                "allow_e2b_fallback": self.config.allow_e2b_fallback,
                "timeout": self.config.timeout,
                "network_enabled": self.config.network_enabled,
            },
            "docker_available": self._docker_available,
            "e2b_available": self._e2b_available,
            "supported_languages": list(self.LANGUAGE_MAP.keys()),
        }


# Global executor instance
sandbox_executor = SandboxExecutor()
