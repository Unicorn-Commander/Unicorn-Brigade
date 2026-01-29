"""
Agent Builder routes — Gunny conversational agent creation.
Provides chat with Gunny to design and deploy new agents.
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, Dict, List
import json
import logging
import uuid

from app.llm.ops_center_client import OpsCenterLLMClient
from app.db.database import get_session, AsyncSession
from app.db.repositories import AgentRepository, BuilderSessionRepository

logger = logging.getLogger(__name__)
router = APIRouter()

# Injected during startup
llm_client: OpsCenterLLMClient = None


def init_builder_routes(client: OpsCenterLLMClient):
    global llm_client
    llm_client = client


# ---- Models ----

class BuilderChatRequest(BaseModel):
    message: str
    sessionId: Optional[str] = None
    userId: Optional[str] = "anonymous"
    preferences: Optional[Dict] = {}


# ---- Gunny System Prompt ----

GUNNY_SYSTEM = """You are Gunny, the Unicorn Brigade's drill instructor and agent builder. You are direct, efficient, and no-nonsense but also supportive.

Your job is to help users create new AI agents through conversation. Guide them through:

1. **Purpose & Domain** — What will this agent do? (financial, legal, medical, technology, investigation, intelligence, cybersecurity, etc.)
2. **Capabilities** — What specific skills does it need? (research, analysis, code generation, data processing, etc.)
3. **Tools** — Which tools should it have access to? (web_search, http_request, calculator, shell, memory, json, datetime)
4. **Personality** — How should it communicate? (formal, casual, technical, friendly)
5. **Model** — Which LLM model? (gpt-4o for quality, gpt-4o-mini for speed, claude-3.5-sonnet for nuance)
6. **Parameters** — Temperature (0.0-2.0), max tokens

When you have enough information to define the agent, output a structured configuration block like:

```json
{
  "name": "agent-slug-name",
  "displayName": "Display Name",
  "title": "Agent's Title",
  "avatar": "🔍",
  "bio": "One-line description",
  "domain": "technology",
  "agentType": "research",
  "capabilities": ["capability-1", "capability-2"],
  "tools": ["web_search", "calculator"],
  "model": "openai/gpt-4o",
  "temperature": 0.7,
  "maxTokens": 4096,
  "systemPrompt": "You are..."
}
```

Then ask: "Ready to deploy this agent? Say **confirm** to create it."

Be direct and efficient. Ask one or two questions at a time, not all at once. Use military metaphors sparingly."""


# ---- Endpoints ----

@router.get("/agent-builder/info")
async def get_builder_info(session: AsyncSession = Depends(get_session)):
    """Return Gunny's info and current builder capabilities."""
    repo = AgentRepository(session)
    gunny = await repo.get("gunny")

    available_tools = [
        "web_search", "http_request", "calculator",
        "datetime", "json", "shell", "memory"
    ]

    available_domains = await repo.get_domains()

    return {
        "builder": {
            "id": "gunny",
            "name": "Gunny",
            "displayName": gunny.get("displayName", "Gunny") if gunny else "Gunny",
            "title": gunny.get("title", "Agent Builder") if gunny else "Agent Builder",
            "avatar": gunny.get("avatar", "🎯") if gunny else "🎯",
            "bio": gunny.get("bio", "") if gunny else "",
            "status": "ready",
        },
        "theGeneral": {
            "status": "online",
            "agentCount": await repo.count(),
        },
        "capabilities": {
            "availableTools": available_tools,
            "availableDomains": [d["name"] for d in available_domains],
            "availableModels": ["openai/gpt-4o", "openai/gpt-4o-mini", "anthropic/claude-3.5-sonnet"],
        }
    }


@router.post("/agent-builder/chat")
async def builder_chat(
    request: BuilderChatRequest,
    session: AsyncSession = Depends(get_session),
):
    """Chat with Gunny to build an agent."""
    repo = BuilderSessionRepository(session)

    # Get or create DB-backed session
    db_session = await repo.get_or_create(
        session_id=request.sessionId,
        user_id=request.userId,
    )
    session_id = db_session["id"]
    history = db_session.get("messages") or []

    # Build messages
    messages = [{"role": "system", "content": GUNNY_SYSTEM}]

    # Add preference context if provided
    if request.preferences:
        pref_parts = []
        if request.preferences.get("model") and request.preferences["model"] != "ai-choice":
            pref_parts.append(f"User prefers model: {request.preferences['model']}")
        if request.preferences.get("domain"):
            pref_parts.append(f"User prefers domain: {request.preferences['domain']}")
        if request.preferences.get("temperature") is not None:
            pref_parts.append(f"User prefers temperature: {request.preferences['temperature']}")
        if request.preferences.get("maxTokens"):
            pref_parts.append(f"User prefers maxTokens: {request.preferences['maxTokens']}")
        if pref_parts:
            messages.append({
                "role": "system",
                "content": f"User preferences: {'; '.join(pref_parts)}"
            })

    # Add conversation history
    for msg in history:
        messages.append({"role": msg["role"], "content": msg["content"]})

    # Add current message
    messages.append({"role": "user", "content": request.message})

    try:
        response = await llm_client.chat_completion(
            messages=messages,
            model="openai/gpt-4o",
            temperature=0.7,
            max_tokens=2000,
            user_id=request.userId
        )

        content = llm_client.get_response_content(response)
        usage = response.get("usage", {})

        # Persist to database
        await repo.add_messages(session_id, request.message, content)

        # Detect agent creation intent (JSON config block in response)
        agent_creation_intent = "```json" in content or '"systemPrompt"' in content

        return {
            "message": content,
            "sessionId": session_id,
            "usage": {
                "total_tokens": usage.get("total_tokens", 0),
                "model": response.get("model", "gpt-4o"),
            },
            "agentCreationIntent": agent_creation_intent,
        }

    except Exception as e:
        logger.error(f"Builder chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/agent-builder/session/{session_id}")
async def get_session_history(
    session_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Get build session conversation history."""
    repo = BuilderSessionRepository(session)
    db_session = await repo.get(session_id)
    if not db_session:
        raise HTTPException(status_code=404, detail="Session not found")

    history = db_session.get("messages") or []
    return {
        "sessionId": session_id,
        "messages": history,
        "messageCount": len(history),
        "agentConfig": db_session.get("agent_config"),
        "status": db_session.get("status"),
    }
