# Phase 16 개발 계획 리뷰 결과

- 리뷰 일시: 2026-03-31
- 리뷰어: gemini (에이전트 팀 관점)
- 대상 파일: `docs/phases/phase16_dependency_pooling_apidocs_개발계획.md`

---

## 카테고리: [논리적 완결성 / 구현 가능성]

### 에이전트: 지훈 (백엔드 실용주의자)

### 문제
Elasticsearch `httpx.AsyncClient`를 영속화할 때, FastAPI의 `Lifespan` 이벤트를 사용하지 않고 `app.state`에 직접 할당하는 방식은 현대적인 FastAPI 패턴에서 권장되지 않으며, 테스트 환경에서 의존성 주입(DI)이 까다로워집니다. 또한, `keyword_es.py` 클래스 내부에서 클라이언트를 생성하면, 싱글톤 보장이 어렵고 여러 서비스에서 중복 생성될 위험이 있습니다.

### 위치
- 2-3. Elasticsearch httpx 클라이언트 영속화
- 2-4. "shutdown 시퀀스" 부분

### 제안
FastAPI의 `lifespan` context manager를 사용하여 `httpx.AsyncClient`의 생명주기를 관리하고, `Depends`를 통해 각 서비스에 주입하는 방식을 채택해야 합니다. 또한 `AsyncClient` 생성 시 `limits` 뿐만 아니라 `transport` 계층의 `retries` 설정도 명시적으로 포함하여 네트워크 일시 오류에 대응해야 합니다.

### 우선순위
[높음]

---

## 카테고리: [누락 항목 / 일관성]

### 에이전트: 소연 (프론트엔드 장인)

### 문제
`ErrorResponse` 스키마에 `request_id` 필드가 정의되어 있지만, 현재 백엔드 로직에 모든 에러 발생 시 이 `request_id`를 추적하여 응답에 포함시키는 전역 예외 처리기(Global Exception Handler)와 상관관계 ID(Correlation ID) 미들웨어 구현 계획이 누락되어 있습니다. 문서만 있고 실제 응답에 데이터가 없으면 프론트엔드 디버깅에 혼선이 생깁니다.

### 위치
- 3-1. 공통 에러 응답 스키마 정의
- API 설계 섹션의 `ErrorResponse`

### 제안
`app/middleware/logging.py` 혹은 신규 미들웨어를 통해 모든 요청에 `X-Request-ID` 헤더를 부여하고, `FastAPI.exception_handler`를 오버라이드하여 `HTTPException`이나 유효성 검사 에러 발생 시 반드시 `ErrorResponse` 스키마에 맞춰 `request_id`를 포함하여 반환하는 로직을 Step 3에 명시적으로 추가해야 합니다.

### 우선순위
[높음]

---

## 카테고리: [보안 / 구현 가능성]

### 에이전트: 민수 (보안 리드)

### 문제
`pip-audit`과 `pnpm audit`을 CI에 추가하는 것은 좋으나, "해결 불가능한 취약점"에 대한 예외 처리 정책이 모호합니다. 메인라인 빌드가 외부 라이브러리의 패치되지 않은 취약점으로 인해 무기한 중단될 위험이 있습니다. 또한, Docker 이미지 보안 스캔(`trivy` 등)이 누락되어 있습니다.

### 위치
- 1-3. CI에 보안 감사 스텝 추가
- 예상 이슈 R-2

### 제안
`.pip-audit-ignore` 파일을 도입하여 현재 비즈니스 로직상 영향이 없거나 패치가 나오지 않은 항목은 명시적으로 관리하고 사유를 기재해야 합니다. 또한 GitHub Actions에 `aquasecurity/trivy-action`을 추가하여 Docker 베이스 이미지의 OS 취약점도 함께 스캔하도록 강화하십시오.

### 우선순위
[중간]

---

## 카테고리: [논리적 완결성 / DevOps]

### 에이전트: 현우 (DevOps 자동화 덕후)

### 문제
`pyproject.toml`에 버전 상한을 추가하는 것은 좋으나, `pnpm` (프론트엔드)에 대한 버전 고정 및 업데이트 전략이 상대적으로 빈약합니다. 또한, 로컬 PostgreSQL 14(포트 5432)와의 충돌 주의사항이 명시되어 있는데, CI 환경이나 `docker-compose` 실행 시 이 포트 충돌을 피하기 위한 구체적인 환경변수 처리(`DB_PORT` 등)가 계획에 누락되었습니다.

### 위치
- 1-1. pyproject.toml 버전 범위 지정
- 프로젝트 컨텍스트 (Postgres 5432 충돌 주의)

### 제안
`frontend/package.json`의 `dependencies`에도 `^` 대신 가급적 범위를 제한하거나 `pnpm-lock.yaml`의 무결성을 체크하는 `pnpm install --frozen-lockfile`을 CI에 강제해야 합니다. 또한 `docker-compose.yml`에서 호스트 포트를 변수화(`${DB_PORT:-5432}:5432`)하여 로컬 환경에 따라 유연하게 대응할 수 있도록 수정 계획을 포함하십시오.

### 우선순위
[중간]

---

## 카테고리: [명세 완결성 / UX]

### 에이전트: 은지 (기획자)

### 문제
에러 코드 체계에서 `500 INTERNAL_ERROR`는 개발자용입니다. 실제 사용자가 마주했을 때 "서버 오류입니다"라는 불친절한 메시지 외에, 사용자가 취할 수 있는 행동(예: "잠시 후 다시 시도해주세요", "고객센터에 문의하세요")에 대한 가이드가 `ErrorResponse`에 포함되지 않았습니다.

### 위치
- 에러 코드 체계 테이블

### 제안
`ErrorResponse`에 `user_message` (사용자 노출용 국문 메시지) 필드를 추가하거나, 에러 코드 정의서(`docs/api/error-codes.md`)에 각 에러별로 프론트엔드가 사용자에게 보여줘야 할 권장 메시지를 명시하여 UX 일관성을 확보하십시오.

### 우선순위
[낮음]

---

## 전체 요약 및 핵심 개선 사항 5가지

리뷰 결과, 계획의 방향성은 훌륭하나 **"연결의 영속성 관리"**와 **"에러 응답의 실질적 구현"** 부분에서 보완이 필요합니다.

1.  **FastAPI Lifespan 도입**: Elasticsearch 및 Redis 클라이언트의 생명주기를 `lifespan`으로 관리하고 DI(Dependency Injection) 패턴으로 통일하여 테스트 가능성을 높일 것.
2.  **Global Exception Handler 구현**: 단순히 스키마만 정의하는 게 아니라, 백엔드에서 발생하는 모든 예외를 `ErrorResponse` 형식으로 변환하고 `request_id`를 강제 삽입하는 처리기를 구현할 것.
3.  **보안 스캔 예외 정책 수립**: CI 중단을 방지하기 위한 `pip-audit` 화이트리스트 관리 파일(`.pip-audit-ignore`)과 Docker 이미지용 `Trivy` 스캔을 추가할 것.
4.  **포트 가변성 확보**: 로컬 DB(5432)와의 충돌을 방지하기 위해 `docker-compose` 및 `config.py`에서 포트 번호를 환경변수로 완벽히 분리할 것.
5.  **에러 가이드 문서화**: `error-codes.md`에 개발자용 설명뿐만 아니라 사용자를 위한 "조치 방법" 메시지 가이드를 포함하여 프론트엔드 UX 설계 지원을 강화할 것.
