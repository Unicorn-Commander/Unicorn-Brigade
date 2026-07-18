#!/usr/bin/env bash
# Unicorn Brigade — durable backup of the primary stateful surface (PostgreSQL),
# plus optional Qdrant vector snapshots. READ-SIDE ONLY — a pg_dump against a live
# DB is safe and non-blocking (MVCC snapshot); this script never writes to the app DB.
#
# Runs on the HOST (bigboy/commander), reaching the DB inside its docker container.
# Configure via env (see BRIGADE-DR.md). Safe defaults; degrades gracefully when an
# optional surface (Qdrant / object storage) is not configured.
#
#   PG_CONTAINER   docker container running Postgres            (default: unicorn-postgresql)
#   PG_USER        postgres role                                (default: unicorn)
#   PG_DB          database to dump                             (default: brigade_db)
#   BACKUP_DIR     where dumps land on the host                 (default: /home/muut/brigade-backups)
#   RETENTION_DAYS prune local dumps older than N days          (default: 14)
#   # optional object-store offload (S3-compatible, e.g. Garage):
#   BACKUP_S3_BUCKET, BACKUP_S3_ENDPOINT, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY
#   # optional Qdrant snapshot:
#   QDRANT_URL   (e.g. http://unicorn-qdrant:6333 or http://127.0.0.1:6333)
set -euo pipefail

PG_CONTAINER="${PG_CONTAINER:-unicorn-postgresql}"
PG_USER="${PG_USER:-unicorn}"
PG_DB="${PG_DB:-brigade_db}"
BACKUP_DIR="${BACKUP_DIR:-/home/muut/brigade-backups}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
TS="$(date -u +%Y%m%dT%H%M%SZ)"
STAMP_HOST="$(hostname -s 2>/dev/null || echo host)"
DEST="${BACKUP_DIR}/${PG_DB}"
DUMP="${DEST}/${PG_DB}-${STAMP_HOST}-${TS}.dump"

log() { echo "[backup ${TS}] $*"; }
fail() { echo "[backup ${TS}] ERROR: $*" >&2; exit 1; }

mkdir -p "${DEST}"

command -v docker >/dev/null 2>&1 || fail "docker not found on host"
docker ps --format '{{.Names}}' | grep -qx "${PG_CONTAINER}" \
  || fail "postgres container '${PG_CONTAINER}' not running"

# --- 1. Postgres: custom-format dump (compressed, restorable selectively) --------
log "pg_dump ${PG_CONTAINER}:${PG_DB} (role ${PG_USER}) -> ${DUMP}"
# -Fc custom format, -Z6 compression. Stream out of the container to the host file.
if ! docker exec "${PG_CONTAINER}" pg_dump -U "${PG_USER}" -d "${PG_DB}" -Fc -Z6 > "${DUMP}"; then
  rm -f "${DUMP}"
  fail "pg_dump failed"
fi

# Integrity gate: a valid custom dump must list its table of contents. This catches
# a truncated/empty/corrupt dump BEFORE we trust it or prune older good copies.
if ! docker exec -i "${PG_CONTAINER}" pg_restore --list < "${DUMP}" >/dev/null 2>&1; then
  rm -f "${DUMP}"
  fail "dump failed integrity check (pg_restore --list) — NOT keeping a bad backup"
fi
SIZE="$(du -h "${DUMP}" | cut -f1)"
OBJCOUNT="$(docker exec -i "${PG_CONTAINER}" pg_restore --list < "${DUMP}" | grep -c ';' || true)"
log "OK postgres dump ${SIZE}, ${OBJCOUNT:-?} archive entries, verified restorable"

# checksum sidecar for tamper/transfer detection
( cd "${DEST}" && sha256sum "$(basename "${DUMP}")" > "$(basename "${DUMP}").sha256" )

# --- 2. Qdrant snapshot (optional) ----------------------------------------------
if [ -n "${QDRANT_URL:-}" ]; then
  log "Qdrant snapshot via ${QDRANT_URL}"
  QSNAP="${DEST}/qdrant-${STAMP_HOST}-${TS}.json"
  if curl -fsS -X POST "${QDRANT_URL%/}/snapshots" -H 'content-type: application/json' > "${QSNAP}" 2>/dev/null; then
    log "OK qdrant snapshot metadata -> ${QSNAP} (binary snapshot retained inside Qdrant volume)"
  else
    log "WARN qdrant snapshot request failed (non-fatal) — check QDRANT_URL"
    rm -f "${QSNAP}"
  fi
else
  log "skip Qdrant (QDRANT_URL not set)"
fi

# --- 3. Object-store offload (optional, S3-compatible / Garage) ------------------
if [ -n "${BACKUP_S3_BUCKET:-}" ]; then
  if command -v aws >/dev/null 2>&1; then
    ENDPOINT_ARG=()
    [ -n "${BACKUP_S3_ENDPOINT:-}" ] && ENDPOINT_ARG=(--endpoint-url "${BACKUP_S3_ENDPOINT}")
    KEY="brigade/${PG_DB}/${STAMP_HOST}/$(basename "${DUMP}")"
    log "offload -> s3://${BACKUP_S3_BUCKET}/${KEY}"
    # Garage/S3: server-side checksums differ from local; --no-guess-mime-type avoids
    # a class of Garage SDK header mismatches. Upload dump + its sha256 sidecar.
    aws "${ENDPOINT_ARG[@]}" s3 cp "${DUMP}" "s3://${BACKUP_S3_BUCKET}/${KEY}" --no-guess-mime-type \
      && aws "${ENDPOINT_ARG[@]}" s3 cp "${DUMP}.sha256" "s3://${BACKUP_S3_BUCKET}/${KEY}.sha256" --no-guess-mime-type \
      && log "OK offloaded to object storage" \
      || log "WARN object-store offload failed (non-fatal, local copy retained)"
  else
    log "WARN BACKUP_S3_BUCKET set but 'aws' CLI missing — local copy only"
  fi
else
  log "skip object-store offload (BACKUP_S3_BUCKET not set) — local copy only"
fi

# --- 4. Retention: prune local dumps + sidecars older than N days ----------------
if [ "${RETENTION_DAYS}" -gt 0 ] 2>/dev/null; then
  PRUNED="$(find "${DEST}" -maxdepth 1 -type f \( -name "*.dump" -o -name "*.dump.sha256" -o -name "qdrant-*.json" \) -mtime "+${RETENTION_DAYS}" -print -delete | wc -l | tr -d ' ')"
  log "retention: pruned ${PRUNED} file(s) older than ${RETENTION_DAYS}d"
fi

log "DONE ${DUMP}"
