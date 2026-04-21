import { cookies } from "next/headers"
import { notFound } from "next/navigation"
import { ApiError, apiFetch } from "@/lib/api-client"
import { ResultsTable } from "@/components/domain/screening/results-table"
import { Card } from "@/components/ui/card"

export const dynamic = "force-dynamic"

type Props = { params: Promise<{ runId: string }> }

export default async function ScreeningDetailPage({ params }: Props) {
  const { runId } = await params
  const cookieStore = await cookies()
  const h = { cookie: cookieStore.getAll().map((c) => `${c.name}=${c.value}`).join("; ") }
  let data: {
    run_id: string; name: string; market: string; strategy: string
    factor_weights: Record<string, number>; top_n: number
    market_context: Record<string, unknown>
    results: { code: string; name: string; market: string; score: number; factors: Record<string, number> }[]
    created_at: number
  }
  try {
    data = await apiFetch(`/api/v1/screening/runs/${runId}`, {
      headers: h, cache: "no-store",
    })
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound()
    throw e
  }
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">{data.name || data.run_id.slice(0, 8)}</h1>
        <p className="text-sm text-neutral-500">
          {data.market} · {data.strategy} · Top {data.top_n} · {new Date(data.created_at * 1000).toISOString().slice(0, 19).replace("T", " ")}
        </p>
      </div>
      {Object.keys(data.market_context).length > 0 && (
        <Card className="p-4">
          <h2 className="font-medium mb-2">시장 컨텍스트</h2>
          <pre className="text-xs text-neutral-400">
            {JSON.stringify(data.market_context, null, 2)}
          </pre>
        </Card>
      )}
      <ResultsTable results={data.results} />
    </div>
  )
}
