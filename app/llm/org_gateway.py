"""BR-3.2 per-org gateway key selection for UC/LiteLLM routes.

This module is intentionally config-only: it never mints, rotates, or validates
live provider keys. Aaron owns that prod/money step. When enabled, Brigade picks
an already-provisioned per-org gateway key before using the shared fallback.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Mapping, Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OrgGatewayCredential:
    org_id: str
    api_key: str
    key_alias: Optional[str] = None
    max_budget: Optional[float] = None
    source: str = "env"


def per_org_gateway_enabled() -> bool:
    return os.getenv("UC_GATEWAY_PER_ORG_KEYS_ENABLED", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _as_mapping(value: Any) -> Optional[Mapping[str, Any]]:
    return value if isinstance(value, Mapping) else None


@lru_cache(maxsize=1)
def _load_env_map() -> dict[str, OrgGatewayCredential]:
    """Parse UC_GATEWAY_ORG_KEYS_JSON.

    Expected shape:
      {"<org_id>": {"api_key": "sk-...", "key_alias": "org-a", "max_budget": 50}}

    A shorthand {"<org_id>": "sk-..."} is accepted for local tests/dev only.
    Invalid entries are skipped loudly without logging secret values.
    """
    raw = os.getenv("UC_GATEWAY_ORG_KEYS_JSON", "").strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.error("UC_GATEWAY_ORG_KEYS_JSON is invalid JSON: %s", exc)
        return {}
    if not isinstance(parsed, Mapping):
        logger.error("UC_GATEWAY_ORG_KEYS_JSON must be an object keyed by org_id")
        return {}

    credentials: dict[str, OrgGatewayCredential] = {}
    for org_id, entry in parsed.items():
        oid = str(org_id).strip()
        if not oid:
            continue
        if isinstance(entry, str):
            api_key = entry.strip()
            meta: Mapping[str, Any] = {}
        else:
            meta = _as_mapping(entry) or {}
            api_key = str(meta.get("api_key") or meta.get("key") or "").strip()
        if not api_key:
            logger.warning("UC gateway org key entry for org %s has no api_key", oid)
            continue
        max_budget = meta.get("max_budget")
        try:
            max_budget_value = float(max_budget) if max_budget is not None else None
        except (TypeError, ValueError):
            max_budget_value = None
        credentials[oid] = OrgGatewayCredential(
            org_id=oid,
            api_key=api_key,
            key_alias=str(meta.get("key_alias") or meta.get("alias") or "") or None,
            max_budget=max_budget_value,
        )
    return credentials


def clear_org_gateway_cache() -> None:
    _load_env_map.cache_clear()


def get_org_gateway_credential(org_id: Optional[str]) -> Optional[OrgGatewayCredential]:
    if not org_id or not per_org_gateway_enabled():
        return None
    return _load_env_map().get(str(org_id))


def gateway_headers(
    *,
    shared_key: str,
    org_id: Optional[str],
    user_id: Optional[str] = None,
) -> dict[str, str]:
    """Return OpenAI-compatible headers for the UC gateway.

    With per-org keys enabled, an org-scoped request must have a configured
    org key. Falling back to the shared key in that mode would recreate the
    BR-3.2 blast radius for exactly the calls the flag is meant to protect.
    """
    credential = get_org_gateway_credential(org_id)
    if per_org_gateway_enabled() and org_id and credential is None:
        raise RuntimeError(f"no UC gateway key configured for org {org_id}")

    bearer = credential.api_key if credential is not None else shared_key
    headers = {
        "Authorization": f"Bearer {bearer}",
        "Content-Type": "application/json",
    }
    if org_id:
        headers["X-Org-ID"] = str(org_id)
    if user_id and user_id not in ("anonymous", "dev-bypass", ""):
        headers["X-User-ID"] = str(user_id)
    if credential and credential.key_alias:
        headers["X-UC-Gateway-Key-Alias"] = credential.key_alias
    if credential and credential.max_budget is not None:
        headers["X-UC-Gateway-Max-Budget"] = str(credential.max_budget)
    return headers
