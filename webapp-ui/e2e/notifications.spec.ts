import { expect, test } from "@playwright/test"

const EMAIL = process.env.E2E_ADMIN_EMAIL ?? "test@example.com"
const PASSWORD = process.env.E2E_ADMIN_PASSWORD ?? "test-password-12!"

test.describe("Notifications", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/login")
    await page.fill('input[type="email"]', EMAIL)
    await page.fill('input[type="password"]', PASSWORD)
    await page.click('button[type="submit"]')
    await expect(page).toHaveURL(/\/(?!login)/)
  })

  test("상단바에 알림 벨 아이콘이 보임", async ({ page }) => {
    await page.goto("/")
    await expect(
      page.getByRole("button", { name: /알림/ }),
    ).toBeVisible()
  })

  test("벨 아이콘 클릭 시 드롭다운이 열림", async ({ page }) => {
    await page.goto("/")
    await page.getByRole("button", { name: /알림/ }).click()
    // 드롭다운 헤더 "알림" 제목 또는 빈 상태 "알림 없음" 문구
    await expect(
      page.getByText("알림 없음").or(page.getByText("알림").nth(1)),
    ).toBeVisible()
  })
})
