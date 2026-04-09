# 프로덕션 배포 가이드

UrstoryRAG를 프로덕션 환경에 배포하기 위한 가이드입니다.

## 목차

- [시스템 요구사항](#시스템-요구사항)
- [아키텍처 개요](#아키텍처-개요)
- [1단계: 환경변수 설정](#1단계-환경변수-설정)
- [2단계: 인프라 구성](#2단계-인프라-구성)
- [3단계: 앱 배포](#3단계-앱-배포)
- [4단계: Langfuse 설정](#4단계-langfuse-설정-선택)
- [5단계: 리버스 프록시 설정](#5단계-리버스-프록시-설정)
- [6단계: 배포 확인](#6단계-배포-확인)
- [배포 전 체크리스트](#배포-전-체크리스트)

---

## 시스템 요구사항

| 항목 | 최소 | 권장 |
|------|------|------|
| CPU | 4코어 | 8코어 |
| RAM | 8GB | 16GB |
| 디스크 | 50GB SSD | 100GB SSD |
| Docker | 24.0+ | 최신 |
| Docker Compose | v2.20+ | 최신 |

리랭커 모델(`bge-reranker-v2-m3-ko`)이 CPU에서 실행되므로 RAM이 충분해야 합니다.

## 아키텍처 개요

```
                          ┌─────────────┐
                          │   Nginx     │ :443 (HTTPS)
                          │  (Reverse   │
                          │   Proxy)    │
                          └──────┬──────┘
                       ┌─────────┼─────────┐
                       ▼         ▼         ▼
                  ┌─────────┐ ┌──────┐ ┌────────┐
                  │Frontend │ │ API  │ │Langfuse│
                  │ :3000   │ │:8000 │ │ :3000  │
                  └─────────┘ └──┬───┘ └────────┘
                                 │
              ┌──────────┬───────┼───────┬──────────┐
              ▼          ▼       ▼       ▼          ▼
         ┌─────────┐ ┌──────┐ ┌─────┐ ┌──────┐ ┌──────┐
         │PostgreSQL│ │  ES  │ │Redis│ │Click │ │MinIO │
         │+pgvector│ │+Nori │ │     │ │House │ │      │
         └─────────┘ └──────┘ └─────┘ └──────┘ └──────┘
```

서비스는 두 레이어로 분리되어 있습니다:

- **인프라 레이어** (`infra/docker-compose.yml`): PostgreSQL, Elasticsearch, Redis — 다른 프로젝트와 공유 가능
- **앱 레이어** (`docker-compose.yml` / `docker-compose.prod.yml`): API, Frontend, Langfuse

---

## 1단계: 환경변수 설정

```bash
cp .env.prod.example .env
```

### 필수 시크릿 생성

```bash
# JWT 시크릿 키
openssl rand -hex 32

# Langfuse NEXTAUTH_SECRET
openssl rand -hex 32

# Langfuse SALT
openssl rand -hex 32

# Langfuse ENCRYPTION_KEY (64자 hex)
openssl rand -hex 32
```

### 환경변수 분류

#### 필수 (미설정 시 서비스 불안정)

| 변수 | 설명 | 생성 방법 |
|------|------|-----------|
| `POSTGRES_PASSWORD` | DB 비밀번호 | 강력한 비밀번호 직접 설정 |
| `JWT_SECRET_KEY` | JWT 서명 키 | `openssl rand -hex 32` |
| `ADMIN_PASSWORD` | 최초 관리자 비밀번호 | 직접 설정 (기본값 사용 금지) |
| `OPENAI_API_KEY` | 임베딩 + LLM 생성 | OpenAI 콘솔에서 발급 |
| `CORS_ORIGINS` | 허용 도메인 | `https://your-domain.com` |

#### 필수 (Langfuse 사용 시)

| 변수 | 설명 |
|------|------|
| `NEXTAUTH_SECRET` | Langfuse 인증 시크릿 |
| `SALT` | Langfuse 해시 솔트 |
| `LANGFUSE_ENCRYPTION_KEY` | 64자 hex 암호화 키 |
| `CLICKHOUSE_PASSWORD` | ClickHouse 비밀번호 |
| `LANGFUSE_REDIS_AUTH` | Langfuse Redis 비밀번호 |
| `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD` | MinIO 자격증명 |

#### 권장

| 변수 | 설명 | 프로덕션 권장값 |
|------|------|----------------|
| `LOG_LEVEL` | 로그 레벨 | `WARNING` |
| `LOG_FORMAT` | 로그 형식 | `json` |
| `SENTRY_DSN` | Sentry 에러 추적 | Sentry 프로젝트 DSN |
| `SENTRY_ENVIRONMENT` | 환경 구분 | `production` |

---

## 2단계: 인프라 구성

### PostgreSQL + Elasticsearch + Redis

```bash
# 인프라 시작
cd infra
docker compose up -d

# 상태 확인
docker compose ps
```

정상 기동 확인:

```bash
# PostgreSQL
docker exec shared-postgres pg_isready -U ${POSTGRES_USER}

# Elasticsearch (Nori 플러그인 포함)
curl -s http://localhost:9200/_cat/plugins | grep analysis-nori

# Redis
docker exec shared-redis redis-cli ping
```

### PostgreSQL 설정

`infra/docker-compose.yml`의 PostgreSQL은 `pgvector/pgvector:pg17` 이미지를 사용합니다.
초기화 시 `init-db.sql`이 자동 실행되어 `pgvector` 확장과 RAG 스키마를 생성합니다.

**관리형 DB 사용 시 (AWS RDS, Cloud SQL 등):**

1. pgvector 확장이 지원되는지 확인
2. `.env`의 `DATABASE_URL`을 관리형 DB 주소로 변경
3. `infra/init-db.sql`의 SQL을 수동 실행:
   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   ```

### Elasticsearch + Nori

한국어 형태소 분석을 위해 커스텀 이미지를 빌드합니다 (`infra/Dockerfile.elasticsearch`).
Nori 인덱스 템플릿이 `infra/elasticsearch/nori-index-template.json`에 정의되어 있으며,
백엔드 시작 시 자동으로 적용됩니다.

프로덕션 권장 Elasticsearch 설정:

```yaml
environment:
  - "ES_JAVA_OPTS=-Xms2g -Xmx2g"  # 서버 RAM의 50% 이하
```

### 데이터 영속성

모든 데이터는 Docker named volume에 저장됩니다:

| 볼륨 | 서비스 | 데이터 |
|------|--------|--------|
| `pg_data` | PostgreSQL | 문서 메타데이터, 벡터, 사용자, 설정 |
| `es_data` | Elasticsearch | 키워드 인덱스 |
| `redis_data` | Redis | 캐시, 세션 |

**백업 대상은 `pg_data`가 가장 중요합니다.** Elasticsearch 인덱스는 재인덱싱으로 복구 가능합니다.

---

## 3단계: 앱 배포

### Docker 이미지 빌드

CI/CD에서 자동으로 GHCR에 푸시됩니다:

```
ghcr.io/urstory/urstory-rag-api:latest
ghcr.io/urstory/urstory-rag-frontend:latest
```

특정 버전 배포 시 `.env`에서 `TAG` 설정:

```bash
TAG=abc1234  # 커밋 SHA
```

### 프로덕션 배포

```bash
# docker-compose.prod.yml 사용 (API + Frontend만, Langfuse 제외)
docker compose -f docker-compose.prod.yml up -d

# 또는 Langfuse 포함 전체 스택
docker compose up -d
```

### DB 마이그레이션

배포 전 반드시 마이그레이션을 실행합니다:

```bash
docker compose run --rm rag-api alembic upgrade head
```

### 리소스 제한

`docker-compose.prod.yml`에 다음 제한이 설정되어 있습니다:

- API 서버: 메모리 2GB 제한
- 로그 로테이션: 10MB x 3개 파일

필요에 따라 조정하세요:

```yaml
deploy:
  resources:
    limits:
      memory: 4G    # 리랭커 모델 로딩 시 메모리 사용량에 따라 조정
```

---

## 4단계: Langfuse 설정 (선택)

Langfuse는 RAG 파이프라인의 관찰성(Observability)을 제공합니다.
설정하지 않아도 앱은 정상 동작합니다 (no-op 모드).

### Langfuse v3 구성요소

| 서비스 | 역할 |
|--------|------|
| `langfuse-web` | 웹 UI (포트 3100) |
| `langfuse-worker` | 비동기 이벤트 처리 |
| `rag-clickhouse` | OLAP 분석 DB |
| `langfuse-redis` | 내부 캐시 |
| `langfuse-minio` | S3 호환 오브젝트 스토리지 |

### 초기 설정

1. `docker compose up -d`로 전체 스택 시작
2. `http://your-domain:3100`에서 Langfuse UI 접속
3. 관리자 계정 생성 → 프로젝트 생성
4. 프로젝트의 API 키를 `.env`에 설정:
   ```
   LANGFUSE_PUBLIC_KEY=pk-lf-xxx
   LANGFUSE_SECRET_KEY=sk-lf-xxx
   ```
5. API 서버 재시작: `docker compose restart rag-api`

---

## 5단계: 리버스 프록시 설정

### Nginx 설정 예시

```nginx
upstream rag_api {
    server 127.0.0.1:8000;
}

upstream rag_frontend {
    server 127.0.0.1:3500;
}

upstream langfuse {
    server 127.0.0.1:3100;
}

# HTTP → HTTPS 리다이렉트
server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;

    # TLS 인증서 (Let's Encrypt 등)
    ssl_certificate     /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;
    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_ciphers         HIGH:!aNULL:!MD5;

    # 보안 헤더
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    # 프론트엔드 (기본)
    location / {
        proxy_pass http://rag_frontend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # API
    location /api/ {
        proxy_pass http://rag_api;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # 파일 업로드 크기 제한 (PDF 업로드용)
        client_max_body_size 100M;
    }

    # OpenAI 호환 API
    location /v1/ {
        proxy_pass http://rag_api;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Langfuse UI (선택)
    location /langfuse/ {
        proxy_pass http://langfuse/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Let's Encrypt SSL 발급

```bash
# certbot 설치
sudo apt install certbot python3-certbot-nginx

# 인증서 발급
sudo certbot --nginx -d your-domain.com

# 자동 갱신 확인
sudo certbot renew --dry-run
```

---

## 6단계: 배포 확인

### 헬스체크 엔드포인트

```bash
# 프로세스 살아있는지 확인
curl http://localhost:8000/api/health/live

# DB, ES, Redis 연결 확인
curl http://localhost:8000/api/health/ready

# 전체 시스템 상태 (커넥션 풀, 서킷브레이커 등)
curl http://localhost:8000/api/health
```

### 정상 응답 예시

```json
{
  "status": "healthy",
  "components": {
    "database": "healthy",
    "elasticsearch": "healthy",
    "redis": "healthy"
  }
}
```

### 프론트엔드 확인

```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:3500
# 200이면 정상
```

---

## 배포 전 체크리스트

### 시크릿

- [ ] `POSTGRES_PASSWORD` — 강력한 비밀번호 설정
- [ ] `JWT_SECRET_KEY` — `openssl rand -hex 32`로 생성
- [ ] `ADMIN_PASSWORD` — 기본값(`ChangeMe1234!@#$`) 변경
- [ ] `OPENAI_API_KEY` — 유효한 API 키 설정
- [ ] `NEXTAUTH_SECRET` — 랜덤 생성 (Langfuse 사용 시)
- [ ] `SALT` — 랜덤 생성 (Langfuse 사용 시)
- [ ] `LANGFUSE_ENCRYPTION_KEY` — 64자 hex (Langfuse 사용 시)
- [ ] `CLICKHOUSE_PASSWORD` — 기본값 변경 (Langfuse 사용 시)
- [ ] `LANGFUSE_REDIS_AUTH` — 기본값 변경 (Langfuse 사용 시)
- [ ] `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD` — 기본값 변경 (Langfuse 사용 시)

### 네트워크

- [ ] `CORS_ORIGINS` — 실제 도메인으로 변경 (와일드카드 사용 금지)
- [ ] `ALLOW_PUBLIC_SIGNUP=false` — 불필요한 회원가입 차단
- [ ] HTTPS 설정 완료 (TLS 인증서)
- [ ] 리버스 프록시 보안 헤더 설정

### 인프라

- [ ] PostgreSQL 정상 기동 및 pgvector 확장 활성화 확인
- [ ] Elasticsearch 정상 기동 및 Nori 플러그인 설치 확인
- [ ] Redis 정상 기동
- [ ] DB 마이그레이션 실행: `alembic upgrade head`
- [ ] Docker 볼륨 백업 전략 수립

### 모니터링

- [ ] `SENTRY_DSN` 설정 (에러 추적)
- [ ] `SENTRY_ENVIRONMENT=production`
- [ ] `LOG_LEVEL=WARNING`, `LOG_FORMAT=json`
- [ ] 헬스체크 엔드포인트 모니터링 도구 연동

### 운영

- [ ] Docker 리소스 제한 확인 (메모리, 로그 로테이션)
- [ ] `restart: unless-stopped` 설정 확인
- [ ] 백업 스케줄 설정 (PostgreSQL)
- [ ] 롤백 절차 숙지 (`docs/deployment/rollback.md`)
