import { cookies } from "next/headers"
import { ApiError, apiFetch } from "@/lib/api-client"
import { SettingsTabs } from "@/components/domain/settings/settings-tabs"
import { CategorySettingsForm } from "@/components/domain/settings/category-settings-form"
import { EncryptKeyMissing } from "@/components/domain/settings/encrypt-key-missing"

export const dynamic = "force-dynamic"

const LABELS: Record<string, string> = {
  TELEGRAM_BOT_TOKEN: "Telegram Bot Token (콘텐츠)",
  TELEGRAM_CHANNEL_ID: "Telegram Channel ID (콘텐츠)",
  TELEGRAM_MONITOR_BOT_TOKEN: "Telegram Bot Token (모니터링)",
  TELEGRAM_MONITOR_CHANNEL_ID: "Telegram Channel ID (모니터링)",
}

type Item = {
  key: string
  value: string
  is_secret: boolean
  category: string
  updated_at: number
}

export default async function NotificationsPage() {
  const cookieStore = await cookies()
  const h = {
    cookie: cookieStore.getAll().map((c) => `${c.name}=${c.value}`).join("; "),
  }
  let items: Item[] | null = null
  try {
    const data = await apiFetch<{ items: Item[] }>(
      "/api/v1/settings?category=notification",
      { headers: h, cache: "no-store" },
    )
    items = data.items
  } catch (e) {
    if (!(e instanceof ApiError) || e.status !== 404) throw e
  }
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">설정</h1>
      <SettingsTabs active="notifications" />
      {items === null ? (
        <EncryptKeyMissing />
      ) : (
        <CategorySettingsForm items={items} labels={LABELS} />
      )}
    </div>
  )
}
