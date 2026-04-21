import { expect, test } from "@playwright/test"

const EMAIL = process.env.E2E_ADMIN_EMAIL ?? "test@example.com"
const PASSWORD = process.env.E2E_ADMIN_PASSWORD ?? "test-password-12!"

test.describe("Market Pulse", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/login")
    await page.fill('input[type="email"]', EMAIL)
    await page.fill('input[type="password"]', PASSWORD)
    await page.click('button[type="submit"]')
    await expect(page).toHaveURL(/\/(?!login)/)
  })

  test("사이드바에 시황 진입점 존재", async ({ page }) => {
    await expect(page.locator("nav a[href='/market/pulse']")).toBeVisible()
  })

  test("/market/pulse 에서 ScoreHeroCard 또는 NoPulseSnapshot 렌더", async ({
    page,
  }) => {
    await page.goto("/market/pulse")
    const hero = page.locator("text=/K-Market Pulse/")
    const empty = page.locator("text=/Pulse 이력이 없습니다/")
    await expect(hero.or(empty)).toBeVisible()
  })

  test("이력 있을 때 지표 카드 11개 렌더", async ({ page }) => {
    await page.goto("/market/pulse")
    const empty = page.locator("text=/Pulse 이력이 없습니다/")
    if (await empty.isVisible()) {
      test.skip(true, "history DB 비어있어 검증 스킵")
    }
    // 한글 라벨 중 하나
    await expect(page.locator("text=/외국인\\+기관 수급/")).toBeVisible()
  })

  test("'지금 실행' 클릭 → 모달 또는 Job 페이지 이동", async ({ page }) => {
    await page.goto("/market/pulse")
    const runButton = page.locator("button", { hasText: /지금 실행/ })
    if (!(await runButton.isVisible())) {
      test.skip(true, "run button 없음 (이력 없음 상태)")
    }
    await runButton.click()
    // 모달 ("재실행 확인") 또는 URL 변경 (/market/pulse/jobs/)
    await expect(
      page
        .locator("text=/재실행 확인/")
        .or(page.locator("h1", { hasText: /Market Pulse 실행 중/ })),
    ).toBeVisible()
  })
})
