"""
Slack Tool Definition for Agent Execution

Provides Slack integration as a tool that agents can use to interact with
Slack workspaces - sending messages, reading channels, managing reactions, etc.
"""

import logging
from typing import Dict, Any, Optional, List

from app.llm.ops_center_client import ToolDefinition, ToolParameter
from app.integrations.slack import get_slack_client, SlackClient

logger = logging.getLogger(__name__)


async def slack_handler(
    action: str,
    channel: Optional[str] = None,
    user_id: Optional[str] = None,
    message: Optional[str] = None,
    query: Optional[str] = None,
    emoji: Optional[str] = None,
    timestamp: Optional[str] = None,
    thread_ts: Optional[str] = None,
    limit: int = 10,
    file_path: Optional[str] = None,
    file_content: Optional[str] = None,
    filename: Optional[str] = None,
    title: Optional[str] = None,
    blocks: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Unified Slack tool handler for all Slack operations.

    Args:
        action: The Slack action to perform
        channel: Channel name or ID (for channel operations)
        user_id: User ID or email (for DM and user operations)
        message: Message text to send
        query: Search query
        emoji: Emoji name for reactions
        timestamp: Message timestamp (for reactions)
        thread_ts: Thread timestamp (for replies)
        limit: Number of results to return
        file_path: Path to file to upload
        file_content: File content to upload
        filename: Filename for uploaded content
        title: Title for uploaded file
        blocks: Block Kit blocks for rich formatting

    Returns:
        Dict with operation results
    """
    logger.info(f"Slack tool action: {action}")

    # Get client
    client = get_slack_client()

    # Check if configured
    if not client.is_configured():
        return {
            "success": False,
            "error": "Slack not configured. Set SLACK_BOT_TOKEN environment variable.",
        }

    try:
        # Route to appropriate handler
        if action == "send_message":
            if not channel:
                return {"success": False, "error": "Channel is required for send_message"}
            if not message:
                return {"success": False, "error": "Message is required for send_message"}

            return await client.send_message(
                channel=channel,
                text=message,
                blocks=blocks,
                thread_ts=thread_ts,
            )

        elif action == "send_dm":
            if not user_id:
                return {"success": False, "error": "User ID is required for send_dm"}
            if not message:
                return {"success": False, "error": "Message is required for send_dm"}

            return await client.send_dm(
                user_id=user_id,
                text=message,
                blocks=blocks,
            )

        elif action == "list_channels":
            return await client.list_channels(limit=limit)

        elif action == "list_users":
            return await client.list_users(limit=limit)

        elif action == "get_history":
            if not channel:
                return {"success": False, "error": "Channel is required for get_history"}

            return await client.get_channel_history(
                channel=channel,
                limit=limit,
            )

        elif action == "search":
            if not query:
                return {"success": False, "error": "Query is required for search"}

            return await client.search_messages(
                query=query,
                count=limit,
            )

        elif action == "react":
            if not channel:
                return {"success": False, "error": "Channel is required for react"}
            if not timestamp:
                return {"success": False, "error": "Timestamp is required for react"}
            if not emoji:
                return {"success": False, "error": "Emoji is required for react"}

            return await client.add_reaction(
                channel=channel,
                timestamp=timestamp,
                emoji=emoji,
            )

        elif action == "upload_file":
            if not channel:
                return {"success": False, "error": "Channel is required for upload_file"}
            if not file_path and not file_content:
                return {"success": False, "error": "Either file_path or file_content is required for upload_file"}

            return await client.upload_file(
                channels=channel,
                file_path=file_path,
                content=file_content,
                filename=filename,
                title=title,
                thread_ts=thread_ts,
            )

        elif action == "get_user":
            if not user_id:
                return {"success": False, "error": "User ID is required for get_user"}

            return await client.get_user_info(user_id=user_id)

        elif action == "update_message":
            if not channel:
                return {"success": False, "error": "Channel is required for update_message"}
            if not timestamp:
                return {"success": False, "error": "Timestamp is required for update_message"}
            if not message:
                return {"success": False, "error": "Message is required for update_message"}

            return await client.update_message(
                channel=channel,
                ts=timestamp,
                text=message,
                blocks=blocks,
            )

        elif action == "delete_message":
            if not channel:
                return {"success": False, "error": "Channel is required for delete_message"}
            if not timestamp:
                return {"success": False, "error": "Timestamp is required for delete_message"}

            return await client.delete_message(
                channel=channel,
                ts=timestamp,
            )

        else:
            return {
                "success": False,
                "error": f"Unknown action: {action}. Valid actions: send_message, send_dm, list_channels, list_users, get_history, search, react, upload_file, get_user, update_message, delete_message",
            }

    except Exception as e:
        logger.error(f"Slack tool error: {e}")
        return {
            "success": False,
            "error": str(e),
        }


# Tool Definition
SLACK_TOOL = ToolDefinition(
    name="slack",
    description="Interact with Slack workspaces. Send messages, read channels, search messages, add reactions, upload files, and more. Requires SLACK_BOT_TOKEN to be configured.",
    parameters=[
        ToolParameter(
            name="action",
            type="string",
            description="The Slack action to perform",
            required=True,
            enum=[
                "send_message",
                "send_dm",
                "list_channels",
                "list_users",
                "get_history",
                "search",
                "react",
                "upload_file",
                "get_user",
                "update_message",
                "delete_message",
            ],
        ),
        ToolParameter(
            name="channel",
            type="string",
            description="Channel name (e.g., #general) or ID. Required for: send_message, get_history, react, upload_file, update_message, delete_message",
            required=False,
        ),
        ToolParameter(
            name="user_id",
            type="string",
            description="User ID (U1234567890) or email address. Required for: send_dm, get_user",
            required=False,
        ),
        ToolParameter(
            name="message",
            type="string",
            description="Message text to send. Required for: send_message, send_dm, update_message",
            required=False,
        ),
        ToolParameter(
            name="query",
            type="string",
            description="Search query (supports Slack search syntax). Required for: search",
            required=False,
        ),
        ToolParameter(
            name="emoji",
            type="string",
            description="Emoji name without colons (e.g., 'thumbsup'). Required for: react",
            required=False,
        ),
        ToolParameter(
            name="timestamp",
            type="string",
            description="Message timestamp (ts). Required for: react, update_message, delete_message",
            required=False,
        ),
        ToolParameter(
            name="thread_ts",
            type="string",
            description="Thread timestamp for replying in a thread. Optional for: send_message, upload_file",
            required=False,
        ),
        ToolParameter(
            name="limit",
            type="number",
            description="Number of results to return (default: 10). Used by: list_channels, list_users, get_history, search",
            required=False,
            default=10,
        ),
        ToolParameter(
            name="file_path",
            type="string",
            description="Path to file to upload. Required for upload_file (unless file_content provided)",
            required=False,
        ),
        ToolParameter(
            name="file_content",
            type="string",
            description="File content to upload as text. Alternative to file_path for upload_file",
            required=False,
        ),
        ToolParameter(
            name="filename",
            type="string",
            description="Filename for uploaded content. Optional for: upload_file",
            required=False,
        ),
        ToolParameter(
            name="title",
            type="string",
            description="Title for uploaded file. Optional for: upload_file",
            required=False,
        ),
        ToolParameter(
            name="blocks",
            type="array",
            description="Block Kit blocks for rich message formatting (JSON array). Optional for: send_message, send_dm, update_message",
            required=False,
        ),
    ],
    handler=slack_handler,
)


# Export all tools
SLACK_TOOLS = [SLACK_TOOL]
