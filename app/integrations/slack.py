"""
Slack Integration Client

Provides a comprehensive Slack integration using the official slack_sdk.
Supports both Bot Token and User Token authentication for different use cases.

Bot Token (xoxb-*): For app-level actions (posting to channels, managing channels)
User Token (xoxp-*): For user-level actions (search, advanced features)
"""

import logging
import os
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass
from datetime import datetime

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from slack_sdk.signature import SignatureVerifier

logger = logging.getLogger(__name__)

# Environment configuration
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN", "")
SLACK_USER_TOKEN = os.getenv("SLACK_USER_TOKEN", "")
SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET", "")
SLACK_APP_ID = os.getenv("SLACK_APP_ID", "")


@dataclass
class SlackMessage:
    """Represents a Slack message"""
    channel: str
    text: str
    user: Optional[str] = None
    timestamp: Optional[str] = None
    thread_ts: Optional[str] = None
    blocks: Optional[List[Dict[str, Any]]] = None
    attachments: Optional[List[Dict[str, Any]]] = None


@dataclass
class SlackChannel:
    """Represents a Slack channel"""
    id: str
    name: str
    is_private: bool
    is_member: bool
    num_members: int
    topic: Optional[str] = None
    purpose: Optional[str] = None


@dataclass
class SlackUser:
    """Represents a Slack user"""
    id: str
    name: str
    real_name: str
    display_name: str
    email: Optional[str] = None
    is_bot: bool = False
    is_admin: bool = False


class SlackClient:
    """
    Slack API client with comprehensive functionality.

    Supports:
    - Sending messages (channel, DM, threaded)
    - Channel management (list, history)
    - User management (list, lookup)
    - Search (messages)
    - Reactions
    - File uploads

    Example:
        client = SlackClient()
        await client.send_message("#general", "Hello from Unicorn Brigade!")
    """

    def __init__(
        self,
        bot_token: Optional[str] = None,
        user_token: Optional[str] = None,
        signing_secret: Optional[str] = None,
    ):
        """
        Initialize Slack client.

        Args:
            bot_token: Bot OAuth token (xoxb-*). Falls back to SLACK_BOT_TOKEN env var.
            user_token: User OAuth token (xoxp-*). Falls back to SLACK_USER_TOKEN env var.
            signing_secret: Signing secret for webhook verification. Falls back to SLACK_SIGNING_SECRET env var.
        """
        self.bot_token = bot_token or SLACK_BOT_TOKEN
        self.user_token = user_token or SLACK_USER_TOKEN
        self.signing_secret = signing_secret or SLACK_SIGNING_SECRET

        # Initialize clients
        self._bot_client: Optional[WebClient] = None
        self._user_client: Optional[WebClient] = None
        self._signature_verifier: Optional[SignatureVerifier] = None

        # Cache for channel/user lookups
        self._channel_cache: Dict[str, str] = {}  # name -> id mapping
        self._user_cache: Dict[str, str] = {}  # name/email -> id mapping

        logger.info(
            f"SlackClient initialized - Bot token: {'set' if self.bot_token else 'not set'}, "
            f"User token: {'set' if self.user_token else 'not set'}"
        )

    @property
    def bot_client(self) -> WebClient:
        """Get or create the bot WebClient."""
        if not self._bot_client:
            if not self.bot_token:
                raise ValueError("Bot token not configured. Set SLACK_BOT_TOKEN environment variable.")
            self._bot_client = WebClient(token=self.bot_token)
        return self._bot_client

    @property
    def user_client(self) -> WebClient:
        """Get or create the user WebClient."""
        if not self._user_client:
            if not self.user_token:
                raise ValueError("User token not configured. Set SLACK_USER_TOKEN environment variable.")
            self._user_client = WebClient(token=self.user_token)
        return self._user_client

    @property
    def signature_verifier(self) -> SignatureVerifier:
        """Get or create the signature verifier."""
        if not self._signature_verifier:
            if not self.signing_secret:
                raise ValueError("Signing secret not configured. Set SLACK_SIGNING_SECRET environment variable.")
            self._signature_verifier = SignatureVerifier(signing_secret=self.signing_secret)
        return self._signature_verifier

    def is_configured(self) -> bool:
        """Check if the client is properly configured with at least a bot token."""
        return bool(self.bot_token)

    def verify_request(self, body: bytes, timestamp: str, signature: str) -> bool:
        """
        Verify a Slack webhook request signature.

        Args:
            body: Raw request body
            timestamp: X-Slack-Request-Timestamp header
            signature: X-Slack-Signature header

        Returns:
            True if signature is valid
        """
        try:
            return self.signature_verifier.is_valid(
                body=body.decode("utf-8") if isinstance(body, bytes) else body,
                timestamp=timestamp,
                signature=signature,
            )
        except Exception as e:
            logger.error(f"Signature verification failed: {e}")
            return False

    # ==================== Messaging ====================

    async def send_message(
        self,
        channel: str,
        text: str,
        blocks: Optional[List[Dict[str, Any]]] = None,
        thread_ts: Optional[str] = None,
        reply_broadcast: bool = False,
        unfurl_links: bool = True,
        unfurl_media: bool = True,
    ) -> Dict[str, Any]:
        """
        Send a message to a Slack channel.

        Args:
            channel: Channel name (#general) or ID (C1234567890)
            text: Message text (also used as fallback for blocks)
            blocks: Block Kit blocks for rich formatting
            thread_ts: Thread timestamp to reply to
            reply_broadcast: Also post reply to channel
            unfurl_links: Unfurl URLs in the message
            unfurl_media: Unfurl media in the message

        Returns:
            Dict with 'success', 'ts' (message timestamp), 'channel', and any errors
        """
        logger.info(f"Sending message to {channel}: {text[:50]}...")

        try:
            # Resolve channel name to ID if needed
            channel_id = await self._resolve_channel(channel)

            response = self.bot_client.chat_postMessage(
                channel=channel_id,
                text=text,
                blocks=blocks,
                thread_ts=thread_ts,
                reply_broadcast=reply_broadcast,
                unfurl_links=unfurl_links,
                unfurl_media=unfurl_media,
            )

            return {
                "success": True,
                "ts": response["ts"],
                "channel": response["channel"],
                "message": response.get("message", {}),
            }

        except SlackApiError as e:
            logger.error(f"Slack API error sending message: {e.response['error']}")
            return {
                "success": False,
                "error": e.response["error"],
                "error_detail": str(e),
            }
        except Exception as e:
            logger.error(f"Error sending Slack message: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    async def send_dm(
        self,
        user_id: str,
        text: str,
        blocks: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Send a direct message to a user.

        Args:
            user_id: User ID (U1234567890) or email address
            text: Message text
            blocks: Block Kit blocks for rich formatting

        Returns:
            Dict with 'success', 'ts', 'channel', and any errors
        """
        logger.info(f"Sending DM to user {user_id}: {text[:50]}...")

        try:
            # Resolve user email to ID if needed
            resolved_user_id = await self._resolve_user(user_id)

            # Open a DM channel with the user
            dm_response = self.bot_client.conversations_open(users=[resolved_user_id])
            channel_id = dm_response["channel"]["id"]

            # Send the message
            response = self.bot_client.chat_postMessage(
                channel=channel_id,
                text=text,
                blocks=blocks,
            )

            return {
                "success": True,
                "ts": response["ts"],
                "channel": channel_id,
                "user_id": resolved_user_id,
            }

        except SlackApiError as e:
            logger.error(f"Slack API error sending DM: {e.response['error']}")
            return {
                "success": False,
                "error": e.response["error"],
                "error_detail": str(e),
            }
        except Exception as e:
            logger.error(f"Error sending Slack DM: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    async def update_message(
        self,
        channel: str,
        ts: str,
        text: str,
        blocks: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Update an existing message.

        Args:
            channel: Channel ID
            ts: Message timestamp
            text: New message text
            blocks: New Block Kit blocks

        Returns:
            Dict with 'success' and message details
        """
        try:
            channel_id = await self._resolve_channel(channel)

            response = self.bot_client.chat_update(
                channel=channel_id,
                ts=ts,
                text=text,
                blocks=blocks,
            )

            return {
                "success": True,
                "ts": response["ts"],
                "channel": response["channel"],
            }

        except SlackApiError as e:
            logger.error(f"Slack API error updating message: {e.response['error']}")
            return {
                "success": False,
                "error": e.response["error"],
            }

    async def delete_message(
        self,
        channel: str,
        ts: str,
    ) -> Dict[str, Any]:
        """
        Delete a message.

        Args:
            channel: Channel ID
            ts: Message timestamp

        Returns:
            Dict with 'success' and any errors
        """
        try:
            channel_id = await self._resolve_channel(channel)

            self.bot_client.chat_delete(
                channel=channel_id,
                ts=ts,
            )

            return {"success": True}

        except SlackApiError as e:
            logger.error(f"Slack API error deleting message: {e.response['error']}")
            return {
                "success": False,
                "error": e.response["error"],
            }

    # ==================== Channels ====================

    async def list_channels(
        self,
        types: str = "public_channel,private_channel",
        exclude_archived: bool = True,
        limit: int = 100,
    ) -> Dict[str, Any]:
        """
        List channels the bot has access to.

        Args:
            types: Channel types (public_channel, private_channel, mpim, im)
            exclude_archived: Exclude archived channels
            limit: Maximum number of channels to return

        Returns:
            Dict with 'success', 'channels' list, and any errors
        """
        logger.info("Listing Slack channels...")

        try:
            channels = []
            cursor = None

            while True:
                response = self.bot_client.conversations_list(
                    types=types,
                    exclude_archived=exclude_archived,
                    limit=min(limit - len(channels), 200),
                    cursor=cursor,
                )

                for channel in response["channels"]:
                    channels.append(SlackChannel(
                        id=channel["id"],
                        name=channel.get("name", ""),
                        is_private=channel.get("is_private", False),
                        is_member=channel.get("is_member", False),
                        num_members=channel.get("num_members", 0),
                        topic=channel.get("topic", {}).get("value"),
                        purpose=channel.get("purpose", {}).get("value"),
                    ))

                    # Update cache
                    if channel.get("name"):
                        self._channel_cache[channel["name"]] = channel["id"]

                # Check for pagination
                cursor = response.get("response_metadata", {}).get("next_cursor")
                if not cursor or len(channels) >= limit:
                    break

            return {
                "success": True,
                "channels": [
                    {
                        "id": c.id,
                        "name": c.name,
                        "is_private": c.is_private,
                        "is_member": c.is_member,
                        "num_members": c.num_members,
                        "topic": c.topic,
                        "purpose": c.purpose,
                    }
                    for c in channels
                ],
                "count": len(channels),
            }

        except SlackApiError as e:
            logger.error(f"Slack API error listing channels: {e.response['error']}")
            return {
                "success": False,
                "error": e.response["error"],
            }
        except Exception as e:
            logger.error(f"Error listing Slack channels: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    async def get_channel_history(
        self,
        channel: str,
        limit: int = 10,
        oldest: Optional[str] = None,
        latest: Optional[str] = None,
        inclusive: bool = True,
    ) -> Dict[str, Any]:
        """
        Get message history from a channel.

        Args:
            channel: Channel name or ID
            limit: Number of messages to return (max 100)
            oldest: Start of time range (timestamp)
            latest: End of time range (timestamp)
            inclusive: Include messages with oldest/latest timestamps

        Returns:
            Dict with 'success', 'messages' list, and any errors
        """
        logger.info(f"Getting channel history for {channel}...")

        try:
            channel_id = await self._resolve_channel(channel)

            kwargs = {
                "channel": channel_id,
                "limit": min(limit, 100),
                "inclusive": inclusive,
            }
            if oldest:
                kwargs["oldest"] = oldest
            if latest:
                kwargs["latest"] = latest

            response = self.bot_client.conversations_history(**kwargs)

            messages = []
            for msg in response["messages"]:
                messages.append({
                    "ts": msg.get("ts"),
                    "user": msg.get("user"),
                    "text": msg.get("text", ""),
                    "type": msg.get("type"),
                    "subtype": msg.get("subtype"),
                    "thread_ts": msg.get("thread_ts"),
                    "reply_count": msg.get("reply_count", 0),
                    "reactions": msg.get("reactions", []),
                    "attachments": msg.get("attachments", []),
                    "blocks": msg.get("blocks", []),
                })

            return {
                "success": True,
                "messages": messages,
                "count": len(messages),
                "has_more": response.get("has_more", False),
            }

        except SlackApiError as e:
            logger.error(f"Slack API error getting history: {e.response['error']}")
            return {
                "success": False,
                "error": e.response["error"],
            }
        except Exception as e:
            logger.error(f"Error getting Slack channel history: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    # ==================== Users ====================

    async def list_users(
        self,
        limit: int = 100,
        include_bots: bool = False,
    ) -> Dict[str, Any]:
        """
        List users in the workspace.

        Args:
            limit: Maximum number of users to return
            include_bots: Include bot users

        Returns:
            Dict with 'success', 'users' list, and any errors
        """
        logger.info("Listing Slack users...")

        try:
            users = []
            cursor = None

            while True:
                response = self.bot_client.users_list(
                    limit=min(limit - len(users), 200),
                    cursor=cursor,
                )

                for member in response["members"]:
                    # Skip bots if not requested
                    if not include_bots and member.get("is_bot", False):
                        continue

                    # Skip deleted/deactivated users
                    if member.get("deleted", False):
                        continue

                    profile = member.get("profile", {})
                    user = SlackUser(
                        id=member["id"],
                        name=member.get("name", ""),
                        real_name=profile.get("real_name", ""),
                        display_name=profile.get("display_name", ""),
                        email=profile.get("email"),
                        is_bot=member.get("is_bot", False),
                        is_admin=member.get("is_admin", False),
                    )
                    users.append(user)

                    # Update cache
                    if user.email:
                        self._user_cache[user.email] = user.id
                    if user.name:
                        self._user_cache[user.name] = user.id

                # Check for pagination
                cursor = response.get("response_metadata", {}).get("next_cursor")
                if not cursor or len(users) >= limit:
                    break

            return {
                "success": True,
                "users": [
                    {
                        "id": u.id,
                        "name": u.name,
                        "real_name": u.real_name,
                        "display_name": u.display_name,
                        "email": u.email,
                        "is_bot": u.is_bot,
                        "is_admin": u.is_admin,
                    }
                    for u in users
                ],
                "count": len(users),
            }

        except SlackApiError as e:
            logger.error(f"Slack API error listing users: {e.response['error']}")
            return {
                "success": False,
                "error": e.response["error"],
            }
        except Exception as e:
            logger.error(f"Error listing Slack users: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    async def get_user_info(self, user_id: str) -> Dict[str, Any]:
        """
        Get detailed information about a user.

        Args:
            user_id: User ID or email

        Returns:
            Dict with 'success', user details, and any errors
        """
        try:
            resolved_id = await self._resolve_user(user_id)

            response = self.bot_client.users_info(user=resolved_id)
            user = response["user"]
            profile = user.get("profile", {})

            return {
                "success": True,
                "user": {
                    "id": user["id"],
                    "name": user.get("name", ""),
                    "real_name": profile.get("real_name", ""),
                    "display_name": profile.get("display_name", ""),
                    "email": profile.get("email"),
                    "phone": profile.get("phone"),
                    "title": profile.get("title"),
                    "status_text": profile.get("status_text"),
                    "status_emoji": profile.get("status_emoji"),
                    "image_url": profile.get("image_192"),
                    "is_bot": user.get("is_bot", False),
                    "is_admin": user.get("is_admin", False),
                    "tz": user.get("tz"),
                    "tz_label": user.get("tz_label"),
                },
            }

        except SlackApiError as e:
            logger.error(f"Slack API error getting user info: {e.response['error']}")
            return {
                "success": False,
                "error": e.response["error"],
            }

    # ==================== Search ====================

    async def search_messages(
        self,
        query: str,
        count: int = 20,
        sort: str = "timestamp",
        sort_dir: str = "desc",
    ) -> Dict[str, Any]:
        """
        Search for messages in the workspace.

        Note: Requires User Token (xoxp-*) with search:read scope.

        Args:
            query: Search query (supports Slack search syntax)
            count: Number of results to return
            sort: Sort field ('timestamp' or 'score')
            sort_dir: Sort direction ('asc' or 'desc')

        Returns:
            Dict with 'success', 'messages' list, 'total', and any errors
        """
        logger.info(f"Searching Slack messages: {query}")

        try:
            response = self.user_client.search_messages(
                query=query,
                count=count,
                sort=sort,
                sort_dir=sort_dir,
            )

            messages = response.get("messages", {})
            matches = messages.get("matches", [])

            results = []
            for match in matches:
                results.append({
                    "ts": match.get("ts"),
                    "text": match.get("text", ""),
                    "user": match.get("user"),
                    "username": match.get("username"),
                    "channel": match.get("channel", {}).get("id"),
                    "channel_name": match.get("channel", {}).get("name"),
                    "permalink": match.get("permalink"),
                })

            return {
                "success": True,
                "messages": results,
                "total": messages.get("total", 0),
                "count": len(results),
            }

        except SlackApiError as e:
            logger.error(f"Slack API error searching: {e.response['error']}")
            return {
                "success": False,
                "error": e.response["error"],
            }
        except Exception as e:
            logger.error(f"Error searching Slack: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    # ==================== Reactions ====================

    async def add_reaction(
        self,
        channel: str,
        timestamp: str,
        emoji: str,
    ) -> Dict[str, Any]:
        """
        Add a reaction to a message.

        Args:
            channel: Channel containing the message
            timestamp: Message timestamp
            emoji: Emoji name (without colons, e.g., 'thumbsup')

        Returns:
            Dict with 'success' and any errors
        """
        logger.info(f"Adding reaction :{emoji}: to message {timestamp}")

        try:
            channel_id = await self._resolve_channel(channel)

            self.bot_client.reactions_add(
                channel=channel_id,
                timestamp=timestamp,
                name=emoji.strip(":"),  # Remove colons if present
            )

            return {"success": True, "emoji": emoji}

        except SlackApiError as e:
            # "already_reacted" is not really an error
            if e.response["error"] == "already_reacted":
                return {"success": True, "emoji": emoji, "note": "already_reacted"}

            logger.error(f"Slack API error adding reaction: {e.response['error']}")
            return {
                "success": False,
                "error": e.response["error"],
            }
        except Exception as e:
            logger.error(f"Error adding Slack reaction: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    async def remove_reaction(
        self,
        channel: str,
        timestamp: str,
        emoji: str,
    ) -> Dict[str, Any]:
        """
        Remove a reaction from a message.

        Args:
            channel: Channel containing the message
            timestamp: Message timestamp
            emoji: Emoji name (without colons)

        Returns:
            Dict with 'success' and any errors
        """
        try:
            channel_id = await self._resolve_channel(channel)

            self.bot_client.reactions_remove(
                channel=channel_id,
                timestamp=timestamp,
                name=emoji.strip(":"),
            )

            return {"success": True}

        except SlackApiError as e:
            logger.error(f"Slack API error removing reaction: {e.response['error']}")
            return {
                "success": False,
                "error": e.response["error"],
            }

    # ==================== Files ====================

    async def upload_file(
        self,
        channels: Union[str, List[str]],
        file_path: Optional[str] = None,
        content: Optional[str] = None,
        filename: Optional[str] = None,
        title: Optional[str] = None,
        initial_comment: Optional[str] = None,
        thread_ts: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Upload a file to Slack.

        Args:
            channels: Channel(s) to share the file in
            file_path: Path to file to upload
            content: File content (alternative to file_path)
            filename: Name for the file
            title: Title of the file
            initial_comment: Comment to add with the file
            thread_ts: Thread to upload to

        Returns:
            Dict with 'success', file details, and any errors
        """
        logger.info(f"Uploading file to Slack: {filename or file_path}")

        try:
            # Handle channel list
            if isinstance(channels, str):
                channel_ids = [await self._resolve_channel(channels)]
            else:
                channel_ids = [await self._resolve_channel(c) for c in channels]

            kwargs = {
                "channels": ",".join(channel_ids),
            }

            if file_path:
                kwargs["file"] = file_path
            elif content:
                kwargs["content"] = content
            else:
                return {
                    "success": False,
                    "error": "Either file_path or content must be provided",
                }

            if filename:
                kwargs["filename"] = filename
            if title:
                kwargs["title"] = title
            if initial_comment:
                kwargs["initial_comment"] = initial_comment
            if thread_ts:
                kwargs["thread_ts"] = thread_ts

            response = self.bot_client.files_upload_v2(**kwargs)

            file_info = response.get("file", {})
            return {
                "success": True,
                "file_id": file_info.get("id"),
                "name": file_info.get("name"),
                "title": file_info.get("title"),
                "mimetype": file_info.get("mimetype"),
                "size": file_info.get("size"),
                "permalink": file_info.get("permalink"),
            }

        except SlackApiError as e:
            logger.error(f"Slack API error uploading file: {e.response['error']}")
            return {
                "success": False,
                "error": e.response["error"],
            }
        except Exception as e:
            logger.error(f"Error uploading file to Slack: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    # ==================== Helpers ====================

    async def _resolve_channel(self, channel: str) -> str:
        """
        Resolve channel name to ID.

        Args:
            channel: Channel name (#general) or ID (C1234567890)

        Returns:
            Channel ID
        """
        # Already an ID
        if channel.startswith("C") or channel.startswith("D") or channel.startswith("G"):
            return channel

        # Remove # prefix if present
        channel_name = channel.lstrip("#")

        # Check cache
        if channel_name in self._channel_cache:
            return self._channel_cache[channel_name]

        # Lookup channel
        try:
            response = self.bot_client.conversations_list(types="public_channel,private_channel")
            for ch in response["channels"]:
                if ch.get("name") == channel_name:
                    self._channel_cache[channel_name] = ch["id"]
                    return ch["id"]
        except SlackApiError:
            pass

        # Return as-is if not found (might be a valid ID format we don't recognize)
        return channel

    async def _resolve_user(self, user: str) -> str:
        """
        Resolve user identifier to ID.

        Args:
            user: User ID (U1234567890), name, or email

        Returns:
            User ID
        """
        # Already an ID
        if user.startswith("U") or user.startswith("W"):
            return user

        # Check cache
        if user in self._user_cache:
            return self._user_cache[user]

        # Try email lookup
        if "@" in user:
            try:
                response = self.bot_client.users_lookupByEmail(email=user)
                user_id = response["user"]["id"]
                self._user_cache[user] = user_id
                return user_id
            except SlackApiError:
                pass

        # Return as-is
        return user


# Singleton instance
_slack_client: Optional[SlackClient] = None


def get_slack_client() -> SlackClient:
    """Get or create the singleton Slack client."""
    global _slack_client
    if _slack_client is None:
        _slack_client = SlackClient()
    return _slack_client
