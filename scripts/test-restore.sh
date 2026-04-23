#!/usr/bin/env bash
# UrstoryRAG restore verification script.
#
# Picks the newest PostgreSQL dump and restores it into a throwaway database
# `restore_test_<timestamp>` inside the same container, then verifies that
# at least one expected table exists and row counts are non-zero.
#
# Usage:
#   ./scripts/test-restore.sh                # auto-pick latest dump
#   ./scripts/test-restore.sh path/to/dump.sql.gz
#
# Intended to be run monthly (e.g. by cron) to catch silent backup rot.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
BACKUP_DIR="${BACKUP_DIR:-${PROJECT_ROOT}/backups}"

POSTGRES_CONTAINER="${POSTGRES_CONTAINER:-shared-postgres}"
POSTGRES_USER="${POSTGRES_USER:-admin}"

# Tables that must exist post-restore in the UrstoryRAG DB.
EXPECTED_TABLES="${EXPECTED_TABLES:-documents users}"

log() { echo "[$(date +%H:%M:%S)] $*"; }
err() { echo "[$(date +%H:%M:%S)] ERROR: $*" >&2; }

dump_file="${1:-}"
if [ -z "${dump_file}" ]; then
  dump_file="$(find "${BACKUP_DIR}/postgres" -type f -name 'shared_*.sql.gz' 2>/dev/null | sort | tail -1)"
  if [ -z "${dump_file}" ]; then
    err "no PostgreSQL dumps found under ${BACKUP_DIR}/postgres"
    exit 1
  fi
fi

if [ ! -f "${dump_file}" ]; then
  err "dump file does not exist: ${dump_file}"
  exit 1
fi

log "Using dump: ${dump_file}"
test_db="restore_test_$(date +%s)"

cleanup() {
  log "Cleaning up test database ${test_db}"
  docker exec -e PGPASSWORD="${POSTGRES_PASSWORD:-}" "${POSTGRES_CONTAINER}" \
    psql -U "${POSTGRES_USER}" -d postgres -c "DROP DATABASE IF EXISTS \"${test_db}\";" >/dev/null 2>&1 || true
}
trap cleanup EXIT

log "Creating test database ${test_db}"
docker exec -e PGPASSWORD="${POSTGRES_PASSWORD:-}" "${POSTGRES_CONTAINER}" \
  psql -U "${POSTGRES_USER}" -d postgres -c "CREATE DATABASE \"${test_db}\";"

log "Streaming dump into ${test_db}"
gunzip -c "${dump_file}" \
  | docker exec -i -e PGPASSWORD="${POSTGRES_PASSWORD:-}" "${POSTGRES_CONTAINER}" \
    psql -U "${POSTGRES_USER}" -d "${test_db}" -v ON_ERROR_STOP=1 >/dev/null

log "Verifying restored schema"
failed=0
for tbl in ${EXPECTED_TABLES}; do
  count="$(docker exec -e PGPASSWORD="${POSTGRES_PASSWORD:-}" "${POSTGRES_CONTAINER}" \
    psql -U "${POSTGRES_USER}" -d "${test_db}" -tAc "SELECT COUNT(*) FROM ${tbl};" 2>/dev/null || echo "MISSING")"
  if [ "${count}" = "MISSING" ]; then
    err "table '${tbl}' missing after restore"
    failed=1
  else
    log "  ${tbl}: ${count} rows"
  fi
done

if [ "${failed}" -ne 0 ]; then
  err "restore verification FAILED"
  exit 1
fi

log "Restore verification PASSED"
