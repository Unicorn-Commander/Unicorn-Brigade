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
3. **Ruff — gate (real breakage, tree-wide).** `ruff check --select E9,F63,F7
   app tests`. This subset (syntax errors, invalid comparisons, statement
   misuse) is currently **green** across the tree and **blocks** the PR if new
   code breaks it.
4. **Ruff — gate (full config, changed files).** The full `[tool.ruff]` config,
   run against only the Python files that differ from `origin/main`
   (`git merge-base origin/main HEAD`). New/changed code must pass the whole
   ruleset; the untouched legacy backlog is grandfathered. **Blocks** the PR.
   See the design note below.
5. **Ruff — advisory.** `ruff check .` using the full `[tool.ruff]` config in
   `pyproject.toml`. Non-blocking; surfaces the pre-existing lint backlog count.
6. **Mypy — advisory.** `mypy app`. Non-blocking type baseline.
7. **Pytest.** Runs **both** `tests/` and `app/tests/` (see `testpaths` in
   `pytest.ini`) with `--continue-on-collection-errors`.

### `frontend`
`npm ci && npm run build` in `frontend/` (Node 20, Vite build).

### `secrets`
gitleaks secret scan (SEC-1). Installs the pinned gitleaks binary (v8.30.1) and
runs `gitleaks git` scoped to the commits this push/PR introduces
(`origin/main..HEAD`), using the repo `.gitleaks.toml` allowlist. **Blocks** the
PR if a new secret is introduced. See the design note below; the same
`.gitleaks.toml` also drives the pre-commit hook and local scans.

## Design decisions (read before changing the gates)

### Ruff is tiered because the legacy backlog is large
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
ignore CI. So there are two gates plus an advisory:

- **Gate 1 — real-breakage subset, tree-wide.** `E9,F63,F7` on `app tests`,
  green today, catches new syntax-level breakage anywhere.
- **Gate 2 — full config, changed files only (SEC-1).** The complete
  `[tool.ruff]` ruleset, but scoped to Python files that differ from
  `origin/main`. This makes **new/changed code** pass the full linter while the
  ~5k-finding legacy backlog stays grandfathered. Implementation: diff
  `merge-base(origin/main, HEAD)..HEAD` for `*.py` (excluding `frontend/`,
  `alembic/versions/`, `migrations/`), then `ruff check <those files>`. If no
  Python files changed, the step is a no-op.
- **Advisory — full config, whole tree.** `ruff check .`, non-blocking, so the
  total backlog count stays visible.

Caveat of Gate 2: ruff lints a **whole file**, not just the changed lines — so
editing a legacy file that still carries findings will fail the gate. That is
intentional (touch it, clean it), but for a large legacy file split the change
or clean it in the same PR. When the backlog (and those 4 findings) is burned
down, fold the advisory into a tree-wide full-config gate.

### Secret scanning is diff-scoped for the same reason (SEC-1)
The `secrets` job runs **gitleaks** as a gate, and it is scoped to the pushed
commit range (`origin/main..HEAD`), **not** the full history — for exactly the
ruff reason above. The tree/history still carries a small number of pre-existing
real findings that are owed to the Security-Ops repo scan + the rotation lane, so
a whole-history gitleaks gate would be red on day one and train people to ignore
it. Diff-scoping blocks any **newly introduced** secret while grandfathering the
backlog.

- **Config / allowlist:** [`.gitleaks.toml`](../.gitleaks.toml) extends the
  gitleaks default ruleset and allowlists only vetted placeholders / test
  fixtures **by value** (e.g. `EXAMPLE`, `YOUR_*`, `${...}` doc curl tokens, the
  `REMOVED` dev sentinel the app refuses in prod, `sk-*-...`
  ellipsis doc keys, `whsec_` test values) plus `*.example`/`*.sample`/
  `*.template` template paths. Real values are **not** allowlisted, so they still
  trip.
- **Pre-commit hook:** [`.pre-commit-config.yaml`](../.pre-commit-config.yaml)
  wires the same gitleaks (pinned v8.30.1) as a **pre-commit** hook so a secret
  is caught *before* it enters history. Install per clone with
  `pip install pre-commit && pre-commit install`. The hook reads the same
  `.gitleaks.toml`.
- **Owed follow-up:** a **full-history / whole-repo** gitleaks scan is owed to
  the Security-Ops gitleaks engine (a repo-target run). Once history is scrubbed
  and the outstanding values are rotated, the CI gate can be flipped from
  diff-scoped to whole-tree.

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
# lint gate 1 — real breakage, tree-wide (must pass)
ruff check --select E9,F63,F7 app tests
# lint gate 2 — full config on files you changed vs main (must pass)
ruff check $(git diff --name-only --diff-filter=ACMR origin/main...HEAD -- '*.py')
# full lint (advisory)
ruff check .
# types (advisory)
mypy app
# tests — both suites
python3 -m pytest -q --continue-on-collection-errors
# frontend
cd frontend && npm ci && npm run build

# secret scan (SEC-1) — needs gitleaks (brew install gitleaks)
gitleaks git . -c .gitleaks.toml --log-opts="origin/main..HEAD" --redact   # gate range
gitleaks detect --no-git -c .gitleaks.toml --redact                        # whole working tree
# block secrets before they land — install the pre-commit hook once:
pip install pre-commit && pre-commit install
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
