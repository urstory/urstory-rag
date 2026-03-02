# Phase 10 개발 계획: Cascading + Query Expansion 하이브리드 검색

## 개요

| 항목 | 내용 |
|------|------|
| Phase | 10 |
| 기능명 | Cascading + Query Expansion 하이브리드 검색 |
| 작성일 | 2026-03-02 |
| 상태 | 계획 |
| 담당 | RAG/ML 엔지니어 |

### 배경 및 문제 상황

**왜 이 Phase가 필요한가?**

Round 8~9 테스트에서 현재 RRF 균등 가중치(벡터 0.5 + 키워드 0.5) 방식의 한계가 확인됨:

- 키워드 전용(82.8점)이 하이브리드(82.1점)보다 소폭 우수
- 벡터 검색이 BM25의 올바른 결과를 희석 (Q13: 키워드 GOOD → 하이브리드 FAIL)
- FAIL 6건 중 5건(83%)이 검색 단계 실패 — 관련 청크를 아예 찾지 못함
- text-embedding-3-small의 한국어 품질이 ES+Nori BM25보다 낮음

### 목표

1. BM25의 높은 검색 적중률(87%)을 보존하면서 어휘 불일치 문제를 해결
2. 벡터 검색의 노이즈 주입을 방지 (BM25 결과가 충분하면 벡터 미사용)
3. BM25 실패 시 HyDE 기반 키워드 확장으로 ES 생태계 내에서 먼저 해결
4. 벡터 검색은 최후의 수단으로만 사용
5. 관리자 UI에서 cascading 관련 설정 ON/OFF 제어 가능

### 핵심 해결 방안 요약

```
[Query] → ES BM25 검색 → 품질 평가
  ├─ 충분 (top_score ≥ 임계값) → BM25 결과 그대로 사용
  └─ 불충분 → HyDE로 가상 답변 생성
              → 가상 답변에서 키워드 추출
              → 확장된 키워드로 ES 재검색
              → 여전히 불충분 → 벡터 검색 폴백 (BM25 0.7 + Vector 0.3)
→ [리랭커] → 답변 생성
```

---

## 상세 목표

1. `search_mode = "cascading"` 추가 (기존 hybrid/vector/keyword 유지)
2. BM25 결과 품질 평가 로직 (`CascadingQualityEvaluator`)
3. HyDE 기반 키워드 추출/확장 (`QueryExpander`)
4. 확장된 키워드로 ES 재검색 로직
5. 벡터 폴백 시 비대칭 RRF (keyword 0.7, vector 0.3)
6. 파이프라인 트레이스에 cascading 각 단계 기록
7. 관리자 UI 설정 페이지 업데이트
8. 기존 테스트 유지 + cascading 전용 테스트 추가

---

## 관련 유스케이스

| ID | 유스케이스 명 | 액터 | 설명 |
|----|-------------|------|------|
| UC-1 | Cascading 검색 실행 | 사용자 | 질문 입력 시 자동으로 cascading 전략 적용 |
| UC-2 | 검색 전략 설정 | 관리자 | UI에서 cascading 임계값, 가중치 등 조정 |
| UC-3 | 파이프라인 트레이스 확인 | 관리자 | 검색 결과에서 어떤 단계까지 진행되었는지 확인 |

---

## 데이터베이스 스키마

DB 변경 없음. 모든 설정은 기존 `rag_settings` JSON 컬럼에 추가 필드로 저장.

---

## API 설계

기존 API 변경 없음. `PATCH /api/settings`를 통해 새 설정값 전달.

### 새 설정 필드 (RAGSettings에 추가)

| 필드 | 타입 | 기본값 | 설명 |
|------|------|--------|------|
| `cascading_bm25_threshold` | float | 3.0 | BM25 충분 판정 기준 (ES raw score) |
| `cascading_min_qualifying_docs` | int | 3 | 최소 유효 문서 수 |
| `cascading_min_doc_score` | float | 1.0 | 유효 문서 판정 최소 점수 |
| `cascading_fallback_vector_weight` | float | 0.3 | 폴백 시 벡터 가중치 |
| `cascading_fallback_keyword_weight` | float | 0.7 | 폴백 시 키워드 가중치 |
| `query_expansion_enabled` | bool | True | HyDE 키워드 확장 ON/OFF |
| `query_expansion_max_keywords` | int | 10 | 확장 키워드 최대 개수 |

**참고**: `search_mode` 필드에 `"cascading"` 값 추가 (기존 `"hybrid"`, `"vector"`, `"keyword"` 유지).

### SettingsUpdateRequest 확장

기존 `SettingsUpdateRequest`에 위 필드들을 Optional로 추가.

### SettingsResponse 확장

기존 `SettingsResponse`에 위 필드들을 추가.

---

## 단계별 구현 계획

### Step 1: 백엔드 — 설정 모델 확장

**파일: `backend/app/config.py`**

RAGSettings에 cascading 관련 설정 추가:

```python
# Cascading + Query Expansion
cascading_bm25_threshold: float = 3.0
cascading_min_qualifying_docs: int = 3
cascading_min_doc_score: float = 1.0
cascading_fallback_vector_weight: float = 0.3
cascading_fallback_keyword_weight: float = 0.7
query_expansion_enabled: bool = True
query_expansion_max_keywords: int = 10
```

**파일: `backend/app/models/schemas.py`**

- `SettingsResponse`에 cascading 필드 추가
- `SettingsUpdateRequest`에 cascading 필드 추가 (Optional)
- `SearchRequest.search_mode`에 `"cascading"` 값 허용

**테스트: `backend/tests/unit/test_config.py`**

```python
def test_cascading_settings_defaults():
    settings = RAGSettings()
    assert settings.cascading_bm25_threshold == 3.0
    assert settings.cascading_min_qualifying_docs == 3
    assert settings.cascading_fallback_vector_weight == 0.3
    assert settings.query_expansion_enabled is True
```

### Step 2: 백엔드 — QueryExpander 구현

**파일: `backend/app/services/search/query_expander.py` (신규)**

HyDE로 가상 답변을 생성하고, 그 답변에서 핵심 키워드를 추출하여 ES 재검색 쿼리를 구성.

```python
class QueryExpander:
    """HyDE 기반 쿼리 확장.

    1. LLM으로 가상 답변 생성
    2. 가상 답변에서 핵심 키워드 추출 (LLM 또는 형태소 분석)
    3. 원본 쿼리 + 확장 키워드로 ES bool 쿼리 구성
    """

    def __init__(self, llm: LLMProvider) -> None:
        self.llm = llm

    async def expand(self, query: str, max_keywords: int = 10) -> ExpandedQuery:
        """쿼리를 확장한다.

        Returns:
            ExpandedQuery(
                original_query=query,
                hypothetical_answer=str,  # HyDE 가상 답변
                expanded_keywords=list[str],  # 추출된 키워드
                expanded_query=str,  # 원본 + 키워드 결합 쿼리
            )
        """
```

**핵심 설계**:
- 키워드 추출은 LLM에게 "다음 텍스트에서 검색에 유용한 핵심 키워드 N개를 추출하세요" 프롬프트 사용
- 확장 쿼리는 `original_query + " " + " ".join(keywords)` 형태로 ES에 전달
- ES의 match 쿼리는 기본적으로 OR 연산이므로 키워드 추가만으로 재현율 향상

**프롬프트**:

```
HYDE_EXPANSION_PROMPT = """다음 질문에 대한 답변이 될 수 있는 짧은 문단을 작성하세요.
실제 사실 여부는 중요하지 않습니다. 질문과 관련된 구체적인 용어, 수치, 고유명사를 포함하세요.

질문: {query}

답변:"""

KEYWORD_EXTRACTION_PROMPT = """다음 텍스트에서 검색에 가장 유용한 핵심 키워드를 {max_keywords}개 추출하세요.
한국어 명사, 고유명사, 전문 용어를 우선 추출하세요.
키워드만 쉼표로 구분하여 나열하세요. 다른 설명은 불필요합니다.

텍스트: {text}

키워드:"""
```

**테스트: `backend/tests/unit/test_query_expander.py` (신규)**

```python
class TestQueryExpander:
    async def test_expand_returns_keywords(self):
        """확장 쿼리에 추출된 키워드가 포함되어야 한다."""

    async def test_expand_preserves_original_query(self):
        """확장 쿼리에 원본 쿼리가 포함되어야 한다."""

    async def test_expand_respects_max_keywords(self):
        """max_keywords를 초과하지 않아야 한다."""

    async def test_expand_with_empty_response(self):
        """LLM이 빈 응답을 반환해도 원본 쿼리는 유지된다."""
```

### Step 3: 백엔드 — CascadingQualityEvaluator 구현

**파일: `backend/app/services/search/cascading_evaluator.py` (신규)**

BM25 검색 결과의 품질을 평가하여 다음 단계 진행 여부를 결정.

```python
@dataclass
class CascadingEvalResult:
    sufficient: bool
    top_score: float
    qualifying_count: int
    stage: str  # "bm25_sufficient", "expansion_sufficient", "vector_fallback"

class CascadingQualityEvaluator:
    """Cascading 품질 평가.

    BM25 raw score 기반으로 결과 충분성을 평가.
    ES BM25 score는 0~∞ 범위이며, 문서/쿼리에 따라 차이가 큼.
    """

    def __init__(
        self,
        threshold: float = 3.0,
        min_qualifying_docs: int = 3,
        min_doc_score: float = 1.0,
    ) -> None: ...

    def evaluate(self, results: list[SearchResult]) -> CascadingEvalResult: ...
```

**임계값 설계 근거** (Round 8~9 데이터 분석):
- GOOD 케이스의 BM25 top_score 중앙값: ~5.0~15.0
- FAIL 케이스의 BM25 top_score: 0.02~0.25 (매우 낮음)
- threshold=3.0이면 FAIL 케이스는 모두 "불충분"으로 판정되고, GOOD 케이스 대부분은 "충분"

**테스트: `backend/tests/unit/test_cascading_evaluator.py` (신규)**

```python
class TestCascadingQualityEvaluator:
    def test_sufficient_when_high_score(self):
        """높은 점수 + 충분한 문서 수 → sufficient=True"""

    def test_insufficient_when_low_score(self):
        """낮은 점수 → sufficient=False"""

    def test_insufficient_when_few_qualifying_docs(self):
        """유효 문서 수 부족 → sufficient=False"""

    def test_empty_results(self):
        """빈 결과 → sufficient=False"""

    def test_threshold_boundary(self):
        """임계값 경계 테스트"""
```

### Step 4: 백엔드 — HybridSearchOrchestrator에 cascading 모드 추가

**파일: `backend/app/services/search/hybrid.py`**

기존 `search()` 메서드의 모드별 검색 실행 섹션에 `elif mode == "cascading":` 분기 추가.

```python
elif mode == "cascading":
    documents, cascading_steps = await self._cascading_search(
        query, settings,
    )
    trace.extend(cascading_steps)
```

**신규 메서드: `_cascading_search()`**

```python
async def _cascading_search(
    self,
    query: str,
    settings: RAGSettings,
) -> tuple[list[SearchResult], list[PipelineStep]]:
    """Cascading + Query Expansion 검색.

    단계:
    1. BM25 검색 → 품질 평가
    2. 불충분 시 → HyDE 키워드 확장 → ES 재검색 → 품질 재평가
    3. 여전히 불충분 → 벡터 폴백 (BM25 0.7 + Vector 0.3 RRF)
    """
    steps: list[PipelineStep] = []
    evaluator = CascadingQualityEvaluator(
        threshold=settings.cascading_bm25_threshold,
        min_qualifying_docs=settings.cascading_min_qualifying_docs,
        min_doc_score=settings.cascading_min_doc_score,
    )

    # Stage 1: BM25 검색
    kw_docs, kw_step = await self._keyword_search(query, settings)
    steps.append(kw_step)

    eval_result = evaluator.evaluate(kw_docs)
    steps.append(PipelineStep(
        name="cascading_eval_stage1",
        passed=eval_result.sufficient,
        duration_ms=...,
        detail={"top_score": eval_result.top_score, "qualifying": eval_result.qualifying_count},
    ))

    if eval_result.sufficient:
        return kw_docs, steps

    # Stage 2: Query Expansion (HyDE 키워드 확장)
    if settings.query_expansion_enabled:
        expanded = await self.query_expander.expand(
            query, max_keywords=settings.query_expansion_max_keywords,
        )
        steps.append(PipelineStep(
            name="query_expansion",
            passed=True,
            duration_ms=...,
            detail={"keywords": expanded.expanded_keywords},
        ))

        # 확장된 쿼리로 ES 재검색
        expanded_docs, expanded_step = await self._keyword_search(
            expanded.expanded_query, settings,
        )
        expanded_step.name = "keyword_search_expanded"
        steps.append(expanded_step)

        eval_result2 = evaluator.evaluate(expanded_docs)
        steps.append(PipelineStep(
            name="cascading_eval_stage2",
            passed=eval_result2.sufficient,
            duration_ms=...,
            detail={"top_score": eval_result2.top_score, "qualifying": eval_result2.qualifying_count},
        ))

        if eval_result2.sufficient:
            return expanded_docs, steps

    # Stage 3: 벡터 폴백
    vec_docs, vec_step, kw_docs2, kw_step2 = await self._hybrid_search(
        query, query, settings,
    )
    steps.append(vec_step)
    steps.append(kw_step2)

    # 비대칭 RRF 결합 (BM25 우세)
    documents = self.rrf.combine(
        vec_docs, kw_docs2,
        k=settings.rrf_constant,
        vector_weight=settings.cascading_fallback_vector_weight,
        keyword_weight=settings.cascading_fallback_keyword_weight,
    )
    steps.append(PipelineStep(
        name="cascading_vector_fallback",
        passed=True,
        duration_ms=...,
        results_count=len(documents),
    ))

    return documents, steps
```

**HybridSearchOrchestrator.__init__에 QueryExpander 추가**:

```python
def __init__(self, ..., query_expander: QueryExpander | None = None) -> None:
    ...
    self.query_expander = query_expander or QueryExpander(llm=llm)
```

**테스트: `backend/tests/unit/test_cascading_search.py` (신규)**

```python
class TestCascadingSearch:
    async def test_bm25_sufficient_no_fallback(self):
        """BM25 결과가 충분하면 벡터 검색/확장 없이 반환."""

    async def test_bm25_insufficient_triggers_expansion(self):
        """BM25 불충분 → 쿼리 확장 → ES 재검색 실행."""

    async def test_expansion_sufficient_no_vector_fallback(self):
        """확장 재검색이 충분하면 벡터 폴백 없이 반환."""

    async def test_all_stages_to_vector_fallback(self):
        """BM25 + 확장 모두 불충분 → 벡터 폴백 실행."""

    async def test_expansion_disabled_skips_to_vector(self):
        """query_expansion_enabled=False → 바로 벡터 폴백."""

    async def test_cascading_trace_records_all_stages(self):
        """트레이스에 cascading 각 단계가 모두 기록되어야 한다."""

    async def test_cascading_with_reranking(self):
        """cascading 결과도 리랭커를 거쳐야 한다."""

    async def test_cascading_fallback_uses_asymmetric_weights(self):
        """폴백 시 keyword 0.7 + vector 0.3 가중치 적용."""
```

### Step 5: 백엔드 — 기존 테스트 호환성 유지

기존 `test_hybrid_search.py`의 모든 테스트가 그대로 통과해야 함.

- `search_mode="hybrid"`, `"vector"`, `"keyword"` 동작은 변경 없음
- cascading 관련 코드는 `mode == "cascading"` 분기에서만 실행
- 기존 `RAGSettings` 기본값은 변경 없음 (`search_mode="hybrid"`)

### Step 6: 프론트엔드 — 검색 설정 폼 업데이트

**파일: `frontend/src/components/settings/search-form.tsx`**

- 검색 모드 셀렉트에 `"cascading"` 옵션 추가: "캐스케이딩 (BM25 우선)"
- cascading 모드 선택 시 추가 설정 패널 표시:
  - BM25 충분 판정 임계값 (slider: 0.5~10.0, default: 3.0)
  - 최소 유효 문서 수 (input: 1~10, default: 3)
  - 쿼리 확장 ON/OFF (switch)
  - 확장 키워드 최대 개수 (input: 3~20, default: 10)
  - 폴백 벡터 가중치 (slider: 0~0.5, default: 0.3)
  - 폴백 키워드 가중치 (slider: 0.5~1.0, default: 0.7)
- 기존 hybrid 모드 설정(vector_weight, keyword_weight, rrf_constant)은 hybrid 모드에서만 표시

**파일: `frontend/src/components/settings/search-form.tsx` 스키마 확장**

```typescript
const searchSchema = z.object({
  mode: z.enum(["hybrid", "vector", "keyword", "cascading"]),
  keyword_engine: z.string(),
  rrf_constant: z.number().min(1).max(200),
  vector_weight: z.number().min(0).max(1),
  keyword_weight: z.number().min(0).max(1),
  // Cascading 전용
  cascading_bm25_threshold: z.number().min(0.5).max(10).optional(),
  cascading_min_qualifying_docs: z.number().min(1).max(10).optional(),
  cascading_min_doc_score: z.number().min(0.1).max(5).optional(),
  cascading_fallback_vector_weight: z.number().min(0).max(0.5).optional(),
  cascading_fallback_keyword_weight: z.number().min(0.5).max(1).optional(),
  query_expansion_enabled: z.boolean().optional(),
  query_expansion_max_keywords: z.number().min(3).max(20).optional(),
});
```

**파일: `frontend/src/components/search/pipeline-trace.tsx`**

- cascading 관련 트레이스 스텝 표시 지원:
  - `cascading_eval_stage1`: "BM25 품질 평가"
  - `query_expansion`: "쿼리 확장"
  - `keyword_search_expanded`: "확장 키워드 재검색"
  - `cascading_eval_stage2`: "확장 결과 품질 평가"
  - `cascading_vector_fallback`: "벡터 폴백"

---

## TDD 구현 전략

### RED 단계 (테스트 먼저)

1. `test_config.py`에 cascading 설정 기본값 테스트 추가
2. `test_query_expander.py` 신규 작성 (QueryExpander 단위 테스트)
3. `test_cascading_evaluator.py` 신규 작성 (CascadingQualityEvaluator 단위 테스트)
4. `test_cascading_search.py` 신규 작성 (cascading 통합 테스트)

### GREEN 단계 (구현)

1. `config.py` — RAGSettings 확장
2. `schemas.py` — SettingsResponse/UpdateRequest 확장
3. `query_expander.py` — QueryExpander 구현
4. `cascading_evaluator.py` — CascadingQualityEvaluator 구현
5. `hybrid.py` — `_cascading_search()` 추가

### REFACTOR 단계

1. 기존 `retrieval_gate.py`와 `cascading_evaluator.py` 간 중복 제거 검토
2. 프롬프트 상수를 `prompts.py`로 통합 검토

---

## 테스트 시나리오

### 단위 테스트

| 테스트 파일 | 테스트 수 | 대상 |
|------------|----------|------|
| `test_config.py` | +4 | cascading 설정 기본값/유효성 |
| `test_query_expander.py` | +5 | 키워드 추출, 쿼리 확장 |
| `test_cascading_evaluator.py` | +5 | 품질 평가 로직 |
| `test_cascading_search.py` | +8 | 전체 cascading 파이프라인 |
| `test_settings_api.py` | +2 | 설정 API cascading 필드 |

### 통합 테스트 (수동)

- Round 10 품질 테스트: `test_files/run_quality_test.py`로 60개 Q&A 검증
  - 목표: Judge 평균 85+ (현재 82.1), FAIL 4건 이하 (현재 6건)
  - search_mode="cascading"으로 설정 후 실행

---

## 의존성

| 의존 대상 | 유형 | 설명 |
|----------|------|------|
| `ElasticsearchNoriEngine` | 기존 코드 | BM25 검색 호출 (변경 없음) |
| `VectorSearchEngine` | 기존 코드 | 벡터 검색 호출 (변경 없음) |
| `HyDEGenerator` 또는 `LLMProvider` | 기존 코드 | 가상 답변 생성 (재사용) |
| `RRFCombiner` | 기존 코드 | 폴백 시 결합 (변경 없음) |
| `Reranker` | 기존 코드 | 최종 리랭킹 (변경 없음) |

---

## 예상 이슈 및 해결 방안

| 이슈 | 해결 방안 |
|------|----------|
| BM25 임계값(3.0)이 문서/쿼리에 따라 변동 큼 | Round 10 테스트에서 실험적으로 조정. 관리자 UI에서 실시간 조정 가능하게 설계 |
| HyDE가 환각 키워드를 생성할 수 있음 | 원본 쿼리와 결합하므로 ES의 OR 연산으로 자연스럽게 상쇄. 심각하면 키워드 필터링 추가 |
| 폴백 시 레이턴시 증가 (BM25 + HyDE LLM + ES재검색 + 임베딩 + 벡터검색) | 대부분(87%) BM25 한 번으로 해결. 폴백은 13% 케이스에서만 발생 |
| 기존 hybrid 모드와의 혼동 | UI에서 모드별 설명 텍스트 표시. cascading은 "BM25 우선 + 자동 폴백" |
| QueryExpander의 LLM 호출 비용 | 폴백 시에만 호출 (전체의 ~13%). HyDE와 동일 모델(gpt-4.1-mini) 사용 |

---

## 파일 변경 요약

### 신규 파일

| 파일 | 설명 |
|------|------|
| `backend/app/services/search/query_expander.py` | HyDE 기반 쿼리 확장 |
| `backend/app/services/search/cascading_evaluator.py` | Cascading 품질 평가 |
| `backend/tests/unit/test_query_expander.py` | QueryExpander 단위 테스트 |
| `backend/tests/unit/test_cascading_evaluator.py` | CascadingQualityEvaluator 단위 테스트 |
| `backend/tests/unit/test_cascading_search.py` | Cascading 검색 통합 테스트 |

### 수정 파일

| 파일 | 변경 내용 |
|------|----------|
| `backend/app/config.py` | RAGSettings에 cascading 설정 추가 |
| `backend/app/models/schemas.py` | SettingsResponse/UpdateRequest 확장 |
| `backend/app/services/search/hybrid.py` | `_cascading_search()` 메서드 추가 |
| `backend/tests/unit/test_config.py` | cascading 설정 테스트 추가 |
| `backend/tests/unit/test_settings_api.py` | 설정 API cascading 테스트 추가 |
| `frontend/src/components/settings/search-form.tsx` | cascading 설정 UI |
| `frontend/src/components/search/pipeline-trace.tsx` | cascading 트레이스 표시 |

---

## 다음 단계

1. Phase 10 구현 완료 후 Round 10 품질 테스트 수행
2. 임계값 튜닝 (cascading_bm25_threshold, min_qualifying_docs 등)
3. 결과를 `docs/rag_tuning_log.md`에 Round 10으로 기록
4. 필요시 CRAG(LLM 기반 관련성 판단)으로 업그레이드 검토
