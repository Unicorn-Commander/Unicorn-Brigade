"""
Slack Event Webhook Routes

Handles incoming Slack events and interactions:
- Event subscriptions (messages, reactions, app mentions)
- Interactive components (buttons, modals)
- Slash commands

Configure your Slack App's request URLs:
- Event Subscriptions: https://your-domain/api/v1/slack/events
- Interactivity: https://your-domain/api/v1/slack/interactions
- Slash Commands: https://your-domain/api/v1/slack/commands
"""

import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime

from fastapi import APIRouter, Request, Response, HTTPException, BackgroundTasks, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Annotated

from app.integrations.slack import get_slack_client, SlackClient
from app.llm.ops_center_client import OpsCenterLLMClient
from app.auth.middleware import require_admin, AuthUser

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/slack", tags=["slack"])

# Global references (injected at startup)
_llm_client: Optional[OpsCenterLLMClient] = None


def init_slack_routes(llm_client: OpsCenterLLMClient):
    """Initialize Slack routes with dependencies."""
    global _llm_client
    _llm_client = llm_client
    logger.info("Slack routes initialized")


# ==================== Request Models ====================


class SlackEventCallback(BaseModel):
    """Slack event callback payload."""
    token: str
    team_id: Optional[str] = None
    api_app_id: Optional[str] = None
    event: Optional[Dict[str, Any]] = None
    type: str
    event_id: Optional[str] = None
    event_time: Optional[int] = None
    challenge: Optional[str] = None  # URL verification challenge


class SlackInteractionPayload(BaseModel):
    """Slack interaction payload (buttons, modals, etc.)."""
    type: str
    user: Dict[str, Any]
    channel: Optional[Dict[str, Any]] = None
    message: Optional[Dict[str, Any]] = None
    actions: Optional[list] = None
    trigger_id: Optional[str] = None
    response_url: Optional[str] = None


class SlackCommandPayload(BaseModel):
    """Slack slash command payload."""
    command: str
    text: str
    user_id: str
    user_name: str
    channel_id: str
    channel_name: str
    team_id: str
    response_url: str
    trigger_id: str


# ==================== Webhook Endpoints ====================


@router.post("/events")
async def slack_events(request: Request, background_tasks: BackgroundTasks):
    """
    Handle Slack Event API webhooks.

    Supports:
    - URL verification (challenge response)
    - Message events
    - App mention events
    - Reaction events
    - Channel events

    Returns:
        Challenge response for verification, or acknowledgment for events
    """
    # Get raw body for signature verification
    body = await request.body()

    # Get headers for signature verification
    timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    signature = request.headers.get("X-Slack-Signature", "")

    # Verify signature (skip in development if signing secret not set)
    slack_client = get_slack_client()
    if slack_client.signing_secret:
        try:
            if not slack_client.verify_request(body, timestamp, signature):
                logger.warning("Invalid Slack signature")
                raise HTTPException(status_code=401, detail="Invalid signature")
        except ValueError:
            # Signing secret not configured - log warning but continue in dev
            logger.warning("Slack signing secret not configured - skipping verification")

    # Parse payload
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    event_type = payload.get("type")

    # Handle URL verification challenge
    if event_type == "url_verification":
        challenge = payload.get("challenge")
        logger.info("Slack URL verification challenge received")
        return {"challenge": challenge}

    # Handle event callback
    if event_type == "event_callback":
        event = payload.get("event", {})
        event_subtype = event.get("type")

        logger.info(f"Slack event received: {event_subtype}")

        # Process event in background to respond quickly
        background_tasks.add_task(
            process_slack_event,
            event=event,
            team_id=payload.get("team_id"),
            event_id=payload.get("event_id"),
        )

        # Acknowledge receipt immediately
        return Response(status_code=200)

    logger.warning(f"Unknown Slack event type: {event_type}")
    return Response(status_code=200)


@router.post("/interactions")
async def slack_interactions(request: Request, background_tasks: BackgroundTasks):
    """
    Handle Slack interactive components.

    Supports:
    - Button clicks
    - Select menu changes
    - Modal submissions
    - Message shortcuts

    Returns:
        Immediate response or acknowledgment
    """
    # Get form data (interactions come as form-encoded)
    form_data = await request.form()
    payload_str = form_data.get("payload", "{}")

    try:
        payload = json.loads(payload_str)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid payload")

    interaction_type = payload.get("type")
    logger.info(f"Slack interaction received: {interaction_type}")

    # Process interaction in background
    background_tasks.add_task(
        process_slack_interaction,
        payload=payload,
    )

    # Acknowledge receipt immediately
    # For modals, return empty JSON. For messages, return nothing.
    if interaction_type in ["view_submission", "view_closed"]:
        return JSONResponse(content={})

    return Response(status_code=200)


@router.post("/commands")
async def slack_commands(request: Request, background_tasks: BackgroundTasks):
    """
    Handle Slack slash commands.

    Configure commands in your Slack App and point them here.
    Example: /unicorn <message> -> sends to an AI agent

    Returns:
        Immediate ephemeral response, with follow-up via response_url
    """
    # Parse form data
    form_data = await request.form()

    command = form_data.get("command", "")
    text = form_data.get("text", "")
    user_id = form_data.get("user_id", "")
    user_name = form_data.get("user_name", "")
    channel_id = form_data.get("channel_id", "")
    channel_name = form_data.get("channel_name", "")
    response_url = form_data.get("response_url", "")
    trigger_id = form_data.get("trigger_id", "")

    logger.info(f"Slack command received: {command} from {user_name}")

    # Process command in background
    background_tasks.add_task(
        process_slack_command,
        command=command,
        text=text,
        user_id=user_id,
        channel_id=channel_id,
        response_url=response_url,
    )

    # Immediate ephemeral response
    return JSONResponse(
        content={
            "response_type": "ephemeral",
            "text": f"Processing your request: `{text}`...",
        }
    )


# ==================== Event Handlers ====================


async def process_slack_event(
    event: Dict[str, Any],
    team_id: Optional[str],
    event_id: Optional[str],
):
    """
    Process a Slack event asynchronously.

    Handles:
    - app_mention: When the bot is @mentioned
    - message: New messages (can filter by channel type)
    - reaction_added: When a reaction is added
    """
    event_type = event.get("type")
    logger.info(f"Processing Slack event: {event_type} (event_id: {event_id})")

    slack_client = get_slack_client()

    try:
        if event_type == "app_mention":
            await handle_app_mention(event, slack_client)

        elif event_type == "message":
            # Skip bot messages to avoid loops
            if event.get("bot_id") or event.get("subtype") == "bot_message":
                return

            # Only handle direct messages or specific triggers
            channel_type = event.get("channel_type")
            if channel_type == "im":
                # Direct message to the bot
                await handle_direct_message(event, slack_client)

        elif event_type == "reaction_added":
            await handle_reaction_added(event, slack_client)

        else:
            logger.debug(f"Unhandled event type: {event_type}")

    except Exception as e:
        logger.error(f"Error processing Slack event: {e}")


async def handle_app_mention(event: Dict[str, Any], slack_client: SlackClient):
    """Handle when the bot is @mentioned."""
    channel = event.get("channel")
    user = event.get("user")
    text = event.get("text", "")
    thread_ts = event.get("thread_ts") or event.get("ts")

    # Remove the mention from the text
    # Text comes like: "<@U123> hello" - remove the mention
    import re
    cleaned_text = re.sub(r"<@[A-Z0-9]+>\s*", "", text).strip()

    logger.info(f"App mention from {user} in {channel}: {cleaned_text}")

    if not cleaned_text:
        # Just a mention with no text
        await slack_client.send_message(
            channel=channel,
            text="Hi! How can I help you? Just mention me with your question.",
            thread_ts=thread_ts,
        )
        return

    # Process with LLM if available
    if _llm_client:
        try:
            response = await _llm_client.chat_completion(
                messages=[
                    {"role": "system", "content": "You are a helpful AI assistant integrated with Slack. Keep responses concise and professional."},
                    {"role": "user", "content": cleaned_text},
                ],
                model="default",
                max_tokens=500,
            )

            assistant_message = _llm_client.get_response_content(response)

            await slack_client.send_message(
                channel=channel,
                text=assistant_message,
                thread_ts=thread_ts,
            )

        except Exception as e:
            logger.error(f"Error processing mention with LLM: {e}")
            await slack_client.send_message(
                channel=channel,
                text="Sorry, I encountered an error processing your request.",
                thread_ts=thread_ts,
            )
    else:
        # No LLM configured - simple echo
        await slack_client.send_message(
            channel=channel,
            text=f"I heard you say: {cleaned_text}",
            thread_ts=thread_ts,
        )


async def handle_direct_message(event: Dict[str, Any], slack_client: SlackClient):
    """Handle direct messages to the bot."""
    channel = event.get("channel")
    user = event.get("user")
    text = event.get("text", "")

    logger.info(f"Direct message from {user}: {text}")

    # Process with LLM if available
    if _llm_client:
        try:
            response = await _llm_client.chat_completion(
                messages=[
                    {"role": "system", "content": "You are a helpful AI assistant. The user is messaging you directly via Slack. Be helpful and concise."},
                    {"role": "user", "content": text},
                ],
                model="default",
                max_tokens=500,
            )

            assistant_message = _llm_client.get_response_content(response)

            await slack_client.send_message(
                channel=channel,
                text=assistant_message,
            )

        except Exception as e:
            logger.error(f"Error processing DM with LLM: {e}")
            await slack_client.send_message(
                channel=channel,
                text="Sorry, I encountered an error processing your message.",
            )
    else:
        await slack_client.send_message(
            channel=channel,
            text=f"Thanks for your message! I received: {text}",
        )


async def handle_reaction_added(event: Dict[str, Any], slack_client: SlackClient):
    """Handle when a reaction is added to a message."""
    reaction = event.get("reaction")
    user = event.get("user")
    item = event.get("item", {})

    logger.info(f"Reaction {reaction} added by {user}")

    # Example: Track specific reactions for feedback
    if reaction in ["thumbsup", "+1"]:
        logger.info(f"Positive feedback on message {item.get('ts')}")
    elif reaction in ["thumbsdown", "-1"]:
        logger.info(f"Negative feedback on message {item.get('ts')}")


async def process_slack_interaction(payload: Dict[str, Any]):
    """Process a Slack interaction asynchronously."""
    interaction_type = payload.get("type")

    logger.info(f"Processing Slack interaction: {interaction_type}")

    if interaction_type == "block_actions":
        # Button click or select menu
        actions = payload.get("actions", [])
        for action in actions:
            action_id = action.get("action_id")
            action_value = action.get("value")
            logger.info(f"Action: {action_id} = {action_value}")

    elif interaction_type == "view_submission":
        # Modal submission
        view = payload.get("view", {})
        callback_id = view.get("callback_id")
        values = view.get("state", {}).get("values", {})
        logger.info(f"Modal submitted: {callback_id}")

    elif interaction_type == "shortcut":
        # Global or message shortcut
        callback_id = payload.get("callback_id")
        logger.info(f"Shortcut triggered: {callback_id}")


async def process_slack_command(
    command: str,
    text: str,
    user_id: str,
    channel_id: str,
    response_url: str,
):
    """Process a Slack slash command asynchronously."""
    import httpx

    logger.info(f"Processing command {command}: {text}")

    slack_client = get_slack_client()

    try:
        # Process with LLM if available
        if _llm_client and text:
            response = await _llm_client.chat_completion(
                messages=[
                    {"role": "system", "content": f"You are an AI assistant responding to a Slack slash command '{command}'. Be helpful and format responses for Slack (use *bold* and _italic_ for emphasis)."},
                    {"role": "user", "content": text},
                ],
                model="default",
                max_tokens=1000,
            )

            assistant_message = _llm_client.get_response_content(response)

            # Send response via response_url
            async with httpx.AsyncClient() as client:
                await client.post(
                    response_url,
                    json={
                        "response_type": "in_channel",  # or "ephemeral" for private
                        "text": assistant_message,
                    },
                )

        else:
            # Echo command
            async with httpx.AsyncClient() as client:
                await client.post(
                    response_url,
                    json={
                        "response_type": "in_channel",
                        "text": f"Received command `{command}` with text: {text}",
                    },
                )

    except Exception as e:
        logger.error(f"Error processing slash command: {e}")

        # Send error response
        try:
            async with httpx.AsyncClient() as client:
                await client.post(
                    response_url,
                    json={
                        "response_type": "ephemeral",
                        "text": f"Error processing command: {str(e)}",
                    },
                )
        except Exception:
            pass


# ==================== Utility Endpoints ====================


@router.get("/health")
async def slack_health():
    """Check Slack integration health."""
    slack_client = get_slack_client()

    return {
        "configured": slack_client.is_configured(),
        "bot_token_set": bool(slack_client.bot_token),
        "user_token_set": bool(slack_client.user_token),
        "signing_secret_set": bool(slack_client.signing_secret),
    }


@router.post("/test")
async def slack_test(
    channel: str = "#general",
    message: str = "Hello from Unicorn Brigade!",
    user: Annotated[AuthUser, Depends(require_admin)] = None,
):
    """
    Test Slack integration by sending a message.

    Args:
        channel: Channel to send to
        message: Message to send
    """
    slack_client = get_slack_client()

    if not slack_client.is_configured():
        raise HTTPException(
            status_code=503,
            detail="Slack not configured. Set SLACK_BOT_TOKEN environment variable.",
        )

    result = await slack_client.send_message(channel=channel, text=message)

    if not result.get("success"):
        raise HTTPException(
            status_code=500,
            detail=f"Failed to send message: {result.get('error')}",
        )

    return result
