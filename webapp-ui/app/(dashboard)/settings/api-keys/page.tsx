import { cookies } from "next/headers"
import { ApiError, apiFetch } from "@/lib/api-client"
import { SettingsTabs } from "@/components/domain/settings/settings-tabs"
import { ApiKeysForm } from "@/components/domain/settings/api-keys-form"
import { EncryptKeyMissing } from "@/components/domain/settings/encrypt-key-missing"

export const dynamic = "force-dynamic"

type Item = {
  key: string
  value: string
  is_secret: boolean
  category: string
  updated_at: number
}

export default async function ApiKeysPage() {
  const cookieStore = await cookies()
  const h = {
    cookie: cookieStore.getAll().map((c) => `${c.name}=${c.value}`).join("; "),
  }
  let items: Item[] | null = null
  try {
    const data = await apiFetch<{ items: Item[] }>(
      "/api/v1/settings?category=api_key",
      { headers: h, cache: "no-store" },
    )
    items = data.items
  } catch (e) {
    if (!(e instanceof ApiError) || e.status !== 404) throw e
  }
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">설정</h1>
      <SettingsTabs active="api-keys" />
      {items === null ? <EncryptKeyMissing /> : <ApiKeysForm items={items} />}
    </div>
  )
}
