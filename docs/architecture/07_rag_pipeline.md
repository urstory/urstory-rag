# RAG 파이프라인 상세

## 전체 파이프라인 개요

```
문서 업로드/감시                           사용자 쿼리
    │                                        │
    ▼                                        ▼
┌──────────────┐                   ┌──────────────────┐
│ 인덱싱        │                   │ 입력 가드레일      │ 프롬프트 인젝션 검사
│ 파이프라인     │                   └────────┬─────────┘
│              │                            │
│ 파일 변환     │                            ▼
│   ↓          │                   ┌──────────────────┐
│ 청킹 전략     │                   │ 질문 유형 분류      │ extraction/regulatory/explanatory
│ (recursive   │                   └────────┬─────────┘
│  semantic    │                            │
│  contextual  │                            ▼
│  auto)       │                   ┌──────────────────┐
│   ↓          │                   │ 멀티쿼리 생성       │ 구조 분해 전략
│ 컨텍스추얼    │                   └────────┬─────────┘
│ 청킹 (선택)  │                            │
│   ↓          │                            ▼
│ 임베딩 생성   │                   ┌──────────────────┐
│ (OpenAI)     │                   │ HyDE (선택)       │ 쿼리→LLM→가상 문서→임베딩
│   ↓          │                   └────────┬─────────┘
│ PGVector 저장 │                            │
│   ↓          │                   ┌────────┴─────────┐
│ ES+Nori 인덱싱│                   │                   │
└──────────────┘                   ▼                   ▼
                          ┌──────────────┐  ┌──────────────┐
                          │ 벡터 검색      │  │ 키워드 검색    │
                          │ PGVector      │  │ ES+Nori      │
                          │ Top 20        │  │ Top 20       │
                          └──────┬───────┘  └──────┬───────┘
                                 │                  │
                                 │   ┌──────────────┘
                                 │   │
                                 ▼   ▼
                          ┌──────────────────┐
                          │ 캐스캐이딩 검색    │ BM25 품질 평가→폴백
                          │ 또는 RRF 결합     │
                          └────────┬─────────┘
                                   │
                                   ▼
                          ┌──────────────────┐
                          │ 문서 스코프 선택    │ 상위 N개 문서 필터
                          └────────┬─────────┘
                                   │
                                   ▼
                          ┌──────────────────┐
                          │ 리랭킹            │ bge-reranker-v2-m3-ko
                          │ (Sigmoid 보정)    │ calibrated 점수 결합
                          └────────┬─────────┘
                                   │
                                   ▼
                          ┌──────────────────┐
                          │ 검색 품질 게이트    │ 점수 기반 품질 판정
                          └────────┬─────────┘
                                   │
                                   ▼
                          ┌──────────────────┐
                          │ PII 탐지/마스킹    │ 출력 가드레일 1
                          └────────┬─────────┘
                                   │
                                   ▼
                          ┌──────────────────┐
                          │ 답변 생성 분기      │ 규정형: CoT 근거 추출
                          │                  │ 추출형: 단답 추출
                          │                  │ 설명형: 표준 생성
                          └────────┬─────────┘
                                   │
                                   ▼
                          ┌──────────────────┐
                          │ 숫자 검증          │ 답변 수치 ↔ 컨텍스트 대조
                          └────────┬─────────┘
                                   │
                                   ▼
                          ┌──────────────────┐
                          │ 충실도 검증        │ 출력 가드레일 2
                          └────────┬─────────┘
                                   │
                                   ▼
                          ┌──────────────────┐
                          │ 할루시네이션 검증    │ 출력 가드레일 3
                          └────────┬─────────┘
                                   │
                                   ▼
                          ┌──────────────────┐
                          │ Langfuse 트레이싱   │ 전체 파이프라인 기록
                          └──────────────────┘
```

## 인덱싱 파이프라인

```
문서 업로드 (API)          디렉토리 감시 (Watcher)
    │                          │
    │  POST /api/documents     │  watchdog 이벤트
    │  /upload                 │  또는 폴링 스캔
    │                          │
    └──────────┬───────────────┘
               │
               ▼
        ┌─────────────┐
        │ documents    │  DB에 문서 등록
        │ 테이블 등록   │  source: "upload" | "watcher"
        └──────┬──────┘
               │
               ▼  Celery 비동기 태스크
┌─────────────────┐
│ 파일 변환        │  TextFileToDocument, PyPDFToDocument 등
│ (Haystack)      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 청킹 전략 선택   │  설정에 따라 분기
│                 │
│ ┌─ recursive    │  DocumentSplitter (기본)
│ ├─ semantic     │  SemanticChunker (임베딩 기반 문장 유사도)
│ ├─ contextual   │  LLM으로 청크에 문맥 추가
│ └─ auto         │  문서 구조 분석 후 자동 선택
└────────┬────────┘
         │
         ▼
┌──────────────────────────────────┐
│ 컨텍스추얼 청킹 (선택, 데코레이터) │  LLM으로 주제/섹션/키워드 접두사 추가
│ contextual_chunking_enabled      │
└────────┬─────────────────────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
┌────────┐ ┌──────────────┐
│임베딩   │ │Elasticsearch │
│생성     │ │인덱싱        │
│(OpenAI │ │(Nori 역색인)  │
│ text-  │ │              │
│embedding│ │              │
│-3-small)│ │              │
└───┬────┘ └──────────────┘
    │
    ▼
┌────────┐
│PGVector│
│저장     │
└────────┘
```

### 청킹 전략별 상세

#### 1. 재귀적 문자 분할 (기본)

```python
# Haystack DocumentSplitter
splitter = DocumentSplitter(
    split_by="sentence",
    split_length=3,        # 3문장씩
    split_overlap=1,       # 1문장 겹침
)
```

- 기본값: chunk_size=1024자, overlap=200자
- 대부분의 일반 문서에 적합
- 처리 속도가 가장 빠름

#### 2. 시맨틱 청킹

```python
# 문장 간 임베딩 유사도로 의미 단위 분할
# 유사도가 임계값 이하로 떨어지는 지점에서 분할
class SemanticChunker:
    def chunk(self, text: str) -> list[Chunk]:
        sentences = split_sentences(text)
        embeddings = embed(sentences)
        # 인접 문장 간 코사인 유사도 계산
        # 유사도 < threshold인 지점에서 분할
```

- 의미적으로 연결된 문장들을 하나의 청크로 묶음
- 임베딩 호출이 추가로 필요 (인덱싱 시간 증가)
- 기술 문서, 설명 문서에 효과적

#### 3. Contextual Retrieval

```python
# 각 청크에 문서 전체의 맥락을 LLM으로 추가
class ContextualChunker:
    def chunk(self, text: str) -> list[Chunk]:
        base_chunks = recursive_split(text)
        for chunk in base_chunks:
            context = llm.generate(
                f"다음 문서에서 이 청크의 맥락을 한 문장으로 설명하세요.\n"
                f"문서: {text[:2000]}\n청크: {chunk.text}"
            )
            chunk.text = f"{context}\n\n{chunk.text}"
```

- 각 청크에 문서 전체 맥락이 추가되어 검색 정확도 향상
- LLM 호출이 청크 수만큼 발생 (인덱싱 비용 크게 증가)
- 중요한 내부 규정, 법률 문서 등에 적합

#### 4. 자동 감지

```python
class AutoDetectChunker:
    def detect_strategy(self, doc: Document) -> str:
        # 규칙 기반 분류
        if doc.meta.get("file_type") in ["csv", "xlsx"]:
            return "recursive"  # 테이블 형태 → 행 단위 분할
        if avg_paragraph_length(doc.content) > 500:
            return "semantic"   # 긴 문단 → 시맨틱
        if has_structured_sections(doc.content):
            return "recursive"  # 섹션 구조 → 재귀적
        return "recursive"      # 기본값
```

#### 5. 컨텍스추얼 청킹 (Phase 11)

데코레이터 패턴으로 어떤 청킹 전략이든 감싸서 각 청크에 LLM 생성 문맥을 추가한다.

```python
class ContextualChunking:
    """기본 청킹 전략 위에 LLM 생성 맥락을 추가하는 데코레이터."""

    def __init__(self, llm_provider, base_strategy, max_doc_chars=2000):
        self.llm_provider = llm_provider
        self.base_strategy = base_strategy
        self.max_doc_chars = max_doc_chars

    async def chunk(self, text: str) -> list[Chunk]:
        base_chunks = await self.base_strategy.chunk(text)
        doc_prefix = text[:self.max_doc_chars]

        for chunk in base_chunks:
            # LLM이 주제/섹션/하위섹션 경로 + 검색 키워드를 생성
            context = await self.llm_provider.generate(
                CONTEXT_PROMPT.format(
                    doc_prefix=doc_prefix,
                    chunk_content=chunk.content,
                )
            )
            # 문맥을 청크 앞에 접두사로 추가
            chunk.content = f"{context}\n\n{chunk.content}"
        return base_chunks
```

LLM이 생성하는 접두사 형식:

```
장기요양 등급판정 > 인정기준 > 등급 유지 조건
키워드: 호전율, 기준점수, 재심사, 등급유지율, 우수
```

설정:

| 설정 키 | 기본값 | 설명 |
|--------|-------|------|
| `contextual_chunking_enabled` | `false` | 컨텍스추얼 청킹 활성화 |
| `contextual_chunking_model` | `gpt-4.1-mini` | 문맥 생성 LLM 모델 |
| `contextual_chunking_max_doc_chars` | `2000` | 문서 앞부분 참조 글자 수 |

## 검색 파이프라인

![검색 파이프라인 실행](../images/r05.png)

```
사용자 쿼리
    │
    ▼
[1] 입력 가드레일 ─────── 프롬프트 인젝션 검사 (LLM 기반)
    │
    ▼
[2] 질문 유형 분류 ─────── 정규식 기반 (extraction/regulatory/explanatory)
    │
    ▼
[3] 멀티쿼리 생성 ─────── 구조 분해 전략 (비교→분리, 복합→분리, 단순→규정형)
    │
    ▼
[4] HyDE (선택) ──────── 원문 쿼리에만 적용, 가상 문서 생성 → 임베딩
    │
    ▼
[5] 모드별 검색 실행 ──── hybrid | vector | keyword | cascading
    │                     × 멀티쿼리 병렬 실행
    ├── [5a] 벡터 검색 ── OpenAI text-embedding-3-small → PGVector Top 20
    ├── [5b] 키워드 검색 ─ ES+Nori BM25 Top 20
    └── [5c] 캐스캐이딩 ─ BM25 품질 평가 → 쿼리 확장 → 벡터 폴백
    │
    ▼
[6] RRF 결합 ──────────── score = Σ weight_i / (k + rank_i), 중복 제거
    │
    ▼
[7] 문서 스코프 선택 ──── 상위 N개 문서의 청크만 필터 (오참조 방지)
    │
    ▼
[8] 리랭킹 ────────────── bge-reranker-v2-m3-ko (Sigmoid 보정 + 순위 신호 결합)
    │
    ▼
[9] 검색 품질 게이트 ──── 점수 기반 품질 판정 (soft_fail → 근거 추출로 rescue)
    │
    ▼
[10] PII 탐지/마스킹 ──── 출력 가드레일 1: 개인정보 마스킹
    │
    ▼
[11] 답변 생성 분기 ───── 규정형: CoT 근거 추출 + 답변
    │                     추출형: 단답 추출
    │                     설명형: 표준 프롬프트 생성
    ▼
[12] 숫자 검증 ────────── 답변 수치 ↔ 컨텍스트 대조 (동등어 사전)
    │
    ▼
[13] 충실도 검증 ─────── 출력 가드레일 2: LLM-as-Judge 충실도 점수
    │
    ▼
[14] 할루시네이션 검증 ── 출력 가드레일 3: LLM-as-Judge 근거율
    │
    ▼
[15] Langfuse 트레이싱 ── 전체 파이프라인 기록 + 점수 스코어링
```

### 캐스캐이딩 검색 (Phase 10)

BM25 검색 결과의 품질을 평가하여, 충분하면 키워드 결과만 사용하고 불충분하면 벡터 검색으로 폴백하는 3단계 전략이다.

```
Stage 1: BM25 검색 → 품질 평가
    │
    ├── 충분 → 키워드 결과 반환 (벡터 검색 생략으로 지연 시간 절감)
    │
    └── 불충분 ──→ Stage 2: 쿼리 확장 (HyDE 키워드) → ES 재검색 → 품질 재평가
                      │
                      ├── 충분 → 확장된 키워드 결과 반환
                      │
                      └── 불충분 ──→ Stage 3: 벡터 폴백 (비대칭 RRF)
                                      벡터 가중치 0.3 + 키워드 가중치 0.7
```

```python
class CascadingQualityEvaluator:
    """BM25 결과의 품질을 평가하여 다음 단계 진행 여부를 결정."""

    def __init__(
        self,
        threshold: float = 3.0,        # BM25 최고 점수 임계값
        min_qualifying_docs: int = 3,   # 최소 적격 문서 수
        min_doc_score: float = 1.0,     # 적격 문서 최소 점수
    ):
        ...

    def evaluate(self, results: list[SearchResult]) -> CascadingEvalResult:
        top_score = results[0].score
        qualifying = [r for r in results if r.score >= self.min_doc_score]
        sufficient = (
            top_score >= self.threshold
            and len(qualifying) >= self.min_qualifying_docs
        )
        return CascadingEvalResult(sufficient=sufficient, ...)
```

설정:

| 설정 키 | 기본값 | 설명 |
|--------|-------|------|
| `cascading_bm25_threshold` | `3.0` | BM25 최고 점수 충분 임계값 |
| `cascading_min_qualifying_docs` | `3` | 최소 적격 문서 수 |
| `cascading_min_doc_score` | `1.0` | 적격 문서 최소 점수 |
| `cascading_fallback_vector_weight` | `0.3` | 벡터 폴백 시 벡터 가중치 |
| `cascading_fallback_keyword_weight` | `0.7` | 벡터 폴백 시 키워드 가중치 |

### 쿼리 확장 (Phase 10)

캐스캐이딩 Stage 2에서 BM25 검색 실패 시, LLM으로 가상 답변을 생성하고 핵심 키워드를 추출하여 ES 재검색 쿼리를 구성한다.

```python
class QueryExpander:
    """HyDE 기반 쿼리 확장.

    1. LLM으로 가상 답변 생성
    2. 가상 답변에서 핵심 키워드 추출 (한국어 명사, 고유명사, 전문 용어 우선)
    3. 원본 쿼리 + 확장 키워드로 결합하여 ES 재검색
    """

    async def expand(self, query: str, max_keywords: int = 10) -> ExpandedQuery:
        hyde_answer = await self.llm.generate(HYDE_EXPANSION_PROMPT.format(query=query))
        keywords = await self.llm.generate(
            KEYWORD_EXTRACTION_PROMPT.format(text=hyde_answer, max_keywords=max_keywords)
        )
        expanded_query = query + " " + " ".join(keywords)
        return ExpandedQuery(original_query=query, expanded_query=expanded_query, ...)
```

설정:

| 설정 키 | 기본값 | 설명 |
|--------|-------|------|
| `query_expansion_enabled` | `true` | 쿼리 확장 활성화 |
| `query_expansion_max_keywords` | `10` | 최대 추출 키워드 수 |

### 문서 스코프 선택 (Phase 10)

리랭킹 전에 청크를 문서 단위로 그룹핑하여 상위 N개 문서의 청크만 남긴다. 엉뚱한 문서에서 온 청크가 리랭킹에 포함되는 오참조 문제를 방지한다.

```python
class DocumentScopeSelector:
    """문서 단위 후보 선택기.

    1. 청크를 document_id로 그룹핑
    2. 각 문서의 대표 점수 = 해당 문서 청크 중 max score
    3. 대표 점수 기준 상위 top_n 문서만 남김
    4. 남은 문서들의 청크만 반환
    """

    def __init__(self, top_n: int = 3):
        self.top_n = top_n

    def select(self, documents: list[SearchResult]) -> list[SearchResult]:
        groups = group_by_document_id(documents)
        doc_scores = [(doc_id, max(c.score for c in chunks)) for doc_id, chunks in groups]
        top_doc_ids = top_n_by_score(doc_scores, self.top_n)
        return [d for d in documents if d.document_id in top_doc_ids]
```

설정:

| 설정 키 | 기본값 | 설명 |
|--------|-------|------|
| `document_scope_enabled` | `true` | 문서 스코프 선택 활성화 |
| `document_scope_top_n` | `3` | 선택할 상위 문서 수 |

### 하이브리드 검색 상세

#### RRF (Reciprocal Rank Fusion)

```python
# 두 검색 결과를 결합
# k = 상수 (기본 60, 관리자 UI에서 조정 가능)
def rrf_score(doc, rankings: list[dict], k: int = 60) -> float:
    score = 0
    for ranking in rankings:
        if doc.id in ranking:
            rank = ranking[doc.id]
            score += 1.0 / (k + rank)
    return score
```

#### 가중치 적용

```python
# vector_weight, keyword_weight로 비율 조정
final_score = (vector_weight * vector_rrf_score +
               keyword_weight * keyword_rrf_score)
```

### 멀티쿼리 생성 (Phase 11)

사용자 질문을 구조 분해하여 검색 커버리지를 높인다. 원문 쿼리를 항상 첫 번째로 포함하고, LLM이 변형 쿼리를 추가 생성한다.

#### 구조 분해 전략

| 질문 유형 | 분해 방식 | 예시 |
|----------|---------|------|
| 비교 질문 | 각 대상을 개별 질문으로 분리 | "A와 B의 차이" → "A란?", "B란?" |
| 복합 조건 | 각 조건을 개별 질문으로 분리 | "X이면서 Y인 경우" → "X인 경우?", "Y인 경우?" |
| 단순 질문 | 문서/규정 문장 형태로 변환 | "급여 기준은?" → "급여 지급 기준에 관한 규정" |

```python
class MultiQueryGenerator:
    """LLM 기반 멀티쿼리 생성기.

    안전장치: LLM 호출 실패/타임아웃 시 원문 쿼리만으로 폴백.
    """

    async def generate(self, query: str, count: int = 4) -> MultiQueryResult:
        prompt = MULTI_QUERY_PROMPT.format(query=query, count=count - 1)
        response = await self.llm.generate(prompt)
        variants = self._parse_variants(response)
        # 원문을 항상 첫 번째로 포함
        all_queries = [query] + [v for v in variants if v != query]
        return MultiQueryResult(original_query=query, variant_queries=all_queries[:count])
```

실행 흐름:
- 원문 쿼리: 기존 파이프라인 (HyDE/캐스캐이딩 적용)
- 변형 쿼리: 벡터+키워드 직접 검색 (HyDE/캐스캐이딩 생략)
- 모든 쿼리 병렬 실행 후 결과 합집합 + 중복 제거

설정:

| 설정 키 | 기본값 | 설명 |
|--------|-------|------|
| `multi_query_enabled` | `true` | 멀티쿼리 생성 활성화 |
| `multi_query_count` | `4` | 생성할 쿼리 수 (원문 포함) |
| `multi_query_model` | `gpt-4.1-mini` | 멀티쿼리 생성 LLM 모델 |

### 질문 유형 분류 (Phase 11)

정규식 기반으로 질문 유형을 자동 분류한다. LLM 호출 없이 동작하여 지연 시간 추가가 없다.

#### 분류 체계

| 유형 | 패턴 예시 | 답변 전략 |
|------|---------|---------|
| `extraction` | "이름은 무엇", "명칭", "기본값", "세 가지" | 문서에서 단답/목록을 그대로 추출 |
| `regulatory` | 숫자+단위 ("회", "번", "%", "원"), "몇", "빈도", "기준" | CoT 근거 추출 + 정확 인용 답변 |
| `explanatory` | 위 패턴에 해당하지 않는 경우 (기본값) | 표준 프롬프트 기반 답변 생성 |

```python
class QuestionClassifier:
    """룰 기반 질문 유형 분류기. extraction > regulatory > explanatory 우선순위."""

    EXTRACTION_PATTERNS = [
        (r"(이름|명칭|별칭)은?\s*(무엇|뭐|어떤)", "이름/명칭 질문"),
        (r"(기본\s*값|초기\s*값|디폴트)", "기본값 질문"),
        (r"(세\s*가지|네\s*가지|다섯\s*가지)", "열거 질문"),
        ...
    ]

    REGULATORY_PATTERNS = [
        (r"\d+\s*[회번개점%원]", "숫자+단위"),
        (r"(몇|얼마나?)\s*(회|번|자주|많이)", "빈도 질문"),
        (r"(매|반기|분기|월|주|일)\s*(별|마다|단위)", "주기 표현"),
        (r"(기준|조건|요건|자격|한도|제한)", "기준/조건"),
        ...
    ]

    def classify(self, query: str) -> QuestionType:
        # extraction 패턴 우선 체크 → regulatory 패턴 → explanatory 폴백
        ...
```

### 근거 추출 (Phase 11)

질문 유형에 따라 Chain-of-Thought 기반 근거 추출을 수행한다. 단일 LLM 호출로 근거 문장 추출과 답변 생성을 동시에 수행한다.

#### 규정형 (regulatory): CoT 근거 추출

```
[Step 1: 근거 추출]
문서에서 질문에 직접 답하는 문장을 1~3개 찾아 원문 그대로 복사.
문장을 바꾸거나 요약하지 않음.

[Step 2: 답변 작성]
추출한 근거 문장만을 사용하여 답변.
숫자, 기간, 횟수, 주기, 금액은 근거 문장의 표현을 글자 그대로 사용.
```

#### 추출형 (extraction): 단답 추출

```
이름, 명칭, 고유명사이면 문서에 적힌 그대로 추출.
목록이면 번호를 붙여 모두 나열. 하나도 빠뜨리지 않음.
서술하지 않고 답만 추출.
```

```python
class EvidenceExtractor:
    """CoT 기반 근거 추출 + 답변 생성 (단일 LLM 호출)."""

    async def extract_and_answer(self, query, documents) -> EvidenceResult:
        """규정형: CoT 프롬프트로 근거 추출 + 답변 생성."""
        prompt = EVIDENCE_COT_PROMPT.format(documents=docs_text, query=query)
        response = await self.llm.generate(prompt, system_prompt=EVIDENCE_COT_SYSTEM_PROMPT)
        return self._parse_response(response)  # [근거]와 [답변] 섹션 분리

    async def extract_short_answer(self, query, documents) -> EvidenceResult:
        """추출형: 단답 추출 모드."""
        prompt = EXTRACTION_PROMPT.format(documents=docs_text, query=query)
        response = await self.llm.generate(prompt, system_prompt=EXTRACTION_SYSTEM_PROMPT)
        return self._parse_response(response)
```

답변 생성 분기 로직:

```
질문 유형 분류 결과
    │
    ├── regulatory + exact_citation_enabled
    │     → CoT 근거 추출 + 답변 (실패 시 표준 생성으로 폴백)
    │
    ├── extraction
    │     → 단답 추출 모드 (실패 시 표준 생성으로 폴백)
    │
    └── explanatory
          → 표준 프롬프트 기반 답변 생성
```

### 리랭커 점수 보정 (Phase 11)

Cross-Encoder의 raw logit을 sigmoid로 확률 공간에 보정하고, 순위 신호를 결합하여 최종 점수를 산출한다.

#### Sigmoid 캘리브레이션 공식

```
ce_prob = sigmoid(logit)                    # CE logit → 0~1 확률
rank_score = 1 / (rank + 1)                 # 순위 기반 점수 (1위=1.0, 2위=0.5, ...)
final = alpha * ce_prob + (1-alpha) * rank_score  # 가중 결합
```

```python
class KoreanCrossEncoder:
    """dragonkue/bge-reranker-v2-m3-ko 기반 한국어 리랭커.

    Score Modes:
    - "calibrated": sigmoid(CE logit) + rank signal 결합 (권장)
    - "replace": 기존 동작 (raw logit으로 점수 교체)
    """

    async def rerank(self, query, documents, top_k=5, score_mode="calibrated", alpha=0.7):
        pairs = [(query, doc.content) for doc in documents]
        raw_scores = self.model.predict(pairs)

        if score_mode == "calibrated":
            # CE logit 기준 정렬하여 rank 할당
            indexed = sorted(enumerate(raw_scores), key=lambda x: x[1], reverse=True)
            for rank, (orig_idx, logit) in enumerate(indexed):
                ce_prob = sigmoid(float(logit))
                rank_score = 1.0 / (rank + 1)
                combined = alpha * ce_prob + (1.0 - alpha) * rank_score
                ...
```

설정:

| 설정 키 | 기본값 | 설명 |
|--------|-------|------|
| `reranker_score_mode` | `"calibrated"` | 점수 모드 (`calibrated` / `replace`) |
| `reranker_alpha` | `0.7` | calibrated 모드에서 CE 확률 가중치 |

### 숫자 검증 (Phase 11)

답변에 등장한 숫자/단위가 컨텍스트에도 존재하는지 룰 기반으로 검증한다. LLM 호출 없이 정규식과 동등어 사전으로 동작한다.

#### 검증 프로세스

```
답변 텍스트에서 숫자+도메인 단위 추출 (정규식)
    → "3회", "6개월", "80%" 등
    │
    ▼
컨텍스트(검색된 문서 원문)에서 동일 표현 탐색
    │
    ├── 직접 매칭 ("3회" → "3회") → 검증 통과
    ├── 정규화 매칭 (쉼표/공백 제거) → 검증 통과
    └── 동등어 매칭 ("반기" ↔ "6개월") → 검증 통과
    │
    └── 어디에도 없음 → 근거 없는 수치 (ungrounded)
```

#### 동등어 사전

| 원본 | 동등어 |
|------|-------|
| 반기 | 6개월, 반년 |
| 분기 | 3개월 |
| 연 | 1년, 12개월 |
| 월 | 30일 |

```python
class NumericVerifier:
    """답변 내 숫자/수치의 컨텍스트 존재 여부를 검증한다."""

    EQUIVALENTS = {
        "반기": ["6개월", "반년"],
        "분기": ["3개월"],
        "연": ["1년", "12개월"],
        "월": ["30일"],
        ...  # 양방향 매핑
    }

    def verify(self, answer: str, context_texts: list[str]) -> NumericVerification:
        answer_numbers = self._extract_numbers(answer)
        for num_expr in answer_numbers:
            if not self._is_grounded(num_expr, context):
                ungrounded.append(num_expr)
        return NumericVerification(passed=len(ungrounded) == 0, ...)
```

설정:

| 설정 키 | 기본값 | 설명 |
|--------|-------|------|
| `numeric_verification_enabled` | `true` | 숫자 검증 활성화 |

### HyDE 상세

```python
class HyDEGenerator:
    PROMPT = """다음 질문에 대한 답변이 될 수 있는 문서를 한 단락으로 작성하세요.
실제 사실 여부는 중요하지 않습니다. 질문과 관련된 내용을 포함하면 됩니다.

질문: {query}

문서:"""

    async def generate(self, query: str) -> str:
        hypothetical_doc = await self.llm.generate(
            self.PROMPT.format(query=query)
        )
        return hypothetical_doc  # 이 가상 문서를 임베딩해서 검색

    def should_apply(self, query: str, mode: str) -> bool:
        if mode == "all":
            return True
        if mode == "long_query" and len(query) > 50:
            return True
        if mode == "complex" and self._is_complex(query):
            return True
        return False
```

### 답변 생성 프롬프트

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

![검색 결과 및 답변](../images/r10.png)

## Haystack 파이프라인 코드 (검색)

```python
from haystack import Pipeline
from haystack.components.joiners import DocumentJoiner
from haystack.components.builders import PromptBuilder
from haystack_integrations.components.embedders.openai import OpenAITextEmbedder
from haystack_integrations.components.retrievers.pgvector import PgvectorEmbeddingRetriever
from haystack_integrations.components.retrievers.elasticsearch import ElasticsearchBM25Retriever
from haystack_integrations.components.generators.openai import OpenAIGenerator

def build_search_pipeline(settings: RAGSettings) -> Pipeline:
    pipeline = Pipeline()

    # 쿼리 임베딩 (OpenAI)
    pipeline.add_component("query_embedder", OpenAITextEmbedder(
        model=settings.embedding_model,  # text-embedding-3-small
    ))

    # 벡터 검색
    pipeline.add_component("vector_retriever", PgvectorEmbeddingRetriever(
        document_store=pg_store,
        top_k=settings.retriever_top_k,
    ))

    # 키워드 검색
    pipeline.add_component("keyword_retriever", ElasticsearchBM25Retriever(
        document_store=es_store,
        top_k=settings.retriever_top_k,
    ))

    # RRF 결합
    pipeline.add_component("joiner", DocumentJoiner(
        join_mode="reciprocal_rank_fusion",
        top_k=settings.retriever_top_k,
    ))

    # 리랭킹
    if settings.reranking_enabled:
        from haystack.components.rankers import TransformersSimilarityRanker
        pipeline.add_component("ranker", TransformersSimilarityRanker(
            model=settings.reranker_model,
            top_k=settings.reranker_top_k,
        ))

    # 프롬프트 빌더
    pipeline.add_component("prompt_builder", PromptBuilder(
        template=USER_PROMPT
    ))

    # LLM 생성 (OpenAI)
    pipeline.add_component("llm", OpenAIGenerator(
        model=settings.llm_model,  # gpt-4.1-mini
    ))

    # 연결
    pipeline.connect("query_embedder.embedding", "vector_retriever.query_embedding")
    pipeline.connect("vector_retriever", "joiner")
    pipeline.connect("keyword_retriever", "joiner")

    if settings.reranking_enabled:
        pipeline.connect("joiner", "ranker")
        pipeline.connect("ranker.documents", "prompt_builder.documents")
    else:
        pipeline.connect("joiner.documents", "prompt_builder.documents")

    pipeline.connect("prompt_builder", "llm")

    return pipeline
```

## HybridSearchOrchestrator 전체 흐름

실제 검색 파이프라인은 Haystack 파이프라인이 아닌 `HybridSearchOrchestrator` 클래스에서 직접 조립한다. 설정에 따라 각 단계를 동적으로 활성화/비활성화한다.

```python
class HybridSearchOrchestrator:
    """전체 검색 파이프라인 조립:

    [입력 가드레일] → 질문 분류 → 멀티쿼리 생성 → HyDE(선택) → 병렬 검색
    → RRF 결합 → 문서 스코프 선택 → 리랭킹(선택) → [검색 품질 게이트]
    → [출력 가드레일: PII] → 답변 생성 분기(규정형/추출형/설명형)
    → [숫자 검증] → [출력 가드레일: 충실도/할루시네이션]
    """

    def __init__(self, embedder, vector_engine, keyword_engine,
                 reranker, hyde_generator, llm, ...):
        self.embedder = embedder          # OpenAI text-embedding-3-small
        self.vector_engine = vector_engine  # PGVector
        self.keyword_engine = keyword_engine  # Elasticsearch+Nori
        self.reranker = reranker           # bge-reranker-v2-m3-ko
        self.hyde = hyde_generator          # HyDE (gpt-4.1-mini)
        self.llm = llm                     # gpt-4.1-mini
        self.rrf = RRFCombiner()
        self.query_expander = QueryExpander(llm=llm)
        self.multi_query_generator = MultiQueryGenerator(llm=llm)
        self.question_classifier = QuestionClassifier()
        self.evidence_extractor = EvidenceExtractor(llm=llm)
        self.numeric_verifier = NumericVerifier()
        self.document_scope = DocumentScopeSelector()
        # 가드레일
        self.injection_detector = PromptInjectionDetector(llm=llm)
        self.pii_detector = KoreanPIIDetector()
        self.hallucination_detector = HallucinationDetector(llm=llm)
        self.faithfulness_checker = FaithfulnessChecker(llm=llm)
        self.retrieval_gate = RetrievalQualityGate()
```

## 모델 구성 요약

| 용도 | 모델 | 공급자 |
|------|------|-------|
| 임베딩 | text-embedding-3-small | OpenAI |
| 답변 생성 | gpt-4.1-mini | OpenAI |
| HyDE / 멀티쿼리 / 쿼리 확장 | gpt-4.1-mini | OpenAI |
| 컨텍스추얼 청킹 | gpt-4.1-mini | OpenAI |
| 리랭킹 | dragonkue/bge-reranker-v2-m3-ko | 로컬 (Cross-Encoder) |
| 평가 (RAGAS Judge) | gpt-4o | OpenAI |
| 할루시네이션 검증 | gpt-4.1-mini | OpenAI |
