#!/usr/bin/env bash
#
# Cross-tenant execution-disclosure fix proof runner.
#
# Unlike the RLS proofs, this needs NO Postgres: it is a pure in-process exercise
# of the REAL hierarchical + Ralph routers via a FastAPI TestClient, with the auth
# dependency overridden to impersonate an org-A / org-B / unbound / admin caller.
# It asserts each execution list/read endpoint is org-scoped (org-A sees only
# org-A; cross-org GET -> 404 not 403; unbound -> empty + 404; admin -> all).
#
# Exit codes: 0 = all assertions passed; 1 = a proof assertion failed.
#
# Usage:  scripts/run_execution_org_scoping_proof.sh
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Pick a Python that has the deps (prefer a project venv).
PY="python3"
for cand in "${REPO_ROOT}/venv/bin/python" "${REPO_ROOT}/.venv/bin/python"; do
  [ -x "${cand}" ] && PY="${cand}" && break
done
echo "[proof] using interpreter: ${PY}"

PYTHONPATH="${REPO_ROOT}" "${PY}" "${REPO_ROOT}/scripts/prove_execution_org_scoping.py"
rc=$?
echo "[proof] exited with code ${rc}"
exit "${rc}"
