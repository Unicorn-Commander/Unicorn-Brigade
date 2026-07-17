"""
Built-in Tools for Agent Execution

Provides a standard set of tools that agents can use for common operations.
"""

import asyncio
import ast
import ipaddress
import json
import logging
import math
import operator as _operator
import os
import socket
import httpx
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from urllib.parse import urlparse

from app.llm.ops_center_client import ToolDefinition, ToolParameter

# BR-4: shared outbound-tool timeout defaults (connect kept short for fast-fail).
try:
    from app.reliability.retry import DEFAULT_TOOL_TIMEOUT, DEFAULT_CONNECT_TIMEOUT
except Exception:  # pragma: no cover - reliability layer should always import
    DEFAULT_TOOL_TIMEOUT, DEFAULT_CONNECT_TIMEOUT = 30.0, 10.0

# Hard ceiling on the model-supplied http_request timeout so a tool call cannot
# request an unbounded (or absurdly long) wait and hang the turn.
MAX_HTTP_REQUEST_TIMEOUT: float = float(os.getenv("HTTP_REQUEST_MAX_TIMEOUT_SECONDS", "60") or 60)

logger = logging.getLogger(__name__)


# ============== BR-0.3: Safe Expression Evaluator (calculator RCE fix) ==============
#
# The calculator tool previously used eval(), which is a Remote Code Execution
# sink even with an emptied __builtins__ (e.g.
# "(1).__class__.__bases__[0].__subclasses__()" reaches arbitrary classes).
# We replace eval() with an AST whitelist walker that evaluates ONLY numeric
# arithmetic plus a fixed set of safe math functions/constants.

# Binary operators explicitly permitted.
_SAFE_BINOPS = {
    ast.Add: _operator.add,
    ast.Sub: _operator.sub,
    ast.Mult: _operator.mul,
    ast.Div: _operator.truediv,
    ast.FloorDiv: _operator.floordiv,
    ast.Mod: _operator.mod,
    ast.Pow: _operator.pow,
}

# Unary operators explicitly permitted (+x / -x).
_SAFE_UNARYOPS = {
    ast.UAdd: _operator.pos,
    ast.USub: _operator.neg,
}

# Guard against CPU/memory DoS via absurd exponents (e.g. 9**9**9).
_MAX_POW_EXPONENT = 1000
# Cap the estimated bit-length of an integer power result so nested exponentiation
# (e.g. ((9**1000)**1000)**1000) and pow(10, 100000000) can't blow up memory/CPU.
_MAX_RESULT_BITS = 10000


def _check_pow_magnitude(base, exp) -> None:
    """Reject integer exponentiation whose result would be enormous. Applies to both
    the ** operator and the whitelisted pow() call. Float exponents hit C's O(1) pow
    (no unbounded int growth), so they only need the exponent cap."""
    if isinstance(exp, bool) or not isinstance(exp, int):
        return
    if abs(exp) > _MAX_POW_EXPONENT:
        raise ValueError("exponent too large")
    if isinstance(base, int) and not isinstance(base, bool):
        if abs(exp) * max(1, base.bit_length()) > _MAX_RESULT_BITS:
            raise ValueError("result magnitude too large")


def _safe_pow(base, exp, mod=None):
    """pow() wrapper: 2-arg integer power is magnitude-checked; 3-arg modular pow
    is intrinsically fast and bounded, so it's allowed through."""
    if mod is None:
        _check_pow_magnitude(base, exp)
        return base ** exp
    return pow(base, exp, mod)


# Fixed whitelist of callable math names. No attribute access, no other names.
_SAFE_FUNCTIONS = {
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
    "sum": sum,
    "pow": _safe_pow,
    "len": len,
    "sqrt": math.sqrt,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "log": math.log,
    "log10": math.log10,
    "exp": math.exp,
}

# Fixed whitelist of constant names.
_SAFE_NAMES = {
    "pi": math.pi,
    "e": math.e,
}


def _safe_eval_node(node: ast.AST):
    """Recursively evaluate a whitelisted AST node. Raises ValueError on anything else."""
    if isinstance(node, ast.Expression):
        return _safe_eval_node(node.body)

    if isinstance(node, ast.Constant):
        # Reject bool (subclass of int) and anything non-numeric (str, bytes, ...).
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float, complex)):
            raise ValueError("only numeric constants are allowed")
        return node.value

    if isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type not in _SAFE_BINOPS:
            raise ValueError(f"operator {op_type.__name__} is not allowed")
        left = _safe_eval_node(node.left)
        right = _safe_eval_node(node.right)
        if op_type is ast.Pow:
            _check_pow_magnitude(left, right)
        return _SAFE_BINOPS[op_type](left, right)

    if isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type not in _SAFE_UNARYOPS:
            raise ValueError(f"unary operator {op_type.__name__} is not allowed")
        return _SAFE_UNARYOPS[op_type](_safe_eval_node(node.operand))

    if isinstance(node, ast.Call):
        if node.keywords:
            raise ValueError("keyword arguments are not allowed")
        if not isinstance(node.func, ast.Name):
            raise ValueError("only direct calls to whitelisted functions are allowed")
        fname = node.func.id
        if fname not in _SAFE_FUNCTIONS:
            raise ValueError(f"function '{fname}' is not allowed")
        # ast.Starred args (f(*x)) fall through _safe_eval_node and are rejected.
        args = [_safe_eval_node(arg) for arg in node.args]
        return _SAFE_FUNCTIONS[fname](*args)

    if isinstance(node, ast.Name):
        if node.id not in _SAFE_NAMES:
            raise ValueError(f"name '{node.id}' is not allowed")
        return _SAFE_NAMES[node.id]

    raise ValueError(f"disallowed expression element: {type(node).__name__}")


def safe_eval_expression(expression: str):
    """Safely evaluate an arithmetic expression. Raises ValueError on unsafe input."""
    tree = ast.parse(expression, mode="eval")
    return _safe_eval_node(tree)


# ============== BR-0.4: SSRF Egress Guard ==============
#
# Tools that fetch a caller-supplied URL (http_request, url_preview, screenshot)
# can be abused for Server-Side Request Forgery: reaching localhost, RFC1918
# hosts, or the cloud metadata endpoint (169.254.169.254). validate_url_egress()
# resolves the target hostname and blocks any address that is not a genuine
# public unicast address.


def _ip_is_blocked(ip_str: str) -> bool:
    """True if an IP is loopback / private / link-local / reserved / unspecified / multicast."""
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        # Unparseable address -> block (fail closed).
        return True
    return (
        ip.is_loopback
        or ip.is_private          # RFC1918 (IPv4) + ULA fc00::/7 (IPv6)
        or ip.is_link_local       # 169.254.0.0/16 incl. cloud metadata + fe80::/10
        or ip.is_reserved
        or ip.is_unspecified      # 0.0.0.0 / ::
        or ip.is_multicast
    )


def resolve_and_validate_egress(
    url: str,
) -> Tuple[bool, Optional[str], Optional[str], Optional[str]]:
    """
    SSRF guard that ALSO returns the connection pin.

    Returns ``(allowed, error_message, hostname, pinned_ip)``:

    - ``allowed`` / ``error_message`` mirror :func:`validate_url_egress`.
    - ``hostname`` is the parsed host (preserved for the Host header + TLS SNI).
    - ``pinned_ip`` is a validated address the caller should CONNECT to. It is
      ``None`` when the host is already an IP literal (no DNS — connect normally)
      and on any failure.

    Resolving ONCE here and connecting to ``pinned_ip`` closes the DNS-rebinding
    TOCTOU: a hostile resolver could otherwise pass this guard and then, when
    httpx (or any client) re-resolves at connect time, point the socket at
    127.0.0.1 / 169.254.169.254. See :class:`_PinnedIPTransport`.
    """
    try:
        parsed = urlparse(url)
    except Exception:
        return False, "invalid URL", None, None

    scheme = (parsed.scheme or "").lower()
    if scheme not in ("http", "https"):
        return False, f"blocked URL scheme '{scheme or 'none'}' (only http/https allowed)", None, None

    hostname = parsed.hostname
    if not hostname:
        return False, "URL has no host", None, None

    # If the host is already an IP literal, check it directly (no DNS, no pin).
    try:
        ipaddress.ip_address(hostname)
        if _ip_is_blocked(hostname):
            return False, f"blocked: {hostname} is a private/reserved address", None, None
        return True, None, hostname, None
    except ValueError:
        pass

    # Resolve the hostname to every address it maps to and block if ANY is
    # internal. The FIRST validated address becomes the connection pin.
    port = parsed.port or (443 if scheme == "https" else 80)
    try:
        infos = socket.getaddrinfo(hostname, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        return False, f"DNS resolution failed for {hostname}: {exc}", None, None

    if not infos:
        return False, f"no addresses resolved for {hostname}", None, None

    pinned_ip: Optional[str] = None
    for info in infos:
        ip_str = info[4][0]
        if _ip_is_blocked(ip_str):
            return False, f"blocked: {hostname} resolves to non-public address {ip_str}", None, None
        if pinned_ip is None:
            pinned_ip = ip_str

    return True, None, hostname, pinned_ip


def validate_url_egress(url: str) -> Tuple[bool, Optional[str]]:
    """
    SSRF guard. Returns (allowed, error_message).

    Rejects non-http(s) schemes and any URL whose host resolves to a
    loopback / private / link-local (169.254/16 metadata) / reserved /
    unspecified address. Callers should return a clean tool error (not raise)
    when allowed is False.

    Thin wrapper over :func:`resolve_and_validate_egress` — use that directly (or
    :func:`build_egress_guarded_transport`) when you also need to PIN the
    connection to the validated IP.
    """
    allowed, error, _host, _pinned_ip = resolve_and_validate_egress(url)
    return allowed, error


class _PinnedIPTransport(httpx.AsyncHTTPTransport):
    """httpx transport that pins the TCP connection to a pre-validated IP.

    Closes the SSRF DNS-rebinding TOCTOU: the egress guard resolves + validates
    the host ONCE, and this transport connects to THAT ip instead of letting
    httpx re-resolve at connect time. The original hostname is preserved for the
    Host header (httpx already derived it from the request URL) and for TLS SNI +
    certificate verification via the ``sni_hostname`` request extension, so HTTPS
    still verifies against the real hostname rather than the raw IP.
    """

    def __init__(self, expected_host: str, pinned_ip: str, **kwargs):
        super().__init__(**kwargs)
        self._expected_host = (expected_host or "").lower()
        self._pinned_ip = pinned_ip

    async def handle_async_request(self, request: "httpx.Request") -> "httpx.Response":
        host = (request.url.host or "").lower()
        if host == self._expected_host:
            # Defense in depth: never connect to a blocked IP even if pinned.
            if _ip_is_blocked(self._pinned_ip):
                raise httpx.ConnectError(
                    f"SSRF guard: pinned address {self._pinned_ip} is private/reserved"
                )
            request.extensions = dict(request.extensions)
            request.extensions.setdefault("sni_hostname", request.url.host)
            # Connect to the validated IP; Host header + SNI keep the real host.
            request.url = request.url.copy_with(host=self._pinned_ip)
        else:
            # Host changed unexpectedly (e.g. a redirect slipped past a caller
            # that did not disable them). Re-validate and refuse anything
            # internal rather than connecting blind.
            allowed, error = validate_url_egress(str(request.url))
            if not allowed:
                raise httpx.ConnectError(f"SSRF guard: {error}")
        return await super().handle_async_request(request)


def build_egress_guarded_transport(
    url: str, **transport_kwargs
) -> Tuple[Optional[httpx.AsyncBaseTransport], Optional[str]]:
    """Validate egress for ``url`` and return a DNS-pinned httpx transport.

    Returns ``(transport, None)`` when the URL is allowed, or ``(None, reason)``
    when it is blocked (caller should return a clean tool error, not raise).

    Build the client with ``follow_redirects=False`` so the pin (tied to the
    original host) cannot be bypassed by a redirect to another host::

        transport, reason = build_egress_guarded_transport(url)
        if transport is None:
            return {"error": reason, "success": False}
        async with httpx.AsyncClient(transport=transport, follow_redirects=False) as client:
            ...
    """
    allowed, error, host, pinned_ip = resolve_and_validate_egress(url)
    if not allowed:
        return None, error
    if pinned_ip is None:
        # Host was an IP literal (already validated) — no DNS, nothing to pin.
        return httpx.AsyncHTTPTransport(**transport_kwargs), None
    return _PinnedIPTransport(expected_host=host, pinned_ip=pinned_ip, **transport_kwargs), None


# ============== Web Search Configuration ==============

# Search provider config from environment
SEARCH_PROVIDER = os.getenv("SEARCH_PROVIDER", "serper")  # serper, searxng, brightdata
# No hardcoded default: a source-code secret is treated as leaked (repo is mirrored
# to a public -OSS repo). web_search degrades gracefully when this is unset.
SERPER_API_KEY = os.getenv("SERPER_API_KEY", "")
SEARXNG_URL = os.getenv("SEARXNG_URL", "http://localhost:8889")
BRIGHTDATA_API_KEY = os.getenv("BRIGHTDATA_API_KEY", "")
BRIGHTDATA_ZONE = os.getenv("BRIGHTDATA_ZONE", "serp")


async def _search_serper(query: str, num_results: int = 5) -> Dict[str, Any]:
    """Search via Serper.dev (Google SERP API)"""
    # Degrade gracefully instead of firing a request with an empty API key
    # (which would 4xx) — return a clean, actionable tool error.
    if not SERPER_API_KEY:
        logger.warning("web_search: SERPER_API_KEY is not configured; serper provider unavailable")
        return {
            "query": query,
            "provider": "serper",
            "results": [],
            "error": "Web search unavailable: SERPER_API_KEY is not configured.",
            "success": False,
        }
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

    # BR-0.4 / SSRF hardening: resolve + validate the host ONCE and pin the
    # connection to the validated IP (DNS-rebinding TOCTOU fix). The returned
    # transport connects to the checked address while preserving Host + TLS SNI,
    # so a hostile resolver cannot pass validation then rebind to 127.0.0.1 /
    # 169.254.169.254 at connect time.
    transport, block_reason = build_egress_guarded_transport(url)
    if transport is None:
        logger.warning(f"http_request blocked by SSRF guard: {url} ({block_reason})")
        return {
            "error": f"Request blocked by SSRF guard: {block_reason}",
            "success": False,
        }

    # BR-4: clamp the model-supplied timeout to a sane range so a tool call
    # cannot hang the turn indefinitely, and always attach an explicit connect
    # timeout for fast-fail on unreachable hosts.
    try:
        req_timeout = float(timeout) if timeout else DEFAULT_TOOL_TIMEOUT
    except (TypeError, ValueError):
        req_timeout = DEFAULT_TOOL_TIMEOUT
    req_timeout = min(max(1.0, req_timeout), MAX_HTTP_REQUEST_TIMEOUT)
    total_timeout = httpx.Timeout(req_timeout, connect=min(DEFAULT_CONNECT_TIMEOUT, req_timeout))

    try:
        # follow_redirects=False so a redirect cannot bounce us to an internal
        # host that the guard never validated (redirect-based SSRF bypass), and
        # so the pinned transport's host binding cannot be sidestepped.
        async with httpx.AsyncClient(
            timeout=total_timeout, follow_redirects=False, transport=transport
        ) as client:
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

    try:
        # Allow caret as an exponent operator, as before.
        clean_expr = expression.replace("^", "**")

        # BR-0.3: AST whitelist evaluation instead of eval(). Only numeric
        # arithmetic and a fixed set of math functions/constants are permitted;
        # attribute access, arbitrary names, and arbitrary calls are rejected.
        result = safe_eval_expression(clean_expr)

        return {
            "expression": expression,
            "result": result,
            "success": True,
        }

    except SyntaxError as e:
        return {
            "expression": expression,
            "error": f"Invalid expression: {e}",
            "success": False,
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


# ============== Shell Command Tool (SANDBOXED VIA DOCKER) ==============
#
# SECURITY NOTE: The shell tool executes commands in a Docker container,
# NOT on the host system. This is critical for preventing RCE attacks.
#
# The old implementation used asyncio.create_subprocess_shell which would
# execute commands directly on the host - this was a critical security flaw.
#

async def shell_handler(
    command: str,
    timeout: int = 30,
    working_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Execute a shell command in a sandboxed Docker container.

    SECURITY: This runs in an isolated container, not on the host.
    """
    logger.info(f"Shell command (sandboxed): {command}")

    # Import sandbox executor (lazy import to avoid circular deps)
    try:
        from app.mcp.sandbox_executor import sandbox_executor
    except ImportError:
        return {
            "error": "Shell execution disabled: sandbox executor not available",
            "success": False,
        }

    # Check if Docker is available
    docker_available = await sandbox_executor.check_docker()
    if not docker_available:
        return {
            "error": "Shell execution disabled: Docker sandbox not available. "
                     "Use the code sandbox API or enable Docker.",
            "success": False,
        }

    # Execute in sandbox
    try:
        result = await sandbox_executor.execute(
            code=command,
            language="bash",
            timeout=min(timeout, 60),  # Cap at 60s for safety
        )

        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.exit_code,
            "success": result.success,
            "sandbox": "docker",  # Indicate this ran in sandbox
        }

    except Exception as e:
        logger.error(f"Sandboxed shell execution failed: {e}")
        return {"error": str(e), "success": False}


SHELL_TOOL = ToolDefinition(
    name="shell",
    description="Execute a shell command in a sandboxed Docker container. Use for running scripts, installing packages, etc. Commands run in isolation, not on the host system.",
    parameters=[
        ToolParameter(
            name="command",
            type="string",
            description="The shell command to execute (runs in Docker container)",
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
    """
    Get the default set of built-in tools.

    NOTE: Shell tool is excluded by default for security reasons.
    Use get_all_tools() if shell access is needed.
    """
    return [
        WEB_SEARCH_TOOL,
        HTTP_REQUEST_TOOL,
        CALCULATOR_TOOL,
        DATETIME_TOOL,
        JSON_TOOL,
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


def get_all_tools() -> List[ToolDefinition]:
    """
    Get all built-in tools including shell (sandboxed).

    WARNING: Only use when Docker sandbox is available.
    Shell commands run in containers, not on host.
    """
    return [
        WEB_SEARCH_TOOL,
        HTTP_REQUEST_TOOL,
        CALCULATOR_TOOL,
        DATETIME_TOOL,
        JSON_TOOL,
        SHELL_TOOL,
        MEMORY_TOOL,
    ]
