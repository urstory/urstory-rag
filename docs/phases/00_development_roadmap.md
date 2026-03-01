# UrstoryRAG 전체 개발 로드맵

## 개요

| 항목 | 내용 |
|------|------|
| 작성일 | 2026-03-01 |
| 총 Phase | 9개 |
| 아키텍처 문서 | `docs/architecture/` (10개 문서) |
| 참조 설계 | `/Users/toto/mybooks/gisa/기사/20260302_korean_rag_production_architecture.md` |

## 개발 원칙

### 검증 자동화
- 모든 Phase는 Claude Code가 자동으로 빌드/테스트를 실행하여 검증
- 검증 실패 시 원인 분석 → 수정 → 재검증 사이클 반복
- 각 Phase 완료 조건에 자동 검증 명령어 명시

### 백엔드 TDD
- RED: 실패하는 테스트 먼저 작성
- GREEN: 테스트를 통과하는 최소 구현
- REFACTOR: 중복 제거, 구조 개선
- pytest + pytest-asyncio 사용

### 프론트엔드 E2E 테스트
- 지원 환경: 모바일, PC (태블릿 별도 대응 없음)
- Playwright Docker 이미지: `fullstackfamily-platform-playwright:latest`
- Playwright 별도 설치 금지. Docker 컨테이너로만 실행

---

## Phase 의존성 다이어그램

```
Phase 1 (인프라)
  └──→ Phase 2 (백엔드 기반 + Makefile)
         ├──→ Phase 3 (문서 파이프라인)
         │      └──→ Phase 4 (RAG 검색 파이프라인)
         │             ├──→ Phase 5 (가드레일)
         │             └──→ Phase 6 (평가/모니터링)
         └──→ Phase 7 (프론트엔드 빌드)
                         ↓
              Phase 8 (통합/E2E 테스트) ←── Phase 5, 6 완료 필요
                      └──→ Phase 9 (배포)
```

**병렬 가능 구간:**
- Phase 7은 Phase 2 완료 후 Phase 3~6과 병렬 진행 가능 (API 명세 기반 개발, 빌드 검증만)
- Phase 5와 Phase 6은 둘 다 Phase 4 이후이므로 병렬 진행 가능

---

## Phase 1: 공유 인프라 구축

### 목표
PostgreSQL+PGVector, Elasticsearch+Nori 공유 인프라 Docker Compose 구성

### 범위
- `infra/docker-compose.yml` (PostgreSQL 17 + PGVector, Elasticsearch 8.17 + Nori)
- `infra/Dockerfile.elasticsearch` (Nori 플러그인 설치)
- `infra/init-db.sql` (PGVector 확장, rag/langfuse 스키마)
- `infra/elasticsearch/nori-index-template.json` (형태소 분석 설정)
- 공유 네트워크 설정 (`shared-infra`)

### 완료 조건
```bash
# 자동 검증
cd infra && docker compose up -d
# PostgreSQL 접속 + PGVector 확인
docker exec shared-postgres psql -U admin -d shared -c "SELECT extname FROM pg_extension WHERE extname='vector';"
# Elasticsearch + Nori 확인
curl -s localhost:9200/_cat/plugins | grep analysis-nori
# Nori 인덱스 템플릿 적용
curl -X PUT "http://localhost:9200/_index_template/rag_template" \
  -H "Content-Type: application/json" \
  -d @elasticsearch/nori-index-template.json
# 템플릿 적용 확인
curl -s localhost:9200/_index_template/rag_template | python -m json.tool
```

### 참조 문서
- `docs/architecture/03_infrastructure.md`

---

## Phase 2: 백엔드 기반 구축

### 목표
FastAPI 프로젝트 스켈레톤, DB 모델, 설정 시스템, LLM 프로바이더 추상화 계층

### 범위
- 프로젝트 초기화: `pyproject.toml`, 디렉토리 구조, `backend/app/main.py`
- SQLAlchemy 모델: documents, chunks, settings 테이블
- Alembic 마이그레이션 설정
- 설정 2단계 관리: 환경변수(.env) + DB 설정 테이블
- LLM 프로바이더 인터페이스 (Protocol): EmbeddingProvider, LLMProvider
- Ollama 프로바이더 구현체
- 헬스체크 API (`GET /api/health`)
- `docker-compose.yml` (앱 계층: rag-api, redis)
- `Makefile` 기본 개발 도구: infra-up/down, app-up/down, dev-backend, migrate, test

### 완료 조건
```bash
# 자동 검증
cd backend && pytest --tb=short -q
# API 서버 기동 + 헬스체크
uvicorn app.main:app --host 0.0.0.0 --port 8000 &
curl -s localhost:8000/api/health | python -m json.tool
# DB 마이그레이션
alembic upgrade head
```

### 참조 문서
- `docs/architecture/02_project_structure.md`
- `docs/architecture/04_backend.md`

---

## Phase 3: 문서 수집/파싱 파이프라인

### 목표
문서 업로드 + 디렉토리 감시 듀얼 수집, 파싱, 청킹, 임베딩, 듀얼 인덱싱(PGVector + Elasticsearch) 파이프라인

### 범위
- 문서 CRUD API (`/api/documents`)
- 파일 파싱: PDF, DOCX, TXT, Markdown
- 청킹 전략 4종: recursive(기본), semantic, contextual, auto
- bge-m3 임베딩 (Ollama)
- PGVector 저장 + Elasticsearch 인덱싱 (듀얼)
- Celery 비동기 인덱싱 태스크
- **디렉토리 감시 서비스 (watchdog)**: 지정 디렉토리 파일 변경 감지 → 자동 인덱싱
  - 이벤트 모드 (watchdog) + 폴링 모드 지원
  - 파일 해시 기반 변경 감지, 초기 전체 스캔
  - 감시 API (`/api/watcher/*`): 시작/중지/상태/수동 스캔
- 재인덱싱 (무중단: 새 인덱스 생성 → alias 교체)

### 완료 조건
```bash
# 자동 검증 - 단위 테스트
cd backend && pytest tests/services/test_document*.py tests/services/test_chunking*.py tests/services/test_embedding*.py tests/services/test_watcher*.py -v
# 통합 테스트: 문서 업로드 → 청킹 → 임베딩 → 듀얼 인덱싱
pytest tests/integration/test_document_pipeline.py -v
# 통합 테스트: 디렉토리 감시 → 자동 인덱싱
pytest tests/integration/test_watcher_pipeline.py -v
# 애플리케이션 수준 검증: 문서 업로드 후 인덱싱된 문서 수 확인
curl -s localhost:8000/api/documents | python -c "import sys,json; docs=json.load(sys.stdin); assert len(docs['items'])>0, 'No documents indexed'"
# 감시 상태 확인
curl -s localhost:8000/api/watcher/status | python -m json.tool
# Elasticsearch 인덱스 문서 수 확인 (인덱스명은 구현 시 결정)
curl -s "localhost:9200/rag_*/_count" | python -m json.tool
```

### 참조 문서
- `docs/architecture/04_backend.md` (듀얼 인덱싱, Celery)
- `docs/architecture/07_rag_pipeline.md` (청킹 전략)

---

## Phase 4: RAG 검색/답변 파이프라인

### 목표
하이브리드 검색(벡터+키워드), RRF, 리랭킹, HyDE, 답변 생성 전체 파이프라인

### 범위
- Haystack 2.x 파이프라인 구성
- 벡터 검색: PGVector (Top-K)
- 키워드 검색: Elasticsearch + Nori (BM25 Top-K)
- RRF 결합 (k=60, 가중치 조정 가능)
- 리랭킹: dragonkue/bge-reranker-v2-m3-ko (20→5건)
- HyDE: Qwen2.5-7B로 가상 문서 생성 (ON/OFF, 모드 선택)
- 답변 생성 + 프롬프트 관리
- 검색 API: `POST /api/search`, `POST /api/search/debug`
- 디버그 응답: pipeline_trace (각 단계별 passed, duration_ms, results_count)

### 완료 조건
```bash
# 자동 검증
cd backend && pytest tests/services/test_search*.py tests/services/test_reranking*.py tests/services/test_hyde*.py tests/pipelines/ -v
# 통합 테스트: 문서 인덱싱 후 검색 → 리랭킹 → 답변 생성
pytest tests/integration/test_search_pipeline.py -v
# 디버그 API로 파이프라인 트레이스 확인
curl -s -X POST localhost:8000/api/search/debug -H 'Content-Type: application/json' -d '{"query": "테스트 검색"}' | python -m json.tool
```

### 참조 문서
- `docs/architecture/07_rag_pipeline.md`
- `docs/architecture/06_api_design.md`

---

## Phase 5: 가드레일

### 목표
PII 탐지/마스킹, 프롬프트 인젝션 방어, 할루시네이션 탐지 3계층 가드레일

### 범위
- **PII 탐지**: 한국 고유 패턴 정규식(주민번호, 전화번호, 사업자번호 등) → LLM 2차 검증 → 마스킹
- **프롬프트 인젝션 방어**: 패턴 매칭(한/영) → 분류 모델 → LLM-as-Judge 3계층
- **할루시네이션 탐지**: LLM-as-Judge (코사인 유사도 방식 사용 금지)
  - grounded_ratio 0.8 미만 시 경고/재생성
- 각 가드레일 독립 ON/OFF + action(mask/block/warn) 설정
- 입력 가드레일 → [검색/생성] → 출력 가드레일 파이프라인 통합

### 완료 조건
```bash
# 자동 검증 - 단위 테스트 (PII 패턴, 인젝션 패턴, 할루시네이션 fixture 포함)
cd backend && pytest tests/services/test_guardrails*.py -v
# 통합 테스트: 입력 가드레일 → 검색/생성 → 출력 가드레일 전체 파이프라인
pytest tests/integration/test_guardrails_pipeline.py -v
# 가드레일 ON/OFF 설정 API 확인
curl -s localhost:8000/api/settings | python -c "import sys,json; s=json.load(sys.stdin); print(s['guardrails'])"
```

### 참조 문서
- `docs/architecture/08_guardrails.md`

---

## Phase 6: 평가 및 모니터링

### 목표
RAGAS 자동 평가 + Langfuse v3 트레이싱/모니터링

### 범위
- **RAGAS 평가**: Faithfulness, Answer Relevancy, Context Precision, Context Recall
  - GPT-4 judge, 한국어 few-shot 예제
  - 평가 데이터셋 CRUD (`/api/evaluation/datasets`)
  - 평가 실행 (`/api/evaluation/run`) → Celery 비동기
  - 평가 결과 조회 (`/api/evaluation/runs`)
- **Langfuse v3**: Web + Worker + ClickHouse + Redis + MinIO 컨테이너 구성
  - `@observe` 데코레이터로 파이프라인 전체 트레이싱
  - 모니터링 API (`/api/monitoring/stats|traces|costs`)
  - 이상 탐지: hallucination 평균 0.7 미만 시 알림

### 사전 조건
- 앱 계층 compose 기동 완료 (`make app-up` → Langfuse + ClickHouse 포함)

### 완료 조건
```bash
# 사전 조건: 앱 계층 기동 (Langfuse + ClickHouse 포함)
make infra-up && make app-up
# 자동 검증
cd backend && pytest tests/services/test_evaluation*.py tests/services/test_monitoring*.py -v
# Langfuse 헬스체크
curl -sf localhost:3100/api/health | python -m json.tool
# RAGAS 평가 실행 테스트 (샘플 데이터셋)
pytest tests/integration/test_evaluation_run.py -v
```

### 참조 문서
- `docs/architecture/09_evaluation_monitoring.md`

---

## Phase 7: 관리자 프론트엔드

### 목표
Next.js 15 관리자 대시보드 (모바일 + PC 반응형)

### 범위
- 프로젝트 초기화: Next.js 15, React 19, Tailwind CSS 4, shadcn/ui, pnpm
- **페이지 구현**:
  - `/` 대시보드: 시스템 상태, 문서 수, 검색 통계
  - `/documents` 문서 관리: 업로드, 목록, 삭제, 재인덱싱, 수집 소스(업로드/감시) 표시
  - `/search` 검색 테스트: 파이프라인 시각화, 단계별 결과/시간
  - `/settings/*` 설정: chunking, embedding, search, reranking, hyde, guardrails, generation, watcher
  - `/evaluation` 평가: 데이터셋 관리, 평가 실행, 결과 시각화
  - `/monitoring` 모니터링: Langfuse 트레이스, 비용, 알림
- API 클라이언트 (`lib/api.ts`): TanStack Query v5
- 반응형: 모바일(≤768px), PC(>768px)
- Dockerfile: node:22-alpine 멀티스테이지, standalone 출력

### 완료 조건
```bash
# 자동 검증 - 빌드 검증 (E2E는 Phase 8에서 수행)
cd frontend && pnpm install && pnpm lint && pnpm type-check && pnpm build
```

### 참조 문서
- `docs/architecture/05_frontend.md`
- `docs/architecture/06_api_design.md`

---

## Phase 8: 통합 테스트 및 E2E 테스트

### 목표
전체 시스템 엔드투엔드 검증 (인프라 → 백엔드 → 프론트엔드)

### 범위
- **백엔드 통합 테스트**: 전체 파이프라인 (문서 업로드/디렉토리 감시 → 인덱싱 → 검색 → 답변 → 가드레일)
- **프론트엔드 E2E 테스트** (Playwright Docker):
  - 문서 업로드 시나리오
  - 디렉토리 감시 설정 시나리오
  - 검색 및 답변 시나리오
  - 설정 변경 시나리오 (가드레일 ON/OFF, 감시 ON/OFF 등)
  - 모바일 뷰포트 테스트
  - PC 뷰포트 테스트
- **성능 테스트**: 검색 응답 시간, 인덱싱 처리량
- **에러 시나리오**: Ollama 미응답, DB 연결 실패 등 복원력 테스트

### 완료 조건
```bash
# 자동 검증 - 전체 시스템 기동 (Makefile은 Phase 2에서 생성됨)
make infra-up && make app-up
# 백엔드 전체 테스트
cd backend && pytest tests/ -v --tb=short
# 프론트엔드 E2E 테스트 (Playwright Docker) - 실 백엔드 연동
docker run --rm --network host \
  -v $(pwd)/frontend/e2e:/work/e2e \
  -v $(pwd)/frontend/playwright.config.ts:/work/playwright.config.ts \
  fullstackfamily-platform-playwright:latest \
  npx playwright test
# 전체 시스템 정리
make app-down && make infra-down
```

### 참조 문서
- 전체 `docs/architecture/` 문서

---

## Phase 9: 배포 및 운영

### 목표
앱 계층 Docker Compose, Makefile, 배포 자동화

### 범위
- `docker-compose.yml` 최종 정리 (앱 계층): rag-api, rag-worker(Celery), rag-watcher(디렉토리 감시), rag-frontend, rag-redis, langfuse-web, langfuse-worker, rag-clickhouse, langfuse-redis, langfuse-minio
- `Makefile` 배포용 확장: dev-frontend, eval, reindex-all, ollama-setup 추가
- `.env.example`: 환경별 설정 템플릿
- 배포 순서 문서화 및 검증 스크립트
- Mac Studio 전용 설정: `OLLAMA_URL=http://host.docker.internal:11434`
- 헬스체크 스크립트: 전 컨테이너 상태 확인

### 완료 조건
```bash
# 자동 검증 - 클린 상태에서 전체 배포
cp .env.example .env
make ollama-setup   # 모델 확인
make infra-up       # 인프라 기동
make migrate        # DB 마이그레이션
make app-up         # 앱 기동
# 전체 헬스체크
curl -s localhost:8000/api/health   # 백엔드
curl -s localhost:3000              # 프론트엔드
curl -s localhost:3100/api/health   # Langfuse
make app-down && make infra-down
```

### 참조 문서
- `docs/architecture/10_deployment.md`

---

## 자동 검증 전략 요약

| 검증 단계 | 도구 | 트리거 |
|-----------|------|--------|
| 백엔드 단위 테스트 | pytest (TDD) | 매 구현 단계 |
| 백엔드 통합 테스트 | pytest + Docker infra | Phase 완료 시 |
| 프론트엔드 빌드 | pnpm lint + type-check + build | 매 구현 단계 |
| E2E 테스트 | fullstackfamily-platform-playwright:latest | Phase 8 |
| 전체 시스템 검증 | Makefile + 헬스체크 | Phase 9 |

### 실패 시 자동 수정 사이클

```
테스트 실행 → 실패 감지 → 에러 분석 → 코드 수정 → 재테스트 → (반복)
```

- Claude Code가 테스트 출력을 분석하여 실패 원인 파악
- 코드 수정 후 동일 테스트 재실행으로 수정 확인
- 최대 3회 반복 후에도 실패 시 사용자에게 보고

---

## 일정 요약

| Phase | 이름 | 의존성 | 병렬 가능 |
|-------|------|--------|-----------|
| 1 | 공유 인프라 구축 | 없음 | - |
| 2 | 백엔드 기반 구축 + Makefile | Phase 1 | - |
| 3 | 문서 수집/파싱 파이프라인 | Phase 2 | Phase 7과 병렬 |
| 4 | RAG 검색/답변 파이프라인 | Phase 3 | Phase 7과 병렬 |
| 5 | 가드레일 | Phase 4 | Phase 6과 병렬 |
| 6 | 평가 및 모니터링 | Phase 4 | Phase 5와 병렬 |
| 7 | 관리자 프론트엔드 (빌드 검증) | Phase 2 | Phase 3~6과 병렬 |
| 8 | 통합/E2E 테스트 | Phase 5, 6, 7 | - |
| 9 | 배포 및 운영 | Phase 8 | - |
