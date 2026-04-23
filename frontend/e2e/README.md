# E2E 테스트

Playwright 기반 End-to-End 테스트. `fullstackfamily-platform-playwright:latest`
Docker 이미지로만 실행한다 (로컬 Playwright 설치 금지).

## 테스트 스위트 요약

| 파일 | 내용 |
|------|------|
| `auth.spec.ts` | 로그인/로그아웃, 401 리다이렉트, 자격증명 오류, 라벨 연결 |
| `documents.spec.ts` | 업로드/삭제/목록/상세, 파일 input label, Escape로 다이얼로그 닫기 |
| `search.spec.ts` | 기본 검색, 파이프라인 트레이스, 옵션 UI, 빈 쿼리 처리 |
| `search-flow.spec.ts` | HyDE/리랭킹 토글, 검색 모드 전환, Top-K 키보드 제어, role="search" |
| `settings.spec.ts` | 카테고리 목록, 토글, 저장 버튼, 503 시 ErrorState |
| `error-states.spec.ts` | 5xx/네트워크 오류, 401→로그인, 404, 빈 목록, 존재하지 않는 문서 |
| `a11y.spec.ts` | Skip-link, aria-current, html lang, 아이콘 버튼 aria-label |
| `responsive.spec.ts` | 모바일/PC 뷰포트별 레이아웃, 햄버거 메뉴, Sheet |

## 실행

```bash
# 반드시 이 이미지로 실행
docker run --rm --network=host \
  -v "$PWD:/work" -w /work/frontend \
  -e ADMIN_USERNAME=admin -e ADMIN_PASSWORD='ChangeMe1234!@#$' \
  fullstackfamily-platform-playwright:latest \
  npx playwright test

# 특정 스위트만
docker run --rm --network=host \
  -v "$PWD:/work" -w /work/frontend \
  fullstackfamily-platform-playwright:latest \
  npx playwright test e2e/error-states.spec.ts
```

## 인증 처리

`fixtures/auth.ts`의 `test` 픽스처(`authedPage`)가 각 테스트 전에
관리자 계정으로 UI 로그인을 수행한다. 기본 자격증명은 CLAUDE.md의 시드
계정(`admin` / `ChangeMe1234!@#$`)이며, `ADMIN_USERNAME` / `ADMIN_PASSWORD`
환경변수로 덮어쓸 수 있다.

```ts
import { test, expect } from "./fixtures/auth";

test("tuần 1", async ({ authedPage: page }) => {
  await page.goto("/settings");
  // ...
});
```

## 새 테스트 작성 시

- 인증이 필요한 경로는 반드시 `fixtures/auth.ts`의 `test`를 사용한다
  (기본 `@playwright/test`는 `/login` 리다이렉트를 처리하지 않는다).
- API 호출을 mock하려면 `page.route(...)`를 사용한다 — 백엔드가 없는 CI에서도 통과.
- 접근성 관련 테스트는 가능하면 `getByRole` / `getByLabel`을 사용한다.
- 모바일 레이아웃 테스트는 `test.use({ viewport })`로 격리한다.
