import { cookies } from "next/headers"
import { apiFetch } from "@/lib/api-client"
import { SummaryCard } from "@/components/domain/portfolio/summary-card"
import { HoldingsTable } from "@/components/domain/portfolio/holdings-table"

export const dynamic = "force-dynamic"

type Props = { searchParams: Promise<{ mode?: string }> }

export default async function PortfolioPage({ searchParams }: Props) {
  const sp = await searchParams
  const mode = sp.mode || "paper"
  const cookieStore = await cookies()
  const h = { cookie: cookieStore.getAll().map((c) => `${c.name}=${c.value}`).join("; ") }
  const snap = await apiFetch<{
    date: string; cash: number; total_value: number
    daily_return: number; cumulative_return: number; drawdown: number
    positions: { code: string; name: string; quantity: number; avg_price: number; current_price: number; unrealized_pnl: number; weight: number }[]
  } | null>(`/api/v1/portfolio?mode=${mode}`, {
    headers: h, cache: "no-store",
  })
  if (!snap) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-semibold">포트폴리오 ({mode})</h1>
        <p className="text-neutral-500">스냅샷 없음.</p>
      </div>
    )
  }
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">포트폴리오 — {snap.date} ({mode})</h1>
      <SummaryCard snapshot={snap} />
      <HoldingsTable positions={snap.positions} />
    </div>
  )
}
