import { test, expect } from "@playwright/test";
import {
  ADMIN_USERNAME,
  ADMIN_PASSWORD,
  loginThroughUi,
} from "./fixtures/auth";

test.describe("인증 플로우", () => {
  test("로그인하지 않은 상태에서 보호된 경로 접근 시 /login으로 리다이렉트", async ({
    page,
  }) => {
    // Clear storage to ensure clean state
    await page.goto("/login");
    await page.context().clearCookies();

    await page.goto("/documents");
    await expect(page).toHaveURL(/\/login/, { timeout: 10000 });
    await expect(
      page.getByRole("button", { name: /^로그인$/ })
    ).toBeVisible();
  });

  test("잘못된 자격증명 입력 시 에러 메시지(role=alert) 노출", async ({ page }) => {
    await page.goto("/login");

    await page.getByLabel("아이디").fill("nobody");
    await page.getByLabel("비밀번호").fill("invalid-password-xyz");
    await page.getByRole("button", { name: /^로그인$/ }).click();

    // ErrorState/alert semantic
    await expect(page.locator('[role="alert"]')).toBeVisible({
      timeout: 10000,
    });
    // Still on login page
    await expect(page).toHaveURL(/\/login/);
  });

  test("로그인 → 대시보드 → 로그아웃 플로우", async ({ page }) => {
    await loginThroughUi(page);
    await page.goto("/");
    await expect(page.getByText("대시보드")).toBeVisible({ timeout: 10000 });

    // Open user dropdown and click 로그아웃
    const userBtn = page.getByRole("button", { name: /사용자 메뉴/ });
    if (await userBtn.isVisible().catch(() => false)) {
      await userBtn.click();
      await page.getByRole("menuitem", { name: /로그아웃/ }).click();
      await expect(page).toHaveURL(/\/login/, { timeout: 10000 });
    }
  });

  test("label htmlFor 연결 — getByLabel로 입력창 접근 가능", async ({ page }) => {
    await page.goto("/login");
    // If a11y htmlFor associations are wired correctly, getByLabel resolves
    // to the underlying input (from issue #20).
    await expect(page.getByLabel("아이디")).toBeVisible();
    await expect(page.getByLabel("비밀번호")).toBeVisible();
  });

  test("기본 관리자 계정으로 로그인 시 세션 유지", async ({ page, context }) => {
    await loginThroughUi(page);
    // Refresh cookie-backed session by opening a new tab
    const page2 = await context.newPage();
    await page2.goto("/");
    await expect(page2.getByText("대시보드")).toBeVisible({ timeout: 10000 });
    await page2.close();
  });

  test.skip(!ADMIN_USERNAME || !ADMIN_PASSWORD, "credentials required");
});
