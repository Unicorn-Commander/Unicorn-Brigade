# Per-Caller Authorization (BR-6.4)

Brigade consumers (Unicorn Stable's runtime, Crisis Ops, any OpenAI-SDK
client) authenticate with **one service credential** and forward the **human**
they act for on every chat run — `user` on the OpenAI-compatible payload,
`user_id` on the native `ChatRequest`. Historically that forwarded identity fed
only memory isolation and metering; every authorization decision was made
against the **transport credential** (frequently admin-scoped, so it always
passed), and per-tool `tool_catalog.permission_level` was never checked at
execution time. Result: a confused deputy — a low-privilege user chatting with
a high-privilege agent ("The Colonel") could trigger config-changing tools with
the agent's full privileges.

BR-6.4 adds two additive enforcement layers. Agents and deployments that
configure neither behave **exactly as before**.

## Layer 1 — agent-level: `accessPolicy.user_policy`

A new optional object inside the existing per-agent `accessPolicy` JSON
(`agents.access_policy`). The **existing** accessPolicy fields (`users`,
`tiers`, `orgs`, `key_names`, `apps`, `paid_only`, `require_mfa`) keep gating
the *transport* credential via `evaluate_agent_access`; `user_policy` gates the
**effective end-user** and is evaluated at every chat entry
(`app/auth/caller_authz.evaluate_user_policy`):

```json
{
  "key_names": ["stable"],
  "user_policy": {
    "users": ["<users.id | keycloak sub | email | consumer-side id>"],
    "min_role": "operator",
    "allow_service": false
  }
}
```

Semantics (first match allows):

- End user resolved to a `users` row with role `admin` → allow.
- `users` allowlist — matched against the **raw forwarded id**, canonical
  `users.id`, e-mail (case-insensitive), and Keycloak sub, so a consumer-side
  id can be allowlisted verbatim even before Brigade knows the user.
- `min_role` — the end user resolved to a `users` row whose role meets the bar
  (`viewer < operator < admin`). Unresolved forwarded ids can never satisfy it.
- **No end user** (nothing forwarded, or only placeholders like `anonymous`):
  **deny** — no anonymous privilege — unless the caller is an identified
  service credential *and* the policy sets `"allow_service": true` (for
  cron/automation runs against a locked agent).
- Nothing matched → deny.

Denials return HTTP 403 with a machine-readable body the consumer can surface:

```json
{
  "message": "Agent 'the-colonel' is not available to this user",
  "code": "agent_user_policy_denied",          // or agent_user_policy_missing_user
  "reason": "user-not-allowed",
  "agentId": "the-colonel",
  "userId": "stable-user-9"
}
```

## Layer 2 — tool-level: per-caller privilege vs `permission_level`

Every run resolves a **caller privilege level** on the same 1–5 scale as
`tool_catalog.permission_level`. At tool-execution time (every server-side
execution site) a tool whose required level exceeds the caller's is **refused
for that call**: the agent receives a structured
`permission_denied: tool '<name>' requires permission level N …` tool-error it
can verbalize, and **the run continues** — the turn is never killed.

Caller level resolution (first match wins):

1. **Per-user override map** — the v1 per-user store:
   `BRIGADE_USER_TOOL_LEVELS_FILE` (path to a JSON file, operator-maintained)
   and/or `BRIGADE_USER_TOOL_LEVELS` (inline JSON env; wins on conflict).
   Keys are `users.id` **or** e-mail **or** the consumer-side forwarded id,
   lowercased; values are levels 1–5.
   ```json
   { "aaron@magicunicorn.tech": 5, "stable-user-9": 3 }
   ```
2. **Role default** — the end user's role → level via
   `BRIGADE_ROLE_TOOL_LEVELS` (default `{"admin":5,"operator":3,"viewer":1}`).
   For a direct human caller the role is the (key-scope-derived) AuthUser role;
   for a service-forwarded user it is `users.role` (looked up by id, Keycloak
   sub, or e-mail).
3. **Unknown forwarded user** (no `users` row matched) →
   `BRIGADE_UNKNOWN_USER_TOOL_LEVEL` (default **2**: standard tools, nothing
   config-changing).
4. **No end user at all**:
   - identified **service caller** (machine credential with no bound human —
     the master admin key or an `api_keys` service/agent key) →
     `BRIGADE_SERVICE_CALLER_TOOL_LEVEL` (default **5** — service-to-service
     flows keep today's full privilege; lower it to cap userless machine runs);
   - anyone else → `BRIGADE_NO_USER_TOOL_LEVEL` (default **1** — the anonymous
     floor).

Tools missing from `tool_catalog` require only
`BRIGADE_UNKNOWN_TOOL_PERMISSION_LEVEL` (default 1 — matches the roster
enrichment's long-standing neutral fallback, so an unseeded tool never bricks
chat).

### Rollout switch

`BRIGADE_TOOL_PERMISSION_ENFORCEMENT` = `enforce` (default) | `log` | `off`.

- `log` — **dry run**: evaluates and emits the audit events but allows every
  call. Run production in `log` first and review the `brigade.authz` events to
  see exactly which users/tools would be refused before flipping to `enforce`.
- `off` — no guard is constructed at all (bitwise-identical to pre-BR-6.4).

## What is and is not covered

Enforced entry points (guard built per run from the effective end user):

- `POST /api/v1/agents/{id}/chat` (+ its SSE streaming branch)
- `POST /api/v1/agents/{id}/chat/local` (MLX)
- `POST /api/v1/openai/v1/chat/completions` — enhanced, enhanced-streaming,
  dual-layer (server-side tool executions), and passthrough (agent-level
  policy only: the client executes its own tools there).

Intentionally unchanged (service-originated by definition; they call
`execute_tool_loop` without a guard): the cron scheduler, the workflow engine,
A2A federation, and `agentic_rag` internals. The federation MCP gateway keeps
its own per-key scope gate (`mcp_scope_level`).

## Audit

- Structured JSON events on the **`brigade.authz`** logger:
  `agent_access_denied` (layer `user_policy`) and `tool_permission_denied`
  (layer `tool_permission`) with agent, tool, required vs caller level, basis,
  end user, transport, and mode.
- Agent-level denials also insert into the **`rbac_denials`** table (readable
  at `GET /api/v1/agents/admin/rbac/denials`, admin-only) with reason
  `user-policy:<detail>`. Migration `20260810_01_rbac_denials_audit_table`
  finally ships DDL for that table — the helper had been inserting into it
  best-effort since the original RBAC pass, silently no-oping wherever the
  table was never created by hand.
