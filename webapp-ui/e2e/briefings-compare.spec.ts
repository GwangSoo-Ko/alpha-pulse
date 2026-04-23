import { expect, test } from "@playwright/test"

const EMAIL = process.env.E2E_ADMIN_EMAIL ?? "test@example.com"
const PASSWORD = process.env.E2E_ADMIN_PASSWORD ?? "test-password-12!"

test.describe("Briefing Compare", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/login")
    await page.fill('input[type="email"]', EMAIL)
    await page.fill('input[type="password"]', PASSWORD)
    await page.click('button[type="submit"]')
    await expect(page).toHaveURL(/\/(?!login)/)
  })

  test("체크박스 0개면 비교 버튼 disabled", async ({ page }) => {
    await page.goto("/briefings")
    const btn = page.getByRole("button", { name: /비교하기/ })
    await expect(btn).toBeDisabled()
  })

  test("같은 날짜 URL 직접 진입 → 상세 리다이렉트", async ({ page }) => {
    await page.goto("/briefings/compare?a=20260421&b=20260421")
    await expect(page).toHaveURL(/\/briefings\/20260421$/)
  })

  test("a 파라미터 누락 → 목록으로 리다이렉트", async ({ page }) => {
    await page.goto("/briefings/compare?b=20260421")
    await expect(page).toHaveURL(/\/briefings($|\?)/)
  })

  test("두 날짜 모두 존재하지 않는 경우 empty state", async ({ page }) => {
    await page.goto("/briefings/compare?a=19990101&b=19990102")
    await expect(
      page.getByText("두 날짜 모두 브리핑이 없습니다"),
    ).toBeVisible()
  })

  test("체크박스 2개 선택 → 비교 버튼 활성화 → 비교 페이지 이동", async ({ page }) => {
    await page.goto("/briefings")
    const checkboxes = page.locator('input[type="checkbox"]')
    const count = await checkboxes.count()
    test.skip(count < 2, "브리핑 2개 미만 — 비교 스모크 스킵")
    await checkboxes.nth(0).check()
    await checkboxes.nth(1).check()
    const btn = page.getByRole("button", { name: /비교하기/ })
    await expect(btn).toBeEnabled()
    await btn.click()
    await expect(page).toHaveURL(/\/briefings\/compare\?a=\d{8}&b=\d{8}/)
    await expect(page.getByRole("heading", { name: "브리핑 비교" })).toBeVisible()
  })
})
