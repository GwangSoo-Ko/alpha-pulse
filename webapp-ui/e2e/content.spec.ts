import { expect, test } from "@playwright/test"

const EMAIL = process.env.E2E_ADMIN_EMAIL ?? "test@example.com"
const PASSWORD = process.env.E2E_ADMIN_PASSWORD ?? "test-password-12!"

test.describe("Content", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/login")
    await page.fill('input[type="email"]', EMAIL)
    await page.fill('input[type="password"]', PASSWORD)
    await page.click('button[type="submit"]')
    await expect(page).toHaveURL(/\/(?!login)/)
  })

  test("사이드바에 콘텐츠 진입점 존재", async ({ page }) => {
    await expect(page.locator("nav a[href='/content']")).toBeVisible()
  })

  test("/content 로드 → 리스트 또는 빈 상태 렌더", async ({ page }) => {
    await page.goto("/content")
    const filterBar = page.locator("text=/카테고리/")
    const empty = page.locator("text=/리포트가 없습니다/")
    await expect(filterBar.or(empty)).toBeVisible()
  })

  test("'지금 실행' 버튼 존재", async ({ page }) => {
    await page.goto("/content")
    await expect(page.locator("button", { hasText: /지금 실행/ })).toBeVisible()
  })

  test("검색어 입력 → 결과 있으면 mark 태그 렌더", async ({ page }) => {
    await page.goto("/content?q=%EB%B0%98%EB%8F%84%EC%B2%B4") // q=반도체 URL-encoded
    const empty = page.getByText(/리포트가 없습니다/)
    const isEmpty = await empty.isVisible().catch(() => false)
    test.skip(isEmpty, "검색 결과 없음 — 스모크 스킵")
    await expect(page.locator("mark").first()).toBeVisible()
  })
})
