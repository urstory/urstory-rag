# 트러블슈팅 가이드

프로덕션 운영 중 자주 발생하는 문제와 해결 방법입니다.

## 목차

- [로그 확인 방법](#로그-확인-방법)
- [컨테이너 디버깅](#컨테이너-디버깅)
- [PostgreSQL](#postgresql)
- [Elasticsearch](#elasticsearch)
- [Redis](#redis)
- [API 서버](#api-서버)
- [프론트엔드](#프론트엔드)
- [Langfuse](#langfuse)

---

## 로그 확인 방법

### Docker 컨테이너 로그

```bash
# 특정 서비스 로그 (최근 100줄)
docker logs --tail 100 rag-api
docker logs --tail 100 shared-postgres
docker logs --tail 100 shared-elasticsearch

# 실시간 로그 추적
docker logs -f rag-api

# 타임스탬프 포함
docker logs --timestamps --tail 50 rag-api
```

### 구조화 로그 (JSON) 파싱

프로덕션에서 `LOG_FORMAT=json` 사용 시 `jq`로 파싱할 수 있습니다:

```bash
# 에러 로그만 필터
docker logs rag-api 2>&1 | jq -r 'select(.level == "error")'

# 특정 시간 이후 로그
docker logs --since "2024-01-01T00:00:00" rag-api

# 느린 요청 찾기 (응답시간 1초 이상)
docker logs rag-api 2>&1 | jq -r 'select(.duration_ms > 1000)'
```

### 로그 레벨 임시 변경

디버깅 시 환경변수로 로그 레벨을 변경할 수 있습니다:

```bash
# .env 수정 후 재시작
LOG_LEVEL=DEBUG
docker compose restart rag-api
# 디버깅 완료 후 반드시 WARNING으로 복원
```

---

## 컨테이너 디버깅

### 컨테이너 상태 확인

```bash
# 전체 서비스 상태
docker compose ps
docker compose -f infra/docker-compose.yml ps

# 리소스 사용량
docker stats --no-stream

# 헬스체크 상태
docker inspect --format='{{.State.Health.Status}}' rag-api
```

### 컨테이너 내부 접속

```bash
# API 서버 내부 쉘
docker exec -it rag-api /bin/bash

# PostgreSQL 클라이언트
docker exec -it shared-postgres psql -U admin -d shared

# Elasticsearch
docker exec -it shared-elasticsearch bash

# Redis CLI
docker exec -it shared-redis redis-cli
```

### 네트워크 디버깅

```bash
# shared-infra 네트워크에 연결된 컨테이너 목록
docker network inspect shared-infra --format='{{range .Containers}}{{.Name}} {{end}}'

# 컨테이너 간 연결 테스트
docker exec rag-api curl -s http://shared-postgres:5432 || echo "연결 실패"
docker exec rag-api curl -s http://shared-elasticsearch:9200 || echo "연결 실패"
```

---

## PostgreSQL

### 연결 실패

**증상:** API 서버 로그에 `connection refused` 또는 `timeout`

```bash
# PostgreSQL 프로세스 확인
docker exec shared-postgres pg_isready -U admin

# 연결 수 확인
docker exec shared-postgres psql -U admin -d shared -c "SELECT count(*) FROM pg_stat_activity;"

# 최대 연결 수 확인
docker exec shared-postgres psql -U admin -d shared -c "SHOW max_connections;"
```

**해결:**
1. PostgreSQL 컨테이너가 실행 중인지 확인: `docker compose -f infra/docker-compose.yml ps`
2. 연결 수가 max_connections에 도달했으면 API 서버의 `DB_POOL_SIZE`를 줄이거나 PostgreSQL의 `max_connections`를 늘림
3. `shared-infra` 네트워크에 두 서비스가 모두 연결되어 있는지 확인

### pgvector 확장 누락

**증상:** `extension "vector" is not available`

```bash
docker exec shared-postgres psql -U admin -d shared -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

### 마이그레이션 실패

**증상:** `alembic upgrade head` 실행 시 에러

```bash
# 현재 마이그레이션 버전 확인
docker compose run --rm rag-api alembic current

# 마이그레이션 히스토리 확인
docker compose run --rm rag-api alembic history --verbose

# 특정 버전으로 다운그레이드 후 재시도
docker compose run --rm rag-api alembic downgrade -1
docker compose run --rm rag-api alembic upgrade head
```

### 디스크 공간 부족

```bash
# 테이블 크기 확인
docker exec shared-postgres psql -U admin -d shared -c "
SELECT schemaname, tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename))
FROM pg_tables WHERE schemaname = 'public' ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
"

# 볼륨 사용량 확인
docker system df -v | grep pg_data
```

---

## Elasticsearch

### 클러스터 상태 비정상

**증상:** 클러스터 상태가 `red` 또는 `yellow`

```bash
# 클러스터 상태 확인
curl -s http://localhost:9200/_cluster/health | jq .

# 인덱스 상태 확인
curl -s http://localhost:9200/_cat/indices?v

# 미할당 샤드 확인
curl -s http://localhost:9200/_cat/shards?v | grep UNASSIGNED
```

**해결 (yellow → green):**
단일 노드 환경에서는 레플리카를 0으로 설정:

```bash
curl -X PUT "http://localhost:9200/rag_*/_settings" -H 'Content-Type: application/json' -d '{
  "index": { "number_of_replicas": 0 }
}'
```

### Nori 플러그인 미설치

**증상:** 인덱싱 시 `Unknown analyzer type [korean]`

```bash
# 플러그인 확인
curl -s http://localhost:9200/_cat/plugins | grep analysis-nori
```

플러그인이 없으면 `infra/Dockerfile.elasticsearch`로 이미지를 다시 빌드:

```bash
cd infra && docker compose build elasticsearch && docker compose up -d elasticsearch
```

### OOM (Out of Memory)

**증상:** Elasticsearch 컨테이너가 자동 재시작됨

```bash
# JVM 힙 사용량 확인
curl -s http://localhost:9200/_nodes/stats/jvm | jq '.nodes[].jvm.mem'
```

`infra/docker-compose.yml`에서 힙 크기 조정:

```yaml
environment:
  - "ES_JAVA_OPTS=-Xms2g -Xmx2g"  # 서버 RAM의 50% 이하로 설정
```

---

## Redis

### 메모리 부족

```bash
# 메모리 사용량 확인
docker exec shared-redis redis-cli info memory | grep used_memory_human

# maxmemory 설정 확인
docker exec shared-redis redis-cli config get maxmemory
```

**해결:** `infra/docker-compose.yml`에서 `--maxmemory` 값 조정 (기본 256MB)

### 연결 거부

```bash
# Redis 프로세스 확인
docker exec shared-redis redis-cli ping
# PONG이면 정상
```

---

## API 서버

### 서버 시작 실패

```bash
# 상세 로그 확인
docker logs rag-api 2>&1 | head -50

# 환경변수 확인
docker exec rag-api env | sort
```

**주요 원인:**
- `DATABASE_URL` 형식 오류 → `postgresql+asyncpg://` 접두사 확인
- DB 연결 실패 → 인프라 먼저 시작 후 앱 시작
- 마이그레이션 미실행 → `alembic upgrade head` 실행

### 느린 응답

```bash
# 헬스체크로 병목 확인
curl -s http://localhost:8000/api/health | jq .

# 커넥션 풀 상태 확인
curl -s http://localhost:8000/api/health | jq '.pool_stats'
```

**주요 원인:**
- 커넥션 풀 소진 → `DB_POOL_SIZE`, `DB_MAX_OVERFLOW` 조정
- 리랭커 모델 초기 로딩 → 첫 요청 시 모델 다운로드에 시간 소요 (정상)
- Elasticsearch 슬로우 쿼리 → ES 힙 메모리 확인

### OpenAI API 오류

**증상:** `openai.AuthenticationError` 또는 `Rate limit exceeded`

```bash
# API 키 유효성 확인
curl -s https://api.openai.com/v1/models \
  -H "Authorization: Bearer ${OPENAI_API_KEY}" | jq .error
```

**해결:**
- 키가 만료되었으면 OpenAI 콘솔에서 재발급
- Rate limit이면 요청 간격을 두고 재시도 (자동 재시도 로직 내장)

---

## 프론트엔드

### 빌드 실패

```bash
docker logs rag-frontend 2>&1 | head -30
```

### API 연결 실패

**증상:** 프론트엔드에서 "서버에 연결할 수 없습니다" 오류

`NEXT_PUBLIC_API_URL` 환경변수 확인:

```bash
# Docker 내부에서는 컨테이너 이름 사용
NEXT_PUBLIC_API_URL=http://rag-api:8000

# 리버스 프록시 뒤에서는 외부 URL 사용
NEXT_PUBLIC_API_URL=https://your-domain.com
```

---

## Langfuse

### 웹 UI 접속 불가

```bash
# Langfuse 의존 서비스 확인
docker compose ps | grep -E "langfuse|clickhouse|minio"

# ClickHouse 헬스체크
docker exec rag-clickhouse wget -qO- http://localhost:8123/ping
```

**주요 원인:**
- ClickHouse 미기동 → `docker compose up -d rag-clickhouse` 후 대기
- MinIO 버킷 미생성 → `langfuse-minio-init` 컨테이너 로그 확인:
  ```bash
  docker logs langfuse-minio-init
  ```

### ENCRYPTION_KEY 오류

**증상:** `Invalid ENCRYPTION_KEY`

`LANGFUSE_ENCRYPTION_KEY`는 정확히 64자의 16진수 문자열이어야 합니다:

```bash
# 올바른 키 생성
openssl rand -hex 32
# 출력: 64자 hex (예: a1b2c3d4...)
```

주의: 한번 설정한 키를 변경하면 기존 암호화 데이터를 읽을 수 없습니다.
