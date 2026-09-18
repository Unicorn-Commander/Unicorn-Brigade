# uc-browser bridge — real Chrome for Brigade agents

`app/llm/ucbrowser_mcp_tools.py` proxies the uc-browser gate
(`https://browser.magicunicorn.dev/mcp`, Playwright MCP 0.0.81 driving a real
Chrome) into nine Brigade agent tools. Same shape as the Center-Deep bridge:
uchub client_credentials bearer, JSON-RPC `tools/call` over Streamable HTTP,
`ToolDefinition` wrappers, env-gated registration in `tool_resolver`.

## Tools

| tool | upstream | notes |
|---|---|---|
| `ucb_navigate(url)` | `browser_navigate` | returns final URL/title only — content is not in the reply |
| `ucb_snapshot()` | `browser_snapshot` | accessibility YAML with `[ref=eN]` tags (truncated at `UC_BROWSER_TEXT_MAX`) |
| `ucb_page_text(url=None)` | `browser_navigate` (if url) + `browser_evaluate('() => document.body.innerText')` | truncated at `UC_BROWSER_TEXT_MAX` (20 000 chars) |
| `ucb_click(element, ref)` | `browser_click` | `ref` → upstream `target` |
| `ucb_type(element, ref, text, submit=false)` | `browser_type` | `ref` → `target`; `submit` sent only when true |
| `ucb_fill_form(fields)` | `browser_fill_form` | each field `{name, type, ref, value}`; `ref` → `target`, bools → `"true"/"false"` |
| `ucb_screenshot(full_page=false)` | `browser_take_screenshot` | returns `saved_as` (path on the browser host), mime, size; base64 only when `UC_BROWSER_IMAGE_INLINE_MAX` allows |
| `ucb_pdf_save()` | `browser_pdf_save` | returns `saved_as` |
| `ucb_console_messages(level="info")` | `browser_console_messages` | console log text |

All results are `{"result": ...}` or `{"error": "<text>"}`; the tool loop
JSON-dumps them for the model. Playwright's `isError` replies and JSON-RPC
error objects both become `{"error": ...}`.

## Enable for an agent

Add the tool names to the agent record's `tools` list (any subset):

```json
{"tools": ["ucb_navigate", "ucb_page_text", "ucb_snapshot", "ucb_screenshot"]}
```

Add `ucb_click`, `ucb_type`, `ucb_fill_form` only for agents that should act
on pages, not just read them. All agents share ONE pinned browser session at
the gate (one Chrome, one current tab): give the browser to one agent at a
time.

## Enable in the deployment (bigboy)

The prod Brigade is compose project `uc-cloud-production`, file
`/home/muut/UC-Cloud-production/docker-compose.brigade.yml`, service
`unicorn-brigade`. Its config is the inline `environment:` block (no
env_file). Add one line there, next to `KNOWLEDGE_OPS_URL`:

```yaml
      UC_BROWSER_MCP_URL: https://browser.magicunicorn.dev/mcp
```

Nothing else is needed: the bearer is minted with the `KEYCLOAK_CLIENT_ID` /
`KEYCLOAK_CLIENT_SECRET` already in that block (the gate accepts
`azp=brigade`), and the token endpoint defaults to the same uchub URL as
`OIDC_TOKEN_ENDPOINT`. Optional knobs: `UC_BROWSER_MCP_TIMEOUT` (default 60 s;
keep it below the tool loop's `TOOL_EXECUTION_TIMEOUT_SECONDS`, default 60 —
raise that to 90 if slow sites time out), `UC_BROWSER_TEXT_MAX`,
`UC_BROWSER_IMAGE_INLINE_MAX`, `UC_BROWSER_TOKEN_URL`,
`UC_BROWSER_CLIENT_ID/SECRET`.

Registration is gated on `UC_BROWSER_MCP_URL`: unset → the `ucb_*` names do
not exist, and the container log says `uc-browser tools skipped`.

## How the prod image is built and deployed (discovered 2026-09-17, read-only)

- `unicorn-brigade:latest` is **built on bigboy** from a git checkout, not
  pulled: `build: context: ./Unicorn-Brigade, dockerfile: Dockerfile`
  relative to `/home/muut/UC-Cloud-production`. The Dockerfile `COPY`s the
  working tree — **what is on disk is what ships, not HEAD.**
- The checkout is `/home/muut/UC-Cloud-production/Unicorn-Brigade`
  (origin = Forgejo `UnicornCommander/Unicorn-Brigade`, branch `main`).
- Running image was built 2026-09-02; the container was recreated 09-13 and
  restarted 09-17 16:41Z.

**Precondition — the build context is dirty and prod runs the dirty tree.**
On 09-17 `git status` there showed `app/llm/ops_center_client.py` and
`app/api/openai_compat_routes.py` modified (plus a `.bak-20260917-route`),
and the running container's copies are byte-identical to those working-tree
files, i.e. prod = a 09-17 "route" patch (direct Anthropic/OpenAI/DashScope
keys) that is **not on main**, and it **lacks** main's BR-6.4 per-caller
authorization in `openai_compat_routes.py`. Consequences:

- `git checkout` of this branch there will be refused (local changes), and
  `git stash` would drop the route patch prod is running.
- Building from the tree as-is ships the route patch but not BR-6.4.

Whoever owns the route patch must commit it (or decide to drop it) before
this bridge is deployed. Do not resolve that from this lane.

### Deploy commands (for the orchestrator; not run here)

```bash
ssh bigboy
cd /home/muut/UC-Cloud-production/Unicorn-Brigade

# 0. Preflight — STOP if this prints anything you do not expect.
git status --short
git log --oneline -1
md5sum app/llm/ops_center_client.py app/api/openai_compat_routes.py
docker exec unicorn-brigade md5sum /app/app/llm/ops_center_client.py /app/app/api/openai_compat_routes.py

# 1. Reconcile the dirty tree (owner's call): commit the route patch on a
#    branch and merge it with feat/uc-browser-bridge-20260917, or stash it
#    knowingly. Only then:
git fetch origin
git checkout feat/uc-browser-bridge-20260917   # or main once merged
git log --oneline -1

# 2. Env line (edit, then verify — values are not secrets, but keep the diff small)
cd /home/muut/UC-Cloud-production
grep -n "KNOWLEDGE_OPS_URL" docker-compose.brigade.yml   # add the line right after it:
#      UC_BROWSER_MCP_URL: https://browser.magicunicorn.dev/mcp
docker compose -f docker-compose.brigade.yml config 2>/dev/null | grep -n "UC_BROWSER_MCP_URL"

# 3. Build + recreate (the build takes minutes: full pip install)
docker compose -f docker-compose.brigade.yml build unicorn-brigade
docker compose -f docker-compose.brigade.yml up -d unicorn-brigade

# 4. Verify — measure, do not assume
docker inspect unicorn-brigade --format 'StartedAt={{.State.StartedAt}} Image={{.Image}}'
docker logs unicorn-brigade --since 5m 2>&1 | grep -i "uc-browser tools"
docker exec unicorn-brigade python -c "from app.llm.tool_resolver import TOOL_REGISTRY as R; print(sorted(k for k in R if k.startswith('ucb_')))"
docker exec unicorn-brigade md5sum /app/app/llm/ops_center_client.py   # must match step 0's intended lineage
# then: put {"tools":["ucb_page_text"]} on a test agent and ask it what https://example.com says.
```

Rollback: `git checkout <previous sha>` in the checkout, rebuild, `up -d`
(or simply remove the env line and `up -d` — the tools vanish, the module is
inert).

## Transport details worth knowing

- Accept header is `application/json, text/event-stream` (spec). The gate
  unwraps SSE to JSON for callers that omit `text/event-stream`; we parse
  either framing (`_parse_streamable_response`, last `result`/`error` frame).
- `Mcp-Session-Id`: stored per process and resent. If a call is refused with
  HTTP 400/404 and a "session"/"initialized" message (the MCP SDK's `-32000
  Bad Request: Server not initialized` / `-32001 Session not found`), the
  module runs `initialize` + `notifications/initialized` once and retries
  once. Measured against a local `playwright-mcp --port` (real SDK transport)
  on 2026-09-17: first call 400 → handshake → session reused for every later
  call; a deliberately stale id re-handshakes transparently.
- Every request carries a browser-style `User-Agent` — Cloudflare 403s
  `python-httpx/…` on our hosts.
- The bearer is cached in memory for ≤ 4 min and never written anywhere.

## Schema mismatches vs Playwright MCP 0.0.81 (kept on purpose)

1. **`ref` vs `target`.** 0.0.81 calls the element reference `target`
   ("exact target element reference from the page snapshot, or a unique
   element selector"); older releases called it `ref`. The agent-facing tools
   keep `ref` and the module remaps it, also inside `fill_form` fields (whose
   schema is `additionalProperties: false` — sending `ref` upstream is a
   hard error: `expected string, received undefined → at target`).
   `ucb_click`/`ucb_type` also accept `target` as an alias.
2. **`element` is optional upstream** (it is a human-readable label "used to
   obtain permission"). Kept optional here; descriptions encourage it.
3. **`level` and `scale` are `required` upstream despite having defaults**
   (`browser_console_messages.level="info"`,
   `browser_take_screenshot.scale="css"`). The module always sends them.
4. **Implicit snapshots are files, not text.** After navigate/click/type,
   0.0.81 writes the snapshot to a file on the browser host and only links
   it; only an explicit `browser_snapshot` returns the YAML inline. So
   `ucb_navigate` returns URL/title and the agent must call `ucb_snapshot` or
   `ucb_page_text` to read the page. `ucb_page_text` uses `browser_evaluate`,
   whose `### Result` is the JSON-encoded return value (decoded here).
5. **Screenshots** come back as a file link plus an `image` content item
   (base64). The tool loop feeds a text model, so base64 is omitted by
   default (`UC_BROWSER_IMAGE_INLINE_MAX=0`); the path on the browser host is
   returned instead.

## Tests

`tests/test_ucbrowser_mcp_tools.py` — 33 tests, hermetic (`httpx.MockTransport`
plays uchub + the gate; the canned replies are real 0.0.81 responses captured
from a throwaway headless instance). Runs standalone without Postgres/Redis:

```bash
python3 -m pytest tests/test_ucbrowser_mcp_tools.py -q
```

Needs only `httpx`, `pytest`, `pytest-asyncio`, `python-dotenv` (the shared
conftest imports dotenv). The last test (runtime registration through
`tool_resolver`) skips itself when `slack_sdk` & co. are absent and runs in
the full environment/CI.
