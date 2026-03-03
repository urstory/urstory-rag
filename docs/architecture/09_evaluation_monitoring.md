# RAGAS 평가 + Langfuse 모니터링

## RAGAS 평가

![평가 (RAGAS) 허브](../images/r08.png)

### 메트릭

| 메트릭 | 설명 | 측정 대상 |
|--------|------|-----------|
| Faithfulness | 답변이 검색된 문서에 근거하는 정도 | 할루시네이션 |
| Answer Relevancy | 답변이 질문에 관련된 정도 | 답변 품질 |
| Context Precision | 검색된 문서의 관련성 순위 정확도 | 검색 품질 |
| Context Recall | 필요한 정보가 검색된 비율 | 검색 범위 |

### 한국어 RAGAS 제한사항과 대응

| 제한사항 | 대응 |
|----------|------|
| 내부 instruction이 영어 | 평가 judge에 GPT-4o 사용 (한국어 이해력 높음) |
| adapt() few-shot 예제 번역 품질 | 한국어 few-shot 예제 직접 작성 |
| 주장 추출 정확도 낮음 | DeepEval 병행 검토 |

### 평가 워크플로

프론트엔드 관리자 UI에서 데이터셋 관리, 평가 실행, 결과 비교를 모두 수행합니다.

```
1. 평가 데이터셋 준비 (UI: 데이터셋 관리 페이지)
   ├── 한국어 QA 쌍을 JSON으로 DB에 저장
   ├── 각 항목: {question, ground_truth, source_documents[], category}
   ├── 도메인별 분류 (인사, 재무, 기술 등)
   └── UI에서 데이터셋 생성/편집/삭제

2. 평가 실행 (UI: 평가 실행 페이지)
   ├── 데이터셋 선택 후 평가 실행 요청
   ├── 현재 RAG 설정 스냅샷을 평가 실행 레코드에 저장 (재현성 보장)
   ├── 실행 상태 추적: pending → running → completed / failed
   ├── 각 질문에 대해 검색 + 생성 파이프라인 실행
   ├── RAGAS 메트릭 계산 (GPT-4o judge)
   └── 질문별 4개 메트릭 결과 DB에 저장
       (faithfulness, answer_relevancy, context_precision, context_recall)

3. 결과 비교 (UI: 비교 페이지)
   ├── 두 평가 실행을 나란히 비교 (side-by-side)
   ├── 메트릭별 차이(diff) 표시
   ├── 설정 변경 전후 비교로 튜닝 효과 검증
   └── 질문별 상세 분석
```

### 평가 데이터셋 스키마

![평가 데이터셋 관리](../images/r09.png)

데이터셋은 DB에 JSON 형태로 저장됩니다.

```json
{
  "id": "ds_001",
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

### 평가 실행 레코드

```json
{
  "id": "run_001",
  "dataset_id": "ds_001",
  "status": "completed",
  "settings_snapshot": {
    "hyde_enabled": true,
    "reranking_enabled": true,
    "reranker_model": "dragonkue/bge-reranker-v2-m3-ko",
    "llm_model": "gpt-4.1-mini",
    "embedding_model": "text-embedding-3-small",
    "top_k": 5
  },
  "metrics_summary": {
    "faithfulness": 0.85,
    "answer_relevancy": 0.78,
    "context_precision": 0.82,
    "context_recall": 0.76
  },
  "per_question_results": [
    {
      "question": "연차 신청 절차가 어떻게 되나요?",
      "faithfulness": 0.90,
      "answer_relevancy": 0.85,
      "context_precision": 0.88,
      "context_recall": 0.80
    }
  ],
  "created_at": "2026-03-03T10:00:00Z",
  "completed_at": "2026-03-03T10:15:00Z"
}
```

### RAGAS 코드

```python
from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy, context_precision, context_recall
from ragas.llms import LangchainLLMWrapper
from langchain_openai import ChatOpenAI

class RAGASEvaluator:
    def __init__(self):
        # 평가 judge는 GPT-4o 사용 (한국어 평가 정확도 높음)
        self.judge_llm = LangchainLLMWrapper(
            ChatOpenAI(model="gpt-4o", temperature=0)
        )

    async def evaluate(self, dataset_id: str, run_id: str) -> EvaluationResult:
        dataset = await self.load_dataset(dataset_id)

        # 현재 설정 스냅샷 저장 (재현성)
        settings_snapshot = await self.capture_settings()
        await self.update_run(run_id, status="running", settings=settings_snapshot)

        # 현재 설정으로 각 질문에 대해 검색+생성 실행
        results = []
        for item in dataset.items:
            search_result = await self.rag_pipeline.run(item.question)
            results.append({
                "question": item.question,
                "answer": search_result.answer,
                "contexts": [d.content for d in search_result.documents],
                "ground_truth": item.ground_truth,
            })

        # RAGAS 메트릭 계산 (GPT-4o judge)
        scores = evaluate(
            dataset=results,
            metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
            llm=self.judge_llm,
        )

        # 질문별 결과 + 전체 요약 저장
        return await self.save_result(run_id, dataset_id, scores)
```

## Langfuse 모니터링

### 배포 구성

Langfuse v3는 Web + Worker 2컨테이너 구성이며, ClickHouse + 전용 Redis + MinIO(S3)가 필요합니다. PostgreSQL은 인프라 계층의 공유 인스턴스를 사용합니다. `ENCRYPTION_KEY`(64자 hex) 환경변수가 필수입니다.

```yaml
# docker-compose.yml (앱 계층)
langfuse-web:
  image: langfuse/langfuse:3
  container_name: rag-langfuse-web
  ports:
    - "3100:3000"
  environment:
    DATABASE_URL: postgresql://admin:${POSTGRES_PASSWORD}@shared-postgres:5432/shared
    CLICKHOUSE_MIGRATION_URL: clickhouse://clickhouse:9000
    CLICKHOUSE_URL: http://clickhouse:8123
    NEXTAUTH_SECRET: ${NEXTAUTH_SECRET}
    SALT: ${SALT}
    ENCRYPTION_KEY: ${ENCRYPTION_KEY}
    NEXTAUTH_URL: http://localhost:3100
    REDIS_CONNECTION_STRING: redis://langfuse-redis:6379
    LANGFUSE_S3_ENDPOINT: http://minio:9000
  depends_on:
    - clickhouse
    - langfuse-redis
    - minio
  networks:
    - default
    - shared-infra

langfuse-worker:
  image: langfuse/langfuse:3
  container_name: rag-langfuse-worker
  command: ["node", "packages/worker/dist/index.js"]
  environment:
    DATABASE_URL: postgresql://admin:${POSTGRES_PASSWORD}@shared-postgres:5432/shared
    CLICKHOUSE_URL: http://clickhouse:8123
    REDIS_CONNECTION_STRING: redis://langfuse-redis:6379
    ENCRYPTION_KEY: ${ENCRYPTION_KEY}
  depends_on:
    - clickhouse
    - langfuse-redis
  networks:
    - default
    - shared-infra

clickhouse:
  image: clickhouse/clickhouse-server:latest
  container_name: rag-clickhouse
  volumes:
    - clickhouse_data:/var/lib/clickhouse

langfuse-redis:
  image: redis:7-alpine
  container_name: rag-langfuse-redis
  volumes:
    - langfuse_redis_data:/data

minio:
  image: minio/minio:latest
  container_name: rag-minio
  command: server /data
  volumes:
    - minio_data:/data
```

### Langfuse 의존성 및 No-op 모드

모니터링 데이터는 전적으로 Langfuse에 의존합니다. Langfuse 키(`LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`)가 설정되지 않은 경우, 트레이싱은 no-op 모드로 동작하며 모니터링 페이지에는 빈 데이터가 표시됩니다. 개발 환경에서 Langfuse 없이도 RAG 파이프라인 자체는 정상 동작합니다.

### 트레이싱 통합

모든 RAG 파이프라인 실행을 Langfuse에 기록합니다. 현재 15단계 파이프라인 구조:

```python
from langfuse import Langfuse
from langfuse.decorators import observe

langfuse = Langfuse(
    public_key=settings.langfuse_public_key,
    secret_key=settings.langfuse_secret_key,
    host=settings.langfuse_host,
)

class RAGPipelineRunner:
    @observe(name="rag-search")
    async def run(self, query: str) -> SearchResult:
        trace = langfuse.trace(name="rag-search", input=query)

        # 1. 입력 가드레일
        span = trace.span(name="guardrail-input")
        injection_check = await self.injection_detector.detect(query)
        span.end(output={"passed": not injection_check.blocked})

        # 2. 질문 분류
        span = trace.span(name="question-classification")
        classification = await self.classifier.classify(query)
        span.end(output={"type": classification.type})

        # 3. 멀티쿼리 생성
        span = trace.span(name="multi-query")
        sub_queries = await self.multi_query_generator.generate(query)
        span.end(output={"count": len(sub_queries), "queries": sub_queries})

        # 4. HyDE (가상 문서 생성)
        if self.settings.hyde_enabled:
            span = trace.span(name="hyde")
            hyde_doc = await self.hyde_generator.generate(query)
            span.end(output={"generated_doc": hyde_doc[:200]})

        # 5. 하이브리드 검색
        span = trace.span(name="hybrid-search")
        documents = await self.search(query, sub_queries)
        span.end(output={"count": len(documents)})

        # 6. 문서 범위 필터링
        span = trace.span(name="document-scope")
        documents = await self.scope_filter.filter(documents)
        span.end(output={"count": len(documents)})

        # 7. 리랭킹
        if self.settings.reranking_enabled:
            span = trace.span(name="reranking")
            documents = await self.reranker.rerank(query, documents)
            span.end(output={"count": len(documents)})

        # 8. 검색 게이트 (충분한 문서가 있는지 판단)
        span = trace.span(name="retrieval-gate")
        gate_result = await self.retrieval_gate.check(query, documents)
        span.end(output={"passed": gate_result.passed})

        # 9. PII 가드레일
        span = trace.span(name="guardrail-pii")
        pii_check = await self.pii_detector.check(documents)
        span.end(output={"pii_found": pii_check.found})

        # 10. 답변 생성
        generation = trace.generation(
            name="answer-generation",
            model=self.settings.llm_model,
            input={"query": query, "documents": [d.content for d in documents]},
        )
        answer = await self.generator.generate(query, documents)
        generation.end(output=answer)

        # 11. 근거 추출
        span = trace.span(name="evidence-extraction")
        evidence = await self.evidence_extractor.extract(answer, documents)
        span.end(output={"citations": len(evidence.citations)})

        # 12. 숫자 검증
        span = trace.span(name="numeric-verification")
        numeric_result = await self.numeric_verifier.verify(answer, documents)
        span.end(output={"verified": numeric_result.all_verified})

        # 13. 할루시네이션 감지
        span = trace.span(name="hallucination-detection")
        hal_result = await self.hallucination_detector.detect(answer, documents)
        span.end(output={"grounded_ratio": hal_result.grounded_ratio})
        trace.score(name="hallucination", value=hal_result.grounded_ratio)

        # 14. 충실도 검사
        span = trace.span(name="faithfulness-check")
        faith_result = await self.faithfulness_checker.check(answer, documents)
        span.end(output={"score": faith_result.score})
        trace.score(name="faithfulness", value=faith_result.score)

        trace.update(output=answer)
        return SearchResult(answer=answer, documents=documents, trace_id=trace.id)
```

### 트레이스 구조 (15단계)

```
rag-search
├── guardrail-input          # 프롬프트 인젝션 탐지
├── question-classification  # 질문 유형 분류
├── multi-query              # 멀티쿼리 생성
├── hyde                     # 가상 문서 생성 (HyDE)
├── hybrid-search            # 시맨틱 + 키워드 하이브리드 검색
├── document-scope           # 문서 범위 필터링
├── reranking                # 리랭킹 (bge-reranker-v2-m3-ko)
├── retrieval-gate           # 검색 충분성 판단
├── guardrail-pii            # PII 마스킹
├── answer-generation        # LLM 답변 생성 (gpt-4.1-mini)
├── evidence-extraction      # 근거 추출 및 인용
├── numeric-verification     # 숫자/수치 정확성 검증
├── hallucination-detection  # 할루시네이션 감지
└── faithfulness-check       # 충실도 최종 검사
```

### 트레이싱 대상

| 파이프라인 | trace name | 설명 |
|-----------|-----------|------|
| 검색/답변 | `rag-search` | 쿼리 → 15단계 파이프라인 (위 트레이스 구조 참조) |
| 문서 인덱싱 (업로드) | `document-index` | 업로드 → 변환 → 청킹 → 임베딩 → 듀얼 인덱싱 |
| 문서 인덱싱 (감시) | `watcher-index` | 디렉토리 감시 → 변경 감지 → 변환 → 청킹 → 임베딩 → 듀얼 인덱싱 |
| 디렉토리 스캔 | `watcher-scan` | 전체/수동 스캔 → 파일 비교 → 신규/변경/삭제 처리 |
| RAGAS 평가 | `ragas-evaluation` | 평가 데이터셋 → 검색/생성 → 메트릭 계산 |

### 모니터링 API 엔드포인트

관리자 UI에서 모니터링 데이터를 조회하기 위한 백엔드 API입니다.

| 엔드포인트 | 메서드 | 설명 | 응답 주요 필드 |
|-----------|--------|------|---------------|
| `/api/monitoring/stats` | GET | 시스템 통계 요약 | `total_documents`, `total_chunks`, `today_queries`, `avg_response_time_ms` |
| `/api/monitoring/traces` | GET | 트레이스 목록 (Langfuse REST API 프록시) | 페이징된 트레이스 목록 |
| `/api/monitoring/traces/:id` | GET | 트레이스 상세 조회 | 개별 트레이스의 전체 span 트리 |
| `/api/monitoring/costs` | GET | API 호출 비용 추적 | 기간별 비용 합산 (모델별, 용도별) |

```python
# 모니터링 라우터 예시
@router.get("/api/monitoring/stats")
async def get_stats(db: AsyncSession = Depends(get_db)):
    return {
        "total_documents": await document_repo.count(db),
        "total_chunks": await chunk_repo.count(db),
        "today_queries": await trace_service.count_today_queries(),
        "avg_response_time_ms": await trace_service.avg_response_time_today(),
    }

@router.get("/api/monitoring/traces")
async def get_traces(page: int = 1, limit: int = 20):
    """Langfuse REST API를 프록시하여 트레이스 목록 반환"""
    return await langfuse_client.get_traces(page=page, limit=limit)

@router.get("/api/monitoring/traces/{trace_id}")
async def get_trace_detail(trace_id: str):
    """개별 트레이스의 전체 span 트리 반환"""
    return await langfuse_client.get_trace(trace_id)

@router.get("/api/monitoring/costs")
async def get_costs(period: str = "7d"):
    """기간별 API 호출 비용 추적"""
    return await langfuse_client.get_costs(period=period)
```

### 모니터링 대시보드 연동

관리자 UI에서 Langfuse 데이터를 조회합니다:

```
/monitoring
├── 시스템 통계: 총 문서 수, 총 청크 수, 오늘 쿼리 수, 평균 응답 시간
├── 트레이스 목록: 최근 검색 요청의 전체 15단계 파이프라인 추적
├── 트레이스 상세: 개별 트레이스의 span 트리 및 입출력 데이터
├── 비용 추적: API 호출 비용 (GPT-4o 평가, gpt-4.1-mini 답변 생성 등)
├── 에러율: 실패한 쿼리, 가드레일 차단 비율
├── 할루시네이션 점수 분포: 답변 신뢰도 추이
└── 인덱싱 통계: 업로드/감시별 인덱싱 성공률, 처리 시간
```

### 알림 설정 (AlertChecker)

Celery Beat 주기 작업으로 Langfuse의 할루시네이션 점수를 정기적으로 확인하고, 임계값 미만일 경우 알림을 발생시킵니다.

```python
# Celery Beat 주기 작업으로 등록
class AlertChecker:
    """Langfuse에서 할루시네이션 점수를 주기적으로 확인하는 Celery Beat 태스크"""

    async def check(self):
        recent_scores = await langfuse_client.get_scores(
            name="hallucination",
            period="1h"
        )

        if not recent_scores:
            return  # 데이터 없으면 스킵

        avg = sum(s.value for s in recent_scores) / len(recent_scores)
        if avg < 0.7:
            await notify(
                f"[AlertChecker] 할루시네이션 비율 증가: "
                f"최근 1시간 평균 {avg:.2f} (임계값: 0.70)"
            )
```
