import { test, expect } from "@playwright/test";

test.describe("검색 테스트", () => {
  test("쿼리 검색 및 결과 확인", async ({ page }) => {
    await page.goto("/search");

    // 검색 입력
    await page
      .getByPlaceholder("검색 쿼리를 입력하세요...")
      .fill("연차 신청 절차");

    // 검색 버튼 클릭
    await page.getByRole("button", { name: /검색/ }).click();

    // 답변 표시 확인 (네트워크 요청 대기)
    await expect(
      page.locator("[data-testid='answer-view']")
    ).toBeVisible({ timeout: 30000 });

    // 참조 문서 영역 확인
    await expect(page.getByText("최종 답변")).toBeVisible();
    await expect(page.getByText("참조 문서")).toBeVisible();
  });

  test("검색 결과에 파이프라인 트레이스 표시", async ({ page }) => {
    await page.goto("/search");

    await page
      .getByPlaceholder("검색 쿼리를 입력하세요...")
      .fill("테스트 쿼리");

    await page.getByRole("button", { name: /검색/ }).click();

    // 파이프라인 트레이스 표시 확인
    await expect(
      page.locator("[data-testid='pipeline-trace']")
    ).toBeVisible({ timeout: 30000 });

    // 파이프라인 단계 표시 확인
    await expect(page.getByText("파이프라인 실행 결과")).toBeVisible();
  });

  test("검색 모드 변경", async ({ page }) => {
    await page.goto("/search");

    // 검색 모드 셀렉트 확인
    await expect(page.getByText("검색 모드")).toBeVisible();

    // HyDE 토글 확인
    await expect(page.getByText("HyDE")).toBeVisible();

    // 리랭킹 토글 확인
    await expect(page.getByText("리랭킹")).toBeVisible();

    // Top-K 슬라이더 확인
    await expect(page.getByText(/Top-K:/)).toBeVisible();
  });

  test("빈 쿼리로 검색 불가", async ({ page }) => {
    await page.goto("/search");

    // 검색 버튼 비활성화 확인
    const searchBtn = page.getByRole("button", { name: /^검색$/ });
    await expect(searchBtn).toBeDisabled();
  });

  test("검색 중 로딩 상태 표시", async ({ page }) => {
    await page.goto("/search");

    await page
      .getByPlaceholder("검색 쿼리를 입력하세요...")
      .fill("로딩 테스트");

    await page.getByRole("button", { name: /검색/ }).click();

    // 로딩 상태 (검색 중...) 표시 확인
    await expect(
      page.getByRole("button", { name: /검색 중/ })
    ).toBeVisible();
  });
});
