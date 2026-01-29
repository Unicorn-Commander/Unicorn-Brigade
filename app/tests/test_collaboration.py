"""
Tests for Multi-Agent Collaboration Patterns (app/engine/collaboration.py)

Tests:
- Supervisor pattern execution
- Swarm pattern with handoffs
- Agent capability definitions
- Handoff context management
- Shared memory management
"""

import pytest
import asyncio
from datetime import datetime

from app.engine.collaboration import (
    CollaborationAgent,
    AgentRole,
    AgentCapability,
    HandoffReason,
    HandoffContext,
    AgentMessage,
    CollaborationState,
    SupervisorPattern,
    SwarmPattern,
    SharedMemoryManager,
    AgentTeamFactory,
)
from app.llm.ops_center_client import ToolDefinition, ToolParameter


# ============== Agent Definition Tests ==============

class TestCollaborationAgent:
    """Test agent definition and configuration"""

    def test_agent_creation(self, test_supervisor_agent):
        """Should create agent with correct attributes"""
        agent = test_supervisor_agent

        assert agent.id == "supervisor"
        assert agent.name == "Test Supervisor"
        assert agent.role == AgentRole.SUPERVISOR
        assert len(agent.system_prompt) > 0

    def test_agent_to_tool_conversion(self, test_specialist_agents):
        """Agent should convert to a handoff tool"""
        specialist = test_specialist_agents[0]
        tool = specialist.to_tool()

        assert tool.name == "handoff_to_specialist_a"
        assert "Specialist A" in tool.description
        assert len(tool.parameters) >= 1

        # Should have task parameter
        task_param = next((p for p in tool.parameters if p.name == "task"), None)
        assert task_param is not None
        assert task_param.required is True

    def test_agent_capabilities(self):
        """Should define agent capabilities"""
        capability = AgentCapability(
            name="web_search",
            description="Search the web",
            domains=["research", "fact-checking"],
            tools=["search_tool", "scrape_tool"]
        )

        agent = CollaborationAgent(
            id="researcher",
            name="Researcher",
            role=AgentRole.SPECIALIST,
            description="Research specialist",
            system_prompt="You are a researcher",
            capabilities=[capability],
        )

        assert len(agent.capabilities) == 1
        assert agent.capabilities[0].name == "web_search"
        assert "research" in agent.capabilities[0].domains


# ============== Handoff Context Tests ==============

class TestHandoffContext:
    """Test structured handoff context"""

    def test_handoff_context_creation(self):
        """Should create structured handoff context"""
        context = HandoffContext(
            task="Analyze the sales data",
            intent="data_analysis",
            entities={"data_source": "sales_db", "time_range": "Q4"},
            relevant_facts=["Data is updated daily", "Q4 has 3 months"],
            pending_actions=["Extract data", "Generate report"],
        )

        assert context.task == "Analyze the sales data"
        assert context.intent == "data_analysis"
        assert "data_source" in context.entities
        assert len(context.relevant_facts) == 2

    def test_handoff_context_from_free_text(self):
        """Should create context from free text"""
        text = "Please help me analyze the quarterly sales report and identify trends"
        context = HandoffContext.from_free_text(text)

        assert context.task == text
        assert len(context.conversation_summary) > 0


# ============== Agent Message Tests ==============

class TestAgentMessage:
    """Test agent message handling"""

    def test_message_creation(self):
        """Should create message with defaults"""
        msg = AgentMessage(
            sender_id="agent1",
            sender_name="Agent One",
            content="Hello from agent"
        )

        assert msg.sender_id == "agent1"
        assert msg.role == "assistant"
        assert msg.id is not None
        assert msg.timestamp is not None

    def test_message_to_llm_format(self):
        """Should convert to LLM message format"""
        msg = AgentMessage(
            role="user",
            content="Test content"
        )

        llm_msg = msg.to_llm_message()

        assert llm_msg["role"] == "user"
        assert llm_msg["content"] == "Test content"

    def test_message_with_tool_calls(self):
        """Should handle tool calls in message"""
        tool_calls = [
            {"id": "tc1", "function": {"name": "search", "arguments": "{}"}}
        ]
        msg = AgentMessage(
            sender_id="agent1",
            sender_name="Agent",
            content="Let me search...",
            tool_calls=tool_calls
        )

        llm_msg = msg.to_llm_message()
        assert "tool_calls" in llm_msg


# ============== Collaboration State Tests ==============

class TestCollaborationState:
    """Test collaboration state management"""

    def test_state_initialization(self):
        """Should initialize with empty state"""
        state = CollaborationState()

        assert state.id is not None
        assert len(state.messages) == 0
        assert state.active_agent_id is None
        assert len(state.handoff_history) == 0
        assert len(state.shared_memory) == 0

    def test_state_message_tracking(self):
        """Should track messages"""
        state = CollaborationState()

        state.messages.append(AgentMessage(
            role="user",
            content="Hello"
        ))
        state.messages.append(AgentMessage(
            sender_id="agent1",
            content="Hi there"
        ))

        assert len(state.messages) == 2

    def test_state_handoff_history(self):
        """Should track handoff history"""
        state = CollaborationState()

        state.handoff_history.append({
            "from_agent": "supervisor",
            "to_agent": "specialist",
            "timestamp": datetime.utcnow().isoformat(),
            "reason": "specialization"
        })

        assert len(state.handoff_history) == 1
        assert state.handoff_history[0]["from_agent"] == "supervisor"


# ============== Supervisor Pattern Tests ==============

class TestSupervisorPattern:
    """Test supervisor/orchestrator pattern"""

    def test_supervisor_initialization(
        self,
        test_supervisor_agent,
        test_specialist_agents,
        mock_llm_client
    ):
        """Should initialize supervisor with specialists"""
        pattern = SupervisorPattern(
            supervisor=test_supervisor_agent,
            specialists=test_specialist_agents,
            llm_client=mock_llm_client,
        )

        assert pattern.supervisor is test_supervisor_agent
        assert len(pattern.specialists) == 2
        # Supervisor should have handoff tools for each specialist
        assert len(pattern.supervisor.tools) >= 2

    @pytest.mark.asyncio
    async def test_supervisor_simple_task(
        self,
        test_supervisor_agent,
        test_specialist_agents,
        mock_llm_client
    ):
        """Supervisor should complete simple task without handoff"""
        # Setup mock to respond with completion
        mock_llm_client.add_response("Task complete. The answer is 42.")

        pattern = SupervisorPattern(
            supervisor=test_supervisor_agent,
            specialists=test_specialist_agents,
            llm_client=mock_llm_client,
        )

        result = await pattern.execute(
            task="What is the answer to life?",
            user_id="test_user",
            max_turns=3
        )

        assert result["status"] == "completed"
        assert len(result["messages"]) >= 1
        assert "42" in result["final_output"]

    @pytest.mark.asyncio
    async def test_supervisor_handoff_to_specialist(
        self,
        test_supervisor_agent,
        test_specialist_agents,
        mock_llm_client
    ):
        """Supervisor should hand off to specialist"""
        # First response: supervisor delegates
        mock_llm_client.add_response(
            "I'll delegate this to Specialist A",
            tool_calls=[{
                "id": "tc_1",
                "function": {
                    "name": "handoff_to_specialist_a",
                    "arguments": '{"task": "Handle this specific task"}'
                }
            }]
        )
        # Second response: specialist completes
        mock_llm_client.add_response("Task complete. Specialist A handled it.")

        pattern = SupervisorPattern(
            supervisor=test_supervisor_agent,
            specialists=test_specialist_agents,
            llm_client=mock_llm_client,
        )

        result = await pattern.execute(
            task="Do something specialized",
            user_id="test_user",
            max_turns=5
        )

        # Should have handoff in history
        assert len(result["handoff_history"]) >= 1

    @pytest.mark.asyncio
    async def test_supervisor_agent_turn_callback(
        self,
        test_supervisor_agent,
        test_specialist_agents,
        mock_llm_client
    ):
        """Should call callback on each turn"""
        mock_llm_client.add_response("Task complete.")

        pattern = SupervisorPattern(
            supervisor=test_supervisor_agent,
            specialists=test_specialist_agents,
            llm_client=mock_llm_client,
        )

        turns = []

        def on_turn(agent, turn):
            turns.append({"agent": agent.name, "turn": turn})

        await pattern.execute(
            task="Simple task",
            max_turns=2,
            on_agent_turn=on_turn
        )

        assert len(turns) >= 1
        assert turns[0]["turn"] == 1

    @pytest.mark.asyncio
    async def test_supervisor_max_turns_limit(
        self,
        test_supervisor_agent,
        test_specialist_agents,
        mock_llm_client
    ):
        """Should respect max_turns limit"""
        # Keep responding without completion
        for _ in range(10):
            mock_llm_client.add_response("Still working on it...")

        pattern = SupervisorPattern(
            supervisor=test_supervisor_agent,
            specialists=test_specialist_agents,
            llm_client=mock_llm_client,
        )

        result = await pattern.execute(
            task="Endless task",
            max_turns=3
        )

        # Should complete after max_turns even without "done"
        assert result["status"] == "completed"
        # LLM should have been called at most max_turns times
        assert len(mock_llm_client.call_history) <= 3


# ============== Swarm Pattern Tests ==============

class TestSwarmPattern:
    """Test swarm pattern with direct handoffs"""

    def test_swarm_initialization(self, test_specialist_agents, mock_llm_client):
        """Should initialize swarm with agents"""
        # Add a router agent
        from app.engine.collaboration import CollaborationAgent, AgentRole
        router = CollaborationAgent(
            id="router",
            name="Router",
            role=AgentRole.ROUTER,
            description="Routes requests",
            system_prompt="Route tasks",
        )

        agents = [router] + test_specialist_agents

        swarm = SwarmPattern(
            agents=agents,
            default_agent_id="router",
            llm_client=mock_llm_client,
        )

        assert len(swarm.agents) == 3
        assert swarm.default_agent_id == "router"
        # Each agent should have handoff tools for others
        assert len(swarm.agents["router"].tools) >= 2

    @pytest.mark.asyncio
    async def test_swarm_simple_completion(
        self,
        test_specialist_agents,
        mock_llm_client
    ):
        """Swarm should complete simple task"""
        mock_llm_client.add_response("Done! Here's the result.")

        swarm = SwarmPattern(
            agents=test_specialist_agents,
            default_agent_id="specialist_a",
            llm_client=mock_llm_client,
        )

        result = await swarm.execute(
            task="Simple task",
            max_turns=3
        )

        assert result["status"] == "completed"
        assert "result" in result["final_output"].lower()

    @pytest.mark.asyncio
    async def test_swarm_handoff_chain(
        self,
        test_specialist_agents,
        mock_llm_client
    ):
        """Swarm should handle agent-to-agent handoffs"""
        # First agent hands off
        mock_llm_client.add_response(
            "Passing to B",
            tool_calls=[{
                "id": "tc_1",
                "function": {
                    "name": "handoff_to_specialist_b",
                    "arguments": '{"task": "Continue work"}'
                }
            }]
        )
        # Second agent completes
        mock_llm_client.add_response("All done!")

        swarm = SwarmPattern(
            agents=test_specialist_agents,
            default_agent_id="specialist_a",
            llm_client=mock_llm_client,
        )

        result = await swarm.execute(
            task="Multi-agent task",
            max_turns=5
        )

        # Should have handoff recorded
        assert len(result["handoff_history"]) >= 1


# ============== Shared Memory Manager Tests ==============

class TestSharedMemoryManager:
    """Test shared memory across agents"""

    def test_global_memory(self):
        """Should manage global memory"""
        manager = SharedMemoryManager()

        manager.set_global("user_name", "Alice")
        manager.set_global("task_id", "123")

        assert manager.get_global("user_name") == "Alice"
        assert manager.get_global("task_id") == "123"
        assert manager.get_global("nonexistent") is None

    def test_local_memory(self):
        """Should manage agent-local memory"""
        manager = SharedMemoryManager()

        manager.set_local("agent1", "state", "working")
        manager.set_local("agent2", "state", "idle")

        assert manager.get_local("agent1", "state") == "working"
        assert manager.get_local("agent2", "state") == "idle"
        assert manager.get_local("agent1", "other") is None

    def test_context_for_agent(self):
        """Should provide combined context for agent"""
        manager = SharedMemoryManager()

        manager.set_global("shared_key", "shared_value")
        manager.set_local("agent1", "private_key", "private_value")

        context = manager.get_context_for_agent("agent1")

        assert "global" in context
        assert "local" in context
        assert "shared_key" in context["global"]
        assert "private_key" in context["local"]

    def test_scoped_memory(self):
        """Should handle scoped memory"""
        manager = SharedMemoryManager()

        # Set scoped memory
        manager.scoped_memory["scope1"] = {"key1": "value1"}
        manager.scoped_memory["scope2"] = {"key2": "value2"}

        context = manager.get_context_for_agent("agent1", scope_ids=["scope1"])

        assert "scoped" in context
        assert "scope1" in context["scoped"]
        assert context["scoped"]["scope1"]["key1"] == "value1"


# ============== Agent Team Factory Tests ==============

class TestAgentTeamFactory:
    """Test pre-built team configurations"""

    def test_create_research_team(self, mock_llm_client):
        """Should create research team"""
        factory = AgentTeamFactory(mock_llm_client)
        team = factory.create_research_team()

        assert isinstance(team, SupervisorPattern)
        assert team.supervisor.name == "Research Coordinator"
        assert len(team.specialists) >= 3

        # Check specialists
        specialist_names = [s.name for s in team.specialists.values()]
        assert "Web Researcher" in specialist_names
        assert "Data Analyst" in specialist_names
        assert "Report Writer" in specialist_names

    def test_create_code_review_team(self, mock_llm_client):
        """Should create code review team"""
        factory = AgentTeamFactory(mock_llm_client)
        team = factory.create_code_review_team()

        assert isinstance(team, SupervisorPattern)
        assert "Code Review" in team.supervisor.name

        specialist_names = [s.name for s in team.specialists.values()]
        assert "Security Reviewer" in specialist_names
        assert "Performance Reviewer" in specialist_names
        assert "Style Reviewer" in specialist_names

    def test_create_customer_support_swarm(self, mock_llm_client):
        """Should create customer support swarm"""
        factory = AgentTeamFactory(mock_llm_client)
        swarm = factory.create_customer_support_swarm()

        assert isinstance(swarm, SwarmPattern)
        assert swarm.default_agent_id == "triage_agent"
        assert len(swarm.agents) >= 4

        agent_names = [a.name for a in swarm.agents.values()]
        assert "Triage Agent" in agent_names
        assert "Billing Agent" in agent_names
        assert "Technical Agent" in agent_names


# ============== Integration Tests ==============

class TestCollaborationIntegration:
    """Integration tests for collaboration patterns"""

    @pytest.mark.asyncio
    async def test_research_workflow(self, mock_llm_client):
        """Test complete research workflow"""
        # Setup responses
        # 1. Supervisor delegates to web researcher
        mock_llm_client.add_response(
            "I'll have the web researcher find information",
            tool_calls=[{
                "id": "tc_1",
                "function": {
                    "name": "handoff_to_web_researcher",
                    "arguments": '{"task": "Research AI trends"}'
                }
            }]
        )
        # 2. Web researcher finds info
        mock_llm_client.add_response("Found key findings about AI trends")
        # 3. Supervisor delegates to report writer
        mock_llm_client.add_response(
            "Now let's write the report",
            tool_calls=[{
                "id": "tc_2",
                "function": {
                    "name": "handoff_to_report_writer",
                    "arguments": '{"task": "Write summary"}'
                }
            }]
        )
        # 4. Report writer completes
        mock_llm_client.add_response("Task complete. Report is ready.")

        factory = AgentTeamFactory(mock_llm_client)
        team = factory.create_research_team()

        result = await team.execute(
            task="Research and summarize AI trends",
            max_turns=10
        )

        assert result["status"] == "completed"
        # Should have handoffs to different specialists
        handoff_targets = [h.get("to_agent") for h in result["handoff_history"]]
        assert len(handoff_targets) >= 1

    @pytest.mark.asyncio
    async def test_support_escalation(self, mock_llm_client):
        """Test customer support escalation flow"""
        # 1. Triage identifies technical issue
        mock_llm_client.add_response(
            "This is a technical issue, routing to technical support",
            tool_calls=[{
                "id": "tc_1",
                "function": {
                    "name": "handoff_to_technical_agent",
                    "arguments": '{"task": "Debug API error"}'
                }
            }]
        )
        # 2. Technical agent resolves
        mock_llm_client.add_response(
            "I've identified the issue. You need to update your API key. Done!"
        )

        factory = AgentTeamFactory(mock_llm_client)
        swarm = factory.create_customer_support_swarm()

        result = await swarm.execute(
            task="My API calls are failing with 401 errors",
            max_turns=5
        )

        assert result["status"] == "completed"
        # Should have routed to technical
        handoffs = result["handoff_history"]
        assert len(handoffs) >= 1
