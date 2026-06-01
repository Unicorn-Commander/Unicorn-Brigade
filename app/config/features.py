"""Feature flags for Brigade runtime deployments.

Brigade ships one codebase that runs in two postures:

- Internal/dogfood (default) — full agent suite + Maj.Recon + LLM catalog
  admin + crisis/medical/etc. routers. Used at brigade.magicunicorn.dev.
- Federation broker — federation surface only (JWKS, register, /mcp). Used
  at brigade.unicorncommander.ai. Internal-only routers and agent seeding
  are skipped at startup.

Flags default to the dogfood posture so no env change is needed on existing
deployments.
"""

import os


def _bool_env(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


# When True, Brigade serves the federation broker surface only:
# /.well-known/jwks.json, /api/v1/admin/federated-apps/*, /mcp,
# plus the metrics + health surface. All internal routers and agent
# initialization are skipped. Used on the customer-facing prod instance.
FEDERATION_ONLY: bool = _bool_env("BRIGADE_FEDERATION_ONLY", default=False)

# When True, the seeded internal agents (31 of them across 12 domains)
# are loaded at startup. Defaults to True for dogfood; explicitly disabled
# on prod even if FEDERATION_ONLY is somehow not set, to belt-and-suspender
# the agent-leak risk.
INTERNAL_AGENTS_ENABLED: bool = _bool_env(
    "BRIGADE_INTERNAL_AGENTS_ENABLED", default=not FEDERATION_ONLY
)
