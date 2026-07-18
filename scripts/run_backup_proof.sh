#!/usr/bin/env bash
# Proof harness for backup.sh + restore.sh — full round-trip against a THROWAWAY
# postgres:16 (never a real DB). Follows the repo's run_*_proof.sh pattern.
#
#   Creates data -> backup.sh -> simulate disaster (drop) -> restore.sh -> assert
#   every row + a content hash survived. Exit 0 pass, 1 fail, 3 docker unavailable.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
CT="brigade-backup-proof-$$"
PROOF_DIR="$(mktemp -d)"
export PG_CONTAINER="${CT}" PG_USER="postgres" PG_DB="brigade_proof" BACKUP_DIR="${PROOF_DIR}" RETENTION_DAYS="0"

cleanup() { docker rm -f "${CT}" >/dev/null 2>&1 || true; rm -rf "${PROOF_DIR}"; }
trap cleanup EXIT

command -v docker >/dev/null 2>&1 || { echo "PENDING-Docker: docker unavailable"; exit 3; }

echo "== spin throwaway postgres:16 (${CT}) =="
docker run --rm -d --name "${CT}" -e POSTGRES_PASSWORD=proof -e POSTGRES_USER=postgres \
  -e POSTGRES_DB="${PG_DB}" postgres:16 >/dev/null \
  || { echo "PENDING-Docker: cannot start container"; exit 3; }
READY=0
for i in $(seq 1 45); do
  if docker exec "${CT}" pg_isready -U postgres >/dev/null 2>&1; then READY=1; break; fi
  docker ps --format '{{.Names}}' | grep -qx "${CT}" || { echo "FAIL: container exited early"; docker logs "${CT}" 2>&1 | tail -20; exit 1; }
  sleep 1
done
if [ "${READY}" != "1" ]; then echo "FAIL: pg never ready after 45s"; docker logs "${CT}" 2>&1 | tail -20; exit 1; fi
echo "   pg ready"

echo "== seed realistic multi-table data (incl. an org-scoped billing ledger) =="
docker exec -i "${CT}" psql -U postgres -d "${PG_DB}" >/dev/null <<'SQL'
CREATE TABLE organizations (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), name text NOT NULL);
CREATE TABLE agents (id text PRIMARY KEY, org_id uuid REFERENCES organizations(id), title text);
CREATE TABLE usage_events (id bigserial PRIMARY KEY, org_id uuid, response_cost double precision, created_at timestamptz DEFAULT now());
INSERT INTO organizations (id, name) SELECT gen_random_uuid(), 'org '||g FROM generate_series(1,5) g;
INSERT INTO agents (id, org_id, title) SELECT 'agent-'||g, (SELECT id FROM organizations ORDER BY random() LIMIT 1), 'title '||g FROM generate_series(1,50) g;
INSERT INTO usage_events (org_id, response_cost) SELECT (SELECT id FROM organizations ORDER BY random() LIMIT 1), (random()*0.01)::float FROM generate_series(1,500) g;
SQL

# fingerprints BEFORE backup
BEFORE_ORGS=$(docker exec -i "${CT}" psql -U postgres -d "${PG_DB}" -Atc "SELECT count(*) FROM organizations;")
BEFORE_AGENTS=$(docker exec -i "${CT}" psql -U postgres -d "${PG_DB}" -Atc "SELECT count(*) FROM agents;")
BEFORE_SUM=$(docker exec -i "${CT}" psql -U postgres -d "${PG_DB}" -Atc "SELECT round(sum(response_cost)::numeric,6) FROM usage_events;")
BEFORE_HASH=$(docker exec -i "${CT}" psql -U postgres -d "${PG_DB}" -Atc "SELECT md5(string_agg(id||coalesce(title,''), ',' ORDER BY id)) FROM agents;")
echo "   before: orgs=${BEFORE_ORGS} agents=${BEFORE_AGENTS} cost_sum=${BEFORE_SUM} hash=${BEFORE_HASH}"

echo "== run backup.sh =="
bash "${HERE}/backup.sh"
DUMP="$(ls -t ${PROOF_DIR}/${PG_DB}/*.dump | head -1)"
[ -f "${DUMP}" ] || { echo "FAIL: no dump produced"; exit 1; }
echo "   dump: ${DUMP}"

echo "== verify sha256 sidecar =="
( cd "$(dirname "${DUMP}")" && sha256sum -c "$(basename "${DUMP}").sha256" >/dev/null ) \
  && echo "   sha256 OK" || { echo "FAIL: sidecar checksum"; exit 1; }

echo "== simulate DISASTER: drop all data =="
docker exec -i "${CT}" psql -U postgres -d "${PG_DB}" -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;" >/dev/null
POST_DROP=$(docker exec -i "${CT}" psql -U postgres -d "${PG_DB}" -Atc "SELECT count(*) FROM information_schema.tables WHERE table_schema='public';")
[ "${POST_DROP}" = "0" ] || { echo "FAIL: drop didn't clear schema (${POST_DROP})"; exit 1; }
echo "   schema empty (${POST_DROP} tables)"

echo "== run restore.sh =="
RESTORE_CONFIRM=yes bash "${HERE}/restore.sh" "${DUMP}" --into "${CT}" postgres "${PG_DB}"

echo "== assert full recovery =="
AFTER_ORGS=$(docker exec -i "${CT}" psql -U postgres -d "${PG_DB}" -Atc "SELECT count(*) FROM organizations;")
AFTER_AGENTS=$(docker exec -i "${CT}" psql -U postgres -d "${PG_DB}" -Atc "SELECT count(*) FROM agents;")
AFTER_SUM=$(docker exec -i "${CT}" psql -U postgres -d "${PG_DB}" -Atc "SELECT round(sum(response_cost)::numeric,6) FROM usage_events;")
AFTER_HASH=$(docker exec -i "${CT}" psql -U postgres -d "${PG_DB}" -Atc "SELECT md5(string_agg(id||coalesce(title,''), ',' ORDER BY id)) FROM agents;")
echo "   after:  orgs=${AFTER_ORGS} agents=${AFTER_AGENTS} cost_sum=${AFTER_SUM} hash=${AFTER_HASH}"

FAILED=0
[ "${BEFORE_ORGS}"   = "${AFTER_ORGS}" ]   || { echo "FAIL orgs ${BEFORE_ORGS}!=${AFTER_ORGS}"; FAILED=1; }
[ "${BEFORE_AGENTS}" = "${AFTER_AGENTS}" ] || { echo "FAIL agents ${BEFORE_AGENTS}!=${AFTER_AGENTS}"; FAILED=1; }
[ "${BEFORE_SUM}"    = "${AFTER_SUM}" ]    || { echo "FAIL cost_sum ${BEFORE_SUM}!=${AFTER_SUM}"; FAILED=1; }
[ "${BEFORE_HASH}"   = "${AFTER_HASH}" ]   || { echo "FAIL hash mismatch"; FAILED=1; }

echo "== negative test: restore without RESTORE_CONFIRM must be refused =="
if bash "${HERE}/restore.sh" "${DUMP}" --into "${CT}" postgres "${PG_DB}" >/dev/null 2>&1; then
  echo "FAIL: restore ran without RESTORE_CONFIRM"; FAILED=1
else
  echo "   correctly refused unconfirmed restore"
fi

echo "== negative test: prod-named target refused without RESTORE_ALLOW_PROD =="
if RESTORE_CONFIRM=yes bash "${HERE}/restore.sh" "${DUMP}" --into "${CT}" postgres "brigade_prod" >/dev/null 2>&1; then
  echo "FAIL: prod-named restore ran without RESTORE_ALLOW_PROD"; FAILED=1
else
  echo "   correctly refused prod-named restore"
fi

if [ "${FAILED}" = "0" ]; then echo "PROOF PASS ✅ — full backup→disaster→restore round-trip + guards verified"; exit 0
else echo "PROOF FAIL ❌"; exit 1; fi
