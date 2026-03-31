# Phase 17 개발 계획 리뷰 결과

## 리뷰 일시
2026-03-31

## 리뷰어
- gemini (외부 리뷰)
- Claude Code (코드베이스 기반 상세 리뷰)
- 에이전트 팀: 은지(기획), 민수(보안), 지훈(백엔드), 소연(프론트엔드), 현우(DevOps)

---

## gemini 리뷰 결과

### 1. [구현 가능성] 가짜 스트리밍 (높음)

**문제**: orchestrator가 전체 답변을 한 번에 반환하므로, 단어 단위로 분할하는 "가짜 스트리밍"은 TTFT가 전체 생성 시간과 동일하여 스트리밍의 핵심 이점이 없음.

**위치**: Step 4, 예상 이슈 R-3

**제안**: HybridSearchOrchestrator에 스트리밍 모드를 추가하거나 가짜 스트리밍은 최종 수단으로만 고려.

### 2. [보안] SHA-256 해시 보안 강화 (높음)

**문제**: SHA-256은 빠르므로 DB 유출 시 무차별 대입 공격에 취약. 타이밍 공격 가능성.

**위치**: Step 2 - hash_api_key, authenticate_api_key

**제안**: HMAC 사용, secrets.compare_digest()로 타이밍 공격 방지, 로깅 필터.

### 3. [명세 완결성] OpenAI SDK 호환성 부족 (중간)

**문제**: usage 필드가 0, system_fingerprint 누락, OpenAI 에러 형식 미준수.

**위치**: Step 4 - Request/Response 형식

**제안**: tiktoken으로 토큰 카운팅, system_fingerprint 추가, OpenAI 에러 형식 준수.

### 4. [논리적 완결성] Rate Limit 단위/범위 모호 (중간)

**문제**: 일일 제한만 있고 분당 제한(RPM) 없어 Burst 공격 방어 불가.

**위치**: Step 6

**제안**: 일일 제한 + 분당 제한 이중 적용, Redis 캐싱으로 DB 조회 최소화.

### 5. [누락 항목] API Key Scoping 부재 (낮음)

**문제**: API Key가 사용자의 모든 권한을 가짐. 범위 제한 기능 없음.

**위치**: 데이터베이스 스키마

**제안**: scopes 필드 추가 (향후 확장 가능하도록).

---

## Claude Code 코드베이스 기반 상세 리뷰

### 6. [구현 가능성] dependencies.py 변경의 영향 범위 (높음)

**문제**: 현재 `get_current_user()`는 `HTTPBearer(auto_error=False)`를 사용하며, credentials가 None일 때 401을 반환한다. 계획에서는 `token.startswith("rag_sk_")`로 API Key를 판별하는데, `HTTPBearer`는 "Bearer" 스킴을 전제로 한다. API Key도 "Bearer rag_sk_..." 형태로 전달되므로 문제는 없지만, **JWT decode 실패 시 예외가 발생하는 기존 로직이 API Key 경로에서도 트리거될 수 있다**.

**위치**: Step 2 - dependencies.py 변경

**제안**: `rag_sk_` 접두사 체크를 **JWT decode보다 먼저** 수행해야 한다. 현재 계획의 코드는 올바르게 되어 있으나, 기존 코드에서 `decode_token()`이 먼저 호출되는 구조를 변경해야 함을 명시해야 한다.

### 7. [명세 완결성] OpenAI SDK의 model validation (높음)

**문제**: OpenAI Python SDK v1.x는 응답을 Pydantic 모델로 파싱한다. `ChatCompletion`, `ChatCompletionChunk` 등의 모델에서 필수 필드가 누락되면 ValidationError가 발생한다. 현재 계획에서 누락된 필수 필드:
- SSE 스트리밍: `model` 필드가 각 chunk에 포함되어야 함
- SSE 스트리밍: `created` 필드가 각 chunk에 포함되어야 함
- 비스트리밍: `id` 형식이 `chatcmpl-`로 시작해야 함 (계획은 `chatcmpl-rag-` 사용 -- 호환성 확인 필요)

**위치**: Step 4 - SSE 스트리밍 응답 형식

**제안**: SSE chunk에 `model`, `created` 필드 추가. OpenAI SDK의 실제 Pydantic 모델을 참조하여 필수 필드 목록을 검증.

### 8. [논리적 완결성] orchestrator 인스턴스 공유 문제 (중간)

**문제**: 현재 `search.py`에서 `_orchestrator`가 글로벌 인스턴스로 관리된다. 새로운 `openai_compat.py`에서도 동일한 orchestrator를 사용해야 하는데, 계획에서는 이를 어떻게 공유할지 명시하지 않았다. `search.py`의 `get_orchestrator()` 함수를 import하면 되지만, 이 의존 관계를 명시해야 한다.

**위치**: Step 4 - 핵심 로직

**제안**: `openai_compat.py`에서 `search.py`의 `get_orchestrator()`, `get_search_settings_service()`를 import하여 사용한다는 것을 명시. 또는 `app/dependencies.py`로 이동하여 공유.

### 9. [보안] API Key의 last_used_at 갱신이 매 요청마다 DB write 유발 (중간)

**문제**: `authenticate_api_key()`에서 `last_used_at = func.now()`와 `await db.commit()`을 실행한다. 매 API 요청마다 DB UPDATE + COMMIT이 발생하여 성능에 영향을 줄 수 있다.

**위치**: Step 2 - authenticate_api_key 함수

**제안**: `last_used_at`는 Redis에 저장하고, 주기적(5분 등)으로 DB에 배치 업데이트하는 방식으로 변경. 또는 비동기 백그라운드 태스크로 처리.

### 10. [일관성] Rate Limit 구현 방식 불일치 (중간)

**문제**: 기존 시스템은 `slowapi`(IP 기반)를 사용하는데, 계획에서는 Step 6에서 Redis를 직접 사용하는 커스텀 Rate Limit을 구현한다. 두 가지 Rate Limit 메커니즘이 공존하게 된다. `slowapi`도 Redis 백엔드를 지원하므로 통합 가능.

**위치**: Step 6 - Redis 기반 일일 카운터

**제안**: `slowapi`의 커스텀 key_func로 API Key 기반 Rate Limit을 구현하거나, 명시적으로 "OpenAI 호환 엔드포인트는 slowapi 대신 커스텀 Rate Limit 사용" 이라고 기술.

### 11. [누락 항목] CORS 설정 (중간)

**문제**: `/v1/chat/completions`는 외부 서버에서 호출하는 서버간 API이므로 CORS가 불필요하다. 하지만 현재 `main.py`의 CORS 미들웨어가 모든 경로에 적용된다. 브라우저 기반 클라이언트가 직접 호출할 수도 있으므로 CORS 전략을 명시해야 한다.

**위치**: 전체 계획

**제안**: `/v1/*` 엔드포인트의 CORS 정책을 명시. 서버간 통신이 주 용도이므로 CORS 헤더가 불필요할 수 있으나, 브라우저 호출을 허용할 경우 `allow_origins`에 추가 필요.

### 12. [누락 항목] API Key 만료 기능 (중간)

**문제**: `api_keys` 테이블에 만료일(`expires_at`) 필드가 없다. API Key가 무기한 유효하면 보안 리스크가 증가.

**위치**: 데이터베이스 스키마

**제안**: `expires_at: Mapped[datetime | None]` 필드 추가. None이면 무기한, 값이 있으면 만료일 적용.

### 13. [누락 항목] API Key 발급 시 user role 검증 (중간)

**문제**: 계획에서 API Key는 "admin" 권한으로만 발급 가능하지만, API Key로 인증 시 연결된 user가 admin이어야 하는지, 일반 user에게도 발급 가능한지 명확하지 않다. UC-3에서 "외부 서비스"가 actor인데, 이 키의 권한 범위가 불명확.

**위치**: UC-1, API Key 관리 엔드포인트

**제안**: API Key로 인증한 사용자의 권한 범위를 명시. 예: "API Key 인증 시 검색(/v1/chat/completions, /v1/models)만 가능, 관리자 API(/api/admin/*)는 불가"

### 14. [기획/UX] 키 발급 후 복사 확인 UX (낮음)

**문제**: 은지(기획) 관점 - 키를 발급 후 모달을 닫으면 키를 다시 볼 수 없다. 사용자가 복사하지 않고 닫을 위험이 있다.

**위치**: Step 5 - UI 구성

**제안**: "복사했습니다" 버튼 클릭 또는 체크박스 확인 후에만 모달 닫기 가능. 복사하지 않고 닫으려 하면 경고 다이얼로그.

### 15. [누락 항목] 키 발급 개수 제한 (낮음)

**문제**: 한 관리자가 무제한으로 키를 발급할 수 있다. 악용 시 관리 불가.

**위치**: API Key 관리 엔드포인트

**제안**: 사용자당 최대 활성 키 수 제한 (예: 10개). 설정으로 조정 가능하게.
