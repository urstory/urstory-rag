#!/bin/bash
# UrstoryRAG 개발 서버 시작 스크립트
# 사용법: ./scripts/start.sh [--all | --backend | --frontend | --infra]
#   인자 없이 실행하면 전체(infra + backend + frontend) 시작

set -e
cd "$(dirname "$0")/.."
ROOT_DIR=$(pwd)

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${GREEN}[START]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
err()  { echo -e "${RED}[ERROR]${NC} $1"; }

# --- 인프라 (ES + Redis, PostgreSQL은 공용 컨테이너 사용) ---
start_infra() {
    log "인프라 시작 (Elasticsearch + Redis)..."

    # shared-postgres가 이미 실행 중이면 docker compose에서 postgres 제외
    if docker ps --format '{{.Names}}' | grep -q shared-postgres; then
        log "shared-postgres 이미 실행 중 — ES + Redis만 시작"
        cd infra && docker compose up -d elasticsearch redis
    else
        log "전체 인프라 시작 (PostgreSQL + ES + Redis)"
        cd infra && docker compose up -d
    fi
    cd "$ROOT_DIR"

    # ES 헬스 대기
    log "Elasticsearch 헬스체크 대기..."
    i=0
    while [ $i -lt 30 ]; do
        es_status=$(docker inspect shared-elasticsearch --format '{{.State.Health.Status}}' 2>/dev/null || echo "not found")
        [ "$es_status" = "healthy" ] && break
        sleep 5
        i=$((i+1))
    done

    if [ "$es_status" = "healthy" ]; then
        log "Elasticsearch ready"
    else
        warn "Elasticsearch 헬스체크 타임아웃 (계속 진행)"
    fi

    # Redis 헬스 대기
    i=0
    while [ $i -lt 10 ]; do
        redis_status=$(docker inspect shared-redis --format '{{.State.Health.Status}}' 2>/dev/null || echo "not found")
        [ "$redis_status" = "healthy" ] && break
        sleep 2
        i=$((i+1))
    done
    log "Redis ready"
}

# --- 백엔드 ---
start_backend() {
    if lsof -ti :8000 >/dev/null 2>&1; then
        warn "백엔드가 이미 실행 중 (port 8000)"
        return 0
    fi

    log "DB 마이그레이션 실행..."
    cd backend && source .venv/bin/activate && alembic upgrade head 2>&1 | tail -1
    cd "$ROOT_DIR"

    log "백엔드 시작 (port 8000)..."
    mkdir -p logs
    cd backend && source .venv/bin/activate && \
        nohup uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 > ../logs/backend.log 2>&1 &
    echo $! > "$ROOT_DIR/.backend.pid"
    cd "$ROOT_DIR"

    # 기동 대기
    i=0
    while [ $i -lt 20 ]; do
        if curl -s http://localhost:8000/api/health/live >/dev/null 2>&1; then
            log "백엔드 ready — http://localhost:8000"
            log "Swagger UI — http://localhost:8000/docs"
            return 0
        fi
        sleep 2
        i=$((i+1))
    done
    warn "백엔드 기동 대기 타임아웃 — 로그 확인: tail -f logs/backend.log"
}

# --- 프론트엔드 ---
start_frontend() {
    if lsof -ti :3500 >/dev/null 2>&1; then
        warn "프론트엔드가 이미 실행 중 (port 3500)"
        return 0
    fi

    log "프론트엔드 시작 (port 3500)..."
    mkdir -p logs
    cd frontend && \
        nohup pnpm dev --port 3500 > ../logs/frontend.log 2>&1 &
    echo $! > "$ROOT_DIR/.frontend.pid"
    cd "$ROOT_DIR"

    sleep 3
    log "프론트엔드 ready — http://localhost:3500"
}

# --- 상태 출력 ---
print_status() {
    echo ""
    echo "======================================"
    echo " UrstoryRAG 서비스 상태"
    echo "======================================"
    for svc in shared-postgres shared-elasticsearch shared-redis; do
        s=$(docker inspect "$svc" --format '{{.State.Health.Status}}' 2>/dev/null || echo "stopped")
        printf "  %-24s %s\n" "$svc" "$s"
    done
    for port_name in "8000:백엔드" "3500:프론트엔드"; do
        port=${port_name%%:*}
        name=${port_name##*:}
        if lsof -ti :$port >/dev/null 2>&1; then
            printf "  %-24s %s\n" "$name (port $port)" "running"
        else
            printf "  %-24s %s\n" "$name (port $port)" "stopped"
        fi
    done
    echo "======================================"
    echo ""
    echo "  Swagger UI   http://localhost:8000/docs"
    echo "  프론트엔드   http://localhost:3500"
    echo "  헬스체크     http://localhost:8000/api/health"
    echo ""
    echo "  종료: ./scripts/stop.sh"
    echo "======================================"
}

# --- 메인 ---
case "${1:-all}" in
    --infra)    start_infra ;;
    --backend)  start_backend ;;
    --frontend) start_frontend ;;
    --all|all)
        start_infra
        start_backend
        start_frontend
        print_status
        ;;
    *)
        echo "사용법: $0 [--all | --infra | --backend | --frontend]"
        exit 1
        ;;
esac
