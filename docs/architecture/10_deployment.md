# 배포 및 운영 가이드

## 앱 계층 docker-compose

```yaml
# docker-compose.yml (프로젝트 루트)
services:
  rag-api:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: rag-api
    ports:
      - "8000:8000"
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
    volumes:
      - upload_data:/app/uploads
    depends_on:
      - rag-redis
    networks:
      - default
      - shared-infra
    restart: unless-stopped

  rag-worker:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: rag-worker
    command: celery -A app.worker worker --loglevel=info --concurrency=2
    environment:
      DATABASE_URL: postgresql+asyncpg://admin:${POSTGRES_PASSWORD}@shared-postgres:5432/shared
      ELASTICSEARCH_URL: http://shared-elasticsearch:9200
      OLLAMA_URL: ${OLLAMA_URL:-http://host.docker.internal:11434}
      REDIS_URL: redis://rag-redis:6379
    depends_on:
      - rag-redis
    networks:
      - default
      - shared-infra
    restart: unless-stopped

  rag-watcher:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: rag-watcher
    command: python -m app.services.document.watcher
    environment:
      DATABASE_URL: postgresql+asyncpg://admin:${POSTGRES_PASSWORD}@shared-postgres:5432/shared
      ELASTICSEARCH_URL: http://shared-elasticsearch:9200
      OLLAMA_URL: ${OLLAMA_URL:-http://host.docker.internal:11434}
      REDIS_URL: redis://rag-redis:6379
    volumes:
      - upload_data:/app/uploads
      - ${WATCH_DIR_1:-./watched}:/data/documents:ro
    depends_on:
      - rag-redis
    networks:
      - default
      - shared-infra
    restart: unless-stopped

  rag-frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    container_name: rag-frontend
    ports:
      - "3000:3000"
    environment:
      NEXT_PUBLIC_API_URL: http://localhost:8000
    restart: unless-stopped

  rag-redis:
    image: redis:7-alpine
    container_name: rag-redis
    volumes:
      - redis_data:/data
    restart: unless-stopped

  langfuse:
    image: langfuse/langfuse:3
    container_name: rag-langfuse
    ports:
      - "3100:3000"
    environment:
      DATABASE_URL: postgresql://admin:${POSTGRES_PASSWORD}@shared-postgres:5432/shared
      CLICKHOUSE_MIGRATION_URL: clickhouse://rag-clickhouse:9000
      CLICKHOUSE_URL: http://rag-clickhouse:8123
      NEXTAUTH_SECRET: ${NEXTAUTH_SECRET}
      SALT: ${SALT}
      NEXTAUTH_URL: http://localhost:3100
    depends_on:
      - rag-clickhouse
    networks:
      - default
      - shared-infra
    restart: unless-stopped

  rag-clickhouse:
    image: clickhouse/clickhouse-server:latest
    container_name: rag-clickhouse
    volumes:
      - clickhouse_data:/var/lib/clickhouse
    restart: unless-stopped

volumes:
  redis_data:
  clickhouse_data:
  upload_data:

networks:
  shared-infra:
    external: true
```

## 환경 변수

```bash
# .env.example
# === 인프라 연결 ===
POSTGRES_PASSWORD=changeme_strong_password

# === Ollama ===
# Mac Studio: http://host.docker.internal:11434 (Docker에서) 또는 http://localhost:11434 (로컬)
# Linux GPU: http://localhost:11434
OLLAMA_URL=http://host.docker.internal:11434

# === 외부 API (저사양 또는 평가용) ===
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# === 디렉토리 감시 ===
# Docker 볼륨 마운트할 감시 디렉토리 (호스트 경로)
WATCH_DIR_1=./watched

# === Langfuse ===
LANGFUSE_PUBLIC_KEY=pk-...
LANGFUSE_SECRET_KEY=sk-...
NEXTAUTH_SECRET=changeme
SALT=changeme
```

## 백엔드 Dockerfile

```dockerfile
# backend/Dockerfile
FROM python:3.12-slim

WORKDIR /app

# 시스템 의존성
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Python 의존성
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e .

COPY . .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## 배포 순서

### 1. 인프라 기동

```bash
cd infra
cp .env.example .env
# .env 파일 수정 (패스워드 등)
docker compose up -d

# 헬스체크
docker compose ps
curl http://localhost:9200/_cluster/health?pretty
docker exec shared-postgres pg_isready -U admin
```

### 2. Elasticsearch Nori 인덱스 생성

```bash
# 인덱스 템플릿 적용
curl -X PUT "http://localhost:9200/_index_template/rag_template" \
  -H "Content-Type: application/json" \
  -d @infra/elasticsearch/nori-index-template.json
```

### 3. Ollama 모델 확인 (Mac Studio)

```bash
# Ollama가 실행 중인지 확인
curl http://localhost:11434/api/tags

# 필요한 모델 다운로드
ollama pull bge-m3
ollama pull qwen2.5:7b
```

### 4. 앱 기동

```bash
cd ..  # 프로젝트 루트
cp .env.example .env
# .env 파일 수정

# shared-infra 네트워크 확인 (infra에서 이미 생성됨)
docker network ls | grep shared-infra

# 앱 기동
docker compose up -d

# 확인
docker compose ps
curl http://localhost:8000/api/health
```

### 5. Langfuse 초기 설정

브라우저에서 `http://localhost:3100`에 접속하여 관리자 계정을 생성합니다.
프로젝트를 생성하고 API Key를 발급받아 `.env`에 설정합니다.

### 6. 관리자 UI 접속

브라우저에서 `http://localhost:3000`에 접속합니다.

## Makefile

```makefile
# Makefile
.PHONY: infra-up infra-down app-up app-down dev logs

# 인프라
infra-up:
	cd infra && docker compose up -d

infra-down:
	cd infra && docker compose down

# 앱
app-up:
	docker compose up -d

app-down:
	docker compose down

# 전체
up: infra-up app-up
down: app-down infra-down

# 개발 모드 (백엔드 로컬 실행)
dev-backend:
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

dev-frontend:
	cd frontend && pnpm dev

# 로그
logs:
	docker compose logs -f

logs-api:
	docker compose logs -f rag-api

logs-worker:
	docker compose logs -f rag-worker

logs-watcher:
	docker compose logs -f rag-watcher

# DB 마이그레이션
migrate:
	cd backend && alembic upgrade head

# RAGAS 평가 (CLI)
eval:
	cd backend && python -m app.services.evaluation.ragas --dataset-id $(DATASET_ID)

# 전체 재인덱싱
reindex-all:
	curl -X POST http://localhost:8000/api/system/reindex-all

# Ollama 모델 다운로드
ollama-setup:
	ollama pull bge-m3
	ollama pull qwen2.5:7b
```

## Mac Studio 환경 주의사항

1. **Ollama는 호스트에서 직접 실행**: Docker 내 Ollama는 Metal GPU를 사용할 수 없어 5-6배 느림
2. **Docker에서 Ollama 접근**: `OLLAMA_URL=http://host.docker.internal:11434` 사용
3. **로컬 개발 시 Ollama 접근**: `OLLAMA_URL=http://localhost:11434` 사용
4. **Docker Named Volume 사용**: 바인드 마운트는 Linux 대비 3배 느림
5. **슬립 방지**: 서버로 사용 시 `caffeinate -s` 실행

## 리랭커 실행 환경

bge-reranker-v2-m3-ko는 HuggingFace Transformers로 실행합니다. Mac Studio에서는 MPS (Metal Performance Shaders) 가속을 사용합니다.

```python
import torch
device = "mps" if torch.backends.mps.is_available() else "cpu"
```

Ollama에서 리랭커 모델을 직접 지원하지 않으므로, FastAPI 백엔드 프로세스 내에서 `sentence-transformers`로 로드합니다. 모델 로드 시간을 줄이기 위해 앱 시작 시 한 번 로드하고 메모리에 유지합니다.
