"""
Tests for Remote Code Execution Service
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from app.services.remote_executor import RemoteExecutor


@pytest.fixture
def mock_ops_center_url():
    return "http://test-ops-center:8000"


@pytest.fixture
def user_id():
    return "test-user-123"


@pytest.fixture
def remote_executor(user_id, mock_ops_center_url):
    return RemoteExecutor(user_id, mock_ops_center_url)


class TestRemoteExecutor:
    """Test suite for RemoteExecutor"""

    @pytest.mark.asyncio
    async def test_get_server_config_ssh(self, remote_executor):
        """Test fetching SSH server configuration"""
        mock_config = {
            "type": "ssh",
            "connection": {
                "host": "example.com",
                "port": 22,
                "username": "testuser",
                "keyPath": "/path/to/key",
                "workspaceRoot": "/home/testuser/workspace"
            },
            "enabled": True
        }

        with patch('httpx.AsyncClient') as mock_client:
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_config
            mock_response.raise_for_status = Mock()

            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            config = await remote_executor.get_server_config()

            assert config["type"] == "ssh"
            assert config["connection"]["host"] == "example.com"

    @pytest.mark.asyncio
    async def test_get_server_config_fallback_to_local(self, remote_executor):
        """Test fallback to local when no server configured"""
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = AsyncMock()
            mock_response.status_code = 404

            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            config = await remote_executor.get_server_config()

            assert config["type"] == "local"
            assert config["enabled"] is True

    @pytest.mark.asyncio
    async def test_execute_local_python(self, remote_executor):
        """Test local Python code execution"""
        code = "print('Hello, World!')"
        language = "python"

        with patch('docker.from_env') as mock_docker:
            # Mock container
            mock_container = MagicMock()
            mock_container.wait.return_value = {"StatusCode": 0}
            mock_container.logs.return_value = b"Hello, World!\n"

            # Mock client
            mock_client = MagicMock()
            mock_client.containers.run.return_value = mock_container
            mock_docker.return_value = mock_client

            # Force local execution
            remote_executor.server_config = {"type": "local", "enabled": True}

            result = await remote_executor.execute_code(language, code)

            assert result["success"] is True
            assert "Hello, World!" in result["output"]
            assert result["exit_code"] == 0
            assert result["language"] == "python"
            assert result["execution_type"] == "local"

    @pytest.mark.asyncio
    async def test_execute_timeout(self, remote_executor):
        """Test execution timeout handling"""
        code = "import time; time.sleep(100)"
        language = "python"

        with patch('docker.from_env') as mock_docker:
            mock_container = MagicMock()

            # Simulate timeout
            async def wait_timeout():
                await asyncio.sleep(100)
                return {"StatusCode": 0}

            mock_container.wait = lambda: asyncio.run(wait_timeout())

            mock_client = MagicMock()
            mock_client.containers.run.return_value = mock_container
            mock_docker.return_value = mock_client

            remote_executor.server_config = {"type": "local", "enabled": True}

            result = await remote_executor.execute_code(language, code, timeout=1)

            assert result["success"] is False
            assert "timeout" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_sanitize_path_security(self, remote_executor):
        """Test path sanitization prevents directory traversal"""
        with pytest.raises(ValueError, match="outside allowed workspace"):
            remote_executor._sanitize_path("../../etc/passwd", "/tmp/workspace")

    @pytest.mark.asyncio
    async def test_language_command_mapping(self, remote_executor):
        """Test language to command mapping"""
        assert "python" in RemoteExecutor.LANGUAGE_COMMANDS
        assert "javascript" in RemoteExecutor.LANGUAGE_COMMANDS
        assert "go" in RemoteExecutor.LANGUAGE_COMMANDS

        python_config = RemoteExecutor.LANGUAGE_COMMANDS["python"]
        assert python_config["ext"] == "py"
        assert "python3" in python_config["cmd"]

    @pytest.mark.asyncio
    async def test_execute_javascript_local(self, remote_executor):
        """Test local JavaScript execution"""
        code = "console.log('Hello from Node');"
        language = "javascript"

        with patch('docker.from_env') as mock_docker:
            mock_container = MagicMock()
            mock_container.wait.return_value = {"StatusCode": 0}
            mock_container.logs.return_value = b"Hello from Node\n"

            mock_client = MagicMock()
            mock_client.containers.run.return_value = mock_container
            mock_docker.return_value = mock_client

            remote_executor.server_config = {"type": "local", "enabled": True}

            result = await remote_executor.execute_code(language, code)

            assert result["success"] is True
            assert result["language"] == "javascript"

    @pytest.mark.asyncio
    async def test_execute_code_error_handling(self, remote_executor):
        """Test error handling during code execution"""
        code = "this will cause an error"
        language = "python"

        with patch('docker.from_env') as mock_docker:
            mock_container = MagicMock()
            mock_container.wait.return_value = {"StatusCode": 1}
            mock_container.logs.return_value = b"SyntaxError: invalid syntax\n"

            mock_client = MagicMock()
            mock_client.containers.run.return_value = mock_container
            mock_docker.return_value = mock_client

            remote_executor.server_config = {"type": "local", "enabled": True}

            result = await remote_executor.execute_code(language, code)

            assert result["success"] is False
            assert result["exit_code"] == 1
            assert "SyntaxError" in result["output"]

    @pytest.mark.asyncio
    async def test_unsupported_language(self, remote_executor):
        """Test handling of unsupported languages"""
        code = "some code"
        language = "brainfuck"

        remote_executor.server_config = {"type": "local", "enabled": True}

        with pytest.raises(ValueError, match="Unsupported language"):
            await remote_executor.execute_code(language, code)


class TestSSHExecution:
    """Test SSH-based remote execution"""

    @pytest.mark.asyncio
    async def test_ssh_connection_mock(self, remote_executor):
        """Test SSH connection and execution (mocked)"""
        code = "print('SSH Test')"
        language = "python"

        config = {
            "type": "ssh",
            "connection": {
                "host": "remote.example.com",
                "port": 22,
                "username": "testuser",
                "keyPath": "/path/to/key",
                "workspaceRoot": "/home/testuser/workspace"
            }
        }

        remote_executor.server_config = config

        with patch('asyncssh.connect') as mock_connect:
            # Mock SSH connection
            mock_conn = AsyncMock()
            mock_sftp = AsyncMock()
            mock_file = AsyncMock()

            mock_sftp.open = AsyncMock(return_value=mock_file)
            mock_file.__aenter__.return_value = mock_file
            mock_file.__aexit__.return_value = None

            mock_conn.start_sftp_client.return_value = mock_sftp
            mock_sftp.__aenter__.return_value = mock_sftp
            mock_sftp.__aexit__.return_value = None

            mock_result = AsyncMock()
            mock_result.exit_status = 0
            mock_result.stdout = "SSH Test\n"
            mock_result.stderr = ""

            mock_conn.run = AsyncMock(return_value=mock_result)
            mock_conn.__aenter__.return_value = mock_conn
            mock_conn.__aexit__.return_value = None

            mock_connect.return_value = mock_conn

            result = await remote_executor.execute_code(language, code)

            assert result["execution_type"] == "ssh"
            mock_connect.assert_called()


class TestDockerExecution:
    """Test Docker-based remote execution"""

    @pytest.mark.asyncio
    async def test_docker_custom_image(self, remote_executor):
        """Test Docker execution with custom image"""
        code = "print('Docker Test')"
        language = "python"

        config = {
            "type": "docker",
            "connection": {
                "image": "python:3.9-slim",
                "memoryLimit": "256m",
                "cpuQuota": 50000
            }
        }

        remote_executor.server_config = config

        with patch('docker.from_env') as mock_docker:
            mock_container = MagicMock()
            mock_container.wait.return_value = {"StatusCode": 0}
            mock_container.logs.return_value = b"Docker Test\n"

            mock_client = MagicMock()
            mock_client.containers.run.return_value = mock_container
            mock_docker.return_value = mock_client

            result = await remote_executor.execute_code(language, code)

            assert result["execution_type"] == "docker"
            assert result["success"] is True


class TestFileOperations:
    """Test remote file operations"""

    @pytest.mark.asyncio
    async def test_read_file_local(self, remote_executor):
        """Test reading file locally"""
        test_content = "Test file content"
        test_path = "/tmp/brigade_workspace/test.txt"

        remote_executor.server_config = {"type": "local", "enabled": True}

        with patch('builtins.open', create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = test_content

            content = await remote_executor.read_file(test_path)

            assert content == test_content

    @pytest.mark.asyncio
    async def test_write_file_local(self, remote_executor):
        """Test writing file locally"""
        test_content = "New file content"
        test_path = "/tmp/brigade_workspace/output.txt"

        remote_executor.server_config = {"type": "local", "enabled": True}

        with patch('builtins.open', create=True) as mock_open, \
             patch('os.makedirs') as mock_makedirs:

            success = await remote_executor.write_file(test_path, test_content)

            assert success is True
            mock_makedirs.assert_called()
