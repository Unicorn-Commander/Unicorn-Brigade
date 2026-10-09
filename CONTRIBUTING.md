# Contributing to Unicorn Brigade

Thanks for your interest in improving Brigade. This guide covers the basics of
getting set up and getting a change merged.

## Ground Rules

- Be honest in docs and commit messages — describe what the code actually does,
  not what it aspires to.
- Keep secrets out of the repo. Never commit a real key; `.env` is git-ignored
  and only `.env.example` (with placeholders) is tracked.
- Security issues go to **security@unicorncommander.ai**, not the public issue
  tracker. See [SECURITY.md](SECURITY.md).

## Development Setup

Brigade is a Python 3.11 / FastAPI backend (`app/`) and a React + Vite frontend
(`frontend/`).

```bash
# 1. Clone
git clone https://git.unicorncommander.ai/UnicornCommander/Unicorn-Brigade.git
cd Unicorn-Brigade

# 2. Backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 3. Config
cp .env.example .env      # then edit: BRIGADE_ADMIN_KEY, OPENAI_API_KEY, DB passwords

# 4. Run (either bare or via Docker)
uvicorn app.main:app --reload --port 8100
# or:  docker compose up -d

# 5. Frontend
cd frontend && npm install && npm run dev
```

For a full walkthrough see [docs/GETTING_STARTED.md](docs/GETTING_STARTED.md).

## Quality Checks

Run these before opening a pull request:

```bash
ruff check .          # lint
python -m pytest      # tests (some suites need optional extras / services)
```

Note: the full test suite has optional-dependency collection points (Slack,
LangGraph, asyncssh) and integration tests that need live services. When your
change is narrow, run the focused tests that exercise it and say so in the PR.

- Deterministic performance correctness tests run by default; wall-clock tests use the `perf` marker and are excluded by default.
- Run `BRIGADE_BENCHMARK=1 pytest tests/test_performance.py -m perf -s` to opt into benchmark mean/p95 output.

## Pull Requests

1. Branch off `main`.
2. Keep the change focused; explain the "why" in the description.
3. Update docs and `.env.example` when you add or change configuration.
4. Confirm `ruff` is clean and the relevant tests pass.

## License

By contributing you agree that your contributions are licensed under the
project's [Apache License 2.0](LICENSE).
