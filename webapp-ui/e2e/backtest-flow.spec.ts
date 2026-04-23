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

  test("runs 테이블 컬럼 클릭 정렬", async ({ page }) => {
    await page.goto("/backtest")
    const firstLink = page.locator("a[href*='/backtest/']").first()
    const visible = await firstLink.isVisible().catch(() => false)
    test.skip(!visible, "런 데이터 없음")
    // 이름 컬럼 클릭 → sort=name URL 반영
    const header = page.getByRole("columnheader", { name: /^이름/ }).first()
    if (await header.isVisible()) {
      await header.click()
      await expect(page).toHaveURL(/sort=name/)
    }
  })

  test("runs 내보내기 버튼 클릭 시 다운로드", async ({ page }) => {
    await page.goto("/backtest")
    const firstLink = page.locator("a[href*='/backtest/']").first()
    const visible = await firstLink.isVisible().catch(() => false)
    test.skip(!visible, "런 데이터 없음")
    const exportLink = page.getByRole("link", { name: /내보내기/ }).first()
    if (await exportLink.isVisible()) {
      const [download] = await Promise.all([
        page.waitForEvent("download"),
        exportLink.click(),
      ])
      expect(download.suggestedFilename()).toMatch(/backtest_runs_.*\.csv/)
    }
  })

  test("logout clears session", async ({ page }) => {
    await page.goto("/backtest")
    await page.getByRole("button", { name: "Logout" }).click()
    await page.goto("/backtest")
    await expect(page).toHaveURL(/\/login/)
  })
})
