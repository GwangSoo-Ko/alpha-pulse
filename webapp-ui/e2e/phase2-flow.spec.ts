import { expect, test } from "@playwright/test"

const EMAIL = process.env.E2E_ADMIN_EMAIL ?? "test@example.com"
const PASSWORD = process.env.E2E_ADMIN_PASSWORD ?? "test-password-12!"

test.describe.serial("Phase 2 flow smoke", () => {
  test("login", async ({ page }) => {
    await page.goto("/login")
    await page.fill('input[type="email"]', EMAIL)
    await page.fill('input[type="password"]', PASSWORD)
    await page.click('button[type="submit"]')
    await expect(page).toHaveURL(/\/(?!login)/)
  })

  test("mode selector changes URL", async ({ page }) => {
    await page.goto("/portfolio")
    await page.selectOption('select[aria-label="Mode selector"]', "backtest")
    await expect(page).toHaveURL(/mode=backtest/)
  })

  test("risk page loads", async ({ page }) => {
    await page.goto("/risk")
    await expect(page.getByRole("heading", { name: /리스크/ })).toBeVisible()
  })

  test("screening list loads", async ({ page }) => {
    await page.goto("/screening")
    await expect(page.getByRole("heading", { name: /스크리닝/ })).toBeVisible()
    await expect(page.getByRole("button", { name: "새 스크리닝" })).toBeVisible()
  })

  test("data page shows collect_all disabled", async ({ page }) => {
    await page.goto("/data")
    const disabled = page.getByRole("button", { name: /전종목 수집/ })
    await expect(disabled).toBeVisible()
    await expect(disabled).toBeDisabled()
  })

  test("settings tabs navigate", async ({ page }) => {
    await page.goto("/settings/api-keys")
    await expect(page.getByRole("heading", { name: "설정" })).toBeVisible()
    await page.click('a[href="/settings/risk-limits"]')
    await expect(page).toHaveURL(/risk-limits/)
  })

  test("audit viewer loads", async ({ page }) => {
    await page.goto("/audit")
    await expect(page.getByRole("heading", { name: "감사 로그" })).toBeVisible()
  })
})
