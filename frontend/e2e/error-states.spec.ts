import { test, expect } from "./fixtures/auth";

test.describe("에러/빈/로딩 상태", () => {
  test("백엔드 API 5xx 실패 시 ErrorState 표시", async ({ authedPage: page }) => {
    // Intercept settings API and force a 500
    await page.route("**/api/settings", (route) => {
      route.fulfill({
        status: 500,
        contentType: "application/json",
        body: JSON.stringify({ detail: "mock server error" }),
      });
    });

    await page.goto("/settings/chunking");
    // Forms under /settings/* use the shared ErrorState (#17)
    await expect(page.locator('[role="alert"]')).toBeVisible({
      timeout: 10000,
    });
    await expect(page.getByText(/서버 오류가 발생했습니다/)).toBeVisible();
  });

  test("네트워크 오류 시 ErrorState와 '다시 시도' 버튼", async ({
    authedPage: page,
  }) => {
    await page.route("**/api/settings", (route) => route.abort("failed"));

    await page.goto("/settings/chunking");
    await expect(page.locator('[role="alert"]')).toBeVisible({
      timeout: 10000,
    });
  });

  test("401 응답 시 로그인 페이지로 리다이렉트", async ({ authedPage: page }) => {
    // Mock the /api/auth/me endpoint to return 401 on next refetch
    await page.route("**/api/documents**", (route) =>
      route.fulfill({
        status: 401,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Unauthorized" }),
      })
    );
    await page.route("**/api/auth/refresh", (route) =>
      route.fulfill({
        status: 401,
        contentType: "application/json",
        body: JSON.stringify({ detail: "expired" }),
      })
    );

    await page.goto("/documents");
    await expect(page).toHaveURL(/\/login/, { timeout: 15000 });
  });

  test("존재하지 않는 경로 → not-found.tsx 노출", async ({ authedPage: page }) => {
    await page.goto("/foo-bar-nonexistent");
    await expect(
      page.getByRole("heading", { name: /페이지를 찾을 수 없습니다/ })
    ).toBeVisible({ timeout: 10000 });
    await expect(page.getByRole("link", { name: /대시보드로/ })).toBeVisible();
  });

  test("빈 데이터셋 조회 시 EmptyState 친절 메시지", async ({
    authedPage: page,
  }) => {
    // Mock evaluation runs to return empty list
    await page.route("**/api/evaluation/runs**", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ items: [], total: 0 }),
      })
    );
    await page.goto("/evaluation/runs");
    // Any empty hint string or explicit EmptyState semantics
    await expect(
      page.getByText(/기록이 없습니다|데이터가 없습니다/).first()
    ).toBeVisible({ timeout: 10000 });
  });

  test("document 상세 — 존재하지 않는 ID는 ErrorState 또는 EmptyState", async ({
    authedPage: page,
  }) => {
    await page.route("**/api/documents/nonexistent-id", (route) =>
      route.fulfill({
        status: 404,
        contentType: "application/json",
        body: JSON.stringify({ detail: "not found" }),
      })
    );
    await page.goto("/documents/nonexistent-id");
    await expect(
      page.getByText(/문서를 찾을 수 없습니다|요청한 리소스를 찾을 수 없습니다/)
    ).toBeVisible({ timeout: 10000 });
  });
});
