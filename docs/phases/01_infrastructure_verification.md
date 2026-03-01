# Phase 1: 공유 인프라 구축 - 검증 가이드

## 구현 완료 파일

| 파일 | 설명 |
|------|------|
| `infra/.env.example` | 환경 변수 템플릿 |
| `infra/.env` | 실제 환경 변수 (`.env.example` 복사본) |
| `infra/init-db.sql` | PGVector 확장 + rag/langfuse 스키마 |
| `infra/Dockerfile.elasticsearch` | ES 8.17.0 + Nori 플러그인 |
| `infra/elasticsearch/nori-index-template.json` | 한국어 분석기 인덱스 템플릿 |
| `infra/docker-compose.yml` | PostgreSQL + Elasticsearch 컴포즈 |

---

## 직접 검증 방법

### 0. 사전 조건
- Docker Desktop 실행 중
- 포트 5432, 9200 미사용 상태

### 1. 인프라 기동

```bash
cd infra && docker compose up -d
```

정상이면 두 컨테이너가 기동됩니다. 약 30초 후 healthy 상태가 됩니다.

### 2. 컨테이너 상태 확인

```bash
docker compose ps
```

**기대 결과:** 두 서비스 모두 `(healthy)` 표시

```
NAME                   STATUS                    PORTS
shared-elasticsearch   Up ... (healthy)          0.0.0.0:9200->9200/tcp
shared-postgres        Up ... (healthy)          0.0.0.0:5432->5432/tcp
```

### 3. PostgreSQL + PGVector 확인

```bash
docker exec shared-postgres psql -U admin -d shared -c "SELECT extname FROM pg_extension WHERE extname='vector';"
```

**기대 결과:**
```
 extname
---------
 vector
(1 row)
```

### 4. PostgreSQL 스키마 확인

```bash
docker exec shared-postgres psql -U admin -d shared -c "SELECT schema_name FROM information_schema.schemata WHERE schema_name IN ('rag', 'langfuse');"
```

**기대 결과:**
```
 schema_name
-------------
 langfuse
 rag
(2 rows)
```

### 5. Elasticsearch + Nori 플러그인 확인

```bash
curl -s localhost:9200/_cat/plugins
```

**기대 결과:** `analysis-nori 8.17.0` 포함된 행 출력

### 6. Nori 인덱스 템플릿 적용 (최초 1회)

```bash
curl -s -X PUT "http://localhost:9200/_index_template/rag_template" \
  -H "Content-Type: application/json" \
  -d @elasticsearch/nori-index-template.json
```

**기대 결과:** `{"acknowledged":true}`

### 7. 템플릿 적용 확인

```bash
curl -s localhost:9200/_index_template/rag_template | python3 -m json.tool
```

**기대 결과:** `index_patterns: ["rag_*"]`, `korean` 분석기 설정이 포함된 JSON 출력

### 8. Nori 한국어 분석기 동작 테스트

테스트용 인덱스를 만들고 분석기를 실행합니다:

```bash
# 테스트 인덱스 생성 (rag_* 패턴이라 템플릿 자동 적용)
curl -s -X PUT "http://localhost:9200/rag_test"

# 한국어 분석 실행
curl -s -X POST "localhost:9200/rag_test/_analyze" \
  -H "Content-Type: application/json" \
  -d '{"analyzer": "korean", "text": "한국어 형태소 분석 테스트입니다"}' \
  | python3 -m json.tool

# 테스트 인덱스 정리
curl -s -X DELETE "http://localhost:9200/rag_test"
```

**기대 결과:** `한국어` → `한국어`, `한국`, `어` / `형태소` → `형태소`, `형태`, `소` / `분석` / `테스트` 토큰으로 분리. 조사 `입니다`는 필터링되어 제거됨.

### 9. 네트워크 확인

```bash
docker network ls | grep shared-infra
```

**기대 결과:** `shared-infra` 네트워크 존재

---

## 인프라 관리 명령어

```bash
# 인프라 중지 (데이터 유지)
cd infra && docker compose down

# 인프라 재시작
cd infra && docker compose up -d

# 인프라 완전 초기화 (데이터 삭제)
cd infra && docker compose down -v
```

---

## Phase 2 인수인계 정보

| 항목 | 값 |
|------|---|
| PostgreSQL 접속 (컨테이너 간) | `postgresql+asyncpg://admin:changeme_strong_password@shared-postgres:5432/shared` |
| PostgreSQL 접속 (호스트) | `postgresql+asyncpg://admin:changeme_strong_password@localhost:5432/shared` |
| Elasticsearch URL (컨테이너 간) | `http://shared-elasticsearch:9200` |
| Elasticsearch URL (호스트) | `http://localhost:9200` |
| Docker 네트워크 | `shared-infra` (external: true로 참조) |
| Nori 인덱스 패턴 | `rag_*` |
| PGVector | 활성화 완료 |
| DB 스키마 | `rag`, `langfuse` 생성 완료 |
