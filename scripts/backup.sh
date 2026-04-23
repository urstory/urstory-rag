#!/usr/bin/env bash
# UrstoryRAG backup script.
#
# Backs up PostgreSQL (shared DBs) and Elasticsearch indices to a local
# backup directory. Designed to run via cron on the Docker host.
#
# Usage:
#   ./scripts/backup.sh                           # all backups
#   ./scripts/backup.sh --postgres-only           # only PostgreSQL
#   ./scripts/backup.sh --elasticsearch-only      # only Elasticsearch
#   BACKUP_DIR=/mnt/backup ./scripts/backup.sh    # custom backup dir
#
# Retention: daily backups for 7 days, weekly for 30 days (see cleanup_backups).

set -euo pipefail

# --- Config -----------------------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

BACKUP_DIR="${BACKUP_DIR:-${PROJECT_ROOT}/backups}"
DAILY_RETENTION_DAYS="${BACKUP_DAILY_RETENTION:-7}"
WEEKLY_RETENTION_DAYS="${BACKUP_WEEKLY_RETENTION:-30}"

POSTGRES_CONTAINER="${POSTGRES_CONTAINER:-shared-postgres}"
POSTGRES_USER="${POSTGRES_USER:-admin}"
POSTGRES_DATABASES="${POSTGRES_DATABASES:-shared langfuse}"

ES_CONTAINER="${ES_CONTAINER:-shared-elasticsearch}"
ES_HOST="${ES_HOST:-http://localhost:9200}"
ES_REPO_NAME="${ES_REPO_NAME:-urstory_rag_snapshots}"
# Docker-internal path (mounted as a volume in docker-compose override).
ES_REPO_PATH="${ES_REPO_PATH:-/usr/share/elasticsearch/snapshots}"

TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
DATE_TAG="$(date +%Y%m%d)"

MODE="all"
for arg in "$@"; do
  case "$arg" in
    --postgres-only)       MODE="postgres" ;;
    --elasticsearch-only)  MODE="elasticsearch" ;;
    -h|--help)
      sed -n '1,20p' "$0"
      exit 0
      ;;
    *)
      echo "unknown argument: $arg" >&2
      exit 2
      ;;
  esac
done

# --- Helpers ----------------------------------------------------------------

log() { echo "[$(date +%H:%M:%S)] $*"; }
err() { echo "[$(date +%H:%M:%S)] ERROR: $*" >&2; }

require() {
  if ! command -v "$1" >/dev/null 2>&1; then
    err "required command not found: $1"
    exit 1
  fi
}

docker_running() {
  docker inspect -f '{{.State.Running}}' "$1" 2>/dev/null | grep -q true
}

# --- PostgreSQL -------------------------------------------------------------

backup_postgres() {
  log "PostgreSQL backup (container=${POSTGRES_CONTAINER})"
  if ! docker_running "${POSTGRES_CONTAINER}"; then
    err "container '${POSTGRES_CONTAINER}' is not running"
    return 1
  fi

  local out_dir="${BACKUP_DIR}/postgres/${DATE_TAG}"
  mkdir -p "${out_dir}"

  for db in ${POSTGRES_DATABASES}; do
    local out_file="${out_dir}/${db}_${TIMESTAMP}.sql.gz"
    log "  dumping ${db} -> ${out_file}"
    docker exec -e PGPASSWORD="${POSTGRES_PASSWORD:-}" "${POSTGRES_CONTAINER}" \
      pg_dump -U "${POSTGRES_USER}" \
        --format=plain \
        --no-owner --no-privileges \
        --encoding=UTF8 \
        "${db}" \
      | gzip -c > "${out_file}"
    log "  done: $(du -h "${out_file}" | cut -f1)"
  done
}

# --- Elasticsearch ----------------------------------------------------------

register_es_repo() {
  # Register snapshot repository if it does not exist.
  local status
  status="$(curl -s -o /dev/null -w '%{http_code}' "${ES_HOST}/_snapshot/${ES_REPO_NAME}")"
  if [ "${status}" = "200" ]; then
    return 0
  fi
  log "  registering snapshot repository ${ES_REPO_NAME}"
  curl -s -X PUT "${ES_HOST}/_snapshot/${ES_REPO_NAME}" \
    -H 'Content-Type: application/json' \
    -d "{\"type\": \"fs\", \"settings\": {\"location\": \"${ES_REPO_PATH}\", \"compress\": true}}" \
    | python3 -m json.tool >/dev/null || true
}

backup_elasticsearch() {
  log "Elasticsearch backup (host=${ES_HOST})"
  if ! docker_running "${ES_CONTAINER}"; then
    err "container '${ES_CONTAINER}' is not running"
    return 1
  fi

  # path.repo must be configured in elasticsearch.yml / ES_JAVA_OPTS for
  # snapshots to work. If the repo is not accessible, print a helpful hint.
  if ! register_es_repo; then
    err "failed to register snapshot repository; check that path.repo='${ES_REPO_PATH}' is set in Elasticsearch"
    return 1
  fi

  local snapshot_name="snapshot_${TIMESTAMP}"
  log "  creating snapshot ${snapshot_name}"
  local resp
  resp="$(curl -s -X PUT "${ES_HOST}/_snapshot/${ES_REPO_NAME}/${snapshot_name}?wait_for_completion=true" \
    -H 'Content-Type: application/json' \
    -d '{"indices": "*", "ignore_unavailable": true, "include_global_state": false}')"
  if echo "${resp}" | grep -q '"state":"SUCCESS"'; then
    log "  snapshot SUCCESS"
  else
    err "snapshot failed: ${resp}"
    return 1
  fi
}

# --- Retention --------------------------------------------------------------

cleanup_backups() {
  # Delete PostgreSQL dumps older than retention windows.
  if [ -d "${BACKUP_DIR}/postgres" ]; then
    log "Cleaning up old PostgreSQL backups (>${DAILY_RETENTION_DAYS}d daily, >${WEEKLY_RETENTION_DAYS}d weekly)"
    find "${BACKUP_DIR}/postgres" -type d -mtime +"${DAILY_RETENTION_DAYS}" -print | while read -r d; do
      # Keep Sunday directories up to WEEKLY_RETENTION_DAYS.
      local age_days
      age_days="$(( ($(date +%s) - $(stat -f %m "$d" 2>/dev/null || stat -c %Y "$d")) / 86400 ))"
      local name dow
      name="$(basename "$d")"
      if [[ "${name}" =~ ^[0-9]{8}$ ]]; then
        # macOS + GNU date compatibility
        dow="$(date -j -f '%Y%m%d' "${name}" +%u 2>/dev/null || date -d "${name}" +%u)"
        if [ "${dow}" = "7" ] && [ "${age_days}" -le "${WEEKLY_RETENTION_DAYS}" ]; then
          continue
        fi
      fi
      log "  removing ${d}"
      rm -rf "${d}"
    done
  fi

  # Elasticsearch snapshots are managed by Curator or SLM in production; this
  # script leaves snapshot retention to the ES-side policy by default.
}

# --- Main -------------------------------------------------------------------

require docker
require curl
require gzip

mkdir -p "${BACKUP_DIR}"

log "Starting backup (mode=${MODE}, dir=${BACKUP_DIR})"

case "${MODE}" in
  postgres)      backup_postgres ;;
  elasticsearch) backup_elasticsearch ;;
  all)
    backup_postgres || err "postgres backup failed"
    backup_elasticsearch || err "elasticsearch backup failed"
    ;;
esac

cleanup_backups || true

log "Backup completed"
