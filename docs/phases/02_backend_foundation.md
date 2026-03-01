# Phase 2: 백엔드 기반 구축 상세 개발 계획

## 개요

| 항목 | 내용 |
|------|------|
| Phase | 2 |
| 담당 | 백엔드 엔지니어 |
| 의존성 | Phase 1 |
| 참조 문서 | `docs/architecture/02_project_structure.md`, `docs/architecture/04_backend.md` |

## 사전 조건

- Phase 1 완료 (infra docker-compose 기동 가능)
- Python 3.12+ 설치
- Ollama 호스트 실행 중 (http://localhost:11434)

## 상세 구현 단계

### Step 2.1: 프로젝트 초기화

#### 생성 파일
- `backend/pyproject.toml`
- `backend/app/__init__.py`
- `backend/app/main.py`

#### 구현 내용

**pyproject.toml**: 핵심 의존성 정의
```
fastapi>=0.115, uvicorn[standard]>=0.34, python-multipart>=0.0.18
haystack-ai>=2.9, haystack-integrations[pgvector,elasticsearch,ollama]
sqlalchemy[asyncio]>=2.0, asyncpg>=0.30, alembic>=1.14
celery[redis]>=5.4
transformers>=4.47, sentence-transformers>=3.3, torch>=2.5
kiwipiepy>=0.18, rank-bm25>=0.2
openai>=1.58, anthropic>=0.40
langchain-openai>=0.3  # RAGAS LLM wrapper용
langfuse>=2.55, ragas>=0.2
pydantic-settings>=2.7, python-dotenv>=1.0
```

개발 의존성:
```
pytest>=8.0, pytest-asyncio>=0.24, httpx>=0.27
```

**main.py**: FastAPI 앱 진입점
- CORS 미들웨어 설정 (개발: `*`, 프로덕션: 프론트엔드 URL만)
- 전역 예외 핸들러 등록 (`RAGException` 계열)
- 라우터 등록 (`/api` prefix)
- lifespan으로 DB 연결, 모델 로드 등 초기화/정리

#### TDD
```
RED:   test_health_endpoint → GET /api/health → 200 {"status": "ok"} 확인
GREEN: main.py에 헬스체크 라우터 추가
```

---

### Step 2.2: 설정 시스템 (Pydantic Settings)

#### 생성 파일
- `backend/app/config.py`
- `backend/.env.example`

#### 구현 내용

**config.py**: 2단계 설정 관리

1단계 - 환경 변수 (BaseSettings):
```python
class Settings(BaseSettings):
    database_url: str
    elasticsearch_url: str
    ollama_url: str = "http://localhost:11434"
    redis_url: str = "redis://localhost:6379"
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_host: str = "http://localhost:3100"
```

2단계 - DB 런타임 설정:
```python
class RAGSettings:
    chunking_strategy: str = "recursive"
    chunk_size: int = 512
    chunk_overlap: int = 50
    embedding_provider: str = "ollama"
    embedding_model: str = "bge-m3"
    search_mode: str = "hybrid"
    keyword_engine: str = "elasticsearch"
    rrf_constant: int = 60
    vector_weight: float = 0.5
    keyword_weight: float = 0.5
    reranking_enabled: bool = True
    reranker_model: str = "dragonkue/bge-reranker-v2-m3-ko"
    reranker_top_k: int = 5
    retriever_top_k: int = 20
    hyde_enabled: bool = True
    hyde_model: str = "qwen2.5:7b"
    pii_detection_enabled: bool = True
    injection_detection_enabled: bool = True
    hallucination_detection_enabled: bool = True
    llm_provider: str = "ollama"
    llm_model: str = "qwen2.5:7b"
    system_prompt: str = "..."
```

#### TDD
```
RED:   test_settings_from_env → 환경변수로 Settings 생성 확인
RED:   test_rag_settings_defaults → 기본값 검증
GREEN: config.py 구현
```

---

### Step 2.3: SQLAlchemy 모델 + DB 세션

#### 생성 파일
- `backend/app/models/__init__.py`
- `backend/app/models/database.py`
- `backend/app/models/schemas.py`

#### 구현 내용

**database.py**: SQLAlchemy 2.0 비동기 모델

테이블 정의:
- `documents` - id(UUID PK), filename, file_path(str, uploads/ 내 저장 경로), file_type, file_size, status(enum: uploaded/indexing/indexed/failed), chunk_count, created_at, updated_at
- `chunks` - id(UUID PK), document_id(FK), content(text), chunk_index(int), embedding(Vector(1024)), metadata(JSONB), created_at
- `settings` - id(int PK), key(unique str), value(JSONB), updated_at
- `evaluation_datasets` - id(UUID), name, items(JSONB), created_at
- `evaluation_runs` - id(UUID), dataset_id(FK), status, settings_snapshot(JSONB), metrics(JSONB), per_question_results(JSONB), created_at
- `tasks` - id(UUID), type, status(enum: pending/running/completed/failed), progress(int), result(JSONB), error(text), created_at, updated_at

DB 세션 관리:
- `async_session_factory` (async sessionmaker)
- `get_db()` dependency (yield async session)
- `Base` (DeclarativeBase)

**schemas.py**: Pydantic 요청/응답 스키마
- `DocumentResponse`, `DocumentListResponse` (페이징)
- `SearchRequest`, `SearchResponse`, `DebugSearchResponse`
- `SettingsResponse`, `SettingsUpdateRequest`
- `HealthResponse`
- `TaskStatusResponse`

#### TDD
```
RED:   test_document_model_creation → Document 인스턴스 생성 검증
RED:   test_chunk_model_with_vector → Vector(1024) 필드 포함 Chunk 검증
RED:   test_settings_model → Settings CRUD 검증
GREEN: database.py, schemas.py 구현
```

---

### Step 2.4: Alembic 마이그레이션 설정

#### 생성 파일
- `backend/alembic.ini`
- `backend/alembic/env.py`
- `backend/alembic/versions/` (디렉토리)

#### 구현 내용
- `alembic init alembic`으로 초기화
- `env.py`에서 async 엔진 사용 설정
- `target_metadata = Base.metadata` 연결
- 초기 마이그레이션 생성: `alembic revision --autogenerate -m "initial tables"`

#### 검증
```bash
cd backend && alembic upgrade head
alembic current  # head 확인
```

---

### Step 2.5: 커스텀 예외 및 전역 핸들러

#### 생성 파일
- `backend/app/exceptions.py`

#### 구현 내용

```python
class RAGException(Exception):
    status_code: int = 500
    error_code: str = "INTERNAL_ERROR"

class DocumentNotFoundError(RAGException):
    status_code = 404
    error_code = "DOCUMENT_NOT_FOUND"

class EmbeddingServiceError(RAGException):
    status_code = 503
    error_code = "EMBEDDING_SERVICE_ERROR"

class SearchServiceError(RAGException):
    status_code = 503
    error_code = "SEARCH_SERVICE_ERROR"

class GuardrailViolation(RAGException):
    status_code = 400
    error_code = "GUARDRAIL_VIOLATION"
```

`main.py`에 전역 핸들러 등록:
```python
@app.exception_handler(RAGException)
async def rag_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.error_code, "message": str(exc)}
    )
```

#### TDD
```
RED:   test_rag_exception_handler → RAGException 발생 시 JSON 응답 형식 검증
RED:   test_document_not_found → 404 + DOCUMENT_NOT_FOUND 확인
GREEN: exceptions.py + main.py 핸들러 등록
```

---

### Step 2.6: LLM 프로바이더 인터페이스 (Protocol)

#### 생성 파일
- `backend/app/services/embedding/base.py`
- `backend/app/services/embedding/__init__.py`
- `backend/app/services/embedding/ollama.py`
- `backend/app/services/generation/base.py`
- `backend/app/services/generation/__init__.py`
- `backend/app/services/generation/ollama.py`

#### 구현 내용

**EmbeddingProvider Protocol**:
```python
class EmbeddingProvider(Protocol):
    async def embed_documents(self, texts: list[str]) -> list[list[float]]: ...
    async def embed_query(self, text: str) -> list[float]: ...
```

**OllamaEmbedding 구현체**:
- `httpx.AsyncClient`로 Ollama API 호출
- `POST /api/embed` (model: bge-m3)
- 배치 처리 지원 (한 번에 여러 텍스트)
- 에러 시 `EmbeddingServiceError` 발생

**LLMProvider Protocol**:
```python
class LLMProvider(Protocol):
    async def generate(self, prompt: str, system_prompt: str | None = None) -> str: ...
```

**OllamaLLM 구현체**:
- `POST /api/generate` (model: qwen2.5:7b)
- temperature, max_tokens 설정 가능

#### TDD
```
RED:   test_embedding_provider_protocol → Protocol 인터페이스 준수 확인
RED:   test_ollama_embedding_embed_query → mock Ollama API 응답으로 벡터 반환 검증
RED:   test_llm_provider_protocol → Protocol 인터페이스 준수 확인
RED:   test_ollama_llm_generate → mock Ollama API 응답으로 텍스트 생성 검증
GREEN: base.py, ollama.py 구현
```

---

### Step 2.7: 헬스체크 API 확장

#### 생성/수정 파일
- `backend/app/api/__init__.py`
- `backend/app/api/health.py`

#### 구현 내용

`GET /api/health`:
```json
{
  "status": "ok",
  "components": {
    "database": "connected",
    "elasticsearch": "connected",
    "ollama": "connected",
    "redis": "connected"
  }
}
```

각 컴포넌트 연결 상태를 실제로 확인:
- DB: `SELECT 1` 실행
- ES: `GET /` 호출
- Ollama: `GET /api/tags` 호출
- Redis: `PING`

연결 실패 시 해당 컴포넌트만 `"disconnected"`로 표시 (전체 서버는 200)

#### TDD
```
RED:   test_health_all_connected → 모든 컴포넌트 connected 확인
RED:   test_health_db_disconnected → DB 실패 시 disconnected 표시 확인
GREEN: health.py 구현
```

---

### Step 2.8: 설정 API

#### 생성 파일
- `backend/app/api/settings.py`
- `backend/app/services/settings.py`

#### 구현 내용

- `GET /api/settings` → DB에서 RAGSettings 조회 (없으면 기본값)
- `PATCH /api/settings` → 부분 업데이트 (변경된 필드만)
- `GET /api/settings/models` → Ollama 사용 가능 모델 + API 모델 목록

설정 서비스:
- DB settings 테이블에서 JSON으로 저장/조회
- 캐싱: 메모리 캐시 (TTL 60초)
- 설정 변경 시 캐시 무효화

#### TDD
```
RED:   test_get_default_settings → 초기 상태에서 기본 설정 반환 확인
RED:   test_patch_settings → 부분 업데이트 후 변경 확인
RED:   test_settings_cache_invalidation → 업데이트 후 캐시 반영 확인
GREEN: settings.py (API + 서비스) 구현
```

---

### Step 2.9: 앱 계층 Docker Compose + Makefile

#### 생성 파일
- `docker-compose.yml` (프로젝트 루트)
- `backend/Dockerfile`
- `Makefile`
- `.env.example`

#### 구현 내용

**docker-compose.yml** (앱 계층 - Phase 2에서는 최소 구성):
- `rag-api`: FastAPI 백엔드
- `rag-redis`: Redis 7 (작업 큐용)
- 네트워크: `shared-infra` (external: true)

**backend/Dockerfile**:
```dockerfile
FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends build-essential && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e .
COPY . .
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Makefile** 기본 커맨드:
```makefile
infra-up:     cd infra && docker compose up -d
infra-down:   cd infra && docker compose down
app-up:       docker compose up -d
app-down:     docker compose down
dev-backend:  cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
migrate:      docker compose run --rm rag-api alembic upgrade head
migrate-local: cd backend && alembic upgrade head
test:         cd backend && pytest --tb=short -q
```

#### 검증
```bash
make infra-up && make app-up
curl -s localhost:8000/api/health | python3 -m json.tool
make app-down
```

---

### Step 2.10: 테스트 인프라

#### 생성 파일
- `backend/tests/__init__.py`
- `backend/tests/conftest.py`
- `backend/tests/unit/__init__.py`
- `backend/tests/integration/__init__.py`

#### 구현 내용

**conftest.py**:
- `@pytest.fixture` async 테스트 DB 세션 (PostgreSQL 테스트 DB — `shared_test` 데이터베이스 사용)
  - Vector(1024), JSONB 등 PostgreSQL 전용 타입을 정확히 검증하기 위해 SQLite 대신 PostgreSQL 사용
  - 순수 서비스 로직 테스트(mock 의존성)에만 SQLite 허용
- `@pytest.fixture` FastAPI TestClient (httpx AsyncClient)
- `@pytest.fixture` mock Ollama, mock Elasticsearch
- `pytest.ini` 또는 `pyproject.toml [tool.pytest]` 설정

## 생성 파일 전체 목록

| 파일 | 설명 |
|------|------|
| `backend/pyproject.toml` | Python 프로젝트 설정 + 의존성 |
| `backend/app/__init__.py` | 패키지 초기화 |
| `backend/app/main.py` | FastAPI 앱 진입점 |
| `backend/app/config.py` | 설정 관리 (Pydantic Settings + DB 런타임) |
| `backend/app/exceptions.py` | 커스텀 예외 |
| `backend/app/models/__init__.py` | 모델 패키지 |
| `backend/app/models/database.py` | SQLAlchemy 모델 |
| `backend/app/models/schemas.py` | Pydantic 스키마 |
| `backend/app/api/__init__.py` | API 라우터 패키지 |
| `backend/app/api/health.py` | 헬스체크 API |
| `backend/app/api/settings.py` | 설정 API |
| `backend/app/services/settings.py` | 설정 서비스 |
| `backend/app/services/embedding/base.py` | EmbeddingProvider Protocol |
| `backend/app/services/embedding/__init__.py` | 패키지 |
| `backend/app/services/embedding/ollama.py` | Ollama 임베딩 구현체 |
| `backend/app/services/generation/base.py` | LLMProvider Protocol |
| `backend/app/services/generation/__init__.py` | 패키지 |
| `backend/app/services/generation/ollama.py` | Ollama LLM 구현체 |
| `backend/alembic.ini` | Alembic 설정 |
| `backend/alembic/env.py` | Alembic 환경 설정 |
| `backend/alembic/versions/` | 마이그레이션 디렉토리 |
| `backend/Dockerfile` | 백엔드 Docker 이미지 |
| `backend/tests/conftest.py` | 테스트 fixture |
| `docker-compose.yml` | 앱 계층 컴포즈 (최소) |
| `Makefile` | 개발/운영 커맨드 |
| `.env.example` | 환경 변수 템플릿 |

## 테스트 전략

- **단위 테스트**: 모델 생성, 설정 로드, 예외 처리, Provider Protocol 준수
- **통합 테스트**: 헬스체크 API, 설정 API CRUD
- TDD 사이클: 각 Step마다 RED → GREEN → REFACTOR

## 완료 조건 (자동 검증)

```bash
cd backend && pytest --tb=short -q
uvicorn app.main:app --host 0.0.0.0 --port 8000 &
sleep 3
curl -s localhost:8000/api/health | python3 -m json.tool
kill %1
alembic upgrade head
```

## 인수인계 항목

Phase 3으로 전달:
- FastAPI 앱 구조 (`app/main.py`, 라우터 등록 방식)
- SQLAlchemy 모델 (`documents`, `chunks` 테이블 스키마)
- EmbeddingProvider Protocol (embed_documents, embed_query)
- DB 세션 dependency (`get_db()`)
- 설정 시스템 (Settings + RAGSettings)
- Celery 연결 정보 (Redis URL)

Phase 7로 전달 (병렬):
- API 엔드포인트 명세 (`/api/health`, `/api/settings`)
- 응답 스키마 (Pydantic schemas.py)
- 에러 응답 형식 (`{"error": "...", "message": "..."}`)
