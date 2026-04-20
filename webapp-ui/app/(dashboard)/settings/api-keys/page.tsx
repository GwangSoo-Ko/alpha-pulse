import { cookies } from "next/headers"
import { apiFetch } from "@/lib/api-client"
import { SettingsTabs } from "@/components/domain/settings/settings-tabs"
import { ApiKeysForm } from "@/components/domain/settings/api-keys-form"

export const dynamic = "force-dynamic"

export default async function ApiKeysPage() {
  const cookieStore = await cookies()
  const h = { cookie: cookieStore.getAll().map((c) => `${c.name}=${c.value}`).join("; ") }
  const data = await apiFetch<{
    items: { key: string; value: string; is_secret: boolean; category: string; updated_at: number }[]
  }>("/api/v1/settings?category=api_key", { headers: h, cache: "no-store" })
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">설정</h1>
      <SettingsTabs active="api-keys" />
      <ApiKeysForm items={data.items} />
    </div>
  )
}
