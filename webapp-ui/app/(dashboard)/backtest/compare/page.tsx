import { cookies } from "next/headers"
import { apiFetch } from "@/lib/api-client"
import { MetricsCards } from "@/components/domain/backtest/metrics-cards"
import type { RunDetail } from "@/lib/types"

export const dynamic = "force-dynamic"

type Props = { searchParams: Promise<{ ids?: string }> }

export default async function ComparePage({ searchParams }: Props) {
  const sp = await searchParams
  const ids = sp.ids
  if (!ids || ids.split(",").length !== 2) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-semibold">백테스트 비교</h1>
        <p className="text-neutral-400">
          URL 파라미터에 ids=a,b 형식으로 두 run_id(또는 접두사)를 지정하세요.
        </p>
      </div>
    )
  }
  const cookieStore = await cookies()
  const h = { cookie: cookieStore.getAll().map((c) => `${c.name}=${c.value}`).join("; ") }
  const data = await apiFetch<{ a: RunDetail; b: RunDetail }>(
    `/api/v1/backtest/compare`,
    { headers: h, cache: "no-store", searchParams: { ids } },
  )

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">백테스트 비교</h1>
      <div className="grid gap-6 md:grid-cols-2">
        {[data.a, data.b].map((r, i) => (
          <div key={i} className="space-y-3 rounded-lg border border-neutral-800 p-4">
            <div>
              <p className="text-sm text-neutral-400">ID {i + 1}</p>
              <p className="font-semibold">{r.name || r.run_id.slice(0, 8)}</p>
              <p className="text-xs text-neutral-500">{r.start_date}~{r.end_date}</p>
            </div>
            <MetricsCards metrics={r.metrics} />
          </div>
        ))}
      </div>
    </div>
  )
}
