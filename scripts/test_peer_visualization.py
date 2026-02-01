#!/usr/bin/env python3
"""
Test script for peer-to-peer connection visualization.

This script verifies that:
1. Backend emits agent_invocation events correctly
2. Frontend receives and displays peer-to-peer connections in yellow
3. Activity feed shows peer invocations distinctly
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.orchestration import emit_agent_invocation

async def test_peer_invocation():
    """Test peer-to-peer agent invocation event emission"""
    
    print("🔧 Testing peer-to-peer agent invocation...")
    print("-" * 60)
    
    # Test case 1: Data agent invoking financial agent
    print("\n📊 Test 1: Data agent → Finance agent")
    await emit_agent_invocation(
        agent_id="sgt-data",
        agent_name="Sgt. Data Analyst",
        target_agent_id="col-finance",
        target_agent_name="Col. Finance",
        purpose="Request financial metrics for Q4 analysis",
        protocol="peer",
        mission_id="test-mission-1"
    )
    print("✓ Event emitted successfully")
    
    await asyncio.sleep(1)
    
    # Test case 2: Specialist invoking another specialist
    print("\n🔍 Test 2: Research agent → Legal agent")
    await emit_agent_invocation(
        agent_id="lt-researcher",
        agent_name="Lt. Researcher",
        target_agent_id="capt-legal",
        target_agent_name="Capt. Legal",
        purpose="Legal precedent verification",
        protocol="peer",
        mission_id="test-mission-2"
    )
    print("✓ Event emitted successfully")
    
    await asyncio.sleep(1)
    
    # Test case 3: External A2A invocation (should be blue, not yellow)
    print("\n🌐 Test 3: A2A protocol invocation (should be blue)")
    await emit_agent_invocation(
        agent_id="col-finance",
        agent_name="Col. Finance",
        target_agent_id="external-market-data",
        target_agent_name="External Market Data Agent",
        purpose="Fetch real-time market data",
        protocol="a2a",
        mission_id="test-mission-3"
    )
    print("✓ Event emitted successfully")
    
    print("\n" + "=" * 60)
    print("✅ All test events emitted successfully!")
    print("\n📋 Frontend Verification Checklist:")
    print("   1. Open http://localhost:5173/orchestration")
    print("   2. Check Activity Feed for yellow peer invocations")
    print("   3. Verify 3D visualization shows yellow connections")
    print("   4. Confirm legend shows 'Peer-to-Peer' in yellow")
    print("   5. A2A invocation should be blue, not yellow")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_peer_invocation())
