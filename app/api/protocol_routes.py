"""
Protocol API Routes

Implements endpoints for:
- A2A (Agent-to-Agent) Protocol - Agent cards and invocation
- MCP (Model Context Protocol) - Tool listing and invocation
- UCP (Universal Commerce Protocol) - Commerce sessions and payments
"""

from fastapi import APIRouter, HTTPException, status, Header, Request, Depends
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from app.protocols.a2a import A2AProtocol, AgentCard, A2AInvokeRequest, A2AInvokeResponse
from app.protocols.mcp import MCPServer, mcp_server, MCPResourceManager
from app.protocols.ucp import UCPPayment, CommerceSession
from app.db.database import get_session
from app.db.repositories import AgentRepository

logger = logging.getLogger(__name__)

# Routers
a2a_router = APIRouter(prefix="/a2a", tags=["A2A Protocol"])
mcp_router = APIRouter(prefix="/mcp", tags=["MCP Protocol"])
ucp_router = APIRouter(prefix="/ucp", tags=["UCP Protocol"])

# Protocol instances
a2a_protocol = A2AProtocol()
ucp_handler = UCPPayment()

# Resource manager for MCP resource reading
resource_manager = MCPResourceManager()


# =============================================================================
# A2A (Agent-to-Agent) Protocol Routes
# =============================================================================

class AgentCardResponse(BaseModel):
    """Agent card response"""
    name: str
    description: str
    version: str
    invoke_url: str
    capabilities: List[Dict[str, Any]]
    pricing_model: str
    price_per_call: Optional[float]


@a2a_router.get("/agents/{agent_id}/card")
async def get_agent_card(agent_id: str):
    """
    Get A2A Agent Card for an agent.

    The Agent Card describes the agent's capabilities for discovery.
    """
    # Generate agent card (in production, fetch from database)
    card = a2a_protocol.generate_card(
        agent_id=agent_id,
        name=f"Agent {agent_id}",
        description="AI agent on Unicorn Brigade",
        capabilities=[
            {
                "name": "execute_task",
                "description": "Execute a task",
                "parameters": {"task": {"type": "string"}},
                "returns": {"result": {"type": "object"}},
            }
        ],
        domain="general",
        pricing_model="free",
    )

    return card.model_dump()


@a2a_router.post("/agents/{agent_id}/invoke")
async def invoke_agent(
    agent_id: str,
    request: A2AInvokeRequest,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    session: AsyncSession = Depends(get_session),
):
    """
    Invoke an agent using A2A protocol.

    This is the standard endpoint for agent-to-agent communication.
    Routes to the actual agent chat endpoint for execution with function calling.
    """
    try:
        start_time = datetime.utcnow()

        # First, try to use the agent chat system (preferred - supports function calling)
        from app.api.agent_routes import llm_client
        from app.llm.tool_resolver import get_tools_for_agent

        repo = AgentRepository(session)
        agent = await repo.get(agent_id)

        if agent and llm_client:
            # Build system message from agent config
            system_parts = []
            if agent.get("persona"):
                system_parts.append(agent["persona"])
            if agent.get("systemPrompt"):
                system_parts.append(agent["systemPrompt"])
            system_content = "\n\n".join(system_parts) if system_parts else (
                f"You are {agent.get('displayName', agent['name'])}, a specialized AI agent."
            )

            # Build messages for LLM
            messages = [
                {"role": "system", "content": system_content},
                {"role": "user", "content": request.task},
            ]

            # Add context if provided
            if request.context:
                context_str = "\n".join(f"- {k}: {v}" for k, v in request.context.items())
                messages[1]["content"] = f"Context:\n{context_str}\n\nTask: {request.task}"

            # Resolve agent tools
            agent_tools = get_tools_for_agent(agent)

            model = agent.get("model", "openai/gpt-4o-mini")
            temperature = agent.get("temperature", 0.7)
            max_tokens = agent.get("maxTokens", 2000)

            tool_calls_log = []

            if agent_tools:
                # Execute with function calling
                from app.llm.ops_center_client import ToolCall, ToolResult

                def on_tool_call(tc: ToolCall):
                    tool_calls_log.append({
                        "id": tc.id,
                        "name": tc.name,
                        "arguments": tc.arguments,
                    })

                def on_tool_result(tr: ToolResult):
                    for entry in tool_calls_log:
                        if entry["id"] == tr.tool_call_id:
                            entry["result"] = tr.result
                            entry["error"] = tr.error
                            break

                response = await llm_client.execute_tool_loop(
                    messages=messages,
                    tools=agent_tools,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    user_id=request.user_id or "a2a-caller",
                    on_tool_call=on_tool_call,
                    on_tool_result=on_tool_result,
                )
            else:
                # Plain chat without tools
                response = await llm_client.chat_completion(
                    messages=messages,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    user_id=request.user_id or "a2a-caller",
                )

            content = llm_client.get_response_content(response)
            usage = response.get("usage", {})
            duration = (datetime.utcnow() - start_time).total_seconds()

            result_data = {
                "output": content,
                "model": response.get("model", model),
            }
            if tool_calls_log:
                result_data["tool_calls"] = tool_calls_log

            return A2AInvokeResponse(
                status="success",
                result=result_data,
                task_id=f"a2a_{agent_id}_{datetime.utcnow().timestamp()}",
                tokens_used=usage.get("total_tokens", 0),
                duration_seconds=duration,
            ).model_dump()

        # Fallback to workflow engine if agent not found or llm_client not available
        from app.engine.models import Task
        from app.api.workflow_routes import workflow_engine

        if workflow_engine:
            task = Task(
                task=request.task,
                user_id=request.user_id or "a2a-caller",
                context=request.context,
            )

            result = await workflow_engine.execute(task)

            duration = (datetime.utcnow() - start_time).total_seconds()

            return A2AInvokeResponse(
                status="success" if result.status == "completed" else "error",
                result={"output": result.output},
                task_id=result.task_id,
                tokens_used=result.tokens_used,
                duration_seconds=duration,
            ).model_dump()

        # Agent not found
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent not found: {agent_id}"
            )

        # Mock response when neither agent chat nor engine available
        duration = (datetime.utcnow() - start_time).total_seconds()

        return A2AInvokeResponse(
            status="success",
            result={"message": f"Agent {agent_id} processed task"},
            task_id=f"a2a_{agent_id}_{datetime.utcnow().timestamp()}",
            duration_seconds=duration,
        ).model_dump()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"A2A invoke failed: {e}")
        return A2AInvokeResponse(
            status="error",
            error=str(e),
        ).model_dump()


@a2a_router.get("/discover")
async def discover_agents(
    capability: Optional[str] = None,
    domain: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
):
    """
    Discover available agents.

    Returns a list of Agent Cards matching the criteria.
    Queries the database for actual agents and converts them to A2A format.
    """
    repo = AgentRepository(session)
    db_agents = await repo.list_all()

    # Convert database agents to A2A Agent Card format
    agents = []
    for agent in db_agents:
        # Skip inactive agents
        if agent.get("status") != "active":
            continue

        # Build capabilities from agent's tools and capabilities list
        capabilities = []
        for cap in agent.get("capabilities", []):
            capabilities.append({
                "name": cap,
                "description": f"Agent capability: {cap}",
            })

        # Add tool-based capabilities
        for tool in agent.get("tools", []):
            capabilities.append({
                "name": tool,
                "description": f"Tool: {tool}",
            })

        agent_card = {
            "id": agent["id"],
            "name": agent.get("displayName") or agent.get("name"),
            "description": agent.get("bio") or agent.get("persona") or f"AI agent: {agent.get('name')}",
            "version": "1.0.0",
            "invoke_url": f"/api/v1/a2a/agents/{agent['id']}/invoke",
            "capabilities": capabilities,
            "pricing_model": "free",  # Default to free; could be stored in agent config
            "domain": agent.get("domain", "general"),
            "avatar": agent.get("avatar", ""),
            "agent_type": agent.get("agentType", "analysis"),
        }

        agents.append(agent_card)

    # Filter by capability
    if capability:
        agents = [a for a in agents if any(
            c["name"] == capability or c["name"].lower() == capability.lower()
            for c in a.get("capabilities", [])
        )]

    # Filter by domain
    if domain:
        agents = [a for a in agents if a.get("domain") == domain or a.get("domain", "").lower() == domain.lower()]

    return {
        "agents": agents,
        "count": len(agents),
    }


# =============================================================================
# MCP (Model Context Protocol) Routes
# =============================================================================

@mcp_router.get("/tools")
async def list_mcp_tools():
    """
    List all registered MCP tools.

    Returns tools in Anthropic format for Claude integration.
    """
    return {
        "tools": mcp_server.get_tools_list(),
        "count": len(mcp_server.tools),
    }


@mcp_router.get("/tools/openai")
async def list_mcp_tools_openai():
    """
    List tools in OpenAI function calling format.
    """
    return {
        "tools": mcp_server.get_openai_tools(),
        "count": len(mcp_server.tools),
    }


@mcp_router.post("/tools/{tool_name}/invoke")
async def invoke_mcp_tool(
    tool_name: str,
    request: Dict[str, Any],
    user_id: str = Header("anonymous", alias="X-User-ID"),
):
    """
    Invoke an MCP tool.

    This allows external LLMs to use Brigade's tools.
    """
    try:
        arguments = request.get("arguments", request)

        result = await mcp_server.invoke_tool(
            name=tool_name,
            arguments=arguments,
            user_id=user_id,
        )

        return result

    except Exception as e:
        logger.error(f"MCP tool invocation failed: {e}")
        return {"error": str(e)}


@mcp_router.get("/resources")
async def list_mcp_resources():
    """List all registered MCP resources"""
    return {
        "resources": mcp_server.get_resources_list(),
        "count": len(mcp_server.resources),
    }


@mcp_router.get("/resources/{uri:path}")
async def read_mcp_resource(uri: str):
    """
    Read an MCP resource.

    Supports multiple URI schemes:
    - file:// - Local file system resources
    - http:// / https:// - Remote HTTP resources
    - Custom schemes registered with the resource manager
    """
    # Check if resource is registered (optional - allows reading unregistered URIs too)
    resource = mcp_server.resources.get(uri)

    # Use the resource manager to read the content
    try:
        result = await resource_manager.read(uri)

        if "error" in result:
            # Resource read failed
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["error"]
            )

        # Return in MCP format
        contents = result.get("contents", [])

        # If resource is registered, include its metadata
        response = {
            "uri": uri,
            "contents": contents,
        }

        if resource:
            response["name"] = resource.name
            response["description"] = resource.description
            response["mimeType"] = resource.mime_type

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"MCP resource read failed for {uri}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read resource: {str(e)}"
        )


@mcp_router.post("/handle")
async def handle_mcp_request(request: Dict[str, Any]):
    """
    Handle an MCP protocol request.

    This is the main entry point for MCP clients.
    """
    return await mcp_server.handle_mcp_request(request)


# =============================================================================
# UCP (Universal Commerce Protocol) Routes
# =============================================================================

class CreateSessionRequest(BaseModel):
    """Request to create a commerce session"""
    agent_id: str
    price_per_call: float = 0.0


class ChargeCallRequest(BaseModel):
    """Request to charge for an agent call"""
    tokens_used: int = 0


@ucp_router.post("/sessions")
async def create_commerce_session(
    request: CreateSessionRequest,
    user_id: str = Header(..., alias="X-User-ID"),
):
    """
    Create a commerce session for agent usage.

    Sessions track billing for paid agent interactions.
    """
    try:
        # Get user's credit balance
        balance = await ucp_handler.get_user_balance(user_id)

        session = await ucp_handler.create_session(
            user_id=user_id,
            agent_id=request.agent_id,
            price_per_call=request.price_per_call,
            user_credits=balance.get("credits", 0),
        )

        return {
            "session_id": session.id,
            "agent_id": session.agent_id,
            "price_per_call": session.price_per_call,
            "user_credits": session.user_credits,
            "status": session.status,
        }

    except Exception as e:
        logger.error(f"Session creation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@ucp_router.post("/sessions/{session_id}/charge")
async def charge_session(
    session_id: str,
    request: ChargeCallRequest,
):
    """
    Charge for an agent call within a session.
    """
    try:
        result = await ucp_handler.charge_call(
            session_id=session_id,
            tokens_used=request.tokens_used,
        )

        if "error" in result:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["error"]
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Charge failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@ucp_router.get("/sessions/{session_id}")
async def get_session(session_id: str):
    """Get commerce session details"""
    session = ucp_handler.get_session(session_id)

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session not found: {session_id}"
        )

    return session.model_dump()


@ucp_router.get("/balance")
async def get_user_balance(
    user_id: str = Header(..., alias="X-User-ID"),
):
    """Get user's credit balance"""
    try:
        balance = await ucp_handler.get_user_balance(user_id)
        return balance

    except Exception as e:
        logger.error(f"Balance check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@ucp_router.post("/credits/add")
async def add_credits(
    amount: float,
    user_id: str = Header(..., alias="X-User-ID"),
    source: str = "api",
):
    """Add credits to user account"""
    try:
        success = await ucp_handler.add_credits(
            user_id=user_id,
            amount=amount,
            source=source,
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to add credits"
            )

        return {
            "user_id": user_id,
            "credits_added": amount,
            "source": source,
            "timestamp": datetime.utcnow().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Add credits failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@ucp_router.get("/payments/{payment_id}")
async def get_payment(payment_id: str):
    """Get payment intent details"""
    payment = ucp_handler.get_payment(payment_id)

    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Payment not found: {payment_id}"
        )

    return payment.model_dump()


@ucp_router.post("/payments/{payment_id}/refund")
async def refund_payment(
    payment_id: str,
    reason: str = "",
):
    """Refund a captured payment"""
    try:
        success = await ucp_handler.refund_payment(
            payment_id=payment_id,
            reason=reason,
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Payment cannot be refunded"
            )

        return {
            "payment_id": payment_id,
            "refunded": True,
            "reason": reason,
            "timestamp": datetime.utcnow().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Refund failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
