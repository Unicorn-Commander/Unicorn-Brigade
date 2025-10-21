"""Workflow state management for LangGraph"""

from typing import Dict, Any, List, Annotated
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages
import operator

class AgentState(TypedDict):
    """State model for LangGraph workflows"""

    # Messages with reducer
    messages: Annotated[List[Dict[str, Any]], add_messages]

    # Task information
    task_id: str
    agent_type: str
    task: str
    user_id: str

    # Execution state
    current_agent: str
    status: str

    # Results and context
    context: Dict[str, Any]
    results: Annotated[List[Dict[str, Any]], operator.add]

    # Tokens and billing
    input_tokens: int
    output_tokens: int
    tools_used: List[Dict[str, Any]]
    llm_route: str

    # Memory
    memory_keys: List[str]

    # Next agent
    next: str
