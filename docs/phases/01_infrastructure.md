# Phase 1: 공유 인프라 구축 상세 개발 계획

## 개요

| 항목 | 내용 |
|------|------|
| Phase | 1 |
| 담당 | 인프라 엔지니어 |
| 의존성 | 없음 |
| 참조 문서 | `docs/architecture/03_infrastructure.md` |

## 사전 조건

- Docker Desktop 설치 및 실행 중
- 포트 5432(PostgreSQL), 9200(Elasticsearch) 사용 가능

## 상세 구현 단계

### Step 1.1: 인프라 디렉토리 및 환경 변수 구성

#### 생성 파일
- `infra/.env.example`

#### 구현 내용
```bash
# infra/.env.example
POSTGRES_USER=admin
POSTGRES_PASSWORD=changeme_strong_password
POSTGRES_DB=shared
POSTGRES_PORT=5432
ES_PORT=9200
```

#### 검증
- `.env.example` 파일 존재 확인

---

### Step 1.2: PostgreSQL + PGVector 설정

#### 생성 파일
- `infra/init-db.sql`

#### 구현 내용
- `pgvector/pgvector:pg17` 이미지 사용
- `init-db.sql`로 PGVector 확장 활성화
- `rag`, `langfuse` 스키마 생성
- 컨테이너명: `shared-postgres`
- 데이터 볼륨: `pg_data`
- 헬스체크: `pg_isready -U admin`

```sql
-- infra/init-db.sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE SCHEMA IF NOT EXISTS rag;
CREATE SCHEMA IF NOT EXISTS langfuse;
```

#### 검증
```bash
docker exec shared-postgres psql -U admin -d shared -c "SELECT extname FROM pg_extension WHERE extname='vector';"
```

---

### Step 1.3: Elasticsearch + Nori 플러그인

#### 생성 파일
- `infra/Dockerfile.elasticsearch`

#### 구현 내용
- `elasticsearch:8.17.0` 기반으로 Nori 플러그인 빌드
- 단일 노드 모드 (`discovery.type=single-node`)
- 보안 비활성화 (`xpack.security.enabled=false`)
- JVM 메모리: `-Xms1g -Xmx1g`
- 컨테이너명: `shared-elasticsearch`
- 데이터 볼륨: `es_data`
- 헬스체크: `curl -f http://localhost:9200/_cluster/health`

```dockerfile
FROM docker.elastic.co/elasticsearch/elasticsearch:8.17.0
RUN bin/elasticsearch-plugin install --batch analysis-nori
```

#### 검증
```bash
curl -s localhost:9200/_cat/plugins | grep analysis-nori
```

---

### Step 1.4: Nori 인덱스 템플릿

#### 생성 파일
- `infra/elasticsearch/nori-index-template.json`

#### 구현 내용
- `rag_*` 패턴 인덱스에 자동 적용
- `nori_tokenizer` (decompound_mode: mixed)
- `korean` 분석기: nori_tokenizer + nori_readingform + lowercase + nori_part_of_speech
- 불용 품사 필터링: 조사(J), 어미(E), 기호(S계열), 보조용언(VX) 등
- mappings: content(text, analyzer: korean), meta(object)

#### 검증
```bash
curl -X PUT "http://localhost:9200/_index_template/rag_template" \
  -H "Content-Type: application/json" \
  -d @elasticsearch/nori-index-template.json
curl -s localhost:9200/_index_template/rag_template | python3 -m json.tool
```

---

### Step 1.5: Docker Compose 파일 작성

#### 생성 파일
- `infra/docker-compose.yml`

#### 구현 내용
- `postgres` 서비스: pgvector:pg17, init-db.sql 마운트
- `elasticsearch` 서비스: 커스텀 Dockerfile.elasticsearch 빌드
- 볼륨: `pg_data`, `es_data`
- 네트워크: `shared-infra` (default network name 지정)
- 재시작 정책: `unless-stopped`

#### 검증
```bash
cd infra && docker compose up -d
docker compose ps  # 두 서비스 모두 healthy
```

---

### Step 1.6: 통합 검증

#### 검증 스크립트

```bash
# 1. 인프라 기동
cd infra && docker compose up -d

# 2. PostgreSQL 접속 + PGVector 확인
docker exec shared-postgres psql -U admin -d shared \
  -c "SELECT extname FROM pg_extension WHERE extname='vector';"

# 3. Elasticsearch + Nori 확인
curl -s localhost:9200/_cat/plugins | grep analysis-nori

# 4. Nori 인덱스 템플릿 적용
curl -X PUT "http://localhost:9200/_index_template/rag_template" \
  -H "Content-Type: application/json" \
  -d @elasticsearch/nori-index-template.json

# 5. 템플릿 적용 확인
curl -s localhost:9200/_index_template/rag_template | python3 -m json.tool

# 6. Nori 분석기 동작 테스트
curl -s -X POST "localhost:9200/_analyze" \
  -H "Content-Type: application/json" \
  -d '{"analyzer": "korean", "text": "한국어 형태소 분석 테스트입니다"}' \
  | python3 -m json.tool

# 7. 네트워크 확인
docker network ls | grep shared-infra
```

## 생성 파일 전체 목록

| 파일 | 설명 |
|------|------|
| `infra/docker-compose.yml` | PostgreSQL + Elasticsearch 컴포즈 |
| `infra/Dockerfile.elasticsearch` | Nori 플러그인 포함 ES 이미지 |
| `infra/init-db.sql` | PGVector 확장, 스키마 생성 |
| `infra/elasticsearch/nori-index-template.json` | 한국어 분석기 인덱스 템플릿 |
| `infra/.env.example` | 환경 변수 템플릿 |

## 완료 조건 (자동 검증)

```bash
cd infra && docker compose up -d
docker exec shared-postgres psql -U admin -d shared -c "SELECT extname FROM pg_extension WHERE extname='vector';"
curl -s localhost:9200/_cat/plugins | grep analysis-nori
curl -X PUT "http://localhost:9200/_index_template/rag_template" \
  -H "Content-Type: application/json" \
  -d @elasticsearch/nori-index-template.json
curl -s localhost:9200/_index_template/rag_template | python3 -m json.tool
```

## 인수인계 항목

Phase 2로 전달할 정보:
- PostgreSQL 접속 정보: `postgresql+asyncpg://admin:<password>@shared-postgres:5432/shared`
- Elasticsearch URL: `http://shared-elasticsearch:9200`
- Docker 네트워크: `shared-infra` (external: true로 참조)
- Nori 인덱스 패턴: `rag_*`
- PGVector 확장 활성화 완료, `rag` 스키마 생성 완료
