"""
Agent Trace Example - Code Attribution Tracking Demo

This script demonstrates how to use Agent Trace to track code generation
by AI agents, query attributions, and generate compliance reports.
"""

import asyncio
import sys
import os
from datetime import datetime, timedelta

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.database import async_session
from app.observability import (
    AgentTraceRecorder,
    TraceRepository,
    CodeExtractor,
)
from app.observability.langfuse_client import get_tracer


async def example_1_manual_recording():
    """Example 1: Manually record code generation"""
    print("\n=== Example 1: Manual Code Recording ===\n")

    async with async_session() as db_session:
        # Create trace recorder
        recorder = AgentTraceRecorder(
            session_id="demo-session-1",
            db_session=db_session,
            user_id="demo-user",
        )

        # Record a code generation
        contribution = await recorder.record_code_generation(
            agent_id="claude-sonnet",
            agent_name="Claude Sonnet 4.5",
            model="claude-sonnet-4-5-20250929",
            file_path="/app/api/demo_endpoint.py",
            code_content='''@router.get("/demo")
async def demo_endpoint():
    """Demo endpoint for testing"""
    return {"message": "Hello from AI-generated code!"}
''',
            prompt="Create a simple demo endpoint",
            start_line=1,
            metadata={
                "language": "python",
                "framework": "fastapi",
                "tokens_used": 150,
            },
        )

        if contribution:
            print(f"✅ Recorded code generation:")
            print(f"   Agent: {contribution.agent_name}")
            print(f"   File: {contribution.location.file_path}")
            print(f"   Lines: {contribution.location.start_line}-{contribution.location.end_line}")
            print(f"   Hash: {contribution.code_hash}")
        else:
            print("❌ Agent Trace is disabled (set AGENT_TRACE_ENABLED=true)")


async def example_2_auto_extraction():
    """Example 2: Auto-extract code from LLM response"""
    print("\n=== Example 2: Auto-Extraction from LLM Response ===\n")

    # Simulate an LLM response with code
    llm_response = '''
Here's a user authentication function:

```python
# File: app/auth/authenticate.py
async def authenticate_user(username: str, password: str) -> User:
    """Authenticate a user with username and password"""
    user = await get_user(username)
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return user
```

This function checks credentials and returns the user object.
'''

    async with async_session() as db_session:
        recorder = AgentTraceRecorder(
            session_id="demo-session-2",
            db_session=db_session,
            user_id="demo-user",
        )

        # Auto-extract and record
        contributions = await recorder.record_from_llm_response(
            agent_id="claude-sonnet",
            agent_name="Claude Sonnet 4.5",
            model="claude-sonnet-4-5-20250929",
            prompt="Create user authentication function",
            response=llm_response,
            metadata={
                "auto_extracted": True,
                "response_length": len(llm_response),
            },
        )

        print(f"✅ Auto-extracted {len(contributions)} code block(s):")
        for contrib in contributions:
            print(f"   - {contrib.location.file_path} ({contrib.metadata.get('language', 'unknown')})")


async def example_3_querying():
    """Example 3: Query attributions"""
    print("\n=== Example 3: Query Attributions ===\n")

    async with async_session() as db_session:
        repo = TraceRepository(db_session)

        # Query by agent
        agent_attributions = await repo.get_by_agent(
            agent_id="claude-sonnet",
            limit=5,
        )
        print(f"📊 Found {len(agent_attributions)} attribution(s) by claude-sonnet")

        # Query recent attributions
        recent = await repo.get_by_date_range(
            start_date=datetime.utcnow() - timedelta(days=7),
            limit=10,
        )
        print(f"📊 Found {len(recent)} recent attribution(s) in last 7 days")


async def example_4_file_history():
    """Example 4: Get file modification history"""
    print("\n=== Example 4: File History ===\n")

    async with async_session() as db_session:
        repo = TraceRepository(db_session)

        # Get history for a file
        history = await repo.get_file_history(
            file_path="/app/api/demo_endpoint.py",
            limit=10,
        )

        if history.get("total_modifications", 0) > 0:
            print(f"📁 File: {history['file_path']}")
            print(f"   Total modifications: {history['total_modifications']}")
            print(f"   Agents involved: {', '.join(history['agents_involved'])}")
            print(f"   Models used: {', '.join(history['models_used'])}")
            print(f"   First created: {history.get('first_created', 'N/A')}")
            print(f"   Last modified: {history.get('last_modified', 'N/A')}")
        else:
            print(f"ℹ️  No history found for /app/api/demo_endpoint.py")


async def example_5_agent_statistics():
    """Example 5: Get agent statistics"""
    print("\n=== Example 5: Agent Statistics ===\n")

    async with async_session() as db_session:
        repo = TraceRepository(db_session)

        # Get stats for an agent
        stats = await repo.get_agent_statistics(
            agent_id="claude-sonnet",
            days=30,
        )

        print(f"📈 Agent Statistics (last 30 days):")
        print(f"   Agent ID: {stats['agent_id']}")
        print(f"   Total contributions: {stats['total_contributions']}")
        print(f"   Files modified: {stats['files_modified']}")
        print(f"   Total lines: {stats['total_lines_modified']}")
        print(f"   Models used: {stats.get('models_used', {})}")
        print(f"   Change types: {stats.get('change_types', {})}")


async def example_6_compliance_report():
    """Example 6: Generate compliance report"""
    print("\n=== Example 6: Compliance Report ===\n")

    async with async_session() as db_session:
        repo = TraceRepository(db_session)

        # Generate summary report
        report = await repo.generate_compliance_report(
            start_date=datetime.utcnow() - timedelta(days=30),
            end_date=datetime.utcnow(),
            format="summary",
        )

        print(f"📋 Compliance Report:")
        print(f"   Report type: {report.get('report_type', 'N/A')}")
        print(f"   Period: {report.get('period', {}).get('days', 0)} days")

        summary = report.get('summary', {})
        print(f"\n   Summary:")
        print(f"   - Total contributions: {summary.get('total_contributions', 0)}")
        print(f"   - Unique agents: {summary.get('unique_agents', 0)}")
        print(f"   - Files modified: {summary.get('files_modified', 0)}")
        print(f"   - Unique sessions: {summary.get('unique_sessions', 0)}")

        agents = report.get('agents', {})
        if agents:
            print(f"\n   Top Agents:")
            for agent_id, data in list(agents.items())[:3]:
                print(f"   - {data['name']}: {data['contributions']} contributions")


async def example_7_code_extractor():
    """Example 7: Use CodeExtractor utility"""
    print("\n=== Example 7: Code Extractor Utility ===\n")

    # Example text with code blocks
    text = '''
Here are two implementations:

```python
def hello():
    print("Hello!")
```

And a JavaScript version:

```javascript
function hello() {
    console.log("Hello!");
}
```
'''

    # Extract code blocks
    code_blocks = CodeExtractor.extract_code_blocks(text)
    print(f"🔍 Found {len(code_blocks)} code block(s):")
    for language, code in code_blocks:
        print(f"   - Language: {language or 'unknown'}")
        print(f"     Lines: {len(code.splitlines())}")
        hash_value = CodeExtractor.compute_code_hash(code)
        print(f"     Hash: {hash_value}")


async def example_8_langfuse_integration():
    """Example 8: Integration with Langfuse"""
    print("\n=== Example 8: Langfuse Integration ===\n")

    # Create Langfuse tracer
    langfuse_tracer = get_tracer(
        agent_id="claude-sonnet",
        session_id="demo-session-langfuse",
        user_id="demo-user",
    )

    # Start Langfuse trace
    langfuse_tracer.start_trace(
        name="code_generation_with_attribution",
        input_data={"prompt": "Create a hello world function"},
    )

    async with async_session() as db_session:
        # Create Agent Trace recorder with Langfuse integration
        recorder = AgentTraceRecorder(
            session_id="demo-session-langfuse",
            db_session=db_session,
            langfuse_tracer=langfuse_tracer,  # Enable correlation
            user_id="demo-user",
        )

        # Record code (will appear as span in Langfuse)
        await recorder.record_code_generation(
            agent_id="claude-sonnet",
            agent_name="Claude Sonnet 4.5",
            model="claude-sonnet-4-5-20250929",
            file_path="/app/examples/hello.py",
            code_content='def hello():\n    return "Hello, World!"\n',
            prompt="Create a hello world function",
        )

        print("✅ Code attribution recorded and logged to Langfuse")

    # End Langfuse trace
    langfuse_tracer.end_trace(
        output={"code_generated": True},
        status="success",
    )


async def main():
    """Run all examples"""
    print("\n" + "="*60)
    print("  Agent Trace - Code Attribution Tracking Examples")
    print("="*60)

    try:
        await example_1_manual_recording()
        await example_2_auto_extraction()
        await example_3_querying()
        await example_4_file_history()
        await example_5_agent_statistics()
        await example_6_compliance_report()
        await example_7_code_extractor()
        await example_8_langfuse_integration()

        print("\n" + "="*60)
        print("  ✅ All examples completed successfully!")
        print("="*60 + "\n")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
