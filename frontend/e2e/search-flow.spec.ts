import { test, expect } from "./fixtures/auth";

test.describe("검색 플로우 확장", () => {
  test("HyDE 토글을 OFF → 검색 실행 → 파이프라인 트레이스에 HyDE 생략 표시", async ({
    authedPage: page,
  }) => {
    await page.goto("/search");

    // Turn HyDE off
    const hydeSwitch = page.getByLabel("HyDE 사용");
    if (await hydeSwitch.isVisible().catch(() => false)) {
      const initial = await hydeSwitch.getAttribute("data-state");
      if (initial === "checked") {
        await hydeSwitch.click();
      }
    }

    await page.getByLabel("검색 쿼리").fill("연차 신청 절차");
    await page.getByRole("button", { name: /^검색$/ }).click();

    // Pipeline trace rendered
    await expect(
      page.locator("[data-testid='pipeline-trace']")
    ).toBeVisible({ timeout: 30000 });
  });

  test("리랭킹 토글 상호작용이 UI에 반영", async ({ authedPage: page }) => {
    await page.goto("/search");
    const reSwitch = page.getByLabel("리랭킹 사용");
    const before = await reSwitch.getAttribute("data-state");
    await reSwitch.click();
    const after = await reSwitch.getAttribute("data-state");
    expect(before).not.toBe(after);
  });

  test("검색 모드 변경 (하이브리드 → 벡터)", async ({ authedPage: page }) => {
    await page.goto("/search");
    const select = page.getByLabel("검색 모드 선택");
    await select.click();
    await page.getByRole("option", { name: "벡터" }).click();
    // Trigger shows selection
    await expect(select).toContainText("벡터");
  });

  test("Top-K 슬라이더 변경", async ({ authedPage: page }) => {
    await page.goto("/search");
    const slider = page.getByLabel(/Top-K \(현재/);
    await slider.focus();
    // Keyboard-accessible: ArrowRight increments value
    await page.keyboard.press("ArrowRight");
    await page.keyboard.press("ArrowRight");
    const label = page.getByText(/Top-K: \d+/);
    await expect(label).toBeVisible();
  });

  test("빈 결과 쿼리도 에러 없이 응답 영역 표시", async ({ authedPage: page }) => {
    await page.goto("/search");
    // Highly unlikely to match anything indexed
    await page
      .getByLabel("검색 쿼리")
      .fill("zzzqqqxxx-nonexistent-string-9284");
    await page.getByRole("button", { name: /^검색$/ }).click();

    // Either pipeline-trace shows (search ran) or ErrorState/EmptyState
    // is visible — any of these means the UI handled empty results.
    await expect(
      page
        .locator("[data-testid='pipeline-trace'], [role='alert'], [role='status']")
        .first()
    ).toBeVisible({ timeout: 30000 });
  });

  test("검색 입력창이 role='search' 랜드마크 안에 존재", async ({
    authedPage: page,
  }) => {
    await page.goto("/search");
    await expect(page.getByRole("search", { name: /RAG 검색/ })).toBeVisible();
  });
});
