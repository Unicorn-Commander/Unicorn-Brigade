# Unicorn Brigade Changelog

All notable changes to Unicorn Brigade are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.10.0] — 2026-04-26

Per-case memory scoping. Memories now live at
`{user}__{case}__{agent}` instead of `{user}__{agent}`, so the same
user's chats with the same agent across different cases don't bleed
together. Crisis Ops sends `case_id` on every chat call. Brigade
consumers that don't send `case_id` keep the legacy two-part group_id
(no breakage).

### Added
- **`OpenAIChatRequest.case_id`** — per-call case scope. Forwarded into
  `ChatRequest.case_id`.
- **`ChatRequest.case_id`** field.
- **`graphiti_manager._group_id(user, agent, case_id=None)`** — extended
  signature; case_id is appended to the group when set.
- **`graphiti_manager.store(... case_id=None)`** and **`.retrieve(...
  case_id=None)`** signatures threaded.
- **All memory call sites in agent_routes.py + openai_compat_routes.py
  pass `request.case_id`** through to memory store/retrieve.
- **`delegation_tools._CURRENT_CASE_ID`** ContextVar — `chat_with_agent`
  sets it; `delegate_to_agent_handler` forwards it in the downstream
  body so a Fixer's case scope flows through nested specialist chats.

### Migration notes (1.9.0 → 1.10.0)
- All additive — pre-existing memories still addressable as
  `{user}__{agent}` for callers that don't send case_id.
- New chats from Crisis Ops will write to `{user}__{case}__{agent}`
  groups. Pre-1.10 memories for the same user+agent stay where they
  are; the agent will gradually migrate as the user works new cases.

## [1.9.0] — 2026-04-26

Per-call correlation: orchestration events emitted during a single chat
can now be filtered to that chat by a downstream subscriber. Powers
Crisis Ops's live progress badges that show what The Fixer is doing
during the 30-90s wait.

### Added
- **`OpenAIChatRequest.mission_id`** — per-call correlation id. Forwarded
  to `ChatRequest.mission_id`. If not provided, `chat_with_agent`
  generates one (`chat-<12-hex>`).
- **`ChatRequest.mission_id`** — internal Brigade chat schema mirror.
- **`mission_id` threaded into all `emit_*` helpers** in `chat_with_agent`:
  `emit_agent_started`, `emit_tool_call`, `emit_tool_result`,
  `emit_agent_completed`. The `OrchestrationEvent.mission_id` field already
  existed; this just populates it consistently.
- **`delegation_tools._CURRENT_MISSION_ID`** ContextVar. `chat_with_agent`
  sets it at the top of each call; `delegate_to_agent_handler` reads it
  and forwards `mission_id` in the downstream chat body. Lets a Fixer's
  events AND every nested specialist's events share the same correlation
  id, so a subscriber sees the full delegation chain.
- **`GET /api/v1/orchestration/events?mission_id=X`** filter on the SSE
  firehose. Events with non-matching `mission_id` are dropped from the
  stream. Lets multiple concurrent chats subscribe without bleeding into
  each other.

### Migration notes (1.8.0 → 1.9.0)
- All additive — clients that don't send `mission_id` see no change.
- Subscribers that want per-chat events should send `?mission_id=` on the
  events URL; without it, the stream is the unfiltered firehose (existing
  behavior).

## [1.8.0] — 2026-04-25

Per-call model override on the OpenAI-compat surface so consumer apps
can pick the model per request without forking agent definitions per
quality tier.

### Added
- **`model_override` field on `OpenAIChatRequest`.** When set, replaces
  the agent's configured `model` for this call only. Threaded into
  `chat_with_agent` (which already honored `request.model` as override)
  via `ChatRequest.model`. Also threaded into `_enhanced_stream_chat`'s
  resolver. Lets a Crisis Ops drafter quality picker (best/default/cheap/
  local) work without per-tier agent forks.

### Notes
- `_enhanced_stream_chat` does NOT run a server-side tool loop — it
  streams pure LLM output. Agents that depend on Crisis MCP tools
  (drafters, analytical, The Fixer) should keep using `stream:false`
  through the openai-compat adapter to preserve tool-call functionality.
  Streaming-with-tool-calls is a Tier-2 follow-up.

### Migration notes (1.7.0 → 1.8.0)
- No DB migration. New field is additive; existing clients ignore it.

## [1.7.0] — 2026-04-25

Apps follow identity (Keycloak roles → User.apps), delegation works
through tool loops, downstream timeouts no longer mask specialist
failures.

### Added
- **Keycloak realm/client roles → User.apps sync.** When a user
  authenticates via Keycloak SSO, Brigade derives `user.apps` from
  any role matching pattern `app:<slug>` (e.g., `app:crisis-ops`,
  `app:librechat`, `app:opencode`). The User row is created on first
  SSO login and refreshed on every login (apps merged additively;
  role synced). Single Keycloak admin change ("grant Bob access to
  LibreChat") propagates to Brigade automatically — no per-service
  user-keys provision call needed for app membership.

### Changed
- **`delegate_to_agent` timeout 120s → 300s.** Cloud Claude calls with
  full MCP tool loops can run 2–4 minutes. The previous 120s was
  consistently failing for crisis specialists, causing The Fixer to
  fall back to direct work. Bumped + improved error surfacing
  (TimeoutException catches separately, returns descriptive error
  string instead of empty string so the orchestrator sees what failed).

### Migration notes (1.6.0 → 1.7.0)
- **Keycloak setup:** define realm roles like `app:crisis-ops`,
  `app:librechat`, `app:opencode`, `app:stable`, `app:mission-control`,
  `app:brigade` and assign to users. They flow into Brigade automatically
  on next SSO login. Until you do this, apps still come from upstream
  service provisioning (the existing `apps` field on
  `POST /api/v1/admin/user-keys`).
- The role-pattern is `app:<slug>` (case-insensitive). Slug becomes the
  app identifier that `accessPolicy.apps` checks against.

## [1.6.0] — 2026-04-25

Apps-based access model. Replaces the `key_names` proxy with the
architecturally correct pattern: **users have apps, agents serve apps,
access = intersection.** A user can use an agent if they're a member
of at least one app the agent is offered through. Multi-app users
(e.g., an admin in Crisis Ops + LibreChat + OpenCode) reach more agents
without needing per-app keys.

### Added
- **`User.apps`** column (`JSONB`, default `[]`). DB migration applied
  inline (`ALTER TABLE users ADD COLUMN IF NOT EXISTS apps JSONB DEFAULT
  '[]'::jsonb` + GIN index).
- **`accessPolicy.apps`** field in `evaluate_agent_access`. List of app
  slugs this agent is offered through. User passes if their `user.apps`
  ∩ `agent.apps` is non-empty.
- **`apps` field on `POST /api/v1/admin/user-keys`** request body. The
  `_upsert_user` helper merges new apps into the existing list (apps
  are additive — provisioning doesn't shrink the user's footprint).
- **`_user_apps()`** helper in `agent_routes.py` reads `users.apps`
  per chat call (cheap single-row lookup) and threads it into
  `user_attrs` at all three return paths of `_fetch_user_attrs`.

### Changed
- **All 16 crisis agents migrated** from `accessPolicy.key_names:
  ["crisis-ops"]` to `accessPolicy.apps: ["crisis-ops"]`. Behavior
  unchanged for current users (Crisis Ops users have apps=[crisis-ops]),
  but now multi-app users are first-class — Aaron's apps array includes
  crisis-ops, librechat, opencode, stable, mission-control, brigade
  and he can reach the appropriate agents from any of those surfaces.
- `key_names` policy field still honored for backwards-compatibility
  but new agents should use `apps` going forward.

### Backfill
- Existing crisis-ops users' `apps` field set to `["crisis-ops"]` via
  one-shot SQL: `UPDATE users SET apps = '["crisis-ops"]'::jsonb WHERE
  id IN (SELECT DISTINCT user_id FROM user_api_keys WHERE
  name='crisis-ops')`.

### Migration notes (1.5.0 → 1.6.0)
- DB migration is additive — existing keys keep working. Provision new
  users with `apps:[...]` in the request body to populate the new field.
- Crisis Ops's `brigadeAuth.js` already sends `apps:["crisis-ops"]` on
  provision (1.5.x integration).
- LibreChat / OpenCode / Stable can adopt the same pattern by sending
  `apps:["librechat"]` etc. on their next user-key provision call.
- Future: derive `User.apps` from Keycloak realm roles on SSO callback
  so apps follow the user's identity automatically. Tracked separately.

## [1.5.0] — 2026-04-25

The Fixer (Crisis Ops orchestrator) joins the catalog. Cloud Claude is
now the default for the legal agents (via OpenRouter). All 16 crisis-
case agents are scoped to `key_names: ["crisis-ops"]` so they don't
leak to other Brigade consumers (LibreChat, OpenCode, Stable, etc.).

### Added
- **The Fixer (`the-fixer`)** — Crisis Ops orchestrator. Cross-domain
  fixer pattern: scopes vague asks with a single pointed question,
  decomposes multi-step asks into specialist calls, integrates answers,
  and tells the user what to do next. Roster covers all 15 crisis
  specialists (3 investigators + 6 drafters + 6 analytical/strategic).
  Smoke verified: a "prep us for Tuesday's mediation" ask produced a
  complete settlement packet with damages math, ranked defense
  pushback, tactical day-of notes, and immediate action items in one
  call (22K tokens, ~$0.10).
- **`key_names` access-policy field** — `evaluate_agent_access` now
  honors `accessPolicy: {"key_names": ["service-name", ...]}` to
  restrict an agent to users provisioned via that upstream service.
  All 16 crisis agents are locked to `crisis-ops`. LibreChat-style
  callers (with key name "librechat") are blocked at billing wall +
  policy check (defense in depth).
- **`key_name` threaded into `user_attrs`** at all three return paths
  of `_fetch_user_attrs` so the access-policy check can see it.

### Changed
- **All 13 legal agents now default to `anthropic/claude-sonnet-4.6`**
  (1M ctx, $3/M in $15/M out via OpenRouter) instead of the local
  Qwen3.6-35B fallback. Smoke comparison: cloud Claude pulls exact
  case-record quotes (e.g., investigators' characterizations of Doe), names specific evidence, applies
  the governing legal doctrines with sharper case-specific framing.
  Local Qwen remains a per-call override option.
- **Orchestrator agents (majik, gflow, the-general, gunny) migrated
  from bare `Qwen3.6-35B-A3B-UD-Q4_K_XL` to `local/Qwen3.6-35B-A3B-UD-Q4_K_XL`**
  so they keep hitting the local llama-router after `OPENROUTER_API_KEY`
  is set on the env (without this, bare names start routing to
  OpenRouter and 404 on local model IDs).

### Cost notes
Per-call cost for the legal agents now lands at $0.06–0.10 for typical
drafter calls (5K input, 3K output) and $0.10–0.20 for orchestrator
calls that pull large MCP context (20K input). Anthropic direct API
would be ~10–20% cheaper than OpenRouter; planned for when the direct
keys are wired.

### Migration notes (1.4.0 → 1.5.0)
- Set `OPENROUTER_API_KEY` on the Brigade env (compose passthrough +
  value in your secret store of choice). Without it, agents using
  `anthropic/`, `deepseek/`, `openai/` etc. model prefixes fail.
- Re-run `register_fixer_and_scope.py` to create The Fixer and apply
  the access policy to existing crisis agents.
- Crisis Ops user-key minting (via `/api/v1/admin/user-keys`) MUST use
  `name: "crisis-ops"` — otherwise the new agents will refuse the call.
  The Crisis Ops `brigadeAuth.js` already does this; nothing to change
  on the consumer side.

## [1.4.0] — 2026-04-25

Persona cleanup, model upgrade, three new strategic agents, and a hardened
think-tag stripper.

### Changed
- **Lean personas across the legal agent catalog.** The 10 drafter +
  analytical agents had biographical filler ("you have 25 years of
  experience...") that primed tone but added nothing actionable. Replaced
  with 1-2-sentence functional personas: role + style + don'ts. The
  systemPrompt does the real work; the persona just sets context.
- **Model upgraded** for the same 10 agents from `midboy1/gemma-4-26B-A4B-it-UD-Q4_K_M`
  to `local/Qwen3.6-35B-A3B-UD-Q4_K_XL` (the 35B-A3B MoE with expert
  offload on bigboy's RTX 3090, 32K effective context per parallel slot).
  Smoke verification: devils-advocate produced 681 tokens of clean Mt.
  Healthy doctrine analysis with proper citations.
- **`LOCAL_LLM_URL` defaulted to `http://unicorn-llama-router:8080`** in the
  Brigade compose env (was inheriting an obsolete `unicorn-llama-cpp:8080`
  default). Without this, agents using the `local/` model prefix hit a
  DNS failure at first call.

### Added — three more strategic agents
- **settlement-modeler** — Bayesian settlement-range analysis. Inputs:
  case-strength rating, P(plaintiff verdict), expected verdict
  distribution, both sides' litigation costs, time-to-verdict, discount
  rate, jurisdiction-specific settlement multiplier. Outputs floor /
  target / opening offer / ceiling, with the math behind each, plus a
  negotiation-posture section (when settlement is most likely, defense's
  pressure points). Smoke-verified: produces structured EV analysis with
  cited probability calibrations.
- **cross-exam-builder** — Trial cross outlines (sibling to deposition-prep
  but for the well of the court). Builds 3-5 themes per witness with a
  question ladder per theme: setup → pin → contradiction (with exhibit) →
  exit. Includes impeachment library, exhibit foundation script,
  anticipated objections, and 2-3 closing-argument hooks pulled through
  from cross.
- **media-strategist** — Litigation-PR move recommendations with explicit
  risk/leverage tradeoff. Recommends do-nothing / strategic leak /
  on-the-record interview / op-ed / press conference / social media /
  interest-group coordination. Refuses moves whose downside (jury pool,
  Rule 12 fodder, judicial reaction) exceeds leverage gain.

### Fixed
- **Hardened `_strip_thinking`** to also remove orphan `<think>` opening
  tags through end-of-string. Previously, a max-tokens cutoff mid-think
  block leaked the agent's internal reasoning into the response body
  (and into PDFs). Now the strip is two-pass: closed blocks first,
  then any orphan opening through end-of-string.

### Migration notes (1.3.0 → 1.4.0)
- Set `LOCAL_LLM_URL=http://unicorn-llama-router:8080` (or your equivalent
  llama-router endpoint) in your Brigade compose env, otherwise `local/`-
  prefixed model names will fail with a DNS error.
- Re-run `register_strategic_batch2.py` against Brigade with
  `BRIGADE_ADMIN_KEY` set, OR POST the agent definitions to
  `/api/v1/agents` directly.

### Known limitations carried forward
- **Cloud Claude routing** still requires setting `OPENROUTER_API_KEY`
  (or `ANTHROPIC_API_KEY`) on the Brigade env, AND coordinating the
  switch with the existing orchestrator agents (majik, gflow, the-general)
  whose `model` field uses bare names like `Qwen3.6-35B-A3B-UD-Q4_K_XL`
  that would suddenly route to OpenRouter and 404. Tracked separately.

## [1.3.0] — 2026-04-25

Analytical / strategic agent batch + brigade-pdf-gen separated into its
own repo for cleaner companion-service deployment.

### Added — Analytical agents (4)

- **damages-modeler** — Quantified damages worksheets with stated
  assumptions, transparent calculations, and sensitivity ranges. Lost
  wages, present-value front pay, jurisdiction-benchmark emotional
  distress, punitive multiplier (Gore / State Farm / Campbell), §1988
  attorneys' fees. Output drives demand letters and complaint prayers.
- **devils-advocate** — Steel-mans every argument opposing counsel will
  raise, ranks by strength (1-10), drafts best response + flags residual
  risk for each. Internal-only output. Use before filing major papers
  or going into settlement talks. Smoke-verified against the official-duties question for the Doe case.
- **deposition-prep** — Witness-specific binders: profile, exhibits to
  mark in strategic order, chronological + topical question groups,
  anticipated objections + how to handle, impeachment material from
  the record.
- **legal-theory-evaluator** — Element-by-element strength rating per
  cause of action against the current record, gaps that would close
  weak elements, recommendation matrix (plead now / alternative pleading
  / hold for amendment / do not plead), top discovery priorities.

All four use the Crisis MCP tool list and the integrity rules + WEAK
POINTS pattern from the drafter family.

### Changed
- brigade-pdf microservice now lives at its own repo:
  `git.unicorncommander.ai/UnicornCommander/brigade-pdf-gen`. Brigade's
  `generate_pdf` tool unchanged; the relocation is purely repo hygiene.

### Migration notes (1.2.0 → 1.3.0)
- New agents are DB-registered. Re-run `register_analytical.py` against
  Brigade with `BRIGADE_ADMIN_KEY` set, or POST the agents directly to
  `/api/v1/agents`.
- Crisis Ops `/drafts` page now lists all 10 agents (6 drafters + 4
  analytical). No backend migration required.

## [1.2.0] — 2026-04-25

Drafter family, Crisis MCP tool wiring, and the brigade-pdf microservice
make Brigade a full court-document production stack instead of just a
Q&A surface for the CASE-ID case.

### Added
- **Crisis MCP tools wired into TOOL_REGISTRY** (`app/llm/crisis_mcp_tools.py`).
  Agents whose `tools` field references `search_evidence`, `get_entity`,
  `get_timeline`, `find_connections`, `list_entities`, `search_entities`,
  `get_relationships`, `get_strategy`, `get_evidence_folders`, `get_document`,
  `find_evidence_gaps`, or `get_case_summary` now get them as real callable
  LLM functions in chat_with_agent. Handlers proxy via JSON-RPC 2.0 to the
  crisis-mcp:3011/mcp service. case_id is optional (defaults to active case).
- **`generate_pdf` tool** — proxies to the new brigade-pdf microservice.
  Any agent that produces a markdown draft can hand off to a court-fileable
  PDF in one tool call. Document types: brief / motion / opposition / reply
  (double-spaced, paginated), demand / foia / memo (single-spaced letter),
  complaint (numbered allegations).
- **Drafter agent family** — six new DB-registered agents:
  - `brief-drafter` — general legal briefs
  - `motion-drafter` — federal/state motion practice (MSJ, MTD, MIL, etc.)
  - `complaint-drafter` — element-level pleadings that survive 12(b)(6)
  - `demand-letter-drafter` — pre-litigation demand letters with calibrated tone
  - `foia-drafter` — federal FOIA / state public-records requests with fee-waiver argument
  - `discovery-drafter` — interrogatories, RFPs, RFAs, deposition outlines
  Each has a 25-year-senior-litigator persona, integrity rules forbidding
  invented citations or facts, and a mandatory **WEAK POINTS** closing
  section so reviewing attorneys see risks before filing. Currently routed
  to `midboy1/gemma-4-26B-A4B-it-UD-Q4_K_M`; configurable per-agent.

### Companion service (separate repo)
- **brigade-pdf** — FastAPI microservice rendering markdown → PDF via
  WeasyPrint with per-document-type CSS templates. Listens on port 8090,
  writes to a 24-hour TTL volume. See the brigade-pdf-gen repo / compose.

### Changed
- `BRIGADE_PDF_URL` env var (default `http://brigade-pdf:8090`) controls
  where the `generate_pdf` tool dispatches. Set `BRIGADE_PDF_PUBLIC_URL`
  if the user-facing download URL differs from the internal one
  (e.g., behind Traefik).

### Smoke verification
- `brief-drafter` produced a Statement of Facts citing real evidence
  filenames inline (`rocky-doe-article.md`, `chronology.md`)
  via the `search_evidence` MCP tool.
- `demand-letter-drafter` end-to-end through Crisis Ops: drafted, rendered
  to a 30 KB PDF, downloaded via the proxy, opens in any PDF reader.

### Migration notes (1.1.0 → 1.2.0)
- Stand up the brigade-pdf microservice on the same docker network if you
  want PDF generation: `cd brigade-pdf-gen && docker compose up -d`.
- Crisis-mcp must be reachable at `crisis-mcp:3011/mcp` (set
  `CRISIS_MCP_URL` to override).
- The drafter agents are registered as DB rows on first run of the
  registration script — re-run with PUT to update.

## [1.1.0] — 2026-04-25

### Added
- **OpenAI-compatible adapter** at `/api/v1/openai/v1/chat/completions` and `/api/v1/openai/v1/models`. Each Brigade agent appears as an OpenAI-style "model" so any OpenAI SDK / LibreChat / OpenCode client can call it directly.
  - **Enhanced mode** (no client tools): full Brigade loop — persona, memory, internal tools (delegate_to_agent, web_search, memory ops).
  - **Passthrough mode** (client sends tools): persona + memory injected, client owns the tool loop.
  - **Dual-layer mode** (client tools + agent server tools): LLM mixes both per turn; server-owned tools execute internally, client-owned tool calls are returned for the client to execute.
  - **SSE streaming** for enhanced mode; tool-trace footer (`<details>…Tools used…</details>`) appended to non-streaming responses for visible accountability.
- **Keycloak OIDC SSO end-to-end** — JWKS validation, JWT bearer + session cookie + API key auth all unified via `AuthUser`. PKCE auth-code flow at `/oidc/login` and `/oidc/callback`. Frontend wired through.
- **Graphiti + FalkorDB temporal knowledge-graph memory** replacing mem0 + Qdrant. Per-user-per-agent groups (`{user_id}__{agent_id}`). LLM extraction pinned to a small fast model (gemma-4-E4B on a P40), embeddings via BGE-M3 on Infinity. Background store so chat returns fast.
- **Memory inspector API** (`/api/v1/agents/{agent_id}/memories`, `/api/v1/users/{user_id}/memories`, GDPR-compliant DELETE).
- **Self-serve onboarding** at `/welcome` — single-page signup / login / API-key management. Downloadable opencode.json snippet pre-filled with the user's key. Zero admin intervention to add a new user.
- **Service-delegation user-key API** (`/api/v1/admin/user-keys`) — trusted services (Crisis Ops, Ops-Center) provision per-user Brigade API keys via the BRIGADE_SERVICE_KEY shared secret. Auto-provisions Brigade User rows on first call.
- **Tool trace footer** on OpenAI-compat responses so chat UIs surface which tools fired (delegate_to_agent, web_search, memory ops, etc.) with args + status.
- **Langfuse v3 tracing** — every chat call writes a trace with cost, latency, and tool-call breakdown to the self-hosted langfuse.magicunicorn.dev stack.
- **Conversation auto-persistence** to Postgres per chat — full history accessible across sessions.
- **Crisis investigation agents** (evidence_correlator, gap_analyzer, timeline_builder) registered with the WorkflowManager.
- **Landing page** at `/landing` — marketing surface for brigade.magicunicorn.dev.
- **`BRIGADE_TRUSTED_KEY_NAMES` billing bypass** — service-delegated callers (B2B seats provisioned via `/api/v1/admin/user-keys` with a trusted key name) skip the consumer billing wall since the upstream service is the paying customer.

### Changed
- **Memory provider** is Graphiti+FalkorDB by default. mem0 path retained as a dormant shim for import compatibility.
- **Auth middleware** unified under a single `AuthUser` dataclass with `auth_source` field (api_key | keycloak | session | bypass | public).
- **Non-admin users** can no longer spoof `user_id` in chat requests — the authenticated identity always wins (memory isolation).
- **Dockerfile** splits pip install into two stages so resolver doesn't choke solving Graphiti deps against the full LangChain tree at once.

### Removed
- `app/memory/zep_manager.py` (never wired, replaced by Graphiti).
- `mem0ai` from requirements.

### Fixed
- **Think-tag stripping across SSE chunk boundaries** in the streaming adapter (carry buffer for partial `<think` tags so they never leak to UIs).
- **Service-delegated users 402-ing** on every chat call because they had no Lago subscription — now bypassed when key name is in `BRIGADE_TRUSTED_KEY_NAMES`.

### Dependencies
- Added `graphiti-core[falkordb] >= 0.28.0`.
- Removed `mem0ai`.
- Bumped `openai` to 1.92.0; LangChain set to 0.3.25 / 0.3.66 / 0.3.45 for Graphiti compatibility.

### Migration notes (1.0.0 → 1.1.0)
- Set `MEMORY_PROVIDER=graphiti` (or remove the override) and provision FalkorDB at `unicorn-falkordb:6379`.
- Set `LANGFUSE_ENABLED=true` plus `LANGFUSE_HOST`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` to enable tracing.
- For B2B service integrations, set `BRIGADE_TRUSTED_KEY_NAMES=crisis-ops,ops-center` (comma-separated, case-insensitive) so service-delegated users bypass consumer billing.
- Provision Keycloak client `brigade` in realm `uchub`; set `BRIGADE_USE_KEYCLOAK=true` and the `KEYCLOAK_*` vars.

## [1.0.0] — earlier

Initial production-grade release. See pre-1.1 git history (tags `v0.2.0-memory-adapter`, `v0.3.0-dual-tools`, `v0.4.0-best-in-class`, `v0.5.0-voice-live`) for the staged work that led here.
