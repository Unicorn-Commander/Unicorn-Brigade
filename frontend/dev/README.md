# Brigade mock API (frontend dev harness)

A deterministic, dependency-free mock of the Unicorn Brigade backend so the React
app can run locally against realistic data in every hard state — no Docker, no
Keycloak, no credentials. Node built-ins only (`node:http`, `node:fs`,
`node:crypto`). Verified on Node 26.

```
frontend/dev/
├── mock-api.mjs        the server (one process; REST + SSE + chat streaming)
├── fixtures/*.json     the data (17 files, "$now±…" time tokens resolved at startup — autonomy.json per request)
├── uishot-script.mjs   --script for the house screenshot tool (wizard dismiss, chat send, Activity shot)
├── uishot-autonomy.mjs --script for the autonomy catalogue lane (dialogs, sheet, chart badges, docs)
├── verify-normal/      uishot run, scenario normal   (report.md + PNGs)
├── verify-busy/        uishot run, scenario busy
└── verify-empty/       uishot run, scenario empty
```

Field names follow the FastAPI handlers and SQLAlchemy `to_dict()` bodies under
`app/` (camelCase vs snake_case exactly as the real API serves them). Where the
frontend reads a name the backend does not emit, the mock stays faithful to the
backend and the mismatch is listed under **Known gaps** below.

## Run it

Two terminals from the repo root:

```bash
# 1. the mock (port 8100 is what frontend/vite.config.js proxies /api to)
node frontend/dev/mock-api.mjs --port 8100 --scenario normal

# 2. the app, auto-authenticated as "Dev User" (VITE_DEV_MODE skips /auth/me)
cd frontend && VITE_API_URL=/api/v1 VITE_DEV_MODE=true npm run dev -- --port 5190 --strictPort
```

Open http://localhost:5190/dashboard. The Vite dev proxy forwards `/api/*` to the
mock, so the SSE cookie, the chat stream and every REST call are same-origin.

CLI flags: `--port 8100` · `--host 127.0.0.1` · `--scenario <name>` · `--seed 42`
(PRNG seed for storyline picks and chunking) · `--slow-ms 2500` ·
`--chat-first-byte-ms 450` · `--quiet`.

### Pick a scenario

| How | Example | Scope |
|---|---|---|
| CLI default | `--scenario busy` | every request |
| header | `X-Mock-Scenario: empty` | that request (curl / fetch) |
| cookie | `document.cookie = 'mock_scenario=busy'` in devtools, then reload | the browser tab, including the EventSource (which cannot send headers) |
| query | `?mock_scenario=error` on any API URL | that request |
| runtime switch | `curl -X POST localhost:8100/__mock/scenario -H 'Content-Type: application/json' -d '{"scenario":"error"}'` | changes the CLI default without restarting |

Control surface (not proxied by Vite; hit port 8100 directly):
`GET /__mock/status` (scenario, open SSE clients, busy engine, every unknown path
seen so far), `POST /__mock/scenario`, `POST /__mock/reset` (drops in-memory
edits), `GET /api/v1/__mock/stream-test?mode=spaced|single|buffered` (diagnostic,
see Known gaps).

In-memory state: POST/PUT/PATCH/DELETE on agents, conversations, messages,
scheduled runs, MCP start/stop, orgs, invitations and API keys mutate the
process state (the `empty` scenario still shows what you just created). Restart
or `POST /__mock/reset` to go back to the fixtures.

### Scenario matrix

| Scenario | Roster | Platform | Conversations / tools / MCP / workflows / runs | Org & billing | Orchestration SSE |
|---|---|---|---|---|---|
| `normal` | 18 agents (the 17 seed agents + Cpl. Colophon, id `cpl.-colophon` as on dogfood, under Sgt. Scribe) with `reportsTo` chain (The General → leads → specialists), `affiliation`, `toolDetails`/`toolCostSummary` | `/health` healthy, 7 service checks (langfuse unhealthy), live `/stats` resources | 8 conversations (one 62-message with tool calls), 24 tools, 2 MCP servers (github running), 6 templates, 5 executions (**running, waiting, failed, 2 completed**), 5 scheduled runs (**one `lastStatus: error`**, one **`degraded`** — a status outside the contract's enum, as dogfood's zpool-health reports), 43 autonomy items | 2 orgs (Magic Unicorn + personal), 5 members, 4 invites; **professional plan**, caps, 14 metered events | `connected` + keep-alive pings; chat requests emit agent_started/tool_call/tool_result/agent_responding/agent_completed |
| `large` | 58 agents (18 + 40 synthesized: new leads The Colonel / The CMO / Perry / Maj. Recon with 16 legal drafters under Perry; `avatarUrl` points at existing `/avatars/*.webp`) | as normal | as normal, 7 MCP servers | as normal | as normal |
| `empty` | 0 agents, 0 domains | healthy, `/stats` all zero, 0 models/providers | nothing: `[]` everywhere, templates `[]`, 0 runs, knowledge graph empty (`success: true`) | only the caller's personal org and membership, no invites; **no plan** (`subscription_tier: null`, credits 0, no caps) | `connected` only |
| `busy` | as normal | as normal | as normal (the running execution is `exec-7c2a91-running`, the failed scheduled run is "Nightly fleet patrol") | as normal | **continuous storylines** every 4.5 s across random lead/specialist pairs: agent_started → agent_thinking → agent_invocation (internal) → lead tool_call/tool_result → agent_invocation (a2a or paid) → specialist tool_call → tool_result → agent_responding → agent_completed; every 4th storyline ends a `database` tool_call in **`agent_error`** with a human-readable reason. `/orchestration/state` reflects the live agent states. |
| `error` | — | `/health` **503** `{status: degraded}` | every data endpoint **500** `{detail: "Mock error scenario: …"}` | 500 | ticket mint and stream **401** (auth endpoints still 200 so the app does not bounce to login) |
| `slow` | as normal | as normal | every response (REST, ticket, SSE open, chat) delayed **2500 ms** | as normal | as normal |
| offline | — | — | not a scenario: simply do not start the mock. The app shows "API Unreachable", every page's error/retry state, and the Command Center's "Live feed disconnected" banner. | — | — |

### Streaming contracts (matched to the real code, not approximated)

- **Orchestration SSE** (`frontend/src/services/orchestrationStream.js`): `POST /orchestration/events/ticket` →
  `{ticket, expires_in: 60}` plus `Set-Cookie: brigade_sse_ticket=…; Path=/api/v1/orchestration; HttpOnly`.
  `GET /orchestration/events[?ticket=&mission_id=]` opens `text/event-stream`, first event
  `{"type":"connected","mission_id":null}`, then events shaped like `OrchestrationEvent.to_dict()`:
  `{id, type, timestamp, agentId, agentName, missionId, orgId, data, message}` with
  `data.toAgent/toAgentName/purpose/protocol` on `agent_invocation`, `data.tool/arguments` on
  `tool_call`, `data.tool/result` on `tool_result`, `data.tool/error` on `agent_error`. The mock is
  lenient about a missing/expired ticket (logs it once) — the real API 401s.
- **Per-agent chat** (`frontend/src/hooks/useAgentChat.js`, `pages/AgentChat.jsx`):
  `POST /agents/{id}/chat` with `{message, stream: true, history, model, temperature}` → SSE lines
  `start {agent, model, tools}` → `tool_call {id, name, arguments}` (+300 ms) → `tool_result {id, name, result, error, success}` (+800 ms)
  → ~50 `token {content}` chunks over ~3 s (real markdown: headings, lists, a code block, a table)
  → `complete {content, model, toolCalls}` → `data: [DONE]`. First byte is delayed 450 ms
  (`--chat-first-byte-ms`) because the page re-loads the conversation it just created and that GET
  must land before the stream opens — on the real API the model's latency guarantees it.
  Aborting the request (AbortController) stops the timers. `stream: false` returns JSON.
  Every chat also publishes agent_started/tool_call/tool_result/agent_responding/agent_completed to the orchestration bus, so open chats light up the Command Center.

## Endpoint coverage

Paths are relative to `/api/v1` (the un-versioned `/api/<x>` aliases resolve to the same handlers).
"data" rows return 500 in `error`; "health" rows return 503; auth rows always succeed.
Every route honours `slow` and the `large`/`empty` roster views.

| Endpoint | Shape (source of truth) | Scenario behaviour |
|---|---|---|
| `GET /health` | `{status, timestamp, memory_available, workflow_available}` (`routes.py`) | error → 503 `degraded` |
| `GET /stats` | `{totalAgents, activeAgents, totalModels, totalTools, totalConversations, totalMessages, uptime_seconds, status, version, resources{cpu_percent, memory_percent, memory_used_gb, memory_total_gb, disk_percent}}` (`system_routes.py`) | counts follow the roster view; `resources` walks a 24-sample fixture series so the Monitoring chart moves; empty → zeros |
| `GET /monitoring/services` · `/monitoring/health` · `POST /monitoring/check` | `{services:[{name, status, latency_ms, detail}], checked_at}` (`monitoring_routes.py`) | langfuse `unhealthy` by design |
| `GET /auth/config` | `{sso_enabled, native_register_enabled, langflow_enabled, falkordb_enabled, version, environment}` | always |
| `GET /auth/me` · `/auth/oidc/user` · `/users/me` | `{id, userId, email, name, role, authSource, permissions}` (`_auth_user_to_dict`); the oidc/user + users/me aliases add `tier`, `roles`, `username` | always 200 (admin "Dev User") |
| `POST /auth/oidc/refresh` | `{ok, expires_in}` (no JWT — cookie session) | always |
| `GET /auth/oidc/login` · `/logout` · `/callback` · `/permissions` · `/tool-access` · `/upgrade-info` · `POST /check-permission` | login → 302 `/auth/callback?login=success`; logout → 302 `/login` | always |
| `POST /users/login` · `/users/register` | `{apiKey, user}` | always |
| `GET/POST /users/me/api-keys` · `DELETE /users/me/api-keys/{id}` | `UserApiKey.to_dict()`: `{id, userId, name, keyPrefix, permissions, rateLimit, expiresAt, lastUsedAt, usageCount, isActive, createdAt, createdVia}`; POST also returns `key` once | data |
| `GET /agents` | `{agents:[Agent.to_dict() + _count + agentTools + toolDetails + toolCostSummary]}` incl. `reportsTo`, `avatarUrl`, `affiliation` | normal 17 · large 57 · empty 0 |
| `GET /agents/domains` | `{domains:[{name, count}]}` | derived from the roster view |
| `GET /agents/hierarchy` · `PUT /agents/hierarchy` · `PUT /agents/{id}/reports-to` | `{edges:[{agent, reportsTo}]}` / `{applied}` | data |
| `GET /agents/{id}` | agent dict + `apiKeys` | 404 unknown |
| `POST /agents` · `PUT /agents/{id}` · `DELETE /agents/{id}` | 201 agent / merged agent / `{message, id}` | in-memory |
| `GET/POST /agents/{id}/tools` · `DELETE/PATCH /agents/{id}/tools/{tool}` | `{tools, toolNames}` | in-memory |
| `GET/POST /agents/{id}/api-keys` · `GET/DELETE …/{keyId}` | `ApiKey.to_dict()` (`agentId`, `orgId`, …) | data |
| `POST /agents/{id}/chat` | SSE contract above; `stream:false` → `{response, model, toolCalls, usage}` | 404 unknown agent; error → 500 before the stream |
| `GET /agents/export/json` · `POST /agents/import/json` · `GET /tool-catalog` · `POST /agents/execute` · `/agents/sql` · `/agents/research` · `/agents/{id}/chat/local` | plausible | data |
| `GET /conversations?limit=` | `{conversations:[Conversation.to_dict() + agent{id,name,displayName,avatar}]}` sorted newest first | normal 8 · empty 0 |
| `GET /conversations/{id}` | conversation + `messages:[Message.to_dict()]` (`tool_calls`, `tool_results`, `tokens_used`, `created_at`) | 404 unknown |
| `POST /conversations` · `PATCH/DELETE /conversations/{id}` · `POST /conversations/{id}/messages` | 201 conversation / merged / `{message,id}` / 201 message (bumps `message_count`, `total_tokens`, `updated_at`) | in-memory |
| `GET /chat/models` | `{models:[{id, display_name, provider, category, input_price, output_price, …}], count, categories}` | empty → `[]` |
| `GET /providers` · `/providers/{id}` · `POST /providers/{id}/test` · `GET /llm/models` · `/models/local` | `{providers:[{id, name, type, endpoint, status, latency_ms, isDefault, …}], count}` | empty → `[]` |
| `POST /chat/completions` | OpenAI-style completion | data |
| `GET /tools` · `/tools/available` · `POST /tools/{id}/execute` | `{tools:[{id, name, description, type, domain, icon, provider, parameters, capabilities, status, schema}], count}` (`_format_tool`) | empty → `[]` |
| `GET /mcp/registry/servers` · `/servers/running` · `/servers/{name}` · `/health` | `list_available()` `{name, display_name, description, capabilities, transport, enabled, running}`; running adds `pid`; detail adds `command, args, env_vars` | normal 2 · large 7 · empty 0 |
| `POST /mcp/registry/servers/{name}/start\|stop\|restart` · `POST /servers` · `DELETE /servers/{name}` · `POST /tools/call` · sandbox endpoints · `GET /mcp/tools/list` | `{status, server}` etc.; start/stop flip the in-memory running set | data |
| `GET /hierarchical/templates[?tag=]` | `{workflows:[{id, name, description, tags, required_inputs, step_count, checkpoint_count}], count}` (snake_case list, camelCase when `tag` is given — exactly like the backend) | empty → `[]` |
| `GET /hierarchical/templates/{id}` | `{workflow: WorkflowDefinition.to_dict()}` camelCase with `teamLeads[].workers`, `steps`, `checkpoints`, `requiredInputs` | 404 unknown |
| `GET /hierarchical/executions[?state=&workflow_id=]` · `/executions/{id}` | `{executions:[WorkflowExecution.to_dict()]}` camelCase: `workflowId, workflowName, state, currentStep, startedAt, completedAt, stepExecutions{stepId:…}, pendingCheckpoint, error, totalTokens, totalCost, …` | normal 5 incl. running/failed/waiting |
| `POST /hierarchical/execute` · `/executions/{id}/cancel` · `/executions/{id}/checkpoint` | `{execution_id, status, message, execution}`; a started execution advances one step every 2.5 s until completed | in-memory |
| `GET /hierarchical/health` · `/domains` · `/workers` · `/models` · `/config/presets` · `POST /config/estimate-cost` | as `hierarchical_routes.py` | health → 503 in error |
| `GET /ralph/executions` · `/ralph/executions/{id}` · `POST /ralph/execute` | `{executions: []}` / 404 / started | data |
| `GET /scheduled-runs` | `{items:[ScheduledRun.to_dict()], total}` camelCase (`agentId, description, cron, timezone, enabled, lastRunAt, lastStatus, lastResultSummary, …`) | normal 5 (one `error`, one `degraded`, one disabled/`skipped`; three carry a `description`) · empty 0 |
| `GET /scheduled-runs/{id}` · `POST` · `PUT` (both take `description`, ≤2000 → 422) · `DELETE` (204) · `POST /{id}/run-now` (409 when disabled) · `GET /{id}/history` | history items `{id, scheduledRunId, startedAt, finishedAt, status, trigger, actor, outputSummary, error, toolCallsCount}`; run-now marks the run `running` then `success` after 6 s | in-memory |
| `GET /autonomy` | `{items:[CatalogueItem], counts{total, brigade, external, failing, stale, paused, never}, generatedAt}` — Brigade items from the scheduled runs (`responsibility` = `description`, `host` `brigade`, `runner` `brigade-scheduler`, `notes` null), outside jobs from `fixtures/autonomy.json` (its times are relative to now, or to the job's most recent scheduled fire via `$lastFire±…`, resolved per request so a healthy job reads as on schedule at any hour); `nextRunAt` from a standard 5-field cron engine in the job's zone; `health` by the contract's rule (paused → failing → never → stale at 1.5 × interval + 15 min → ok), with any `lastStatus` outside the enum counted as failing; sorted failing, stale, never, ok, paused, then agent, then name | normal 43 (6 failing incl. the `degraded` run, 4 stale, 3 never, 2 paused; 4 with BROKEN / FAILING / ORPHAN `notes`; 7 hosts; 16 agents + 23 unclaimed jobs, 22 of them owner `infra`) · busy = normal with the Build Log refresh `running` · empty 0 · error 500 |
| `PUT /autonomy/jobs/{key}` | `{created, item}` — validates the slug key (422 string), schema (422 pydantic-style list: missing, too long, not in the runner enum), agent exists, cron, IANA zone, `notes` ≤2000, and refuses a `command` that looks like a secret ("Don't store secrets in the command; reference them by name.") | in-memory upsert |
| `POST /autonomy/jobs/{key}/runs` | `201 {run, item}`; `running` opens a run, a terminal status with the same `runId` closes it, otherwise a finished run is inserted; updates the job's `last_*` (a success clears `lastError`); keeps 200 runs | 404 `No job '<key>'. Register it with PUT …/<key> first.` |
| `GET /autonomy/jobs/{key}/runs?limit=20` | `{runs:[{id, runId, status, startedAt, finishedAt, durationMs, summary, error}]}` newest first (max 100); a fixture job without history answers with its last run | busy prepends a `running` row for the Build Log refresh |
| `DELETE /autonomy/jobs/{key}` | 204 | 404 unknown |
| `POST /orchestration/events/ticket` · `GET /orchestration/events` | SSE contract above | error → 401 both; busy → storylines |
| `GET /orchestration/state` · `/agents/active` · `/missions` · `/missions/{id}` · `POST /missions` · `/command` · `/agents/create` | `get_state_snapshot()` `{missions, agentStates[{agentId, agentName, status, currentTask, …, agent}], recentEvents, activeAgentCount, activeMissionCount, totalAgents}`; missions `ActiveMission.to_dict()` | busy → live agent states; empty → no missions |
| `GET /orgs` · `/orgs/current` · `/orgs/{id}` · `POST /orgs` · `PATCH /orgs/{id}` | `Organization.to_dict() + role` (`planTier`, `metadata.personal`); `X-Org-Id` selects the current org | empty → personal org only |
| `GET /orgs/{id}/members` | `{members:[{userId, email, name, role, joinedAt}]}` | empty → caller only |
| `GET/POST /orgs/{id}/invitations[?status_filter=]` · `DELETE …/{invId}` · `POST /orgs/invitations/accept` | `Invitation.to_dict()` (`expiresAt`, `createdAt`, `status`); POST returns `token` once | empty → `[]` |
| `GET /billing/usage?limit=` | `{org_id, period{tokens, cost, events, since}, cap{monthly_token_cap, monthly_cost_cap, source, hard_stop}, over_cap, over_cap_reason, recent[{id, created_at, source, event_type, model, tokens, cost}], billing{paid, credits_remaining, subscription_tier}}` | normal → professional plan with caps · empty → no plan |
| `GET /billing/upgrade-requirements[?feature=]` | `{feature, currentTier, paid, creditsRemaining, requiredTier, benefits, upgradeUrl, opsCenterUrl}` | empty → trial |
| `GET /trace/recent?days=&limit=&offset=` · `/trace/agents/{id}` · `/trace/sessions/{id}` | `AttributionResponse[]` camelCase (`filePath, agentName, startLine, endLine, changeType, createdAt, …`) | normal 16 · empty `[]` |
| `GET /trace/stats` · `/trace/health` · `/trace/files/{path}` · `POST /trace/report` | `StatsResponse` (`totalLines, uniqueAgents, topAgents[], topFiles[]`) / file view / CSV download | 404 for an unknown file |
| `GET /knowledge/graph?entity_type=&name_pattern=&limit=` | `{success, nodes[{id, name, type, created_at, created_by, val}], links[{id, source, target, label, confidence, learned_at}], total_nodes, total_links}` | normal 20/24 · empty 0 |
| `GET /knowledge/stats` · `/entity/{name}` · `/entities` · `/relationships` · `/search` · `POST /query` · `/rag` | `{success, status, enabled, host, port, graphs, entity_types, relationship_types, total_entities, total_relationships}` / `{success, entity, relationships[{from, to, relationship}]}` | 404 `{success:false}` unknown entity |
| `GET /agent-builder/info` · `POST /agent-builder/chat` · `GET /agent-builder/session/{id}` | `{builder, theGeneral{agentCount}, capabilities{availableTools, availableDomains, availableModels[{id,name,provider}]}}` / `{sessionId, message, agentCreationIntent, usage}` / 404 | data |
| `GET /voice/health` · `/voice/config` · `/voice/rooms` · `POST /voice/rooms` · `GET/POST …/{id}/token` · `POST …/agent/join` · `DELETE …/{id}` | `{status, livekit{url, configured}, …}` | health → 503 in error |
| `GET /api/livekit/health` · `POST /api/livekit/token` (un-versioned, used by `LiveKitRoom.jsx`) | `{status:'ok'}` / `{token, url}` | health |
| `GET /langflow/health` · `/langflow/flows` | `unavailable` / `[]` (nav item stays hidden: `langflow_enabled:false`) | — |
| `POST /memory/search` · `/memory` · `/memory/query` · `GET /memory/user/{id}` | empty results | data |
| `GET /admin/rbac/denials` · `/admin/activity/conversations` · `POST /medical-test/*` · `GET /system/status` | plausible | data |
| any other `GET` | 200 `{items: [], count: 0, <lastSegment>: [], _mock}` + a one-time `[mock] UNKNOWN …` console warning, listed at `/__mock/status` | error → 500 |
| any other `POST/PUT/PATCH/DELETE` | 201/200 echo `{ok, id, …body, _mock}` + warning | — |

## Frontend calls NOT covered (and other known gaps)

Enumerated with `grep -rnE "apiJson\(|apiFetch\(|api\.[a-zA-Z]+\(|fetch\(|EventSource|axios\." frontend/src`.
Every call site found is served. The remaining gaps are contract mismatches between the
frontend and the backend the mock reproduces faithfully, plus one tooling artifact:

1. **Workflow executions modal reads snake_case the API never sends.** `pages/Workflows.jsx`
   lines ~594–718 read `execution.workflow_name`, `started_at`, `completed_at`,
   `duration_seconds`, `total_cost` (and matches templates by `workflow_id`), while
   `WorkflowExecution.to_dict()` serves `workflowName`, `startedAt`, `completedAt`, `totalCost`
   and has no duration field. The list view (lines ~482–499) reads both. The mock serves the
   backend's camelCase, so the modal shows "Unknown" dates — same as on the real API.
2. **Workflow gallery cards show "No workflow steps" / "Team Leads 0".** `WorkflowCard.jsx` /
   `MiniWorkflowDiagram.jsx` read `steps` and `team_leads`/`teamLeads` off the *list* items, but
   `list_workflows()` only returns `step_count` / `checkpoint_count`. Faithful to the backend.
3. **MCP server cards never show a category or env vars.** `MCPServers.jsx` groups by
   `server.category` and the card reads `server.env_vars`; `list_available()` serves neither
   (`env_vars` appears only on the detail endpoint). Faithful to the backend.
4. **`ScheduledRuns.jsx` logs a React "unique key" warning** (the `<>` fragment inside the
   rows `.map()` has no key — the key sits on the inner `<tr>`). This is the single console
   error in every uishot report; it is a frontend bug, not a missing endpoint.
5. **`AgentChat.jsx` races itself after creating a conversation.** `setSearchParams({conversation})`
   re-fires the `[searchParams, agents]` effect, which GETs the conversation and *replaces*
   `messages`, wiping the streaming assistant bubble if that GET lands after the chat stream
   opened. The mock's 450 ms first-byte delay (`--chat-first-byte-ms`) keeps the production
   ordering; set it to `0` to reproduce the bug. The same page also saves the assistant message
   twice (on `complete` and again after the loop).
6. **Tables in chat replies render as raw pipes** — `AgentChat.jsx` uses `react-markdown`
   without `remark-gfm`. The Command Center's `components/chat/Markdown.jsx` path may differ.
7. **uishot reports `net::ERR_ABORTED` for the chat stream on `/chat` even though it completes.**
   Reproducible with `GET /api/v1/__mock/stream-test?mode=spaced` read via `getReader()`:
   Chrome DevTools emits `requestfailed` when an incrementally-consumed chunked body ends
   (any content type, with or without the Vite proxy, `Connection: close` makes no difference),
   while the same body read with `res.text()` or sent in one write reports "finished". The
   fetch itself resolves `ok:true` and reads to `done`; the mock logs
   `chat stream <agent>: complete after …ms`. Treat that one "failed request" as a false
   positive; the real backend's `text/event-stream` chat triggers it identically.
8. **`/api/v1/orchestration/events` without a ticket is accepted** (logged once). The real
   API 401s; the frontend always mints a ticket first, so this only matters for hand-made
   EventSource experiments.
9. **`ActivityFeed` logs "two children with the same key `ev-N`" under a live stream.**
   `hooks/useOrchestrationStream.js` increments `seq.current` and then reads it *inside* the
   deferred `setEvents(prev => …)` updater; when two SSE events land in the same React batch
   (which a real orchestration bus does constantly) both updaters read the final counter and
   emit the same key. Visible on `/command` → Activity in the `busy` run (3 console errors);
   the fix is to compute the key before calling `setEvents`.
10. **Autonomy catalogue: what the mock does that the contract leaves open or gets wrong** (P-00092, e7816874;
   measured 2026-10-24):
   - **Day-of-week numbering.** `app/services/scheduler.py::_parse_cron` passes the weekday field straight to
     APScheduler 3.10.4's `CronTrigger(day_of_week=…)`, where **0 = Monday**. Measured in the brigade lane venv:
     `0 8 * * 1-5` fires Tue–Sat and `0 9 * * 1` fires on Tuesday. The UI (and this mock) read cron the standard
     way (0/7 = Sunday, so `1-5` = weekdays). Until the backend translates the weekday field, every humanized
     weekday schedule — on Scheduled runs and in the catalogue — is one day off from when the run actually fires.
     The backend lane reads OUTSIDE jobs as standard crontab and Brigade's own schedules exactly as the scheduler
     fires them, so its `nextRunAt` for a Brigade weekday schedule is the APScheduler one; the mock reads both the
     standard way. No dogfood Brigade schedule uses a weekday field today, so fixing `_parse_cron` to read standard
     crontab changes nothing that runs.
   - **Day-of-month AND weekday.** Vixie cron fires when EITHER restricted day field matches; APScheduler requires
     both. The mock uses the Vixie rule.
   - **Stale on weekends.** Read literally, the contract measures the interval between the NEXT two fire times
     from now: for a weekday job on a Sunday that is Mon→Tue (24 h), so Friday's run is "stale" by Sunday morning.
     The backend lane anchors it on the first fire time after `lastRunAt` (stale = that time + half the gap to the
     next fire + 15 min); the mock does the same.
   - **The secret check** runs on `command`, `runbookUrl` and `notes`, each with its own message, and its key
     shapes are anchored at a token boundary with a minimum length (a bare `sk-` matches `disk-guard.sh`). The mock
     and the form use the backend lane's exact patterns (`sk-`/`ubk-`/`sbk-` 16+, `ghp_` 20+, `AKIA` + 16, …).
   - **Agent ids with dots.** Cpl. Colophon is `cpl.-colophon` on dogfood (the contract's examples say
     `cpl-colophon`, which a real PUT would reject as an unknown agent). The UI encodes every id it puts in a path
     or a selector; the mock now decodes path params once in the dispatcher.
11. Not exercised by any page the mock was verified against, served with plausible shapes
   only: `/agent-builder/chat` (Gunny's builder flow), `/voice/rooms*` and LiveKit tokens
   (no LiveKit server — the voice modal cannot connect), `/langflow/*`, `/ralph/*`,
   `/mcp/registry/sandbox/*`, `/memory/*`, `/trace/report` CSV, `/orgs/invitations/accept`.

## Verification — autonomy catalogue lane (2026-10-24)

```bash
node frontend/dev/mock-api.mjs --port 8121 --scenario normal
cd frontend && VITE_PROXY_TARGET=http://localhost:8121 VITE_API_URL=/api/v1 VITE_DEV_MODE=true npx vite --port 5121 --strictPort
node ~/.claude/tools/uishot/uishot.mjs --url http://localhost:5121 \
  --routes "/command?view=autonomous,/agent/the-general,/agent/maj-devops,/scheduled-runs,/docs" \
  --viewport desktop --viewport mobile --script frontend/dev/uishot-autonomy.mjs \
  --out ~/lane-reports/2026-10-24-brigade-uiux/shots/autonomy-normal --no-fail --wait-ms 3000
# then POST /__mock/scenario {"scenario":"empty"} / {"scenario":"error"} / {"scenario":"busy"} and repeat with -empty / -error / -busy
```

`uishot-autonomy.mjs` never submits a form, so the mock's state is the same for every capture.

## Verification

Captured with the house screenshot tool (`~/.claude/tools/uishot/uishot.mjs`) at desktop
1440×900 over `/dashboard,/command,/chat,/library,/workflows,/scheduled-runs,/mcp-servers,/billing`,
with `frontend/dev/uishot-script.mjs` (dismisses the first-run wizard, sends a chat message on
`/chat`, takes an extra `activity` shot on `/command`):

```bash
node ~/.claude/tools/uishot/uishot.mjs --url http://localhost:5190 \
  --routes /dashboard,/command,/chat,/library,/workflows,/scheduled-runs,/mcp-servers,/billing \
  --viewport desktop --wait-ms 2500 --script frontend/dev/uishot-script.mjs \
  --out frontend/dev/verify-normal --no-fail
# busy: POST /__mock/scenario {"scenario":"busy"} first, then the same with --wait-ms 5000 and UISHOT_SETTLE_MS=6000
# empty: POST /__mock/scenario {"scenario":"empty"} first
```

| Run | Report | Console errors | Failed requests | Notes |
|---|---|---|---|---|
| normal | `frontend/dev/verify-normal/report.md` | 1 (gap 4, `/scheduled-runs`) | 1 (gap 7, `/chat`) | all 8 routes render fixture data; chart shows the 17-agent chain of command; `/chat` shows the streamed reply with its tool-call card |
| busy | `frontend/dev/verify-busy/report.md` | 4 (3 × gap 9 on `/command`, 1 × gap 4) | 1 (gap 7) | `/command` shows the "3 live comms" chip, pulsing delegation edges and lit status rings; `command__desktop__01-activity.png` is the Activity wall mid-storyline |
| empty | `frontend/dev/verify-empty/report.md` | **0** | **0** | CLEAN — every page's first-run state; billing shows "Free plan" with no cap, chart has no nodes |

None of the findings is a missing or mis-shaped endpoint: 4 and 9 are frontend key bugs, 7 is
a Chrome DevTools reporting artifact on streamed fetches. The mock's own log shows every
request served (`[mock …] METHOD path → status (scenario) ms`) and `GET /__mock/status`
lists zero unknown paths after the three runs.
