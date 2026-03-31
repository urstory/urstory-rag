# Phase 17 개발 계획: OpenAI 호환 API 및 API Key 인증 시스템

## 개요

| 항목 | 내용 |
|------|------|
| Phase | 17 |
| 기능명 | OpenAI 호환 API + API Key 인증 |
| 작성일 | 2026-03-31 |
| 상태 | 계획 |
| 관련 이슈 | #50 |
| 에이전트 팀 | 지훈(백엔드), 민수(보안), 소연(프론트엔드), 은지(기획) |

### 배경 및 문제 상황

**왜 이 Phase가 필요한가?**

현재 UrstoryRAG는 JWT 로그인 기반 인증만 지원한다. 다른 프로젝트에서 RAG를 연동하려면:

1. **로그인 → 토큰 발급 → API 호출**을 직접 구현해야 함
2. JWT는 30분 만료 → 자동 갱신 로직도 필요
3. 응답 형식이 UrstoryRAG 전용 → 각 프로젝트마다 파서 작성 필요
4. LangChain, LlamaIndex 등 프레임워크와 직접 호환 불가

### 목표

- OpenAI SDK의 `base_url`만 변경하면 즉시 연동 가능한 API 제공
- 서버간 연동에 적합한 API Key 인증 시스템 구축
- 기존 JWT 인증과 API Key 인증 공존

### 핵심 해결 방안 요약

```
[기존] 다른 프로젝트 → POST /api/auth/login → JWT 발급 → POST /api/search → 전용 응답 파싱
[신규] 다른 프로젝트 → POST /v1/chat/completions (api_key) → OpenAI 형식 응답 (그대로 사용)
```

---

## 상세 목표

1. **API Key 모델 + CRUD**: `api_keys` 테이블, 발급/폐기/목록 관리
2. **통합 인증 미들웨어**: JWT 또는 API Key를 자동 판별하여 동일한 User 객체 반환
3. **OpenAI Chat Completions 호환 엔드포인트**: `POST /v1/chat/completions`
4. **SSE 스트리밍**: `stream: true` 지원
5. **키별 Rate Limit**: API Key마다 일일 사용량 제한
6. **관리자 UI**: API Key 발급/관리 페이지

---

## 관련 유스케이스

| ID | 유스케이스 명 | 액터 | 설명 |
|----|-------------|------|------|
| UC-1 | API Key 발급 | 관리자 | 관리자 UI에서 이름을 지정하여 API Key 발급. 키는 생성 시 1회만 표시 |
| UC-2 | API Key 폐기 | 관리자 | 유출된 키를 즉시 비활성화 |
| UC-3 | OpenAI SDK로 검색 | 외부 서비스 | `OpenAI(base_url=..., api_key=...)` 으로 RAG 검색+답변 |
| UC-4 | 스트리밍 답변 | 외부 서비스 | `stream=True`로 SSE 기반 실시간 답변 수신 |
| UC-5 | 사용량 확인 | 관리자 | 키별 마지막 사용일, 일일 사용량 모니터링 |
| UC-6 | LangChain 연동 | 외부 서비스 | `ChatOpenAI(base_url=..., api_key=...)`로 체인에 RAG 통합 |

---

## 데이터베이스 스키마

### 신규 테이블: `api_keys`

```python
class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    key_prefix: Mapped[str] = mapped_column(String(12))         # "rag_sk_a3Bf" (관리자 UI 식별용)
    key_hash: Mapped[str] = mapped_column(String(255), unique=True)  # HMAC-SHA256 해시
    name: Mapped[str] = mapped_column(String(200))               # "사내 포털 연동", "테스트용"
    is_active: Mapped[bool] = mapped_column(default=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)  # None이면 무기한
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship()
```

**설계 포인트**:
- `key_hash`: 평문 키를 저장하지 않음 (HMAC-SHA256 + 서버 시크릿). DB 유출 시에도 서버 시크릿 없이 원본 복원 불가
- `key_prefix`: `rag_sk_a3Bf...`의 앞 12자만 저장. 관리자 UI에서 식별용
- `user_id`: 키를 발급한 관리자. 권한은 해당 유저의 role을 따름
- `expires_at`: 키 만료일. None이면 무기한 유효. 발급 시 선택적으로 지정 가능 (기본: 무기한)
- **키 발급 수 제한**: 사용자당 활성 키 최대 10개 (설정으로 조정 가능: `api_key_max_per_user`)
- **권한 범위**: API Key로 인증 시 OpenAI 호환 엔드포인트(`/v1/*`)만 접근 가능. 관리자 API(`/api/admin/*`)는 JWT 인증 필수

---

## API 설계

### API Key 관리 엔드포인트

| Method | Endpoint | 설명 | 권한 |
|--------|----------|------|------|
| POST | `/api/admin/api-keys` | API Key 발급 | admin |
| GET | `/api/admin/api-keys` | API Key 목록 | admin |
| DELETE | `/api/admin/api-keys/{key_id}` | API Key 폐기 | admin |

### OpenAI 호환 엔드포인트

| Method | Endpoint | 설명 | 인증 |
|--------|----------|------|------|
| POST | `/v1/chat/completions` | Chat Completions | API Key 또는 JWT |
| GET | `/v1/models` | 모델 목록 | API Key 또는 JWT |

### Request/Response 형식

#### API Key 발급

```
POST /api/admin/api-keys
Request: { "name": "사내 포털 연동", "expires_in_days": 90 }   ← expires_in_days는 선택 (미지정 시 무기한)
Response: {
  "id": "uuid",
  "name": "사내 포털 연동",
  "key": "rag_sk_a3BfC7dE9xYz...(48자)",   ← 이 필드는 생성 시 1회만 반환
  "key_prefix": "rag_sk_a3Bf",
  "expires_at": "2026-06-29T..." | null,
  "created_at": "2026-03-31T..."
}
```

#### OpenAI Chat Completions

```
POST /v1/chat/completions
Authorization: Bearer rag_sk_a3BfC7dE9xYz...

Request:
{
  "model": "urstory-rag",
  "messages": [
    {"role": "system", "content": "검색 범위를 제한하는 지시 (선택)"},
    {"role": "user", "content": "한국의 GDP 성장률은?"}
  ],
  "stream": false,
  "temperature": 0.3
}

Response:
{
  "id": "chatcmpl-a1b2c3d4e5f6g7h8i9j0k1l2m",
  "object": "chat.completion",
  "created": 1714000000,
  "model": "urstory-rag",
  "system_fingerprint": "rag_abc123def456",
  "choices": [{
    "index": 0,
    "message": {
      "role": "assistant",
      "content": "한국의 2025년 GDP 성장률은 약 1.8%로..."
    },
    "finish_reason": "stop"
  }],
  "usage": {
    "prompt_tokens": 18,
    "completion_tokens": 45,
    "total_tokens": 63
  }
}
```

#### SSE 스트리밍 (`stream: true`)

**현재 제약**: orchestrator가 전체 답변을 한 번에 반환하므로, 1단계에서는 완성된 답변을 청크로 분할하는 "시뮬레이션 스트리밍"을 구현한다. TTFT(Time To First Token)는 전체 생성 시간과 동일하다는 한계가 있다. 향후 orchestrator에 실시간 토큰 스트리밍 모드를 추가하면 자연스럽게 교체 가능한 구조로 설계한다.

**SSE chunk 필수 필드** (OpenAI SDK Pydantic 모델 검증 통과를 위해):
- `id`: 전체 스트림에서 동일한 ID 유지
- `object`: `"chat.completion.chunk"` (고정)
- `model`: 요청에서 받은 모델명 그대로 반환 (필수!)
- `created`: Unix timestamp (필수!)
- `choices[].delta`: content 또는 role 포함

```
data: {"id":"chatcmpl-rag-uuid","object":"chat.completion.chunk","model":"urstory-rag","created":1714000000,"choices":[{"index":0,"delta":{"role":"assistant","content":""},"finish_reason":null}]}

data: {"id":"chatcmpl-rag-uuid","object":"chat.completion.chunk","model":"urstory-rag","created":1714000000,"choices":[{"index":0,"delta":{"content":"한국"},"finish_reason":null}]}

data: {"id":"chatcmpl-rag-uuid","object":"chat.completion.chunk","model":"urstory-rag","created":1714000000,"choices":[{"index":0,"delta":{"content":"의 GDP"},"finish_reason":null}]}

...

data: {"id":"chatcmpl-rag-uuid","object":"chat.completion.chunk","model":"urstory-rag","created":1714000000,"choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}

data: [DONE]
```

**향후 개선 (별도 Phase)**: Haystack 2.x의 스트리밍 콜백을 활용하여 orchestrator에 실제 토큰 단위 스트리밍 구현. 이때 `stream_response()` 함수만 교체하면 되도록 인터페이스를 분리해 둔다.

---

## 인증 흐름 설계

```
Authorization: Bearer <token>
         │
         ▼
get_current_user()  ← 기존 함수 확장
         │
         ├─ rag_sk_ 접두사? ← 반드시 JWT decode보다 먼저 체크
         │   ├─ Yes → HMAC-SHA256 해시 → api_keys 테이블 조회
         │   │         → is_active 체크 → expires_at 체크
         │   │         → user.is_active 체크 → User 반환
         │   └─ No  → JWT 경로 (기존 로직 유지)
         │            → decode_token() → 블랙리스트 체크 → User 반환
         │
         ▼
      User 객체 (JWT든 API Key든 동일)
```

**보안 설계 (민수 리뷰)**:
- API Key는 `rag_sk_` 접두사로 시작 → JWT와 형식 구분 명확
- **접두사 체크를 JWT decode보다 먼저 수행** (기존 decode_token() 호출 전에 분기)
- 평문 키 미저장 (HMAC-SHA256 + 서버 시크릿으로 해시). 단순 SHA-256보다 안전
- 해시 비교 시 **`secrets.compare_digest()` 사용** (타이밍 공격 방지)
- `last_used_at` 갱신은 **Redis에 기록 후 주기적(5분) DB 배치 업데이트** (매 요청 DB write 방지)
- 폐기된 키(`is_active=false`) 및 만료된 키(`expires_at < now`)는 즉시 인증 거부
- 키 생성 시 `secrets.token_urlsafe(36)` 사용 (48바이트 = 256비트 엔트로피)
- API Key 평문은 로그에 절대 기록하지 않음 (로깅 시 key_prefix만 사용)

---

## 단계별 구현 계획

### Step 1: DB 모델 + 마이그레이션

**담당**: 지훈(백엔드)

**변경 파일**:
- `backend/app/models/database.py` — ApiKey 모델 추가
- `backend/alembic/versions/xxxx_add_api_keys_table.py` — 마이그레이션 신규

```bash
cd backend && alembic revision --autogenerate -m "add_api_keys_table"
alembic upgrade head
```

**검증**: 마이그레이션 실행 후 `api_keys` 테이블 생성 확인

### Step 2: API Key 서비스 + 인증 미들웨어

**담당**: 지훈(백엔드), 민수(보안 리뷰)

**신규 파일**:
- `backend/app/services/apikey.py` — 키 생성, 해싱, 검증 서비스

```python
import hmac
import hashlib
import secrets
from datetime import datetime, timezone

from app.config import get_settings

def generate_api_key() -> str:
    """rag_sk_ 접두사 + 48자 랜덤 키 생성."""
    raw = secrets.token_urlsafe(36)
    return f"rag_sk_{raw}"

def hash_api_key(key: str) -> str:
    """HMAC-SHA256 해시. 서버 시크릿을 HMAC 키로 사용하여 단순 SHA-256보다 안전."""
    secret = get_settings().jwt_secret_key.encode()
    return hmac.new(secret, key.encode(), hashlib.sha256).hexdigest()

async def authenticate_api_key(db: AsyncSession, key: str) -> User | None:
    """API Key로 유저 조회. 타이밍 공격 방지를 위해 secrets.compare_digest 사용."""
    key_hash = hash_api_key(key)
    result = await db.execute(
        select(ApiKey).options(selectinload(ApiKey.user)).where(
            ApiKey.key_hash == key_hash, ApiKey.is_active == True
        )
    )
    api_key = result.scalar_one_or_none()
    if not api_key:
        return None

    # 타이밍 안전 비교 (DB 조회 결과와 계산 해시 재검증)
    if not secrets.compare_digest(api_key.key_hash, key_hash):
        return None

    # 만료일 체크
    if api_key.expires_at and api_key.expires_at < datetime.now(timezone.utc):
        return None

    # 연결된 유저 활성 상태 체크
    if not api_key.user or not api_key.user.is_active:
        return None

    # last_used_at은 Redis에 기록 (매 요청 DB write 방지)
    redis = await get_redis()
    await redis.set(f"apikey_last_used:{api_key.id}", datetime.now(timezone.utc).isoformat(), ex=600)

    return api_key.user
```

**last_used_at 배치 갱신** (별도 백그라운드 태스크):
```python
async def flush_api_key_last_used(db: AsyncSession):
    """Redis에 저장된 last_used_at을 5분마다 DB에 반영."""
    redis = await get_redis()
    async for key in redis.scan_iter(match="apikey_last_used:*"):
        api_key_id = key.split(":")[-1]
        ts = await redis.get(key)
        if ts:
            await db.execute(
                update(ApiKey).where(ApiKey.id == api_key_id).values(last_used_at=ts)
            )
            await redis.delete(key)
    await db.commit()
```

**변경 파일**:
- `backend/app/dependencies.py` — `get_current_user()` 확장

```python
async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=401, detail="인증이 필요합니다.")

    token = credentials.credentials

    # API Key 판별: rag_sk_ 접두사 → JWT decode보다 먼저 체크 (중요!)
    if token.startswith("rag_sk_"):
        user = await authenticate_api_key(db, token)
        if not user:
            raise HTTPException(status_code=401, detail="유효하지 않은 API Key입니다.")
        return user

    # 기존 JWT 경로 (변경 없음)
    try:
        payload = decode_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="유효하지 않은 토큰입니다.")
    # ... 기존 JWT 검증 로직 유지 ...
```

**주의**: 기존 `get_current_user()` 함수를 수정하므로, **모든 기존 테스트가 통과하는지** 반드시 확인. API Key 분기가 추가되어도 JWT 경로는 완전히 동일하게 유지해야 한다.

**테스트**: 16개 (키 생성, HMAC 해싱, 인증 성공/실패, 폐기된 키 거부, 만료된 키 거부, 비활성 유저 거부, last_used_at Redis 기록, 기존 JWT 인증 정상 동작)

### Step 3: API Key 관리 엔드포인트

**담당**: 지훈(백엔드)

**신규 파일**:
- `backend/app/api/keys.py` — API Key CRUD 라우터

| 엔드포인트 | 동작 |
|-----------|------|
| `POST /api/admin/api-keys` | 키 발급 (평문 키 1회 반환). 활성 키 수 제한 초과 시 400 |
| `GET /api/admin/api-keys` | 키 목록 (prefix만 표시, 만료일, 마지막 사용일 포함) |
| `DELETE /api/admin/api-keys/{id}` | 키 폐기 (is_active=false). Redis 캐시도 즉시 무효화 |

**발급 시 검증**:
- 사용자당 활성 키 수 제한 (기본 10개, `api_key_max_per_user` 설정)
- `name` 필드 필수 (빈 문자열 불가)
- `expires_in_days` 선택 (미지정 시 무기한, 지정 시 현재 시각 + N일)

**변경 파일**:
- `backend/app/models/schemas.py` — Request/Response 스키마 추가
- `backend/app/main.py` — 라우터 등록
- `backend/app/config.py` — `api_key_max_per_user: int = 10` 추가

**테스트**: 9개 (CRUD 통합 테스트, 키 수 초과, 만료일 설정, 빈 이름 거부, 폐기 후 목록 반영)

### Step 4: OpenAI 호환 엔드포인트

**담당**: 지훈(백엔드)

**신규 파일**:
- `backend/app/api/openai_compat.py` — OpenAI 호환 라우터

**orchestrator 공유**: `search.py`의 `get_orchestrator()`, `get_search_settings_service()`를 import하여 동일한 인스턴스를 사용한다.

핵심 로직:
```python
from app.api.search import get_orchestrator, get_search_settings_service

@router.post("/v1/chat/completions")
async def chat_completions(request: OpenAIChatRequest, user = Depends(get_current_user)):
    # 1. messages에서 마지막 user 메시지 추출
    query = next((m.content for m in reversed(request.messages) if m.role == "user"), "")
    if not query:
        return openai_error_response(400, "invalid_request_error", "messages에 user 메시지가 필요합니다.")

    # 2. system 메시지가 있으면 system_prompt로 사용
    system_prompt = next((m.content for m in request.messages if m.role == "system"), None)

    # 3. RAG 검색 실행
    orchestrator = get_orchestrator()
    settings_service = get_search_settings_service()
    settings = await settings_service.get_settings()
    if system_prompt:
        settings = settings.model_copy(update={"system_prompt": system_prompt})

    result = await orchestrator.search(query, settings, generate_answer=True)

    # 4. OpenAI 형식으로 변환
    answer = result.answer or ""
    completion_id = f"chatcmpl-{uuid.uuid4().hex[:29]}"

    if request.stream:
        return StreamingResponse(
            stream_response(answer, completion_id, request.model),
            media_type="text/event-stream",
            headers={"X-Accel-Buffering": "no"},  # nginx 버퍼링 비활성화
        )

    return {
        "id": completion_id,
        "object": "chat.completion",
        "created": int(time.time()),
        "model": request.model,
        "system_fingerprint": f"rag_{hashlib.md5(settings.model_dump_json().encode()).hexdigest()[:12]}",
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": answer},
            "finish_reason": "stop",
        }],
        "usage": {
            "prompt_tokens": _estimate_tokens(query),
            "completion_tokens": _estimate_tokens(answer),
            "total_tokens": _estimate_tokens(query) + _estimate_tokens(answer),
        },
    }

def _estimate_tokens(text: str) -> int:
    """토큰 수 근사 추정. 한국어는 대략 글자당 1.5토큰."""
    return max(1, int(len(text) * 1.5))

def openai_error_response(status_code: int, error_type: str, message: str):
    """OpenAI 표준 에러 응답 형식."""
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "message": message,
                "type": error_type,
                "param": None,
                "code": None,
            }
        },
    )
```

**에러 응답**: OpenAI SDK가 기대하는 에러 형식(`{"error": {"message": ..., "type": ..., "param": ..., "code": ...}}`)을 준수해야 한다. 기존 UrstoryRAG 에러 형식과 다르므로 `/v1/*` 경로에 별도 예외 핸들러를 등록한다.

**변경 파일**:
- `backend/app/models/schemas.py` — OpenAI 호환 스키마 (Request/Response/Error)
- `backend/app/main.py` — `/v1` 라우터 등록 + OpenAI 형식 예외 핸들러
- `backend/app/api/search.py` — `get_orchestrator()`, `get_search_settings_service()` 외부 공개 유지 확인

**테스트**: 10개 (정상 응답, 스트리밍, system 메시지, 빈 메시지, user 메시지 없음 에러, 모델 목록, OpenAI 에러 형식, usage 필드 검증, SDK 실제 파싱 검증)

### Step 5: 프론트엔드 — API Key 관리 페이지

**담당**: 소연(프론트엔드)

**신규 파일**:
- `frontend/src/app/settings/api-keys/page.tsx` — 페이지
- `frontend/src/components/settings/api-keys-manager.tsx` — 키 목록 + 발급 컴포넌트

**변경 파일**:
- `frontend/src/lib/api.ts` — `api.admin.apiKeys.*` 추가
- `frontend/src/app/settings/page.tsx` — API Keys 카드 추가

**UI 구성**:
- 키 목록 테이블: 이름, 접두사(`rag_sk_a3Bf...`), 생성일, 만료일, 마지막 사용일, 상태
  - 만료된 키는 시각적으로 구분 (회색 처리 + "만료됨" 뱃지)
  - 빈 상태(키 0개): "API Key가 없습니다. 새 키를 발급하세요" 안내 문구 + 발급 버튼
- 발급 버튼 → 모달:
  - 이름 입력 (필수)
  - 만료일 선택 (선택: 30일/90일/1년/무기한)
  - 생성 후: 키 표시 영역 (모노스페이스 폰트, 마스킹 토글 가능)
  - **"복사 완료" 버튼** 클릭 또는 Clipboard API로 복사 완료 감지 후에만 "닫기" 버튼 활성화
  - 경고 문구: "이 키는 다시 확인할 수 없습니다. 반드시 복사한 후 안전한 곳에 저장하세요."
  - 복사하지 않고 닫으려 하면 확인 다이얼로그: "키를 복사하셨나요? 닫으면 다시 볼 수 없습니다."
- 폐기 버튼 (확인 다이얼로그: "이 키를 폐기하면 사용 중인 모든 연동이 중단됩니다.")

### Step 6: 키별 Rate Limit + 사용량

**담당**: 지훈(백엔드), 현우(DevOps)

**변경 파일**:
- `backend/app/config.py` — Rate Limit 설정 추가:
  - `api_key_rate_limit_per_day: int = 1000` (일일 한도)
  - `api_key_rate_limit_per_minute: int = 30` (분당 한도 - Burst 방어)
  - `api_key_max_per_user: int = 10` (사용자당 최대 활성 키 수)
- `backend/app/api/openai_compat.py` — Redis 기반 이중 카운터

```python
async def check_api_key_rate_limit(key_hash: str) -> tuple[bool, str | None]:
    """이중 Rate Limit 체크. (통과 여부, 초과 사유) 반환."""
    redis = await get_redis()
    env = get_settings()

    # 1. 분당 제한 (Burst 방어)
    minute_key = f"apikey_rpm:{key_hash}:{datetime.now().strftime('%Y-%m-%d-%H-%M')}"
    rpm_count = await redis.incr(minute_key)
    if rpm_count == 1:
        await redis.expire(minute_key, 60)
    if rpm_count > env.api_key_rate_limit_per_minute:
        return False, f"분당 {env.api_key_rate_limit_per_minute}회 제한 초과"

    # 2. 일일 제한
    daily_key = f"apikey_daily:{key_hash}:{datetime.now().strftime('%Y-%m-%d')}"
    daily_count = await redis.incr(daily_key)
    if daily_count == 1:
        await redis.expire(daily_key, 86400)
    if daily_count > env.api_key_rate_limit_per_day:
        return False, f"일일 {env.api_key_rate_limit_per_day}회 제한 초과"

    return True, None
```

Rate Limit 초과 시 OpenAI 표준 에러 형식으로 429 응답:
```json
{
  "error": {
    "message": "Rate limit exceeded: 분당 30회 제한 초과",
    "type": "rate_limit_error",
    "param": null,
    "code": "rate_limit_exceeded"
  }
}
```

**참고**: 기존 `slowapi` Rate Limit(IP 기반)은 `/api/*` 경로에서 유지. `/v1/*` 경로는 API Key 기반 커스텀 Rate Limit을 사용. 두 시스템이 공존하며 역할이 다름:
- `slowapi`: 인증 전 IP 기반 방어 (DDoS 수준)
- 커스텀 Redis: 인증 후 키별 사용량 제한 (비즈니스 수준)

---

## TDD 구현 전략

### Step 2 (API Key 서비스) — RED → GREEN

```python
# tests/test_apikey_service.py

class TestApiKeyGeneration:
    def test_key_starts_with_prefix(self):
        key = generate_api_key()
        assert key.startswith("rag_sk_")

    def test_key_length_sufficient(self):
        """48자 이상 = rag_sk_(7자) + urlsafe(48자) = 최소 55자."""
        key = generate_api_key()
        assert len(key) >= 55

    def test_hash_is_deterministic(self):
        """동일 키 → 동일 해시 (HMAC은 서버 시크릿이 같으면 결정적)."""
        key = "rag_sk_test123"
        assert hash_api_key(key) == hash_api_key(key)

    def test_different_keys_different_hashes(self):
        k1 = generate_api_key()
        k2 = generate_api_key()
        assert hash_api_key(k1) != hash_api_key(k2)

    def test_hash_uses_hmac_not_plain_sha256(self):
        """단순 SHA-256과 다른 결과가 나와야 함."""
        import hashlib
        key = "rag_sk_test123"
        plain_sha = hashlib.sha256(key.encode()).hexdigest()
        assert hash_api_key(key) != plain_sha

class TestApiKeyAuth:
    async def test_valid_key_returns_user(self, test_db):
        ...
    async def test_revoked_key_returns_none(self, test_db):
        ...
    async def test_invalid_key_returns_none(self, test_db):
        ...
    async def test_expired_key_returns_none(self, test_db):
        """만료된 키는 인증 거부."""
        ...
    async def test_inactive_user_returns_none(self, test_db):
        """키는 유효하지만 연결된 유저가 비활성인 경우."""
        ...
    async def test_last_used_at_recorded_in_redis(self, test_db, mock_redis):
        """last_used_at이 Redis에 기록되는지 확인."""
        ...
    async def test_jwt_auth_still_works(self, test_db):
        """API Key 분기 추가 후에도 기존 JWT 인증이 정상 동작."""
        ...
```

### Step 4 (OpenAI 엔드포인트) — RED → GREEN

```python
# tests/test_openai_compat.py

class TestChatCompletions:
    async def test_basic_response_format(self, client):
        """응답이 OpenAI ChatCompletion 형식을 준수."""
        resp = await client.post("/v1/chat/completions", json={
            "model": "urstory-rag",
            "messages": [{"role": "user", "content": "테스트 질문"}],
        }, headers={"Authorization": "Bearer rag_sk_test"})
        data = resp.json()
        assert data["object"] == "chat.completion"
        assert data["id"].startswith("chatcmpl-")
        assert "choices" in data
        assert data["choices"][0]["message"]["role"] == "assistant"
        assert data["choices"][0]["finish_reason"] == "stop"

    async def test_usage_field_has_positive_values(self, client):
        """usage 필드가 0이 아닌 근사값을 포함."""
        resp = await client.post("/v1/chat/completions", ...)
        data = resp.json()
        assert data["usage"]["prompt_tokens"] > 0
        assert data["usage"]["total_tokens"] > 0

    async def test_system_fingerprint_present(self, client):
        """system_fingerprint 필드 존재."""
        resp = await client.post("/v1/chat/completions", ...)
        assert "system_fingerprint" in resp.json()

    async def test_error_response_openai_format(self, client):
        """에러 시 OpenAI 표준 형식 반환."""
        resp = await client.post("/v1/chat/completions", json={
            "model": "urstory-rag", "messages": [],
        }, headers={"Authorization": "Bearer rag_sk_test"})
        data = resp.json()
        assert "error" in data
        assert "message" in data["error"]
        assert "type" in data["error"]

    async def test_streaming_chunks_have_required_fields(self, client):
        """SSE chunk에 model, created 필드 포함."""
        ...

    async def test_models_endpoint(self, client):
        resp = await client.get("/v1/models", headers=...)
        assert resp.status_code == 200
        models = resp.json()["data"]
        assert any(m["id"] == "urstory-rag" for m in models)

    async def test_openai_sdk_can_parse_response(self, client):
        """OpenAI Python SDK로 실제 응답을 파싱할 수 있는지 검증."""
        from openai.types.chat import ChatCompletion
        resp = await client.post("/v1/chat/completions", ...)
        ChatCompletion.model_validate(resp.json())  # Pydantic 검증 통과해야 함
```

---

## 테스트 시나리오

| # | 시나리오 | 검증 방법 | Step |
|---|---------|----------|------|
| T-1 | API Key가 rag_sk_ 접두사로 생성, 55자 이상 | 단위 테스트 | 2 |
| T-2 | HMAC-SHA256 해시 (단순 SHA-256과 다른 결과) | 단위 테스트 | 2 |
| T-3 | 유효한 API Key로 인증 성공 | 통합 테스트 | 2 |
| T-4 | 폐기된 API Key로 인증 거부 (401) | 통합 테스트 | 2 |
| T-5 | 만료된 API Key로 인증 거부 (401) | 통합 테스트 | 2 |
| T-6 | 비활성 유저의 API Key로 인증 거부 | 통합 테스트 | 2 |
| T-7 | 존재하지 않는 API Key로 인증 거부 | 통합 테스트 | 2 |
| T-8 | JWT와 API Key 동시 지원 (기존 JWT 인증 미파괴) | 통합 테스트 | 2 |
| T-9 | API Key 발급 시 평문 키 1회 반환 | 통합 테스트 | 3 |
| T-10 | API Key 목록에서 평문 키 미노출 | 통합 테스트 | 3 |
| T-11 | 사용자당 키 수 제한 초과 시 400 | 통합 테스트 | 3 |
| T-12 | 만료일 지정 발급 | 통합 테스트 | 3 |
| T-13 | /v1/chat/completions OpenAI 형식 응답 | 통합 테스트 | 4 |
| T-14 | usage 필드에 양수 토큰 수 포함 | 통합 테스트 | 4 |
| T-15 | system_fingerprint 필드 존재 | 통합 테스트 | 4 |
| T-16 | stream=true SSE 응답 (model, created 필드 포함) | 통합 테스트 | 4 |
| T-17 | system 메시지로 프롬프트 오버라이드 | 통합 테스트 | 4 |
| T-18 | user 메시지 없을 때 OpenAI 에러 형식 반환 | 통합 테스트 | 4 |
| T-19 | /v1/models에 urstory-rag 포함 | 통합 테스트 | 4 |
| T-20 | OpenAI Python SDK로 실제 호출 + Pydantic 파싱 | E2E 테스트 | 4 |
| T-21 | 분당 Rate Limit 초과 시 429 | 통합 테스트 | 6 |
| T-22 | 일일 Rate Limit 초과 시 429 | 통합 테스트 | 6 |
| T-23 | Rate Limit 429 응답이 OpenAI 에러 형식 | 통합 테스트 | 6 |
| T-24 | 관리자 UI에서 키 발급/복사확인/목록/폐기 | 수동 검증 | 5 |
| T-25 | API Key로 관리자 API 접근 시 403 거부 | 통합 테스트 | 2 |

---

## 의존성

### 신규 의존성

없음. 기존 라이브러리만 사용:
- `secrets` (stdlib) — 키 생성 + 타이밍 안전 비교 (`compare_digest`)
- `hmac` (stdlib) — HMAC-SHA256 해싱
- `hashlib` (stdlib) — HMAC 내부 사용
- `fastapi.responses.StreamingResponse` — SSE 스트리밍

### 기존 의존성 활용

- `slowapi` — `/api/*` 경로 IP 기반 Rate Limit (기존 유지)
- `redis.asyncio` — API Key Rate Limit 카운터 + last_used_at 버퍼

### 선택적 의존성 (향후)

- `tiktoken` — 정확한 토큰 카운팅 (현재는 글자 수 기반 근사치 사용)

---

## 예상 이슈 및 해결 방안

| # | 이슈 | 영향 | 해결 방안 |
|---|------|------|----------|
| R-1 | API Key 유출 시 무제한 접근 | 보안 위험 | 키별 이중 Rate Limit(RPM+일일) + 관리자 UI 즉시 폐기 + last_used_at 모니터링 + 만료일 설정 |
| R-2 | HMAC-SHA256 해시 조회 성능 | 매 요청마다 DB 조회 | key_hash에 unique index. 향후 Redis 캐싱 검토 (키 폐기 시 캐시 무효화 필수) |
| R-3 | SSE 스트리밍 시 답변 분할 | UX (TTFT 지연) | 1단계: 시뮬레이션 스트리밍 (전체 답변 분할). 향후 Phase에서 orchestrator 실시간 스트리밍 구현 |
| R-4 | OpenAI SDK 버전별 호환성 | 연동 실패 | openai>=1.0 Pydantic 모델 검증 통과 필수. usage에 근사 토큰 수, system_fingerprint 포함 |
| R-5 | 기존 JWT 인증 엔드포인트와 충돌 | 인증 혼란 | `rag_sk_` 접두사를 JWT decode보다 먼저 체크. 기존 JWT 테스트 전수 통과 확인 |
| R-6 | 매 요청 last_used_at DB write | 성능 저하 | Redis에 기록 후 5분 주기 배치 갱신 |
| R-7 | /v1 경로의 에러 형식 불일치 | SDK 파싱 실패 | /v1 전용 예외 핸들러로 OpenAI 에러 형식 반환 (기존 UrstoryRAG 형식과 분리) |
| R-8 | API Key로 관리자 API 접근 | 권한 상승 | API Key 인증은 /v1/* 엔드포인트만 허용. 관리자 API는 JWT 필수 |

---

## 구현 순서 및 예상 작업량

```
Step 1: DB 모델 + 마이그레이션      ━━━━━━ 가장 빠름
Step 2: API Key 서비스 + 인증       ━━━━━━━━━━ 핵심 보안 로직
Step 3: Key 관리 엔드포인트          ━━━━━━━━ CRUD
Step 4: OpenAI 호환 엔드포인트      ━━━━━━━━━━━━ 핵심 기능
Step 5: 프론트엔드 UI               ━━━━━━━━━━ 관리 페이지
Step 6: Rate Limit + 사용량         ━━━━━━ Redis 카운터
```

---

## 완료 후 사용 예시

```python
# 다른 Python 프로젝트에서
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="rag_sk_a3BfC7dE9xYz...",
)

# 검색 + 답변
response = client.chat.completions.create(
    model="urstory-rag",
    messages=[{"role": "user", "content": "한국의 GDP 성장률은?"}],
)
print(response.choices[0].message.content)

# 스트리밍
for chunk in client.chat.completions.create(
    model="urstory-rag",
    messages=[{"role": "user", "content": "한국의 GDP 성장률은?"}],
    stream=True,
):
    print(chunk.choices[0].delta.content or "", end="")
```

```javascript
// JavaScript (fetch)
const resp = await fetch("http://localhost:8000/v1/chat/completions", {
  method: "POST",
  headers: {
    "Authorization": "Bearer rag_sk_a3BfC7dE9xYz...",
    "Content-Type": "application/json",
  },
  body: JSON.stringify({
    model: "urstory-rag",
    messages: [{ role: "user", content: "한국의 GDP 성장률은?" }],
  }),
});
const data = await resp.json();
console.log(data.choices[0].message.content);
```

---

## 다음 단계

1. `/start-phase 17` 으로 브랜치 생성 및 개발 시작
2. Step 1 (DB) → Step 2 (인증) → Step 3 (CRUD) → Step 4 (OpenAI) → Step 5 (UI) → Step 6 (Rate Limit) 순서
3. 에이전트 팀 리뷰 후 `/finish-phase 17`
