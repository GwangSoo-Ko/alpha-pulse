import { cookies } from "next/headers"
import { notFound } from "next/navigation"
import { ApiError, apiFetch } from "@/lib/api-client"
import { TradesTable } from "@/components/domain/backtest/trades-table"
import type { RunDetail, Trade } from "@/lib/types"

export const dynamic = "force-dynamic"

type Props = {
  params: Promise<{ runId: string }>
  searchParams: Promise<{ code?: string; winner?: string }>
}

export default async function TradesPage({ params, searchParams }: Props) {
  const { runId } = await params
  const sp = await searchParams
  const cookieStore = await cookies()
  const h = { cookie: cookieStore.getAll().map((c) => `${c.name}=${c.value}`).join("; ") }

  try {
    const run = await apiFetch<RunDetail>(
      `/api/v1/backtest/runs/${runId}`,
      { headers: h, cache: "no-store" },
    )
    const trades = await apiFetch<{ items: Trade[] }>(
      `/api/v1/backtest/runs/${runId}/trades`,
      {
        headers: h, cache: "no-store",
        searchParams: { code: sp.code, winner: sp.winner },
      },
    )
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-semibold">거래 이력 — {run.name || runId.slice(0, 8)}</h1>
        <TradesTable trades={trades.items} initialFilters={sp} />
      </div>
    )
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound()
    throw e
  }
}
