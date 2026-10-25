"""Lazy, schema-driven clients for tools owned by sibling applications.

Sibling tools are deliberately not imported into the static tool registry.  An
agent reference is enough to make a name valid, but the sibling's current
schema is fetched only when that name is requested.  This keeps agent CRUD and
prune operations honest when a sibling is temporarily unavailable while still
giving the model the real input schema when the tool can be used.
"""

from __future__ import annotations

import json
import logging
import os
import time
from collections.abc import Collection, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

from app.auth.tool_scope import parse_orgs
from app.llm import knowledge_ops_tools as knowledge_auth
from app.llm.ops_center_client import ToolDefinition, ToolParameter

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).resolve().parents[1] / "data" / "sibling_apps.json"
_FALSE_ENV_VALUES = {"0", "false", "no", "off"}
_SCHEMA_CACHE_FAILURE_SECONDS = 5.0
_SCHEMA_CACHE_TTL_SECONDS = 600.0
_HARD_TIMEOUT_SECONDS = 10.0


@dataclass(frozen=True)
class SiblingAppConfig:
    """Configuration for one sibling application's tool transport."""

    name: str
    namespace: str
    transport: str
    url_env: str
    default_url: str
    token_env: str | None
    token_required: bool
    timeout: float
    tools: frozenset[str] = field(default_factory=frozenset)
    allow_writes: frozenset[str] = field(default_factory=frozenset)
    aliases: dict[str, str] = field(default_factory=dict)
    orgs: tuple[str, ...] | None = None


@dataclass(frozen=True)
class ToolStatus:
    """Machine-readable status for one stored agent tool reference."""

    tool: str
    status: str
    reason: str | None = None
    app: str | None = None
    canonical: str | None = None

    def as_dict(self) -> dict[str, str]:
        result = {"tool": self.tool, "status": self.status}
        if self.reason:
            result["reason"] = self.reason
        if self.app:
            result["app"] = self.app
        if self.canonical:
            result["canonical"] = self.canonical
        return result


@dataclass(frozen=True)
class _SiblingToolSpec:
    canonical_name: str
    description: str
    parameters: tuple[ToolParameter, ...]
    method: str | None = None
    path: str | None = None


@dataclass(frozen=True)
class _SchemaCacheEntry:
    fingerprint: tuple[str, bool, bool]
    specs: dict[str, _SiblingToolSpec]
    expires_at: float
    failure_reason: str | None = None
    failure_detail: str | None = None


def _env_enabled(name: str, default: str = "1") -> bool:
    return os.getenv(name, default).strip().lower() not in _FALSE_ENV_VALUES


def sibling_app_tools_enabled() -> bool:
    """Return whether dynamic sibling tools are enabled for this process."""
    return _env_enabled("SIBLING_APP_TOOLS_ENABLED")


def _canonical_name(namespace: str, name: str) -> str:
    name = str(name).strip()
    return name if "." in name else f"{namespace}.{name}"


def _load_aliases(namespace: str, raw_aliases: object) -> dict[str, str]:
    """Accept the JSON list form and tolerate a mapping for hand-edited config."""
    aliases: dict[str, str] = {}
    if isinstance(raw_aliases, Mapping):
        items = raw_aliases.items()
    elif isinstance(raw_aliases, list | tuple):
        items = []
        for item in raw_aliases:
            if isinstance(item, Mapping):
                alias = item.get("alias") or item.get("name")
                target = item.get("target") or item.get("canonical")
                if alias and target:
                    items.append((alias, target))
            elif isinstance(item, list | tuple) and len(item) == 2:
                items.append((item[0], item[1]))
            elif isinstance(item, str):
                items.append((item, _canonical_name(namespace, item)))
    else:
        items = []

    for alias, target in items:
        alias_text = str(alias).strip()
        target_text = _canonical_name(namespace, str(target))
        if alias_text and target_text:
            aliases[alias_text] = target_text
    return aliases


# A deployment can add sibling apps of its own without replacing the bundled
# file: BRIGADE_SIBLING_APPS_EXTRA names one or more JSON files (os.pathsep-
# separated) in the same list format. Their entries are merged after the bundled
# ones, and an entry whose name or namespace matches a bundled app replaces it.
# This keeps deployment-private apps (and their URLs) out of the repository,
# and the bundled list keeps updating with the image instead of being frozen by
# a bind-mounted copy.
SIBLING_APPS_EXTRA_ENV = "BRIGADE_SIBLING_APPS_EXTRA"
# (name, source file) of each app added by the deployment config, for the startup log.
DEPLOYMENT_APPS: list[tuple[str, str]] = []


def _read_config_list(path: Path, *, extra: bool) -> list[Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        if extra:
            # Configured but unreadable: say so loudly, keep the bundled apps.
            logger.error("deployment sibling-app config %s unavailable: %s", path, type(exc).__name__)
        else:
            logger.warning("sibling-app config unavailable: %s", type(exc).__name__)
        return []
    if not isinstance(raw, list):
        logger.error("sibling-app config %s must be a list", path) if extra else logger.warning(
            "sibling-app config must be a list"
        )
        return []
    return raw


def _config_items() -> list[Any]:
    """The bundled sibling-app entries, plus any deployment extras."""
    items = list(_read_config_list(CONFIG_PATH, extra=False))
    DEPLOYMENT_APPS.clear()
    extra_paths = [p.strip() for p in os.getenv(SIBLING_APPS_EXTRA_ENV, "").split(os.pathsep) if p.strip()]
    for extra_path in extra_paths:
        for entry in _read_config_list(Path(extra_path), extra=True):
            if not isinstance(entry, Mapping):
                continue
            keys = {str(entry.get("name") or ""), str(entry.get("namespace") or "")} - {""}
            replaced = [
                i for i, item in enumerate(items)
                if isinstance(item, Mapping) and keys & {str(item.get("name") or ""), str(item.get("namespace") or "")}
            ]
            for i in reversed(replaced):
                logger.warning("deployment sibling-app config replaces bundled app %s", items[i].get("name"))
                del items[i]
            items.append(entry)
            DEPLOYMENT_APPS.append((str(entry.get("name")), extra_path))
            logger.info("deployment sibling-app config adds %s from %s", entry.get("name"), extra_path)
    return items


def _load_configs() -> tuple[SiblingAppConfig, ...]:
    configs: list[SiblingAppConfig] = []
    for item in _config_items():
        if not isinstance(item, Mapping):
            continue
        try:
            name = str(item["name"])
            namespace = str(item["namespace"])
            transport = str(item["transport"])
            url_env = str(item["url_env"])
            default_url = str(item.get("default_url") or "")
            token_env_value = item.get("token_env")
            token_env = str(token_env_value) if token_env_value else None
            token_required = bool(item.get("token_required", transport == "mcp"))
            timeout = max(0.1, float(item.get("timeout", 15)))
            configured_tools = frozenset(
                _canonical_name(namespace, str(tool))
                for tool in (item.get("tools") or [])
            )
            allow_writes = frozenset(
                _canonical_name(namespace, str(tool))
                for tool in (item.get("allow_writes") or [])
            )
            aliases = _load_aliases(namespace, item.get("aliases") or [])
        except (KeyError, TypeError, ValueError):
            logger.warning("invalid sibling-app config entry skipped")
            continue
        configs.append(
            SiblingAppConfig(
                name=name,
                namespace=namespace,
                transport=transport,
                url_env=url_env,
                default_url=default_url,
                token_env=token_env,
                token_required=token_required,
                timeout=timeout,
                tools=configured_tools,
                allow_writes=allow_writes,
                aliases=aliases,
                orgs=parse_orgs(item.get("orgs"), source=f"sibling-app:{name}"),
            )
        )
    return tuple(configs)


SIBLING_APPS = _load_configs()
_APPS_BY_NAMESPACE = {app.namespace: app for app in SIBLING_APPS}
_APPS_BY_NAME = {app.name: app for app in SIBLING_APPS}
_ALIASES: dict[str, str] = {}
_CANONICAL_TO_APP: dict[str, SiblingAppConfig] = {}
for _app in SIBLING_APPS:
    _ALIASES.update(_app.aliases)
    for _tool_name in _app.tools:
        _CANONICAL_TO_APP[_tool_name] = _app

# Tests and health checks can clear this without reaching into the transport.
_SCHEMA_CACHE: dict[str, _SchemaCacheEntry] = {}


def clear_schema_cache() -> None:
    """Clear successful and failed schema fetches."""
    _SCHEMA_CACHE.clear()


def configured_sibling_tool_names() -> set[str]:
    """Return canonical and legacy names known from static configuration."""
    names = set(_CANONICAL_TO_APP)
    names.update(_ALIASES)
    return names


def canonical_sibling_tool_name(name: str) -> str | None:
    """Map an alias to its canonical name, or return a configured canonical name."""
    value = str(name)
    if value in _ALIASES:
        return _ALIASES[value]
    if value in _CANONICAL_TO_APP:
        return value
    return None


def _app_url(app: SiblingAppConfig) -> str:
    return os.getenv(app.url_env, app.default_url).strip()


def _app_token(app: SiblingAppConfig) -> str:
    return os.getenv(app.token_env, "").strip() if app.token_env else ""


def _is_knowledge_app(app: SiblingAppConfig) -> bool:
    return app.namespace == "knowledge"


def _knowledge_oidc_configured(app: SiblingAppConfig) -> bool:
    return _is_knowledge_app(app) and knowledge_auth.knowledge_ops_oidc_configured()


def _request_timeout(app: SiblingAppConfig) -> float:
    configured_hard_limit = os.getenv(
        "SIBLING_APP_HARD_TIMEOUT_SECONDS", str(_HARD_TIMEOUT_SECONDS)
    )
    try:
        hard_limit = max(0.1, float(configured_hard_limit))
    except ValueError:
        hard_limit = _HARD_TIMEOUT_SECONDS
    return min(app.timeout, hard_limit)


def _headers(
    app: SiblingAppConfig,
    *,
    token: str = "",
    streamable: bool = False,
) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if streamable:
        headers["Accept"] = "application/json, text/event-stream"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _parse_streamable_response(body: str) -> dict[str, Any]:
    """Parse either plain JSON or a single SSE-framed JSON-RPC response."""
    text = (body or "").strip()
    if not text:
        raise ValueError("empty response")
    if text.startswith("{"):
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else {"result": parsed}
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("data:"):
            parsed = json.loads(line[len("data:") :].strip())
            return parsed if isinstance(parsed, dict) else {"result": parsed}
    raise ValueError("missing JSON-RPC data")


def _schema_properties(schema: object) -> tuple[dict[str, Any], set[str]]:
    if not isinstance(schema, Mapping):
        return {}, set()
    properties = schema.get("properties")
    if not isinstance(properties, Mapping):
        properties = {}
    required = schema.get("required")
    required_names = {str(name) for name in required} if isinstance(required, list) else set()
    return dict(properties), required_names


def _parameter_type(schema: Mapping[str, Any]) -> str:
    value = schema.get("type")
    if isinstance(value, list):
        value = next((item for item in value if item != "null"), value[0] if value else "string")
    if not value and isinstance(schema.get("anyOf"), list):
        for option in schema["anyOf"]:
            if isinstance(option, Mapping) and option.get("type"):
                value = option["type"]
                break
    return str(value or "string")


def _parameters_from_schema(schema: object) -> tuple[ToolParameter, ...]:
    properties, required = _schema_properties(schema)
    parameters: list[ToolParameter] = []
    for name, raw_property in properties.items():
        prop = raw_property if isinstance(raw_property, Mapping) else {}
        parameter_type = _parameter_type(prop)
        enum = prop.get("enum")
        enum_values = list(enum) if isinstance(enum, list) else None
        items = prop.get("items") if isinstance(prop.get("items"), Mapping) else None
        parameters.append(
            ToolParameter(
                name=str(name),
                type=parameter_type,
                description=str(prop.get("description") or ""),
                required=str(name) in required,
                enum=enum_values,
                default=prop.get("default"),
                items=dict(items) if items else None,
            )
        )
    return tuple(parameters)


def _normalise_read_only(value: object) -> bool:
    if isinstance(value, str):
        return value.strip().lower() not in _FALSE_ENV_VALUES
    return bool(value) if value is not None else True


def _raw_manifest_tools(payload: object) -> list[Mapping[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, Mapping)]
    if not isinstance(payload, Mapping):
        return []
    raw_tools = payload.get("tools") or payload.get("mcp_tools") or []
    if isinstance(raw_tools, Mapping):
        return [
            {"name": name, **(value if isinstance(value, Mapping) else {})}
            for name, value in raw_tools.items()
        ]
    if isinstance(raw_tools, list):
        return [item for item in raw_tools if isinstance(item, Mapping)]
    return []


def _tool_spec(app: SiblingAppConfig, raw: Mapping[str, Any]) -> _SiblingToolSpec | None:
    raw_name = raw.get("name")
    if not raw_name:
        return None
    canonical = _canonical_name(app.namespace, str(raw_name))
    if app.tools and canonical not in app.tools:
        return None

    read_only = _normalise_read_only(raw.get("read_only", raw.get("readOnly", True)))
    if not read_only and canonical not in app.allow_writes:
        return None

    input_schema = raw.get("inputSchema") or raw.get("input_schema") or {}
    description = str(raw.get("description") or f"Tool provided by {app.name}.")
    rest = raw.get("rest") if isinstance(raw.get("rest"), Mapping) else {}
    method = str(rest.get("method") or raw.get("method") or "POST").upper()
    path = rest.get("path") or raw.get("path")
    return _SiblingToolSpec(
        canonical_name=canonical,
        description=description,
        parameters=_parameters_from_schema(input_schema),
        method=method if app.transport == "rest-manifest" else None,
        path=str(path) if path else None,
    )


def _mcp_specs(app: SiblingAppConfig, payload: Mapping[str, Any]) -> dict[str, _SiblingToolSpec]:
    result = payload.get("result") if isinstance(payload.get("result"), Mapping) else payload
    raw_tools = result.get("tools", []) if isinstance(result, Mapping) else []
    if not isinstance(raw_tools, list):
        return {}
    specs: dict[str, _SiblingToolSpec] = {}
    for raw in raw_tools:
        if not isinstance(raw, Mapping):
            continue
        spec = _tool_spec(app, raw)
        if spec:
            specs[spec.canonical_name] = spec
    return specs


def _manifest_url(app: SiblingAppConfig, base_url: str) -> str:
    if base_url.endswith(".json"):
        return base_url
    return f"{base_url.rstrip('/')}/.well-known/mcps.json"


def _fetch_schema(app: SiblingAppConfig, url: str, headers: dict[str, str]) -> dict[str, _SiblingToolSpec]:
    timeout = _request_timeout(app)
    with httpx.Client(timeout=httpx.Timeout(timeout), trust_env=False) as client:
        if app.transport == "mcp":
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/list",
                "params": {},
            }
            response = client.post(url, headers=headers, json=payload)
            if response.status_code >= 400:
                raise RuntimeError(f"HTTP {response.status_code}")
            parsed = _parse_streamable_response(response.text)
            if parsed.get("error"):
                raise RuntimeError("MCP tools/list error")
            return _mcp_specs(app, parsed)

        response = client.get(_manifest_url(app, url), headers=headers)
        if response.status_code >= 400:
            raise RuntimeError(f"HTTP {response.status_code}")
        return {
            spec.canonical_name: spec
            for raw in _raw_manifest_tools(response.json())
            if (spec := _tool_spec(app, raw)) is not None
        }


def _schema_failure(
    app: SiblingAppConfig,
    fingerprint: tuple[str, bool, bool],
    reason: str,
    detail: str,
) -> _SchemaCacheEntry:
    entry = _SchemaCacheEntry(
        fingerprint=fingerprint,
        specs={},
        expires_at=time.monotonic() + _SCHEMA_CACHE_FAILURE_SECONDS,
        failure_reason=reason,
        failure_detail=detail,
    )
    _SCHEMA_CACHE[app.name] = entry
    return entry


def _load_schema(app: SiblingAppConfig) -> _SchemaCacheEntry:
    url = _app_url(app)
    token = _app_token(app)
    oidc_configured = _knowledge_oidc_configured(app)
    fingerprint = (url, bool(token), oidc_configured)
    now = time.monotonic()
    cached = _SCHEMA_CACHE.get(app.name)
    if cached and cached.fingerprint == fingerprint and cached.expires_at > now:
        return cached

    if not sibling_app_tools_enabled():
        return _schema_failure(app, fingerprint, "unreachable", "disabled")
    if not url:
        return _schema_failure(app, fingerprint, "unreachable", "no URL configured")
    if app.token_required and not token and not oidc_configured:
        return _schema_failure(app, fingerprint, "no_token", "token not configured")

    try:
        schema_token = token
        if oidc_configured:
            schema_token, _ = knowledge_auth.get_knowledge_ops_bearer_sync(
                route=f"{app.namespace}.manifest",
                static_token=token,
            )
            if app.token_required and not schema_token:
                return _schema_failure(
                    app,
                    fingerprint,
                    "no_token",
                    "Knowledge-Ops OIDC credential unavailable",
                )
        specs = _fetch_schema(
            app,
            url,
            _headers(app, token=schema_token, streamable=app.transport == "mcp"),
        )
    except httpx.TimeoutException:
        return _schema_failure(app, fingerprint, "unreachable", "request timed out")
    except (httpx.HTTPError, OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        return _schema_failure(app, fingerprint, "unreachable", type(exc).__name__)
    except Exception as exc:  # noqa: BLE001 - schema discovery must not break agent CRUD
        return _schema_failure(app, fingerprint, "unreachable", type(exc).__name__)

    entry = _SchemaCacheEntry(
        fingerprint=fingerprint,
        specs=specs,
        expires_at=now + _SCHEMA_CACHE_TTL_SECONDS,
    )
    _SCHEMA_CACHE[app.name] = entry
    return entry


def _status_unknown(name: str, app: SiblingAppConfig | None = None) -> ToolStatus:
    return ToolStatus(
        tool=name,
        status="unknown",
        reason="unknown_tool" if app else None,
        app=app.name if app else None,
        canonical=canonical_sibling_tool_name(name),
    )


def resolve_sibling_tool(name: str) -> tuple[ToolDefinition | None, ToolStatus]:
    """Resolve a configured name and lazily discover its current schema."""
    canonical = canonical_sibling_tool_name(name)
    if not canonical:
        return None, _status_unknown(name)
    app = _CANONICAL_TO_APP.get(canonical)
    if app is None:
        return None, _status_unknown(name)
    if not sibling_app_tools_enabled():
        return None, ToolStatus(
            tool=name,
            status="unavailable",
            reason="unreachable",
            app=app.name,
            canonical=canonical,
        )

    cached = _load_schema(app)
    if cached.failure_reason:
        return None, ToolStatus(
            tool=name,
            status="unavailable",
            reason=cached.failure_reason,
            app=app.name,
            canonical=canonical,
        )
    spec = cached.specs.get(canonical)
    if spec is None:
        return None, _status_unknown(name, app)

    async def handler(**kwargs: Any) -> dict[str, Any] | Any:
        return await _invoke(app, spec, dict(kwargs))

    handler.__name__ = f"{canonical.replace('.', '_')}_handler"
    definition = ToolDefinition(
        name=canonical,
        description=spec.description,
        parameters=list(spec.parameters),
        handler=handler,
    )
    return definition, ToolStatus(
        tool=name,
        status="resolved",
        app=app.name,
        canonical=canonical,
    )


def classify_tool_names(
    names: Collection[str] | None,
    *,
    known_names: Collection[str] | None = None,
) -> list[dict[str, str]]:
    """Report each name as resolved, unavailable(reason), or unknown.

    ``known_names`` is the caller's static executable registry.  It lets the
    same function report built-ins as resolved without importing the resolver
    back into this module.
    """
    known = {str(name) for name in (known_names or [])}
    statuses: list[dict[str, str]] = []
    for raw_name in names or []:
        name = str(raw_name)
        if name in known:
            statuses.append({"tool": name, "status": "resolved"})
            continue
        _, status = resolve_sibling_tool(name)
        statuses.append(status.as_dict())
    return statuses


def _error_result(app: SiblingAppConfig, tool: str, error: str) -> dict[str, Any]:
    return {
        "success": False,
        "error": error[:300],
        "app": app.name,
        "tool": tool,
    }


def _content_result(result: object) -> object:
    if not isinstance(result, Mapping):
        return result
    if "structuredContent" in result:
        return result["structuredContent"]
    content = result.get("content")
    if not isinstance(content, list):
        return result
    if len(content) != 1 or not isinstance(content[0], Mapping):
        return content
    text = content[0].get("text")
    if not isinstance(text, str):
        return content
    try:
        return json.loads(text)
    except (TypeError, json.JSONDecodeError):
        return text


def _mcp_call_result(app: SiblingAppConfig, tool: str, parsed: Mapping[str, Any]) -> object:
    if parsed.get("error"):
        return _error_result(app, tool, "MCP tools/call returned an error")
    result = parsed.get("result", parsed)
    if isinstance(result, Mapping) and result.get("isError"):
        return _error_result(app, tool, "sibling tool returned an error")
    return _content_result(result)


def _with_knowledge_oidc_health(app: SiblingAppConfig, result: object) -> object:
    if _is_knowledge_app(app) and isinstance(result, dict):
        return knowledge_auth.add_knowledge_ops_oidc_health(result)
    return result


async def _invoke(app: SiblingAppConfig, spec: _SiblingToolSpec, arguments: dict[str, Any]) -> object:
    """Call a sibling tool and always return a model-visible result object."""
    tool = spec.canonical_name
    url = _app_url(app)
    if not url:
        return _error_result(app, tool, "no URL configured")
    if not sibling_app_tools_enabled():
        return _error_result(app, tool, "sibling app tools disabled")

    try:
        if _is_knowledge_app(app):
            static_token = _app_token(app)
            token, uses_oidc = await knowledge_auth.get_knowledge_ops_bearer(
                route=tool,
                static_token=static_token,
            )
            if uses_oidc and not token:
                return _with_knowledge_oidc_health(
                    app,
                    _error_result(app, tool, "knowledge-ops could not obtain an OIDC credential"),
                )
        else:
            token = _app_token(app)
            uses_oidc = False
        if app.token_required and not token:
            return _error_result(app, tool, "token not configured")

        timeout = _request_timeout(app)
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            trust_env=False,
        ) as client:
            if app.transport == "mcp":
                payload = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {"name": tool.split(".", 1)[-1], "arguments": arguments},
                }
                response = await client.post(
                    url,
                    headers=_headers(app, token=token, streamable=True),
                    json=payload,
                )
                if response.status_code in (401, 403) and uses_oidc:
                    refreshed_token, _ = await knowledge_auth.get_knowledge_ops_bearer(
                        route=tool,
                        force_refresh=True,
                        static_token=static_token,
                    )
                    if refreshed_token:
                        response = await client.post(
                            url,
                            headers=_headers(app, token=refreshed_token, streamable=True),
                            json=payload,
                        )
                if response.status_code >= 400:
                    return _with_knowledge_oidc_health(
                        app, _error_result(app, tool, f"HTTP {response.status_code}")
                    )
                parsed = _parse_streamable_response(response.text)
                return _with_knowledge_oidc_health(app, _mcp_call_result(app, tool, parsed))

            if not spec.path:
                return _error_result(app, tool, "manifest did not provide a REST path")
            # The manifest is remote data: only a path relative to the configured
            # base URL is followed, so a manifest cannot send the bearer (or the
            # agent's arguments) to another origin.
            if "://" in spec.path or spec.path.startswith("//"):
                return _error_result(app, tool, "manifest REST path must be relative")
            endpoint = f"{url.rstrip('/')}/{spec.path.lstrip('/')}"
            method = spec.method or "POST"
            request_kwargs: dict[str, Any] = {"headers": _headers(app, token=token)}
            if method in {"GET", "HEAD"}:
                request_kwargs["params"] = arguments
            else:
                request_kwargs["json"] = arguments
            response = await client.request(method, endpoint, **request_kwargs)
            if response.status_code in (401, 403) and uses_oidc:
                refreshed_token, _ = await knowledge_auth.get_knowledge_ops_bearer(
                    route=tool,
                    force_refresh=True,
                    static_token=static_token,
                )
                if refreshed_token:
                    request_kwargs["headers"] = _headers(app, token=refreshed_token)
                    response = await client.request(method, endpoint, **request_kwargs)
            if response.status_code >= 400:
                return _with_knowledge_oidc_health(
                    app, _error_result(app, tool, f"HTTP {response.status_code}")
                )
            try:
                return _with_knowledge_oidc_health(app, response.json())
            except (TypeError, ValueError):
                return response.text
    except httpx.TimeoutException:
        return _error_result(app, tool, "request timed out")
    except Exception as exc:  # noqa: BLE001 - sibling boundary must not raise into the tool loop
        logger.warning(
            "sibling app call failed app=%s tool=%s error=%s",
            app.name,
            tool,
            type(exc).__name__,
        )
        return _error_result(app, tool, "request failed")
