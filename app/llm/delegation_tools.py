"""
Inter-Agent Delegation Tool

Allows agents to consult other Brigade agents mid-conversation.
For example, Carter Knox can ask The General for a plan, or
Detective Holmes can ask Gunny for help building an agent.
"""

import os
import logging
from contextvars import ContextVar
from typing import Dict, Any, Optional

import httpx

# Context var: chat_with_agent sets this at the start of each chat call so
# delegate_to_agent_handler can forward the mission_id to the downstream
# chat call. Lets a Crisis Ops orchestrator's events + every nested
# specialist's events share one correlation id.
_CURRENT_MISSION_ID: ContextVar[Optional[str]] = ContextVar("_CURRENT_MISSION_ID", default=None)

from app.llm.ops_center_client import ToolDefinition, ToolParameter

logger = logging.getLogger(__name__)

# Inside the container, call ourselves via localhost.
# BRIGADE_ADMIN_KEY is the key set in the container environment.
BRIGADE_API_URL = os.getenv("BRIGADE_API_URL", "http://localhost:8100")
BRIGADE_API_KEY = os.getenv("BRIGADE_ADMIN_KEY", "") or os.getenv("BRIGADE_API_KEY", "")


async def delegate_to_agent_handler(
    agent_id: str,
    task: str,
    context: Optional[str] = None,
    caller_user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Delegate a task to another Brigade agent and return their response.

    ``caller_user_id`` is injected by the tool invocation layer (not by the
    LLM) when the ``DELEGATE_TO_AGENT_TOOL`` is registered with
    ``needs_caller_context=True``. Forwarding it in the downstream request
    body preserves memory isolation and RBAC through delegation chains: the
    delegated agent sees the real caller, not the service key identity.
    """
    logger.info(
        "Delegating to agent '%s' (caller=%s): %s",
        agent_id,
        caller_user_id or "(none)",
        task[:100],
    )

    message = task
    if context:
        message = f"Context: {context}\n\nTask: {task}"

    body: Dict[str, Any] = {"message": message}
    if caller_user_id:
        body["user_id"] = caller_user_id
    # Forward parent's mission_id so the downstream specialist's events
    # carry the same correlation id.
    parent_mission = _CURRENT_MISSION_ID.get()
    if parent_mission:
        body["mission_id"] = parent_mission

    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            headers = {
                "Content-Type": "application/json",
                "X-API-Key": BRIGADE_API_KEY,
            }
            if caller_user_id:
                # Explicit header in addition to body user_id so the chat
                # endpoint has an unambiguous "this call was delegated on
                # behalf of user X" signal for logging / auditing.
                headers["X-Delegate-User"] = caller_user_id
            resp = await client.post(
                f"{BRIGADE_API_URL}/api/v1/agents/{agent_id}/chat",
                headers=headers,
                json=body,
            )

            if resp.status_code == 200:
                data = resp.json()
                return {
                    "success": True,
                    "agent_id": agent_id,
                    "response": data.get("content", ""),
                }
            elif resp.status_code == 404:
                return {
                    "success": False,
                    "error": f"Agent '{agent_id}' not found",
                }
            else:
                return {
                    "success": False,
                    "error": f"Agent returned status {resp.status_code}: {resp.text[:200]}",
                }
    except Exception as e:
        logger.error("Delegation to '%s' failed: %s", agent_id, e)
        return {"success": False, "error": str(e)}


DELEGATE_TO_AGENT_TOOL = ToolDefinition(
    name="delegate_to_agent",
    description=(
        "Delegate a task to another Brigade agent and get their response. "
        "Use this when a question falls outside your expertise or another agent "
        "is better suited. Available agents include: "
        "sgt-carter-knox (home automation), "
        "the-general (orchestration & strategy), "
        "gunny (agent building), "
        "detective-holmes (OSINT & research), "
        "col-finance (finance & investment), "
        "cpt-fullstack (software engineering), "
        "maj-devops (infrastructure & DevOps), "
        "prof-datasci (data science & analytics), "
        "judge-advocate (legal analysis), "
        "doc-medresearch (medical research)."
    ),
    parameters=[
        ToolParameter(
            name="agent_id",
            type="string",
            description="The ID of the agent to delegate to (e.g., 'the-general', 'detective-holmes')",
            required=True,
        ),
        ToolParameter(
            name="task",
            type="string",
            description="The task or question to send to the other agent",
            required=True,
        ),
        ToolParameter(
            name="context",
            type="string",
            description="Optional context from the current conversation to pass along",
            required=False,
        ),
    ],
    handler=delegate_to_agent_handler,
    # The tool invocation layer injects the authenticated caller's user_id as
    # ``caller_user_id`` — NOT an LLM-visible parameter. The LLM only sees
    # agent_id, task, context in its function schema.
    needs_caller_context=True,
)
