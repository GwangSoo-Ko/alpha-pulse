import { cookies } from "next/headers"
import { apiFetch } from "@/lib/api-client"
import { HistoryChart } from "@/components/domain/portfolio/history-chart"

export const dynamic = "force-dynamic"

type Props = { searchParams: Promise<{ mode?: string; days?: string }> }

export default async function PortfolioHistoryPage({ searchParams }: Props) {
  const sp = await searchParams
  const mode = sp.mode || "paper"
  const days = Number(sp.days || 30)
  const cookieStore = await cookies()
  const h = { cookie: cookieStore.getAll().map((c) => `${c.name}=${c.value}`).join("; ") }
  const data = await apiFetch<{
    items: { date: string; total_value: number; daily_return: number }[]
  }>(`/api/v1/portfolio/history?mode=${mode}&days=${days}`, {
    headers: h, cache: "no-store",
  })
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">포트폴리오 이력 ({mode}, {days}일)</h1>
      <HistoryChart snapshots={data.items} />
    </div>
  )
}
