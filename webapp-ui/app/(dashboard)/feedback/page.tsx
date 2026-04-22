import { cookies } from "next/headers"
import { apiFetch } from "@/lib/api-client"
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

export default async function FeedbackPage({ searchParams }: Props) {
  const sp = await searchParams
  const days = Math.min(365, Math.max(1, Number(sp.days || 30)))
  const page = Math.max(1, Number(sp.page || 1))

  const cookieStore = await cookies()
  const h = {
    cookie: cookieStore.getAll().map((c) => `${c.name}=${c.value}`).join("; "),
  }

  const [summary, history] = await Promise.all([
    apiFetch<SummaryResponse>(
      `/api/v1/feedback/summary?days=${days}`,
      { headers: h, cache: "no-store" },
    ),
    apiFetch<HistoryResponse>(
      `/api/v1/feedback/history?days=${days}&page=${page}&size=20`,
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
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div className="md:col-span-1">
              <CorrelationCard correlation={summary.correlation} />
            </div>
            <div className="md:col-span-1"></div>
          </div>
          <HitRateCards rates={summary.hit_rates} />
          <IndicatorAccuracyChart items={summary.indicator_accuracy} />
          <SignalHistoryTable data={history} />
        </>
      )}
    </div>
  )
}
