import { expect, test } from "@playwright/test"

const EMAIL = process.env.E2E_ADMIN_EMAIL ?? "test@example.com"
const PASSWORD = process.env.E2E_ADMIN_PASSWORD ?? "test-password-12!"

test.describe.serial("Backtest flow smoke test", () => {
  test("unauthenticated user is redirected to /login", async ({ page }) => {
    await page.goto("/backtest")
    await expect(page).toHaveURL(/\/login/)
  })

  test("login succeeds with valid credentials", async ({ page }) => {
    await page.goto("/login")
    await page.fill('input[type="email"]', EMAIL)
    await page.fill('input[type="password"]', PASSWORD)
    await page.click('button[type="submit"]')
    await expect(page).toHaveURL(/\/backtest/)
    await expect(page.getByRole("heading", { name: "백테스트 결과" })).toBeVisible()
  })

  test("navigate to new backtest form", async ({ page }) => {
    await page.goto("/backtest")
    await page.getByRole("link", { name: "새 백테스트" }).click()
    await expect(page).toHaveURL(/\/backtest\/new/)
  })

  test("logout clears session", async ({ page }) => {
    await page.goto("/backtest")
    await page.getByRole("button", { name: "Logout" }).click()
    await page.goto("/backtest")
    await expect(page).toHaveURL(/\/login/)
  })
})
