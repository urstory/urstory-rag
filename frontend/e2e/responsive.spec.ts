import { test, expect } from "@playwright/test";

test.describe("모바일 뷰포트", () => {
  test.use({ viewport: { width: 375, height: 812 } });

  test("사이드바 숨겨짐 확인", async ({ page }) => {
    await page.goto("/");

    // 데스크톱 사이드바 숨겨짐
    await expect(
      page.locator("[data-testid='sidebar']")
    ).not.toBeVisible();
  });

  test("햄버거 메뉴로 사이드바 열기", async ({ page }) => {
    await page.goto("/");

    // 햄버거 메뉴 버튼 (md:hidden인 Menu 아이콘 버튼)
    const menuButton = page.locator("button").filter({
      has: page.locator("svg"),
    }).first();

    await menuButton.click();

    // Sheet로 열린 사이드바에서 네비게이션 확인
    await expect(page.getByText("UrstoryRAG")).toBeVisible();
    await expect(page.getByText("문서 관리")).toBeVisible();
  });

  test("모바일 네비게이션 이동", async ({ page }) => {
    await page.goto("/");

    // 햄버거 메뉴 열기
    const menuButton = page.locator("button").filter({
      has: page.locator("svg"),
    }).first();
    await menuButton.click();

    // 문서 관리 클릭
    await page.getByText("문서 관리").click();

    // 페이지 이동 확인
    await page.waitForURL("/documents");
  });

  test("모바일 대시보드 카드 레이아웃", async ({ page }) => {
    await page.goto("/");

    // 대시보드 타이틀
    await expect(page.getByText("대시보드")).toBeVisible();

    // 통계 카드 표시 확인 (세로 배치)
    await expect(page.getByText("총 문서")).toBeVisible();
    await expect(page.getByText("총 청크")).toBeVisible();
  });

  test("모바일 문서 목록", async ({ page }) => {
    await page.goto("/documents");

    // 페이지 타이틀
    await expect(page.getByText("문서 관리")).toBeVisible();

    // 업로드 버튼
    await expect(
      page.getByRole("button", { name: /업로드/ })
    ).toBeVisible();
  });

  test("모바일 검색 페이지", async ({ page }) => {
    await page.goto("/search");

    // 검색 입력 필드
    await expect(
      page.getByPlaceholder("검색 쿼리를 입력하세요...")
    ).toBeVisible();

    // 검색 버튼
    await expect(
      page.getByRole("button", { name: /검색/ })
    ).toBeVisible();
  });
});

test.describe("PC 뷰포트", () => {
  test.use({ viewport: { width: 1280, height: 720 } });

  test("사이드바 항상 표시", async ({ page }) => {
    await page.goto("/");

    await expect(
      page.locator("[data-testid='sidebar']")
    ).toBeVisible();
  });

  test("사이드바 네비게이션 항목 표시", async ({ page }) => {
    await page.goto("/");

    await expect(page.getByText("대시보드")).toBeVisible();
    await expect(page.getByText("문서 관리")).toBeVisible();
    await expect(page.getByText("검색 테스트")).toBeVisible();
    await expect(page.getByText("설정")).toBeVisible();
    await expect(page.getByText("평가")).toBeVisible();
    await expect(page.getByText("모니터링")).toBeVisible();
  });

  test("PC 대시보드 그리드 레이아웃", async ({ page }) => {
    await page.goto("/");

    // 대시보드 통계 카드 모두 표시
    await expect(page.getByText("총 문서")).toBeVisible();
    await expect(page.getByText("총 청크")).toBeVisible();
    await expect(page.getByText("오늘 쿼리")).toBeVisible();
    await expect(page.getByText("평균 응답 시간")).toBeVisible();
  });

  test("PC 문서 목록 테이블 전체 컬럼", async ({ page }) => {
    await page.goto("/documents");

    // 테이블 헤더 표시 (PC에서는 모든 컬럼 보임)
    await expect(page.getByText("파일명").first()).toBeVisible({ timeout: 10000 });
  });

  test("PC 네비게이션 이동", async ({ page }) => {
    await page.goto("/");

    // 사이드바에서 검색 테스트 클릭
    await page.getByText("검색 테스트").click();
    await page.waitForURL("/search");

    // 검색 페이지 확인
    await expect(
      page.getByPlaceholder("검색 쿼리를 입력하세요...")
    ).toBeVisible();
  });

  test("PC 설정 페이지 그리드", async ({ page }) => {
    await page.goto("/settings");

    // 3열 그리드로 설정 카테고리 표시
    await expect(page.getByText("청킹")).toBeVisible();
    await expect(page.getByText("가드레일")).toBeVisible();
    await expect(page.getByText("디렉토리 감시")).toBeVisible();
  });
});
