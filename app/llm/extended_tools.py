"""
Extended Tools for Agent Execution

Additional tools beyond the core builtin set.
These are direct Python tools (not MCP servers) for speed and simplicity.
"""

import asyncio
import json
import logging
import os
import base64
import hashlib
import re
from typing import Dict, Any, List, Optional
from datetime import datetime
import httpx
from dotenv import load_dotenv

# Ensure environment variables are loaded before reading them
load_dotenv()

from app.llm.ops_center_client import ToolDefinition, ToolParameter

logger = logging.getLogger(__name__)


# ============== Email Tool ==============

# Import the email provider abstraction
from app.llm.email_providers import get_email_provider, get_available_providers

EMAIL_PROVIDER = os.getenv("EMAIL_PROVIDER", "ms365")  # ms365, google, resend, sendgrid


async def email_handler(
    to: str,
    subject: str,
    body: str,
    from_email: Optional[str] = None,
    cc: Optional[str] = None,
    bcc: Optional[str] = None,
    html: bool = False,
    provider: Optional[str] = None,
    operation: str = "send",
    message_id: Optional[str] = None,
    query: Optional[str] = None,
    max_results: int = 10,
) -> Dict[str, Any]:
    """
    Email operations via configured provider (MS365, Google, Resend, SendGrid).

    Supports:
    - send: Send an email
    - get: Get a specific email by message_id
    - list: List emails with optional query filter
    - search: Search emails with provider-specific query syntax
    """
    logger.info(f"Email operation: {operation}, provider={provider or EMAIL_PROVIDER}")

    try:
        # Get the email provider
        email_provider = get_email_provider(provider)

        if not email_provider.is_configured():
            return {
                "success": False,
                "error": f"Email provider '{email_provider.name}' is not configured. "
                         f"Available providers: {', '.join(get_available_providers())}",
            }

        # Handle different operations
        if operation == "send":
            logger.info(f"Email: to={to}, subject={subject[:30] if subject else 'N/A'}...")
            return await email_provider.send_email(
                to=to,
                subject=subject,
                body=body,
                from_email=from_email,
                cc=cc,
                bcc=bcc,
                html=html,
            )

        elif operation == "get":
            if not message_id:
                return {"success": False, "error": "message_id required for get operation"}
            return await email_provider.get_email(message_id)

        elif operation == "list":
            return await email_provider.list_emails(query=query, max_results=max_results)

        elif operation == "search":
            if not query:
                return {"success": False, "error": "query required for search operation"}
            return await email_provider.search_emails(query=query, max_results=max_results)

        else:
            return {"success": False, "error": f"Unknown operation: {operation}"}

    except Exception as e:
        logger.error(f"Email handler error: {e}")
        return {"success": False, "error": str(e)}


EMAIL_TOOL = ToolDefinition(
    name="email",
    description=(
        "Email operations via configured provider (MS365 or Google Workspace). "
        "Operations: send (default), get, list, search. "
        "For send: provide to, subject, body. For get: provide message_id. "
        "For list/search: optionally provide query and max_results."
    ),
    parameters=[
        ToolParameter(
            name="operation",
            type="string",
            description="Operation: 'send' (default), 'get', 'list', 'search'",
            required=False,
            default="send",
            enum=["send", "get", "list", "search"],
        ),
        ToolParameter(name="to", type="string", description="Recipient email address (for send)", required=False),
        ToolParameter(name="subject", type="string", description="Email subject (for send)", required=False),
        ToolParameter(name="body", type="string", description="Email body content (for send)", required=False),
        ToolParameter(name="cc", type="string", description="CC recipients, comma-separated (for send)", required=False),
        ToolParameter(name="bcc", type="string", description="BCC recipients, comma-separated (for send)", required=False),
        ToolParameter(name="html", type="boolean", description="Send as HTML (default: plain text)", required=False, default=False),
        ToolParameter(name="message_id", type="string", description="Message ID (for get operation)", required=False),
        ToolParameter(name="query", type="string", description="Search query (for list/search operations)", required=False),
        ToolParameter(name="max_results", type="number", description="Max results for list/search (default 10)", required=False, default=10),
        ToolParameter(name="from_email", type="string", description="DO NOT USE - system uses configured sender", required=False),
        ToolParameter(
            name="provider",
            type="string",
            description="Email provider override (default from EMAIL_PROVIDER env)",
            required=False,
            enum=["ms365", "google", "resend", "sendgrid"],
        ),
    ],
    handler=email_handler,
)


# ============== File Tool ==============

SANDBOX_DIR = os.getenv("TOOL_SANDBOX_DIR", "/tmp/brigade-sandbox")


async def file_handler(
    operation: str,
    path: str,
    content: Optional[str] = None,
    encoding: str = "utf-8",
) -> Dict[str, Any]:
    """File operations within a sandboxed directory."""
    logger.info(f"File operation: {operation} on {path}")

    # Ensure sandbox directory exists
    os.makedirs(SANDBOX_DIR, exist_ok=True)

    # Prevent path traversal
    safe_path = os.path.normpath(os.path.join(SANDBOX_DIR, path))
    if not safe_path.startswith(SANDBOX_DIR):
        return {"error": "Path traversal blocked", "success": False}

    try:
        if operation == "read":
            if not os.path.exists(safe_path):
                return {"error": "File not found", "success": False}
            with open(safe_path, "r", encoding=encoding) as f:
                return {"content": f.read(), "path": path, "success": True}

        elif operation == "write":
            os.makedirs(os.path.dirname(safe_path), exist_ok=True)
            with open(safe_path, "w", encoding=encoding) as f:
                f.write(content or "")
            return {"path": path, "bytes_written": len(content or ""), "success": True}

        elif operation == "append":
            os.makedirs(os.path.dirname(safe_path), exist_ok=True)
            with open(safe_path, "a", encoding=encoding) as f:
                f.write(content or "")
            return {"path": path, "bytes_appended": len(content or ""), "success": True}

        elif operation == "delete":
            if not os.path.exists(safe_path):
                return {"error": "File not found", "success": False}
            os.remove(safe_path)
            return {"path": path, "deleted": True, "success": True}

        elif operation == "list":
            if not os.path.isdir(safe_path):
                return {"error": "Not a directory", "success": False}
            files = os.listdir(safe_path)
            return {"files": files, "count": len(files), "path": path, "success": True}

        elif operation == "exists":
            return {"exists": os.path.exists(safe_path), "path": path, "success": True}

        elif operation == "info":
            if not os.path.exists(safe_path):
                return {"error": "File not found", "success": False}
            stat = os.stat(safe_path)
            return {
                "path": path,
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "is_dir": os.path.isdir(safe_path),
                "success": True,
            }

        else:
            return {"error": f"Unknown operation: {operation}", "success": False}

    except Exception as e:
        return {"error": str(e), "success": False}


FILE_TOOL = ToolDefinition(
    name="file",
    description="File operations in a sandboxed directory. Can read, write, list, and delete files.",
    parameters=[
        ToolParameter(
            name="operation",
            type="string",
            description="Operation: 'read', 'write', 'append', 'delete', 'list', 'exists', 'info'",
            required=True,
            enum=["read", "write", "append", "delete", "list", "exists", "info"],
        ),
        ToolParameter(name="path", type="string", description="File or directory path (relative to sandbox)", required=True),
        ToolParameter(name="content", type="string", description="Content for write/append operations", required=False),
        ToolParameter(name="encoding", type="string", description="File encoding (default: utf-8)", required=False, default="utf-8"),
    ],
    handler=file_handler,
)


# ============== Code Execution Tool ==============

async def code_handler(
    code: str,
    language: str = "python",
    timeout: int = 10,
) -> Dict[str, Any]:
    """Execute code in a sandboxed environment."""
    logger.info(f"Code execution: {language}, {len(code)} chars")

    if language != "python":
        return {"error": f"Language '{language}' not supported. Use 'python'.", "success": False}

    # Security: Block dangerous patterns
    BLOCKED_PATTERNS = [
        "import os", "import subprocess", "import sys",
        "__import__", "eval(", "exec(", "open(",
        "file(", "input(", "compile(",
    ]

    for pattern in BLOCKED_PATTERNS:
        if pattern in code:
            return {"error": f"Blocked pattern detected: {pattern}", "success": False}

    try:
        # Create a restricted execution environment
        safe_globals = {
            "__builtins__": {
                "abs": abs, "round": round, "min": min, "max": max,
                "sum": sum, "len": len, "range": range, "enumerate": enumerate,
                "zip": zip, "map": map, "filter": filter, "sorted": sorted,
                "list": list, "dict": dict, "set": set, "tuple": tuple,
                "str": str, "int": int, "float": float, "bool": bool,
                "print": print, "type": type, "isinstance": isinstance,
                "True": True, "False": False, "None": None,
            },
        }

        # Add math functions
        import math
        safe_globals["math"] = math

        # Add json for data handling
        safe_globals["json"] = json

        # Capture output
        output_lines = []
        def capture_print(*args, **kwargs):
            output_lines.append(" ".join(str(a) for a in args))
        safe_globals["__builtins__"]["print"] = capture_print

        # Execute with timeout
        local_vars = {}
        exec(code, safe_globals, local_vars)

        # Get result if there's a 'result' variable
        result = local_vars.get("result")

        return {
            "output": "\n".join(output_lines),
            "result": result,
            "variables": {k: str(v)[:200] for k, v in local_vars.items() if not k.startswith("_")},
            "success": True,
        }

    except Exception as e:
        return {"error": str(e), "success": False}


CODE_TOOL = ToolDefinition(
    name="code",
    description="Execute Python code in a sandboxed environment. Has access to math, json, and basic builtins. Set 'result' variable to return a value.",
    parameters=[
        ToolParameter(name="code", type="string", description="Python code to execute", required=True),
        ToolParameter(name="language", type="string", description="Language (only 'python' supported)", required=False, default="python"),
        ToolParameter(name="timeout", type="number", description="Execution timeout in seconds", required=False, default=10),
    ],
    handler=code_handler,
)


# ============== Text Processing Tool ==============

async def text_handler(
    operation: str,
    text: str,
    pattern: Optional[str] = None,
    replacement: Optional[str] = None,
) -> Dict[str, Any]:
    """Text processing operations."""
    logger.info(f"Text operation: {operation}")

    try:
        if operation == "length":
            return {"length": len(text), "words": len(text.split()), "lines": len(text.splitlines()), "success": True}

        elif operation == "upper":
            return {"result": text.upper(), "success": True}

        elif operation == "lower":
            return {"result": text.lower(), "success": True}

        elif operation == "title":
            return {"result": text.title(), "success": True}

        elif operation == "reverse":
            return {"result": text[::-1], "success": True}

        elif operation == "trim":
            return {"result": text.strip(), "success": True}

        elif operation == "split":
            delimiter = pattern or " "
            return {"result": text.split(delimiter), "success": True}

        elif operation == "replace":
            if not pattern:
                return {"error": "Pattern required for replace", "success": False}
            return {"result": text.replace(pattern, replacement or ""), "success": True}

        elif operation == "regex_match":
            if not pattern:
                return {"error": "Pattern required for regex_match", "success": False}
            matches = re.findall(pattern, text)
            return {"matches": matches, "count": len(matches), "success": True}

        elif operation == "regex_replace":
            if not pattern:
                return {"error": "Pattern required for regex_replace", "success": False}
            return {"result": re.sub(pattern, replacement or "", text), "success": True}

        elif operation == "extract_emails":
            emails = re.findall(r'[\w.+-]+@[\w-]+\.[\w.-]+', text)
            return {"emails": emails, "count": len(emails), "success": True}

        elif operation == "extract_urls":
            urls = re.findall(r'https?://[^\s<>"{}|\\^`\[\]]+', text)
            return {"urls": urls, "count": len(urls), "success": True}

        elif operation == "extract_numbers":
            numbers = re.findall(r'-?\d+\.?\d*', text)
            return {"numbers": [float(n) if '.' in n else int(n) for n in numbers], "count": len(numbers), "success": True}

        elif operation == "hash":
            hash_type = pattern or "sha256"
            if hash_type == "md5":
                h = hashlib.md5(text.encode()).hexdigest()
            elif hash_type == "sha1":
                h = hashlib.sha1(text.encode()).hexdigest()
            else:
                h = hashlib.sha256(text.encode()).hexdigest()
            return {"hash": h, "algorithm": hash_type, "success": True}

        elif operation == "base64_encode":
            return {"result": base64.b64encode(text.encode()).decode(), "success": True}

        elif operation == "base64_decode":
            return {"result": base64.b64decode(text.encode()).decode(), "success": True}

        elif operation == "summarize":
            # Simple extractive summary: first N sentences
            sentences = re.split(r'[.!?]+', text)
            sentences = [s.strip() for s in sentences if s.strip()]
            max_sentences = int(pattern) if pattern and pattern.isdigit() else 3
            summary = ". ".join(sentences[:max_sentences]) + "." if sentences else text
            return {"summary": summary, "total_sentences": len(sentences), "success": True}

        else:
            return {"error": f"Unknown operation: {operation}", "success": False}

    except Exception as e:
        return {"error": str(e), "success": False}


TEXT_TOOL = ToolDefinition(
    name="text",
    description="Text processing operations: length, upper, lower, split, replace, regex operations, extract emails/urls/numbers, hash, base64, summarize.",
    parameters=[
        ToolParameter(
            name="operation",
            type="string",
            description="Operation to perform",
            required=True,
            enum=["length", "upper", "lower", "title", "reverse", "trim", "split", "replace", "regex_match", "regex_replace", "extract_emails", "extract_urls", "extract_numbers", "hash", "base64_encode", "base64_decode", "summarize"],
        ),
        ToolParameter(name="text", type="string", description="Text to process", required=True),
        ToolParameter(name="pattern", type="string", description="Pattern for operations that need it (regex, replace, split, hash algorithm)", required=False),
        ToolParameter(name="replacement", type="string", description="Replacement text for replace operations", required=False),
    ],
    handler=text_handler,
)


# ============== Image Generation Tool ==============

IMAGE_PROVIDER = os.getenv("IMAGE_PROVIDER", "")  # openai, stability, replicate
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
STABILITY_API_KEY = os.getenv("STABILITY_API_KEY", "")


async def image_handler(
    prompt: str,
    size: str = "1024x1024",
    style: str = "vivid",
) -> Dict[str, Any]:
    """Generate an image from a text prompt."""
    logger.info(f"Image generation: {prompt[:50]}...")

    if not OPENAI_API_KEY:
        return {"error": "OPENAI_API_KEY not configured for image generation", "success": False}

    try:
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                "https://api.openai.com/v1/images/generations",
                headers={
                    "Authorization": f"Bearer {OPENAI_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "dall-e-3",
                    "prompt": prompt,
                    "size": size,
                    "style": style,
                    "n": 1,
                },
            )

            if response.status_code == 200:
                data = response.json()
                image_url = data["data"][0]["url"]
                revised_prompt = data["data"][0].get("revised_prompt", prompt)
                return {
                    "image_url": image_url,
                    "revised_prompt": revised_prompt,
                    "size": size,
                    "success": True,
                }
            return {"error": response.text, "success": False}

    except Exception as e:
        return {"error": str(e), "success": False}


IMAGE_TOOL = ToolDefinition(
    name="image",
    description="Generate an image from a text prompt using DALL-E 3. Requires OPENAI_API_KEY.",
    parameters=[
        ToolParameter(name="prompt", type="string", description="Detailed description of the image to generate", required=True),
        ToolParameter(name="size", type="string", description="Image size", required=False, default="1024x1024", enum=["1024x1024", "1792x1024", "1024x1792"]),
        ToolParameter(name="style", type="string", description="Image style", required=False, default="vivid", enum=["vivid", "natural"]),
    ],
    handler=image_handler,
)


# ============== Database Tool ==============

async def database_handler(
    operation: str,
    query: Optional[str] = None,
    table: Optional[str] = None,
    data: Optional[Dict[str, Any]] = None,
    where: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Simple in-memory key-value database for agents.
    For production, connect to PostgreSQL via environment variables.
    """
    logger.info(f"Database operation: {operation}")

    # In-memory storage (would be Redis/PostgreSQL in production)
    if not hasattr(database_handler, "_storage"):
        database_handler._storage = {}

    storage = database_handler._storage

    try:
        if operation == "set":
            if not table or not data:
                return {"error": "Table and data required for set", "success": False}
            if table not in storage:
                storage[table] = {}
            key = data.get("id") or str(len(storage[table]))
            storage[table][key] = data
            return {"key": key, "table": table, "success": True}

        elif operation == "get":
            if not table:
                return {"error": "Table required for get", "success": False}
            if table not in storage:
                return {"error": f"Table '{table}' not found", "success": False}
            if where and "id" in where:
                record = storage[table].get(where["id"])
                return {"record": record, "success": True}
            return {"records": list(storage[table].values()), "count": len(storage[table]), "success": True}

        elif operation == "delete":
            if not table:
                return {"error": "Table required for delete", "success": False}
            if table not in storage:
                return {"error": f"Table '{table}' not found", "success": False}
            if where and "id" in where:
                if where["id"] in storage[table]:
                    del storage[table][where["id"]]
                    return {"deleted": True, "success": True}
                return {"error": "Record not found", "success": False}
            return {"error": "Where clause with id required for delete", "success": False}

        elif operation == "list_tables":
            return {"tables": list(storage.keys()), "success": True}

        elif operation == "count":
            if not table:
                return {"error": "Table required for count", "success": False}
            count = len(storage.get(table, {}))
            return {"count": count, "table": table, "success": True}

        elif operation == "clear":
            if table:
                storage[table] = {}
            else:
                storage.clear()
            return {"cleared": True, "success": True}

        else:
            return {"error": f"Unknown operation: {operation}", "success": False}

    except Exception as e:
        return {"error": str(e), "success": False}


DATABASE_TOOL = ToolDefinition(
    name="database",
    description="Simple key-value database for storing and retrieving data. Operations: set, get, delete, list_tables, count, clear.",
    parameters=[
        ToolParameter(name="operation", type="string", description="Operation to perform", required=True, enum=["set", "get", "delete", "list_tables", "count", "clear"]),
        ToolParameter(name="table", type="string", description="Table/collection name", required=False),
        ToolParameter(name="data", type="object", description="Data to store (for set operation)", required=False),
        ToolParameter(name="where", type="object", description="Query filter, e.g., {\"id\": \"abc\"}", required=False),
    ],
    handler=database_handler,
)


# ============== Notification Tool ==============

SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")


async def notify_handler(
    message: str,
    channel: str = "default",
    title: Optional[str] = None,
    level: str = "info",
) -> Dict[str, Any]:
    """Send notifications to Slack or Discord."""
    logger.info(f"Notification: {channel} - {message[:50]}...")

    try:
        if channel == "slack" and SLACK_WEBHOOK_URL:
            async with httpx.AsyncClient(timeout=15) as client:
                payload = {"text": f"*{title}*\n{message}" if title else message}
                response = await client.post(SLACK_WEBHOOK_URL, json=payload)
                return {"sent": response.status_code == 200, "channel": "slack", "success": True}

        elif channel == "discord" and DISCORD_WEBHOOK_URL:
            async with httpx.AsyncClient(timeout=15) as client:
                payload = {
                    "content": message,
                    "embeds": [{"title": title, "description": message, "color": 0x00ff00 if level == "info" else 0xff0000}] if title else None,
                }
                response = await client.post(DISCORD_WEBHOOK_URL, json=payload)
                return {"sent": response.status_code in [200, 204], "channel": "discord", "success": True}

        else:
            # Default: just log it
            logger.info(f"[{level.upper()}] {title or 'Notification'}: {message}")
            return {"logged": True, "channel": "log", "success": True}

    except Exception as e:
        return {"error": str(e), "success": False}


NOTIFY_TOOL = ToolDefinition(
    name="notify",
    description="Send notifications to Slack, Discord, or log. Configure SLACK_WEBHOOK_URL or DISCORD_WEBHOOK_URL.",
    parameters=[
        ToolParameter(name="message", type="string", description="Notification message", required=True),
        ToolParameter(name="channel", type="string", description="Channel: 'slack', 'discord', or 'default' (log)", required=False, default="default", enum=["slack", "discord", "default"]),
        ToolParameter(name="title", type="string", description="Optional title", required=False),
        ToolParameter(name="level", type="string", description="Level: 'info', 'warning', 'error'", required=False, default="info", enum=["info", "warning", "error"]),
    ],
    handler=notify_handler,
)


# ============== QR Code Tool ==============

async def qrcode_handler(
    data: str,
    size: int = 256,
    format: str = "png",
) -> Dict[str, Any]:
    """Generate a QR code."""
    logger.info(f"QR code generation: {data[:30]}...")

    try:
        # Use a public QR code API
        url = f"https://api.qrserver.com/v1/create-qr-code/?size={size}x{size}&data={data}&format={format}"

        return {
            "qr_url": url,
            "data": data,
            "size": f"{size}x{size}",
            "success": True,
        }

    except Exception as e:
        return {"error": str(e), "success": False}


QRCODE_TOOL = ToolDefinition(
    name="qrcode",
    description="Generate a QR code from text or URL.",
    parameters=[
        ToolParameter(name="data", type="string", description="Data to encode in QR code", required=True),
        ToolParameter(name="size", type="number", description="Size in pixels (default 256)", required=False, default=256),
        ToolParameter(name="format", type="string", description="Image format", required=False, default="png", enum=["png", "svg", "jpg"]),
    ],
    handler=qrcode_handler,
)


# ============== Agentic RAG Tool ==============

# Lazy import to avoid circular dependencies
_agentic_rag = None


def _get_agentic_rag():
    """Lazy-load AgenticRAG to avoid circular imports"""
    global _agentic_rag
    if _agentic_rag is None:
        from app.agents.agentic_rag import get_agentic_rag
        _agentic_rag = get_agentic_rag()
    return _agentic_rag


async def agentic_rag_handler(
    query: str,
    mode: str = "agentic",
    user_id: str = "system",
    max_iterations: int = 5,
    include_graph: bool = True,
    include_memory: bool = True,
) -> Dict[str, Any]:
    """
    Execute an Agentic RAG query that combines knowledge graph and memory retrieval.

    This tool provides comprehensive question answering by:
    1. Parsing the query to understand intent
    2. Querying the FalkorDB knowledge graph for entities and relationships
    3. Querying Qdrant (via mem0) for semantically similar content
    4. Fusing results and generating an answer with provenance

    Modes:
    - agentic: Full agentic behavior with iterative tool use (slower, more thorough)
    - simple: Direct retrieval and answer generation (faster, less flexible)
    - retrieve: Only retrieve context, no answer generation
    """
    logger.info(f"Agentic RAG query: mode={mode}, query={query[:50]}...")

    try:
        rag = _get_agentic_rag()

        if mode == "agentic":
            # Full agentic behavior with tool use
            response = await rag.query(
                query=query,
                user_id=user_id,
                max_iterations=max_iterations
            )
            return response.to_dict()

        elif mode == "simple":
            # Direct retrieval and answer
            return await rag.simple_query(
                query=query,
                user_id=user_id
            )

        elif mode == "retrieve":
            # Only retrieve context
            context = await rag.retrieve_context(
                query=query,
                user_id=user_id,
                include_graph=include_graph,
                include_memory=include_memory
            )
            return {
                "success": True,
                "context": {
                    "entities": context.graph_entities,
                    "relationships": context.graph_relationships,
                    "paths": context.graph_paths,
                    "memories": context.vector_memories,
                    "context_text": context.context_text,
                    "sources": context.sources
                }
            }

        else:
            return {"success": False, "error": f"Unknown mode: {mode}"}

    except Exception as e:
        logger.error(f"Agentic RAG error: {e}")
        return {"success": False, "error": str(e)}


AGENTIC_RAG_TOOL = ToolDefinition(
    name="agentic_rag",
    description="""Agentic RAG - Retrieval-Augmented Generation combining knowledge graph and memory.

This tool answers questions by:
1. Parsing natural language to understand entities and relationships
2. Querying the FalkorDB knowledge graph for structured data
3. Querying memory (Qdrant) for semantically similar content
4. Fusing results to generate comprehensive answers with sources

Use this for questions like:
- "What companies is John connected to?"
- "Find all entities related to Project X"
- "What do we know about Acme Corp?"
- "How is Alice connected to Bob?"

Modes:
- agentic: Full iterative tool use (thorough, slower)
- simple: Direct retrieval and answer (faster)
- retrieve: Only get context, no answer""",
    parameters=[
        ToolParameter(
            name="query",
            type="string",
            description="Natural language question to answer",
            required=True
        ),
        ToolParameter(
            name="mode",
            type="string",
            description="Query mode: 'agentic' (iterative), 'simple' (fast), 'retrieve' (context only)",
            required=False,
            default="agentic",
            enum=["agentic", "simple", "retrieve"]
        ),
        ToolParameter(
            name="user_id",
            type="string",
            description="User ID for memory context (default: system)",
            required=False,
            default="system"
        ),
        ToolParameter(
            name="max_iterations",
            type="number",
            description="Maximum tool use iterations for agentic mode (default 5)",
            required=False,
            default=5
        ),
        ToolParameter(
            name="include_graph",
            type="boolean",
            description="Include knowledge graph results (default true)",
            required=False,
            default=True
        ),
        ToolParameter(
            name="include_memory",
            type="boolean",
            description="Include memory results (default true)",
            required=False,
            default=True
        ),
    ],
    handler=agentic_rag_handler,
)


# ============== Export all extended tools ==============

EXTENDED_TOOLS = [
    EMAIL_TOOL,
    FILE_TOOL,
    CODE_TOOL,
    TEXT_TOOL,
    IMAGE_TOOL,
    DATABASE_TOOL,
    NOTIFY_TOOL,
    QRCODE_TOOL,
    AGENTIC_RAG_TOOL,
]
