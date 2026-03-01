# Phase 6: 평가 및 모니터링 상세 개발 계획

## 개요

| 항목 | 내용 |
|------|------|
| Phase | 6 |
| 담당 | RAG/ML 엔지니어 |
| 의존성 | Phase 4 |
| 병렬 가능 | Phase 5와 병렬 |
| 참조 문서 | `docs/architecture/09_evaluation_monitoring.md` |

## 사전 조건

- Phase 4 완료 (검색/답변 파이프라인 동작)
- OpenAI API Key 설정 (RAGAS GPT-4 judge용)
- 앱 계층 docker-compose에 Langfuse v3 (Web + Worker + ClickHouse + Redis + MinIO) 추가

## 상세 구현 단계

### Step 6.1: Langfuse v3 + ClickHouse + Redis + MinIO Docker 구성

> **중요**: Langfuse v3는 단일 컨테이너가 아닌 **Web + Worker 2개 컨테이너** 구성이 필수입니다.
> 또한 **Redis**(큐/캐시용), **S3 호환 스토리지**(MinIO, 이벤트/미디어 업로드용)가 필수 의존성입니다.

#### 수정 파일
- `docker-compose.yml` (프로젝트 루트)

#### 구현 내용

앱 계층 docker-compose에 추가:
```yaml
langfuse-web:
  image: langfuse/langfuse:3
  container_name: rag-langfuse-web
  ports:
    - "3100:3000"
  environment: &langfuse-env
    DATABASE_URL: postgresql://admin:${POSTGRES_PASSWORD}@shared-postgres:5432/shared
    NEXTAUTH_URL: http://localhost:3100
    NEXTAUTH_SECRET: ${NEXTAUTH_SECRET}
    SALT: ${SALT}
    ENCRYPTION_KEY: ${LANGFUSE_ENCRYPTION_KEY}
    # ClickHouse
    CLICKHOUSE_URL: http://rag-clickhouse:8123
    CLICKHOUSE_MIGRATION_URL: clickhouse://rag-clickhouse:9000
    CLICKHOUSE_USER: ${CLICKHOUSE_USER:-default}
    CLICKHOUSE_PASSWORD: ${CLICKHOUSE_PASSWORD:-}
    # Redis (Langfuse 전용)
    REDIS_HOST: langfuse-redis
    REDIS_PORT: 6379
    REDIS_AUTH: ${LANGFUSE_REDIS_AUTH:-langfuseredis}
    # MinIO (S3 호환 스토리지)
    LANGFUSE_S3_EVENT_UPLOAD_BUCKET: langfuse
    LANGFUSE_S3_EVENT_UPLOAD_REGION: auto
    LANGFUSE_S3_EVENT_UPLOAD_ACCESS_KEY_ID: ${MINIO_ROOT_USER:-minioadmin}
    LANGFUSE_S3_EVENT_UPLOAD_SECRET_ACCESS_KEY: ${MINIO_ROOT_PASSWORD:-minioadmin}
    LANGFUSE_S3_EVENT_UPLOAD_ENDPOINT: http://langfuse-minio:9000
    LANGFUSE_S3_EVENT_UPLOAD_FORCE_PATH_STYLE: "true"
  depends_on:
    rag-clickhouse:
      condition: service_healthy
    langfuse-redis:
      condition: service_healthy
    langfuse-minio:
      condition: service_healthy
  networks:
    - default
    - shared-infra
  restart: unless-stopped

langfuse-worker:
  image: langfuse/langfuse-worker:3
  container_name: rag-langfuse-worker
  environment:
    <<: *langfuse-env
  depends_on:
    rag-clickhouse:
      condition: service_healthy
    langfuse-redis:
      condition: service_healthy
    langfuse-minio:
      condition: service_healthy
  networks:
    - default
    - shared-infra
  restart: unless-stopped

rag-clickhouse:
  image: clickhouse/clickhouse-server:latest
  container_name: rag-clickhouse
  environment:
    CLICKHOUSE_USER: ${CLICKHOUSE_USER:-default}
    CLICKHOUSE_PASSWORD: ${CLICKHOUSE_PASSWORD:-}
  volumes:
    - clickhouse_data:/var/lib/clickhouse
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
  volumes:
    - langfuse_redis_data:/data
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
  volumes:
    - langfuse_minio_data:/data
  healthcheck:
    test: ["CMD", "mc", "ready", "local"]
    interval: 5s
    timeout: 5s
    retries: 10
  restart: unless-stopped
```

`.env.example` 추가 변수:
```
# Langfuse
LANGFUSE_PUBLIC_KEY=pk-...
LANGFUSE_SECRET_KEY=sk-...
NEXTAUTH_SECRET=changeme_random_string
SALT=changeme_random_string
LANGFUSE_ENCRYPTION_KEY=0000000000000000000000000000000000000000000000000000000000000000
# ClickHouse
CLICKHOUSE_USER=default
CLICKHOUSE_PASSWORD=
# Langfuse Redis
LANGFUSE_REDIS_AUTH=langfuseredis
# MinIO
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=minioadmin
```

#### 검증
```bash
docker compose up -d langfuse-web langfuse-worker rag-clickhouse langfuse-redis langfuse-minio
curl -sf localhost:3100/api/health | python3 -m json.tool
```

---

### Step 6.2: Langfuse SDK 통합

#### 생성 파일
- `backend/app/monitoring/__init__.py`
- `backend/app/monitoring/langfuse.py`

#### 구현 내용

**Langfuse 클라이언트 초기화**:
```python
from langfuse import Langfuse

class LangfuseMonitor:
    def __init__(self, settings):
        self.langfuse = Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
        )

    def create_trace(self, name: str, input: str) -> Trace:
        return self.langfuse.trace(name=name, input=input)

    def create_span(self, trace, name: str) -> Span:
        return trace.span(name=name)

    def create_generation(self, trace, name: str, model: str, input: dict) -> Generation:
        return trace.generation(name=name, model=model, input=input)

    def score(self, trace_id: str, name: str, value: float):
        self.langfuse.score(trace_id=trace_id, name=name, value=value)
```

- 비활성화 모드: Langfuse 키 미설정 시 no-op
- flush: 앱 종료 시 `langfuse.flush()`

#### TDD
```
RED:   test_langfuse_create_trace → 트레이스 생성 확인 (mock)
RED:   test_langfuse_disabled → 키 미설정 시 no-op 확인
GREEN: langfuse.py 구현
```

---

### Step 6.3: 검색 파이프라인 트레이싱

#### 수정 파일
- `backend/app/services/search/hybrid.py` (Phase 4)

#### 구현 내용

`@observe` 데코레이터 또는 수동 트레이싱으로 전체 파이프라인 기록:

```python
async def search(self, query: str, settings: RAGSettings):
    trace = self.langfuse_monitor.create_trace("rag-search", query)

    # 1. 가드레일 (입력)
    span = trace.span(name="guardrail-input")
    # ... 실행 ...
    span.end(output={"passed": True})

    # 2. HyDE
    if settings.hyde_enabled:
        span = trace.span(name="hyde")
        # ...
        span.end(output={"generated_doc": hyde_doc[:200]})

    # 3. 검색
    span = trace.span(name="hybrid-search")
    # ...
    span.end(output={"count": len(documents)})

    # 4. 리랭킹
    span = trace.span(name="reranking")
    # ...

    # 5. 답변 생성
    generation = trace.generation(
        name="answer-generation",
        model=settings.llm_model,
        input={"query": query, "doc_count": len(documents)},
    )
    # ...
    generation.end(output=answer, usage={"prompt_tokens": ..., "completion_tokens": ...})

    # 6. 할루시네이션 스코어
    trace.score(name="hallucination", value=hal_result.grounded_ratio)
    trace.update(output=answer)
```

- 각 단계의 duration은 span이 자동 계산
- 토큰 사용량: LLM 응답에서 추출
- 에러 시 span에 에러 정보 기록

#### TDD
```
RED:   test_search_creates_trace → 검색 실행 시 Langfuse 트레이스 생성 확인
RED:   test_trace_has_all_spans → 모든 파이프라인 단계 span 존재 확인
GREEN: hybrid.py 트레이싱 통합
```

---

### Step 6.4: RAGAS 평가 데이터셋 관리

#### 생성 파일
- `backend/app/services/evaluation/__init__.py`
- `backend/app/services/evaluation/ragas.py`
- `backend/app/api/evaluation.py`

#### 구현 내용

**평가 데이터셋 API**:
- `GET /api/evaluation/datasets` → 데이터셋 목록
- `POST /api/evaluation/datasets` → 데이터셋 생성 (JSON 업로드)
- `GET /api/evaluation/datasets/{id}` → 데이터셋 상세

**데이터셋 스키마**:
```json
{
  "name": "인사 규정 QA",
  "items": [
    {
      "question": "연차 신청 절차가 어떻게 되나요?",
      "ground_truth": "연차 신청은 사내 포털 > 인사 > 연차신청 메뉴에서...",
      "source_documents": ["doc_001"],
      "category": "인사"
    }
  ]
}
```

- DB 저장: evaluation_datasets 테이블 (JSONB)

#### TDD
```
RED:   test_create_dataset → 데이터셋 생성 후 조회 확인
RED:   test_list_datasets → 목록 페이징 확인
RED:   test_dataset_validation → 필수 필드 누락 시 400 에러
GREEN: evaluation.py (API), ragas.py (서비스) 구현
```

---

### Step 6.5: RAGAS 평가 실행

#### 수정 파일
- `backend/app/services/evaluation/ragas.py`
- `backend/app/api/evaluation.py`
- `backend/app/tasks/` (Celery 태스크 추가)

#### 구현 내용

**평가 실행 API**:
- `POST /api/evaluation/run` → 비동기 평가 시작 (Celery)
- `GET /api/evaluation/runs` → 실행 기록 목록
- `GET /api/evaluation/runs/{id}` → 실행 결과 상세
- `GET /api/evaluation/runs/{id1}/compare/{id2}` → 두 실행 비교

**RAGASEvaluator** (RAGAS 최신 클래스 기반 메트릭 API 사용):
```python
from ragas import evaluate
from ragas.metrics import Faithfulness, AnswerRelevancy, ContextPrecision, ContextRecall
from ragas.llms import LangchainLLMWrapper
from ragas.embeddings import LangchainEmbeddingsWrapper
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

class RAGASEvaluator:
    def __init__(self):
        # GPT-4 judge (한국어 평가 정확도)
        evaluator_llm = LangchainLLMWrapper(
            ChatOpenAI(model="gpt-4o", temperature=0)
        )
        evaluator_embeddings = LangchainEmbeddingsWrapper(
            OpenAIEmbeddings(model="text-embedding-3-small")
        )

        # 클래스 기반 메트릭 초기화 (RAGAS 0.2+ 필수)
        self.metrics = [
            Faithfulness(llm=evaluator_llm),
            AnswerRelevancy(llm=evaluator_llm, embeddings=evaluator_embeddings),
            ContextPrecision(llm=evaluator_llm),
            ContextRecall(llm=evaluator_llm),
        ]

    async def evaluate(self, dataset_id: str, run_id: str) -> EvaluationResult:
        dataset = await self.load_dataset(dataset_id)
        settings_snapshot = await self.get_current_settings()

        results = []
        for item in dataset.items:
            search_result = await self.rag_pipeline.run(item.question)
            results.append({
                "question": item.question,
                "answer": search_result.answer,
                "contexts": [d.content for d in search_result.documents],
                "ground_truth": item.ground_truth,
            })

        scores = evaluate(
            dataset=results,
            metrics=self.metrics,
        )

        return await self.save_result(run_id, dataset_id, settings_snapshot, scores)
```

**RAGAS 메트릭** (클래스 기반 — 각 메트릭에 LLM 인스턴스 주입 필수):
- `Faithfulness(llm=...)`: 답변이 문서에 근거하는 정도
- `AnswerRelevancy(llm=..., embeddings=...)`: 답변이 질문에 관련된 정도 (임베딩 필수)
- `ContextPrecision(llm=...)`: 검색 문서의 관련성 순위 정확도
- `ContextRecall(llm=...)`: 필요 정보가 검색된 비율

**한국어 대응**:
- GPT-4o judge 사용 (한국어 이해력 + 비용 효율)
- 한국어 few-shot 예제 직접 작성 (adapt() 번역 품질 문제 회피)

**Celery 태스크**:
```python
@celery_app.task
def run_evaluation_task(dataset_id: str, run_id: str):
    evaluator = RAGASEvaluator()
    asyncio.run(evaluator.evaluate(dataset_id, run_id))
```

#### TDD
```
RED:   test_evaluation_run_creates_task → 평가 실행 시 Celery 태스크 생성
RED:   test_evaluation_result_schema → 결과에 4개 메트릭 포함 확인
RED:   test_evaluation_settings_snapshot → 실행 시점 설정 스냅샷 저장
RED:   test_evaluation_compare → 두 실행 결과 비교 API 확인
GREEN: ragas.py, evaluation.py 구현
```

---

### Step 6.6: 모니터링 API

#### 생성 파일
- `backend/app/api/monitoring.py`

#### 구현 내용

- `GET /api/monitoring/stats` → 집계 통계
  ```json
  {"total_documents": 1234, "total_chunks": 8456, "today_queries": 127, "avg_response_time_ms": 2100}
  ```

- `GET /api/monitoring/traces` → Langfuse 트레이스 목록 (프록시)
  - Langfuse API를 백엔드에서 프록시하여 프론트엔드에 제공
  - 필터: 기간, 상태, 모델

- `GET /api/monitoring/traces/{id}` → 트레이스 상세
  - 각 span의 시작/종료 시간, 입출력

- `GET /api/monitoring/costs` → 비용 추적
  - 기간별 API 호출 비용 (GPT-4 평가, Claude 답변 등)
  - Langfuse의 model_costs 집계

#### TDD
```
RED:   test_monitoring_stats → 통계 API 반환 형식 확인
RED:   test_monitoring_traces_list → 트레이스 목록 반환 확인
RED:   test_monitoring_costs → 비용 추적 API 확인
GREEN: monitoring.py 구현
```

---

### Step 6.7: 이상 탐지 알림

#### 생성 파일
- `backend/app/monitoring/alerts.py`

#### 구현 내용

```python
class AlertChecker:
    async def check_hallucination_rate(self):
        # 최근 1시간 할루시네이션 스코어 평균 확인
        recent_scores = await self.langfuse_monitor.get_scores(
            name="hallucination", period="1h"
        )
        if not recent_scores:
            return
        avg = sum(s.value for s in recent_scores) / len(recent_scores)
        if avg < 0.7:
            await self.notify(f"할루시네이션 비율 증가: 최근 1시간 평균 {avg:.2f}")

    async def check_error_rate(self):
        # 최근 1시간 에러율 확인
        pass
```

- Celery Beat로 주기적 실행 (1시간 간격)
- 알림 방식: DB 기록 + 프론트엔드 대시보드 표시
  - 이메일/슬랙은 향후 확장

#### TDD
```
RED:   test_alert_triggered → 평균 0.7 미만 시 알림 생성
RED:   test_no_alert_when_normal → 정상 범위 시 알림 없음
GREEN: alerts.py 구현
```

---

### Step 6.8: 통합 테스트

#### 생성 파일
- `backend/tests/integration/test_evaluation_run.py`

#### 검증 시나리오
1. 샘플 데이터셋 생성 → 평가 실행 → 결과 확인 (4개 메트릭)
2. 설정 변경 → 재평가 → 결과 비교
3. Langfuse 트레이스 생성 확인
4. 모니터링 통계 API 동작 확인

## 생성 파일 전체 목록

| 파일 | 설명 |
|------|------|
| `backend/app/services/evaluation/__init__.py` | 패키지 |
| `backend/app/services/evaluation/ragas.py` | RAGAS 평가 서비스 |
| `backend/app/api/evaluation.py` | 평가 API |
| `backend/app/api/monitoring.py` | 모니터링 API |
| `backend/app/monitoring/__init__.py` | 패키지 |
| `backend/app/monitoring/langfuse.py` | Langfuse SDK 통합 |
| `backend/app/monitoring/alerts.py` | 이상 탐지 알림 |
| `backend/app/tasks/evaluation.py` | 평가 Celery 태스크 |
| `backend/tests/unit/test_evaluation.py` | 평가 단위 테스트 |
| `backend/tests/unit/test_monitoring.py` | 모니터링 단위 테스트 |
| `backend/tests/integration/test_evaluation_run.py` | 통합 테스트 |

## 완료 조건 (자동 검증)

```bash
make infra-up && make app-up
cd backend && pytest tests/unit/test_evaluation*.py tests/unit/test_monitoring*.py -v
curl -sf localhost:3100/api/health | python3 -m json.tool
pytest tests/integration/test_evaluation_run.py -v
```

## 인수인계 항목

Phase 8로 전달:
- Langfuse 접속 정보 (localhost:3100)
- 평가 API 엔드포인트 (/api/evaluation/*)
- 모니터링 API 엔드포인트 (/api/monitoring/*)
- RAGAS 메트릭 스키마 (faithfulness, answer_relevancy, context_precision, context_recall)
