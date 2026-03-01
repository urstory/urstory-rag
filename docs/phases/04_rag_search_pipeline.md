# Phase 4: RAG 검색/답변 파이프라인 상세 개발 계획

## 개요

| 항목 | 내용 |
|------|------|
| Phase | 4 |
| 담당 | RAG/ML 엔지니어 |
| 의존성 | Phase 3 |
| 참조 문서 | `docs/architecture/07_rag_pipeline.md`, `docs/architecture/06_api_design.md` |

## 사전 조건

- Phase 3 완료 (문서 인덱싱 파이프라인, PGVector + ES에 문서 저장됨)
- Ollama 모델: bge-m3 (임베딩), qwen2.5:7b (HyDE/답변)
- 인프라 기동 상태

## 상세 구현 단계

### Step 4.1: 벡터 검색 서비스 (PGVector)

#### 생성 파일
- `backend/app/services/search/__init__.py`
- `backend/app/services/search/vector.py`

#### 구현 내용

```python
class VectorSearchEngine:
    async def search(self, query_embedding: list[float], top_k: int = 20) -> list[SearchResult]:
        # PGVector cosine distance 검색
        # SELECT *, embedding <=> $1 AS distance FROM chunks
        # ORDER BY distance LIMIT $2
```

- Haystack `PgvectorEmbeddingRetriever` 래핑 또는 직접 SQLAlchemy 쿼리
- 반환: SearchResult(id, content, score, meta)
- 필터링: doc_id별, 메타데이터별

#### TDD
```
RED:   test_vector_search_returns_results → 벡터 검색 결과 반환 확인
RED:   test_vector_search_top_k → top_k 제한 동작 확인
RED:   test_vector_search_score_ordering → 점수 내림차순 정렬 확인
GREEN: vector.py 구현
```

---

### Step 4.2: 키워드 검색 서비스 (Elasticsearch + Nori)

#### 생성 파일
- `backend/app/services/search/keyword_es.py`

#### 구현 내용

```python
class ElasticsearchNoriEngine:
    async def search(self, query: str, top_k: int = 20) -> list[SearchResult]:
        # Elasticsearch BM25 검색 (Nori 분석기 적용)
        # POST /rag_documents/_search
        # {"query": {"match": {"content": {"query": query, "analyzer": "korean"}}}}
```

- Haystack `ElasticsearchBM25Retriever` 래핑
- Nori 형태소 분석 자동 적용 (인덱스 템플릿)
- BM25 스코어 반환

#### TDD
```
RED:   test_keyword_search_nori → 한국어 쿼리로 검색 결과 반환 확인
RED:   test_keyword_search_morpheme → 형태소 분석 동작 확인 ("연차신청" → "연차" + "신청")
GREEN: keyword_es.py 구현
```

---

### Step 4.3: Kiwipiepy + BM25 대안 엔진

#### 생성 파일
- `backend/app/services/search/keyword_kiwi.py`

#### 구현 내용

```python
class KiwipieyyBM25Engine:
    def __init__(self):
        self.kiwi = Kiwi()
        self.bm25 = None  # rank_bm25.BM25Okapi

    def build_index(self, documents: list[str]):
        tokenized = [self._tokenize(doc) for doc in documents]
        self.bm25 = BM25Okapi(tokenized)

    def _tokenize(self, text: str) -> list[str]:
        # kiwipiepy 형태소 분석 → 명사/동사/형용사만 추출
        tokens = self.kiwi.tokenize(text)
        return [t.form for t in tokens if t.tag.startswith(('N', 'V', 'XR'))]
```

- Elasticsearch 없이 동작하는 대안
- 설정: `keyword_engine: "kiwipiepy"` 선택 시 활성화
- 인메모리 인덱스 (서버 시작 시 빌드)

#### TDD
```
RED:   test_kiwi_tokenize → 한국어 형태소 분석 결과 확인
RED:   test_kiwi_bm25_search → BM25 검색 결과 반환 확인
GREEN: keyword_kiwi.py 구현
```

---

### Step 4.4: RRF (Reciprocal Rank Fusion) 결합

#### 생성 파일
- `backend/app/services/search/rrf.py`

#### 구현 내용

```python
class RRFCombiner:
    def combine(
        self,
        vector_results: list[SearchResult],
        keyword_results: list[SearchResult],
        k: int = 60,
        vector_weight: float = 0.5,
        keyword_weight: float = 0.5,
    ) -> list[SearchResult]:
        scores = {}
        for rank, doc in enumerate(vector_results):
            scores[doc.id] = scores.get(doc.id, 0) + vector_weight / (k + rank + 1)
        for rank, doc in enumerate(keyword_results):
            scores[doc.id] = scores.get(doc.id, 0) + keyword_weight / (k + rank + 1)
        # 중복 제거 + 점수 내림차순 정렬
        return sorted(merged, key=lambda x: x.score, reverse=True)
```

- k 상수 조정 가능 (기본 60)
- vector_weight, keyword_weight로 비율 조정
- 중복 문서 제거 (동일 chunk_id 기준)

#### TDD
```
RED:   test_rrf_combine_two_lists → 두 검색 결과 결합 확인
RED:   test_rrf_dedup → 중복 문서 제거 확인
RED:   test_rrf_weight_adjustment → 가중치 변경 시 순서 변화 확인
RED:   test_rrf_constant_k → k값 변경 시 점수 계산 확인
GREEN: rrf.py 구현
```

---

### Step 4.5: 리랭킹 서비스

#### 생성 파일
- `backend/app/services/reranking/__init__.py`
- `backend/app/services/reranking/base.py`
- `backend/app/services/reranking/korean.py`

#### 구현 내용

**base.py** - Reranker Protocol:
```python
class Reranker(Protocol):
    async def rerank(self, query: str, documents: list[SearchResult], top_k: int = 5) -> list[SearchResult]: ...
```

**korean.py** - bge-reranker-v2-m3-ko:
```python
class KoreanCrossEncoder:
    def __init__(self):
        self.model = CrossEncoder("dragonkue/bge-reranker-v2-m3-ko")
        # Mac Studio: MPS 가속
        self.device = "mps" if torch.backends.mps.is_available() else "cpu"

    async def rerank(self, query: str, documents: list[SearchResult], top_k: int = 5):
        pairs = [(query, doc.content) for doc in documents]
        scores = self.model.predict(pairs)
        # 점수 기준 정렬 후 top_k 반환
```

- 모델 로드: 앱 시작 시 1회 로드, 메모리 유지 (lifespan)
- 입력: 20건 (retriever 결과), 출력: 5건 (top_k)
- **주의**: cross-encoder/ms-marco-MiniLM 사용 금지 (영어 전용)

#### TDD
```
RED:   test_reranker_protocol → Protocol 인터페이스 준수 확인
RED:   test_korean_reranker_top_k → 20건 입력 → 5건 출력 확인
RED:   test_korean_reranker_score_ordering → 점수 내림차순 정렬 확인
GREEN: base.py, korean.py 구현
```

---

### Step 4.6: HyDE (Hypothetical Document Embeddings)

#### 생성 파일
- `backend/app/services/hyde/__init__.py`
- `backend/app/services/hyde/generator.py`

#### 구현 내용

```python
class HyDEGenerator:
    PROMPT = """다음 질문에 대한 답변이 될 수 있는 문서를 한 단락으로 작성하세요.
실제 사실 여부는 중요하지 않습니다. 질문과 관련된 내용을 포함하면 됩니다.

질문: {query}

문서:"""

    async def generate(self, query: str) -> str:
        return await self.llm.generate(self.PROMPT.format(query=query))

    def should_apply(self, query: str, mode: str) -> bool:
        if mode == "all": return True
        if mode == "long_query" and len(query) > 50: return True
        if mode == "complex" and self._is_complex(query): return True
        return False
```

- ON/OFF: settings.hyde_enabled
- 모드: all(항상), long_query(긴 쿼리만), complex(복합 질문만)
- LLMProvider 의존성 주입 (Qwen2.5-7B 기본)

#### TDD
```
RED:   test_hyde_generate → 가상 문서 생성 확인 (mock LLM)
RED:   test_hyde_should_apply_all → mode="all"일 때 항상 True
RED:   test_hyde_should_apply_long_query → 50자 초과 시만 True
RED:   test_hyde_disabled → hyde_enabled=False일 때 건너뛰기 확인
GREEN: generator.py 구현
```

---

### Step 4.7: 하이브리드 검색 오케스트레이터

#### 생성 파일
- `backend/app/services/search/hybrid.py`

#### 구현 내용

전체 검색 파이프라인 조립:
```python
class HybridSearchOrchestrator:
    async def search(self, query: str, settings: RAGSettings) -> SearchPipelineResult:
        trace = PipelineTrace()

        # 1. HyDE (선택적)
        search_query = query
        if settings.hyde_enabled and self.hyde.should_apply(query, settings.hyde_apply_mode):
            hyde_doc = await self.hyde.generate(query)
            search_query = hyde_doc  # 가상 문서로 검색
            trace.add("hyde", {"generated_document": hyde_doc})

        # 2. 쿼리 임베딩
        query_embedding = await self.embedder.embed_query(search_query)

        # 3. 병렬 검색
        vector_results, keyword_results = await asyncio.gather(
            self.vector_engine.search(query_embedding, settings.retriever_top_k),
            self.keyword_engine.search(query, settings.retriever_top_k),
        )
        trace.add("vector_search", {"results_count": len(vector_results)})
        trace.add("keyword_search", {"results_count": len(keyword_results)})

        # 4. RRF 결합
        combined = self.rrf.combine(vector_results, keyword_results,
            k=settings.rrf_constant,
            vector_weight=settings.vector_weight,
            keyword_weight=settings.keyword_weight)
        trace.add("rrf_fusion", {"input_count": ..., "output_count": len(combined)})

        # 5. 리랭킹 (선택적)
        if settings.reranking_enabled:
            reranked = await self.reranker.rerank(query, combined, settings.reranker_top_k)
            trace.add("reranking", {"input_count": len(combined), "output_count": len(reranked)})
            combined = reranked

        return SearchPipelineResult(documents=combined, trace=trace)
```

- 검색 모드 분기: vector, keyword, hybrid
- vector 모드: 벡터 검색만
- keyword 모드: 키워드 검색만
- hybrid 모드: 벡터 + 키워드 + RRF

#### TDD
```
RED:   test_hybrid_search → 하이브리드 검색 결과 반환 확인
RED:   test_vector_only_mode → vector 모드에서 벡터 검색만 실행
RED:   test_keyword_only_mode → keyword 모드에서 키워드 검색만 실행
RED:   test_search_with_hyde → HyDE 적용 시 가상 문서 기반 검색
RED:   test_search_with_reranking → 리랭킹 적용 시 결과 재정렬
GREEN: hybrid.py 구현
```

---

### Step 4.8: 답변 생성 서비스

#### 수정 파일
- `backend/app/services/generation/ollama.py` (Phase 2에서 생성)

#### 생성 파일
- `backend/app/services/generation/openai.py`
- `backend/app/services/generation/claude.py`
- `backend/app/services/generation/prompts.py`

#### 구현 내용

**prompts.py** - 프롬프트 관리:
```python
SYSTEM_PROMPT = """당신은 사내 문서를 기반으로 질문에 답변하는 AI 어시스턴트입니다.
규칙:
1. 제공된 문서의 내용만을 기반으로 답변하세요.
2. 문서에 없는 내용은 "제공된 문서에서 관련 정보를 찾을 수 없습니다"라고 답변하세요.
3. 답변에 출처 문서를 명시하세요.
4. 개인정보가 포함된 내용은 마스킹하여 표시하세요."""

USER_PROMPT = """다음 문서들을 참고하여 질문에 답변하세요.

{documents}

질문: {query}

답변:"""
```

**OpenAI/Claude 구현체** - LLMProvider 인터페이스 구현:
- openai.py: OpenAI API (GPT-4 등)
- claude.py: Anthropic API (Claude Sonnet 등)

#### TDD
```
RED:   test_openai_llm_generate → OpenAI API 호출 확인 (mock)
RED:   test_claude_llm_generate → Claude API 호출 확인 (mock)
RED:   test_prompt_builder → 문서 + 쿼리로 프롬프트 조립 확인
GREEN: openai.py, claude.py, prompts.py 구현
```

---

### Step 4.9: Haystack 파이프라인 구성

#### 생성 파일
- `backend/app/pipelines/__init__.py`
- `backend/app/pipelines/search.py`

#### 구현 내용

Haystack Pipeline으로 검색 파이프라인 조립:
- 설정에 따라 동적으로 파이프라인 구성
- 컴포넌트: OllamaTextEmbedder → PgvectorEmbeddingRetriever + ElasticsearchBM25Retriever → DocumentJoiner(RRF) → TransformersSimilarityRanker → PromptBuilder → OllamaGenerator
- 설정 변경 시 파이프라인 재구성

#### TDD
```
RED:   test_build_pipeline_with_reranking → 리랭킹 포함 파이프라인 구성 확인
RED:   test_build_pipeline_without_reranking → 리랭킹 제외 파이프라인 구성 확인
GREEN: search.py 구현
```

---

### Step 4.10: 검색 API

#### 생성 파일
- `backend/app/api/search.py`

#### 구현 내용

- `POST /api/search` → 검색 + 답변 생성
- `POST /api/search/debug` → 검색 + 파이프라인 트레이스 포함

요청:
```json
{"query": "연차 신청 절차가 어떻게 되나요?", "top_k": 5, "search_mode": "hybrid", "use_hyde": true, "use_reranking": true, "generate_answer": true}
```

일반 응답:
```json
{"answer": "...", "documents": [...], "trace_id": "..."}
```

디버그 응답 (추가 필드):
```json
{"pipeline_trace": {"guardrail_input": {...}, "hyde": {...}, "vector_search": {...}, "keyword_search": {...}, "rrf_fusion": {...}, "reranking": {...}, "generation": {...}, "total_duration_ms": 2100}}
```

#### TDD
```
RED:   test_search_api → 검색 API 호출 후 answer + documents 반환 확인
RED:   test_search_debug_api → 디버그 API에서 pipeline_trace 포함 확인
RED:   test_search_with_override → 요청에서 설정 오버라이드 확인
GREEN: search.py (API) 구현
```

---

### Step 4.11: 통합 테스트

#### 생성 파일
- `backend/tests/integration/test_search_pipeline.py`

#### 검증 시나리오
1. 샘플 문서 인덱싱 → 검색 → 결과 반환 확인
2. HyDE ON/OFF 비교
3. 리랭킹 ON/OFF 비교
4. 검색 모드별 (vector/keyword/hybrid) 결과 비교
5. 디버그 API로 파이프라인 트레이스 확인

## 생성 파일 전체 목록

| 파일 | 설명 |
|------|------|
| `backend/app/services/search/__init__.py` | 패키지 |
| `backend/app/services/search/vector.py` | PGVector 벡터 검색 |
| `backend/app/services/search/keyword_es.py` | Elasticsearch + Nori BM25 |
| `backend/app/services/search/keyword_kiwi.py` | kiwipiepy + BM25 (대안) |
| `backend/app/services/search/rrf.py` | RRF 결합 |
| `backend/app/services/search/hybrid.py` | 하이브리드 검색 오케스트레이터 |
| `backend/app/services/reranking/__init__.py` | 패키지 |
| `backend/app/services/reranking/base.py` | Reranker Protocol |
| `backend/app/services/reranking/korean.py` | bge-reranker-v2-m3-ko |
| `backend/app/services/hyde/__init__.py` | 패키지 |
| `backend/app/services/hyde/generator.py` | HyDE 가상 문서 생성 |
| `backend/app/services/generation/openai.py` | OpenAI LLM |
| `backend/app/services/generation/claude.py` | Claude LLM |
| `backend/app/services/generation/prompts.py` | 프롬프트 관리 |
| `backend/app/pipelines/__init__.py` | 패키지 |
| `backend/app/pipelines/search.py` | Haystack 검색 파이프라인 |
| `backend/app/api/search.py` | 검색 API |
| `backend/tests/integration/test_search_pipeline.py` | 통합 테스트 |

## 완료 조건 (자동 검증)

```bash
cd backend && pytest tests/unit/test_search*.py tests/unit/test_reranking*.py tests/unit/test_hyde*.py tests/unit/test_rrf*.py -v
pytest tests/integration/test_search_pipeline.py -v
curl -s -X POST localhost:8000/api/search/debug \
  -H 'Content-Type: application/json' \
  -d '{"query": "테스트 검색"}' | python3 -m json.tool
```

## 인수인계 항목

Phase 5로 전달:
- 검색 파이프라인 인터페이스 (HybridSearchOrchestrator)
- 가드레일 삽입 포인트: 입력(검색 전), PII(리랭킹 후), 할루시네이션(생성 후)
- PipelineTrace 구조 (가드레일 결과 추가 가능)

Phase 6으로 전달:
- SearchPipelineResult 구조 (answer, documents, trace)
- LLMProvider 인터페이스 (RAGAS 평가 시 동일 파이프라인 사용)
- Langfuse 트레이싱 삽입 포인트
