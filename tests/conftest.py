"""Test configuration and fixtures"""

import pytest
import os
from dotenv import load_dotenv

# Load test environment
load_dotenv()

# Set test environment variables if not already set
if not os.getenv("OPENAI_API_KEY"):
    os.environ["OPENAI_API_KEY"] = "sk-test-key-for-testing"

if not os.getenv("QDRANT_URL"):
    os.environ["QDRANT_URL"] = "http://localhost:6333"

@pytest.fixture
def test_task():
    """Sample task for testing"""
    return {
        "task_id": "test-123",
        "task": "Research Python testing best practices",
        "user_id": "test-user",
        "context": {}
    }

@pytest.fixture
def test_user_id():
    """Test user ID"""
    return "test-user-123"
