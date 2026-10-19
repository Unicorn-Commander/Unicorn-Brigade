# Sibling app tools

Brigade can expose selected tools owned by Accounting-Ops, Customer-Ops, and
Knowledge-Ops without copying their schemas into Brigade. Set
`SIBLING_APP_TOOLS_ENABLED=0` to disable the integration; it defaults to `1`.
Schemas are fetched only when an agent requests a configured sibling name and
are cached for ten minutes. Short-lived discovery failures are cached too, so
an unavailable service is not hammered.

## Dogfood environment

| App | URL variable | Token variable | Transport |
| --- | --- | --- | --- |
| Accounting-Ops | `ACCOUNTING_OPS_MCP_URL` (defaults to the public MCP URL) | `ACCOUNTING_OPS_MCP_TOKEN` | Streamable HTTP MCP |
| Customer-Ops | `CUSTOMER_OPS_MCP_URL` (defaults to the public MCP URL) | `CUSTOMER_OPS_MCP_TOKEN` | Streamable HTTP MCP |
| Knowledge-Ops | `KNOWLEDGE_OPS_URL` (defaults to `http://knowledge-ops:8765`) | `KNOWLEDGE_OPS_TOKEN`, or the OIDC variables below for direct `knowledge_ops_*` tools | REST manifest |

Accounting-Ops and Customer-Ops require their configured static bearer tokens.
Knowledge-Ops' internal REST routes answer 401 "missing bearer token" without one
(measured 2026-10-17). The direct `knowledge_ops_*` tools prefer a cached Keycloak
client-credentials bearer when all three variables below are set, otherwise they
fall back to `KNOWLEDGE_OPS_TOKEN`, and otherwise send no bearer:

- `KNOWLEDGE_OPS_OIDC_TOKEN_URL`
- `KNOWLEDGE_OPS_OIDC_CLIENT_ID`
- `KNOWLEDGE_OPS_OIDC_CLIENT_SECRET`

Optional token request parameters are `KNOWLEDGE_OPS_OIDC_AUDIENCE` and
`KNOWLEDGE_OPS_OIDC_SCOPE`. The separate manifest-backed `knowledge.*` tools still
use `KNOWLEDGE_OPS_TOKEN`. Credentials are read from the environment and never
logged.

## Safety and configuration

`app/data/sibling_apps.json` is the source of truth. Bare legacy names are
aliases for namespaced names, while the tool definition sent to the model uses
the sibling's current schema. MCP apps expose only their configured `tools`
allowlist. Manifest tools are read-only by default; a manifest tool with
`read_only: false` is exposed only when its namespaced name appears in that
app's `allow_writes` list. Knowledge-Ops currently allows `upsert_doc` and
`record_metric`; `delete_doc` is intentionally not allowed.

To add another sibling app, add one config entry with its namespace, transport,
URL/token environment variables, timeout, and allowlist. For MCP, the client
uses `tools/list` and `tools/call` with the sibling's schemas. For
`rest-manifest`, the client reads `/.well-known/mcps.json` and sends each
declared `rest.method`/`rest.path` request with the tool arguments as its JSON
body for non-GET methods. Add aliases only when existing stored agent names
need compatibility.
