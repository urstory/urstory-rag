# RAGAS 평가 + Langfuse 모니터링

## RAGAS 평가

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
| 내부 instruction이 영어 | evaluation judge에 GPT-4 사용 (한국어 이해력 높음) |
| adapt() few-shot 예제 번역 품질 | 한국어 few-shot 예제 직접 작성 |
| 주장 추출 정확도 낮음 | DeepEval 병행 검토 |

### 평가 워크플로

```
1. 평가 데이터셋 준비
   ├── 한국어 QA 쌍 50~100개 수작업 작성
   ├── 질문 + 정답(ground truth) + 출처 문서
   └── 도메인별 분류 (인사, 재무, 기술 등)

2. 평가 실행
   ├── 현재 RAG 설정 스냅샷 저장
   ├── 각 질문에 대해 검색 + 생성 파이프라인 실행
   ├── RAGAS 메트릭 계산 (GPT-4 judge)
   └── 결과 DB + Langfuse에 저장

3. 결과 비교
   ├── 설정 변경 전후 비교
   ├── 메트릭별 추이 차트
   └── 질문별 상세 분석
```

### 평가 데이터셋 스키마

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

### RAGAS 코드

```python
from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy, context_precision, context_recall
from ragas.llms import LangchainLLMWrapper
from langchain_openai import ChatOpenAI

class RAGASEvaluator:
    def __init__(self):
        # 평가 judge는 GPT-4 사용 (정확도)
        self.judge_llm = LangchainLLMWrapper(
            ChatOpenAI(model="gpt-4", temperature=0)
        )

    async def evaluate(self, dataset_id: str) -> EvaluationResult:
        dataset = await self.load_dataset(dataset_id)

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

        # RAGAS 메트릭 계산
        scores = evaluate(
            dataset=results,
            metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
            llm=self.judge_llm,
        )

        # 결과 저장
        return await self.save_result(dataset_id, scores)
```

## Langfuse 모니터링

### 배포 구성

Langfuse v3는 ClickHouse + PostgreSQL을 사용합니다. PostgreSQL은 인프라 계층의 공유 인스턴스를 사용합니다.

```yaml
# docker-compose.yml (앱 계층)
langfuse:
  image: langfuse/langfuse:3
  container_name: rag-langfuse
  ports:
    - "3100:3000"
  environment:
    DATABASE_URL: postgresql://admin:${POSTGRES_PASSWORD}@shared-postgres:5432/shared
    CLICKHOUSE_MIGRATION_URL: clickhouse://clickhouse:9000
    CLICKHOUSE_URL: http://clickhouse:8123
    NEXTAUTH_SECRET: ${NEXTAUTH_SECRET}
    SALT: ${SALT}
    NEXTAUTH_URL: http://localhost:3100
  depends_on:
    - clickhouse
  networks:
    - default
    - shared-infra

clickhouse:
  image: clickhouse/clickhouse-server:latest
  container_name: rag-clickhouse
  volumes:
    - clickhouse_data:/var/lib/clickhouse
```

### 트레이싱 통합

모든 RAG 파이프라인 실행을 Langfuse에 기록합니다.

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

        # 1. 가드레일 (입력)
        span = trace.span(name="guardrail-input")
        injection_check = await self.injection_detector.detect(query)
        span.end(output={"passed": not injection_check.blocked})

        # 2. HyDE
        if self.settings.hyde_enabled:
            span = trace.span(name="hyde")
            hyde_doc = await self.hyde_generator.generate(query)
            span.end(output={"generated_doc": hyde_doc[:200]})

        # 3. 검색
        span = trace.span(name="hybrid-search")
        documents = await self.search(query)
        span.end(output={"count": len(documents)})

        # 4. 리랭킹
        if self.settings.reranking_enabled:
            span = trace.span(name="reranking")
            documents = await self.reranker.rerank(query, documents)
            span.end(output={"count": len(documents)})

        # 5. 생성
        generation = trace.generation(
            name="answer-generation",
            model=self.settings.llm_model,
            input={"query": query, "documents": [d.content for d in documents]},
        )
        answer = await self.generator.generate(query, documents)
        generation.end(output=answer)

        # 6. 할루시네이션 검증
        if self.settings.guardrails.hallucination_detection:
            span = trace.span(name="hallucination-check")
            hal_result = await self.hallucination_detector.verify(answer, documents)
            span.end(output={"grounded_ratio": hal_result.grounded_ratio})
            trace.score(name="hallucination", value=hal_result.grounded_ratio)

        trace.update(output=answer)
        return SearchResult(answer=answer, documents=documents, trace_id=trace.id)
```

### 트레이싱 대상

| 파이프라인 | trace name | 설명 |
|-----------|-----------|------|
| 검색/답변 | `rag-search` | 쿼리 → 가드레일 → HyDE → 검색 → 리랭킹 → 생성 → 검증 |
| 문서 인덱싱 (업로드) | `document-index` | 업로드 → 변환 → 청킹 → 임베딩 → 듀얼 인덱싱 |
| 문서 인덱싱 (감시) | `watcher-index` | 디렉토리 감시 → 변경 감지 → 변환 → 청킹 → 임베딩 → 듀얼 인덱싱 |
| 디렉토리 스캔 | `watcher-scan` | 전체/수동 스캔 → 파일 비교 → 신규/변경/삭제 처리 |
| RAGAS 평가 | `ragas-evaluation` | 평가 데이터셋 → 검색/생성 → 메트릭 계산 |

### 모니터링 대시보드 연동

관리자 UI에서 Langfuse 데이터를 조회합니다:

```
/monitoring
├── 트레이스 목록: 최근 검색 요청의 전체 파이프라인 추적
├── 성능 메트릭: 각 단계별 평균 소요시간 차트
├── 비용 추적: API 호출 비용 (GPT-4 평가, Claude 답변 생성 등)
├── 에러율: 실패한 쿼리, 가드레일 차단 비율
├── 할루시네이션 점수 분포: 답변 신뢰도 추이
└── 인덱싱 통계: 업로드/감시별 인덱싱 성공률, 처리 시간
```

### 알림 설정

```python
# 이상 감지 시 알림 (Langfuse 스코어 기반)
class AlertChecker:
    async def check(self):
        recent_scores = await langfuse.get_scores(
            name="hallucination",
            period="1h"
        )
        avg = sum(s.value for s in recent_scores) / len(recent_scores)
        if avg < 0.7:
            await notify("할루시네이션 비율 증가: 최근 1시간 평균 {avg}")
```
