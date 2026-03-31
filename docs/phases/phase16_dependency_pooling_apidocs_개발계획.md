# Phase 16 개발 계획: 의존성 관리, 커넥션 풀링, API 문서 강화

## 개요

| 항목 | 내용 |
|------|------|
| Phase | 16 |
| 기능명 | 의존성 관리 + 커넥션 풀링 + API 문서 강화 |
| 작성일 | 2026-03-31 |
| 상태 | 계획 |
| 관련 이슈 | #19, #11, #14 |
| 에이전트 팀 | 지훈(백엔드), 현우(DevOps), 민수(보안) |

### 배경 및 문제 상황

**왜 이 Phase가 필요한가?**

프로덕션 안정성과 개발자 경험(DX) 향상을 위한 3가지 인프라 개선:

1. **의존성 보안 사각지대 (#19)**: `pyproject.toml`에 하한만 지정(`>=`)하고 상한이 없어 메이저 버전 업그레이드 시 호환성 문제 발생 가능. Dependabot 미설정으로 보안 취약점 자동 감지가 안 됨
2. **커넥션 풀 기본값 방치 (#11)**: SQLAlchemy `pool_size=10, max_overflow=20`이 하드코딩. Elasticsearch는 httpx 클라이언트를 **요청마다 새로 생성** (풀링 없음). Redis는 `max_connections=20` 고정. 환경변수로 튜닝 불가
3. **API 문서 빈약 (#14)**: Swagger UI가 자동 생성되지만, 응답 예제/에러 코드/상세 설명이 없어 프론트엔드 개발 시 소스 코드를 직접 읽어야 함

### 목표

- 보안 취약점 자동 감지 파이프라인 구축
- 프로덕션 부하에 대응 가능한 커넥션 풀 설정
- API 문서만으로 프론트엔드 개발이 가능한 수준의 문서화

### 핵심 해결 방안 요약

```
[Issue #19] .github/dependabot.yml 생성 + pyproject.toml 버전 범위 + CI에 audit 추가
[Issue #11] config.py에 풀 설정 → database.py/redis.py/keyword_es.py 에 적용
[Issue #14] 에러 스키마 정의 → 라우터에 responses 파라미터 + Pydantic examples
```

---

## 상세 목표

### Issue #19: 의존성 버전 관리 및 보안 스캔 자동화

1. `pyproject.toml` 의존성에 상한 버전 추가 (`>=X.Y,<X+1`)
2. `.github/dependabot.yml` 생성 (pip, npm, docker 에코시스템)
3. CI에 `pip-audit` + `pnpm audit` 스텝 추가

### Issue #11: 커넥션 풀링 최적화

1. `config.py`에 커넥션 풀 환경변수 설정 추가
2. SQLAlchemy 엔진에 `pool_pre_ping`, `pool_recycle` 적용
3. Elasticsearch httpx 클라이언트를 영속 커넥션 풀로 변경
4. Redis 풀 설정을 환경변수로 제어 가능하게 변경
5. `/api/health` 에 커넥션 풀 상태 포함

### Issue #14: API 문서 강화

1. 공통 에러 응답 스키마 정의 (`ErrorResponse`)
2. 모든 엔드포인트에 `summary`, `description`, `responses` 추가
3. Pydantic 모델에 `model_config` 예제 추가
4. 에러 코드 정의서 (`docs/api/error-codes.md`) 작성

---

## 관련 유스케이스

| ID | 유스케이스 명 | 액터 | 설명 |
|----|-------------|------|------|
| UC-1 | 의존성 보안 알림 수신 | 개발자 | 취약 의존성 발견 시 Dependabot이 자동으로 PR 생성 |
| UC-2 | 의존성 업데이트 PR 리뷰 | 개발자 | 주간 자동 업데이트 PR에서 변경 범위를 확인 후 머지 |
| UC-3 | 고부하 시 DB 연결 안정 | 시스템 | 동시 요청 증가 시 커넥션 풀이 안정적으로 연결 관리 |
| UC-4 | DB 재시작 후 자동 복구 | 시스템 | PostgreSQL 재시작 후 `pool_pre_ping`이 끊어진 연결을 감지하고 재연결 |
| UC-5 | ES 커넥션 재사용 | 시스템 | Elasticsearch 검색 시 기존 TCP 연결을 재사용하여 지연 감소 |
| UC-6 | API 문서로 프론트 개발 | 프론트엔드 개발자 | Swagger UI의 응답 예제와 에러 코드만 보고 API 연동 구현 |
| UC-7 | 에러 응답 디버깅 | 개발자 | 에러 발생 시 표준화된 에러 코드로 원인을 빠르게 파악 |

---

## 데이터베이스 스키마

**변경 없음.** 이 Phase는 인프라 설정과 문서화 작업이므로 DB 스키마 변경이 없다.

---

## API 설계

### 변경되는 엔드포인트

기존 엔드포인트의 **응답 스키마 보강**만 수행. 새 엔드포인트는 없음.

### 공통 에러 응답 스키마 (신규)

```python
class ErrorDetail(BaseModel):
    """개별 에러 상세"""
    field: str | None = None
    message: str
    code: str

    model_config = ConfigDict(json_schema_extra={
        "examples": [
            {"field": "query", "message": "검색어는 1자 이상이어야 합니다", "code": "VALIDATION_ERROR"}
        ]
    })

class ErrorResponse(BaseModel):
    """표준 에러 응답"""
    status: int
    error: str
    message: str
    details: list[ErrorDetail] | None = None
    request_id: str | None = None

    model_config = ConfigDict(json_schema_extra={
        "examples": [
            {
                "status": 401,
                "error": "Unauthorized",
                "message": "유효하지 않은 인증 토큰입니다",
                "details": None,
                "request_id": "req_abc123"
            }
        ]
    })
```

### 에러 코드 체계

| HTTP 상태 | 에러 코드 | 설명 | 발생 엔드포인트 |
|-----------|----------|------|----------------|
| 400 | `VALIDATION_ERROR` | 요청 파라미터 유효성 검사 실패 | 전체 |
| 400 | `INVALID_FILE_TYPE` | 지원하지 않는 파일 형식 | `POST /api/documents/upload` |
| 400 | `DUPLICATE_USERNAME` | 이미 존재하는 사용자명 | `POST /api/auth/signup` |
| 401 | `TOKEN_EXPIRED` | JWT 토큰 만료 | 인증 필요 엔드포인트 전체 |
| 401 | `TOKEN_INVALID` | 잘못된 JWT 토큰 | 인증 필요 엔드포인트 전체 |
| 401 | `INVALID_CREDENTIALS` | 로그인 실패 | `POST /api/auth/login` |
| 403 | `ADMIN_REQUIRED` | 관리자 권한 필요 | admin 전용 엔드포인트 |
| 404 | `DOCUMENT_NOT_FOUND` | 문서를 찾을 수 없음 | `GET/DELETE /api/documents/{id}` |
| 404 | `USER_NOT_FOUND` | 사용자를 찾을 수 없음 | `GET/PATCH/DELETE /api/admin/users/{id}` |
| 404 | `DATASET_NOT_FOUND` | 평가 데이터셋 없음 | `GET/DELETE /api/evaluation/datasets/{id}` |
| 404 | `RUN_NOT_FOUND` | 평가 실행 없음 | `GET /api/evaluation/runs/{id}` |
| 429 | `RATE_LIMIT_EXCEEDED` | 요청 빈도 초과 | rate limit 설정된 엔드포인트 |
| 500 | `INTERNAL_ERROR` | 서버 내부 오류 | 전체 |
| 503 | `SERVICE_UNAVAILABLE` | 외부 서비스 연결 실패 | 검색, 문서 처리 |

### 엔드포인트별 responses 파라미터 예시

```python
@router.post(
    "/search",
    response_model=SearchResponse,
    summary="문서 검색 및 답변 생성",
    description="하이브리드 검색(벡터+키워드)으로 관련 문서를 찾고, LLM이 답변을 생성합니다. "
                "검색 모드, HyDE, 리랭킹 등을 요청별로 오버라이드할 수 있습니다.",
    responses={
        422: {"model": ErrorResponse, "description": "요청 유효성 검사 실패"},
        429: {"model": ErrorResponse, "description": "Rate limit 초과 (30회/분)"},
        503: {"model": ErrorResponse, "description": "검색 엔진 또는 LLM 서비스 연결 실패"},
    },
)
```

---

## 단계별 구현 계획

### Step 1: 의존성 버전 관리 (#19)

**담당**: 현우(DevOps), 민수(보안)

#### 1-1. pyproject.toml 버전 범위 지정

현재 `>=` 하한만 있는 의존성에 `<` 상한을 추가한다. 메이저 버전 변경을 방지하는 것이 목적.

**변경 파일**: `backend/pyproject.toml`

**원칙**:
- 프레임워크/핵심 라이브러리: 현재 메이저 버전의 다음 메이저까지 (`>=2.0,<3`)
- ML 라이브러리(torch, transformers): 마이너 버전 단위로 제한 고려 (호환성 위험 높음)
- 유틸리티 라이브러리: 메이저 버전 상한 (`>=1.0,<2`)

**변경 예시**:
```toml
# Before
"fastapi>=0.115"
"sqlalchemy[asyncio]>=2.0"
"torch>=2.5"

# After
"fastapi>=0.115,<1"
"sqlalchemy[asyncio]>=2.0,<3"
"torch>=2.5,<3"
```

**주요 의존성 버전 범위 설계**:

| 패키지 | 현재 | 상한 | 사유 |
|--------|------|------|------|
| `fastapi` | `>=0.115` | `<1` | 1.0 미출시, 0.x 내 호환 |
| `sqlalchemy[asyncio]` | `>=2.0` | `<3` | 메이저 버전 방어 |
| `haystack-ai` | `>=2.9` | `<3` | Haystack 2.x API 기반 |
| `torch` | `>=2.5` | `<3` | CUDA 호환성 |
| `transformers` | `>=4.47` | `<5` | 모델 로딩 API 변경 위험 |
| `openai` | `>=1.58` | `<2` | SDK 1.x API 기반 |
| `anthropic` | `>=0.40` | `<1` | 0.x 내 호환 |
| `celery[redis]` | `>=5.4` | `<6` | 메이저 버전 방어 |
| `sentry-sdk[fastapi]` | `>=2.0.0` | `<3` | 메이저 버전 방어 |
| `pydantic-settings` | `>=2.7` | `<3` | Pydantic v2 기반 |
| `langfuse` | `>=2.55` | `<3` | 메이저 버전 방어 |
| `docling` | `>=2.78` | `<3` | 메이저 버전 방어 |

#### 1-2. Dependabot 설정

**신규 파일**: `.github/dependabot.yml`

```yaml
version: 2
updates:
  # Python (backend)
  - package-ecosystem: "pip"
    directory: "/backend"
    schedule:
      interval: "weekly"
      day: "monday"
      time: "09:00"
      timezone: "Asia/Seoul"
    open-pull-requests-limit: 10
    labels:
      - "dependencies"
      - "backend"
    commit-message:
      prefix: "deps(backend)"
    groups:
      ml-libraries:
        patterns:
          - "torch*"
          - "transformers*"
          - "sentence-transformers*"
          - "accelerate*"
        update-types:
          - "minor"
          - "patch"
      llm-clients:
        patterns:
          - "openai*"
          - "anthropic*"
          - "langfuse*"
        update-types:
          - "minor"
          - "patch"

  # npm (frontend)
  - package-ecosystem: "npm"
    directory: "/frontend"
    schedule:
      interval: "weekly"
      day: "monday"
      time: "09:00"
      timezone: "Asia/Seoul"
    open-pull-requests-limit: 10
    labels:
      - "dependencies"
      - "frontend"
    commit-message:
      prefix: "deps(frontend)"
    groups:
      react-ecosystem:
        patterns:
          - "react*"
          - "next*"
          - "@tanstack/*"
        update-types:
          - "minor"
          - "patch"

  # Docker
  - package-ecosystem: "docker"
    directory: "/backend"
    schedule:
      interval: "monthly"
    labels:
      - "dependencies"
      - "docker"
    commit-message:
      prefix: "deps(docker)"

  # GitHub Actions
  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "weekly"
    labels:
      - "dependencies"
      - "ci"
    commit-message:
      prefix: "deps(ci)"
```

#### 1-3. CI에 보안 감사 스텝 추가

**변경 파일**: `.github/workflows/ci.yml`

`backend-test` 잡에 `pip-audit` 스텝 추가:

```yaml
- name: Security audit (pip-audit)
  run: |
    pip install pip-audit
    pip-audit --strict --desc --ignore-vuln-file .pip-audit-ignore
  continue-on-error: false
```

**신규 파일**: `backend/.pip-audit-ignore` (빈 파일로 시작, 예외 발생 시 사유와 함께 추가)

```
# pip-audit 예외 목록
# 형식: VULN-ID  # 사유 + 추적 이슈 URL
# 예: PYSEC-2024-XXXX  # torch 패치 미출시, GPU 전용 코드 경로 → #XX
```

> 민수(보안 리드) 리뷰 반영: 패치되지 않은 취약점으로 CI가 무기한 중단되는 것을 방지하되, 예외 항목은 반드시 사유와 추적 이슈를 기록한다.

`frontend-build` 잡에 `pnpm audit` 스텝 추가:

```yaml
- name: Security audit (pnpm audit)
  run: pnpm audit --audit-level=high
  continue-on-error: true  # high 이상만 실패 처리

- name: Docker image scan (Trivy)
  uses: aquasecurity/trivy-action@0.28.0
  with:
    scan-type: 'fs'
    scan-ref: 'backend/'
    severity: 'HIGH,CRITICAL'
    exit-code: '1'
```

> 민수(보안 리드) 리뷰 반영: Python/npm 의존성뿐 아니라 Docker 베이스 이미지 및 OS 레벨 취약점도 Trivy로 스캔한다.

#### 1-4. 검증 방법

```bash
# Dependabot 설정 유효성 검사
python -c "import yaml; yaml.safe_load(open('.github/dependabot.yml'))"

# pip-audit 로컬 실행 (예외 파일 포함)
cd backend && pip-audit --strict --desc --ignore-vuln-file .pip-audit-ignore

# pnpm audit 로컬 실행
cd frontend && pnpm audit

# .pip-audit-ignore 파일 존재 확인
test -f backend/.pip-audit-ignore && echo "pip-audit ignore file exists"
```

---

### Step 2: 커넥션 풀링 최적화 (#11)

**담당**: 지훈(백엔드)

#### 2-1. config.py에 풀 설정 환경변수 추가

**변경 파일**: `backend/app/config.py`

`Settings` 클래스에 커넥션 풀 설정 추가:

```python
# === 커넥션 풀 설정 ===

# PostgreSQL
db_pool_size: int = 10
db_max_overflow: int = 20
db_pool_pre_ping: bool = True
db_pool_recycle: int = 1800  # 30분 (초)
db_pool_timeout: int = 30    # 풀에서 연결 대기 시간 (초)

# Elasticsearch
es_max_connections: int = 20
es_request_timeout: float = 30.0
es_max_retries: int = 3

# Redis
redis_max_connections: int = 20
redis_socket_timeout: float = 5.0
redis_socket_connect_timeout: float = 5.0
redis_retry_on_timeout: bool = True
```

#### 2-2. SQLAlchemy 엔진 풀 설정 적용

**변경 파일**: `backend/app/models/database.py` (Line ~171)

```python
# Before
_engine = create_async_engine(
    database_url, 
    echo=False, 
    pool_size=10,
    max_overflow=20,
)

# After
from app.config import get_settings

_settings = get_settings()
_engine = create_async_engine(
    database_url,
    echo=False,
    pool_size=_settings.db_pool_size,
    max_overflow=_settings.db_max_overflow,
    pool_pre_ping=_settings.db_pool_pre_ping,
    pool_recycle=_settings.db_pool_recycle,
    pool_timeout=_settings.db_pool_timeout,
)
```

**추가 효과**:
- `pool_pre_ping=True`: 매 연결 사용 전 `SELECT 1`로 유효성 확인 → PostgreSQL 재시작 후 자동 복구
- `pool_recycle=1800`: 30분마다 연결 갱신 → 장시간 유휴 연결의 타임아웃 방지

#### 2-3. Elasticsearch httpx 클라이언트 영속화

**변경 파일**: `backend/app/services/search/keyword_es.py`

현재 문제: httpx `AsyncClient`를 요청마다 새로 생성하고 있음.

```python
# Before (keyword_es.py 내 search 메서드)
async with httpx.AsyncClient() as client:
    response = await client.post(...)

# After
class ElasticsearchNoriEngine:
    def __init__(self, es_url, index_name, settings=None):
        self.es_url = es_url
        self.index_name = index_name
        s = settings or get_settings()
        self._client = httpx.AsyncClient(
            base_url=es_url,
            timeout=httpx.Timeout(s.es_request_timeout),
            limits=httpx.Limits(
                max_connections=s.es_max_connections,
                max_keepalive_connections=s.es_max_connections // 2,
                keepalive_expiry=30,
            ),
            transport=httpx.AsyncHTTPTransport(
                retries=s.es_max_retries,
            ),
        )

    async def close(self):
        await self._client.aclose()
```

**변경 파일**: `backend/app/services/document/stores/elasticsearch_store.py`

동일한 패턴으로 영속 클라이언트 적용.

**변경 파일**: `backend/app/main.py` (lifespan 내 shutdown 시퀀스)

프로젝트는 이미 `lifespan` context manager를 사용 중이므로, ES 클라이언트 정리도 `lifespan` 내부의 shutdown 블록에 추가한다.

```python
# lifespan 함수의 yield 이후 (shutdown 블록)에 추가:
# ES httpx 클라이언트 정리
if hasattr(keyword_engine, '_client'):
    await keyword_engine.close()
    logger.info("es_httpx_client_closed")
```

**주의**: `app.state`에 별도 할당하지 않고, `lifespan` 스코프 내에서 직접 참조한다 (이미 `keyword_engine` 변수가 lifespan 내에 존재).

#### 2-4. Redis 풀 설정 환경변수 적용

**변경 파일**: `backend/app/redis.py`

```python
# Before
_pool = aioredis.ConnectionPool.from_url(
    env.redis_url,
    decode_responses=True,
    max_connections=20,
)

# After
_pool = aioredis.ConnectionPool.from_url(
    env.redis_url,
    decode_responses=True,
    max_connections=env.redis_max_connections,
    socket_timeout=env.redis_socket_timeout,
    socket_connect_timeout=env.redis_socket_connect_timeout,
    retry_on_timeout=env.redis_retry_on_timeout,
)
```

#### 2-5. 헬스체크에 풀 상태 포함

**변경 파일**: `backend/app/api/health.py`

`GET /api/health` 응답에 커넥션 풀 상태 추가:

```python
# SQLAlchemy 풀 상태
pool = _engine.pool
pool_status = {
    "size": pool.size(),
    "checked_in": pool.checkedin(),
    "checked_out": pool.checkedout(),
    "overflow": pool.overflow(),
}

# Redis 풀 상태
redis = await get_redis()
redis_pool = redis.connection_pool
redis_status = {
    "max_connections": redis_pool.max_connections,
    "current_connections": len(redis_pool._in_use_connections),
}
```

#### 2-6. 검증 방법

```bash
# 백엔드 테스트
cd backend && pytest --tb=short -q

# 환경변수 오버라이드 테스트
DB_POOL_SIZE=5 DB_POOL_PRE_PING=true python -c "
from app.config import get_settings
s = get_settings()
assert s.db_pool_size == 5
assert s.db_pool_pre_ping == True
print('OK')
"

# 헬스체크에서 풀 상태 확인
curl -s http://localhost:8000/api/health | python -m json.tool
```

---

### Step 3: API 문서 강화 (#14)

**담당**: 지훈(백엔드), 소연(프론트엔드 검증)

#### 3-1. 공통 에러 응답 스키마 정의 및 기존 예외 핸들러 통합

**변경 파일**: `backend/app/models/schemas.py`

위 API 설계 섹션의 `ErrorResponse`, `ErrorDetail` 모델 추가.

**변경 파일**: `backend/app/main.py` (기존 exception_handler 수정)

프로젝트에 이미 `rag_exception_handler`, `unhandled_exception_handler`, `RequestLoggingMiddleware`(request_id 생성 + `X-Request-ID` 헤더)가 구현되어 있다. 기존 핸들러의 응답 형식을 `ErrorResponse` 스키마에 맞추도록 수정한다:

```python
# Before (현재 구현)
@app.exception_handler(RAGException)
async def rag_exception_handler(request: Request, exc: RAGException):
    request_id = _get_request_id()
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "request_id": request_id},
    )

# After (ErrorResponse 스키마 적용)
@app.exception_handler(RAGException)
async def rag_exception_handler(request: Request, exc: RAGException):
    request_id = _get_request_id()
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            status=exc.status_code,
            error=exc.error_code or "ERROR",
            message=exc.detail,
            request_id=request_id,
        ).model_dump(),
    )
```

> 소연(프론트엔드 장인) 리뷰 반영: 스키마만 정의하는 것이 아니라, 기존 예외 핸들러가 실제로 `ErrorResponse` 형식을 반환하도록 통합한다. `request_id`는 이미 미들웨어에서 생성되므로 추가 구현 불필요.

#### 3-2. 엔드포인트별 문서 보강

**변경 파일**: `backend/app/api/*.py` (전체 라우터)

각 엔드포인트에 추가할 항목:

| 항목 | 설명 | 예시 |
|------|------|------|
| `summary` | 1줄 요약 (Swagger 목록에 표시) | `"문서 검색 및 답변 생성"` |
| `description` | 상세 설명 (마크다운 가능) | 검색 모드, 캐시 동작 설명 |
| `responses` | 에러 코드별 스키마 | `{401: {"model": ErrorResponse}}` |

**엔드포인트별 문서화 체크리스트**:

| 라우터 | 엔드포인트 수 | 현재 docstring | 작업량 |
|--------|-------------|---------------|--------|
| `health.py` | 4 | 간략 있음 | 소 |
| `auth.py` | 7 | 간략 있음 | 중 |
| `search.py` | 2 | 간략 있음 | 중 |
| `documents.py` | 6 | 간략 있음 | 중 |
| `settings.py` | 3 | 간략 있음 | 소 |
| `evaluation.py` | 6 | 간략 있음 | 중 |
| `admin.py` | 5 | 간략 있음 | 소 |
| `monitoring.py` | 2 | 간략 있음 | 소 |
| `system.py` | 2 | 간략 있음 | 소 |
| `watcher.py` | 3 | 간략 있음 | 소 |
| **합계** | **40** | | |

#### 3-3. Pydantic 모델에 예제 추가

**변경 파일**: `backend/app/models/schemas.py`

주요 Request/Response 모델에 `model_config` 예제 추가:

```python
class SearchRequest(BaseModel):
    query: str
    top_k: int = 5
    search_mode: str | None = None
    hyde_enabled: bool | None = None
    reranking_enabled: bool | None = None
    generate_answer: bool = True

    model_config = ConfigDict(json_schema_extra={
        "examples": [
            {
                "query": "한국의 GDP 성장률은?",
                "top_k": 5,
                "search_mode": "hybrid",
                "generate_answer": True,
            }
        ]
    })
```

**예제 추가 대상 모델**:
- `SearchRequest`, `SearchResponse`
- `SignupRequest`, `LoginRequest`, `TokenResponse`
- `DocumentResponse`, `DocumentListResponse`
- `SettingsResponse`, `SettingsUpdateRequest`
- `DatasetCreateRequest`, `DatasetItemSchema`
- `HealthResponse`
- `AdminCreateUserRequest`

#### 3-4. 에러 코드 정의서 작성

**신규 파일**: `docs/api/error-codes.md`

위 API 설계 섹션의 에러 코드 테이블을 독립 문서로 작성. 각 에러 코드에 대해:
- HTTP 상태 코드
- 에러 코드 문자열
- 설명
- 발생 조건
- 해결 방법
- **사용자 안내 메시지 (프론트엔드 권장 표시 문구)**

> 은지(기획자) 리뷰 반영: 개발자용 설명뿐 아니라 프론트엔드가 사용자에게 보여줄 권장 메시지를 에러 코드별로 명시한다.

**에러 코드 정의서 포함 컬럼 예시**:

| 에러 코드 | HTTP | 설명 | 사용자 안내 메시지 (국문) |
|-----------|------|------|--------------------------|
| `VALIDATION_ERROR` | 400 | 요청 파라미터 유효성 실패 | "입력 내용을 확인해주세요." |
| `TOKEN_EXPIRED` | 401 | JWT 토큰 만료 | "로그인이 만료되었습니다. 다시 로그인해주세요." |
| `INTERNAL_ERROR` | 500 | 서버 내부 오류 | "일시적인 오류가 발생했습니다. 잠시 후 다시 시도해주세요." |
| `SERVICE_UNAVAILABLE` | 503 | 외부 서비스 연결 실패 | "서비스 점검 중입니다. 잠시 후 다시 시도해주세요." |

#### 3-5. FastAPI 앱 메타데이터 보강

**변경 파일**: `backend/app/main.py`

```python
app = FastAPI(
    title="UrstoryRAG API",
    description="한국어 특화 RAG(Retrieval-Augmented Generation) 시스템 API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {"name": "health", "description": "시스템 상태 확인"},
        {"name": "auth", "description": "인증 및 사용자 관리"},
        {"name": "search", "description": "문서 검색 및 답변 생성"},
        {"name": "documents", "description": "문서 업로드/관리"},
        {"name": "settings", "description": "RAG 설정 관리"},
        {"name": "evaluation", "description": "RAG 품질 평가"},
        {"name": "admin", "description": "관리자 전용 기능"},
        {"name": "monitoring", "description": "시스템 모니터링"},
        {"name": "system", "description": "시스템 정보"},
        {"name": "watcher", "description": "디렉토리 감시"},
    ],
)
```

#### 3-6. 검증 방법

```bash
# Swagger UI에서 시각적 확인
open http://localhost:8000/docs

# OpenAPI 스키마 JSON 검증
curl -s http://localhost:8000/openapi.json | python -m json.tool > /dev/null && echo "Valid JSON"

# 에러 응답 스키마가 포함되었는지 확인
curl -s http://localhost:8000/openapi.json | python -c "
import json, sys
schema = json.load(sys.stdin)
components = schema.get('components', {}).get('schemas', {})
assert 'ErrorResponse' in components, 'ErrorResponse schema missing'
print('ErrorResponse schema found')
"
```

---

## TDD 구현 전략

### Issue #11 (커넥션 풀링) — TDD 적용

```python
# tests/test_config_pool.py

class TestPoolConfiguration:
    """RED: 커넥션 풀 설정 환경변수가 config에 반영되는지 테스트"""

    def test_default_db_pool_size(self):
        """기본 DB 풀 사이즈는 10"""
        settings = Settings()
        assert settings.db_pool_size == 10

    def test_custom_db_pool_size(self, monkeypatch):
        """환경변수로 DB 풀 사이즈 오버라이드"""
        monkeypatch.setenv("DB_POOL_SIZE", "20")
        settings = Settings()
        assert settings.db_pool_size == 20

    def test_db_pool_pre_ping_default_true(self):
        """pool_pre_ping 기본값은 True"""
        settings = Settings()
        assert settings.db_pool_pre_ping is True

    def test_redis_max_connections_default(self):
        """Redis 기본 max_connections는 20"""
        settings = Settings()
        assert settings.redis_max_connections == 20

    def test_es_request_timeout_default(self):
        """ES 기본 request timeout은 30초"""
        settings = Settings()
        assert settings.es_request_timeout == 30.0
```

### Issue #14 (API 문서) — 스키마 검증 테스트

```python
# tests/test_api_docs.py

class TestAPIDocumentation:
    """API 문서가 올바르게 생성되는지 검증"""

    @pytest.fixture
    def openapi_schema(self, client):
        response = client.get("/openapi.json")
        return response.json()

    def test_error_response_schema_exists(self, openapi_schema):
        """ErrorResponse 스키마가 OpenAPI에 포함"""
        schemas = openapi_schema["components"]["schemas"]
        assert "ErrorResponse" in schemas

    def test_search_endpoint_has_error_responses(self, openapi_schema):
        """검색 엔드포인트에 에러 응답 코드 문서화"""
        search_path = openapi_schema["paths"]["/api/search"]["post"]
        assert "429" in search_path["responses"]

    def test_all_endpoints_have_summary(self, openapi_schema):
        """모든 엔드포인트에 summary가 있음"""
        for path, methods in openapi_schema["paths"].items():
            for method, spec in methods.items():
                if method in ("get", "post", "put", "patch", "delete"):
                    assert "summary" in spec, f"{method.upper()} {path} missing summary"
```

### Issue #14 (API 문서) -- 예외 핸들러 ErrorResponse 통합 테스트

```python
# tests/test_error_response_format.py

class TestErrorResponseFormat:
    """기존 예외 핸들러가 ErrorResponse 스키마를 반환하는지 검증"""

    async def test_rag_exception_returns_error_response_format(self, async_client):
        """RAGException 발생 시 ErrorResponse 형식 응답"""
        response = await async_client.post("/api/search", json={"query": ""})
        data = response.json()
        assert "status" in data
        assert "error" in data
        assert "message" in data
        assert "request_id" in data

    async def test_unhandled_exception_returns_error_response_format(self, async_client):
        """예상치 못한 예외도 ErrorResponse 형식으로 반환"""
        # 의도적으로 잘못된 요청으로 500 유도
        data = response.json()
        assert data["status"] == 500
        assert "request_id" in data

    async def test_validation_error_returns_error_response_format(self, async_client):
        """Pydantic 유효성 검사 실패도 ErrorResponse 형식으로 반환"""
        response = await async_client.post("/api/search", json={"invalid_field": 123})
        data = response.json()
        assert "status" in data
        assert "error" in data
```

---

## 테스트 시나리오

| # | 시나리오 | 검증 방법 | Step |
|---|---------|----------|------|
| T-1 | Dependabot 설정 파일 YAML 유효성 | `python -c "import yaml; ..."` | 1 |
| T-2 | pip-audit가 CI에서 실행됨 | GitHub Actions 로그 확인 | 1 |
| T-3 | pyproject.toml 상한 버전이 현재 설치 버전과 호환 | `pip install -e ".[dev]"` 성공 | 1 |
| T-4 | DB 풀 설정 환경변수 오버라이드 | pytest 단위 테스트 | 2 |
| T-5 | pool_pre_ping으로 끊어진 연결 자동 복구 | DB 재시작 후 API 호출 | 2 |
| T-6 | ES httpx 클라이언트 재사용 | 검색 2회 연속 호출 후 TCP 연결 수 확인 | 2 |
| T-7 | Redis 풀 설정 적용 | redis.connection_pool 속성 확인 | 2 |
| T-8 | 헬스체크에 풀 상태 포함 | `GET /api/health` 응답 확인 | 2 |
| T-9 | Swagger UI에 에러 응답 코드 표시 | 브라우저에서 `/docs` 확인 | 3 |
| T-10 | OpenAPI 스키마에 ErrorResponse 포함 | pytest 스키마 검증 | 3 |
| T-11 | 모든 엔드포인트에 summary 존재 | pytest 자동 검증 | 3 |
| T-12 | Request/Response 예제 표시 | Swagger UI에서 "Example Value" 확인 | 3 |
| T-13 | 기존 예외 핸들러가 ErrorResponse 형식 반환 | 잘못된 요청 시 `status`, `error`, `message`, `request_id` 필드 확인 | 3 |
| T-14 | pip-audit 예외 파일 동작 확인 | `.pip-audit-ignore`에 등록된 취약점이 CI 실패를 일으키지 않음 | 1 |
| T-15 | Trivy 스캔 CI 통합 | GitHub Actions에서 Trivy 스캔이 실행되고 결과 출력 | 1 |

---

## 의존성

### 신규 의존성

| 패키지 | 용도 | 설치 위치 |
|--------|------|----------|
| `pip-audit` | Python 의존성 보안 감사 | CI only (dev 의존성 불필요) |
| `aquasecurity/trivy-action@0.28.0` | Docker/OS 취약점 스캔 | GitHub Actions only |

### 기존 의존성 변경

- `pyproject.toml`: 버전 상한 추가 (기능 변경 없음)

### 외부 서비스

- GitHub Dependabot: GitHub 기본 제공 (추가 비용 없음)

---

## 예상 이슈 및 해결 방안

| # | 이슈 | 영향 | 해결 방안 |
|---|------|------|----------|
| R-1 | pyproject.toml 상한 추가 시 기존 설치와 충돌 | 빌드 실패 | `pip install -e ".[dev]"` 로 사전 검증, 충돌 시 상한 완화 |
| R-2 | pip-audit가 알려진 취약점 발견 | CI 실패 | 해결 불가능한 취약점은 `--ignore-vuln` 으로 예외 처리 후 이슈 추적 |
| R-3 | ES httpx 영속 클라이언트가 연결 끊김 시 에러 | 검색 실패 | 기존 retry 로직이 재연결 처리. `limits.keepalive_expiry` 설정 |
| R-4 | pool_pre_ping으로 인한 SELECT 1 오버헤드 | 미미한 지연 | 연결당 <1ms, 안정성 대비 무시 가능 |
| R-5 | Dependabot PR이 너무 많이 생성됨 | 리뷰 부담 | `groups`로 관련 패키지 묶음, `open-pull-requests-limit: 10` |
| R-6 | pip-audit가 패치 미출시 취약점을 감지하여 CI 무기한 중단 | 배포 불가 | `.pip-audit-ignore`에 사유와 추적 이슈를 기록하여 예외 처리 |
| R-7 | Trivy 스캔에서 베이스 이미지 취약점 발견 | CI 실패 | 베이스 이미지 업데이트 또는 `.trivyignore`로 예외 처리 |

---

## 구현 순서 및 예상 작업량

```
Step 1: 의존성 관리 (#19)     ━━━━━━━━ 설정 파일만 → 가장 빠름
Step 2: 커넥션 풀링 (#11)     ━━━━━━━━━━━━ config + 3개 파일 수정
Step 3: API 문서 강화 (#14)   ━━━━━━━━━━━━━━━━━━ 40개 엔드포인트 반복 작업
```

---

## 다음 단계

1. `/start-phase 16` 으로 브랜치 생성 및 개발 시작
2. Step 1 (의존성) → Step 2 (풀링) → Step 3 (문서) 순서로 구현
3. 각 Step 완료 시 테스트 실행으로 검증
4. 전체 완료 후 `/finish-phase 16` 으로 머지 및 README 반영
