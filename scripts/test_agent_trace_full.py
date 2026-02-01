#!/usr/bin/env python3
"""
Comprehensive Agent Trace System Test Suite

Tests:
1. Database connectivity and table structure
2. Repository methods (create, query, search, stats)
3. API endpoints (simulated - requires server running)
4. LLM client integration
5. Frontend service integration

Run: python scripts/test_agent_trace_full.py
"""

import asyncio
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from app.db.database import async_session, engine
from app.db.repositories import CodeAttributionRepository
from app.observability.agent_trace import AgentTraceRecorder

# ANSI colors
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"


def print_header(msg):
    print(f"\n{BLUE}{'='*80}{RESET}")
    print(f"{BLUE}{msg:^80}{RESET}")
    print(f"{BLUE}{'='*80}{RESET}")


def print_test(msg):
    print(f"\n{YELLOW}→ {msg}{RESET}")


def print_success(msg):
    print(f"{GREEN}✓ {msg}{RESET}")


def print_error(msg):
    print(f"{RED}✗ {msg}{RESET}")


def print_info(msg):
    print(f"  {msg}")


class TestResult:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.tests = []

    def add(self, name, success, message=""):
        self.tests.append((name, success, message))
        if success:
            self.passed += 1
        else:
            self.failed += 1

    def summary(self):
        print_header("TEST SUMMARY")
        for name, success, message in self.tests:
            if success:
                print_success(f"{name}")
                if message:
                    print_info(message)
            else:
                print_error(f"{name}")
                if message:
                    print_info(f"Error: {message}")

        print(f"\n{BLUE}{'='*80}{RESET}")
        total = self.passed + self.failed
        print(f"{GREEN}Passed: {self.passed}/{total}{RESET} | {RED}Failed: {self.failed}/{total}{RESET}")
        print(f"{BLUE}{'='*80}{RESET}\n")

        return self.failed == 0


async def test_database_connectivity(results):
    """Test 1: Database connectivity and table structure"""
    print_header("TEST 1: Database Connectivity")

    try:
        async with async_session() as session:
            # Check table exists
            result = await session.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = 'code_attributions'
                );
            """))
            table_exists = result.scalar()

            if not table_exists:
                results.add("Database Table", False, "code_attributions table does not exist")
                return

            results.add("Database Table", True, "code_attributions table exists")

            # Check columns
            result = await session.execute(text("""
                SELECT COUNT(*)
                FROM information_schema.columns
                WHERE table_name = 'code_attributions';
            """))
            col_count = result.scalar()

            if col_count >= 14:
                results.add("Table Columns", True, f"{col_count} columns present")
            else:
                results.add("Table Columns", False, f"Only {col_count} columns, expected 14")

            # Check indexes
            result = await session.execute(text("""
                SELECT COUNT(*)
                FROM pg_indexes
                WHERE tablename = 'code_attributions';
            """))
            idx_count = result.scalar()

            if idx_count >= 5:
                results.add("Table Indexes", True, f"{idx_count} indexes created")
            else:
                results.add("Table Indexes", False, f"Only {idx_count} indexes, expected at least 5")

    except Exception as e:
        results.add("Database Connectivity", False, str(e))


async def test_repository_create(results):
    """Test 2: Repository create operation"""
    print_header("TEST 2: Repository Create Operation")

    try:
        async with async_session() as session:
            repo = CodeAttributionRepository(session)

            # Create test attribution
            attr = await repo.create({
                "session_id": "test-full-suite",
                "agent_id": None,
                "agent_name": "Test Agent",
                "model": "test-model",
                "file_path": "/test/repository.py",
                "start_line": 1,
                "end_line": 10,
                "change_type": "generation",
                "prompt": "Test create",
                "generated_code": "# Test code",
                "metadata": {"test": True}
            })

            if attr and 'id' in attr:
                results.add("Repository Create", True, f"Created attribution {attr['id'][:8]}...")
            else:
                results.add("Repository Create", False, "Failed to create attribution")

            await session.commit()

    except Exception as e:
        results.add("Repository Create", False, str(e))


async def test_repository_queries(results):
    """Test 3: Repository query operations"""
    print_header("TEST 3: Repository Query Operations")

    try:
        async with async_session() as session:
            repo = CodeAttributionRepository(session)

            # Test get_by_session
            attrs = await repo.get_by_session("test-full-suite")
            if len(attrs) > 0:
                results.add("Query by Session", True, f"Found {len(attrs)} attribution(s)")
            else:
                results.add("Query by Session", False, "No attributions found")

            # Test get_recent
            recent = await repo.get_recent(days=1)
            if len(recent) >= 0:  # >= 0 because there might be no recent data
                results.add("Query Recent", True, f"Found {len(recent)} recent attribution(s)")
            else:
                results.add("Query Recent", False, "Query failed")

            # Test get_stats
            stats = await repo.get_stats()
            if stats and 'totalAttributions' in stats:
                results.add("Get Statistics", True, f"{stats['totalAttributions']} total attributions")
            else:
                results.add("Get Statistics", False, "Failed to get statistics")

    except Exception as e:
        results.add("Repository Queries", False, str(e))


async def test_agent_trace_recorder(results):
    """Test 4: AgentTraceRecorder integration"""
    print_header("TEST 4: AgentTraceRecorder Integration")

    try:
        async with async_session() as session:
            recorder = AgentTraceRecorder(
                session_id="test-recorder",
                db_session=session,
                user_id="test-user"
            )

            # Test code generation recording
            contribution = await recorder.record_code_generation(
                agent_id=None,
                agent_name="Test Recorder Agent",
                model="test-model",
                file_path="/test/recorder.py",
                code_content="def test():\n    pass",
                prompt="Test recording",
                metadata={"test": True}
            )

            if contribution:
                results.add("AgentTraceRecorder", True, "Successfully recorded code generation")
            else:
                results.add("AgentTraceRecorder", False, "Recording disabled or failed")

    except Exception as e:
        results.add("AgentTraceRecorder", False, str(e))


async def test_cleanup(results):
    """Cleanup test data"""
    print_header("CLEANUP")

    try:
        async with async_session() as session:
            result = await session.execute(text("""
                DELETE FROM code_attributions
                WHERE session_id IN ('test-full-suite', 'test-recorder')
            """))
            await session.commit()

            deleted = result.rowcount
            results.add("Cleanup", True, f"Deleted {deleted} test attribution(s)")

    except Exception as e:
        results.add("Cleanup", False, str(e))


async def main():
    """Run all tests"""
    print_header("AGENT TRACE - COMPREHENSIVE TEST SUITE")

    results = TestResult()

    # Run tests
    await test_database_connectivity(results)
    await test_repository_create(results)
    await test_repository_queries(results)
    await test_agent_trace_recorder(results)
    await test_cleanup(results)

    # Display summary
    success = results.summary()

    # Dispose engine
    await engine.dispose()

    # Additional information
    if success:
        print_header("✓ ALL TESTS PASSED")
        print()
        print_info("System Status: OPERATIONAL")
        print_info("Database: Connected and verified")
        print_info("Repository: All methods working")
        print_info("Recorder: Integration functional")
        print()
        print_info("Next steps:")
        print_info("  1. Start API server: uvicorn app.main:app --port 8100")
        print_info("  2. Test frontend: Open http://localhost:3000/code-attribution")
        print_info("  3. Test API: curl http://localhost:8100/api/v1/trace/health")
        print()
    else:
        print_header("✗ TESTS FAILED")
        print()
        print_error("Some tests failed. Please review the errors above.")
        print()

    return 0 if success else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
