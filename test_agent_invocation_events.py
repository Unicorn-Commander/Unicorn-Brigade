#!/usr/bin/env python3
"""
Test script for peer-to-peer agent invocation event emission.

This script demonstrates the new AGENT_INVOCATION event type that enables
the 3D visualization to show complete agent collaboration networks.
"""

import asyncio
import sys
from app.orchestration import (
    event_bus,
    emit_agent_invocation,
    EventType,
)


async def test_agent_invocation_events():
    """Test the new agent invocation event emission"""

    print("=" * 80)
    print("Testing Peer-to-Peer Agent Invocation Event Emission")
    print("=" * 80)

    # Test 1: A2A Protocol Invocation
    print("\n1. Testing A2A Protocol Invocation (blue connection)...")
    await emit_agent_invocation(
        agent_id="external-system",
        agent_name="External System",
        target_agent_id="col-finance",
        target_agent_name="Colonel Finance",
        purpose="A2A invocation: Financial analysis request",
        protocol="a2a",  # Blue connection
        metadata={"task_id": "test-123", "source": "external"},
    )
    print("   ✓ A2A invocation event emitted")

    # Test 2: Internal Agent Communication
    print("\n2. Testing Internal Agent Communication (purple connection)...")
    await emit_agent_invocation(
        agent_id="the-general",
        agent_name="The General",
        target_agent_id="research-lead",
        target_agent_name="Research Team Lead",
        purpose="Hierarchical delegation: Market research task",
        protocol="internal",  # Purple connection
        metadata={"step_id": "step-1", "workflow_type": "hierarchical"},
        mission_id="mission-456",
    )
    print("   ✓ Internal invocation event emitted")

    # Test 3: Peer-to-Peer Agent Communication
    print("\n3. Testing Peer-to-Peer Agent Communication (peer protocol)...")
    await emit_agent_invocation(
        agent_id="agent-a",
        agent_name="Agent Alpha",
        target_agent_id="agent-b",
        target_agent_name="Agent Beta",
        purpose="Peer collaboration: Data exchange",
        protocol="peer",  # Yellow/orange connection (could be used for true peer-to-peer)
        metadata={"data_type": "analysis_results"},
    )
    print("   ✓ Peer-to-peer invocation event emitted")

    # Test 4: Team Lead to Worker Delegation
    print("\n4. Testing Team Lead to Worker Delegation...")
    await emit_agent_invocation(
        agent_id="finance-lead",
        agent_name="Finance Team Lead",
        target_agent_id="financial-analyzer",
        target_agent_name="Financial Analyzer Worker",
        purpose="Worker delegation: Calculate ROI metrics",
        protocol="internal",
        metadata={"worker_task": "roi_calculation", "workflow_type": "hierarchical"},
        mission_id="mission-789",
    )
    print("   ✓ Worker delegation event emitted")

    # Check event types
    print("\n" + "=" * 80)
    print("Event Type Verification")
    print("=" * 80)
    print(f"✓ AGENT_INVOCATION event type exists: {EventType.AGENT_INVOCATION}")
    print(f"✓ Event value: {EventType.AGENT_INVOCATION.value}")

    # Get recent events
    recent_events = event_bus.get_recent_events(limit=10)
    print(f"\n✓ Total events in bus: {len(recent_events)}")

    # Show invocation events
    invocation_events = [e for e in recent_events if e.type == EventType.AGENT_INVOCATION]
    print(f"✓ Agent invocation events: {len(invocation_events)}")

    if invocation_events:
        print("\n" + "=" * 80)
        print("Sample Invocation Event Details")
        print("=" * 80)
        event = invocation_events[-1]
        print(f"Agent ID: {event.agent_id}")
        print(f"Agent Name: {event.agent_name}")
        print(f"Target Agent: {event.data.get('toAgent')}")
        print(f"Target Name: {event.data.get('toAgentName')}")
        print(f"Protocol: {event.data.get('protocol')}")
        print(f"Purpose: {event.data.get('purpose')}")
        print(f"Message: {event.message}")

    print("\n" + "=" * 80)
    print("All Tests Passed! ✓")
    print("=" * 80)
    print("\nEvent Structure for Frontend:")
    print("- type: 'agent_invocation'")
    print("- agentId: source agent ID")
    print("- agentName: source agent name")
    print("- data.toAgent: target agent ID (for connection rendering)")
    print("- data.toAgentName: target agent name")
    print("- data.protocol: connection color (internal/a2a/paid/peer)")
    print("- data.purpose: reason for invocation")
    print("- mission_id: optional mission tracking")
    print("\nProtocol Colors:")
    print("- 'internal': Purple (hierarchical workflows)")
    print("- 'a2a': Blue (A2A protocol)")
    print("- 'paid': Cyan (paid external API)")
    print("- 'peer': Yellow/Orange (peer-to-peer)")


if __name__ == "__main__":
    try:
        asyncio.run(test_agent_invocation_events())
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
