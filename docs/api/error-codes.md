# UrstoryRAG API 에러 코드 정의서

## 에러 응답 형식

모든 에러는 다음 형식의 JSON으로 반환됩니다:

```json
{
  "status": 401,
  "error": "TOKEN_EXPIRED",
  "message": "인증 토큰이 만료되었습니다",
  "details": null,
  "request_id": "req_abc123"
}
```

## 에러 코드 목록

| HTTP 상태 | 에러 코드 | 설명 | 발생 엔드포인트 | 사용자 안내 메시지 |
|-----------|----------|------|----------------|------------------|
| 400 | `VALIDATION_ERROR` | 요청 파라미터 유효성 검사 실패 | 전체 | 입력값을 확인해주세요 |
| 400 | `INVALID_FILE_TYPE` | 지원하지 않는 파일 형식 | `POST /api/documents/upload` | 지원하는 파일 형식: PDF, DOCX, MD, TXT |
| 400 | `GUARDRAIL_VIOLATION` | 가드레일 정책 위반 (PII, 인젝션 등) | `POST /api/search` | 이 질문은 처리할 수 없습니다 |
| 401 | `TOKEN_EXPIRED` | JWT 토큰 만료 | 인증 필요 엔드포인트 전체 | 다시 로그인해주세요 |
| 401 | `TOKEN_INVALID` | 잘못된 JWT 토큰 | 인증 필요 엔드포인트 전체 | 다시 로그인해주세요 |
| 401 | `INVALID_CREDENTIALS` | 로그인 실패 | `POST /api/auth/login` | 아이디 또는 비밀번호가 올바르지 않습니다 |
| 403 | `ADMIN_REQUIRED` | 관리자 권한 필요 | admin 전용 엔드포인트 | 관리자 권한이 필요합니다 |
| 404 | `DOCUMENT_NOT_FOUND` | 문서를 찾을 수 없음 | `GET/DELETE /api/documents/{id}` | 요청한 문서를 찾을 수 없습니다 |
| 404 | `DATASET_NOT_FOUND` | 평가 데이터셋 없음 | `GET /api/evaluation/datasets/{id}` | 요청한 데이터셋을 찾을 수 없습니다 |
| 404 | `RUN_NOT_FOUND` | 평가 실행 없음 | `GET /api/evaluation/runs/{id}` | 요청한 평가 결과를 찾을 수 없습니다 |
| 409 | `DUPLICATE_USERNAME` | 이미 존재하는 사용자명 | `POST /api/auth/signup`, `POST /api/admin/users` | 이미 등록된 아이디입니다 |
| 422 | `PASSWORD_POLICY` | 비밀번호 정책 미충족 | `POST /api/auth/signup`, `PUT /api/auth/me/password` | 비밀번호는 8자 이상, 대소문자+숫자+특수문자 포함 |
| 429 | `RATE_LIMIT_EXCEEDED` | 요청 빈도 초과 | rate limit 설정된 엔드포인트 | 잠시 후 다시 시도해주세요 |
| 500 | `INTERNAL_ERROR` | 서버 내부 오류 | 전체 | 내부 오류가 발생했습니다 |
| 503 | `EMBEDDING_SERVICE_ERROR` | 임베딩 서비스 연결 실패 | `POST /api/search`, `POST /api/documents/upload` | 검색 서비스에 일시적인 문제가 발생했습니다 |
| 503 | `SEARCH_SERVICE_ERROR` | 검색 엔진 연결 실패 | `POST /api/search` | 검색 서비스에 일시적인 문제가 발생했습니다 |
| 503 | `CIRCUIT_BREAKER_OPEN` | 외부 서비스 반복 장애로 차단 | `POST /api/search` | 서비스에 일시적인 문제가 발생했습니다. 잠시 후 다시 시도해주세요 |

## Rate Limit 정책

| 엔드포인트 | 제한 | 비고 |
|-----------|------|------|
| `POST /api/auth/signup` | 3회/분 | 무차별 가입 방지 |
| `POST /api/auth/login` | 5회/분 | 브루트포스 방지 |
| `POST /api/search` | 30회/분 | API 비용 제어 |
| `POST /api/search/debug` | 30회/분 | 디버그 검색도 동일 |

## 인증 방식

- **Bearer Token**: `Authorization: Bearer <access_token>` 헤더
- **access_token 유효기간**: 30분
- **refresh_token**: HttpOnly Cookie, 유효기간 7일, Rotation 적용
