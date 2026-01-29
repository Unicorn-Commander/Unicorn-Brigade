"""
Multi-Agent Collaboration Framework

Implements state-of-the-art patterns for agent collaboration:
- Supervisor Pattern: Orchestrator coordinates specialists
- Swarm Pattern: Direct agent-to-agent handoffs
- Shared Context: Structured memory across agents
- Handoff Protocol: JSON Schema-based context transfer

Based on research from CrewAI, AutoGen, LangGraph, and OpenAI Agents SDK.
"""

import asyncio
import json
import logging
import uuid
from typing import Dict, Any, List, Optional, Callable, Union
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field

from app.llm.ops_center_client import OpsCenterLLMClient, ToolDefinition, ToolParameter

logger = logging.getLogger(__name__)


# ============== Collaboration Models ==============

class AgentRole(str, Enum):
    """Standard agent roles"""
    SUPERVISOR = "supervisor"
    SPECIALIST = "specialist"
    WORKER = "worker"
    ROUTER = "router"
    REVIEWER = "reviewer"


class HandoffReason(str, Enum):
    """Reasons for agent handoffs"""
    SPECIALIZATION = "specialization"
    ESCALATION = "escalation"
    COMPLETION = "completion"
    DELEGATION = "delegation"
    REVIEW = "review"


@dataclass
class AgentCapability:
    """Capability definition for an agent"""
    name: str
    description: str
    domains: List[str] = field(default_factory=list)
    tools: List[str] = field(default_factory=list)


@dataclass
class CollaborationAgent:
    """Agent definition for collaboration"""
    id: str
    name: str
    role: AgentRole
    description: str
    system_prompt: str
    capabilities: List[AgentCapability] = field(default_factory=list)
    can_handoff_to: List[str] = field(default_factory=list)  # Agent IDs
    tools: List[ToolDefinition] = field(default_factory=list)
    model: str = "default"
    temperature: float = 0.7
    max_tokens: int = 2000

    def to_tool(self) -> ToolDefinition:
        """Create a handoff tool for this agent"""
        return ToolDefinition(
            name=f"handoff_to_{self.name.lower().replace(' ', '_')}",
            description=f"Hand off the task to {self.name}. {self.description}",
            parameters=[
                ToolParameter(
                    name="task",
                    type="string",
                    description="The task to hand off",
                    required=True,
                ),
                ToolParameter(
                    name="context",
                    type="object",
                    description="Context to pass to the agent",
                    required=False,
                ),
                ToolParameter(
                    name="reason",
                    type="string",
                    description="Reason for the handoff",
                    required=False,
                ),
            ],
        )


class HandoffContext(BaseModel):
    """Structured context for agent handoffs (prevents context loss)"""
    task: str
    intent: str
    entities: Dict[str, Any] = Field(default_factory=dict)
    conversation_summary: str = ""
    relevant_facts: List[str] = Field(default_factory=list)
    pending_actions: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_free_text(cls, text: str, llm_client: OpsCenterLLMClient = None) -> "HandoffContext":
        """Create structured context from free text (use LLM if available)"""
        # Basic extraction without LLM
        return cls(
            task=text,
            intent="unknown",
            conversation_summary=text[:500],
        )


@dataclass
class AgentMessage:
    """Message in the collaboration"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    sender_id: str = ""
    sender_name: str = ""
    role: str = "assistant"  # "user", "assistant", "system", "tool"
    content: str = ""
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    tool_results: List[Dict[str, Any]] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_llm_message(self) -> Dict[str, Any]:
        """Convert to LLM message format"""
        msg = {
            "role": self.role,
            "content": self.content,
        }
        if self.tool_calls:
            msg["tool_calls"] = self.tool_calls
        return msg


@dataclass
class CollaborationState:
    """Shared state for a collaboration session"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    messages: List[AgentMessage] = field(default_factory=list)
    active_agent_id: Optional[str] = None
    handoff_history: List[Dict[str, Any]] = field(default_factory=list)
    shared_memory: Dict[str, Any] = field(default_factory=dict)
    agent_local_memory: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    artifacts: List[Dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


# ============== Collaboration Patterns ==============

class SupervisorPattern:
    """
    Supervisor/Orchestrator pattern.

    One supervisor agent coordinates multiple specialist agents.
    The supervisor:
    - Receives the initial task
    - Decides which specialist to delegate to
    - Aggregates results
    - Handles escalations
    """

    def __init__(
        self,
        supervisor: CollaborationAgent,
        specialists: List[CollaborationAgent],
        llm_client: Optional[OpsCenterLLMClient] = None,
    ):
        self.supervisor = supervisor
        self.specialists = {agent.id: agent for agent in specialists}
        self.llm_client = llm_client or OpsCenterLLMClient()
        self.state = CollaborationState()

        # Add handoff tools for each specialist
        for specialist in specialists:
            self.supervisor.tools.append(specialist.to_tool())

        logger.info(f"SupervisorPattern initialized with {len(specialists)} specialists")

    async def execute(
        self,
        task: str,
        user_id: str = "anonymous",
        max_turns: int = 10,
        on_agent_turn: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """Execute a task with supervisor coordination"""
        self.state.active_agent_id = self.supervisor.id
        self.state.messages.append(AgentMessage(
            role="user",
            content=task,
        ))

        turn = 0
        while turn < max_turns:
            turn += 1
            active_agent = self._get_active_agent()

            if on_agent_turn:
                on_agent_turn(active_agent, turn)

            logger.info(f"Turn {turn}: {active_agent.name} is active")

            # Get agent response
            response = await self._agent_turn(active_agent, user_id)

            # Check for handoff
            handoff = self._check_for_handoff(response)
            if handoff:
                target_agent_id = handoff.get("target_agent_id")
                if target_agent_id and target_agent_id in self.specialists:
                    self._perform_handoff(active_agent, self.specialists[target_agent_id], handoff)
                    continue

            # Check for completion
            if self._is_complete(response):
                break

        return self._build_result()

    def _get_active_agent(self) -> CollaborationAgent:
        """Get the currently active agent"""
        if self.state.active_agent_id == self.supervisor.id:
            return self.supervisor
        return self.specialists.get(self.state.active_agent_id, self.supervisor)

    async def _agent_turn(self, agent: CollaborationAgent, user_id: str) -> Dict[str, Any]:
        """Execute one agent turn"""
        messages = [{"role": "system", "content": agent.system_prompt}]
        messages.extend([m.to_llm_message() for m in self.state.messages])

        if agent.tools:
            response = await self.llm_client.chat_completion_with_tools(
                messages=messages,
                tools=agent.tools,
                model=agent.model,
                temperature=agent.temperature,
                max_tokens=agent.max_tokens,
                user_id=user_id,
            )
        else:
            response = await self.llm_client.chat_completion(
                messages=messages,
                model=agent.model,
                temperature=agent.temperature,
                max_tokens=agent.max_tokens,
                user_id=user_id,
            )

        # Add response to state
        content = self.llm_client.get_response_content(response)
        tool_calls = response.get("choices", [{}])[0].get("message", {}).get("tool_calls", [])

        self.state.messages.append(AgentMessage(
            sender_id=agent.id,
            sender_name=agent.name,
            role="assistant",
            content=content,
            tool_calls=tool_calls,
        ))

        self.state.updated_at = datetime.utcnow()
        return response

    def _check_for_handoff(self, response: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Check if response contains a handoff request"""
        tool_calls = self.llm_client.parse_tool_calls(response)
        for tc in tool_calls:
            if tc.name.startswith("handoff_to_"):
                agent_name = tc.name.replace("handoff_to_", "").replace("_", " ")
                for agent in self.specialists.values():
                    if agent.name.lower() == agent_name:
                        return {
                            "target_agent_id": agent.id,
                            "task": tc.arguments.get("task", ""),
                            "context": tc.arguments.get("context", {}),
                            "reason": tc.arguments.get("reason", ""),
                        }
        return None

    def _perform_handoff(
        self,
        from_agent: CollaborationAgent,
        to_agent: CollaborationAgent,
        handoff: Dict[str, Any],
    ):
        """Perform handoff between agents"""
        self.state.handoff_history.append({
            "from_agent": from_agent.id,
            "to_agent": to_agent.id,
            "timestamp": datetime.utcnow().isoformat(),
            **handoff,
        })
        self.state.active_agent_id = to_agent.id
        logger.info(f"Handoff: {from_agent.name} -> {to_agent.name}")

    def _is_complete(self, response: Dict[str, Any]) -> bool:
        """Check if the collaboration is complete"""
        content = self.llm_client.get_response_content(response).lower()
        completion_indicators = [
            "task complete",
            "task is complete",
            "completed the task",
            "finished",
            "done",
        ]
        return any(indicator in content for indicator in completion_indicators)

    def _build_result(self) -> Dict[str, Any]:
        """Build the final result"""
        return {
            "status": "completed",
            "messages": [m.to_llm_message() for m in self.state.messages],
            "handoff_history": self.state.handoff_history,
            "final_output": self.state.messages[-1].content if self.state.messages else "",
            "artifacts": self.state.artifacts,
            "shared_memory": self.state.shared_memory,
        }


class SwarmPattern:
    """
    Swarm pattern for direct agent-to-agent handoffs.

    Agents communicate directly without a central supervisor.
    Each agent can hand off to any other agent in the swarm.
    """

    def __init__(
        self,
        agents: List[CollaborationAgent],
        default_agent_id: str,
        llm_client: Optional[OpsCenterLLMClient] = None,
    ):
        self.agents = {agent.id: agent for agent in agents}
        self.default_agent_id = default_agent_id
        self.llm_client = llm_client or OpsCenterLLMClient()
        self.state = CollaborationState()

        # Add handoff tools to each agent
        for agent in agents:
            for other_agent in agents:
                if other_agent.id != agent.id:
                    if not agent.can_handoff_to or other_agent.id in agent.can_handoff_to:
                        agent.tools.append(other_agent.to_tool())

        logger.info(f"SwarmPattern initialized with {len(agents)} agents")

    async def execute(
        self,
        task: str,
        user_id: str = "anonymous",
        max_turns: int = 15,
        on_agent_turn: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """Execute task with swarm coordination"""
        self.state.active_agent_id = self.default_agent_id
        self.state.messages.append(AgentMessage(role="user", content=task))

        turn = 0
        while turn < max_turns:
            turn += 1
            active_agent = self.agents.get(self.state.active_agent_id)
            if not active_agent:
                break

            if on_agent_turn:
                on_agent_turn(active_agent, turn)

            logger.info(f"Swarm turn {turn}: {active_agent.name}")

            # Get response
            response = await self._agent_turn(active_agent, user_id)

            # Check for handoff
            handoff = self._check_for_handoff(response)
            if handoff and handoff["target_agent_id"] in self.agents:
                self.state.handoff_history.append({
                    "from": active_agent.id,
                    "to": handoff["target_agent_id"],
                    "turn": turn,
                })
                self.state.active_agent_id = handoff["target_agent_id"]
                continue

            # Check for completion
            if not self.llm_client.has_tool_calls(response):
                break

        return self._build_result()

    async def _agent_turn(self, agent: CollaborationAgent, user_id: str) -> Dict[str, Any]:
        """Single agent turn"""
        messages = [{"role": "system", "content": agent.system_prompt}]
        messages.extend([m.to_llm_message() for m in self.state.messages])

        response = await self.llm_client.chat_completion_with_tools(
            messages=messages,
            tools=agent.tools,
            model=agent.model,
            temperature=agent.temperature,
            max_tokens=agent.max_tokens,
            user_id=user_id,
        )

        content = self.llm_client.get_response_content(response)
        self.state.messages.append(AgentMessage(
            sender_id=agent.id,
            sender_name=agent.name,
            content=content,
        ))

        return response

    def _check_for_handoff(self, response: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Check for handoff in response"""
        tool_calls = self.llm_client.parse_tool_calls(response)
        for tc in tool_calls:
            if tc.name.startswith("handoff_to_"):
                agent_name = tc.name.replace("handoff_to_", "").replace("_", " ")
                for agent in self.agents.values():
                    if agent.name.lower() == agent_name:
                        return {"target_agent_id": agent.id}
        return None

    def _build_result(self) -> Dict[str, Any]:
        """Build result"""
        return {
            "status": "completed",
            "messages": [m.to_llm_message() for m in self.state.messages],
            "handoff_history": self.state.handoff_history,
            "final_output": self.state.messages[-1].content if self.state.messages else "",
        }


# ============== Agent Factory ==============

class AgentTeamFactory:
    """
    Factory for creating pre-configured agent teams.

    Provides templates for common collaboration patterns.
    """

    def __init__(self, llm_client: Optional[OpsCenterLLMClient] = None):
        self.llm_client = llm_client or OpsCenterLLMClient()

    def create_research_team(self) -> SupervisorPattern:
        """Create a research team with supervisor + specialists"""
        supervisor = CollaborationAgent(
            id="research_supervisor",
            name="Research Coordinator",
            role=AgentRole.SUPERVISOR,
            description="Coordinates research tasks across specialists",
            system_prompt="""You are a research coordinator. Your job is to:
1. Understand the research request
2. Break it down into sub-tasks
3. Delegate to appropriate specialists
4. Synthesize their findings
5. Deliver a comprehensive response

Available specialists:
- Web Researcher: For finding current information online
- Data Analyst: For analyzing data and statistics
- Report Writer: For writing summaries and reports

Delegate tasks using the handoff tools. When all research is complete, provide the final answer.""",
            model="claude-3-5-sonnet",
        )

        web_researcher = CollaborationAgent(
            id="web_researcher",
            name="Web Researcher",
            role=AgentRole.SPECIALIST,
            description="Searches and analyzes web content",
            system_prompt="You are an expert web researcher. Search for information, verify sources, and return factual findings.",
        )

        data_analyst = CollaborationAgent(
            id="data_analyst",
            name="Data Analyst",
            role=AgentRole.SPECIALIST,
            description="Analyzes data and provides insights",
            system_prompt="You are a data analyst. Analyze provided data, identify patterns, and provide statistical insights.",
        )

        report_writer = CollaborationAgent(
            id="report_writer",
            name="Report Writer",
            role=AgentRole.SPECIALIST,
            description="Writes clear reports and summaries",
            system_prompt="You are a report writer. Create clear, well-structured reports from provided information.",
        )

        return SupervisorPattern(
            supervisor=supervisor,
            specialists=[web_researcher, data_analyst, report_writer],
            llm_client=self.llm_client,
        )

    def create_code_review_team(self) -> SupervisorPattern:
        """Create a code review team"""
        supervisor = CollaborationAgent(
            id="code_review_lead",
            name="Code Review Lead",
            role=AgentRole.SUPERVISOR,
            description="Leads code review process",
            system_prompt="""You are a senior code review lead. Coordinate the review process:
1. Security Reviewer checks for vulnerabilities
2. Performance Reviewer checks for efficiency
3. Style Reviewer checks for code quality

Delegate appropriately and synthesize findings.""",
            model="claude-3-5-sonnet",
        )

        security = CollaborationAgent(
            id="security_reviewer",
            name="Security Reviewer",
            role=AgentRole.SPECIALIST,
            description="Reviews code for security vulnerabilities",
            system_prompt="You are a security expert. Review code for vulnerabilities: injection, XSS, auth issues, etc.",
        )

        performance = CollaborationAgent(
            id="performance_reviewer",
            name="Performance Reviewer",
            role=AgentRole.SPECIALIST,
            description="Reviews code for performance issues",
            system_prompt="You are a performance expert. Review code for efficiency: O(n) complexity, memory leaks, etc.",
        )

        style = CollaborationAgent(
            id="style_reviewer",
            name="Style Reviewer",
            role=AgentRole.SPECIALIST,
            description="Reviews code style and maintainability",
            system_prompt="You are a code quality expert. Review for readability, patterns, naming, documentation.",
        )

        return SupervisorPattern(
            supervisor=supervisor,
            specialists=[security, performance, style],
            llm_client=self.llm_client,
        )

    def create_customer_support_swarm(self) -> SwarmPattern:
        """Create a customer support swarm with direct handoffs"""
        triage = CollaborationAgent(
            id="triage_agent",
            name="Triage Agent",
            role=AgentRole.ROUTER,
            description="Routes customer requests",
            system_prompt="""You are a customer support triage agent.
Understand the customer's issue and route to:
- Billing Agent: For payment, subscription, invoice issues
- Technical Agent: For product bugs, technical problems
- Sales Agent: For upgrades, new features, pricing

Be friendly and efficient. Hand off with full context.""",
        )

        billing = CollaborationAgent(
            id="billing_agent",
            name="Billing Agent",
            role=AgentRole.SPECIALIST,
            description="Handles billing inquiries",
            system_prompt="You are a billing specialist. Handle payment, subscription, and invoice questions. Be precise about amounts and dates.",
        )

        technical = CollaborationAgent(
            id="technical_agent",
            name="Technical Agent",
            role=AgentRole.SPECIALIST,
            description="Handles technical issues",
            system_prompt="You are technical support. Diagnose and resolve product issues. Provide clear steps.",
        )

        sales = CollaborationAgent(
            id="sales_agent",
            name="Sales Agent",
            role=AgentRole.SPECIALIST,
            description="Handles sales inquiries",
            system_prompt="You are a sales specialist. Help with upgrades, feature questions, and pricing. Be helpful, not pushy.",
        )

        return SwarmPattern(
            agents=[triage, billing, technical, sales],
            default_agent_id="triage_agent",
            llm_client=self.llm_client,
        )


# ============== Shared Memory Manager ==============

class SharedMemoryManager:
    """
    Manages shared memory across agents in a collaboration.

    Implements tiered memory:
    - Global: Visible to all agents
    - Scoped: Visible to specific agents
    - Local: Private to each agent
    """

    def __init__(self):
        self.global_memory: Dict[str, Any] = {}
        self.scoped_memory: Dict[str, Dict[str, Any]] = {}  # scope_id -> memory
        self.local_memory: Dict[str, Dict[str, Any]] = {}  # agent_id -> memory

    def set_global(self, key: str, value: Any):
        """Set a global memory value"""
        self.global_memory[key] = {
            "value": value,
            "updated_at": datetime.utcnow().isoformat(),
        }

    def get_global(self, key: str) -> Any:
        """Get a global memory value"""
        entry = self.global_memory.get(key)
        return entry["value"] if entry else None

    def set_local(self, agent_id: str, key: str, value: Any):
        """Set agent-local memory"""
        if agent_id not in self.local_memory:
            self.local_memory[agent_id] = {}
        self.local_memory[agent_id][key] = value

    def get_local(self, agent_id: str, key: str) -> Any:
        """Get agent-local memory"""
        return self.local_memory.get(agent_id, {}).get(key)

    def get_context_for_agent(self, agent_id: str, scope_ids: List[str] = None) -> Dict[str, Any]:
        """Get combined context for an agent"""
        context = {
            "global": self.global_memory,
            "local": self.local_memory.get(agent_id, {}),
        }

        if scope_ids:
            context["scoped"] = {
                sid: self.scoped_memory.get(sid, {})
                for sid in scope_ids
            }

        return context

    def compact_context(self, llm_client: OpsCenterLLMClient, max_tokens: int = 4000) -> str:
        """Compact context when it exceeds threshold (Google ADK pattern)"""
        # Simple implementation - in production, use LLM to summarize
        summary_parts = []

        if self.global_memory:
            summary_parts.append(f"Global facts: {list(self.global_memory.keys())}")

        return "; ".join(summary_parts)
