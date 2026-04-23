import { test as base, expect, type Page } from "@playwright/test";

/**
 * Credentials used by tests.
 *
 * These fall back to the default seeded admin account (CLAUDE.md).
 * Override via ADMIN_USERNAME / ADMIN_PASSWORD env vars when running in CI
 * against a non-default environment.
 */
export const ADMIN_USERNAME = process.env.ADMIN_USERNAME ?? "admin";
export const ADMIN_PASSWORD = process.env.ADMIN_PASSWORD ?? "ChangeMe1234!@#$";

/**
 * Log in through the UI. Keeps a single session per worker via storageState
 * when `e2e.setup.ts` runs, but tests can also call this directly.
 */
export async function loginThroughUi(page: Page): Promise<void> {
  await page.goto("/login");
  await page.getByLabel("아이디").fill(ADMIN_USERNAME);
  await page.getByLabel("비밀번호").fill(ADMIN_PASSWORD);
  await page.getByRole("button", { name: /^로그인$/ }).click();
  // Login either succeeds (redirect to /) or shows an error alert.
  await expect(page).toHaveURL(/\/$|\/documents|\/search/, { timeout: 15000 });
}

/**
 * Extended test fixture that ensures the user is authenticated before each
 * test. Tests should import `test` from this file instead of `@playwright/test`.
 */
export const test = base.extend<{ authedPage: Page }>({
  authedPage: async ({ page }, runTest) => {
    await loginThroughUi(page);
    await runTest(page);
  },
});

export { expect };
