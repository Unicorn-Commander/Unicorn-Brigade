# Unicorn Brigade — Backup & Disaster Recovery

Closes the last open reliability blocker from the 2026-07-16 enterprise-readiness
audit (backup/DR was "docs-only"). The primary stateful surface — the PostgreSQL
database holding orgs, agents, conversations, the `usage_events` billing ledger,
`workflow_executions`/`ralph_executions` (durable BR-4 state), `scheduled_runs`,
and `api_keys` — is now backed by an automated, integrity-checked, restore-proven
dump. Scripts live in `scripts/` and run on the host against the DB container.

## What is backed up
| Surface | Mechanism | Status |
|---|---|---|
| **PostgreSQL (primary)** | `pg_dump -Fc` custom format, sha256-sidecar'd, integrity-gated | **automated (this)** |
| Qdrant vectors (mem0) | snapshot API, when `QDRANT_URL` set | optional, off by default |
| FalkorDB / Zep KG | (see follow-ups) | not yet automated |
| Uploaded files / workspace | filesystem | not yet automated |

Postgres is the surface whose loss is unrecoverable; the memory stores are
rebuildable from it + re-embedding. This DR covers Postgres end-to-end and leaves
the rebuildable stores as documented follow-ups.

## RPO / RTO
- **RPO** (max data loss): the backup interval — **24h** with the default daily cron;
  tighten by running the cron more often (dumps are cheap: ~1.6 MB, <2 s on dogfood).
- **RTO** (time to restore): minutes — `restore.sh` into a fresh Postgres, then point
  the app's `DATABASE_URL`/`MIGRATION_DATABASE_URL` at it. Proven round-trip below.

## Scripts
- `scripts/backup.sh` — dump + integrity check (`pg_restore --list`) + sha256 sidecar
  + retention prune + optional Qdrant snapshot + optional S3/Garage offload. READ-ONLY
  against the app DB (safe on a live system). Env: `PG_CONTAINER`, `PG_USER`, `PG_DB`,
  `BACKUP_DIR`, `RETENTION_DAYS`, optional `QDRANT_URL`, `BACKUP_S3_BUCKET`,
  `BACKUP_S3_ENDPOINT`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`.
- `scripts/restore.sh` — guard-railed restore. Requires `RESTORE_CONFIRM=yes`; a
  target whose name contains `prod`/`live` ALSO requires `RESTORE_ALLOW_PROD=yes`.
  Verifies dump integrity + sidecar before touching the target.
- `scripts/run_backup_proof.sh` — spins a throwaway `postgres:16`, seeds realistic
  org-scoped data, backs up, DROPs everything, restores, and asserts byte-for-byte
  recovery + that the safety guards refuse unconfirmed/prod restores. Exit 0 pass,
  3 = Docker unavailable. Run it after any change to the backup scripts.

## Deployed schedule (host-local)
Operational copies live at `/home/muut/brigade-backups/bin/` on each host; a daily
cron runs them. Env differs per ring:

- **Dogfood (bigboy / `ssh magicunicorn`)**: `PG_CONTAINER=unicorn-postgresql`,
  `PG_USER=unicorn`, `PG_DB=brigade_db`.
- **Prod (commander / `ssh commander`)**: `PG_CONTAINER=unicorn-brigade-prod-postgres`,
  `PG_USER=brigade`, `PG_DB=brigade_prod`.

Backups land in `/home/muut/brigade-backups/<db>/` with 14-day local retention.

## Restore / DR drill
```bash
# 1. pick a dump
ls -lt /home/muut/brigade-backups/brigade_db/*.dump

# 2. DRILL: restore into a throwaway to verify (never touches prod)
docker run --rm -d --name brigade-dr-drill -e POSTGRES_PASSWORD=x postgres:16
RESTORE_CONFIRM=yes ./restore.sh <dump> --into brigade-dr-drill postgres brigade_db
docker exec brigade-dr-drill psql -U postgres -d brigade_db -c "SELECT count(*) FROM organizations;"
docker rm -f brigade-dr-drill

# 3. REAL recovery (only in an actual outage): restore into the live/replacement PG,
#    then point DATABASE_URL + MIGRATION_DATABASE_URL at it and recreate the app.
#    Prod target requires BOTH env flags (intentional friction):
RESTORE_CONFIRM=yes RESTORE_ALLOW_PROD=yes ./restore.sh <dump> \
  --into unicorn-brigade-prod-postgres brigade brigade_prod
```

## Proven
`run_backup_proof.sh` on bigboy: backup → `DROP SCHEMA public CASCADE` → restore →
orgs/agents/usage-ledger row counts + content hash all identical; unconfirmed and
prod-named restores correctly refused. Real dogfood `brigade_db` dump (1.6 MB, 220
archive entries) verified restorable via `pg_restore --list`.

## Follow-ups to reach FULL DR (need Aaron / infra)
1. **Offsite offload** — set `BACKUP_S3_BUCKET`/`BACKUP_S3_ENDPOINT` + creds to a
   **Garage** bucket (memory: Garage, not MinIO). Until then backups are host-local
   and would be lost with the host — good against logical corruption / bad migration /
   accidental drop, but not against host loss. This is the one step to true DR.
2. **Restore-drill cron** — a weekly job that restores the latest dump into a throwaway
   and alerts on mismatch (an untested backup is not a backup).
3. **Rebuildable stores** — automate Qdrant (`QDRANT_URL` already wired) + FalkorDB/Zep
   snapshots; document the re-embed path so they can be regenerated from Postgres.
