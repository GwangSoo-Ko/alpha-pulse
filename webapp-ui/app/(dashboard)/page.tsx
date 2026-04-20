import { cookies } from "next/headers"
import { apiFetch } from "@/lib/api-client"
import { PortfolioWidget } from "@/components/domain/home/portfolio-widget"
import { RiskStatusWidget } from "@/components/domain/home/risk-status-widget"
import { DataStatusWidget } from "@/components/domain/home/data-status-widget"
import { RecentBacktestsWidget } from "@/components/domain/home/recent-backtests-widget"
import { RecentAuditWidget } from "@/components/domain/home/recent-audit-widget"

export const dynamic = "force-dynamic"

type HomeData = {
  portfolio: {
    date: string
    cash: number
    total_value: number
    daily_return: number
    cumulative_return: number
    drawdown: number
    positions: { code: string; name: string; quantity: number; current_price: number }[]
  } | null
  portfolio_history: { date: string; total_value: number }[]
  risk: { report: { var_95?: number; cvar_95?: number; drawdown_status?: string; alerts?: { level: string; message: string }[] } } | null
  data_status: { tables: { name: string; row_count: number; latest_date: string | null }[]; gaps_count: number }
  recent_backtests: { run_id: string; name: string; start_date: string; end_date: string; metrics: Record<string, number> }[]
  recent_audits: { id: number; timestamp: number; event_type: string }[]
}

export default async function HomePage() {
  const cookieStore = await cookies()
  const h = { cookie: cookieStore.getAll().map((c) => `${c.name}=${c.value}`).join("; ") }
  const data = await apiFetch<HomeData>("/api/v1/dashboard/home", {
    headers: h, cache: "no-store",
  })
  return (
    <div className="grid gap-4 md:grid-cols-3">
      <div className="md:col-span-2">
        <PortfolioWidget
          portfolio={data.portfolio}
          history={data.portfolio_history}
        />
      </div>
      <div className="space-y-4">
        <RiskStatusWidget risk={data.risk} />
        <DataStatusWidget status={data.data_status} />
        <RecentBacktestsWidget items={data.recent_backtests} />
        <RecentAuditWidget items={data.recent_audits} />
      </div>
    </div>
  )
}
