"""
Validation + registration extraction for federated app discovery manifests.

Each UC app publishes a discovery manifest at /.well-known/mcps.json (see
BRIGADE-FEDERATION-SPEC.md, "Publish a discovery manifest"). Brigade ingests
those manifests at startup / on a refresh cron and uses them to build the
unified namespaced tool catalog. Before a manifest is trusted we validate it
against the contract below and reject anything malformed.

Pure stdlib only (no jsonschema): the schema is small and fixed, and Brigade's
ingest path stays dependency-light. Errors are returned as a flat list of
field-named strings (e.g. "tools[2].scopes_required: required, missing") so the
operator pulling in a manifest sees exactly which field failed.

The federation standardized on RS256 (RSA-2048) on 2026-05-30. python-jose has
no EdDSA/OKP support, so EdDSA cannot be a uniform cross-language choice;
"ed25519"/"EdDSA" in signing_algorithm is therefore a hard validation error,
not a warning.
"""
from __future__ import annotations

import re

# tool_namespace: 6-12 chars, lowercase letters / digits / underscore only.
_NAMESPACE_RE = re.compile(r"^[a-z0-9_]{6,12}$")

# The federation standardized on RS256; anything else fails validation.
_REQUIRED_SIGNING_ALGORITHM = "RS256"
_REJECTED_SIGNING_ALGORITHMS = {"ed25519", "eddsa"}

_VALID_TIERS = {"free", "pro", "enterprise"}


def _is_nonempty_str(value: object) -> bool:
    return isinstance(value, str) and value.strip() != ""


def validate_manifest(doc: dict) -> tuple[bool, list[str]]:
    """
    Validate a discovery manifest dict against the federation contract.

    Returns (ok, errors). ok is True only when errors is empty. Each error
    names the failing field, e.g. "tools[2].scopes_required: required, missing"
    or "tool_namespace: must be 6-12 lowercase [a-z0-9_] chars, got 'ME'".

    Rules:
      - name, version, mcp_endpoint: required, non-empty strings
      - tool_namespace: required, 6-12 lowercase [a-z0-9_] chars
      - auth.federated_auth.expected_audience: required, non-empty string
      - auth.federated_auth.signing_algorithm: must equal "RS256"
        ("ed25519"/"EdDSA" is an explicit error, not a warning)
      - tools: required list (may be empty); each entry needs
          name (str), input_schema (dict), scopes_required (list),
          tier_required in {"free","pro","enterprise"}, read_only (bool)
    """
    errors: list[str] = []

    if not isinstance(doc, dict):
        return False, ["manifest: must be a JSON object"]

    # Top-level required non-empty strings.
    for field in ("name", "version", "mcp_endpoint"):
        if field not in doc:
            errors.append(f"{field}: required, missing")
        elif not _is_nonempty_str(doc[field]):
            errors.append(f"{field}: required, must be a non-empty string")

    # tool_namespace: 6-12 lowercase [a-z0-9_].
    if "tool_namespace" not in doc:
        errors.append("tool_namespace: required, missing")
    else:
        ns = doc["tool_namespace"]
        if not isinstance(ns, str):
            errors.append("tool_namespace: required, must be a string")
        elif not _NAMESPACE_RE.match(ns):
            errors.append(
                "tool_namespace: must be 6-12 lowercase [a-z0-9_] chars, "
                f"got {ns!r}"
            )

    # auth.federated_auth block.
    auth = doc.get("auth")
    if not isinstance(auth, dict):
        errors.append("auth: required, must be an object")
        fed = None
    else:
        fed = auth.get("federated_auth")
        if not isinstance(fed, dict):
            errors.append("auth.federated_auth: required, must be an object")
            fed = None

    if fed is not None:
        if "expected_audience" not in fed:
            errors.append("auth.federated_auth.expected_audience: required, missing")
        elif not _is_nonempty_str(fed["expected_audience"]):
            errors.append(
                "auth.federated_auth.expected_audience: required, "
                "must be a non-empty string"
            )

        if "signing_algorithm" not in fed:
            errors.append("auth.federated_auth.signing_algorithm: required, missing")
        else:
            alg = fed["signing_algorithm"]
            if not isinstance(alg, str):
                errors.append(
                    "auth.federated_auth.signing_algorithm: must be a string "
                    f'equal to "{_REQUIRED_SIGNING_ALGORITHM}"'
                )
            elif alg.lower() in _REJECTED_SIGNING_ALGORITHMS:
                errors.append(
                    "auth.federated_auth.signing_algorithm: federation "
                    f'standardized on "{_REQUIRED_SIGNING_ALGORITHM}", '
                    f"EdDSA/ed25519 not supported, got {alg!r}"
                )
            elif alg != _REQUIRED_SIGNING_ALGORITHM:
                errors.append(
                    "auth.federated_auth.signing_algorithm: must equal "
                    f'"{_REQUIRED_SIGNING_ALGORITHM}", got {alg!r}'
                )

    # tools: must be present, must be a list (may be empty), validate entries.
    if "tools" not in doc:
        errors.append("tools: required, missing")
    elif not isinstance(doc["tools"], list):
        errors.append("tools: must be a list")
    else:
        for i, tool in enumerate(doc["tools"]):
            errors.extend(_validate_tool(i, tool))

    return (len(errors) == 0), errors


def _validate_tool(index: int, tool: object) -> list[str]:
    """Validate a single tools[] entry; return its field-named errors."""
    prefix = f"tools[{index}]"
    if not isinstance(tool, dict):
        return [f"{prefix}: must be an object"]

    errors: list[str] = []

    if "name" not in tool:
        errors.append(f"{prefix}.name: required, missing")
    elif not isinstance(tool["name"], str):
        errors.append(f"{prefix}.name: must be a string")

    if "input_schema" not in tool:
        errors.append(f"{prefix}.input_schema: required, missing")
    elif not isinstance(tool["input_schema"], dict):
        errors.append(f"{prefix}.input_schema: must be an object")

    if "scopes_required" not in tool:
        errors.append(f"{prefix}.scopes_required: required, missing")
    elif not isinstance(tool["scopes_required"], list):
        errors.append(f"{prefix}.scopes_required: must be a list")

    if "tier_required" not in tool:
        errors.append(f"{prefix}.tier_required: required, missing")
    elif tool["tier_required"] not in _VALID_TIERS:
        errors.append(
            f"{prefix}.tier_required: must be one of "
            f'{{"free","pro","enterprise"}}, got {tool["tier_required"]!r}'
        )

    if "read_only" not in tool:
        errors.append(f"{prefix}.read_only: required, missing")
    elif not isinstance(tool["read_only"], bool):
        errors.append(f"{prefix}.read_only: must be a boolean")

    return errors


def extract_registration(doc: dict) -> dict:
    """
    Pull the registration fields Brigade needs from a manifest.

    Assumes the doc already passed validate_manifest, so this does not
    re-validate. Returns the stable subset Brigade persists in its
    federated-apps registry to drive the namespaced tool catalog.

    Each tools[] entry is reduced to the fields Brigade routes / pre-filters
    on: name, scopes_required, tier_required, read_only. The full input_schema
    is carried through so Brigade can advertise it to MCP clients verbatim.
    """
    auth = doc.get("auth") or {}
    fed = auth.get("federated_auth") or {}

    tools = []
    for tool in doc.get("tools") or []:
        tools.append(
            {
                "name": tool.get("name"),
                "scopes_required": list(tool.get("scopes_required") or []),
                "tier_required": tool.get("tier_required"),
                "read_only": tool.get("read_only"),
                "input_schema": tool.get("input_schema"),
            }
        )

    return {
        "name": doc.get("name"),
        "version": doc.get("version"),
        "tool_namespace": doc.get("tool_namespace"),
        "mcp_endpoint": doc.get("mcp_endpoint"),
        "expected_audience": fed.get("expected_audience"),
        "jwks_url": fed.get("jwks_url"),
        "tools": tools,
    }
