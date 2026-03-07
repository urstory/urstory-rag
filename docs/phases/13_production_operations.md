# Phase 13: 프로덕션 운영 기반 구축

> Issues: #6 구조화된 로깅, #8 에러 추적(Sentry), #9 Graceful Shutdown/Probe, #5 Docker 최적화
> 에이전트 팀: 은지(기획), 민수(보안), 지훈(백엔드), 소연(프론트엔드), 현우(DevOps)

---

## 기획자 리뷰 (은지)

이 문서의 초안을 사용자 관점에서 리뷰한 결과, 다음 문제를 발견했다.

### 지적 1: 에러가 발생하면 사용자는 뭘 보나?

초안에는 Sentry로 에러를 **수집**하는 계획만 있고, 사용자가 에러를 **경험**하는 시나리오가 빠져 있다.

- 검색 중 Elasticsearch가 죽으면? → 현재 500 에러 JSON이 그대로 노출됨
- `global-error.tsx`에 "오류가 발생했습니다" 한 줄과 "다시 시도" 버튼만 있음. 사용자가 관리자에게 뭘 신고해야 하는지 모름

**수정**: 에러 화면에 `request_id`를 표시하고, "이 코드를 관리자에게 전달해 주세요" 안내 추가. 백엔드 에러 응답에도 `request_id` 포함.

### 지적 2: Shutdown 메시지가 기술 용어

"서버가 종료 중입니다"는 사용자에게 불안감을 준다. 사용자는 서버가 뭔지 모른다.

**수정**: "시스템 업데이트 중입니다. 잠시 후 다시 시도해 주세요."로 변경. `Retry-After` 헤더 추가.

### 지적 3: 시스템 상태 UI가 너무 간소

"상태 카드", "자동 새로고침" 한 줄씩만 적혀 있다. 구현자가 이걸 보고 무엇을 만들어야 하는지 모른다.

**수정**: 화면에 표시할 정보 목록, 상태별 색상 규칙, 비정상 시 안내 문구를 구체적으로 정의.

### 지적 4: 버전 정보가 없다

사용자가 "지금 어떤 버전이 돌아가고 있지?"를 확인할 방법이 없다. 운영 중 문제 보고 시 버전 정보는 필수.

**수정**: `/api/health` 응답과 시스템 상태 UI에 백엔드/프론트엔드 버전 표시 추가.

### 지적 5: 프론트엔드 서비스 다운 시 사용자 경험 누락

백엔드 API가 응답하지 않을 때 프론트엔드에서 어떤 화면을 보여주는지 정의가 없다.

**수정**: API 연결 실패 시 프론트엔드에 "서비스 연결 중..." 재시도 화면 추가.

---

## 에이전트 팀 논의 요약

**은지**: "이 Phase의 모든 기능은 결국 '문제가 생겼을 때 사용자와 관리자가 빠르게 상황을 파악하고 대응할 수 있는가'가 핵심이다. 로그, Sentry, Probe는 관리자 도구이고, 에러 화면과 상태 UI는 사용자 도구다. 둘 다 빠지면 안 된다."

**지훈**: "4개 이슈를 의존성 순서대로 정리하면 로깅(#6) → Sentry(#8) → Shutdown/Probe(#9) → Docker(#5)다. 로깅이 모든 운영 기능의 기반이니까 먼저 가야 한다."

**민수**: "structlog에서 민감 정보 마스킹 빠지면 안 된다. API Key, 비밀번호, JWT 토큰 로그에 찍히는 순간 보안 사고다. 그리고 Sentry DSN은 반드시 환경변수로."

**소연**: "은지 말이 맞다. global-error.tsx를 제대로 만들겠다. request_id 표시하고, 에러 유형별로 다른 안내 메시지를 보여주는 게 맞다."

**현우**: "Docker 이미지는 CI에서 자동 빌드+푸시까지 연결해야 의미가 있다. GHCR 연동하고 semver+SHA 태깅까지 넣겠다."

---

## 실행 순서 및 의존성

```
Step 1: 구조화된 로깅 (#6)         ← 모든 운영 기능의 기반
   ↓
Step 2: Sentry 에러 추적 (#8)      ← structlog 위에 에러 보고 레이어
   ↓                                 + 사용자 에러 화면 개선 (은지 지적 1)
Step 3: Graceful Shutdown (#9)     ← 안정적 배포의 전제조건
   ↓                                 + 사용자 친화적 점검 안내 (은지 지적 2)
Step 4: Docker 최적화 (#5)         ← 위 모든 기능이 포함된 최종 이미지
   ↓
Step 5: 시스템 상태 UI (추가)       ← 관리자가 운영 상태를 확인하는 화면
                                     + 버전 정보, API 연결 실패 대응 (은지 지적 3,4,5)
```

---

## Step 1: 구조화된 로깅 시스템 — structlog (#6)

> 담당: 지훈(구현) + 민수(마스킹 검증)

### 1.1 의존성 추가

```toml
# backend/pyproject.toml
dependencies = [
    ...
    "structlog>=24.1.0",
]
```

### 1.2 structlog 설정 모듈

```python
# backend/app/logging_config.py
import logging
import re
import structlog

# 민감 정보 마스킹 패턴 (민수 요구사항)
SENSITIVE_PATTERNS = [
    (re.compile(r'(sk-[a-zA-Z0-9]{20,})'), '***API_KEY***'),
    (re.compile(r'(eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,})'), '***JWT***'),
    (re.compile(r'("?password"?\s*[:=]\s*)"[^"]*"'), r'\1"***"'),
    (re.compile(r'(Bearer\s+)\S+'), r'\1***'),
]

def mask_sensitive(_, __, event_dict):
    """로그 이벤트에서 민감 정보를 마스킹한다."""
    msg = event_dict.get("event", "")
    if isinstance(msg, str):
        for pattern, replacement in SENSITIVE_PATTERNS:
            msg = pattern.sub(replacement, msg)
        event_dict["event"] = msg
    return event_dict

def setup_logging(log_level: str = "INFO", json_format: bool = True):
    """structlog + stdlib logging 통합 설정."""
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        mask_sensitive,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if json_format:
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
        foreign_pre_chain=shared_processors,
    )

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # uvicorn 로그도 structlog으로 통합
    for name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
        uv_logger = logging.getLogger(name)
        uv_logger.handlers.clear()
        uv_logger.propagate = True
```

### 1.3 Settings 확장

```python
# backend/app/config.py — Settings 클래스에 추가
log_level: str = "INFO"           # DEBUG, INFO, WARNING, ERROR
log_format: str = "json"          # json (프로덕션) | console (개발)
```

### 1.4 요청/응답 로깅 미들웨어

```python
# backend/app/middleware/logging.py
import time
import uuid
import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = structlog.get_logger()

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())[:8]
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )

        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception as exc:
            elapsed_ms = round((time.perf_counter() - start) * 1000, 1)
            logger.error(
                "request_failed",
                elapsed_ms=elapsed_ms,
                error=str(exc),
            )
            raise

        elapsed_ms = round((time.perf_counter() - start) * 1000, 1)

        logger.info(
            "request_completed",
            status_code=response.status_code,
            elapsed_ms=elapsed_ms,
        )
        response.headers["X-Request-ID"] = request_id
        return response
```

### 1.5 에러 응답에 request_id 포함 (은지 지적 1)

```python
# backend/app/main.py — RAGException 핸들러 수정
@app.exception_handler(RAGException)
async def rag_exception_handler(request: Request, exc: RAGException):
    request_id = request.headers.get("X-Request-ID", "unknown")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.error_code,
            "message": str(exc),
            "request_id": request_id,
        },
    )

# 미처리 예외 핸들러 추가
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    import structlog
    logger = structlog.get_logger()
    request_id = request.headers.get("X-Request-ID", "unknown")
    logger.error("unhandled_exception", error=str(exc), request_id=request_id)
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_error",
            "message": "내부 오류가 발생했습니다.",
            "request_id": request_id,
        },
    )
```

**은지**: "이제 사용자가 에러를 만나면 request_id를 받는다. 이걸 관리자에게 전달하면 structlog에서 해당 요청의 전체 로그를 추적할 수 있다."

### 1.6 main.py 통합

```python
# backend/app/main.py — lifespan 시작 부분에 추가
from app.logging_config import setup_logging

@asynccontextmanager
async def lifespan(app: FastAPI):
    env = get_settings()
    setup_logging(
        log_level=env.log_level,
        json_format=(env.log_format == "json"),
    )
    ...
```

미들웨어 등록:

```python
# main.py — 미들웨어 섹션
from app.middleware.logging import RequestLoggingMiddleware
app.add_middleware(RequestLoggingMiddleware)
```

### 1.7 기존 logger 마이그레이션

기존 `logging.getLogger(__name__)` 호출을 `structlog.get_logger()`로 교체.
structlog이 stdlib과 통합되므로 기존 코드도 자동으로 JSON 포맷이 적용되지만, 새 코드에서는 structlog 직접 사용.

### 1.8 테스트

```
tests/unit/test_logging_config.py
- test_mask_sensitive_api_key: API 키 마스킹 확인
- test_mask_sensitive_jwt: JWT 토큰 마스킹 확인
- test_mask_sensitive_password: 비밀번호 마스킹 확인
- test_mask_sensitive_bearer: Bearer 토큰 마스킹 확인
- test_setup_logging_json: JSON 포맷 설정 확인
- test_setup_logging_console: Console 포맷 설정 확인

tests/unit/test_request_logging_middleware.py
- test_request_id_header: X-Request-ID 헤더 존재 확인
- test_request_log_output: 로그에 method, path, status_code, elapsed_ms 포함 확인
- test_error_response_includes_request_id: 에러 응답에 request_id 포함 확인
- test_unhandled_exception_returns_request_id: 미처리 예외에도 request_id 반환 확인
```

### 검증 명령어

```bash
cd backend && python -m pytest tests/unit/test_logging_config.py tests/unit/test_request_logging_middleware.py -v
```

---

## Step 2: 에러 추적 시스템 — Sentry + 사용자 에러 화면 (#8)

> 담당: 지훈(백엔드) + 소연(프론트엔드 에러 UI) + 민수(DSN 보안 검증)
> 은지 리뷰 반영: 에러 수집뿐 아니라 사용자가 보는 에러 화면도 함께 개선

### 2.1 설계 결정

**민수**: "Sentry는 셀프호스팅 대신 SaaS(sentry.io)를 기본으로 한다. DSN은 환경변수로만 설정하고, 미설정 시 no-op. Langfuse와 같은 패턴."

**소연**: "프론트엔드 소스맵은 프로덕션 빌드에서만 업로드한다. 개발 환경에서는 Sentry 비활성화."

**은지**: "에러 화면에 request_id를 보여주고, '이 코드를 관리자에게 전달해 주세요'라고 안내해야 한다. '오류가 발생했습니다' 한 줄은 사용자에게 아무 도움이 안 된다."

### 2.2 백엔드 의존성 및 설정

```toml
# backend/pyproject.toml
dependencies = [
    ...
    "sentry-sdk[fastapi]>=2.0.0",
]
```

```python
# backend/app/config.py — Settings에 추가
sentry_dsn: str = ""              # 미설정 시 Sentry 비활성화
sentry_environment: str = "development"  # development | staging | production
sentry_traces_sample_rate: float = 0.1   # 트레이싱 샘플링 10%
```

### 2.3 백엔드 Sentry 초기화

```python
# backend/app/sentry_config.py
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
import structlog

logger = structlog.get_logger()

def init_sentry(dsn: str, environment: str, traces_sample_rate: float):
    """Sentry SDK 초기화. DSN이 비어있으면 no-op."""
    if not dsn:
        logger.info("sentry_disabled", reason="SENTRY_DSN not set")
        return

    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        traces_sample_rate=traces_sample_rate,
        integrations=[
            FastApiIntegration(transaction_style="endpoint"),
            SqlalchemyIntegration(),
        ],
        send_default_pii=False,  # 민수: PII 전송 차단
        before_send=_before_send,
    )
    logger.info("sentry_initialized", environment=environment)

def _before_send(event, hint):
    """Sentry로 전송하기 전에 민감 정보 제거."""
    # request 데이터에서 Authorization 헤더 제거
    if "request" in event and "headers" in event["request"]:
        headers = event["request"]["headers"]
        event["request"]["headers"] = {
            k: ("***" if k.lower() in ("authorization", "cookie") else v)
            for k, v in headers.items()
        }
    return event
```

### 2.4 main.py 통합

```python
# lifespan 시작 부분, setup_logging 직후
from app.sentry_config import init_sentry

init_sentry(
    dsn=env.sentry_dsn,
    environment=env.sentry_environment,
    traces_sample_rate=env.sentry_traces_sample_rate,
)
```

### 2.5 프론트엔드 Sentry

```bash
# frontend/
pnpm add @sentry/nextjs
```

```typescript
// frontend/src/lib/sentry.ts
import * as Sentry from "@sentry/nextjs";

export function initSentry() {
  const dsn = process.env.NEXT_PUBLIC_SENTRY_DSN;
  if (!dsn) return;

  Sentry.init({
    dsn,
    environment: process.env.NEXT_PUBLIC_SENTRY_ENVIRONMENT || "development",
    tracesSampleRate: 0.1,
    sendDefaultPii: false,
  });
}
```

### 2.6 사용자 에러 화면 개선 (은지 지적 1 반영)

**은지**: "에러 화면은 세 가지 정보를 보여줘야 한다: (1) 무슨 상황인지, (2) 사용자가 할 수 있는 행동, (3) 관리자에게 전달할 정보."

```typescript
// frontend/src/app/global-error.tsx
"use client";
import * as Sentry from "@sentry/nextjs";
import { useEffect, useState } from "react";

export default function GlobalError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  const [errorId] = useState(() => error.digest || crypto.randomUUID().slice(0, 8));

  useEffect(() => {
    Sentry.captureException(error, { tags: { errorId } });
  }, [error, errorId]);

  return (
    <html>
      <body className="flex min-h-screen items-center justify-center bg-gray-50 p-4">
        <div className="max-w-md text-center space-y-4">
          <h2 className="text-xl font-semibold text-gray-900">
            예상치 못한 오류가 발생했습니다
          </h2>
          <p className="text-gray-600">
            일시적인 문제일 수 있습니다. 아래 버튼을 눌러 다시 시도해 주세요.
          </p>
          <button
            onClick={reset}
            className="rounded-md bg-blue-600 px-4 py-2 text-white hover:bg-blue-700"
          >
            다시 시도
          </button>
          <div className="border-t pt-4 mt-4">
            <p className="text-sm text-gray-400">
              문제가 계속되면 관리자에게 아래 코드를 전달해 주세요.
            </p>
            <code className="text-sm font-mono text-gray-500 select-all">
              {errorId}
            </code>
          </div>
        </div>
      </body>
    </html>
  );
}
```

### 2.7 API 연결 실패 시 프론트엔드 대응 (은지 지적 5 반영)

**은지**: "백엔드가 응답하지 않을 때 fetch에서 에러가 나면, 사용자는 빈 화면이나 깨진 UI를 본다. API 호출 실패를 공통으로 잡아서 안내 화면을 보여줘야 한다."

```typescript
// frontend/src/lib/api.ts — fetch 래퍼에 연결 실패 처리 추가
export class ApiConnectionError extends Error {
  constructor() {
    super("서비스에 연결할 수 없습니다.");
    this.name = "ApiConnectionError";
  }
}

export async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  try {
    const res = await fetch(`${API_BASE}${path}`, {
      ...options,
      credentials: "include",
    });

    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      const err = new Error(body.message || `HTTP ${res.status}`);
      (err as any).status = res.status;
      (err as any).requestId = body.request_id;
      throw err;
    }

    return res.json();
  } catch (err) {
    if (err instanceof TypeError && err.message.includes("fetch")) {
      throw new ApiConnectionError();
    }
    throw err;
  }
}
```

```typescript
// frontend/src/components/error/api-error-fallback.tsx
"use client";

interface Props {
  error: Error;
  retry?: () => void;
}

export function ApiErrorFallback({ error, retry }: Props) {
  const isConnectionError = error.name === "ApiConnectionError";
  const requestId = (error as any).requestId;

  return (
    <div className="rounded-lg border border-red-200 bg-red-50 p-6 text-center space-y-3">
      <p className="font-medium text-red-800">
        {isConnectionError
          ? "서비스에 연결할 수 없습니다. 잠시 후 다시 시도해 주세요."
          : error.message || "요청을 처리하지 못했습니다."}
      </p>
      {retry && (
        <button
          onClick={retry}
          className="rounded-md bg-red-600 px-4 py-2 text-sm text-white hover:bg-red-700"
        >
          다시 시도
        </button>
      )}
      {requestId && (
        <p className="text-xs text-red-400">
          오류 코드: <code className="select-all">{requestId}</code>
        </p>
      )}
    </div>
  );
}
```

### 2.8 환경변수

```dotenv
# .env.example에 추가
SENTRY_DSN=                          # Sentry DSN (미설정 시 비활성화)
SENTRY_ENVIRONMENT=development       # development | staging | production

# frontend용
NEXT_PUBLIC_SENTRY_DSN=
NEXT_PUBLIC_SENTRY_ENVIRONMENT=development
```

### 2.9 테스트

```
tests/unit/test_sentry_config.py
- test_init_sentry_no_dsn: DSN 없을 때 no-op 확인
- test_init_sentry_with_dsn: DSN 있을 때 초기화 확인 (mock)
- test_before_send_strips_auth: Authorization 헤더 제거 확인
- test_before_send_strips_cookie: Cookie 헤더 제거 확인
```

### 검증 명령어

```bash
cd backend && python -m pytest tests/unit/test_sentry_config.py -v
cd frontend && pnpm build  # Sentry 통합 + 에러 UI 빌드 확인
```

---

## Step 3: Graceful Shutdown + Health Probe (#9)

> 담당: 지훈(구현) + 현우(docker-compose healthcheck)
> 은지 리뷰 반영: 사용자 친화적 점검 메시지, Retry-After 헤더

### 3.1 설계 결정

**지훈**: "기존 `/api/health`는 모든 외부 서비스(DB, ES, Redis, OpenAI)를 체크하는 무거운 엔드포인트다. 이걸 용도별로 분리한다."

```
/api/health/live    ← Liveness: 프로세스 살아있나? (200 즉시 반환)
/api/health/ready   ← Readiness: 요청 처리 가능한가? (DB + ES + Redis 확인)
/api/health/startup ← Startup: 초기화 완료됐나? (app.state.ready 플래그)
/api/health         ← 기존 유지: 전체 상세 상태 (관리자 대시보드용, 인증 불필요)
```

**현우**: "OpenAI 체크는 Readiness에서 빼야 한다. 외부 API 장애로 우리 서비스가 내려가면 안 된다."

**은지**: "Readiness에서 503 응답할 때 사용자 프론트엔드에서는 뭐가 보이나? Step 2의 ApiConnectionError로 자연스럽게 연결되는지 확인해야 한다."

→ Readiness 503 시 rag-api 컨테이너가 트래픽에서 빠지므로 프론트엔드는 `fetch failed` → `ApiConnectionError` → "서비스에 연결할 수 없습니다" 화면으로 자연스럽게 연결됨. OK.

### 3.2 Health Probe 구현

```python
# backend/app/api/health.py — 기존 코드에 엔드포인트 추가

@router.get("/health/live")
async def liveness():
    """Liveness Probe — 프로세스 생존 확인."""
    return {"status": "ok"}

@router.get("/health/ready")
async def readiness(request: Request):
    """Readiness Probe — DB, ES, Redis 연결 확인."""
    db_ok = await check_db()
    es_ok = await check_elasticsearch()
    redis_ok = await check_redis()

    all_ok = db_ok and es_ok and redis_ok
    status_code = 200 if all_ok else 503

    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ready" if all_ok else "not_ready",
            "components": {
                "database": "ok" if db_ok else "fail",
                "elasticsearch": "ok" if es_ok else "fail",
                "redis": "ok" if redis_ok else "fail",
            },
        },
    )

@router.get("/health/startup")
async def startup_check(request: Request):
    """Startup Probe — 초기화 완료 확인."""
    ready = getattr(request.app.state, "startup_complete", False)
    return JSONResponse(
        status_code=200 if ready else 503,
        content={"status": "started" if ready else "starting"},
    )
```

### 3.3 Graceful Shutdown

```python
# backend/app/main.py — lifespan 수정

import asyncio

@asynccontextmanager
async def lifespan(app: FastAPI):
    env = get_settings()
    setup_logging(log_level=env.log_level, json_format=(env.log_format == "json"))
    init_sentry(dsn=env.sentry_dsn, ...)
    init_db(env.database_url)

    # ... 기존 초기화 코드 ...

    app.state.startup_complete = True  # Startup Probe용
    app.state.shutting_down = False
    logger.info("application_started")

    yield

    # --- Graceful Shutdown ---
    app.state.shutting_down = True
    app.state.startup_complete = False
    logger.info("graceful_shutdown_started")

    # 1) k8s/docker가 readiness 변경을 감지할 시간
    await asyncio.sleep(1)

    # 2) 리소스 정리
    await settings_session.close()
    app.state.langfuse_monitor.flush()

    # 3) DB 엔진 dispose
    from app.models.database import get_engine
    engine = get_engine()
    if engine:
        await engine.dispose()
        logger.info("db_engine_disposed")

    logger.info("graceful_shutdown_completed")
```

### 3.4 Shutdown 미들웨어 (은지 지적 2 반영)

**은지**: "'서버가 종료 중입니다'는 사용자에게 불안감을 준다. '시스템 업데이트 중입니다'로 바꾸고, Retry-After 헤더를 추가해서 클라이언트가 자동 재시도할 수 있게 해라."

```python
# backend/app/middleware/shutdown.py
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

class ShutdownMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if getattr(request.app.state, "shutting_down", False):
            # health 엔드포인트는 shutdown 중에도 응답
            if request.url.path.startswith("/api/health"):
                return await call_next(request)
            return JSONResponse(
                status_code=503,
                headers={"Retry-After": "30"},
                content={
                    "error": "service_unavailable",
                    "message": "시스템 업데이트 중입니다. 잠시 후 다시 시도해 주세요.",
                },
            )
        return await call_next(request)
```

### 3.5 docker-compose.yml healthcheck

```yaml
# docker-compose.yml — rag-api 서비스에 추가
  rag-api:
    ...
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/health/ready"]
      interval: 10s
      timeout: 5s
      retries: 3
      start_period: 30s
    stop_grace_period: 35s  # graceful shutdown 대기
```

### 3.6 테스트

```
tests/unit/test_health_probes.py
- test_liveness_always_200: liveness 항상 200
- test_readiness_all_ok: 모든 컴포넌트 정상 시 200
- test_readiness_db_down: DB 비정상 시 503
- test_startup_not_ready: startup_complete=False 시 503
- test_startup_ready: startup_complete=True 시 200

tests/unit/test_shutdown_middleware.py
- test_normal_request_passes: 정상 상태에서 요청 통과
- test_shutting_down_returns_503: shutdown 중 503 + Retry-After 헤더
- test_shutdown_message_user_friendly: 응답 메시지에 "시스템 업데이트" 포함
- test_health_during_shutdown: shutdown 중에도 health 응답
```

### 검증 명령어

```bash
cd backend && python -m pytest tests/unit/test_health_probes.py tests/unit/test_shutdown_middleware.py -v
```

---

## Step 4: Docker 이미지 최적화 + 레지스트리 (#5)

> 담당: 현우(주도) + 민수(보안 검증)

### 4.1 백엔드 Dockerfile 최적화

현재 문제점 (민수 지적):
- root 사용자로 실행
- `pip install -e .` 개발 모드 설치
- `.dockerignore` 미비

```dockerfile
# backend/Dockerfile
FROM python:3.12-slim AS builder

WORKDIR /build
RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential && \
    rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN pip install --no-cache-dir --prefix=/install .

FROM python:3.12-slim

# non-root 사용자 (민수 필수 요구사항)
RUN groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /app
COPY --from=builder /install /usr/local
COPY . .

# 불필요 파일 제거 (.dockerignore로도 처리하지만 방어적으로)
RUN rm -rf tests/ .pytest_cache/ __pycache__/

USER appuser
EXPOSE 8000

# graceful shutdown: uvicorn이 SIGTERM 수신
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--workers", "1", "--timeout-graceful-shutdown", "30"]
```

### 4.2 백엔드 .dockerignore

```
# backend/.dockerignore
.venv/
.env
.env.*
tests/
__pycache__/
*.pyc
.pytest_cache/
.mypy_cache/
*.egg-info/
.git/
```

### 4.3 프론트엔드 Dockerfile 최적화

현재 프론트엔드 Dockerfile은 이미 멀티스테이지+standalone이므로 보안만 보강.

```dockerfile
# frontend/Dockerfile
FROM node:22-alpine AS builder
WORKDIR /app
COPY package.json pnpm-lock.yaml ./
RUN corepack enable && pnpm install --frozen-lockfile
COPY . .
RUN pnpm build

FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production

# non-root 사용자
RUN addgroup -S appgroup && adduser -S appuser -G appgroup

COPY --from=builder --chown=appuser:appgroup /app/.next/standalone ./
COPY --from=builder --chown=appuser:appgroup /app/.next/static ./.next/static
COPY --from=builder --chown=appuser:appgroup /app/public ./public

USER appuser
ENV PORT=3000
EXPOSE 3000
CMD ["node", "server.js"]
```

### 4.4 프론트엔드 .dockerignore

```
# frontend/.dockerignore
node_modules/
.next/
.env
.env.*
e2e/
*.test.*
.git/
```

### 4.5 docker-compose.prod.yml 분리

```yaml
# docker-compose.prod.yml — 프로덕션 전용 오버라이드
services:
  rag-api:
    image: ghcr.io/urstory/urstory-rag-api:${TAG:-latest}
    build:
      context: ./backend
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/health/ready"]
      interval: 10s
      timeout: 5s
      retries: 3
      start_period: 30s
    stop_grace_period: 35s
    deploy:
      resources:
        limits:
          memory: 2G
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"
    restart: unless-stopped

  rag-frontend:
    image: ghcr.io/urstory/urstory-rag-frontend:${TAG:-latest}
    build:
      context: ./frontend
    ports:
      - "3500:3000"
    environment:
      NEXT_PUBLIC_API_URL: ${API_URL:-http://rag-api:8000}
    restart: unless-stopped
```

### 4.6 CI/CD — GHCR 자동 빌드+푸시

```yaml
# .github/workflows/ci.yml — docker-build job 확장
  docker-build:
    if: github.ref == 'refs/heads/main'
    needs: [backend-test, frontend-build]
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write
    steps:
      - uses: actions/checkout@v4

      - name: Login to GHCR
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Set image tags
        id: tags
        run: |
          SHA=$(git rev-parse --short HEAD)
          echo "sha_tag=${SHA}" >> $GITHUB_OUTPUT
          echo "date_tag=$(date +%Y%m%d)" >> $GITHUB_OUTPUT

      - name: Build & Push Backend
        uses: docker/build-push-action@v5
        with:
          context: ./backend
          push: true
          tags: |
            ghcr.io/urstory/urstory-rag-api:latest
            ghcr.io/urstory/urstory-rag-api:${{ steps.tags.outputs.sha_tag }}

      - name: Build & Push Frontend
        uses: docker/build-push-action@v5
        with:
          context: ./frontend
          push: true
          tags: |
            ghcr.io/urstory/urstory-rag-frontend:latest
            ghcr.io/urstory/urstory-rag-frontend:${{ steps.tags.outputs.sha_tag }}
```

### 4.7 테스트

```bash
# 이미지 빌드 확인
docker build -t rag-api-test ./backend
docker build -t rag-frontend-test ./frontend

# non-root 실행 확인
docker run --rm rag-api-test whoami
# → appuser

# 이미지 크기 확인
docker images | grep rag-
```

### 검증 명령어

```bash
docker build -t rag-api-test ./backend && docker build -t rag-frontend-test ./frontend
docker run --rm rag-api-test whoami  # appuser 출력 확인
```

---

## Step 5: 시스템 상태 UI + 버전 정보 (추가 기능)

> 담당: 소연(UI) + 지훈(API)
> 은지 리뷰 반영: 구체적 화면 정의, 버전 정보 추가, 비정상 시 안내 문구

### 5.1 사용자 시나리오 (은지 정의)

**시나리오 A**: 관리자가 아침에 출근해서 시스템 상태를 확인한다.
→ 설정 > 시스템 상태 페이지에서 모든 컴포넌트가 초록색인지 한눈에 확인.

**시나리오 B**: 검색이 안 된다는 신고를 받았다.
→ 시스템 상태 페이지에서 Elasticsearch가 빨간색인 것을 즉시 확인.
→ "Elasticsearch 연결 끊김 — Nori 기반 키워드 검색이 비활성화됩니다" 안내를 보고 원인 파악.

**시나리오 C**: "지금 어떤 버전이 돌아가고 있지?"
→ 시스템 상태 페이지 상단에서 백엔드/프론트엔드 버전과 마지막 배포 시각 확인.

### 5.2 백엔드 API 확장

```python
# backend/app/api/health.py — 기존 /api/health 확장
import importlib.metadata

@router.get("/health")
async def health_check():
    """전체 시스템 상태 (관리자 대시보드용)."""
    db_ok = await check_db()
    es_ok = await check_elasticsearch()
    openai_ok = await check_openai()
    redis_ok = await check_redis()

    required_ok = db_ok and es_ok and redis_ok  # OpenAI는 필수가 아님

    return {
        "status": "ok" if required_ok else "degraded",
        "version": _get_version(),
        "components": {
            "database": {
                "status": "connected" if db_ok else "disconnected",
                "required": True,
                "description": "PostgreSQL + PGVector (문서/벡터 저장소)",
                "impact": "disconnected 시 모든 기능 비활성화",
            },
            "elasticsearch": {
                "status": "connected" if es_ok else "disconnected",
                "required": True,
                "description": "Elasticsearch + Nori (키워드 검색)",
                "impact": "disconnected 시 키워드 검색 비활성화",
            },
            "redis": {
                "status": "connected" if redis_ok else "disconnected",
                "required": True,
                "description": "Redis (세션, 작업 큐, 토큰 블랙리스트)",
                "impact": "disconnected 시 로그인/로그아웃 장애 가능",
            },
            "openai": {
                "status": "connected" if openai_ok else "disconnected",
                "required": False,
                "description": "OpenAI API (임베딩, LLM 생성, 평가)",
                "impact": "disconnected 시 검색/답변 생성 불가 (기존 인덱스 검색은 가능)",
            },
        },
    }

def _get_version() -> str:
    """pyproject.toml의 version을 반환한다."""
    try:
        return importlib.metadata.version("urstory-rag")
    except importlib.metadata.PackageNotFoundError:
        return "dev"
```

### 5.3 프론트엔드 시스템 상태 페이지 (은지 지적 3 반영)

```
frontend/src/app/settings/system/page.tsx
```

**은지 요구사항 — 화면에 반드시 포함할 정보:**

| 영역 | 내용 |
|------|------|
| **상단 헤더** | 시스템 전체 상태 배지 (정상/경고), 백엔드 버전, 마지막 확인 시각 |
| **컴포넌트 카드 (4개)** | 이름, 상태 아이콘, 설명, 비정상 시 영향도 표시 |
| **하단** | "30초마다 자동 확인" 표시, 수동 새로고침 버튼 |

**상태별 색상 규칙:**

| 상태 | 색상 | 아이콘 |
|------|------|--------|
| connected | 초록 (`green-500`) | 체크 원 |
| disconnected + required | 빨강 (`red-500`) | X 원 |
| disconnected + !required | 주황 (`amber-500`) | 경고 삼각형 |

**비정상 시 안내 문구 (각 컴포넌트별):**
- Database disconnected: "데이터베이스에 연결할 수 없습니다. 모든 기능이 제한됩니다."
- Elasticsearch disconnected: "검색 엔진에 연결할 수 없습니다. 키워드 검색이 비활성화됩니다."
- Redis disconnected: "캐시 서버에 연결할 수 없습니다. 로그인/로그아웃에 문제가 발생할 수 있습니다."
- OpenAI disconnected: "AI 서비스에 연결할 수 없습니다. 새 문서 임베딩과 답변 생성이 제한됩니다."

### 5.4 프론트엔드 API 클라이언트

```typescript
// frontend/src/lib/api.ts — 추가
export interface ComponentHealth {
  status: "connected" | "disconnected";
  required: boolean;
  description: string;
  impact: string;
}

export interface SystemHealth {
  status: "ok" | "degraded";
  version: string;
  components: Record<string, ComponentHealth>;
}

export async function getSystemHealth(): Promise<SystemHealth> {
  const res = await fetch(`${API_BASE}/api/health`);
  return res.json();
}
```

### 5.5 설정 메뉴에 시스템 상태 링크 추가

기존 설정 페이지 사이드바에 "시스템 상태" 항목 추가 (admin 전용).

### 5.6 테스트

```
tests/unit/test_health_api.py
- test_health_all_connected: 전체 정상 시 status=ok
- test_health_degraded: 필수 컴포넌트 비정상 시 status=degraded
- test_health_openai_down_still_ok: OpenAI만 비정상이면 status=ok (required=false)
- test_health_includes_version: 응답에 version 필드 포함
- test_health_includes_component_description: 각 컴포넌트에 description, impact 포함
```

### 검증 명령어

```bash
cd backend && python -m pytest tests/unit/test_health_api.py -v
cd frontend && pnpm build
```

---

## 환경변수 총정리 (.env.example 추가분)

```dotenv
# === Phase 13 추가 ===

# 로깅
LOG_LEVEL=INFO                       # DEBUG | INFO | WARNING | ERROR
LOG_FORMAT=json                      # json (프로덕션) | console (개발)

# Sentry (미설정 시 비활성화)
SENTRY_DSN=
SENTRY_ENVIRONMENT=development       # development | staging | production
SENTRY_TRACES_SAMPLE_RATE=0.1

# 프론트엔드 Sentry
NEXT_PUBLIC_SENTRY_DSN=
NEXT_PUBLIC_SENTRY_ENVIRONMENT=development
```

---

## 보안 체크리스트 (민수)

- [ ] structlog 마스킹: API Key, JWT, 비밀번호, Bearer 토큰 로그에 노출 안 됨
- [ ] Sentry `send_default_pii=False`: 사용자 개인정보 Sentry로 전송 안 됨
- [ ] Sentry `before_send`: Authorization, Cookie 헤더 제거 확인
- [ ] Dockerfile non-root 실행: `whoami` → `appuser`
- [ ] `.dockerignore`: `.env`, `tests/`, `.git/` 이미지에 포함 안 됨
- [ ] SENTRY_DSN 환경변수만으로 설정 (코드에 하드코딩 없음)
- [ ] 에러 응답에 스택 트레이스 노출 없음 (request_id만 반환)

---

## 사용자 경험 체크리스트 (은지)

- [ ] 에러 응답에 request_id 포함: 사용자가 관리자에게 전달할 수 있는 추적 코드
- [ ] global-error.tsx: "오류 코드를 관리자에게 전달해 주세요" 안내 표시
- [ ] API 연결 실패 시: "서비스에 연결할 수 없습니다" 안내 + 다시 시도 버튼
- [ ] Shutdown 중 메시지: "시스템 업데이트 중입니다" (기술 용어 제거)
- [ ] Shutdown 응답에 Retry-After 헤더 포함
- [ ] 시스템 상태 UI: 각 컴포넌트별 상태 + 비정상 시 영향도 안내
- [ ] 시스템 상태 UI: 백엔드 버전 표시
- [ ] 시스템 상태 UI: 수동 새로고침 버튼 + 30초 자동 갱신

---

## 전체 검증 파이프라인

```bash
# 1. 백엔드 전체 테스트
cd backend && python -m pytest tests/ -v --tb=short

# 2. 프론트엔드 빌드
cd frontend && pnpm build

# 3. Docker 이미지 빌드
docker build -t rag-api-test ./backend
docker build -t rag-frontend-test ./frontend

# 4. non-root 실행 확인
docker run --rm rag-api-test whoami

# 5. CI 통과 확인
git push → GitHub Actions green
```
