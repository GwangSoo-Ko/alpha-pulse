import { expect, test } from "@playwright/test"

const EMAIL = process.env.E2E_ADMIN_EMAIL ?? "test@example.com"
const PASSWORD = process.env.E2E_ADMIN_PASSWORD ?? "test-password-12!"

test.describe("Home Dashboard", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/login")
    await page.fill('input[type="email"]', EMAIL)
    await page.fill('input[type="password"]', PASSWORD)
    await page.click('button[type="submit"]')
    await expect(page).toHaveURL(/\/(?!login)/)
  })

  test("홈 로드 → Hero + 6개 위젯 영역 존재", async ({ page }) => {
    await page.goto("/")
    await expect(page.locator("text=/Market Pulse/i").first()).toBeVisible()
    await expect(page.locator("text=/Feedback/i").first()).toBeVisible()
    await expect(page.locator("text=/Content/i").first()).toBeVisible()
    await expect(page.locator("text=/Portfolio/i").first()).toBeVisible()
    await expect(page.locator("text=/Risk/i").first()).toBeVisible()
    await expect(page.locator("text=/Data Health/i").first()).toBeVisible()
  })

  test("Pulse 위젯 클릭 → /market/pulse 이동", async ({ page }) => {
    await page.goto("/")
    await page.click("a[href='/market/pulse']")
    await expect(page).toHaveURL(/\/market\/pulse/)
  })

  test("Feedback 위젯 클릭 → /feedback 이동", async ({ page }) => {
    await page.goto("/")
    await page.click("a[href='/feedback']")
    await expect(page).toHaveURL(/\/feedback$/)
  })

  test("Content 위젯 클릭 → /content/reports 이동", async ({ page }) => {
    await page.goto("/")
    await page.click("a[href='/content/reports']")
    await expect(page).toHaveURL(/\/content\/reports/)
  })
})
