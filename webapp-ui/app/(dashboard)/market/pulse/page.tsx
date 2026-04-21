import { cookies } from "next/headers"
import { apiFetch } from "@/lib/api-client"
import { PulseDashboardClient } from "@/components/domain/market/pulse-dashboard-client"
import type { PulseSnapshot } from "@/components/domain/market/score-hero-card"
import type { HistoryItem } from "@/components/domain/market/pulse-history-chart"

export const dynamic = "force-dynamic"

export default async function MarketPulsePage() {
  const cookieStore = await cookies()
  const h = {
    cookie: cookieStore.getAll().map((c) => `${c.name}=${c.value}`).join("; "),
  }
  const [latest, hist] = await Promise.all([
    apiFetch<PulseSnapshot | null>(
      "/api/v1/market/pulse/latest",
      { headers: h, cache: "no-store" },
    ),
    apiFetch<{ items: HistoryItem[] }>(
      "/api/v1/market/pulse/history?days=30",
      { headers: h, cache: "no-store" },
    ),
  ])
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">시황 (Market Pulse)</h1>
      <PulseDashboardClient latest={latest} history={hist.items} />
    </div>
  )
}
