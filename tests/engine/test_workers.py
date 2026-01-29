"""
Tests for workers
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from app.workers import (
    get_worker, list_workers, WORKER_REGISTRY,
    ResearchWorker, CodeWorker, ExtractorWorker,
    ReportWorker, OpsWorker, WorkerResult, WorkerStatus,
)


class TestWorkerRegistry:
    """Tests for worker registry"""

    def test_all_workers_registered(self):
        """Verify all expected workers are registered"""
        expected = [
            "research", "deep_research", "code",
            "extractor", "table_extractor", "entity_extractor",
            "report", "summary", "digest",
            "ops", "database",
        ]

        for worker_type in expected:
            assert worker_type in WORKER_REGISTRY, f"Missing worker: {worker_type}"

    def test_get_worker(self):
        """Test getting worker by type"""
        worker = get_worker("research")
        assert isinstance(worker, ResearchWorker)

    def test_get_worker_invalid_type(self):
        """Test error on invalid worker type"""
        with pytest.raises(ValueError) as exc_info:
            get_worker("nonexistent")

        assert "Unknown worker type" in str(exc_info.value)

    def test_list_workers(self):
        """Test listing all workers"""
        workers = list_workers()

        assert len(workers) > 0
        assert all("type" in w for w in workers)
        assert all("name" in w for w in workers)
        assert all("description" in w for w in workers)


class TestResearchWorker:
    """Tests for ResearchWorker"""

    @pytest.fixture
    def mock_llm_client(self):
        """Create mock LLM client"""
        client = MagicMock()
        client.chat_completion = AsyncMock(return_value={
            "choices": [{
                "message": {
                    "content": """## Summary
AI trends are advancing rapidly.

## Key Findings
- Large language models are improving
- Multimodal AI is emerging
- Edge AI is growing

## Confidence: high"""
                }
            }],
            "usage": {"prompt_tokens": 100, "completion_tokens": 200}
        })
        return client

    @pytest.fixture
    def worker(self, mock_llm_client):
        """Create worker with mock client"""
        return ResearchWorker(llm_client=mock_llm_client)

    @pytest.mark.asyncio
    async def test_execute_research(self, worker):
        """Test basic research execution"""
        result = await worker.execute(
            task="What are current AI trends?",
            user_id="test",
        )

        assert result.status == WorkerStatus.COMPLETED
        assert result.output is not None
        assert len(result.artifacts) > 0

    @pytest.mark.asyncio
    async def test_extract_findings(self, worker):
        """Test finding extraction"""
        result = await worker.execute(
            task="Research Python best practices",
            user_id="test",
        )

        # Should have key_findings artifact
        findings_artifact = next(
            (a for a in result.artifacts if a.name == "key_findings"),
            None
        )
        assert findings_artifact is not None
        assert isinstance(findings_artifact.content, list)

    @pytest.mark.asyncio
    async def test_worker_timeout(self):
        """Test worker timeout handling"""
        slow_client = MagicMock()

        async def slow_response(*args, **kwargs):
            import asyncio
            await asyncio.sleep(10)  # Longer than timeout
            return {"choices": [{"message": {"content": "Done"}}]}

        slow_client.chat_completion = slow_response

        worker = ResearchWorker(llm_client=slow_client, timeout=1)

        result = await worker.execute(task="Test", user_id="test")

        assert result.status == WorkerStatus.TIMEOUT

    def test_worker_info(self, worker):
        """Test getting worker info"""
        info = worker.get_info()

        assert info["name"] == "ResearchWorker"
        assert info["timeout"] > 0


class TestCodeWorker:
    """Tests for CodeWorker"""

    @pytest.fixture
    def mock_llm_client(self):
        """Create mock LLM client"""
        client = MagicMock()
        client.chat_completion = AsyncMock(return_value={
            "choices": [{
                "message": {
                    "content": """Here's a function to sort a list:

```python
def sort_list(items):
    return sorted(items)
```

This uses Python's built-in sorted() function."""
                }
            }],
            "usage": {"prompt_tokens": 50, "completion_tokens": 100}
        })
        return client

    @pytest.fixture
    def worker(self, mock_llm_client):
        """Create worker with mock client"""
        return CodeWorker(llm_client=mock_llm_client)

    @pytest.mark.asyncio
    async def test_code_generation(self, worker):
        """Test code generation"""
        result = await worker.execute(
            task="Write a function to sort a list",
            user_id="test",
        )

        assert result.status == WorkerStatus.COMPLETED
        assert "python" in result.output.lower() or "def " in result.output

    @pytest.mark.asyncio
    async def test_extract_code_blocks(self, worker):
        """Test code block extraction"""
        result = await worker.execute(
            task="Write Python code",
            user_id="test",
        )

        code_artifacts = [a for a in result.artifacts if a.type == "code"]
        assert len(code_artifacts) > 0

    @pytest.mark.asyncio
    async def test_code_review_mode(self, worker, mock_llm_client):
        """Test code review detection"""
        mock_llm_client.chat_completion.return_value = {
            "choices": [{
                "message": {
                    "content": """## Code Review

### Issues Found
- warning: Variable name too short
- info: Consider adding type hints

### Suggestions
- Use more descriptive names"""
                }
            }],
            "usage": {"prompt_tokens": 100, "completion_tokens": 150}
        }

        result = await worker.execute(
            task="Review this code for issues",
            context={"code": "def f(x): return x*2"},
            user_id="test",
        )

        assert result.status == WorkerStatus.COMPLETED


class TestExtractorWorker:
    """Tests for ExtractorWorker"""

    @pytest.fixture
    def mock_llm_client(self):
        """Create mock LLM client"""
        client = MagicMock()
        client.chat_completion = AsyncMock(return_value={
            "choices": [{
                "message": {
                    "content": '''```json
{
    "name": "John Doe",
    "email": "john@example.com",
    "date": "2024-01-15"
}
```'''
                }
            }],
            "usage": {"prompt_tokens": 100, "completion_tokens": 50}
        })
        return client

    @pytest.fixture
    def worker(self, mock_llm_client):
        """Create worker with mock client"""
        return ExtractorWorker(llm_client=mock_llm_client)

    @pytest.mark.asyncio
    async def test_extract_json(self, worker):
        """Test JSON extraction"""
        result = await worker.execute(
            task="Extract contact info",
            context={"text": "Contact John Doe at john@example.com. Date: Jan 15, 2024"},
            user_id="test",
        )

        assert result.status == WorkerStatus.COMPLETED

        extracted = next(
            (a for a in result.artifacts if a.name == "extracted_data"),
            None
        )
        assert extracted is not None
        assert extracted.content is not None

    @pytest.mark.asyncio
    async def test_extract_with_schema(self, worker):
        """Test extraction with schema"""
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "email": {"type": "string"},
            },
            "required": ["name", "email"]
        }

        result = await worker.execute(
            task="Extract contact information",
            context={
                "text": "John Doe - john@example.com",
                "schema": schema,
            },
            user_id="test",
        )

        assert result.status == WorkerStatus.COMPLETED


class TestOpsWorker:
    """Tests for OpsWorker"""

    @pytest.fixture
    def worker(self):
        """Create ops worker"""
        return OpsWorker(enable_shell=True, sandbox_mode=True)

    def test_security_check_blocked_commands(self, worker):
        """Test blocking dangerous commands"""
        blocked_commands = [
            "rm -rf /",
            ":(){ :|:& };:",
            "dd if=/dev/zero of=/dev/sda",
        ]

        for cmd in blocked_commands:
            result = worker._check_command_security(cmd)
            assert result["allowed"] is False

    def test_security_check_risky_commands(self, worker):
        """Test flagging risky commands"""
        risky_commands = [
            "rm -rf /tmp/data",
            "curl http://example.com",
            "pip install package",
        ]

        for cmd in risky_commands:
            result = worker._check_command_security(cmd)
            if result["allowed"]:
                assert result.get("requires_approval", False) is True

    def test_security_check_safe_commands(self, worker):
        """Test allowing safe commands"""
        safe_commands = [
            "ls -la",
            "pwd",
            "echo hello",
            "cat file.txt",
        ]

        for cmd in safe_commands:
            result = worker._check_command_security(cmd)
            assert result["allowed"] is True
            assert result.get("requires_approval", False) is False

    def test_detect_operation_type(self, worker):
        """Test operation type detection"""
        assert worker._detect_op_type("run ls command", {}) == "shell"
        assert worker._detect_op_type("call the API", {"url": "..."}) == "api"
        assert worker._detect_op_type("read the file", {"path": "..."}) == "file"

    @pytest.mark.asyncio
    async def test_shell_disabled(self):
        """Test with shell disabled"""
        worker = OpsWorker(enable_shell=False)

        result = await worker.execute(
            task="Run a command",
            context={"command": "ls"},
            user_id="test",
        )

        assert result.status == WorkerStatus.FAILED
        assert "disabled" in result.error.lower()
