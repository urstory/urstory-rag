import { test, expect } from "./fixtures/auth";

test.describe("접근성 스모크", () => {
  test("Skip-link이 Tab 포커스 시 나타나고 main으로 이동", async ({
    authedPage: page,
  }) => {
    await page.goto("/");
    await page.keyboard.press("Tab");
    const skip = page.getByRole("link", { name: "본문으로 건너뛰기" });
    await expect(skip).toBeFocused();

    await page.keyboard.press("Enter");
    // main-content should be the active element
    const activeId = await page.evaluate(() => document.activeElement?.id ?? "");
    expect(activeId).toBe("main-content");
  });

  test("네비게이션에 aria-current='page'이 현재 경로에 적용됨", async ({
    authedPage: page,
  }) => {
    await page.goto("/documents");
    const active = page.locator("a[aria-current='page']");
    await expect(active).toHaveText(/문서 관리/);
  });

  test("<html lang='ko'>", async ({ authedPage: page }) => {
    await page.goto("/");
    const lang = await page.locator("html").getAttribute("lang");
    expect(lang).toBe("ko");
  });

  test("헤더의 아이콘 전용 버튼에 aria-label이 붙어 있음", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto("/");
    await expect(
      page.getByRole("button", { name: "메뉴 열기" })
    ).toBeVisible();
  });

  test("로그인 에러는 role='alert' + aria-live='assertive'", async ({
    page,
  }) => {
    await page.goto("/login");
    await page.getByLabel("아이디").fill("nobody");
    await page.getByLabel("비밀번호").fill("wrongwrong");
    await page.getByRole("button", { name: /^로그인$/ }).click();

    const alert = page.locator("[role='alert']");
    await expect(alert).toBeVisible({ timeout: 10000 });
    const live = await alert.getAttribute("aria-live");
    expect(live).toBe("assertive");
  });

  test("시스템 상태 배지는 role='status' + aria-live='polite'", async ({
    authedPage: page,
  }) => {
    await page.goto("/");
    await expect(
      page.locator("[role='status'][aria-live='polite']").first()
    ).toBeVisible();
  });
});
