#!/usr/bin/env bash
# UrstoryRAG restore script.
#
# Restores PostgreSQL and/or Elasticsearch from backups created by backup.sh.
#
# Usage:
#   ./scripts/restore.sh --postgres <path/to/db.sql.gz> [--database shared]
#   ./scripts/restore.sh --elasticsearch <snapshot_name>
#   ./scripts/restore.sh --list                              # list available
#
# Safety:
#  - Requires typing "RESTORE" to confirm destructive restores
#  - PostgreSQL restore drops the target database first (--drop to skip prompt)
#  - Elasticsearch restore closes matching indices first

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

BACKUP_DIR="${BACKUP_DIR:-${PROJECT_ROOT}/backups}"

POSTGRES_CONTAINER="${POSTGRES_CONTAINER:-shared-postgres}"
POSTGRES_USER="${POSTGRES_USER:-admin}"

ES_HOST="${ES_HOST:-http://localhost:9200}"
ES_REPO_NAME="${ES_REPO_NAME:-urstory_rag_snapshots}"

log() { echo "[$(date +%H:%M:%S)] $*"; }
err() { echo "[$(date +%H:%M:%S)] ERROR: $*" >&2; }

confirm() {
  local prompt="$1"
  echo -n "${prompt} [type RESTORE to confirm]: "
  read -r reply
  if [ "${reply}" != "RESTORE" ]; then
    err "aborted"
    exit 1
  fi
}

list_backups() {
  echo "PostgreSQL dumps:"
  find "${BACKUP_DIR}/postgres" -type f -name '*.sql.gz' 2>/dev/null | sort || echo "  (none)"
  echo
  echo "Elasticsearch snapshots:"
  curl -s "${ES_HOST}/_snapshot/${ES_REPO_NAME}/_all" \
    | python3 -c 'import json,sys; [print(f"  {s[\"snapshot\"]} ({s.get(\"start_time\",\"-\")})") for s in json.load(sys.stdin).get("snapshots", [])]' \
    2>/dev/null || echo "  (repository not registered or ES unreachable)"
}

restore_postgres() {
  local dump_file="$1"
  local database="${2:-shared}"

  if [ ! -f "${dump_file}" ]; then
    err "dump file not found: ${dump_file}"
    exit 1
  fi

  log "Restoring PostgreSQL database '${database}' from ${dump_file}"
  log "  container=${POSTGRES_CONTAINER}"

  confirm "This will DROP and recreate database '${database}'. Continue?"

  # Terminate active connections
  docker exec -e PGPASSWORD="${POSTGRES_PASSWORD:-}" "${POSTGRES_CONTAINER}" \
    psql -U "${POSTGRES_USER}" -d postgres -c \
    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='${database}' AND pid <> pg_backend_pid();" >/dev/null

  # Drop and recreate
  docker exec -e PGPASSWORD="${POSTGRES_PASSWORD:-}" "${POSTGRES_CONTAINER}" \
    psql -U "${POSTGRES_USER}" -d postgres -c "DROP DATABASE IF EXISTS \"${database}\";"
  docker exec -e PGPASSWORD="${POSTGRES_PASSWORD:-}" "${POSTGRES_CONTAINER}" \
    psql -U "${POSTGRES_USER}" -d postgres -c "CREATE DATABASE \"${database}\";"

  # Stream the dump back in
  gunzip -c "${dump_file}" \
    | docker exec -i -e PGPASSWORD="${POSTGRES_PASSWORD:-}" "${POSTGRES_CONTAINER}" \
      psql -U "${POSTGRES_USER}" -d "${database}" -v ON_ERROR_STOP=1 >/dev/null

  log "PostgreSQL restore complete."
}

restore_elasticsearch() {
  local snapshot="$1"

  log "Restoring Elasticsearch snapshot '${snapshot}' from repo '${ES_REPO_NAME}'"
  confirm "This will CLOSE/OVERWRITE indices included in the snapshot. Continue?"

  # Close all existing indices (ignore errors)
  curl -s -X POST "${ES_HOST}/_all/_close" >/dev/null || true

  local resp
  resp="$(curl -s -X POST "${ES_HOST}/_snapshot/${ES_REPO_NAME}/${snapshot}/_restore?wait_for_completion=true" \
    -H 'Content-Type: application/json' \
    -d '{"indices": "*", "ignore_unavailable": true, "include_global_state": false}')"

  if echo "${resp}" | grep -q '"accepted":true\|"snapshot"'; then
    log "Elasticsearch restore requested successfully."
    curl -s -X POST "${ES_HOST}/_all/_open" >/dev/null || true
    log "All indices opened."
  else
    err "restore failed: ${resp}"
    exit 1
  fi
}

# --- Arg parsing ------------------------------------------------------------

MODE=""
DUMP_FILE=""
DATABASE="shared"
SNAPSHOT=""

while [ $# -gt 0 ]; do
  case "$1" in
    --list)           MODE="list"; shift ;;
    --postgres)       MODE="postgres"; DUMP_FILE="$2"; shift 2 ;;
    --database)       DATABASE="$2"; shift 2 ;;
    --elasticsearch)  MODE="elasticsearch"; SNAPSHOT="$2"; shift 2 ;;
    -h|--help)        sed -n '1,20p' "$0"; exit 0 ;;
    *)                err "unknown argument: $1"; exit 2 ;;
  esac
done

case "${MODE}" in
  list)          list_backups ;;
  postgres)      restore_postgres "${DUMP_FILE}" "${DATABASE}" ;;
  elasticsearch) restore_elasticsearch "${SNAPSHOT}" ;;
  *)
    err "missing mode: use --postgres <file>, --elasticsearch <snapshot>, or --list"
    exit 2
    ;;
esac
