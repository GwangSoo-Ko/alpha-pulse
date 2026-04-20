import { cookies } from "next/headers"
import { ApiError, apiFetch } from "@/lib/api-client"
import { SettingsTabs } from "@/components/domain/settings/settings-tabs"
import { CategorySettingsForm } from "@/components/domain/settings/category-settings-form"
import { EncryptKeyMissing } from "@/components/domain/settings/encrypt-key-missing"

export const dynamic = "force-dynamic"

const LABELS: Record<string, string> = {
  BACKTEST_COMMISSION: "수수료율 (0-1)",
  BACKTEST_TAX: "세금율 (0-1)",
  BACKTEST_INITIAL_CAPITAL: "기본 초기 자본 (원)",
  STRATEGY_ALLOCATIONS: "전략 배분 (JSON)",
}

type Item = {
  key: string
  value: string
  is_secret: boolean
  category: string
  updated_at: number
}

export default async function BacktestDefaultsPage() {
  const cookieStore = await cookies()
  const h = {
    cookie: cookieStore.getAll().map((c) => `${c.name}=${c.value}`).join("; "),
  }
  let items: Item[] | null = null
  try {
    const data = await apiFetch<{ items: Item[] }>(
      "/api/v1/settings?category=backtest",
      { headers: h, cache: "no-store" },
    )
    items = data.items
  } catch (e) {
    if (!(e instanceof ApiError) || e.status !== 404) throw e
  }
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">설정</h1>
      <SettingsTabs active="backtest-defaults" />
      {items === null ? (
        <EncryptKeyMissing />
      ) : (
        <CategorySettingsForm items={items} labels={LABELS} />
      )}
    </div>
  )
}
