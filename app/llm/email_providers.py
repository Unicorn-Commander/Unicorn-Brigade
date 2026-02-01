"""
Email Provider Abstraction Layer

Provides a unified interface for email operations across different providers:
- Microsoft 365 (Graph API)
- Google Workspace (Gmail API)
- Resend
- SendGrid

The active provider is determined by the EMAIL_PROVIDER environment variable.
"""

import logging
import os
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class EmailProvider(ABC):
    """Abstract base class for email providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the provider name."""
        pass

    @abstractmethod
    async def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        from_email: Optional[str] = None,
        cc: Optional[str] = None,
        bcc: Optional[str] = None,
        html: bool = False,
        attachments: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Send an email."""
        pass

    @abstractmethod
    async def get_email(self, message_id: str) -> Dict[str, Any]:
        """Get a specific email by ID."""
        pass

    @abstractmethod
    async def list_emails(
        self,
        query: Optional[str] = None,
        max_results: int = 10,
    ) -> Dict[str, Any]:
        """List emails with optional filtering."""
        pass

    @abstractmethod
    async def search_emails(
        self,
        query: str,
        max_results: int = 10,
    ) -> Dict[str, Any]:
        """Search emails."""
        pass

    @abstractmethod
    def is_configured(self) -> bool:
        """Check if the provider is properly configured."""
        pass


class MS365EmailProvider(EmailProvider):
    """
    Microsoft 365 Email Provider using Graph API.

    Uses OAuth2 Client Credentials flow for server-to-server authentication.
    """

    def __init__(self):
        self.client_id = os.getenv("MS365_CLIENT_ID", "")
        self.tenant_id = os.getenv("MS365_TENANT_ID", "")
        self.client_secret = os.getenv("MS365_CLIENT_SECRET", "")
        self.user_email = os.getenv("MS365_USER_EMAIL", "")
        self._token_cache: Dict[str, Any] = {"token": None, "expires_at": 0}

    @property
    def name(self) -> str:
        return "ms365"

    def is_configured(self) -> bool:
        return bool(
            self.client_id and self.tenant_id and self.client_secret and self.user_email
        )

    async def _get_token(self) -> str:
        """Get Microsoft Graph API access token using client credentials."""
        # Return cached token if still valid
        if self._token_cache["token"] and self._token_cache["expires_at"] > time.time() + 60:
            return self._token_cache["token"]

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token",
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "scope": "https://graph.microsoft.com/.default",
                    "grant_type": "client_credentials",
                },
            )
            response.raise_for_status()
            data = response.json()

            self._token_cache["token"] = data["access_token"]
            self._token_cache["expires_at"] = time.time() + data.get("expires_in", 3600)

            logger.info("MS365 token refreshed successfully")
            return data["access_token"]

    async def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        from_email: Optional[str] = None,
        cc: Optional[str] = None,
        bcc: Optional[str] = None,
        html: bool = False,
        attachments: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Send email via Microsoft Graph API."""
        try:
            token = await self._get_token()
            sender = from_email or self.user_email

            # Build message
            message = {
                "message": {
                    "subject": subject,
                    "body": {
                        "contentType": "HTML" if html else "Text",
                        "content": body,
                    },
                    "toRecipients": [
                        {"emailAddress": {"address": addr.strip()}}
                        for addr in to.split(",")
                    ],
                },
                "saveToSentItems": "true",
            }

            # Add CC recipients
            if cc:
                message["message"]["ccRecipients"] = [
                    {"emailAddress": {"address": addr.strip()}}
                    for addr in cc.split(",")
                ]

            # Add BCC recipients
            if bcc:
                message["message"]["bccRecipients"] = [
                    {"emailAddress": {"address": addr.strip()}}
                    for addr in bcc.split(",")
                ]

            # Add attachments
            if attachments:
                message["message"]["attachments"] = []
                for att in attachments:
                    message["message"]["attachments"].append({
                        "@odata.type": "#microsoft.graph.fileAttachment",
                        "name": att.get("filename", "attachment"),
                        "contentType": att.get("mime_type", "application/octet-stream"),
                        "contentBytes": att.get("content", ""),
                    })

            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    f"https://graph.microsoft.com/v1.0/users/{sender}/sendMail",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json",
                    },
                    json=message,
                )

                if response.status_code == 202:
                    logger.info(f"Email sent via MS365 to {to}")
                    return {
                        "success": True,
                        "provider": self.name,
                        "from": sender,
                        "to": to,
                    }
                return {
                    "success": False,
                    "error": response.text,
                    "status_code": response.status_code,
                    "provider": self.name,
                }
        except Exception as e:
            logger.error(f"MS365 email error: {e}")
            return {"success": False, "error": str(e), "provider": self.name}

    async def get_email(self, message_id: str) -> Dict[str, Any]:
        """Get a specific email by ID from MS365."""
        try:
            token = await self._get_token()

            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(
                    f"https://graph.microsoft.com/v1.0/users/{self.user_email}/messages/{message_id}",
                    headers={"Authorization": f"Bearer {token}"},
                )

                if response.status_code == 200:
                    msg = response.json()
                    return {
                        "success": True,
                        "message": {
                            "id": msg.get("id"),
                            "subject": msg.get("subject"),
                            "from": msg.get("from", {}).get("emailAddress", {}).get("address"),
                            "to": [
                                r.get("emailAddress", {}).get("address")
                                for r in msg.get("toRecipients", [])
                            ],
                            "body": msg.get("body", {}).get("content", ""),
                            "date": msg.get("receivedDateTime"),
                            "has_attachments": msg.get("hasAttachments", False),
                        },
                        "provider": self.name,
                    }
                return {
                    "success": False,
                    "error": response.text,
                    "provider": self.name,
                }
        except Exception as e:
            logger.error(f"MS365 get_email error: {e}")
            return {"success": False, "error": str(e), "provider": self.name}

    async def list_emails(
        self,
        query: Optional[str] = None,
        max_results: int = 10,
    ) -> Dict[str, Any]:
        """List emails from MS365."""
        try:
            token = await self._get_token()

            url = f"https://graph.microsoft.com/v1.0/users/{self.user_email}/messages"
            params = {"$top": max_results, "$orderby": "receivedDateTime desc"}

            if query:
                # MS365 uses OData $filter or $search
                params["$search"] = f'"{query}"'

            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(
                    url,
                    headers={"Authorization": f"Bearer {token}"},
                    params=params,
                )

                if response.status_code == 200:
                    data = response.json()
                    messages = [
                        {
                            "id": msg.get("id"),
                            "subject": msg.get("subject"),
                            "from": msg.get("from", {}).get("emailAddress", {}).get("address"),
                            "date": msg.get("receivedDateTime"),
                            "snippet": msg.get("bodyPreview", "")[:200],
                            "has_attachments": msg.get("hasAttachments", False),
                        }
                        for msg in data.get("value", [])
                    ]
                    return {
                        "success": True,
                        "messages": messages,
                        "count": len(messages),
                        "provider": self.name,
                    }
                return {
                    "success": False,
                    "error": response.text,
                    "provider": self.name,
                }
        except Exception as e:
            logger.error(f"MS365 list_emails error: {e}")
            return {"success": False, "error": str(e), "provider": self.name}

    async def search_emails(
        self,
        query: str,
        max_results: int = 10,
    ) -> Dict[str, Any]:
        """Search emails in MS365."""
        return await self.list_emails(query=query, max_results=max_results)


class GoogleEmailProvider(EmailProvider):
    """
    Google Workspace Email Provider using Gmail API.

    Supports both OAuth2 and Service Account authentication.
    """

    def __init__(self):
        from app.integrations.google_email import GoogleEmailClient

        self._client = GoogleEmailClient()
        self.user_email = os.getenv("GOOGLE_USER_EMAIL", "") or os.getenv("GOOGLE_DELEGATED_USER", "")

    @property
    def name(self) -> str:
        return "google"

    def is_configured(self) -> bool:
        # Check OAuth2 credentials
        oauth2_configured = bool(
            os.getenv("GOOGLE_CLIENT_ID")
            and os.getenv("GOOGLE_CLIENT_SECRET")
            and os.getenv("GOOGLE_REFRESH_TOKEN")
        )

        # Check service account credentials
        service_account_file = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "")
        service_account_configured = bool(
            service_account_file and os.path.exists(service_account_file)
        )

        return oauth2_configured or service_account_configured

    async def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        from_email: Optional[str] = None,
        cc: Optional[str] = None,
        bcc: Optional[str] = None,
        html: bool = False,
        attachments: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Send email via Gmail API."""
        return await self._client.send_email(
            to=to,
            subject=subject,
            body=body,
            cc=cc,
            bcc=bcc,
            html=html,
            attachments=attachments,
        )

    async def get_email(self, message_id: str) -> Dict[str, Any]:
        """Get a specific email from Gmail."""
        return await self._client.get_email(message_id)

    async def list_emails(
        self,
        query: Optional[str] = None,
        max_results: int = 10,
    ) -> Dict[str, Any]:
        """List emails from Gmail."""
        return await self._client.list_emails(query=query, max_results=max_results)

    async def search_emails(
        self,
        query: str,
        max_results: int = 10,
    ) -> Dict[str, Any]:
        """Search emails in Gmail."""
        return await self._client.search_emails(query=query, max_results=max_results)


class ResendEmailProvider(EmailProvider):
    """Resend email provider (send-only)."""

    def __init__(self):
        self.api_key = os.getenv("RESEND_API_KEY", "")
        self.default_from = os.getenv("RESEND_FROM_EMAIL", "noreply@unicorncommander.ai")

    @property
    def name(self) -> str:
        return "resend"

    def is_configured(self) -> bool:
        return bool(self.api_key)

    async def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        from_email: Optional[str] = None,
        cc: Optional[str] = None,
        bcc: Optional[str] = None,
        html: bool = False,
        attachments: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Send email via Resend API."""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                payload = {
                    "from": from_email or self.default_from,
                    "to": [addr.strip() for addr in to.split(",")],
                    "subject": subject,
                }

                if html:
                    payload["html"] = body
                else:
                    payload["text"] = body

                if cc:
                    payload["cc"] = [addr.strip() for addr in cc.split(",")]
                if bcc:
                    payload["bcc"] = [addr.strip() for addr in bcc.split(",")]

                if attachments:
                    payload["attachments"] = [
                        {
                            "filename": att.get("filename", "attachment"),
                            "content": att.get("content", ""),
                        }
                        for att in attachments
                    ]

                response = await client.post(
                    "https://api.resend.com/emails",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )

                if response.status_code == 200:
                    data = response.json()
                    return {
                        "success": True,
                        "message_id": data.get("id"),
                        "provider": self.name,
                    }
                return {
                    "success": False,
                    "error": response.text,
                    "provider": self.name,
                }
        except Exception as e:
            logger.error(f"Resend email error: {e}")
            return {"success": False, "error": str(e), "provider": self.name}

    async def get_email(self, message_id: str) -> Dict[str, Any]:
        """Resend doesn't support email retrieval."""
        return {
            "success": False,
            "error": "Resend provider does not support email retrieval",
            "provider": self.name,
        }

    async def list_emails(
        self,
        query: Optional[str] = None,
        max_results: int = 10,
    ) -> Dict[str, Any]:
        """Resend doesn't support email listing."""
        return {
            "success": False,
            "error": "Resend provider does not support email listing",
            "provider": self.name,
        }

    async def search_emails(
        self,
        query: str,
        max_results: int = 10,
    ) -> Dict[str, Any]:
        """Resend doesn't support email search."""
        return {
            "success": False,
            "error": "Resend provider does not support email search",
            "provider": self.name,
        }


class SendGridEmailProvider(EmailProvider):
    """SendGrid email provider (send-only)."""

    def __init__(self):
        self.api_key = os.getenv("SENDGRID_API_KEY", "")
        self.default_from = os.getenv("SENDGRID_FROM_EMAIL", "noreply@unicorncommander.ai")

    @property
    def name(self) -> str:
        return "sendgrid"

    def is_configured(self) -> bool:
        return bool(self.api_key)

    async def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        from_email: Optional[str] = None,
        cc: Optional[str] = None,
        bcc: Optional[str] = None,
        html: bool = False,
        attachments: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Send email via SendGrid API."""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                personalizations = {
                    "to": [{"email": addr.strip()} for addr in to.split(",")]
                }

                if cc:
                    personalizations["cc"] = [{"email": addr.strip()} for addr in cc.split(",")]
                if bcc:
                    personalizations["bcc"] = [{"email": addr.strip()} for addr in bcc.split(",")]

                payload = {
                    "personalizations": [personalizations],
                    "from": {"email": from_email or self.default_from},
                    "subject": subject,
                    "content": [
                        {
                            "type": "text/html" if html else "text/plain",
                            "value": body,
                        }
                    ],
                }

                if attachments:
                    payload["attachments"] = [
                        {
                            "filename": att.get("filename", "attachment"),
                            "content": att.get("content", ""),
                            "type": att.get("mime_type", "application/octet-stream"),
                        }
                        for att in attachments
                    ]

                response = await client.post(
                    "https://api.sendgrid.com/v3/mail/send",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )

                if response.status_code in [200, 202]:
                    return {
                        "success": True,
                        "provider": self.name,
                    }
                return {
                    "success": False,
                    "error": response.text,
                    "provider": self.name,
                }
        except Exception as e:
            logger.error(f"SendGrid email error: {e}")
            return {"success": False, "error": str(e), "provider": self.name}

    async def get_email(self, message_id: str) -> Dict[str, Any]:
        """SendGrid doesn't support email retrieval."""
        return {
            "success": False,
            "error": "SendGrid provider does not support email retrieval",
            "provider": self.name,
        }

    async def list_emails(
        self,
        query: Optional[str] = None,
        max_results: int = 10,
    ) -> Dict[str, Any]:
        """SendGrid doesn't support email listing."""
        return {
            "success": False,
            "error": "SendGrid provider does not support email listing",
            "provider": self.name,
        }

    async def search_emails(
        self,
        query: str,
        max_results: int = 10,
    ) -> Dict[str, Any]:
        """SendGrid doesn't support email search."""
        return {
            "success": False,
            "error": "SendGrid provider does not support email search",
            "provider": self.name,
        }


# Provider registry
_PROVIDERS: Dict[str, type] = {
    "ms365": MS365EmailProvider,
    "google": GoogleEmailProvider,
    "resend": ResendEmailProvider,
    "sendgrid": SendGridEmailProvider,
}

# Cached provider instance
_provider_instance: Optional[EmailProvider] = None


def get_email_provider(provider_name: Optional[str] = None) -> EmailProvider:
    """
    Get the configured email provider.

    Args:
        provider_name: Override the default provider (from EMAIL_PROVIDER env var)

    Returns:
        An EmailProvider instance

    Raises:
        ValueError: If the provider is not supported or not configured
    """
    global _provider_instance

    name = provider_name or os.getenv("EMAIL_PROVIDER", "ms365")

    # Return cached instance if name matches
    if _provider_instance and _provider_instance.name == name:
        return _provider_instance

    # Get provider class
    provider_class = _PROVIDERS.get(name)
    if not provider_class:
        raise ValueError(
            f"Unknown email provider: {name}. "
            f"Supported providers: {', '.join(_PROVIDERS.keys())}"
        )

    # Create and cache instance
    _provider_instance = provider_class()

    if not _provider_instance.is_configured():
        logger.warning(f"Email provider '{name}' is not fully configured")

    return _provider_instance


def get_available_providers() -> List[str]:
    """Get list of available email providers."""
    return list(_PROVIDERS.keys())


def is_provider_configured(provider_name: str) -> bool:
    """Check if a specific provider is configured."""
    provider_class = _PROVIDERS.get(provider_name)
    if not provider_class:
        return False
    return provider_class().is_configured()
