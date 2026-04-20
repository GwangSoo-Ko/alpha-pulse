import Link from "next/link"
import { cookies } from "next/headers"
import { notFound } from "next/navigation"
import { ApiError, apiFetch } from "@/lib/api-client"
import { Button } from "@/components/ui/button"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { MetricsCards } from "@/components/domain/backtest/metrics-cards"
import { EquityCurve } from "@/components/charts/equity-curve"
import { Drawdown } from "@/components/charts/drawdown"
import { MonthlyHeatmap } from "@/components/charts/monthly-heatmap"
import type { RunDetail, Snapshot } from "@/lib/types"

export const dynamic = "force-dynamic"

async function load(runId: string) {
  const cookieStore = await cookies()
  const cookieHeader = cookieStore
    .getAll()
    .map((c) => `${c.name}=${c.value}`)
    .join("; ")
  try {
    const run = await apiFetch<RunDetail>(`/api/v1/backtest/runs/${runId}`, {
      headers: { cookie: cookieHeader },
      cache: "no-store",
    })
    const snaps = await apiFetch<{ items: Snapshot[] }>(
      `/api/v1/backtest/runs/${runId}/snapshots`,
      { headers: { cookie: cookieHeader }, cache: "no-store" },
    )
    return { run, snaps: snaps.items }
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) return null
    throw e
  }
}

type Props = { params: Promise<{ runId: string }> }

export default async function BacktestDetailPage({ params }: Props) {
  const { runId } = await params
  const data = await load(runId)
  if (!data) notFound()
  const { run, snaps } = data

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">{run.name || "(no name)"}</h1>
          <p className="text-sm text-neutral-500">
            {run.strategies.join(", ")} · {run.start_date}~{run.end_date} ·
            초기 {run.initial_capital.toLocaleString()}원 → 최종{" "}
            {run.final_value.toLocaleString()}원
          </p>
        </div>
        <div className="space-x-2">
          <Link href={`/backtest/${runId}/trades`}>
            <Button variant="outline">거래 이력</Button>
          </Link>
          <Link href={`/backtest/${runId}/positions`}>
            <Button variant="outline">포지션</Button>
          </Link>
        </div>
      </div>
      <MetricsCards metrics={run.metrics} />
      <Tabs defaultValue="equity">
        <TabsList>
          <TabsTrigger value="equity">자산 곡선</TabsTrigger>
          <TabsTrigger value="drawdown">드로다운</TabsTrigger>
          <TabsTrigger value="monthly">월별 수익률</TabsTrigger>
        </TabsList>
        <TabsContent value="equity" className="rounded-lg border border-neutral-800 p-4">
          <EquityCurve snapshots={snaps} initialCapital={run.initial_capital} />
        </TabsContent>
        <TabsContent value="drawdown" className="rounded-lg border border-neutral-800 p-4">
          <Drawdown snapshots={snaps} />
        </TabsContent>
        <TabsContent value="monthly" className="rounded-lg border border-neutral-800 p-4">
          <MonthlyHeatmap snapshots={snaps} />
        </TabsContent>
      </Tabs>
    </div>
  )
}
