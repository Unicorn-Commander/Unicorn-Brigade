"""Read-only SQL access to the Umami analytics database (umami_db)."""

import os
import re
from typing import Any, Dict

import asyncpg
from dotenv import load_dotenv

from app.llm.ops_center_client import ToolDefinition, ToolParameter

load_dotenv()

# Same Postgres server as brigade_db; different database.
_UMAMI_DSN = os.getenv(
    "UMAMI_DB_DSN",
    "postgresql://unicorn:{pw}@unicorn-postgresql:5432/umami_db".format(
        pw=os.getenv("POSTGRES_PASSWORD", "")
    ),
)

# Allow only a single read-only statement.
_FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|truncate|grant|revoke|copy|"
    r"vacuum|reindex|comment|call|do|merge|refresh|set|begin|commit)\b",
    re.IGNORECASE,
)


async def analytics_sql_handler(
    query: str,
    max_rows: int = 200,
    timeout_s: float = 15.0,
) -> Dict[str, Any]:
    q = (query or "").strip().rstrip(";")
    if not q:
        return {"error": "empty query"}
    if ";" in q:
        return {"error": "only a single statement is allowed"}
    if not re.match(r"^\s*(select|with)\b", q, re.IGNORECASE):
        return {"error": "only SELECT/WITH queries are allowed"}
    if _FORBIDDEN.search(q):
        return {"error": "write/DDL keywords are not allowed on this read-only connection"}

    conn = None
    try:
        conn = await asyncpg.connect(_UMAMI_DSN, timeout=timeout_s)
        # Database-level guardrails in addition to query validation.
        async with conn.transaction(readonly=True):
            await conn.execute(f"SET LOCAL statement_timeout = {int(timeout_s * 1000)}")
            rows = await conn.fetch(q)
        out = [dict(r) for r in rows[:max_rows]]
        for r in out:
            for k, v in r.items():
                if not isinstance(v, (str, int, float, bool, type(None))):
                    r[k] = str(v)
        return {"row_count": len(out), "rows": out, "truncated": len(rows) > max_rows}
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}
    finally:
        if conn:
            await conn.close()


ANALYTICS_SQL_TOOL = ToolDefinition(
    name="analytics_sql",
    description=(
        "Run a READ-ONLY SQL query (SELECT/WITH only) against the Umami web-analytics "
        "database 'umami_db'. Tables: website(website_id,name,domain,created_at), "
        "website_event(website_id,session_id,created_at,url_path,referrer_domain,event_type,"
        "event_name) where event_type 1=pageview 2=custom-event, and session(session_id,"
        "website_id,country,device,browser,os,created_at). Use it to compute pageviews, "
        "unique visitors, events (track_play/download), referrers, geo and trends per domain."
    ),
    parameters=[
        ToolParameter(
            name="query",
            type="string",
            description="A single read-only SELECT/WITH statement.",
            required=True,
        ),
        ToolParameter(
            name="max_rows",
            type="number",
            description="Row cap (default 200).",
            required=False,
            default=200,
        ),
    ],
    handler=analytics_sql_handler,
)
