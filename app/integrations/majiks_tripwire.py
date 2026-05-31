"""
Majiks Research Monitor — tripwire alert dispatcher.

Called from the `emit-artifacts` step of the `majiks-research-monitor` workflow
when Maj. Recon confirms one or more tripwires have fired. Also callable
directly (scripts/test_tripwires.py) so the channel wiring can be verified
without running a full workflow.

Tripwire rules (encoded in Maj. Recon's orchestrator_prompt + each Captain's
system_prompt — this module only dispatches what the agent nominates):

  - Cpt. Court: any new RIAA-case docket entry
  - Cpt. Cap:   any AI-music funding round announcement >$10M
  - Cpt. Stack: any new ACE-Step / Suno / Udio version release
  - Cpt. Lab:   any new academic paper matching kids+music or music+therapy
  - Any Captain: any cited stat moving >25% in headline-stats.md

Channels (graceful no-op if either is unconfigured):
  - Slack incoming webhook (env: MAJIKS_TRIPWIRE_SLACK_WEBHOOK)
  - Email via Brigade's auto-selected EmailProvider (env: MAJIKS_TRIPWIRE_EMAIL_TO,
    comma-separated). Falls back to aaron@magicunicorn.tech.

Tripwires are also written to logger.warning() unconditionally, so even if both
channels are unconfigured the alert is preserved in Brigade's logs.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterable, Optional

import httpx

logger = logging.getLogger(__name__)

DEFAULT_EMAIL_RECIPIENT = "aaron@magicunicorn.tech"
SLACK_WEBHOOK_TIMEOUT = 10.0
MAJIKS_GRAPH_NAME = os.getenv("MAJIKS_RESEARCH_GRAPH", "majiks_research")


@dataclass
class Tripwire:
    """One material-change alert nominated by a Captain and confirmed by Maj. Recon."""
    rule: str                    # e.g. "riaa_docket_entry"
    domain: str                  # cap | court | stack | lab
    headline: str                # one-line summary
    detail: str = ""             # 1-paragraph context
    source_url: str = ""         # primary source link
    source_n: str = ""           # bibliography ref (e.g. "327")
    deck_impact: str = ""        # suggested deck-slide impact
    severity: str = "material"   # cosmetic | material | tripwire
    fired_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")

    @classmethod
    def from_dict(cls, d: dict) -> "Tripwire":
        return cls(
            rule=d.get("rule", "unknown"),
            domain=d.get("domain", "unknown"),
            headline=d.get("headline", ""),
            detail=d.get("detail", ""),
            source_url=d.get("source_url", ""),
            source_n=d.get("source_n", ""),
            deck_impact=d.get("deck_impact", ""),
            severity=d.get("severity", "material"),
            fired_at=d.get("fired_at") or datetime.utcnow().isoformat() + "Z",
        )


def _slack_blocks_for(tripwires: list[Tripwire], run_id: str) -> dict:
    """Build the Slack incoming-webhook payload (blocks API)."""
    header = {
        "type": "header",
        "text": {"type": "plain_text", "text": f"Maj. Recon — {len(tripwires)} tripwire(s) fired"},
    }
    context = {
        "type": "context",
        "elements": [
            {"type": "mrkdwn",
             "text": f"run_id `{run_id}` · {datetime.utcnow().date().isoformat()} UTC"}
        ],
    }
    blocks: list[dict] = [header, context, {"type": "divider"}]

    for tw in tripwires:
        body = f"*{tw.headline}*"
        if tw.detail:
            body += f"\n{tw.detail}"
        if tw.source_url or tw.source_n:
            ref = []
            if tw.source_url:
                ref.append(f"<{tw.source_url}|source>")
            if tw.source_n:
                ref.append(f"`source-{tw.source_n}`")
            body += f"\n{' · '.join(ref)}"
        if tw.deck_impact:
            body += f"\n_Deck impact:_ {tw.deck_impact}"
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": body},
        })
        blocks.append({
            "type": "context",
            "elements": [
                {"type": "mrkdwn",
                 "text": f"Captain `{tw.domain}` · rule `{tw.rule}` · severity `{tw.severity}`"}
            ],
        })

    return {"text": f"Maj. Recon: {len(tripwires)} tripwire(s) fired", "blocks": blocks}


def _email_body_for(tripwires: list[Tripwire], run_id: str) -> tuple[str, str]:
    """Return (subject, plain-text body) for the email alert."""
    subject = f"[Maj. Recon] {len(tripwires)} tripwire{'s' if len(tripwires) != 1 else ''} fired ({datetime.utcnow().date().isoformat()})"
    lines = [
        f"Maj. Recon — Majiks Research Monitor",
        f"Run: {run_id}",
        f"Fired at (UTC): {datetime.utcnow().isoformat()}Z",
        f"Tripwires: {len(tripwires)}",
        "",
    ]
    for i, tw in enumerate(tripwires, 1):
        lines.append(f"{i}. [{tw.domain}/{tw.rule}] {tw.headline}")
        if tw.detail:
            lines.append(f"   {tw.detail}")
        if tw.source_url:
            lines.append(f"   Source: {tw.source_url}")
        if tw.source_n:
            lines.append(f"   Bibliography: source-{tw.source_n}")
        if tw.deck_impact:
            lines.append(f"   Deck impact: {tw.deck_impact}")
        lines.append("")
    lines.append("— end of tripwire bundle —")
    return subject, "\n".join(lines)


async def _post_slack(webhook_url: str, payload: dict) -> dict:
    try:
        async with httpx.AsyncClient(timeout=SLACK_WEBHOOK_TIMEOUT) as client:
            resp = await client.post(webhook_url, json=payload)
        ok = resp.status_code == 200
        return {"channel": "slack", "ok": ok, "status_code": resp.status_code,
                "body": resp.text[:200]}
    except Exception as e:
        logger.exception("tripwire slack post failed")
        return {"channel": "slack", "ok": False, "error": str(e)}


async def _send_email(recipients: list[str], subject: str, body: str) -> dict:
    try:
        from app.llm.email_providers import get_email_provider
    except Exception as e:
        return {"channel": "email", "ok": False, "skipped": True,
                "reason": f"email_providers import failed: {e}"}

    try:
        provider = get_email_provider()
    except Exception as e:
        return {"channel": "email", "ok": False, "skipped": True,
                "reason": f"no provider configured: {e}"}

    if provider is None or not provider.is_configured():
        return {"channel": "email", "ok": False, "skipped": True,
                "reason": "no email provider configured (set MS365_*/RESEND_*/SENDGRID_*/GOOGLE_* env vars)"}

    to_field = ", ".join(recipients)
    try:
        result = await provider.send_email(to=to_field, subject=subject, body=body)
        return {"channel": "email", "ok": True, "provider": provider.name,
                "recipients": recipients, "provider_response": result}
    except Exception as e:
        logger.exception("tripwire email send failed")
        return {"channel": "email", "ok": False, "error": str(e)}


def _persist_tripwires(bundle: list[Tripwire], run_id: str) -> None:
    """Best-effort Tripwire node persistence for digest aggregation."""
    try:
        from falkordb import FalkorDB

        db = FalkorDB(
            host=os.getenv("FALKORDB_HOST", "unicorn-falkordb"),
            port=int(os.getenv("FALKORDB_PORT", "6379")),
            password=os.getenv("FALKORDB_PASSWORD") or None,
        )
        graph = db.select_graph(MAJIKS_GRAPH_NAME)
        for tw in bundle:
            props = {**tw.__dict__, "run_id": run_id}
            graph.query(
                """
                MERGE (t:Tripwire {run_id: $run_id, headline: $headline, source_url: $source_url})
                ON CREATE SET
                    t.rule = $rule,
                    t.domain = $domain,
                    t.detail = $detail,
                    t.source_n = $source_n,
                    t.deck_impact = $deck_impact,
                    t.severity = $severity,
                    t.fired_at = $fired_at,
                    t.created_at = $fired_at
                ON MATCH SET
                    t.rule = $rule,
                    t.domain = $domain,
                    t.detail = $detail,
                    t.source_n = $source_n,
                    t.deck_impact = $deck_impact,
                    t.severity = $severity,
                    t.fired_at = $fired_at,
                    t.updated_at = $fired_at
                """,
                props,
            )
    except Exception:
        logger.exception("tripwire graph persistence failed")


async def dispatch_tripwires(
    tripwires: Iterable[dict | Tripwire],
    run_id: str,
    dry_run: bool = False,
    slack_webhook_override: Optional[str] = None,
    email_to_override: Optional[list[str]] = None,
) -> dict:
    """
    Dispatch a batch of tripwires to Slack + email.

    Always logs the bundle to logger.warning() so even when both channels are
    unconfigured the tripwires are durably preserved in the Brigade log.

    Returns a dict with per-channel outcome plus the rendered payloads (for
    inspection / dry-run). Never raises — channel failures are surfaced in the
    return value so the calling workflow step can decide what to do.
    """
    bundle: list[Tripwire] = [
        tw if isinstance(tw, Tripwire) else Tripwire.from_dict(tw)
        for tw in tripwires
    ]

    if not bundle:
        logger.info("dispatch_tripwires: no tripwires in bundle for run_id=%s, no-op", run_id)
        return {"run_id": run_id, "count": 0, "channels": []}

    # Always log the full bundle. This is the durable record.
    logger.warning(
        "MAJIKS_TRIPWIRE bundle run_id=%s count=%d payload=%s",
        run_id, len(bundle),
        json.dumps([tw.__dict__ for tw in bundle], default=str),
    )
    _persist_tripwires(bundle, run_id)

    slack_payload = _slack_blocks_for(bundle, run_id)
    subject, email_body = _email_body_for(bundle, run_id)

    if dry_run:
        return {
            "run_id": run_id,
            "count": len(bundle),
            "dry_run": True,
            "slack_payload": slack_payload,
            "email_subject": subject,
            "email_body": email_body,
            "channels": [],
        }

    channels: list[dict] = []

    webhook = slack_webhook_override or os.environ.get("MAJIKS_TRIPWIRE_SLACK_WEBHOOK", "").strip()
    if webhook:
        channels.append(await _post_slack(webhook, slack_payload))
    else:
        channels.append({"channel": "slack", "ok": False, "skipped": True,
                         "reason": "MAJIKS_TRIPWIRE_SLACK_WEBHOOK not set"})

    if email_to_override is not None:
        recipients = email_to_override
    else:
        raw = os.environ.get("MAJIKS_TRIPWIRE_EMAIL_TO", DEFAULT_EMAIL_RECIPIENT)
        recipients = [addr.strip() for addr in raw.split(",") if addr.strip()]
    if recipients:
        channels.append(await _send_email(recipients, subject, email_body))
    else:
        channels.append({"channel": "email", "ok": False, "skipped": True,
                         "reason": "no email recipients (MAJIKS_TRIPWIRE_EMAIL_TO empty)"})

    return {"run_id": run_id, "count": len(bundle), "channels": channels}
