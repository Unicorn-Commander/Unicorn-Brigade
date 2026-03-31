"""
Inter-Agent Delegation Tool

Allows agents to consult other Brigade agents mid-conversation.
For example, Carter Knox can ask The General for a plan, or
Detective Holmes can ask Gunny for help building an agent.

Supports remote edge agents: set REMOTE_AGENTS env var as a JSON
mapping of agent IDs to their edge node base URLs, e.g.:
  REMOTE_AGENTS={"sgt-carter-knox": "http://192.168.10.138:8200"}
"""

import json
import os
import logging
from typing import Dict, Any, Optional

import httpx

from app.llm.ops_center_client import ToolDefinition, ToolParameter

logger = logging.getLogger(__name__)

# Inside the container, call ourselves via localhost.
# BRIGADE_ADMIN_KEY is the key set in the container environment.
BRIGADE_API_URL = os.getenv("BRIGADE_API_URL", "http://localhost:8100")
BRIGADE_API_KEY = os.getenv("BRIGADE_ADMIN_KEY", "") or os.getenv("BRIGADE_API_KEY", "")

# Remote edge agent registry: agent_id -> base URL
# Loaded from REMOTE_AGENTS env var (JSON string).
# When an agent is listed here, delegation calls route to the remote
# edge node instead of the local Brigade API.
_raw_remote = os.getenv("REMOTE_AGENTS", "")
REMOTE_AGENTS: Dict[str, str] = {}
if _raw_remote:
    try:
        REMOTE_AGENTS = json.loads(_raw_remote)
        logger.info("Loaded %d remote agent(s): %s", len(REMOTE_AGENTS), list(REMOTE_AGENTS.keys()))
    except json.JSONDecodeError as exc:
        logger.error("Failed to parse REMOTE_AGENTS env var: %s", exc)


async def delegate_to_agent_handler(
    agent_id: str,
    task: str,
    context: Optional[str] = None,
) -> Dict[str, Any]:
    """Delegate a task to another Brigade agent and return their response.

    If the agent_id is listed in REMOTE_AGENTS, the request is routed to
    the corresponding edge node URL. Otherwise it falls back to the local
    Brigade API at BRIGADE_API_URL.
    """
    remote_url = REMOTE_AGENTS.get(agent_id)
    is_remote = remote_url is not None
    base_url = remote_url if is_remote else BRIGADE_API_URL

    logger.info(
        "Delegating to agent '%s' (%s): %s",
        agent_id,
        f"remote @ {base_url}" if is_remote else "local",
        task[:100],
    )

    message = task
    if context:
        message = f"Context: {context}\n\nTask: {task}"

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{base_url}/api/v1/agents/{agent_id}/chat",
                headers={
                    "Content-Type": "application/json",
                    "X-API-Key": BRIGADE_API_KEY,
                },
                json={"message": message},
            )

            if resp.status_code == 200:
                data = resp.json()
                return {
                    "success": True,
                    "agent_id": agent_id,
                    "remote": is_remote,
                    "response": data.get("content", ""),
                }
            elif resp.status_code == 404:
                return {
                    "success": False,
                    "error": f"Agent '{agent_id}' not found"
                           + (f" on remote node {base_url}" if is_remote else ""),
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
        "sgt-carter-knox (home automation, runs on ha-hq edge node), "
        "the-general (orchestration & strategy), "
        "gunny (agent building), "
        "detective-holmes (OSINT & research), "
        "col-finance (finance & investment), "
        "cpt-fullstack (software engineering), "
        "maj-devops (infrastructure & DevOps), "
        "prof-datasci (data science & analytics), "
        "judge-advocate (legal analysis), "
        "doc-medresearch (medical research). "
        "Some agents may run on remote edge nodes and will be routed automatically."
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
)
