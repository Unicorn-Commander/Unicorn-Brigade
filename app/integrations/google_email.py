"""
Google Workspace Email Integration

Provides email functionality via Gmail API using Google API Python Client.
Supports both OAuth2 (user credentials) and Service Account authentication.

Environment Variables:
    OAuth2 Flow:
        - GOOGLE_CLIENT_ID: OAuth2 client ID
        - GOOGLE_CLIENT_SECRET: OAuth2 client secret
        - GOOGLE_REFRESH_TOKEN: OAuth2 refresh token
        - GOOGLE_USER_EMAIL: Email address of the user

    Service Account Flow:
        - GOOGLE_SERVICE_ACCOUNT_FILE: Path to service account JSON file
        - GOOGLE_DELEGATED_USER: User email to impersonate (domain-wide delegation)
"""

import base64
import json
import logging
import os
import time
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Google API scopes for Gmail
GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
]

# Environment variables
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REFRESH_TOKEN = os.getenv("GOOGLE_REFRESH_TOKEN", "")
GOOGLE_USER_EMAIL = os.getenv("GOOGLE_USER_EMAIL", "")

# Service account configuration
GOOGLE_SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "")
GOOGLE_DELEGATED_USER = os.getenv("GOOGLE_DELEGATED_USER", "")

# Token cache for OAuth2 flow
_token_cache: Dict[str, Any] = {"access_token": None, "expires_at": 0}


class GoogleEmailClient:
    """
    Google Workspace Email client supporting OAuth2 and Service Account authentication.

    Provides methods for:
    - Sending emails (with optional HTML and attachments)
    - Retrieving individual emails
    - Listing emails with filtering
    - Searching emails with Gmail query syntax
    """

    def __init__(self):
        """Initialize the Google Email client."""
        self._credentials = None
        self._service = None
        self._user_email = GOOGLE_USER_EMAIL or GOOGLE_DELEGATED_USER

    def _get_oauth2_credentials(self):
        """
        Get OAuth2 credentials using refresh token.

        Uses client credentials and refresh token to obtain access tokens.
        Tokens are cached and refreshed automatically when expired.
        """
        global _token_cache

        # Return cached token if still valid (with 60s buffer)
        if _token_cache["access_token"] and _token_cache["expires_at"] > time.time() + 60:
            from google.oauth2.credentials import Credentials
            return Credentials(
                token=_token_cache["access_token"],
                refresh_token=GOOGLE_REFRESH_TOKEN,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=GOOGLE_CLIENT_ID,
                client_secret=GOOGLE_CLIENT_SECRET,
                scopes=GMAIL_SCOPES,
            )

        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request

        creds = Credentials(
            token=None,
            refresh_token=GOOGLE_REFRESH_TOKEN,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=GOOGLE_CLIENT_ID,
            client_secret=GOOGLE_CLIENT_SECRET,
            scopes=GMAIL_SCOPES,
        )

        # Refresh the token
        creds.refresh(Request())

        # Cache the new token
        _token_cache["access_token"] = creds.token
        _token_cache["expires_at"] = time.time() + 3500  # ~1 hour

        logger.info("Google OAuth2 token refreshed successfully")
        return creds

    def _get_service_account_credentials(self):
        """
        Get credentials using service account with domain-wide delegation.

        Requires a service account JSON file and the user email to impersonate.
        The service account must have domain-wide delegation enabled in Google Admin.
        """
        from google.oauth2 import service_account

        credentials = service_account.Credentials.from_service_account_file(
            GOOGLE_SERVICE_ACCOUNT_FILE,
            scopes=GMAIL_SCOPES,
        )

        # Delegate to the specified user
        if GOOGLE_DELEGATED_USER:
            credentials = credentials.with_subject(GOOGLE_DELEGATED_USER)

        logger.info(f"Service account credentials loaded, delegating to: {GOOGLE_DELEGATED_USER}")
        return credentials

    def _get_credentials(self):
        """Get the appropriate credentials based on configuration."""
        if self._credentials:
            return self._credentials

        # Prefer service account if configured
        if GOOGLE_SERVICE_ACCOUNT_FILE and os.path.exists(GOOGLE_SERVICE_ACCOUNT_FILE):
            self._credentials = self._get_service_account_credentials()
        elif GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET and GOOGLE_REFRESH_TOKEN:
            self._credentials = self._get_oauth2_credentials()
        else:
            raise ValueError(
                "Google credentials not configured. "
                "Set either GOOGLE_SERVICE_ACCOUNT_FILE or "
                "GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, and GOOGLE_REFRESH_TOKEN"
            )

        return self._credentials

    def _get_service(self):
        """Get or create the Gmail API service."""
        if self._service:
            return self._service

        from googleapiclient.discovery import build

        credentials = self._get_credentials()
        self._service = build("gmail", "v1", credentials=credentials)

        return self._service

    def _create_message(
        self,
        to: str,
        subject: str,
        body: str,
        cc: Optional[str] = None,
        bcc: Optional[str] = None,
        html: bool = False,
        attachments: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, str]:
        """
        Create an email message in the format required by Gmail API.

        Args:
            to: Recipient email address(es), comma-separated for multiple
            subject: Email subject line
            body: Email body content
            cc: CC recipient(s), comma-separated for multiple
            bcc: BCC recipient(s), comma-separated for multiple
            html: If True, body is treated as HTML
            attachments: List of attachment dicts with 'filename', 'content' (base64), 'mime_type'

        Returns:
            Dict with 'raw' key containing base64-encoded message
        """
        if attachments:
            message = MIMEMultipart()
            message.attach(MIMEText(body, "html" if html else "plain"))

            for attachment in attachments:
                part = MIMEBase("application", "octet-stream")
                content = attachment.get("content", "")
                if isinstance(content, str):
                    content = base64.b64decode(content)
                part.set_payload(content)

                from email import encoders
                encoders.encode_base64(part)

                filename = attachment.get("filename", "attachment")
                part.add_header(
                    "Content-Disposition",
                    f'attachment; filename="{filename}"',
                )
                message.attach(part)
        else:
            message = MIMEText(body, "html" if html else "plain")

        message["to"] = to
        message["subject"] = subject
        message["from"] = self._user_email

        if cc:
            message["cc"] = cc
        if bcc:
            message["bcc"] = bcc

        # Encode the message
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
        return {"raw": raw}

    async def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        cc: Optional[str] = None,
        bcc: Optional[str] = None,
        html: bool = False,
        attachments: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Send an email via Gmail API.

        Args:
            to: Recipient email address(es)
            subject: Email subject line
            body: Email body content
            cc: CC recipient(s)
            bcc: BCC recipient(s)
            html: If True, body is treated as HTML
            attachments: List of attachment dicts

        Returns:
            Dict with message_id, thread_id, and success status
        """
        try:
            service = self._get_service()
            message = self._create_message(to, subject, body, cc, bcc, html, attachments)

            # Gmail API uses 'me' as the userId to represent the authenticated user
            result = service.users().messages().send(
                userId="me",
                body=message
            ).execute()

            logger.info(f"Email sent successfully: {result.get('id')}")
            return {
                "success": True,
                "message_id": result.get("id"),
                "thread_id": result.get("threadId"),
                "provider": "google",
                "from": self._user_email,
                "to": to,
            }
        except Exception as e:
            logger.error(f"Failed to send email via Gmail: {e}")
            return {
                "success": False,
                "error": str(e),
                "provider": "google",
            }

    async def get_email(self, message_id: str, format: str = "full") -> Dict[str, Any]:
        """
        Retrieve a specific email by message ID.

        Args:
            message_id: The Gmail message ID
            format: Response format - 'full', 'metadata', 'minimal', or 'raw'

        Returns:
            Dict containing the email data or error
        """
        try:
            service = self._get_service()
            message = service.users().messages().get(
                userId="me",
                id=message_id,
                format=format
            ).execute()

            # Parse the message for easier consumption
            parsed = self._parse_message(message)
            return {
                "success": True,
                "message": parsed,
                "raw": message,
            }
        except Exception as e:
            logger.error(f"Failed to get email {message_id}: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    async def list_emails(
        self,
        query: Optional[str] = None,
        max_results: int = 10,
        label_ids: Optional[List[str]] = None,
        include_spam_trash: bool = False,
    ) -> Dict[str, Any]:
        """
        List emails with optional filtering.

        Args:
            query: Gmail search query (e.g., "from:user@example.com is:unread")
            max_results: Maximum number of messages to return
            label_ids: List of label IDs to filter by (e.g., ['INBOX', 'UNREAD'])
            include_spam_trash: Include spam and trash messages

        Returns:
            Dict containing list of emails or error
        """
        try:
            service = self._get_service()

            # Build the request
            request_params = {
                "userId": "me",
                "maxResults": max_results,
                "includeSpamTrash": include_spam_trash,
            }

            if query:
                request_params["q"] = query
            if label_ids:
                request_params["labelIds"] = label_ids

            results = service.users().messages().list(**request_params).execute()

            messages = results.get("messages", [])

            # Fetch details for each message
            detailed_messages = []
            for msg in messages:
                msg_detail = service.users().messages().get(
                    userId="me",
                    id=msg["id"],
                    format="metadata",
                    metadataHeaders=["From", "To", "Subject", "Date"],
                ).execute()
                detailed_messages.append(self._parse_message(msg_detail))

            return {
                "success": True,
                "messages": detailed_messages,
                "count": len(detailed_messages),
                "next_page_token": results.get("nextPageToken"),
            }
        except Exception as e:
            logger.error(f"Failed to list emails: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    async def search_emails(
        self,
        query: str,
        max_results: int = 10,
    ) -> Dict[str, Any]:
        """
        Search emails using Gmail query syntax.

        Args:
            query: Gmail search query string
                   Examples:
                   - "from:user@example.com"
                   - "subject:invoice"
                   - "is:unread"
                   - "after:2024/01/01 before:2024/12/31"
                   - "has:attachment"
            max_results: Maximum number of results to return

        Returns:
            Dict containing search results or error
        """
        return await self.list_emails(query=query, max_results=max_results)

    def _parse_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse a Gmail message into a more usable format.

        Args:
            message: Raw Gmail API message response

        Returns:
            Parsed message dict with common fields extracted
        """
        headers = {}
        payload = message.get("payload", {})

        # Extract headers
        for header in payload.get("headers", []):
            name = header.get("name", "").lower()
            value = header.get("value", "")
            headers[name] = value

        # Extract body
        body = ""
        parts = payload.get("parts", [])

        if parts:
            for part in parts:
                if part.get("mimeType") == "text/plain":
                    data = part.get("body", {}).get("data", "")
                    if data:
                        body = base64.urlsafe_b64decode(data).decode("utf-8")
                        break
                elif part.get("mimeType") == "text/html" and not body:
                    data = part.get("body", {}).get("data", "")
                    if data:
                        body = base64.urlsafe_b64decode(data).decode("utf-8")
        else:
            # Single part message
            data = payload.get("body", {}).get("data", "")
            if data:
                body = base64.urlsafe_b64decode(data).decode("utf-8")

        return {
            "id": message.get("id"),
            "thread_id": message.get("threadId"),
            "snippet": message.get("snippet", ""),
            "from": headers.get("from", ""),
            "to": headers.get("to", ""),
            "subject": headers.get("subject", ""),
            "date": headers.get("date", ""),
            "labels": message.get("labelIds", []),
            "body": body[:1000] if body else "",  # Truncate for API response
            "has_attachments": any(
                part.get("filename") for part in parts
            ) if parts else False,
        }


# Module-level singleton instance
_client: Optional[GoogleEmailClient] = None


def get_client() -> GoogleEmailClient:
    """Get or create the singleton GoogleEmailClient instance."""
    global _client
    if _client is None:
        _client = GoogleEmailClient()
    return _client


# Convenience functions for direct use
async def send_email(
    to: str,
    subject: str,
    body: str,
    cc: Optional[str] = None,
    bcc: Optional[str] = None,
    html: bool = False,
    attachments: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Send an email via Google Workspace."""
    return await get_client().send_email(to, subject, body, cc, bcc, html, attachments)


async def get_email(message_id: str, format: str = "full") -> Dict[str, Any]:
    """Get a specific email by message ID."""
    return await get_client().get_email(message_id, format)


async def list_emails(
    query: Optional[str] = None,
    max_results: int = 10,
    label_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """List emails with optional filtering."""
    return await get_client().list_emails(query, max_results, label_ids)


async def search_emails(query: str, max_results: int = 10) -> Dict[str, Any]:
    """Search emails using Gmail query syntax."""
    return await get_client().search_emails(query, max_results)
