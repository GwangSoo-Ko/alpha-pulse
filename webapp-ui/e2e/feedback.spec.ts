import { expect, test } from "@playwright/test"

const EMAIL = process.env.E2E_ADMIN_EMAIL ?? "test@example.com"
const PASSWORD = process.env.E2E_ADMIN_PASSWORD ?? "test-password-12!"

test.describe("Feedback", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/login")
    await page.fill('input[type="email"]', EMAIL)
    await page.fill('input[type="password"]', PASSWORD)
    await page.click('button[type="submit"]')
    await expect(page).toHaveURL(/\/(?!login)/)
  })

  test("사이드바에 피드백 진입점 존재", async ({ page }) => {
    await expect(page.locator("nav a[href='/feedback']")).toBeVisible()
  })

  test("/feedback 로드 → 대시보드 또는 빈 상태 렌더", async ({ page }) => {
    await page.goto("/feedback")
    const heading = page.locator("h1", { hasText: "피드백" })
    const empty = page.locator("text=/평가된 시그널이 없습니다/")
    const toggle = page.locator("button", { hasText: /30일/ })
    await expect(heading).toBeVisible()
    await expect(empty.or(toggle)).toBeVisible()
  })

  test("기간 토글 버튼 렌더", async ({ page }) => {
    await page.goto("/feedback")
    for (const d of [30, 60, 90]) {
      await expect(
        page.locator("button", { hasText: new RegExp(`${d}일`) }),
      ).toBeVisible()
    }
  })
})
