import { test, expect } from "@playwright/test";

test.describe("설정", () => {
  test("설정 카테고리 목록 표시", async ({ page }) => {
    await page.goto("/settings");

    // 페이지 타이틀
    await expect(page.getByText("설정").first()).toBeVisible();

    // 설정 카테고리 카드 확인
    await expect(page.getByText("청킹")).toBeVisible();
    await expect(page.getByText("임베딩")).toBeVisible();
    await expect(page.getByText("검색").first()).toBeVisible();
    await expect(page.getByText("리랭킹")).toBeVisible();
    await expect(page.getByText("HyDE")).toBeVisible();
    await expect(page.getByText("가드레일")).toBeVisible();
    await expect(page.getByText("답변 생성")).toBeVisible();
    await expect(page.getByText("디렉토리 감시")).toBeVisible();
  });

  test("가드레일 ON/OFF 토글", async ({ page }) => {
    await page.goto("/settings/guardrails");

    // 페이지 타이틀
    await expect(page.getByText("가드레일 설정")).toBeVisible();

    // PII 탐지 토글 확인
    await expect(page.getByText("PII 탐지")).toBeVisible();

    // 프롬프트 인젝션 탐지 토글 확인
    await expect(page.getByText("프롬프트 인젝션 탐지")).toBeVisible();

    // 할루시네이션 탐지 토글 확인
    await expect(page.getByText("할루시네이션 탐지")).toBeVisible();

    // 저장 버튼 확인
    await expect(
      page.getByRole("button", { name: /저장/ })
    ).toBeVisible();
  });

  test("검색 설정 변경", async ({ page }) => {
    await page.goto("/settings/search");

    // 페이지 타이틀
    await expect(page.getByText("검색 설정")).toBeVisible();

    // 검색 모드 셀렉트 확인
    await expect(page.getByText("검색 모드").first()).toBeVisible();

    // 키워드 엔진 확인
    await expect(page.getByText("키워드 엔진")).toBeVisible();

    // 벡터 가중치 슬라이더 확인
    await expect(page.getByText(/벡터 가중치/)).toBeVisible();

    // 키워드 가중치 슬라이더 확인
    await expect(page.getByText(/키워드 가중치/)).toBeVisible();

    // 저장 버튼 확인
    await expect(
      page.getByRole("button", { name: /저장/ })
    ).toBeVisible();
  });

  test("설정 페이지에서 뒤로가기", async ({ page }) => {
    await page.goto("/settings/guardrails");

    // 뒤로가기 버튼 클릭
    await page.getByRole("link", { name: /설정/ }).first().click();

    // 설정 메인 페이지로 이동 확인
    await expect(page.getByText("청킹")).toBeVisible();
  });

  test("청킹 설정 페이지", async ({ page }) => {
    await page.goto("/settings/chunking");

    await expect(
      page.getByRole("button", { name: /저장/ })
    ).toBeVisible();
  });

  test("임베딩 설정 페이지", async ({ page }) => {
    await page.goto("/settings/embedding");

    await expect(
      page.getByRole("button", { name: /저장/ })
    ).toBeVisible();
  });

  test("HyDE 설정 페이지", async ({ page }) => {
    await page.goto("/settings/hyde");

    await expect(
      page.getByRole("button", { name: /저장/ })
    ).toBeVisible();
  });

  test("답변 생성 설정 페이지", async ({ page }) => {
    await page.goto("/settings/generation");

    await expect(
      page.getByRole("button", { name: /저장/ })
    ).toBeVisible();
  });
});
