import { cookies } from "next/headers"
import { apiFetch } from "@/lib/api-client"
import { SettingsTabs } from "@/components/domain/settings/settings-tabs"
import { RiskLimitsForm } from "@/components/domain/settings/risk-limits-form"

export const dynamic = "force-dynamic"

export default async function RiskLimitsPage() {
  const cookieStore = await cookies()
  const h = { cookie: cookieStore.getAll().map((c) => `${c.name}=${c.value}`).join("; ") }
  const data = await apiFetch<{
    items: { key: string; value: string; is_secret: boolean; category: string; updated_at: number }[]
  }>("/api/v1/settings?category=risk_limit", { headers: h, cache: "no-store" })
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">설정</h1>
      <SettingsTabs active="risk-limits" />
      <RiskLimitsForm items={data.items} />
    </div>
  )
}
