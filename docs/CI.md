# CI / CD — Unicorn Brigade

Continuous integration runs on **Forgejo Actions** (Gitea-Actions syntax) via
the self-hosted `act_runner` registered to
`git.unicorncommander.ai/UnicornCommander/Unicorn-Brigade`.

Workflow: [`.forgejo/workflows/ci.yml`](../.forgejo/workflows/ci.yml).

## What runs, and when

Triggers: every `push` to `main`, `feat/**`, `swarm/**`, and every
`pull_request` targeting `main`. Superseded runs on the same ref are cancelled.

Two parallel jobs:

### `backend`
1. **Set up Python 3.11** (matches the Dockerfile's `python:3.11-slim`).
2. **Install deps** — `requirements-prod.txt` (the runtime set the prod image
   installs) plus the test/lint tooling (`pytest`, `pytest-asyncio`,
   `pytest-cov`, `ruff`, `mypy`).
3. **Ruff — gate.** `ruff check --select E9,F63,F7 app tests`. This subset
   (syntax errors, invalid comparisons, statement misuse) is currently **green**
   across the tree and **blocks** the PR if new code breaks it.
4. **Ruff — advisory.** `ruff check .` using the full `[tool.ruff]` config in
   `pyproject.toml`. Non-blocking; surfaces the pre-existing lint backlog.
5. **Mypy — advisory.** `mypy app`. Non-blocking type baseline.
6. **Pytest.** Runs **both** `tests/` and `app/tests/` (see `testpaths` in
   `pytest.ini`) with `--continue-on-collection-errors`.

### `frontend`
`npm ci && npm run build` in `frontend/` (Node 20, Vite build).

## Design decisions (read before changing the gates)

### Ruff is two-tier because the legacy backlog is large
A full `ruff check .` currently reports ~5k findings (mostly style + import
sorting) plus **4 real `F821`/`F823` undefined-name findings** that predate this
work:

| File | Finding |
| --- | --- |
| `app/engine/executor.py:465` | `F821` undefined `List` |
| `app/llm/advanced_tools.py:192` | `F823` `datetime` referenced before assignment |
| `app/llm/mlx_provider.py:457` | `F821` undefined `user_id` |
| `app/protocols/mcp.py:427` | `F821` undefined `ProtocolMCPTransport` |

Gating the whole thing on day one would paint every PR red and teach everyone to
ignore CI. So the **gate** is the minimal real-breakage subset (green today) and
the **full config runs advisory**. When the backlog (and those 4 findings) is
burned down, promote the advisory step to a gate by folding its select into the
gate step / removing `continue-on-error`.

### Pytest resilience — why `--continue-on-collection-errors`
The suite has known import-time fragility from optional deps and from the
`app/memory/graphiti_manager.py` import guard (fixed on the `feat/br-1.x`
branches, may not be on `main` yet). Approach:

- Install `requirements-prod.txt` so the previously-missing optional deps
  (`slack_sdk`, `asyncssh`, `langgraph`, `openai`, …) are present — those
  bare-import collection errors are simply resolved.
- `graphiti-core` is **not** installed in CI (matches the prod image, which
  layers it in a separate step with a redis-compat patch). With the import
  guard fixed, the memory manager degrades to `GRAPHITI_AVAILABLE=False` and the
  suites collect. On a branch that still has the guard bug, that one module is
  reported as a collection **ERROR** and the run continues.
- `--continue-on-collection-errors` means a module that cannot be imported is
  logged as an ERROR (visible, not hidden) while **every other test still runs**.
  Real test **failures** still fail the job — this widens coverage without
  letting an unrelated pre-existing import error mask a genuine regression, and
  without letting it silently swallow one either (collection errors keep the job
  red until resolved; check the log to tell the two apart, or the uploaded
  `pytest-report.xml`).

If you want collection errors to be strictly non-fatal in the short term, gate
only `tests/` and move `app/tests/` to its own `continue-on-error: true` step —
but the goal is to get both suites collecting cleanly on `main`.

## Running the same checks locally

```bash
# lint gate (must pass)
ruff check --select E9,F63,F7 app tests
# full lint (advisory)
ruff check .
# types (advisory)
mypy app
# tests — both suites
python3 -m pytest -q --continue-on-collection-errors
# frontend
cd frontend && npm ci && npm run build
```

`make lint` / `make format` / `make test` wrap the common ones.

---

# Release / promotion runbook

Deploy topology (Tailscale mesh; internal traffic is direct, not via
Cloudflare):

- **bigboy** (`magicunicorn`, `100.126.207.157`, ssh `muut@`) — the **builder**.
  Has the GPUs and the fat build context.
- **commander** (`100.79.41.137`) — the **prod runtime** host.

The canonical method is **build on bigboy, `docker save | docker load` to
commander** — images are streamed over the mesh, not pulled from a registry.

## 1. Build & tag (on bigboy)

```bash
# on bigboy, from the repo checkout
cd /path/to/Unicorn-Brigade
git pull                      # bigboy builds from src/ — pull first (known gotcha)

# tag with the frontend/app version + short SHA so the running image is traceable
VERSION=$(node -p "require('./frontend/package.json').version")
TAG="v${VERSION}-$(git rev-parse --short HEAD)"

docker build -t unicorn-brigade:${TAG} -t unicorn-brigade:latest .
```

Do **not** rely on `latest` alone in prod — the `vX.Y.Z-<sha>` tag is what makes
"which build is actually running" answerable (verify by image tag + container
`StartedAt`, not by release notes).

## 2. Promote to dogfood

Deploy the tagged image to the dogfood stack first and smoke-test the API
(`/api/v1/health`) + a real agent run before touching prod. Keep the previous
tag available for instant rollback.

## 3. Ship to prod (bigboy -> commander)

```bash
# stream the image bigboy -> commander over the mesh (no registry)
docker save unicorn-brigade:${TAG} | ssh muut@100.79.41.137 'docker load'

# on commander: pin the compose to the new tag and recreate just the API
ssh muut@100.79.41.137
  cd /path/to/Unicorn-Brigade
  # set image: unicorn-brigade:${TAG} (env var or compose override — avoid :latest drift)
  docker compose up -d brigade-api
  docker compose ps
  curl -sf http://localhost:8100/api/v1/health
```

`deploy.sh` at the repo root wraps the compose build/up/health-wait loop for a
same-host deploy; the cross-host promotion above is the `save | load` streaming
variant of that.

### Deploy gotchas (carried from ops notes)
- **Never `rsync --delete` a prod tree.** Stream images, don't sync source over
  a running deploy.
- **Never deploy suite containers from `/tmp`.**
- **Verify by image tag + `StartedAt`**, not by CHANGELOG/release notes — those
  can lie about what is deployed.
- **Nested-ssh piping eats stdin** — if you wrap the `docker load` in a script,
  run it as a file and pass `-n` / `</dev/null` so the stream isn't swallowed.
- **Rollback** = re-`up` the previous `vX.Y.Z-<sha>` tag (still loaded on
  commander); no rebuild needed.
