"""Small Postmark sender for Maj. Recon digest emails.

Uses Postmark's HTTPS API (api.postmarkapp.com) so the digest doesn't need to
go through Stalwart SMTP relay. The Server Token lives in Vaultwarden under
"Postmark Server Token — Stalwart Relay" and is provisioned to bigboy as the
``POSTMARK_SERVER_TOKEN`` env var.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


class PostmarkSender:
    """Minimal Postmark transactional-email client.

    Drop-in replacement for the previous ResendSender. Same ``send`` shape so
    existing call-sites only need an import + class swap.
    """

    POSTMARK_API_URL = "https://api.postmarkapp.com/email"

    def __init__(self) -> None:
        self.api_token = os.getenv("POSTMARK_SERVER_TOKEN")
        self.from_addr = os.getenv("MAJIKS_DIGEST_FROM", "no-reply@magicunicorn.tech")
        self.message_stream = os.getenv("POSTMARK_MESSAGE_STREAM", "outbound")

    @property
    def is_configured(self) -> bool:
        return bool(self.api_token)

    async def send(
        self,
        to: str,
        subject: str,
        html: str,
        *,
        reply_to: Optional[str] = None,
        text_body: Optional[str] = None,
    ) -> dict:
        if not self.is_configured:
            logger.warning(
                "Maj. Recon digest email skipped: POSTMARK_SERVER_TOKEN not set"
            )
            return {"sent": False, "skipped": "POSTMARK_SERVER_TOKEN not set"}

        recipients = [addr.strip() for addr in to.split(",") if addr.strip()]
        payload: dict = {
            "From": self.from_addr,
            "To": ", ".join(recipients),
            "Subject": subject,
            "HtmlBody": html,
            "MessageStream": self.message_stream,
        }
        if text_body:
            payload["TextBody"] = text_body
        if reply_to:
            payload["ReplyTo"] = reply_to

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                self.POSTMARK_API_URL,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "X-Postmark-Server-Token": self.api_token,
                },
                json=payload,
            )
            try:
                resp.raise_for_status()
            except httpx.HTTPStatusError:
                logger.error(
                    "Postmark send failed status=%s body=%s",
                    resp.status_code,
                    resp.text[:500],
                )
                raise
            data = resp.json()
            logger.info(
                "Maj. Recon digest email sent via Postmark id=%s message_id=%s to=%s",
                data.get("MessageID"),
                data.get("MessageID"),
                recipients,
            )
            return {
                "sent": True,
                "id": data.get("MessageID"),
                "submitted_at": data.get("SubmittedAt"),
            }
