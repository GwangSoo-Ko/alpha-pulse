import { cookies } from "next/headers"
import { notFound } from "next/navigation"
import { ApiError, apiFetch } from "@/lib/api-client"
import { ScoreHeroCard, type PulseSnapshot } from "@/components/domain/market/score-hero-card"
import { IndicatorGrid } from "@/components/domain/market/indicator-grid"
import { DatePickerInline } from "@/components/domain/market/date-picker-inline"
import type { HistoryItem } from "@/components/domain/market/pulse-history-chart"

export const dynamic = "force-dynamic"

type Props = { params: Promise<{ date: string }> }

export default async function PulseDetailPage({ params }: Props) {
  const { date } = await params
  const cookieStore = await cookies()
  const h = {
    cookie: cookieStore.getAll().map((c) => `${c.name}=${c.value}`).join("; "),
  }

  try {
    const [snapshot, hist] = await Promise.all([
      apiFetch<PulseSnapshot>(
        `/api/v1/market/pulse/${date}`,
        { headers: h, cache: "no-store" },
      ),
      apiFetch<{ items: HistoryItem[] }>(
        "/api/v1/market/pulse/history?days=365",
        { headers: h, cache: "no-store" },
      ),
    ])
    const availableDates = hist.items.map((i) => i.date)

    return (
      <div className="space-y-6">
        <div className="flex justify-between items-center">
          <h1 className="text-2xl font-semibold">시황 상세</h1>
          <DatePickerInline currentDate={date} availableDates={availableDates} />
        </div>
        <ScoreHeroCard snapshot={snapshot} />
        <IndicatorGrid
          scores={snapshot.indicator_scores}
          descriptions={snapshot.indicator_descriptions}
          expandAll
        />
      </div>
    )
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound()
    throw e
  }
}
