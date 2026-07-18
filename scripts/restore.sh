#!/usr/bin/env bash
# Unicorn Brigade — restore a pg_dump into a target database. This is the DANGEROUS
# half of DR: it DROPS and recreates objects. Guard-railed accordingly.
#
#   ./restore.sh <dump-file> [--into <PG_CONTAINER> <PG_USER> <PG_DB>]
#
# SAFETY MODEL:
#   * Refuses to run unless RESTORE_CONFIRM=yes is exported (no accidental restore).
#   * By default targets a THROWAWAY container/db, never a production name. Restoring
#     onto a name matching the deny-list (prod/live) additionally requires
#     RESTORE_ALLOW_PROD=yes — so a DR drill can never clobber prod by fat-finger.
#   * Verifies the dump's integrity (pg_restore --list) before touching the target.
#   * Verifies the sha256 sidecar if present.
set -euo pipefail

DUMP="${1:-}"
[ -n "${DUMP}" ] && [ -f "${DUMP}" ] || { echo "usage: restore.sh <dump-file> [--into <container> <user> <db>]" >&2; exit 2; }

PG_CONTAINER="${PG_CONTAINER:-brigade-restore-throwaway}"
PG_USER="${PG_USER:-postgres}"
PG_DB="${PG_DB:-brigade_restore}"
if [ "${2:-}" = "--into" ]; then
  PG_CONTAINER="${3:?container}"; PG_USER="${4:?user}"; PG_DB="${5:?db}"
fi

log() { echo "[restore] $*"; }
fail() { echo "[restore] ERROR: $*" >&2; exit 1; }

[ "${RESTORE_CONFIRM:-}" = "yes" ] || fail "refusing to restore without RESTORE_CONFIRM=yes"

# Prod guard: names containing prod/live require an extra explicit override.
if echo "${PG_CONTAINER} ${PG_DB}" | grep -qiE '(prod|live)'; then
  [ "${RESTORE_ALLOW_PROD:-}" = "yes" ] \
    || fail "target '${PG_CONTAINER}/${PG_DB}' looks like PRODUCTION — set RESTORE_ALLOW_PROD=yes to override (are you SURE?)"
  log "!!! PRODUCTION restore explicitly authorized — proceeding !!!"
fi

# sidecar checksum check (if present)
if [ -f "${DUMP}.sha256" ]; then
  ( cd "$(dirname "${DUMP}")" && sha256sum -c "$(basename "${DUMP}").sha256" >/dev/null ) \
    && log "sha256 OK" || fail "sha256 mismatch — refusing corrupt dump"
fi

docker ps --format '{{.Names}}' | grep -qx "${PG_CONTAINER}" || fail "target container '${PG_CONTAINER}' not running"

# integrity of the dump itself
docker exec -i "${PG_CONTAINER}" pg_restore --list < "${DUMP}" >/dev/null 2>&1 \
  || fail "dump is not a valid custom-format archive"

log "restoring ${DUMP} -> ${PG_CONTAINER}:${PG_DB} (role ${PG_USER})"
# Ensure the target DB exists (createdb is a no-op-safe attempt).
docker exec -i "${PG_CONTAINER}" createdb -U "${PG_USER}" "${PG_DB}" 2>/dev/null || true
# --clean --if-exists so a re-restore is idempotent; --no-owner/--no-acl so it lands
# cleanly regardless of role differences between source and target.
docker exec -i "${PG_CONTAINER}" pg_restore -U "${PG_USER}" -d "${PG_DB}" \
  --clean --if-exists --no-owner --no-acl < "${DUMP}"

log "DONE — restored into ${PG_CONTAINER}:${PG_DB}"
