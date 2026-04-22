import { expect, test } from "@playwright/test"

const EMAIL = process.env.E2E_ADMIN_EMAIL ?? "test@example.com"
const PASSWORD = process.env.E2E_ADMIN_PASSWORD ?? "test-password-12!"

test.describe("Briefings", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/login")
    await page.fill('input[type="email"]', EMAIL)
    await page.fill('input[type="password"]', PASSWORD)
    await page.click('button[type="submit"]')
    await expect(page).toHaveURL(/\/(?!login)/)
  })

  test("사이드바에 브리핑 진입점 존재", async ({ page }) => {
    await expect(page.locator("nav a[href='/briefings']")).toBeVisible()
  })

  test("/briefings 로드 → 테이블 또는 빈 상태 렌더", async ({ page }) => {
    await page.goto("/briefings")
    const table = page.locator("text=/날짜/")
    const empty = page.locator("text=/브리핑이 없습니다/")
    await expect(table.or(empty)).toBeVisible()
  })

  test("'지금 실행' 버튼 렌더", async ({ page }) => {
    await page.goto("/briefings")
    await expect(
      page.locator("button", { hasText: /지금 실행/ }),
    ).toBeVisible()
  })
})
