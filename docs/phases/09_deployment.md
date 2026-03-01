# Phase 9: 배포 및 운영 상세 개발 계획

## 개요

| 항목 | 내용 |
|------|------|
| Phase | 9 |
| 담당 | 인프라 엔지니어 |
| 의존성 | Phase 8 |
| 참조 문서 | `docs/architecture/10_deployment.md` |

## 사전 조건

- Phase 8 완료 (모든 테스트 통과)
- Ollama 호스트 실행 중 (bge-m3, qwen2.5:7b 모델 로드)

## 상세 구현 단계

### Step 9.1: docker-compose.yml 최종 정리

#### 수정 파일
- `docker-compose.yml`

#### 구현 내용

전체 앱 계층 서비스 (Langfuse v3는 Web+Worker+Redis+MinIO 4개 서비스 구성):
```yaml
services:
  rag-api:
    build: ./backend
    container_name: rag-api
    ports: ["8000:8000"]
    environment:
      DATABASE_URL: postgresql+asyncpg://admin:${POSTGRES_PASSWORD}@shared-postgres:5432/shared
      ELASTICSEARCH_URL: http://shared-elasticsearch:9200
      OLLAMA_URL: ${OLLAMA_URL:-http://host.docker.internal:11434}
      REDIS_URL: redis://rag-redis:6379
      LANGFUSE_HOST: http://rag-langfuse:3000
      LANGFUSE_PUBLIC_KEY: ${LANGFUSE_PUBLIC_KEY}
      LANGFUSE_SECRET_KEY: ${LANGFUSE_SECRET_KEY}
      OPENAI_API_KEY: ${OPENAI_API_KEY:-}
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY:-}
    volumes: [upload_data:/app/uploads]
    depends_on: [rag-redis]
    networks: [default, shared-infra]
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')"]
      interval: 30s
      timeout: 10s
      retries: 3

  rag-worker:
    build: ./backend
    container_name: rag-worker
    command: celery -A app.worker.celery_app worker --loglevel=info --concurrency=2
    environment: # rag-api와 동일
    depends_on: [rag-redis]
    networks: [default, shared-infra]
    restart: unless-stopped

  rag-frontend:
    build: ./frontend
    container_name: rag-frontend
    ports: ["3000:3000"]
    environment:
      NEXT_PUBLIC_API_URL: http://localhost:8000
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "wget", "--spider", "-q", "http://localhost:3000"]
      interval: 30s
      timeout: 10s
      retries: 3

  rag-redis:
    image: redis:7-alpine
    container_name: rag-redis
    volumes: [redis_data:/data]
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s

  # === Langfuse v3 (Web + Worker + ClickHouse + Redis + MinIO) ===
  langfuse-web:
    image: langfuse/langfuse:3
    container_name: rag-langfuse-web
    ports: ["3100:3000"]
    environment: &langfuse-env
      DATABASE_URL: postgresql://admin:${POSTGRES_PASSWORD}@shared-postgres:5432/shared
      NEXTAUTH_URL: http://localhost:3100
      NEXTAUTH_SECRET: ${NEXTAUTH_SECRET}
      SALT: ${SALT}
      ENCRYPTION_KEY: ${LANGFUSE_ENCRYPTION_KEY}
      CLICKHOUSE_URL: http://rag-clickhouse:8123
      CLICKHOUSE_MIGRATION_URL: clickhouse://rag-clickhouse:9000
      CLICKHOUSE_USER: ${CLICKHOUSE_USER:-default}
      CLICKHOUSE_PASSWORD: ${CLICKHOUSE_PASSWORD:-}
      REDIS_HOST: langfuse-redis
      REDIS_PORT: 6379
      REDIS_AUTH: ${LANGFUSE_REDIS_AUTH:-langfuseredis}
      LANGFUSE_S3_EVENT_UPLOAD_BUCKET: langfuse
      LANGFUSE_S3_EVENT_UPLOAD_REGION: auto
      LANGFUSE_S3_EVENT_UPLOAD_ACCESS_KEY_ID: ${MINIO_ROOT_USER:-minioadmin}
      LANGFUSE_S3_EVENT_UPLOAD_SECRET_ACCESS_KEY: ${MINIO_ROOT_PASSWORD:-minioadmin}
      LANGFUSE_S3_EVENT_UPLOAD_ENDPOINT: http://langfuse-minio:9000
      LANGFUSE_S3_EVENT_UPLOAD_FORCE_PATH_STYLE: "true"
    depends_on:
      rag-clickhouse: { condition: service_healthy }
      langfuse-redis: { condition: service_healthy }
      langfuse-minio: { condition: service_healthy }
    networks: [default, shared-infra]
    restart: unless-stopped

  langfuse-worker:
    image: langfuse/langfuse-worker:3
    container_name: rag-langfuse-worker
    environment:
      <<: *langfuse-env
    depends_on:
      rag-clickhouse: { condition: service_healthy }
      langfuse-redis: { condition: service_healthy }
      langfuse-minio: { condition: service_healthy }
    networks: [default, shared-infra]
    restart: unless-stopped

  rag-clickhouse:
    image: clickhouse/clickhouse-server:latest
    container_name: rag-clickhouse
    environment:
      CLICKHOUSE_USER: ${CLICKHOUSE_USER:-default}
      CLICKHOUSE_PASSWORD: ${CLICKHOUSE_PASSWORD:-}
    volumes: [clickhouse_data:/var/lib/clickhouse]
    healthcheck:
      test: ["CMD", "wget", "--no-verbose", "--tries=1", "--spider", "http://localhost:8123/ping"]
      interval: 5s
      timeout: 5s
      retries: 10
    restart: unless-stopped

  langfuse-redis:
    image: redis:7-alpine
    container_name: langfuse-redis
    command: redis-server --requirepass ${LANGFUSE_REDIS_AUTH:-langfuseredis}
    volumes: [langfuse_redis_data:/data]
    healthcheck:
      test: ["CMD", "redis-cli", "-a", "${LANGFUSE_REDIS_AUTH:-langfuseredis}", "ping"]
      interval: 5s
      timeout: 5s
      retries: 10
    restart: unless-stopped

  langfuse-minio:
    image: minio/minio:latest
    container_name: langfuse-minio
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: ${MINIO_ROOT_USER:-minioadmin}
      MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD:-minioadmin}
    volumes: [langfuse_minio_data:/data]
    healthcheck:
      test: ["CMD", "mc", "ready", "local"]
      interval: 5s
      timeout: 5s
      retries: 10
    restart: unless-stopped
```

- 모든 서비스에 healthcheck 추가
- restart: unless-stopped

---

### Step 9.2: .env.example 최종 정리

#### 수정 파일
- `.env.example`

#### 구현 내용

```bash
# .env.example

# === 인프라 연결 ===
POSTGRES_PASSWORD=changeme_strong_password

# === Ollama ===
# Mac Studio (Docker 내부에서 접근): http://host.docker.internal:11434
# Mac Studio (로컬 개발): http://localhost:11434
# Linux GPU 서버: http://localhost:11434
OLLAMA_URL=http://host.docker.internal:11434

# === 외부 API ===
# RAGAS 평가용 (필수)
OPENAI_API_KEY=sk-...
# 답변 생성 대안 (선택)
ANTHROPIC_API_KEY=sk-ant-...

# === Langfuse v3 ===
# Langfuse UI(http://localhost:3100)에서 프로젝트 생성 후 키 발급
LANGFUSE_PUBLIC_KEY=pk-...
LANGFUSE_SECRET_KEY=sk-...
NEXTAUTH_SECRET=changeme_random_string
SALT=changeme_random_string
# 64자 hex 문자열 (필수, 암호화 키)
LANGFUSE_ENCRYPTION_KEY=0000000000000000000000000000000000000000000000000000000000000000

# === Langfuse ClickHouse ===
CLICKHOUSE_USER=default
CLICKHOUSE_PASSWORD=

# === Langfuse Redis ===
LANGFUSE_REDIS_AUTH=langfuseredis

# === Langfuse MinIO (S3 호환) ===
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=minioadmin
```

---

### Step 9.3: Makefile 최종 정리

#### 수정 파일
- `Makefile`

#### 구현 내용

```makefile
.PHONY: help infra-up infra-down app-up app-down up down \
        dev-backend dev-frontend migrate test test-integration \
        eval reindex-all ollama-setup health logs

help: ## 사용 가능한 커맨드 목록
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# === 인프라 ===
infra-up: ## 공유 인프라 기동 (PostgreSQL, Elasticsearch)
	cd infra && docker compose up -d
	@echo "Waiting for services to be healthy..."
	@sleep 5
	@docker exec shared-postgres pg_isready -U admin
	@curl -sf http://localhost:9200/_cluster/health > /dev/null && echo "Elasticsearch: OK"

infra-down: ## 공유 인프라 중지
	cd infra && docker compose down

# === 앱 ===
app-up: ## 앱 계층 기동 (API, Worker, Frontend, Langfuse)
	docker compose up -d
	@echo "Waiting for services..."
	@sleep 10

app-down: ## 앱 계층 중지
	docker compose down

# === 전체 ===
up: infra-up app-up ## 전체 시스템 기동
down: app-down infra-down ## 전체 시스템 중지

# === 개발 ===
dev-backend: ## 백엔드 로컬 개발 서버 (핫 리로드)
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

dev-frontend: ## 프론트엔드 로컬 개발 서버
	cd frontend && pnpm dev

# === DB ===
migrate: ## DB 마이그레이션 실행 (컨테이너 내부)
	docker compose run --rm rag-api alembic upgrade head

migrate-local: ## DB 마이그레이션 실행 (로컬 개발용)
	cd backend && alembic upgrade head

# === 테스트 ===
test: ## 백엔드 단위 테스트
	cd backend && pytest tests/unit/ --tb=short -q

test-integration: ## 백엔드 통합 테스트 (인프라 필요)
	cd backend && pytest tests/integration/ -v

test-e2e: ## 프론트엔드 E2E 테스트 (Playwright Docker)
	docker run --rm --network host \
		-v $$(pwd)/frontend/e2e:/work/e2e \
		-v $$(pwd)/frontend/playwright.config.ts:/work/playwright.config.ts \
		fullstackfamily-platform-playwright:latest \
		npx playwright test

test-all: test test-integration test-e2e ## 전체 테스트

# === 평가 ===
eval: ## RAGAS 평가 실행 (DATASET_ID 필요)
	cd backend && python -m app.services.evaluation.ragas --dataset-id $(DATASET_ID)

# === 운영 ===
reindex-all: ## 전체 문서 재인덱싱
	curl -X POST http://localhost:8000/api/system/reindex-all

ollama-setup: ## Ollama 필수 모델 다운로드
	ollama pull bge-m3
	ollama pull qwen2.5:7b
	@echo "Models ready:"
	@ollama list | grep -E "bge-m3|qwen2.5"

health: ## 전체 시스템 헬스체크
	@echo "=== Backend ==="
	@curl -sf http://localhost:8000/api/health | python3 -m json.tool || echo "FAILED"
	@echo "\n=== Frontend ==="
	@curl -sf http://localhost:3000 > /dev/null && echo "OK" || echo "FAILED"
	@echo "\n=== Langfuse ==="
	@curl -sf http://localhost:3100/api/health | python3 -m json.tool || echo "FAILED"
	@echo "\n=== Ollama ==="
	@curl -sf http://localhost:11434/api/tags > /dev/null && echo "OK" || echo "FAILED"
	@echo "\n=== PostgreSQL ==="
	@docker exec shared-postgres pg_isready -U admin || echo "FAILED"
	@echo "\n=== Elasticsearch ==="
	@curl -sf http://localhost:9200/_cluster/health | python3 -m json.tool || echo "FAILED"

# === 로그 ===
logs: ## 전체 로그 (follow)
	docker compose logs -f

logs-api: ## 백엔드 API 로그
	docker compose logs -f rag-api

logs-worker: ## Celery 워커 로그
	docker compose logs -f rag-worker
```

---

### Step 9.4: 배포 검증 스크립트

#### 생성 파일
- `scripts/deploy-verify.sh`

#### 구현 내용

```bash
#!/bin/bash
set -e

echo "=== UrstoryRAG 배포 검증 ==="

echo "[1/6] 환경 변수 확인..."
[ -f .env ] || { echo "ERROR: .env 파일 없음. cp .env.example .env 실행 후 설정하세요."; exit 1; }

echo "[2/6] Ollama 모델 확인..."
ollama list | grep -q "bge-m3" || { echo "ERROR: bge-m3 모델 없음. ollama pull bge-m3"; exit 1; }
ollama list | grep -q "qwen2.5" || { echo "ERROR: qwen2.5:7b 모델 없음. ollama pull qwen2.5:7b"; exit 1; }

echo "[3/6] 인프라 기동..."
make infra-up
sleep 10

echo "[4/6] 앱 기동..."
make app-up
sleep 15

echo "[5/6] DB 마이그레이션 (컨테이너 내부)..."
make migrate

echo "[6/6] 헬스체크..."
make health

echo ""
echo "=== 배포 완료 ==="
echo "- 관리자 UI: http://localhost:3000"
echo "- 백엔드 API: http://localhost:8000"
echo "- Langfuse: http://localhost:3100"
echo ""
echo "첫 실행 시 Langfuse(http://localhost:3100)에서 관리자 계정 생성 후"
echo "프로젝트를 만들고 API Key를 .env에 설정하세요."
```

---

### Step 9.5: Mac Studio 전용 설정 문서

#### 생성 파일
- `docs/mac-studio-setup.md`

#### 구현 내용

Mac Studio 환경 주의사항:
1. **Ollama는 호스트에서 직접 실행** — Docker 내 Ollama는 Metal GPU 미사용으로 5-6배 느림
2. **Docker에서 Ollama 접근** — `OLLAMA_URL=http://host.docker.internal:11434`
3. **로컬 개발 시** — `OLLAMA_URL=http://localhost:11434`
4. **Docker Named Volume 사용** — 바인드 마운트는 Linux 대비 3배 느림
5. **슬립 방지** — 서버로 사용 시 `caffeinate -s` 실행
6. **리랭커 MPS 가속** — `torch.backends.mps.is_available()` 자동 감지

---

### Step 9.6: Nori 인덱스 템플릿 자동 적용

#### 수정 파일
- `Makefile` (또는 `scripts/setup-es.sh`)

#### 구현 내용

인프라 최초 기동 시 Nori 인덱스 템플릿 자동 적용:
```bash
infra-up: ## 공유 인프라 기동
	cd infra && docker compose up -d
	@sleep 10
	@curl -X PUT "http://localhost:9200/_index_template/rag_template" \
		-H "Content-Type: application/json" \
		-d @infra/elasticsearch/nori-index-template.json \
		> /dev/null 2>&1 && echo "Nori template applied" || echo "Nori template already exists"
```

---

### Step 9.7: Langfuse v3 초기 설정 가이드

#### 구현 내용 (docs/mac-studio-setup.md에 포함)

> **참고**: Langfuse v3는 `langfuse-web` + `langfuse-worker` 2개 컨테이너로 구성됩니다.
> MinIO 버킷은 첫 기동 시 자동 생성됩니다.

1. `http://localhost:3100` 접속
2. 관리자 계정 생성 (이메일, 비밀번호)
3. 프로젝트 생성 (예: "UrstoryRAG")
4. Settings → API Keys → Create API Key
5. Public Key, Secret Key를 `.env`에 설정
6. `.env`의 `LANGFUSE_ENCRYPTION_KEY`를 안전한 64자 hex로 변경
7. `make app-down && make app-up` (환경 변수 반영)

---

### Step 9.8: 최종 통합 검증

#### 검증 순서

```bash
# 1. 클린 상태에서 시작
make down 2>/dev/null; true

# 2. 환경 변수 설정
cp .env.example .env
# .env 편집 (패스워드, API 키 등)

# 3. Ollama 모델 확인
make ollama-setup

# 4. 전체 기동
make up

# 5. DB 마이그레이션 (컨테이너 내부)
make migrate

# 6. 헬스체크
make health

# 7. 기능 검증
# 문서 업로드
curl -X POST http://localhost:8000/api/documents/upload \
  -F "file=@backend/tests/fixtures/sample.txt"

# 검색
curl -s -X POST http://localhost:8000/api/search \
  -H 'Content-Type: application/json' \
  -d '{"query": "연차 신청"}' | python3 -m json.tool

# 프론트엔드 접속 확인
curl -sf http://localhost:3000 > /dev/null && echo "Frontend: OK"

# 8. 정리
make down
```

## 생성 파일 전체 목록

| 파일 | 설명 |
|------|------|
| `docker-compose.yml` | 앱 계층 최종 (Langfuse v3 Web/Worker/Redis/MinIO + healthcheck) |
| `.env.example` | 환경 변수 템플릿 (최종) |
| `Makefile` | 개발/운영 커맨드 (최종) |
| `scripts/deploy-verify.sh` | 배포 검증 스크립트 |
| `docs/mac-studio-setup.md` | Mac Studio 설정 가이드 |

## 완료 조건 (자동 검증)

```bash
cp .env.example .env
make ollama-setup
make infra-up
make app-up
make migrate
# 헬스체크
curl -sf localhost:8000/api/health | python3 -m json.tool
curl -sf localhost:3000 > /dev/null && echo "Frontend: OK"
curl -sf localhost:3100/api/health | python3 -m json.tool
make app-down && make infra-down
```

## 프로젝트 완료 체크리스트

- [ ] 인프라(PostgreSQL + ES) 기동 확인
- [ ] Nori 인덱스 템플릿 적용
- [ ] Ollama 모델(bge-m3, qwen2.5:7b) 로드
- [ ] DB 마이그레이션 완료
- [ ] 백엔드 API 헬스체크 통과
- [ ] 프론트엔드 빌드 및 접속 확인
- [ ] Langfuse v3 (Web + Worker) 헬스체크 통과
- [ ] 문서 업로드 → 인덱싱 → 검색 → 답변 전체 흐름 동작
- [ ] 가드레일 ON/OFF 동작
- [ ] RAGAS 평가 실행 가능
- [ ] Makefile 모든 커맨드 동작
