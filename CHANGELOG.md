# Unicorn Brigade Changelog

All notable changes to Unicorn Brigade are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
