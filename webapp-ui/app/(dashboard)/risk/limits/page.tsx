import Link from "next/link"
import { cookies } from "next/headers"
import { apiFetch } from "@/lib/api-client"
import { Card } from "@/components/ui/card"
import { fmtPct } from "@/lib/format"

export const dynamic = "force-dynamic"

export default async function LimitsPage() {
  const cookieStore = await cookies()
  const h = { cookie: cookieStore.getAll().map((c) => `${c.name}=${c.value}`).join("; ") }
  const data = await apiFetch<{
    max_position_weight: number
    max_drawdown_soft: number
    max_drawdown_hard: number
    max_daily_orders: number
    max_daily_amount: number
  }>("/api/v1/risk/limits", { headers: h, cache: "no-store" })

  const rows: Array<[string, string]> = [
    ["종목당 최대 비중", fmtPct(data.max_position_weight * 100, 1)],
    ["MDD soft 임계값", fmtPct(data.max_drawdown_soft * 100, 1)],
    ["MDD hard 임계값", fmtPct(data.max_drawdown_hard * 100, 1)],
    ["일일 주문 한도", `${data.max_daily_orders}회`],
    ["일일 금액 한도", `${data.max_daily_amount.toLocaleString("ko-KR")}원`],
  ]

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-semibold">리스크 리밋</h1>
        <Link href="/settings/risk-limits" className="text-sm text-blue-400 hover:underline">
          Settings에서 수정 →
        </Link>
      </div>
      <Card className="p-6 space-y-3">
        {rows.map(([label, val]) => (
          <div key={label} className="flex justify-between py-2 border-b border-neutral-800 last:border-0">
            <span className="text-neutral-400">{label}</span>
            <span className="font-mono">{val}</span>
          </div>
        ))}
      </Card>
    </div>
  )
}
