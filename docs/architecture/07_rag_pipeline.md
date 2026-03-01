# RAG 파이프라인 상세

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
    ┌────┴────┐
    │         │
    ▼         ▼
┌────────┐ ┌──────────────┐
│임베딩   │ │Elasticsearch │
│생성     │ │인덱싱        │
│(bge-m3)│ │(Nori 역색인)  │
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

- 기본값: chunk_size=512자, overlap=50자
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

## 검색 파이프라인

```
사용자 쿼리
    │
    ▼
┌─────────────────────┐
│ 입력 가드레일         │  프롬프트 인젝션 검사
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│ HyDE (ON일 때)       │  쿼리 → LLM → 가상 문서 → 임베딩
│                     │  OFF일 때: 쿼리 직접 임베딩
└────────┬────────────┘
         │
    ┌────┴─────┐
    │          │
    ▼          ▼
┌────────┐ ┌──────────┐
│벡터검색 │ │키워드검색  │
│PGVector│ │ES + Nori  │
│Top 20  │ │Top 20     │
└───┬────┘ └────┬─────┘
    │           │
    └─────┬─────┘
          │
          ▼
┌─────────────────────┐
│ RRF 결합             │  score = Σ 1/(k + rank_i)
│ k=60 (기본)          │  중복 문서 제거
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│ 리랭킹               │  bge-reranker-v2-m3-ko
│ 20건 → 5건           │  Cross-encoder 점수 기반 재정렬
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│ PII 탐지             │  출력 문서에서 개인정보 마스킹
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│ 답변 생성            │  PromptBuilder + LLM
│                     │  검색된 문서 + 쿼리 → 답변
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│ 할루시네이션 검증      │  LLM-as-Judge
│                     │  답변이 문서에 근거하는지 판단
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│ Langfuse 트레이싱     │  전체 파이프라인 기록
└─────────────────────┘
```

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

## Haystack 파이프라인 코드 (검색)

```python
from haystack import Pipeline
from haystack.components.joiners import DocumentJoiner
from haystack.components.builders import PromptBuilder
from haystack_integrations.components.embedders.ollama import OllamaTextEmbedder
from haystack_integrations.components.retrievers.pgvector import PgvectorEmbeddingRetriever
from haystack_integrations.components.retrievers.elasticsearch import ElasticsearchBM25Retriever
from haystack_integrations.components.generators.ollama import OllamaGenerator

def build_search_pipeline(settings: RAGSettings) -> Pipeline:
    pipeline = Pipeline()

    # 쿼리 임베딩
    pipeline.add_component("query_embedder", OllamaTextEmbedder(
        model=settings.embedding_model,
        url=settings.ollama_url,
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

    # LLM 생성
    pipeline.add_component("llm", OllamaGenerator(
        model=settings.llm_model,
        url=settings.ollama_url,
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
