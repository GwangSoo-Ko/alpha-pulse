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

  test("탭 4개 렌더 + 기본 요약 탭", async ({ page }) => {
    await page.goto("/feedback")
    const empty = page.getByText("평가된 시그널이 없습니다")
    const isEmpty = await empty.isVisible().catch(() => false)
    test.skip(isEmpty, "DB 비어있음 — 탭 스모크 스킵")
    await expect(page.getByRole("tab", { name: "요약" })).toBeVisible()
    await expect(page.getByRole("tab", { name: "추이" })).toBeVisible()
    await expect(page.getByRole("tab", { name: "지표" })).toBeVisible()
    await expect(page.getByRole("tab", { name: "이력" })).toBeVisible()
  })

  test("추이 탭 클릭 → HitRateTrendChart 영역", async ({ page }) => {
    await page.goto("/feedback")
    const empty = page.getByText("평가된 시그널이 없습니다")
    const isEmpty = await empty.isVisible().catch(() => false)
    test.skip(isEmpty, "DB 비어있음")
    await page.getByRole("tab", { name: "추이" }).click()
    await expect(page.getByText(/적중률 추이/)).toBeVisible()
  })

  test("지표 탭 클릭 → 히트맵 영역", async ({ page }) => {
    await page.goto("/feedback")
    const empty = page.getByText("평가된 시그널이 없습니다")
    const isEmpty = await empty.isVisible().catch(() => false)
    test.skip(isEmpty, "DB 비어있음")
    await page.getByRole("tab", { name: "지표" }).click()
    await expect(page.getByText(/지표 히트맵/)).toBeVisible()
  })

  test("이력 탭 클릭 → 시그널 히스토리 테이블", async ({ page }) => {
    await page.goto("/feedback")
    const empty = page.getByText("평가된 시그널이 없습니다")
    const isEmpty = await empty.isVisible().catch(() => false)
    test.skip(isEmpty, "DB 비어있음")
    await page.getByRole("tab", { name: "이력" }).click()
    await expect(page.getByRole("table")).toBeVisible()
  })
})
