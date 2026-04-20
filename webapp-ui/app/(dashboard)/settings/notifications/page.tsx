import { cookies } from "next/headers"
import { apiFetch } from "@/lib/api-client"
import { SettingsTabs } from "@/components/domain/settings/settings-tabs"
import { CategorySettingsForm } from "@/components/domain/settings/category-settings-form"

export const dynamic = "force-dynamic"

const LABELS: Record<string, string> = {
  TELEGRAM_BOT_TOKEN: "Telegram Bot Token (콘텐츠)",
  TELEGRAM_CHANNEL_ID: "Telegram Channel ID (콘텐츠)",
  TELEGRAM_MONITOR_BOT_TOKEN: "Telegram Bot Token (모니터링)",
  TELEGRAM_MONITOR_CHANNEL_ID: "Telegram Channel ID (모니터링)",
}

export default async function NotificationsPage() {
  const cookieStore = await cookies()
  const h = { cookie: cookieStore.getAll().map((c) => `${c.name}=${c.value}`).join("; ") }
  const data = await apiFetch<{
    items: { key: string; value: string; is_secret: boolean; category: string; updated_at: number }[]
  }>("/api/v1/settings?category=notification", { headers: h, cache: "no-store" })
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">설정</h1>
      <SettingsTabs active="notifications" />
      <CategorySettingsForm items={data.items} labels={LABELS} />
    </div>
  )
}
