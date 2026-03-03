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
      REDIS_URL: redis://rag-redis:6379
      OPENAI_API_KEY: ${OPENAI_API_KEY}
      LANGFUSE_HOST: http://rag-langfuse:3000
      LANGFUSE_PUBLIC_KEY: ${LANGFUSE_PUBLIC_KEY}
      LANGFUSE_SECRET_KEY: ${LANGFUSE_SECRET_KEY}
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
      REDIS_URL: redis://rag-redis:6379
      OPENAI_API_KEY: ${OPENAI_API_KEY}
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
      REDIS_URL: redis://rag-redis:6379
      OPENAI_API_KEY: ${OPENAI_API_KEY}
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
    # 개발 모드에서는 포트 3500 사용 (pnpm dev --port 3500)
    # 프로덕션 빌드는 포트 3000

  rag-redis:
    image: redis:7-alpine
    container_name: rag-redis
    volumes:
      - redis_data:/data
    restart: unless-stopped

  langfuse-web:
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
      ENCRYPTION_KEY: ${ENCRYPTION_KEY}
      LANGFUSE_S3_EVENT_UPLOAD_BUCKET: langfuse
      LANGFUSE_S3_EVENT_UPLOAD_ENDPOINT: http://rag-langfuse-minio:9000
      LANGFUSE_S3_EVENT_UPLOAD_ACCESS_KEY_ID: minioadmin
      LANGFUSE_S3_EVENT_UPLOAD_SECRET_ACCESS_KEY: minioadmin
      LANGFUSE_S3_EVENT_UPLOAD_FORCE_PATH_STYLE: "true"
      REDIS_HOST: rag-langfuse-redis
      REDIS_PORT: "6379"
    depends_on:
      - rag-clickhouse
      - rag-langfuse-redis
      - rag-langfuse-minio
    networks:
      - default
      - shared-infra
    restart: unless-stopped

  langfuse-worker:
    image: langfuse/langfuse:3
    container_name: rag-langfuse-worker
    command: ["node", "packages/worker/dist/index.js"]
    environment:
      DATABASE_URL: postgresql://admin:${POSTGRES_PASSWORD}@shared-postgres:5432/shared
      CLICKHOUSE_MIGRATION_URL: clickhouse://rag-clickhouse:9000
      CLICKHOUSE_URL: http://rag-clickhouse:8123
      ENCRYPTION_KEY: ${ENCRYPTION_KEY}
      LANGFUSE_S3_EVENT_UPLOAD_BUCKET: langfuse
      LANGFUSE_S3_EVENT_UPLOAD_ENDPOINT: http://rag-langfuse-minio:9000
      LANGFUSE_S3_EVENT_UPLOAD_ACCESS_KEY_ID: minioadmin
      LANGFUSE_S3_EVENT_UPLOAD_SECRET_ACCESS_KEY: minioadmin
      LANGFUSE_S3_EVENT_UPLOAD_FORCE_PATH_STYLE: "true"
      REDIS_HOST: rag-langfuse-redis
      REDIS_PORT: "6379"
    depends_on:
      - rag-clickhouse
      - rag-langfuse-redis
      - rag-langfuse-minio
    networks:
      - default
      - shared-infra
    restart: unless-stopped

  rag-clickhouse:
    image: clickhouse/clickhouse-server:latest
    container_name: rag-clickhouse
    ports:
      - "8123:8123"
      - "9000:9000"
    volumes:
      - clickhouse_data:/var/lib/clickhouse
    restart: unless-stopped

  rag-langfuse-redis:
    image: redis:7-alpine
    container_name: rag-langfuse-redis
    volumes:
      - langfuse_redis_data:/data
    restart: unless-stopped

  rag-langfuse-minio:
    image: minio/minio
    container_name: rag-langfuse-minio
    command: server /data --console-address ":9001"
    ports:
      - "9002:9000"
      - "9003:9001"
    volumes:
      - langfuse_minio_data:/data
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
    restart: unless-stopped

volumes:
  redis_data:
  clickhouse_data:
  upload_data:
  langfuse_redis_data:
  langfuse_minio_data:

networks:
  shared-infra:
    external: true
```

## 환경 변수

```bash
# .env.example
# === 인프라 연결 ===
POSTGRES_PASSWORD=changeme_strong_password

# === OpenAI API (필수) ===
# 임베딩(text-embedding-3-small), LLM(gpt-4.1-mini), 평가(gpt-4o) 모두 사용
OPENAI_API_KEY=sk-...

# === 디렉토리 감시 ===
# Docker 볼륨 마운트할 감시 디렉토리 (호스트 경로)
WATCH_DIR_1=./watched

# === Langfuse v3 ===
LANGFUSE_PUBLIC_KEY=pk-...
LANGFUSE_SECRET_KEY=sk-...
NEXTAUTH_SECRET=changeme
SALT=changeme
ENCRYPTION_KEY=  # 64자 hex (openssl rand -hex 32 으로 생성)
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

### 3. OpenAI API 키 확인

```bash
# API 키가 유효한지 확인
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY" | head -c 200
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
	cd frontend && pnpm dev --port 3500

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

# Langfuse v3 ENCRYPTION_KEY 생성
langfuse-key:
	openssl rand -hex 32
```

## Mac Studio 환경 주의사항

1. **OpenAI API 전용**: 임베딩, LLM, 평가 모두 OpenAI API 사용 (Ollama 미사용)
2. **리랭커 로컬 실행**: bge-reranker-v2-m3-ko는 MPS(Metal Performance Shaders) 가속으로 로컬 실행
3. **Docker Named Volume 사용**: 바인드 마운트는 Linux 대비 3배 느림
4. **슬립 방지**: 서버로 사용 시 `caffeinate -s` 실행
5. **프론트엔드 포트**: 개발 모드 3500, 프로덕션 3000

## 리랭커 실행 환경

bge-reranker-v2-m3-ko는 HuggingFace Transformers로 실행합니다. Mac Studio에서는 MPS (Metal Performance Shaders) 가속을 사용합니다.

```python
import torch
device = "mps" if torch.backends.mps.is_available() else "cpu"
```

Ollama에서 리랭커 모델을 직접 지원하지 않으므로, FastAPI 백엔드 프로세스 내에서 `sentence-transformers`로 로드합니다. 모델 로드 시간을 줄이기 위해 앱 시작 시 한 번 로드하고 메모리에 유지합니다.
