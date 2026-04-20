import { cookies } from "next/headers"
import { notFound } from "next/navigation"
import { ApiError, apiFetch } from "@/lib/api-client"
import { PositionViewer } from "@/components/domain/backtest/position-viewer"
import type { Position, RunDetail } from "@/lib/types"

export const dynamic = "force-dynamic"

type Props = {
  params: Promise<{ runId: string }>
  searchParams: Promise<{ date?: string; code?: string }>
}

export default async function PositionsPage({ params, searchParams }: Props) {
  const { runId } = await params
  const sp = await searchParams
  const cookieStore = await cookies()
  const h = { cookie: cookieStore.getAll().map((c) => `${c.name}=${c.value}`).join("; ") }

  try {
    const run = await apiFetch<RunDetail>(
      `/api/v1/backtest/runs/${runId}`,
      { headers: h, cache: "no-store" },
    )
    // 기본: 전 기간 → 날짜 선택 UI에서 필터
    const pos = await apiFetch<{ items: Position[] }>(
      `/api/v1/backtest/runs/${runId}/positions`,
      {
        headers: h, cache: "no-store",
        searchParams: { date: sp.date, code: sp.code },
      },
    )
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-semibold">
          포지션 이력 — {run.name || runId.slice(0, 8)}
        </h1>
        <PositionViewer
          positions={pos.items}
          initialDate={sp.date}
          initialCode={sp.code}
          startDate={run.start_date}
          endDate={run.end_date}
        />
      </div>
    )
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound()
    throw e
  }
}
