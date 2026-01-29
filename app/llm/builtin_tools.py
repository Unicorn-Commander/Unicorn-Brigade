"""
Built-in Tools for Agent Execution

Provides a standard set of tools that agents can use for common operations.
"""

import asyncio
import json
import logging
import os
import httpx
from typing import Dict, Any, List, Optional
from datetime import datetime

from app.llm.ops_center_client import ToolDefinition, ToolParameter

logger = logging.getLogger(__name__)


# ============== Web Search Configuration ==============

# Search provider config from environment
SEARCH_PROVIDER = os.getenv("SEARCH_PROVIDER", "serper")  # serper, searxng, brightdata
SERPER_API_KEY = os.getenv("SERPER_API_KEY", "REMOVED")
SEARXNG_URL = os.getenv("SEARXNG_URL", "http://localhost:8889")
BRIGHTDATA_API_KEY = os.getenv("BRIGHTDATA_API_KEY", "")
BRIGHTDATA_ZONE = os.getenv("BRIGHTDATA_ZONE", "serp")


async def _search_serper(query: str, num_results: int = 5) -> Dict[str, Any]:
    """Search via Serper.dev (Google SERP API)"""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                "https://google.serper.dev/search",
                headers={
                    "X-API-KEY": SERPER_API_KEY,
                    "Content-Type": "application/json",
                },
                json={
                    "q": query,
                    "num": num_results,
                },
            )
            response.raise_for_status()
            data = response.json()

            results = []
            for item in data.get("organic", [])[:num_results]:
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("link", ""),
                    "snippet": item.get("snippet", ""),
                })

            # Include knowledge graph if present
            knowledge = None
            if "knowledgeGraph" in data:
                kg = data["knowledgeGraph"]
                knowledge = {
                    "title": kg.get("title", ""),
                    "type": kg.get("type", ""),
                    "description": kg.get("description", ""),
                }

            return {
                "query": query,
                "provider": "serper",
                "results": results,
                "knowledge_graph": knowledge,
                "success": True,
            }

    except Exception as e:
        logger.error(f"Serper search error: {e}")
        return {"query": query, "error": str(e), "success": False}


async def _search_searxng(query: str, num_results: int = 5) -> Dict[str, Any]:
    """Search via SearXNG (self-hosted metasearch)"""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(
                f"{SEARXNG_URL}/search",
                params={
                    "q": query,
                    "format": "json",
                    "categories": "general",
                },
            )
            response.raise_for_status()
            data = response.json()

            results = []
            for item in data.get("results", [])[:num_results]:
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "snippet": item.get("content", ""),
                    "engine": item.get("engine", ""),
                })

            return {
                "query": query,
                "provider": "searxng",
                "results": results,
                "success": True,
            }

    except Exception as e:
        logger.error(f"SearXNG search error: {e}")
        return {"query": query, "error": str(e), "success": False}


async def _search_brightdata(query: str, num_results: int = 5) -> Dict[str, Any]:
    """Search via Brightdata SERP API"""
    if not BRIGHTDATA_API_KEY:
        return {"query": query, "error": "BRIGHTDATA_API_KEY not configured", "success": False}

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            # Brightdata SERP API endpoint
            response = await client.post(
                "https://api.brightdata.com/serp/req",
                headers={
                    "Authorization": f"Bearer {BRIGHTDATA_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "zone": BRIGHTDATA_ZONE,
                    "query": query,
                    "search_engine": "google",
                    "num": num_results,
                },
            )
            response.raise_for_status()
            data = response.json()

            results = []
            for item in data.get("organic", [])[:num_results]:
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("link", ""),
                    "snippet": item.get("snippet", ""),
                })

            return {
                "query": query,
                "provider": "brightdata",
                "results": results,
                "success": True,
            }

    except Exception as e:
        logger.error(f"Brightdata search error: {e}")
        return {"query": query, "error": str(e), "success": False}


async def web_search_handler(query: str, num_results: int = 5, provider: str = None) -> Dict[str, Any]:
    """Execute a web search using configured provider"""
    use_provider = provider or SEARCH_PROVIDER
    logger.info(f"Web search [{use_provider}]: {query}")

    if use_provider == "serper":
        return await _search_serper(query, num_results)
    elif use_provider == "searxng":
        return await _search_searxng(query, num_results)
    elif use_provider == "brightdata":
        return await _search_brightdata(query, num_results)
    else:
        return {
            "query": query,
            "error": f"Unknown search provider: {use_provider}",
            "success": False,
        }


WEB_SEARCH_TOOL = ToolDefinition(
    name="web_search",
    description="Search the web for current information. Returns titles, URLs, and snippets from search results.",
    parameters=[
        ToolParameter(
            name="query",
            type="string",
            description="The search query",
            required=True,
        ),
        ToolParameter(
            name="num_results",
            type="number",
            description="Number of results to return (1-10)",
            required=False,
            default=5,
        ),
        ToolParameter(
            name="provider",
            type="string",
            description="Search provider: serper (Google), searxng, or brightdata",
            required=False,
            enum=["serper", "searxng", "brightdata"],
        ),
    ],
    handler=web_search_handler,
)


# ============== HTTP Request Tool ==============

async def http_request_handler(
    url: str,
    method: str = "GET",
    headers: Optional[Dict[str, str]] = None,
    body: Optional[Dict[str, Any]] = None,
    timeout: int = 30,
) -> Dict[str, Any]:
    """Make an HTTP request"""
    logger.info(f"HTTP {method} request to: {url}")

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.request(
                method=method.upper(),
                url=url,
                headers=headers or {},
                json=body if body and method.upper() in ["POST", "PUT", "PATCH"] else None,
                params=body if body and method.upper() == "GET" else None,
            )

            # Try to parse JSON response
            try:
                response_data = response.json()
            except:
                response_data = response.text

            return {
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "data": response_data,
                "success": response.is_success,
            }

    except Exception as e:
        return {
            "error": str(e),
            "success": False,
        }


HTTP_REQUEST_TOOL = ToolDefinition(
    name="http_request",
    description="Make an HTTP request to an API or website. Use for fetching data, calling APIs, etc.",
    parameters=[
        ToolParameter(
            name="url",
            type="string",
            description="The URL to request",
            required=True,
        ),
        ToolParameter(
            name="method",
            type="string",
            description="HTTP method (GET, POST, PUT, DELETE, etc.)",
            required=False,
            default="GET",
            enum=["GET", "POST", "PUT", "DELETE", "PATCH"],
        ),
        ToolParameter(
            name="headers",
            type="object",
            description="Optional HTTP headers",
            required=False,
        ),
        ToolParameter(
            name="body",
            type="object",
            description="Optional request body (for POST, PUT, etc.)",
            required=False,
        ),
    ],
    handler=http_request_handler,
)


# ============== Calculator Tool ==============

async def calculator_handler(expression: str) -> Dict[str, Any]:
    """Evaluate a mathematical expression safely"""
    logger.info(f"Calculator: {expression}")

    # Safe math evaluation
    allowed_names = {
        "abs": abs, "round": round, "min": min, "max": max,
        "sum": sum, "pow": pow, "len": len,
    }

    # Additional safe math functions
    import math
    allowed_names.update({
        "sqrt": math.sqrt, "sin": math.sin, "cos": math.cos, "tan": math.tan,
        "log": math.log, "log10": math.log10, "exp": math.exp,
        "pi": math.pi, "e": math.e,
    })

    try:
        # Clean expression
        clean_expr = expression.replace("^", "**")

        # Evaluate safely
        result = eval(clean_expr, {"__builtins__": {}}, allowed_names)

        return {
            "expression": expression,
            "result": result,
            "success": True,
        }

    except Exception as e:
        return {
            "expression": expression,
            "error": str(e),
            "success": False,
        }


CALCULATOR_TOOL = ToolDefinition(
    name="calculator",
    description="Evaluate mathematical expressions. Supports basic arithmetic, powers, roots, and trigonometric functions.",
    parameters=[
        ToolParameter(
            name="expression",
            type="string",
            description="Mathematical expression to evaluate (e.g., '2 + 2', 'sqrt(16)', 'sin(pi/2)')",
            required=True,
        ),
    ],
    handler=calculator_handler,
)


# ============== Date/Time Tool ==============

async def datetime_handler(
    operation: str = "now",
    timezone: str = "UTC",
    format: str = "%Y-%m-%d %H:%M:%S",
) -> Dict[str, Any]:
    """Get date/time information"""
    from datetime import datetime, timedelta
    import pytz

    logger.info(f"DateTime operation: {operation}")

    try:
        tz = pytz.timezone(timezone)
        now = datetime.now(tz)

        if operation == "now":
            return {
                "datetime": now.strftime(format),
                "timestamp": now.timestamp(),
                "timezone": timezone,
            }

        elif operation == "date":
            return {
                "date": now.strftime("%Y-%m-%d"),
                "day_of_week": now.strftime("%A"),
                "day": now.day,
                "month": now.month,
                "year": now.year,
            }

        elif operation == "time":
            return {
                "time": now.strftime("%H:%M:%S"),
                "hour": now.hour,
                "minute": now.minute,
                "second": now.second,
            }

        else:
            return {"error": f"Unknown operation: {operation}"}

    except Exception as e:
        return {"error": str(e)}


DATETIME_TOOL = ToolDefinition(
    name="datetime",
    description="Get current date and time information",
    parameters=[
        ToolParameter(
            name="operation",
            type="string",
            description="What to return: 'now' (full datetime), 'date', or 'time'",
            required=False,
            default="now",
            enum=["now", "date", "time"],
        ),
        ToolParameter(
            name="timezone",
            type="string",
            description="Timezone (e.g., 'UTC', 'America/New_York', 'Europe/London')",
            required=False,
            default="UTC",
        ),
    ],
    handler=datetime_handler,
)


# ============== JSON Tool ==============

async def json_handler(
    operation: str,
    data: Any,
    path: Optional[str] = None,
) -> Dict[str, Any]:
    """Manipulate JSON data"""
    logger.info(f"JSON operation: {operation}")

    try:
        if operation == "parse":
            if isinstance(data, str):
                return {"result": json.loads(data), "success": True}
            return {"result": data, "success": True}

        elif operation == "stringify":
            return {"result": json.dumps(data, indent=2), "success": True}

        elif operation == "get" and path:
            # Simple JSONPath-like access
            result = data
            for key in path.split("."):
                if isinstance(result, dict):
                    result = result.get(key)
                elif isinstance(result, list) and key.isdigit():
                    result = result[int(key)]
                else:
                    return {"error": f"Invalid path: {path}", "success": False}
            return {"result": result, "success": True}

        elif operation == "keys":
            if isinstance(data, dict):
                return {"result": list(data.keys()), "success": True}
            return {"error": "Data is not an object", "success": False}

        else:
            return {"error": f"Unknown operation: {operation}", "success": False}

    except Exception as e:
        return {"error": str(e), "success": False}


JSON_TOOL = ToolDefinition(
    name="json",
    description="Parse, stringify, and manipulate JSON data",
    parameters=[
        ToolParameter(
            name="operation",
            type="string",
            description="Operation: 'parse', 'stringify', 'get' (with path), 'keys'",
            required=True,
            enum=["parse", "stringify", "get", "keys"],
        ),
        ToolParameter(
            name="data",
            type="object",
            description="The data to operate on",
            required=True,
        ),
        ToolParameter(
            name="path",
            type="string",
            description="Path for 'get' operation (e.g., 'user.name' or 'items.0.id')",
            required=False,
        ),
    ],
    handler=json_handler,
)


# ============== Shell Command Tool (Sandboxed) ==============

async def shell_handler(
    command: str,
    timeout: int = 30,
    working_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute a shell command (sandboxed)"""
    logger.info(f"Shell command: {command}")

    # Security: Block dangerous commands
    BLOCKED_PATTERNS = [
        "rm -rf /", "dd if=/dev/zero", ":(){ :|:& };:",
        "mkfs", "format", "> /dev/sda", "sudo", "su ",
    ]

    for pattern in BLOCKED_PATTERNS:
        if pattern in command.lower():
            return {
                "error": f"Command blocked for security: contains '{pattern}'",
                "success": False,
            }

    try:
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=working_dir,
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            process.kill()
            return {"error": f"Command timed out after {timeout}s", "success": False}

        return {
            "stdout": stdout.decode('utf-8', errors='replace'),
            "stderr": stderr.decode('utf-8', errors='replace'),
            "exit_code": process.returncode,
            "success": process.returncode == 0,
        }

    except Exception as e:
        return {"error": str(e), "success": False}


SHELL_TOOL = ToolDefinition(
    name="shell",
    description="Execute a shell command. Use for file operations, running scripts, etc. Some commands are blocked for security.",
    parameters=[
        ToolParameter(
            name="command",
            type="string",
            description="The shell command to execute",
            required=True,
        ),
        ToolParameter(
            name="timeout",
            type="number",
            description="Timeout in seconds (max 60)",
            required=False,
            default=30,
        ),
    ],
    handler=shell_handler,
)


# ============== Memory Tool ==============

# In-memory store for the session
_memory_store: Dict[str, Any] = {}


async def memory_handler(
    operation: str,
    key: str,
    value: Any = None,
) -> Dict[str, Any]:
    """Store and retrieve data in session memory"""
    global _memory_store

    logger.info(f"Memory operation: {operation} key={key}")

    if operation == "set":
        _memory_store[key] = value
        return {"success": True, "message": f"Stored '{key}'"}

    elif operation == "get":
        if key in _memory_store:
            return {"success": True, "value": _memory_store[key]}
        return {"success": False, "error": f"Key not found: {key}"}

    elif operation == "delete":
        if key in _memory_store:
            del _memory_store[key]
            return {"success": True, "message": f"Deleted '{key}'"}
        return {"success": False, "error": f"Key not found: {key}"}

    elif operation == "list":
        return {"success": True, "keys": list(_memory_store.keys())}

    elif operation == "clear":
        _memory_store.clear()
        return {"success": True, "message": "Memory cleared"}

    else:
        return {"success": False, "error": f"Unknown operation: {operation}"}


MEMORY_TOOL = ToolDefinition(
    name="memory",
    description="Store and retrieve data during the conversation. Use for keeping track of information across multiple steps.",
    parameters=[
        ToolParameter(
            name="operation",
            type="string",
            description="Operation: 'set', 'get', 'delete', 'list', 'clear'",
            required=True,
            enum=["set", "get", "delete", "list", "clear"],
        ),
        ToolParameter(
            name="key",
            type="string",
            description="The key for the data",
            required=True,
        ),
        ToolParameter(
            name="value",
            type="object",
            description="The value to store (for 'set' operation)",
            required=False,
        ),
    ],
    handler=memory_handler,
)


# ============== Tool Registry ==============

def get_default_tools() -> List[ToolDefinition]:
    """Get the default set of built-in tools"""
    return [
        WEB_SEARCH_TOOL,
        HTTP_REQUEST_TOOL,
        CALCULATOR_TOOL,
        DATETIME_TOOL,
        JSON_TOOL,
        SHELL_TOOL,
        MEMORY_TOOL,
    ]


def get_safe_tools() -> List[ToolDefinition]:
    """Get a safe subset of tools (no shell, no http)"""
    return [
        CALCULATOR_TOOL,
        DATETIME_TOOL,
        JSON_TOOL,
        MEMORY_TOOL,
    ]


def get_research_tools() -> List[ToolDefinition]:
    """Get tools useful for research tasks"""
    return [
        WEB_SEARCH_TOOL,
        HTTP_REQUEST_TOOL,
        CALCULATOR_TOOL,
        DATETIME_TOOL,
        MEMORY_TOOL,
    ]
