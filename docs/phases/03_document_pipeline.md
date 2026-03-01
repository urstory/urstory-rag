# Phase 3: 문서 수집/파싱 파이프라인 상세 개발 계획

## 개요

| 항목 | 내용 |
|------|------|
| Phase | 3 |
| 담당 | RAG/ML 엔지니어 |
| 의존성 | Phase 2 |
| 참조 문서 | `docs/architecture/04_backend.md`, `docs/architecture/07_rag_pipeline.md` |

## 사전 조건

- Phase 2 완료 (FastAPI 앱, SQLAlchemy 모델, EmbeddingProvider, 설정 시스템)
- 인프라 기동 (PostgreSQL + PGVector, Elasticsearch + Nori)
- Ollama bge-m3 모델 로드

## 상세 구현 단계

### Step 3.1: 파일 변환 서비스 (Converter)

#### 생성 파일
- `backend/app/services/document/__init__.py`
- `backend/app/services/document/converter.py`

#### 구현 내용
- 지원 형식: PDF, DOCX, TXT, Markdown
- Haystack 컨버터 활용:
  - `PyPDFToDocument` (PDF)
  - `DOCXToDocument` (DOCX, python-docx)
  - `TextFileToDocument` (TXT)
  - `MarkdownToDocument` (Markdown)
- 파일 타입 자동 감지 (확장자 + MIME type)
- 변환 결과: `Document(content=str, meta={"filename", "file_type", "file_size"})`

#### TDD
```
RED:   test_convert_txt → TXT 파일 변환 후 content 추출 확인
RED:   test_convert_pdf → PDF 파일 변환 확인 (테스트 fixture PDF 사용)
RED:   test_convert_unsupported_type → 미지원 형식 시 예외 발생 확인
GREEN: converter.py 구현
```

---

### Step 3.2: 청킹 전략 구현

#### 생성 파일
- `backend/app/services/chunking/__init__.py`
- `backend/app/services/chunking/base.py`
- `backend/app/services/chunking/recursive.py`
- `backend/app/services/chunking/semantic.py`
- `backend/app/services/chunking/contextual.py`
- `backend/app/services/chunking/auto_detect.py`

#### 구현 내용

**base.py** - ChunkingStrategy 인터페이스:
```python
class ChunkingStrategy(Protocol):
    async def chunk(self, text: str, meta: dict | None = None) -> list[Chunk]: ...

@dataclass
class Chunk:
    content: str
    chunk_index: int
    metadata: dict
```

**recursive.py** - 재귀적 문자 분할 (기본):
- Haystack `DocumentSplitter` 래핑
- 설정: chunk_size(기본 512자), chunk_overlap(기본 50자)
- `split_by="sentence"`, `split_length=3`, `split_overlap=1`

**semantic.py** - 시맨틱 청킹:
- 문장 분리 → 문장별 임베딩 → 인접 문장 코사인 유사도 계산
- 유사도가 threshold(기본 0.5) 이하로 떨어지는 지점에서 분할
- EmbeddingProvider 의존성 주입

**contextual.py** - Contextual Retrieval:
- 기본 재귀적 청킹 수행
- 각 청크에 대해 LLM 호출: 문서 전체 맥락에서 이 청크의 위치/의미 요약
- 요약 문장을 청크 앞에 추가
- LLMProvider 의존성 주입

**auto_detect.py** - 자동 감지:
- 파일 타입, 평균 문단 길이, 섹션 구조 분석
- 규칙 기반으로 전략 선택

#### TDD
```
RED:   test_recursive_chunking → 긴 텍스트를 청크로 분할 확인
RED:   test_recursive_chunk_overlap → 청크 간 겹침 영역 존재 확인
RED:   test_semantic_chunking → 의미 단위 분할 확인 (mock 임베딩)
RED:   test_contextual_chunking → 문맥 추가된 청크 확인 (mock LLM)
RED:   test_auto_detect_strategy → 파일 타입별 전략 선택 확인
GREEN: 각 전략 구현
```

---

### Step 3.3: 듀얼 인덱서 (PGVector + Elasticsearch)

#### 생성 파일
- `backend/app/services/document/indexer.py`

#### 구현 내용

**DocumentIndexer 클래스**:

```python
class DocumentIndexer:
    def __init__(self, embedding_provider, pg_store, es_store): ...

    async def index(self, doc_id: str, chunks: list[Chunk]):
        # 1. 임베딩 생성 (배치)
        embeddings = await self.embedding_provider.embed_documents(
            [c.content for c in chunks]
        )
        # 2. PGVector 저장 (벡터 + 텍스트 + 메타데이터)
        await self.pg_store.write(chunks, embeddings, meta={"doc_id": doc_id})
        # 3. Elasticsearch 인덱싱 (텍스트 + Nori 역색인)
        await self.es_store.write(chunks, meta={"doc_id": doc_id})

    async def delete(self, doc_id: str):
        await self.pg_store.delete(filters={"doc_id": doc_id})
        await self.es_store.delete(filters={"doc_id": doc_id})
```

PGVector 스토어:
- Haystack `PgvectorDocumentStore` 또는 직접 SQLAlchemy로 chunks 테이블에 저장
- Vector(1024) 차원 (bge-m3)

Elasticsearch 스토어:
- Haystack `ElasticsearchDocumentStore`
- 인덱스명: `rag_documents` (rag_* 패턴으로 Nori 템플릿 자동 적용)
- 문서 ID = chunk UUID, meta에 doc_id 포함

#### TDD
```
RED:   test_index_document → 인덱싱 후 PGVector와 ES 양쪽에 저장 확인
RED:   test_delete_document → 삭제 후 양쪽에서 제거 확인
RED:   test_index_with_embeddings → 임베딩 차원(1024) 확인
GREEN: indexer.py 구현
```

---

### Step 3.4: 문서 처리 오케스트레이터

#### 생성 파일
- `backend/app/services/document/processor.py`

#### 구현 내용

전체 파이프라인 조립:
```python
class DocumentProcessor:
    async def process(self, doc_id: str, file_path: str):
        # 1. 파일 변환
        document = await self.converter.convert(file_path)
        # 2. 청킹 전략 선택 (설정에서)
        strategy = self.get_chunking_strategy(settings.chunking_strategy)
        # 3. 청킹
        chunks = await strategy.chunk(document.content, document.meta)
        # 4. 듀얼 인덱싱
        await self.indexer.index(doc_id, chunks)
        # 5. DB 상태 업데이트
        await self.update_document_status(doc_id, "indexed", len(chunks))
```

#### TDD
```
RED:   test_process_document_full → 파일 → 변환 → 청킹 → 인덱싱 전체 흐름 (mock)
RED:   test_process_updates_status → 처리 완료 후 document.status="indexed" 확인
RED:   test_process_failure_sets_failed → 에러 시 document.status="failed" 확인
GREEN: processor.py 구현
```

---

### Step 3.5: Celery 비동기 인덱싱 태스크

#### 생성 파일
- `backend/app/worker.py`
- `backend/app/tasks/indexing.py`

#### 구현 내용

**worker.py**: Celery 앱 초기화
```python
from celery import Celery
celery_app = Celery("rag", broker=settings.redis_url)
```

**indexing.py**: 비동기 태스크
```python
@celery_app.task(bind=True, max_retries=3)
def index_document_task(self, doc_id: str):
    processor = DocumentProcessor(...)
    try:
        # doc_id로 DB 조회하여 저장 경로 복원
        file_path = asyncio.run(get_document_file_path(doc_id))
        asyncio.run(processor.process(doc_id, file_path))
    except Exception as exc:
        self.retry(exc=exc, countdown=60)

async def get_document_file_path(doc_id: str) -> str:
    """documents 테이블에서 doc_id로 파일 저장 경로를 조회한다."""
    async with async_session_factory() as session:
        doc = await session.get(Document, doc_id)
        if not doc:
            raise DocumentNotFoundError(f"Document {doc_id} not found")
        return doc.file_path  # uploads/ 디렉토리 내 경로
```

- 재시도 로직: 최대 3회, 60초 간격
- 진행률 추적: tasks 테이블에 progress 업데이트

#### TDD
```
RED:   test_index_task_queued → 태스크가 큐에 등록되는지 확인
RED:   test_index_task_retry_on_failure → 실패 시 재시도 확인
GREEN: worker.py, indexing.py 구현
```

---

### Step 3.6: 문서 CRUD API

#### 생성 파일
- `backend/app/api/documents.py`

#### 구현 내용

엔드포인트:
- `GET /api/documents` → 문서 목록 (페이징: page, size, sort, order)
- `POST /api/documents/upload` → 파일 업로드 (multipart/form-data) → 즉시 응답 + Celery 비동기 인덱싱
- `GET /api/documents/{id}` → 문서 상세 (메타데이터 + 상태 + 청크 수)
- `DELETE /api/documents/{id}` → 문서 삭제 (DB + PGVector + Elasticsearch)
- `POST /api/documents/{id}/reindex` → 단일 문서 재인덱싱
- `GET /api/documents/{id}/chunks` → 청크 목록

업로드 흐름:
1. 파일 저장 (uploads/ 디렉토리)
2. documents 테이블에 메타데이터 저장 (status: "uploaded")
3. `index_document_task.delay(doc_id)` → Celery 큐
4. 즉시 응답: `{"id": doc_id, "status": "indexing"}`

응답 스키마:
```json
{
  "items": [...],
  "total": 150,
  "page": 1,
  "size": 20,
  "pages": 8
}
```

#### TDD
```
RED:   test_upload_document → 파일 업로드 후 201 + doc_id 반환 확인
RED:   test_list_documents_pagination → 페이징 파라미터 동작 확인
RED:   test_get_document_detail → 문서 상세 조회 확인
RED:   test_delete_document → 삭제 후 404 확인
RED:   test_get_document_chunks → 청크 목록 반환 확인
GREEN: documents.py 구현
```

---

### Step 3.7: 디렉토리 감시 서비스 (Directory Watcher)

#### 생성 파일
- `backend/app/services/watcher/__init__.py`
- `backend/app/services/watcher/handler.py`
- `backend/app/services/watcher/scanner.py`
- `backend/app/services/document/watcher.py`
- `backend/app/api/watcher.py`
- `backend/app/tasks/watcher.py`

#### 구현 내용

**handler.py** - watchdog 이벤트 핸들러:
```python
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer
from watchdog.observers.polling import PollingObserver

class DocumentFileHandler(FileSystemEventHandler):
    """지원 파일(PDF, DOCX, TXT, MD) 변경 이벤트 처리"""

    SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}

    def on_created(self, event):
        if self._is_supported(event.src_path):
            self._debounce_process(event.src_path, "created")

    def on_modified(self, event):
        if self._is_supported(event.src_path):
            self._debounce_process(event.src_path, "modified")

    def on_deleted(self, event):
        if self._is_supported(event.src_path):
            self._handle_deleted(event.src_path)

    def _is_supported(self, path: str) -> bool:
        return Path(path).suffix.lower() in self.SUPPORTED_EXTENSIONS

    def _debounce_process(self, path: str, event_type: str):
        """짧은 시간 내 중복 이벤트 무시 (1초 debounce)"""
        sync_watched_file_task.delay(path, event_type)

    def _handle_deleted(self, path: str):
        if settings.watcher_auto_delete:
            delete_watched_file_task.delay(path)
```

**scanner.py** - 전체/부분 스캔:
```python
class DirectoryScanner:
    """감시 디렉토리 전체 스캔 — 누락분 보정용"""

    async def full_scan(self, directories: list[str]) -> ScanResult:
        """DB의 watched_files와 실제 파일 시스템 비교"""
        for directory in directories:
            fs_files = self._scan_supported_files(directory)
            db_files = await get_watched_files_by_directory(directory)

            # 신규 파일: fs에 있고 db에 없음
            for path in fs_files - db_files:
                await self._register_and_index(path)

            # 변경 파일: 해시 불일치
            for path in fs_files & db_files:
                if await self._is_changed(path):
                    await self._reindex(path)

            # 삭제 파일: db에 있고 fs에 없음 (auto_delete 설정 시)
            if settings.watcher_auto_delete:
                for path in db_files - fs_files:
                    await self._remove(path)

        return ScanResult(added=..., updated=..., deleted=...)
```

**watcher.py** (document 서비스) - 감시 오케스트레이터:
```python
class DirectoryWatcherService:
    """디렉토리 감시 서비스 메인 클래스"""

    def __init__(self):
        self.observer: Observer | None = None
        self.scanner = DirectoryScanner()

    async def start(self):
        """감시 시작"""
        directories = settings.watcher_directories
        if not directories:
            raise ValueError("감시할 디렉토리가 설정되지 않았습니다")

        # 1. 초기 전체 스캔
        await self.scanner.full_scan(directories)

        # 2. Observer 시작
        handler = DocumentFileHandler()
        ObserverClass = PollingObserver if settings.watcher_use_polling else Observer
        self.observer = ObserverClass(
            timeout=settings.watcher_polling_interval if settings.watcher_use_polling else 1
        )
        for directory in directories:
            self.observer.schedule(handler, directory, recursive=True)
        self.observer.start()

    async def stop(self):
        """감시 중지"""
        if self.observer:
            self.observer.stop()
            self.observer.join()
            self.observer = None

    def is_running(self) -> bool:
        return self.observer is not None and self.observer.is_alive()
```

**watcher.py** (tasks) - Celery 태스크:
```python
@celery_app.task(bind=True, max_retries=3)
def sync_watched_file_task(self, file_path: str, event_type: str):
    """파일 생성/수정 이벤트 → 해시 비교 → 인덱싱"""
    file_hash = compute_sha256(file_path)
    existing = asyncio.run(get_watched_file_by_path(file_path))

    if existing and existing.file_hash == file_hash:
        return  # 변경 없음 (중복 이벤트)

    if existing:
        # 변경: 기존 인덱스 삭제 후 재인덱싱
        doc_id = existing.document_id
        asyncio.run(reindex_document(doc_id, file_path))
    else:
        # 신규: documents 테이블에 등록 + 인덱싱
        doc = asyncio.run(register_document(
            file_path=file_path,
            source="watcher",
        ))
        index_document_task.delay(doc.id)

    # watched_files 테이블 갱신
    asyncio.run(upsert_watched_file(file_path, file_hash, doc_id))

@celery_app.task
def delete_watched_file_task(file_path: str):
    """파일 삭제 이벤트 → 인덱스에서 제거"""
    watched = asyncio.run(get_watched_file_by_path(file_path))
    if watched:
        asyncio.run(delete_document(watched.document_id))
        asyncio.run(remove_watched_file(file_path))
```

**watcher.py** (API) - 감시 제어 엔드포인트:
```python
@router.get("/api/watcher/status")
async def get_watcher_status():
    """감시 상태 조회"""

@router.post("/api/watcher/start")
async def start_watcher():
    """감시 시작 (설정의 directories 사용)"""

@router.post("/api/watcher/stop")
async def stop_watcher():
    """감시 중지"""

@router.post("/api/watcher/scan")
async def trigger_scan():
    """수동 전체 스캔 (비동기 태스크)"""

@router.get("/api/watcher/files")
async def list_watched_files(page: int = 1, size: int = 20):
    """감시 중인 파일 목록 (페이징)"""
```

**DB 모델 추가** (Phase 2의 database.py에 추가):
```python
class WatchedFile(Base):
    __tablename__ = "watched_files"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    file_path: Mapped[str] = mapped_column(unique=True, index=True)
    file_hash: Mapped[str]          # SHA-256
    file_size: Mapped[int]
    document_id: Mapped[UUID] = mapped_column(ForeignKey("documents.id"))
    last_synced_at: Mapped[datetime]
    created_at: Mapped[datetime]
```

**documents 테이블 수정** — `source` 컬럼 추가:
```python
class Document(Base):
    # ... 기존 필드 ...
    source: Mapped[str] = mapped_column(default="upload")  # "upload" | "watcher"
    watch_path: Mapped[str | None] = mapped_column(nullable=True)  # watcher인 경우 원본 경로
```

#### TDD
```
RED:   test_handler_filters_supported_files → 지원 확장자만 처리하는지 확인
RED:   test_handler_debounce → 1초 내 중복 이벤트 무시 확인
RED:   test_scanner_detects_new_files → 신규 파일 감지 확인
RED:   test_scanner_detects_changed_files → 해시 변경 감지 확인
RED:   test_scanner_detects_deleted_files → 삭제 파일 감지 확인 (auto_delete=True)
RED:   test_scanner_ignores_deleted_when_disabled → auto_delete=False 시 삭제 무시
RED:   test_sync_task_indexes_new_file → 신규 파일 인덱싱 확인
RED:   test_sync_task_skips_unchanged → 해시 동일 시 스킵 확인
RED:   test_watcher_start_stop → 서비스 시작/중지 확인
RED:   test_watcher_api_status → API 상태 응답 확인
GREEN: 각 모듈 구현
```

---

### Step 3.8: 전체 재인덱싱 (무중단)

#### 생성 파일
- `backend/app/services/document/reindexer.py`
- `backend/app/api/system.py`

#### 구현 내용

**reindexer.py** - 무중단 전체 재인덱싱:
1. 새 ES 인덱스 생성 (`rag_documents_{timestamp}`)
2. 새 PGVector 테이블 또는 새 컬럼 세트 생성
3. 모든 문서를 새 인덱스에 배치 인덱싱 (Celery)
4. 완료 후 ES alias 전환, PG 테이블 교체
5. 이전 인덱스/테이블 정리

**system.py** - 시스템 API:
- `POST /api/system/reindex-all` → 비동기 재인덱싱 시작, task_id 반환
- `GET /api/system/tasks/{task_id}` → 작업 상태 확인
- `GET /api/system/status` → DB, ES, Ollama 연결 상태 + 모델 로드 상태

#### TDD
```
RED:   test_reindex_creates_new_index → 새 인덱스 생성 확인
RED:   test_reindex_swaps_alias → alias 전환 확인
RED:   test_system_reindex_all_returns_task_id → API 응답에 task_id 포함 확인
GREEN: reindexer.py, system.py 구현
```

---

### Step 3.9: 통합 테스트

#### 생성 파일
- `backend/tests/integration/test_document_pipeline.py`
- `backend/tests/integration/test_watcher_pipeline.py`

#### 구현 내용

**test_document_pipeline.py** (기존):
- 테스트 TXT 파일 업로드 → 변환 → 청킹 → 임베딩 → 듀얼 인덱싱 전체 흐름
- 인덱싱 완료 후 PGVector에서 벡터 검색 가능 확인
- 인덱싱 완료 후 Elasticsearch에서 키워드 검색 가능 확인
- 문서 삭제 후 양쪽 인덱스에서 제거 확인

**test_watcher_pipeline.py** (신규):
- 감시 디렉토리에 파일 생성 → 자동 감지 → 인덱싱 확인
- 감시 디렉토리의 파일 수정 → 재인덱싱 확인 (해시 변경)
- 감시 디렉토리의 파일 삭제 → auto_delete 설정에 따른 인덱스 제거 확인
- 전체 스캔으로 누락 파일 보정 확인
- 감시 서비스 시작/중지 API 확인

## 생성 파일 전체 목록

| 파일 | 설명 |
|------|------|
| `backend/app/services/document/__init__.py` | 패키지 |
| `backend/app/services/document/converter.py` | 파일 변환 (PDF, DOCX, TXT, MD) |
| `backend/app/services/document/processor.py` | 문서 처리 오케스트레이터 |
| `backend/app/services/document/indexer.py` | 듀얼 인덱서 (PGVector + ES) |
| `backend/app/services/document/reindexer.py` | 전체 재인덱싱 (무중단) |
| `backend/app/services/chunking/__init__.py` | 패키지 |
| `backend/app/services/chunking/base.py` | ChunkingStrategy Protocol |
| `backend/app/services/chunking/recursive.py` | 재귀적 문자 분할 |
| `backend/app/services/chunking/semantic.py` | 시맨틱 청킹 |
| `backend/app/services/chunking/contextual.py` | Contextual Retrieval |
| `backend/app/services/chunking/auto_detect.py` | 자동 감지 |
| `backend/app/services/watcher/__init__.py` | 패키지 |
| `backend/app/services/watcher/handler.py` | watchdog 이벤트 핸들러 |
| `backend/app/services/watcher/scanner.py` | 전체/부분 디렉토리 스캔 |
| `backend/app/services/document/watcher.py` | 디렉토리 감시 오케스트레이터 |
| `backend/app/api/documents.py` | 문서 CRUD API |
| `backend/app/api/watcher.py` | 감시 제어 API |
| `backend/app/api/system.py` | 시스템 API (재인덱싱, 작업상태) |
| `backend/app/worker.py` | Celery 앱 |
| `backend/app/tasks/indexing.py` | 인덱싱 비동기 태스크 |
| `backend/app/tasks/watcher.py` | 감시 관련 비동기 태스크 |
| `backend/tests/unit/test_chunking_*.py` | 청킹 단위 테스트 |
| `backend/tests/unit/test_converter.py` | 변환 단위 테스트 |
| `backend/tests/unit/test_indexer.py` | 인덱서 단위 테스트 |
| `backend/tests/unit/test_watcher_*.py` | 디렉토리 감시 단위 테스트 |
| `backend/tests/integration/test_document_pipeline.py` | 문서 파이프라인 통합 테스트 |
| `backend/tests/integration/test_watcher_pipeline.py` | 디렉토리 감시 통합 테스트 |

## 테스트 전략

- **단위 테스트**: 각 청킹 전략, 파일 변환, 인덱서, 디렉토리 감시 핸들러/스캐너 (mock 의존성)
- **통합 테스트**: 파일 업로드 → 인덱싱, 디렉토리 감시 → 자동 인덱싱 (실 인프라 필요)
- 테스트 fixture: 샘플 TXT/PDF 파일 (`backend/tests/fixtures/`), 임시 감시 디렉토리 (tempfile)

## 완료 조건 (자동 검증)

```bash
cd backend && pytest tests/unit/test_chunking*.py tests/unit/test_converter.py tests/unit/test_indexer.py tests/unit/test_watcher*.py -v
pytest tests/integration/test_document_pipeline.py tests/integration/test_watcher_pipeline.py -v
curl -s localhost:8000/api/documents | python3 -c "import sys,json; docs=json.load(sys.stdin); assert len(docs['items'])>=0"
curl -s localhost:8000/api/watcher/status | python3 -m json.tool
curl -s "localhost:9200/rag_*/_count" | python3 -m json.tool
```

## 인수인계 항목

Phase 4로 전달:
- DocumentIndexer 인터페이스 (PGVector + ES 저장소 접근 방식)
- PGVector 저장소: 벡터 차원 1024, chunks 테이블, doc_id 메타데이터
- Elasticsearch 인덱스: `rag_documents`, Nori 분석기 적용, content/meta 필드
- 청크 구조: content(text), chunk_index(int), metadata(JSON)
- EmbeddingProvider 재사용 (쿼리 임베딩에 동일 모델 사용)
- documents 테이블에 `source` 컬럼 추가됨 ("upload" | "watcher")
- 디렉토리 감시 서비스: watcher API, watched_files 테이블, 이벤트/폴링 모드

Phase 7로 전달:
- 감시 API 엔드포인트: `/api/watcher/*` (status, start, stop, scan, files)
- 설정 스키마에 watcher 섹션 추가됨 (enabled, directories, use_polling, polling_interval, auto_delete, file_patterns)
- 문서 목록 API에 `source` 필터 파라미터 추가됨
