import { cookies } from "next/headers"
import { apiFetch } from "@/lib/api-client"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { HitRateCards, type HitRates } from "@/components/domain/feedback/hit-rate-cards"
import { CorrelationCard } from "@/components/domain/feedback/correlation-card"
import {
  IndicatorAccuracyChart,
  type IndicatorAccuracy,
} from "@/components/domain/feedback/indicator-accuracy-chart"
import {
  SignalHistoryTable,
  type SignalHistoryItem,
} from "@/components/domain/feedback/signal-history-table"
import { PeriodToggle } from "@/components/domain/feedback/period-toggle"
import { NoFeedback } from "@/components/domain/feedback/no-feedback"
import {
  HitRateTrendChart,
  type HitRateTrendPoint,
} from "@/components/domain/feedback/hit-rate-trend-chart"
import {
  ScoreReturnScatter,
  type ScoreReturnPoint,
} from "@/components/domain/feedback/score-return-scatter"
import {
  IndicatorHeatmap,
  type IndicatorHeatmapCell,
} from "@/components/domain/feedback/indicator-heatmap"
import {
  SignalBreakdownTable,
  type SignalBreakdownRow,
} from "@/components/domain/feedback/signal-breakdown-table"

export const dynamic = "force-dynamic"

type Props = {
  searchParams: Promise<{ days?: string; page?: string }>
}

type SummaryResponse = {
  days: number
  hit_rates: HitRates
  correlation: number | null
  indicator_accuracy: IndicatorAccuracy[]
  recent_history: SignalHistoryItem[]
}

type HistoryResponse = {
  items: SignalHistoryItem[]
  page: number
  size: number
  total: number
}

type AnalyticsResponse = {
  days: number
  hit_rate_trend: HitRateTrendPoint[]
  score_return_points: ScoreReturnPoint[]
  indicator_heatmap: IndicatorHeatmapCell[]
  signal_breakdown: SignalBreakdownRow[]
}

export default async function FeedbackPage({ searchParams }: Props) {
  const sp = await searchParams
  const days = Math.min(365, Math.max(1, Number(sp.days || 30)))
  const page = Math.max(1, Number(sp.page || 1))

  const cookieStore = await cookies()
  const h = {
    cookie: cookieStore.getAll().map((c) => `${c.name}=${c.value}`).join("; "),
  }

  const [summary, history, analytics] = await Promise.all([
    apiFetch<SummaryResponse>(
      `/api/v1/feedback/summary?days=${days}`,
      { headers: h, cache: "no-store" },
    ),
    apiFetch<HistoryResponse>(
      `/api/v1/feedback/history?days=${days}&page=${page}&size=20`,
      { headers: h, cache: "no-store" },
    ),
    apiFetch<AnalyticsResponse>(
      `/api/v1/feedback/analytics?days=${days}`,
      { headers: h, cache: "no-store" },
    ),
  ])

  const empty = summary.hit_rates.total_evaluated === 0

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-semibold">피드백</h1>
        <PeriodToggle current={days} />
      </div>
      {empty ? (
        <NoFeedback />
      ) : (
        <Tabs defaultValue="summary" className="space-y-4">
          <TabsList>
            <TabsTrigger value="summary">요약</TabsTrigger>
            <TabsTrigger value="trend">추이</TabsTrigger>
            <TabsTrigger value="indicators">지표</TabsTrigger>
            <TabsTrigger value="history">이력</TabsTrigger>
          </TabsList>

          <TabsContent value="summary" className="space-y-4">
            <HitRateCards rates={summary.hit_rates} />
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <CorrelationCard correlation={summary.correlation} />
            </div>
            <SignalBreakdownTable rows={analytics.signal_breakdown} />
          </TabsContent>

          <TabsContent value="trend" className="space-y-4">
            <HitRateTrendChart points={analytics.hit_rate_trend} />
            <ScoreReturnScatter points={analytics.score_return_points} />
          </TabsContent>

          <TabsContent value="indicators" className="space-y-4">
            <IndicatorAccuracyChart items={summary.indicator_accuracy} />
            <IndicatorHeatmap cells={analytics.indicator_heatmap} />
          </TabsContent>

          <TabsContent value="history" className="space-y-4">
            <SignalHistoryTable data={history} />
          </TabsContent>
        </Tabs>
      )}
    </div>
  )
}
