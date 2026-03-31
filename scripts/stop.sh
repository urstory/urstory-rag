#!/bin/bash
# UrstoryRAG 개발 서버 종료 스크립트
# 사용법: ./scripts/stop.sh [--all | --backend | --frontend | --infra]
#   인자 없이 실행하면 전체(backend + frontend) 종료 (인프라는 유지)
#   --all: 인프라(ES, Redis)까지 종료 (shared-postgres는 공용이므로 유지)

set -e
cd "$(dirname "$0")/.."
ROOT_DIR=$(pwd)

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${GREEN}[STOP]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }

# --- 백엔드 종료 ---
stop_backend() {
    local found=0

    if [ -f "$ROOT_DIR/.backend.pid" ]; then
        pid=$(cat "$ROOT_DIR/.backend.pid")
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid"
            log "백엔드 종료 (PID: $pid)"
            found=1
        fi
        rm -f "$ROOT_DIR/.backend.pid"
    fi

    if [ $found -eq 0 ]; then
        pids=$(lsof -ti :8000 2>/dev/null || true)
        if [ -n "$pids" ]; then
            echo "$pids" | xargs kill 2>/dev/null || true
            log "포트 8000 프로세스 종료 (PID: $pids)"
        else
            warn "실행 중인 백엔드 없음"
        fi
    fi
}

# --- 프론트엔드 종료 ---
stop_frontend() {
    local found=0

    if [ -f "$ROOT_DIR/.frontend.pid" ]; then
        pid=$(cat "$ROOT_DIR/.frontend.pid")
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid"
            log "프론트엔드 종료 (PID: $pid)"
            found=1
        fi
        rm -f "$ROOT_DIR/.frontend.pid"
    fi

    if [ $found -eq 0 ]; then
        pids=$(lsof -ti :3500 2>/dev/null || true)
        if [ -n "$pids" ]; then
            echo "$pids" | xargs kill 2>/dev/null || true
            log "포트 3500 프로세스 종료 (PID: $pids)"
        else
            warn "실행 중인 프론트엔드 없음"
        fi
    fi
}

# --- 인프라 종료 (shared-postgres는 공용이므로 유지) ---
stop_infra() {
    log "인프라 종료 (ES + Redis)..."
    log "shared-postgres는 공용 컨테이너이므로 유지합니다"
    docker stop shared-elasticsearch shared-redis 2>/dev/null || true
    log "인프라 종료 완료"
}

# --- 메인 ---
case "${1:-app}" in
    --backend)  stop_backend ;;
    --frontend) stop_frontend ;;
    --infra)    stop_infra ;;
    --all)
        stop_backend
        stop_frontend
        stop_infra
        ;;
    --app|app)
        stop_backend
        stop_frontend
        log "인프라(ES, Redis, PostgreSQL)는 유지됩니다. 종료하려면: ./scripts/stop.sh --all"
        ;;
    *)
        echo "사용법: $0 [--app | --all | --backend | --frontend | --infra]"
        echo ""
        echo "  (기본)    앱만 종료 (백엔드 + 프론트엔드)"
        echo "  --all     앱 + 인프라(ES, Redis) 종료"
        echo "  --backend 백엔드만 종료"
        echo "  --frontend 프론트엔드만 종료"
        echo "  --infra   인프라(ES, Redis)만 종료"
        echo ""
        echo "  * shared-postgres는 공용이므로 어떤 옵션에서도 종료하지 않습니다."
        exit 1
        ;;
esac
