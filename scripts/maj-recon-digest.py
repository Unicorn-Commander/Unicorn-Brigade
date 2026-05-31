#!/usr/bin/env python3
"""Build and send Maj. Recon tripwire digests."""

from __future__ import annotations

import argparse
import asyncio
import html
import json
import logging
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.integrations.postmark_sender import PostmarkSender  # noqa: E402

STATE_FILE = Path(os.getenv("MAJIKS_DIGEST_STATE_FILE", "/etc/maj-recon/last-digest-ts"))
DEFAULT_TO = "aaron@magicunicorn.tech"
GRAPH_NAME = os.getenv("MAJIKS_RESEARCH_GRAPH", "majiks_research")
STABLE_URL = "https://stable.magicunicorn.dev/?room=majiks-research"
PROJECT_OPS_URL = os.getenv(
    "MAJIKS_PROJECT_OPS_URL",
    "https://ops.magicunicorn.dev/projects/P-00001",
)

logger = logging.getLogger("maj_recon_digest")


@dataclass
class DigestTripwire:
    domain: str
    rule: str
    headline: str
    deck_impact: str = ""
    source_url: str = ""
    detail: str = ""
    severity: str = "material"
    fired_at: str = ""

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> "DigestTripwire":
        props = value.get("properties", value)
        domain = props.get("domain") or props.get("captain") or props.get("cap") or "unknown"
        return cls(
            domain=str(domain or "unknown"),
            rule=str(props.get("rule") or "unknown"),
            headline=str(props.get("headline") or "(untitled tripwire)"),
            deck_impact=str(props.get("deck_impact") or props.get("deckImpact") or ""),
            source_url=str(props.get("source_url") or props.get("sourceUrl") or props.get("url") or ""),
            detail=str(props.get("detail") or props.get("body") or ""),
            severity=str(props.get("severity") or "material"),
            fired_at=str(props.get("fired_at") or props.get("firedAt") or props.get("created_at") or ""),
        )


def parse_iso_ts(value: str) -> datetime:
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def utc_now() -> datetime:
    return datetime.now(UTC)


def default_since() -> datetime:
    if STATE_FILE.exists():
        raw = STATE_FILE.read_text(encoding="utf-8").strip()
        if raw:
            return parse_iso_ts(raw)
    return utc_now() - timedelta(days=7)


def write_state(ts: datetime) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(ts.astimezone(UTC).isoformat().replace("+00:00", "Z") + "\n", encoding="utf-8")


def falkordb_graph():
    try:
        from falkordb import FalkorDB
    except Exception as exc:
        logger.warning("FalkorDB package unavailable, skipping graph query: %s", exc)
        return None

    host = os.getenv("FALKORDB_HOST", "unicorn-falkordb")
    port = int(os.getenv("FALKORDB_PORT", "6379"))
    password = os.getenv("FALKORDB_PASSWORD") or None
    try:
        return FalkorDB(host=host, port=port, password=password).select_graph(GRAPH_NAME)
    except Exception as exc:
        logger.warning("FalkorDB connection failed, skipping graph query: %s", exc)
        return None


def graph_node_to_dict(node: Any) -> dict[str, Any]:
    if isinstance(node, dict):
        return node
    props = getattr(node, "properties", None)
    if isinstance(props, dict):
        return props
    if hasattr(node, "items"):
        return dict(node.items())
    return {}


def query_tripwires_from_graph(since: datetime) -> list[DigestTripwire]:
    graph = falkordb_graph()
    if graph is None:
        return []

    queries = [
        (
            "MATCH (t:Tripwire) "
            "WHERE t.fired_at > $since OR t.created_at > $since "
            "RETURN t ORDER BY coalesce(t.fired_at, t.created_at) DESC"
        ),
        (
            "MATCH (t:Tripwire) "
            "WHERE t.fired_at > datetime($since) OR t.created_at > datetime($since) "
            "RETURN t ORDER BY coalesce(t.fired_at, t.created_at) DESC"
        ),
    ]
    params = {"since": since.isoformat().replace("+00:00", "Z")}

    for query in queries:
        try:
            result = graph.query(query, params)
            rows = getattr(result, "result_set", []) or []
            return [DigestTripwire.from_mapping(graph_node_to_dict(row[0])) for row in rows if row]
        except Exception as exc:
            logger.info("Tripwire graph query variant failed: %s", exc)
    return []


LOG_PAYLOAD_RE = re.compile(r"MAJIKS_TRIPWIRE bundle .*?payload=(\[.*\])")


def query_tripwires_from_docker_logs(since: datetime) -> list[DigestTripwire]:
    """Best-effort fallback when run on a Docker host with access to docker logs."""
    if os.getenv("MAJIKS_DIGEST_DISABLE_DOCKER_LOGS"):
        return []
    since_arg = since.isoformat().replace("+00:00", "Z")
    try:
        proc = subprocess.run(
            ["docker", "logs", "unicorn-brigade", f"--since={since_arg}"],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except Exception as exc:
        logger.info("Docker log fallback unavailable: %s", exc)
        return []
    if proc.returncode != 0:
        logger.info("Docker log fallback failed: %s", proc.stderr.strip()[:240])
        return []

    tripwires: list[DigestTripwire] = []
    for line in proc.stdout.splitlines() + proc.stderr.splitlines():
        match = LOG_PAYLOAD_RE.search(line)
        if not match:
            continue
        try:
            payload = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        for item in payload:
            tw = DigestTripwire.from_mapping(item)
            if tw.fired_at:
                try:
                    if parse_iso_ts(tw.fired_at) <= since:
                        continue
                except ValueError:
                    pass
            tripwires.append(tw)
    return dedupe_tripwires(tripwires)


def dedupe_tripwires(items: list[DigestTripwire]) -> list[DigestTripwire]:
    seen: set[tuple[str, str, str, str]] = set()
    out: list[DigestTripwire] = []
    for item in items:
        key = (item.domain, item.rule, item.headline, item.source_url)
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def collect_tripwires(since: datetime) -> list[DigestTripwire]:
    graph_items = query_tripwires_from_graph(since)
    if graph_items:
        return dedupe_tripwires(graph_items)
    return query_tripwires_from_docker_logs(since)


def captain_label(domain: str) -> str:
    return {
        "cap": "Cpt. Cap",
        "court": "Cpt. Court",
        "stack": "Cpt. Stack",
        "lab": "Cpt. Lab",
    }.get(domain.lower(), domain.title() if domain else "Unknown")


def source_anchor(source_url: str) -> str:
    if not source_url:
        return "source pending"
    return f'<a href="{html.escape(source_url)}">source</a>'


def render_email(tripwires: list[DigestTripwire], since: datetime, cadence: str) -> tuple[str, str]:
    since_label = since.strftime("%Y-%m-%d %H:%M UTC")
    subject = f"Maj. Recon digest - {len(tripwires)} tripwires since {since.strftime('%Y-%m-%d')}"
    density = "compact" if cadence == "weekly" else "daily"
    by_domain: dict[str, list[DigestTripwire]] = {}
    for tw in tripwires:
        by_domain.setdefault(tw.domain.lower(), []).append(tw)

    sections: list[str] = []
    for domain in ["court", "cap", "stack", "lab"]:
        items = by_domain.pop(domain, [])
        if not items:
            continue
        rows = []
        for tw in items:
            source = source_anchor(tw.source_url)
            detail = "" if density == "compact" else f"<p>{html.escape(tw.detail)}</p>" if tw.detail else ""
            deck = f"<p><strong>Deck impact:</strong> {html.escape(tw.deck_impact)}</p>" if tw.deck_impact else ""
            fired = f"<span>{html.escape(tw.fired_at)}</span>" if tw.fired_at else ""
            rows.append(
                "<li>"
                f"<h3>{html.escape(tw.headline)}</h3>"
                f"{detail}{deck}"
                f"<p class=\"meta\">{source} &nbsp; {fired}</p>"
                "</li>"
            )
        sections.append(
            f"<section><h2>{html.escape(captain_label(domain))}</h2><ul>{''.join(rows)}</ul></section>"
        )

    for domain, items in sorted(by_domain.items()):
        rows = "".join(
            f"<li><h3>{html.escape(tw.headline)}</h3>"
            f"<p><strong>Deck impact:</strong> {html.escape(tw.deck_impact)}</p>"
            f"<p class=\"meta\">{source_anchor(tw.source_url)}</p></li>"
            for tw in items
        )
        sections.append(f"<section><h2>{html.escape(captain_label(domain))}</h2><ul>{rows}</ul></section>")

    if not sections:
        sections.append(
            "<section><h2>No material tripwires</h2>"
            "<p>No Maj. Recon tripwire alerts were found for this digest window.</p></section>"
        )

    html_body = f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {{ margin: 0; background: #f5f7fb; color: #17202a; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    .wrap {{ max-width: 760px; margin: 0 auto; padding: 28px 18px; }}
    .panel {{ background: #ffffff; border: 1px solid #dfe5ef; border-radius: 8px; overflow: hidden; }}
    header {{ padding: 24px 28px; background: #122033; color: #ffffff; }}
    header h1 {{ margin: 0 0 8px; font-size: 24px; line-height: 1.2; font-weight: 700; }}
    header p {{ margin: 0; color: #c8d4e4; font-size: 14px; }}
    section {{ padding: 22px 28px; border-top: 1px solid #e8edf5; }}
    h2 {{ margin: 0 0 12px; font-size: 17px; color: #122033; }}
    h3 {{ margin: 0 0 8px; font-size: 15px; line-height: 1.35; }}
    p {{ margin: 0 0 10px; font-size: 14px; line-height: 1.5; }}
    ul {{ margin: 0; padding: 0; list-style: none; }}
    li {{ padding: 14px 0; border-top: 1px solid #edf1f7; }}
    li:first-child {{ border-top: 0; padding-top: 0; }}
    a {{ color: #0b62b4; text-decoration: none; }}
    .meta {{ color: #66748a; font-size: 12px; }}
    footer {{ padding: 18px 28px 24px; border-top: 1px solid #e8edf5; color: #526074; font-size: 13px; }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="panel">
      <header>
        <h1>Maj. Recon digest</h1>
        <p>{len(tripwires)} tripwire{"s" if len(tripwires) != 1 else ""} since {html.escape(since_label)}</p>
      </header>
      {''.join(sections)}
      <footer>
        <a href="{STABLE_URL}">Live Stable channel</a>
        &nbsp;|&nbsp;
        <a href="{PROJECT_OPS_URL}">Project Ops P-00001</a>
      </footer>
    </div>
  </div>
</body>
</html>"""
    return subject, html_body


async def run(args: argparse.Namespace) -> int:
    run_ts = utc_now()
    since = parse_iso_ts(args.since) if args.since else default_since()
    tripwires = collect_tripwires(since)
    subject, body = render_email(tripwires, since, args.cadence)

    if args.dry_run:
        print(f"Subject: {subject}\n")
        print(body)
        return 0

    # Suppress empty digests by default — only mail when there's something to report.
    # Use --force-send to mail regardless (useful when verifying delivery pipeline).
    if not tripwires and not args.force_send:
        logger.info("Maj. Recon digest skipped — no tripwires since %s. Use --force-send to mail anyway.", since.isoformat())
        # Still advance the state file so the next run only scans new material.
        write_state(run_ts)
        return 0

    to_addr = os.getenv("MAJIKS_DIGEST_TO", DEFAULT_TO)
    result = await PostmarkSender().send(to_addr, subject, body)
    print(json.dumps({"to": to_addr, "subject": subject, **result}, indent=2))
    if not result.get("sent"):
        return 1
    write_state(run_ts)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--since", help="ISO timestamp override for the digest window")
    parser.add_argument("--dry-run", action="store_true", help="print rendered email instead of sending")
    parser.add_argument("--cadence", choices=["daily", "weekly"], default="daily")
    parser.add_argument("--force-send", action="store_true", help="send even when there are zero tripwires (useful for verifying delivery)")
    args = parser.parse_args()
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(name)s %(message)s")
    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
