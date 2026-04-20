import { cookies } from "next/headers"
import { apiFetch } from "@/lib/api-client"
import { RiskCards } from "@/components/domain/risk/risk-cards"

export const dynamic = "force-dynamic"

type Props = { searchParams: Promise<{ mode?: string }> }

export default async function RiskPage({ searchParams }: Props) {
  const sp = await searchParams
  const mode = sp.mode || "paper"
  const cookieStore = await cookies()
  const h = { cookie: cookieStore.getAll().map((c) => `${c.name}=${c.value}`).join("; ") }
  const data = await apiFetch<{
    report: {
      drawdown_status: string
      var_95: number
      cvar_95: number
      alerts: { level: string; message: string }[]
    }
    stress: Record<string, number>
    cached: boolean
    computed_at?: number
  } | null>(`/api/v1/risk/report?mode=${mode}`, {
    headers: h, cache: "no-store",
  })
  if (!data) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-semibold">리스크 ({mode})</h1>
        <p className="text-neutral-500">스냅샷 없음.</p>
      </div>
    )
  }
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">리스크 ({mode})</h1>
      <RiskCards report={data.report} cached={data.cached} />
      <div>
        <h2 className="text-lg mb-2">경고</h2>
        {data.report.alerts.length === 0 ? (
          <p className="text-sm text-neutral-500">경고 없음.</p>
        ) : (
          <ul className="space-y-1">
            {data.report.alerts.map((a, i) => (
              <li key={i} className="text-sm">
                <span className={`font-mono mr-2 ${a.level === "CRITICAL" ? "text-red-400" : "text-yellow-400"}`}>
                  [{a.level}]
                </span>
                {a.message}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
