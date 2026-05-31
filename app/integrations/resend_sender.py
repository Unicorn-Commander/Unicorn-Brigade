"""Small Resend sender for Maj. Recon digest emails."""

from __future__ import annotations

import logging
import os
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


class ResendSender:
    def __init__(self):
        self.api_key = os.getenv("RESEND_API_KEY")
        self.from_addr = os.getenv("MAJIKS_DIGEST_FROM", "no-reply@magicunicorn.tech")

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    async def send(
        self,
        to: str,
        subject: str,
        html: str,
        *,
        reply_to: Optional[str] = None,
    ) -> dict:
        if not self.is_configured:
            logger.warning("Maj. Recon digest email skipped: RESEND_API_KEY not set")
            return {"sent": False, "skipped": "RESEND_API_KEY not set"}

        payload = {
            "from": self.from_addr,
            "to": [addr.strip() for addr in to.split(",") if addr.strip()],
            "subject": subject,
            "html": html,
        }
        if reply_to:
            payload["reply_to"] = reply_to

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            logger.info(
                "Maj. Recon digest email sent via Resend id=%s to=%s",
                data.get("id"),
                payload["to"],
            )
            return {"sent": True, "id": data.get("id")}
