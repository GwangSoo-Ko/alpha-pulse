import { cookies } from "next/headers"
import { apiFetch } from "@/lib/api-client"
import { AttributionBars } from "@/components/domain/portfolio/attribution-bars"

export const dynamic = "force-dynamic"

type Props = { searchParams: Promise<{ mode?: string; date?: string }> }

export default async function AttributionPage({ searchParams }: Props) {
  const sp = await searchParams
  const mode = sp.mode || "paper"
  const cookieStore = await cookies()
  const h = { cookie: cookieStore.getAll().map((c) => `${c.name}=${c.value}`).join("; ") }
  const url = `/api/v1/portfolio/attribution?mode=${mode}${sp.date ? `&date=${sp.date}` : ""}`
  const data = await apiFetch<{
    date: string
    strategy_returns: Record<string, number>
    factor_returns: Record<string, number>
    sector_returns: Record<string, number>
  } | null>(url, { headers: h, cache: "no-store" })
  if (!data) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-semibold">성과 귀속 ({mode})</h1>
        <p className="text-neutral-500">attribution 데이터 없음.</p>
      </div>
    )
  }
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">성과 귀속 — {data.date} ({mode})</h1>
      <AttributionBars title="전략별" data={data.strategy_returns} />
      <AttributionBars title="섹터별" data={data.sector_returns} />
      <AttributionBars title="팩터별" data={data.factor_returns} />
    </div>
  )
}
