# 백엔드 아키텍처

## 기술 스택

| 항목 | 기술 | 용도 |
|------|------|------|
| 웹 프레임워크 | FastAPI | REST API, 비동기 처리 |
| RAG 프레임워크 | Haystack 2.x | 파이프라인 조립, 컴포넌트 추상화 |
| ORM | SQLAlchemy 2.0 | PostgreSQL 모델, 설정 관리 |
| 마이그레이션 | Alembic | DB 스키마 버전 관리 |
| 작업 큐 | Celery + Redis | 문서 인덱싱 등 비동기 작업 |
| 디렉토리 감시 | watchdog | 지정 디렉토리 파일 변경 감지 |
| 형태소 분석 (대안) | kiwipiepy | ES 없이 한국어 BM25 검색 시 |
| BM25 (대안) | rank-bm25 | kiwipiepy와 조합 |
| 리랭킹 | transformers + sentence-transformers | bge-reranker-v2-m3-ko 실행 |
| 모니터링 | langfuse SDK | 트레이싱, 비용 추적 |
| 평가 | ragas | RAG 품질 메트릭 |
| 테스트 | pytest + pytest-asyncio | 단위/통합 테스트 |

## 핵심 의존성 (pyproject.toml)

```toml
[project]
name = "urstory-rag"
version = "0.1.0"
requires-python = ">=3.12"

dependencies = [
    # 웹
    "fastapi>=0.115",
    "uvicorn[standard]>=0.34",
    "python-multipart>=0.0.18",

    # RAG 프레임워크
    "haystack-ai>=2.9",
    "haystack-integrations[pgvector]",
    "haystack-integrations[elasticsearch]",

    # DB
    "sqlalchemy[asyncio]>=2.0",
    "asyncpg>=0.30",
    "alembic>=1.14",

    # 작업 큐
    "celery[redis]>=5.4",

    # 디렉토리 감시
    "watchdog>=6.0",

    # ML/NLP
    "transformers>=4.47",
    "sentence-transformers>=3.3",
    "torch>=2.5",
    "kiwipiepy>=0.18",
    "rank-bm25>=0.2",

    # LLM 클라이언트
    "openai>=1.58",
    "anthropic>=0.40",

    # 모니터링/평가
    "langfuse>=2.55",
    "ragas>=0.4",

    # 유틸리티
    "pydantic-settings>=2.7",
    "python-dotenv>=1.0",
]
```

## 계층 구조

```
┌──────────────────────────────────────┐
│            API Layer                 │
│  FastAPI 라우터 (documents, search,  │
│  settings, evaluation, monitoring)   │
└──────────────┬───────────────────────┘
               │
┌──────────────▼───────────────────────┐
│          Service Layer               │
│  비즈니스 로직, 파이프라인 조립       │
│  (chunking, embedding, search,       │
│   reranking, hyde, generation,       │
│   guardrails, evaluation, document,  │
│   watcher, multi_query, classifier,  │
│   query_expander, cascading_eval,    │
│   evidence_extractor, numeric_verify)│
└──────────────┬───────────────────────┘
               │
┌──────────────▼───────────────────────┐
│        Pipeline Layer                │
│  Haystack 파이프라인 구성            │
│  (IndexingPipeline, SearchPipeline)  │
└──────────────┬───────────────────────┘
               │
┌──────────────▼───────────────────────┐
│       Infrastructure Layer           │
│  PGVector, Elasticsearch, Redis,     │
│  Langfuse, OpenAI API (primary),     │
│  Claude API (alternative)            │
└──────────────────────────────────────┘
```

## 서비스 인터페이스 설계

각 서비스는 프로토콜(인터페이스)로 정의하여 구현체를 교체할 수 있습니다.

### EmbeddingProvider

```python
from typing import Protocol

class EmbeddingProvider(Protocol):
    async def embed_documents(self, texts: list[str]) -> list[list[float]]: ...
    async def embed_query(self, text: str) -> list[float]: ...

class OpenAIEmbedding:
    """OpenAI text-embedding-3-small (기본 제공자)"""
    def __init__(self, model: str = "text-embedding-3-small"): ...
```

### KeywordSearchEngine

```python
class KeywordSearchEngine(Protocol):
    async def index(self, doc_id: str, text: str, metadata: dict) -> None: ...
    async def search(self, query: str, top_k: int = 20) -> list[SearchResult]: ...
    async def delete(self, doc_id: str) -> None: ...

class ElasticsearchNoriEngine:
    """Elasticsearch + Nori 기반 BM25 검색"""

class KiwipieyyBM25Engine:
    """kiwipiepy + rank-bm25 기반 BM25 검색 (대안)"""
```

### Reranker

```python
class Reranker(Protocol):
    async def rerank(self, query: str, documents: list[Document], top_k: int = 5) -> list[Document]: ...

class KoreanCrossEncoder:
    """dragonkue/bge-reranker-v2-m3-ko

    sigmoid 캘리브레이션 지원 (reranker_score_mode: "calibrated"):
    - raw 점수를 sigmoid로 변환하여 0~1 확률로 정규화
    - 순위 신호(rank-based score)와 결합하여 최종 점수 산출
    - reranker_alpha 파라미터로 sigmoid/rank 비중 조절
    """
```

### LLMProvider

```python
class LLMProvider(Protocol):
    async def generate(self, prompt: str, system_prompt: str | None = None) -> str: ...

class OpenAILLM:
    """OpenAI API (기본 제공자) — gpt-4.1-mini (답변 생성, HyDE), gpt-4o (평가 Judge)"""

class ClaudeLLM:
    """Anthropic Claude (대안 제공자)"""

class OllamaLLM:
    """Ollama 로컬 LLM (대안 제공자)"""
```

## Phase 10-11 서비스 (검색 품질 튜닝)

### 검색 서비스 확장

```python
class MultiQueryGenerator:
    """services/search/multi_query.py
    원본 질문을 다양한 관점의 하위 쿼리로 분해하여 검색 커버리지 확대"""

class QuestionClassifier:
    """services/search/question_classifier.py
    질문 유형(사실형/비교형/절차형 등) 분류 → 검색 전략 분기"""

class QueryExpander:
    """services/search/query_expander.py
    동의어·관련어 확장으로 키워드 검색 재현율 향상"""

class CascadingQualityEvaluator:
    """services/search/cascading_evaluator.py
    vector → hybrid → multi_query 순으로 품질 평가하며 단계적 검색 전환"""

class DocumentScopeSelector:
    """services/search/document_scope.py
    질문에 언급된 문서/카테고리를 식별하여 검색 범위 한정"""
```

### 생성·검증 서비스 확장

```python
class EvidenceExtractor:
    """services/generation/evidence_extractor.py
    검색된 청크에서 정확한 인용 근거(문장 단위)를 추출"""

class FaithfulnessChecker:
    """services/guardrails/faithfulness.py
    생성된 답변이 검색 근거에 충실한지 검증 (할루시네이션 방지)"""

class RetrievalQualityGate:
    """services/guardrails/retrieval_gate.py
    검색 결과 품질이 임계치 미달 시 답변 거부 또는 재검색"""

class NumericVerifier:
    """services/guardrails/numeric_verifier.py
    답변 내 숫자 데이터가 원문과 일치하는지 교차 검증"""
```

### 청킹 서비스 확장

```python
class ContextualChunking:
    """services/chunking/contextual.py
    기존 청킹에 문서 전체 맥락(요약)을 각 청크 앞에 추가하는 데코레이터 패턴"""

class AutoDetectChunking:
    """services/chunking/auto_detect.py
    문서 형식(PDF/MD/TXT 등)을 자동 감지하여 최적 청킹 전략 선택"""
```

## 서비스 디렉토리 구조

```
backend/app/
├── api/
│   ├── documents.py
│   ├── search.py
│   ├── settings.py
│   ├── evaluation.py
│   ├── monitoring.py
│   ├── watcher.py
│   └── system.py
├── services/
│   ├── chunking/
│   │   ├── base.py
│   │   ├── contextual.py          # ContextualChunking
│   │   └── auto_detect.py         # AutoDetectChunking
│   ├── embedding/
│   │   └── openai.py              # OpenAIEmbedding (기본)
│   ├── search/
│   │   ├── hybrid.py
│   │   ├── multi_query.py         # MultiQueryGenerator
│   │   ├── question_classifier.py # QuestionClassifier
│   │   ├── query_expander.py      # QueryExpander
│   │   ├── cascading_evaluator.py # CascadingQualityEvaluator
│   │   └── document_scope.py      # DocumentScopeSelector
│   ├── reranking/
│   │   └── korean_cross_encoder.py
│   ├── hyde/
│   │   └── generator.py
│   ├── generation/
│   │   ├── answer.py
│   │   └── evidence_extractor.py  # EvidenceExtractor
│   ├── guardrails/
│   │   ├── input_guard.py
│   │   ├── faithfulness.py        # FaithfulnessChecker
│   │   ├── retrieval_gate.py      # RetrievalQualityGate
│   │   └── numeric_verifier.py    # NumericVerifier
│   ├── evaluation/
│   │   └── ragas.py
│   ├── document/
│   │   └── indexer.py
│   ├── watcher/
│   │   └── directory.py
│   └── llm/
│       ├── openai.py              # OpenAILLM (기본)
│       ├── claude.py              # ClaudeLLM (대안)
│       └── ollama.py              # OllamaLLM (대안)
├── models/
├── core/
└── pipelines/
```

## 비동기 작업 처리

문서 인덱싱, 재인덱싱, RAGAS 평가 같은 시간이 오래 걸리는 작업은 Celery를 통해 비동기로 처리합니다.

```python
# 문서 업로드 → 즉시 응답 + 백그라운드 인덱싱
@router.post("/documents/upload")
async def upload_document(file: UploadFile):
    doc = await save_document_metadata(file)
    index_document_task.delay(doc.id)  # Celery 태스크 큐
    return {"id": doc.id, "status": "indexing"}

# Celery 워커에서 실행
@celery_app.task
def index_document_task(doc_id: str):
    # 1. 청킹
    # 2. 임베딩 생성 → PGVector 저장
    # 3. Elasticsearch 인덱싱
    # 4. 상태 업데이트
    pass
```

## 디렉토리 감시 (Directory Watcher)

파일 업로드 외에 지정 디렉토리의 파일 변경을 감지하여 자동으로 인덱싱합니다.

```python
class DirectoryWatcher:
    """watchdog 기반 디렉토리 감시 서비스"""

    async def start(self, directories: list[str]):
        """감시 시작 — 파일 생성/수정/삭제 이벤트 처리"""
        # 1. 기존 파일 초기 스캔 (watched_files 테이블과 비교)
        # 2. watchdog Observer로 이벤트 리스닝
        # 3. 이벤트 발생 시 debounce 후 처리

    async def on_file_created_or_modified(self, path: str):
        """파일 생성/수정 시 — 해시 비교 후 인덱싱"""
        file_hash = compute_hash(path)
        existing = await get_watched_file(path)
        if existing and existing.file_hash == file_hash:
            return  # 변경 없음
        doc = await register_document(path, source="watcher")
        index_document_task.delay(doc.id)

    async def on_file_deleted(self, path: str):
        """파일 삭제 시 — 설정에 따라 인덱스에서도 제거"""
        if settings.watcher_auto_delete:
            await delete_document_by_path(path)

    async def full_scan(self, directories: list[str]):
        """전체 스캔 — 서비스 시작 시 누락분 보정"""
        for directory in directories:
            for file_path in scan_supported_files(directory):
                await self.on_file_created_or_modified(file_path)
```

### watched_files 테이블

```python
class WatchedFile(Base):
    __tablename__ = "watched_files"
    id: Mapped[UUID]
    file_path: Mapped[str]        # 감시 디렉토리 내 절대 경로
    file_hash: Mapped[str]        # SHA-256 해시 (변경 감지용)
    file_size: Mapped[int]
    document_id: Mapped[UUID]     # documents 테이블 FK
    last_synced_at: Mapped[datetime]
```

### 실행 방식

- **독립 프로세스**: `python -m app.watcher` 또는 Celery worker와 함께 기동
- **Docker**: `docker-compose.yml`에 `rag-watcher` 서비스로 추가, 감시 디렉토리를 볼륨 마운트
- **Celery Beat 대안**: watchdog 대신 주기적 폴링 방식도 지원 (네트워크 드라이브 등 inotify 미지원 환경)

## 에러 처리

```python
# 커스텀 예외
class RAGException(Exception): ...
class DocumentNotFoundError(RAGException): ...
class EmbeddingServiceError(RAGException): ...
class SearchServiceError(RAGException): ...
class GuardrailViolation(RAGException): ...

# 전역 예외 핸들러
@app.exception_handler(RAGException)
async def rag_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.error_code, "message": str(exc)}
    )
```

## 듀얼 인덱싱 전략

같은 문서 청크가 PGVector(벡터 검색)와 Elasticsearch(키워드 검색) 양쪽에 저장됩니다. `doc_id` 메타데이터로 연결합니다.

```python
class DocumentIndexer:
    async def index(self, doc_id: str, chunks: list[Chunk]):
        """PGVector와 Elasticsearch에 동시 인덱싱"""
        # 임베딩 생성
        embeddings = await self.embedding_provider.embed_documents(
            [c.text for c in chunks]
        )

        # PGVector 저장 (벡터 + 텍스트 + 메타데이터)
        await self.pg_store.write(chunks, embeddings, meta={"doc_id": doc_id})

        # Elasticsearch 인덱싱 (텍스트 + Nori 역색인)
        await self.es_store.write(chunks, meta={"doc_id": doc_id})

    async def delete(self, doc_id: str):
        """양쪽 저장소에서 삭제"""
        await self.pg_store.delete(filters={"doc_id": doc_id})
        await self.es_store.delete(filters={"doc_id": doc_id})

    async def reindex(self, doc_id: str, new_text: str):
        """문서 업데이트 시 재인덱싱"""
        await self.delete(doc_id)
        chunks = await self.chunker.chunk(new_text)
        await self.index(doc_id, chunks)
```

## 전체 재인덱싱

임베딩 모델 변경이나 청킹 전략 변경 시 모든 문서를 재처리합니다. 무중단 전환을 위해 새 인덱스를 별도 생성 후 교체합니다.

```python
class FullReindexer:
    async def reindex_all(self):
        """무중단 전체 재인덱싱"""
        # 1. 새 PGVector 테이블, 새 ES 인덱스 생성
        new_pg_table = f"chunks_{timestamp}"
        new_es_index = f"rag_documents_{timestamp}"

        # 2. 모든 문서를 새 인덱스에 인덱싱 (Celery 배치)
        for doc in await get_all_documents():
            reindex_task.delay(doc.id, new_pg_table, new_es_index)

        # 3. 완료 후 인덱스 교체
        # PGVector: 테이블명 교체
        # ES: Alias 전환
        await swap_indexes(new_pg_table, new_es_index)
```
