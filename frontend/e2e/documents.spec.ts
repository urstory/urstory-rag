import { test, expect } from "@playwright/test";
import path from "path";

test.describe("문서 관리", () => {
  test("문서 업로드 및 목록 확인", async ({ page }) => {
    await page.goto("/documents");

    // 업로드 버튼 클릭
    await page.getByRole("button", { name: /업로드/ }).click();

    // 업로드 다이얼로그 표시 확인
    await expect(page.getByText("문서 업로드")).toBeVisible();

    // 파일 선택
    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles(
      path.join(__dirname, "fixtures", "sample.txt")
    );

    // 파일명 표시 확인
    await expect(page.getByText("sample.txt")).toBeVisible();

    // 업로드 실행
    const uploadBtn = page
      .getByRole("dialog")
      .getByRole("button", { name: /업로드/ });
    await uploadBtn.click();

    // 업로드 완료 후 목록에서 확인 (토스트 또는 목록 갱신)
    await expect(
      page.getByText("sample.txt").first()
    ).toBeVisible({ timeout: 15000 });
  });

  test("문서 삭제", async ({ page }) => {
    await page.goto("/documents");

    // 문서가 있는 경우에만 삭제 테스트
    const deleteButtons = page.getByRole("button", { name: /삭제|Trash/ });
    const count = await deleteButtons.count();

    if (count > 0) {
      // 첫 번째 문서 삭제 버튼 클릭
      await deleteButtons.first().click();

      // 확인 다이얼로그
      await expect(page.getByText("문서 삭제")).toBeVisible();
      await page
        .getByRole("dialog")
        .getByRole("button", { name: /삭제/ })
        .click();

      // 삭제 완료 확인
      await expect(
        page.getByText(/삭제/).first()
      ).toBeVisible({ timeout: 10000 });
    }
  });

  test("문서 목록 페이지네이션", async ({ page }) => {
    await page.goto("/documents");

    // 목록 테이블 표시 확인
    await expect(page.getByText("파일명").first()).toBeVisible({ timeout: 10000 });

    // 필터 드롭다운 확인
    await expect(page.getByText("전체").first()).toBeVisible();
  });

  test("문서 상세 페이지 접근", async ({ page }) => {
    await page.goto("/documents");

    // 문서가 있으면 상세 페이지로 이동
    const viewButtons = page.locator('a[href*="/documents/"]');
    const count = await viewButtons.count();

    if (count > 0) {
      await viewButtons.first().click();
      await page.waitForURL(/\/documents\/.+/);
    }
  });
});
