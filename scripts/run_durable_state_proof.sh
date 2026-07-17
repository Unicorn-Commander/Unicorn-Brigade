#!/usr/bin/env bash
#
# BR-4 durable-state proof runner.
#
# Spins an EPHEMERAL throwaway Postgres 16 in Docker, points the app DSNs at it,
# drives the REAL app migrations + the durability/leader-election assertions via
# scripts/prove_durable_state.py, and tears the container down. Nothing here
# touches any real/dogfood database — only the disposable container.
#
# The two BR-4 durability tables carry NO RLS (they are cross-org system
# bookkeeping read via admin_session), so — unlike run_org_rls_proof.sh — a
# single owner role is sufficient: DATABASE_URL == MIGRATION_DATABASE_URL.
#
# Exit codes: 0 = all assertions passed; 1 = an assertion failed;
#             3 = Docker unavailable (proof PENDING-Postgres — land code + retry).
#
# Usage:  scripts/run_durable_state_proof.sh
# Env:    PGPORT_PROOF (default 5601)   PG_IMAGE (default postgres:16)
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${PGPORT_PROOF:-5601}"
IMAGE="${PG_IMAGE:-postgres:16}"
CONTAINER="brigade-durable-proof-$$"
DB="brigade_durable_test"
OWNER_PW="postgres"

log() { printf '\033[1;35m[durable-proof]\033[0m %s\n' "$*"; }

cleanup() {
  log "tearing down ephemeral container ${CONTAINER}"
  docker rm -f "${CONTAINER}" >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

# ── 1. Ensure Docker is up (best-effort; open the app on macOS and poll) ───────
if ! docker info >/dev/null 2>&1; then
  log "Docker not responding — attempting to start it (open -a Docker)…"
  open -a Docker >/dev/null 2>&1 || true
  for _ in $(seq 1 45); do
    docker info >/dev/null 2>&1 && break
    sleep 2
  done
fi
if ! docker info >/dev/null 2>&1; then
  log "Docker is not available. Proof is PENDING-Postgres (code landed, rerun later)."
  exit 3
fi

# ── 2. Launch ephemeral Postgres ───────────────────────────────────────────────
log "starting ${IMAGE} as ${CONTAINER} on localhost:${PORT}"
docker run --rm -d \
  --name "${CONTAINER}" \
  -e POSTGRES_PASSWORD="${OWNER_PW}" \
  -e POSTGRES_DB="${DB}" \
  -p "${PORT}:5432" \
  "${IMAGE}" >/dev/null || { log "docker run failed"; exit 3; }

log "waiting for Postgres to accept connections…"
ready=""
for _ in $(seq 1 30); do
  if docker exec "${CONTAINER}" pg_isready -U postgres -d "${DB}" >/dev/null 2>&1; then
    ready=1; break
  fi
  sleep 1
done
if [ -z "${ready}" ]; then
  log "Postgres never became ready"; docker logs "${CONTAINER}" 2>&1 | tail -20; exit 3
fi
sleep 1  # pg_isready can flap 'ready' a beat before auth is live

# ── 3. Single-owner DSNs against the throwaway DB ──────────────────────────────
export MIGRATION_DATABASE_URL="postgresql+asyncpg://postgres:${OWNER_PW}@localhost:${PORT}/${DB}"
export DATABASE_URL="${MIGRATION_DATABASE_URL}"

# ── 4. Pick a Python that has the deps (prefer a project venv) ─────────────────
PY="python3"
for cand in "${REPO_ROOT}/venv/bin/python" "${REPO_ROOT}/.venv/bin/python"; do
  [ -x "${cand}" ] && PY="${cand}" && break
done
log "using interpreter: ${PY}"

# ── 5. Drive the real migrations + assertions ──────────────────────────────────
log "running scripts/prove_durable_state.py"
PYTHONPATH="${REPO_ROOT}" "${PY}" "${REPO_ROOT}/scripts/prove_durable_state.py"
rc=$?

log "proof exited with code ${rc}"
exit "${rc}"
