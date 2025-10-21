"""LangGraph workflow orchestration"""

from typing import Dict, Any, Literal
import logging
from langgraph.graph import StateGraph, END
from app.graph.state import AgentState
from app.agents import ResearchAgent, CodeAgent, AnalysisAgent

logger = logging.getLogger(__name__)

class WorkflowManager:
    """Manages multi-agent workflows using LangGraph"""

    def __init__(self, memory_manager):
        self.memory_manager = memory_manager
        self.workflows = {}

        # Initialize agents
        self.agents = {
            "research": ResearchAgent(memory_manager),
            "code": CodeAgent(memory_manager),
            "analysis": AnalysisAgent(memory_manager)
        }

        # Build graph
        self.graph = self._build_graph()
        logger.info("WorkflowManager initialized with LangGraph")

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph multi-agent workflow"""

        # Create graph
        workflow = StateGraph(AgentState)

        # Add nodes
        workflow.add_node("router", self._route_agent)
        workflow.add_node("research", self._execute_research)
        workflow.add_node("code", self._execute_code)
        workflow.add_node("analysis", self._execute_analysis)
        workflow.add_node("finalizer", self._finalize)

        # Set entry point
        workflow.set_entry_point("router")

        # Add conditional edges from router
        workflow.add_conditional_edges(
            "router",
            self._determine_next_agent,
            {
                "research": "research",
                "code": "code",
                "analysis": "analysis",
                "end": "finalizer"
            }
        )

        # Add edges from agents back to router (for multi-agent collaboration)
        workflow.add_edge("research", "router")
        workflow.add_edge("code", "router")
        workflow.add_edge("analysis", "router")

        # Finalizer ends workflow
        workflow.add_edge("finalizer", END)

        return workflow.compile()

    def _route_agent(self, state: AgentState) -> AgentState:
        """Route to appropriate agent"""
        logger.info(f"Routing task {state['task_id']} to {state['agent_type']}")
        state["current_agent"] = state["agent_type"]
        state["status"] = "routing"
        return state

    async def _execute_research(self, state: AgentState) -> AgentState:
        """Execute research agent"""
        logger.info(f"Executing research agent for task {state['task_id']}")
        agent = self.agents["research"]

        result = await agent.execute({
            "task_id": state["task_id"],
            "task": state["task"],
            "context": state["context"],
            "user_id": state["user_id"]
        })

        # Update state with results
        state["results"].append(result)
        state["input_tokens"] += result.get("tokens", {}).get("input", 0)
        state["output_tokens"] += result.get("tokens", {}).get("output", 0)
        state["next"] = result.get("next_agent", "end")

        # Add result message
        state["messages"].append({
            "role": "assistant",
            "content": f"Research completed: {result.get('result', {}).get('summary', '')[:200]}..."
        })

        return state

    async def _execute_code(self, state: AgentState) -> AgentState:
        """Execute code agent"""
        logger.info(f"Executing code agent for task {state['task_id']}")
        agent = self.agents["code"]

        result = await agent.execute({
            "task_id": state["task_id"],
            "task": state["task"],
            "context": state["context"],
            "user_id": state["user_id"]
        })

        # Update state with results
        state["results"].append(result)
        state["input_tokens"] += result.get("tokens", {}).get("input", 0)
        state["output_tokens"] += result.get("tokens", {}).get("output", 0)
        state["next"] = result.get("next_agent", "end")

        # Add result message
        state["messages"].append({
            "role": "assistant",
            "content": f"Code generated: {result.get('result', {}).get('language', 'code')} solution"
        })

        return state

    async def _execute_analysis(self, state: AgentState) -> AgentState:
        """Execute analysis agent"""
        logger.info(f"Executing analysis agent for task {state['task_id']}")
        agent = self.agents["analysis"]

        result = await agent.execute({
            "task_id": state["task_id"],
            "task": state["task"],
            "context": state["context"],
            "user_id": state["user_id"]
        })

        # Update state with results
        state["results"].append(result)
        state["input_tokens"] += result.get("tokens", {}).get("input", 0)
        state["output_tokens"] += result.get("tokens", {}).get("output", 0)
        state["next"] = result.get("next_agent", "end")

        # Add result message
        state["messages"].append({
            "role": "assistant",
            "content": f"Analysis completed with {len(result.get('result', {}).get('insights', []))} insights"
        })

        return state

    def _determine_next_agent(self, state: AgentState) -> Literal["research", "code", "analysis", "end"]:
        """Determine next agent to execute"""
        next_agent = state.get("next", "end")

        # First execution - route to requested agent
        if state.get("current_agent") == "":
            if state["agent_type"] in ["research", "code", "analysis"]:
                return state["agent_type"]
            return "end"

        # Multi-agent collaboration - check if we should continue
        if next_agent in ["research", "code", "analysis"]:
            # Prevent infinite loops - max 3 agents in chain
            if len(state.get("results", [])) < 3:
                return next_agent

        return "end"

    def _finalize(self, state: AgentState) -> AgentState:
        """Finalize workflow"""
        state["status"] = "completed"
        logger.info(f"Workflow {state['task_id']} completed with {len(state['results'])} agents")

        # Calculate total tokens
        total_tokens = state["input_tokens"] + state["output_tokens"]

        # Add final summary message
        state["messages"].append({
            "role": "system",
            "content": f"Workflow completed. Used {len(state['results'])} agents, {total_tokens} tokens."
        })

        return state

    async def execute_workflow(self, initial_state: AgentState) -> AgentState:
        """Execute complete workflow"""
        try:
            logger.info(f"Starting workflow {initial_state['task_id']}")

            # Run the graph
            final_state = await self.graph.ainvoke(initial_state)

            # Store in memory
            if self.memory_manager:
                await self.memory_manager.store(
                    user_id=final_state["user_id"],
                    agent_id=final_state["agent_type"],
                    messages=final_state["messages"],
                    metadata={
                        "task_id": final_state["task_id"],
                        "tokens": {
                            "input": final_state["input_tokens"],
                            "output": final_state["output_tokens"],
                            "total": final_state["input_tokens"] + final_state["output_tokens"]
                        },
                        "agents_used": len(final_state["results"])
                    }
                )

            return final_state

        except Exception as e:
            logger.error(f"Workflow execution failed: {e}")
            raise

    def get_workflow_stats(self) -> Dict[str, Any]:
        """Get workflow statistics"""
        return {
            "available_agents": list(self.agents.keys()),
            "agents_status": {name: agent.get_status() for name, agent in self.agents.items()},
            "memory_enabled": self.memory_manager is not None
        }
