"use client"
import { Card } from "@/components/ui/card"
import { signalStyle } from "@/lib/market-labels"

export type FeedbackDetail = {
  date: string
  score: number
  signal: string
  indicator_scores: Record<string, number | null>
  kospi_close: number | null
  kospi_change_pct: number | null
  kosdaq_close: number | null
  kosdaq_change_pct: number | null
  return_1d: number | null
  return_3d: number | null
  return_5d: number | null
  hit_1d: boolean | null
  hit_3d: boolean | null
  hit_5d: boolean | null
  post_analysis: string | null
  news_summary: string | null
  blind_spots: string | null
  evaluated_at: number | null
  created_at: number
}

function formatDate(yyyymmdd: string): string {
  return `${yyyymmdd.slice(0, 4)}-${yyyymmdd.slice(4, 6)}-${yyyymmdd.slice(6)}`
}

function formatPct(v: number | null): string {
  if (v === null) return "-"
  const sign = v >= 0 ? "+" : ""
  return `${sign}${v.toFixed(2)}%`
}

function HitBadge({ hit }: { hit: boolean | null }) {
  if (hit === null) return <span className="text-neutral-500">-</span>
  return hit
    ? <span className="text-green-400">✓</span>
    : <span className="text-red-400">✗</span>
}

export function FeedbackDetailCard({ detail }: { detail: FeedbackDetail }) {
  const style = signalStyle(detail.signal)
  const sign = detail.score >= 0 ? "+" : ""

  return (
    <Card className="p-6 space-y-4">
      <div>
        <p className="text-xs text-neutral-400 mb-1">
          피드백 · {formatDate(detail.date)}
        </p>
        <div className="flex items-baseline gap-4">
          <span className={`text-4xl font-bold font-mono ${style.badge.split(" ").find((c) => c.startsWith("text-"))}`}>
            {sign}{detail.score.toFixed(1)}
          </span>
          <span className={`inline-block px-3 py-1 rounded-full text-sm ${style.badge}`}>
            {style.label}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 border-t border-neutral-800 pt-3">
        <div>
          <p className="text-xs text-neutral-400 mb-1">KOSPI</p>
          <p className="text-sm font-mono tabular-nums">
            {detail.kospi_close?.toFixed(2) ?? "-"} ({formatPct(detail.kospi_change_pct)})
          </p>
        </div>
        <div>
          <p className="text-xs text-neutral-400 mb-1">KOSDAQ</p>
          <p className="text-sm font-mono tabular-nums">
            {detail.kosdaq_close?.toFixed(2) ?? "-"} ({formatPct(detail.kosdaq_change_pct)})
          </p>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-3 border-t border-neutral-800 pt-3">
        <div>
          <p className="text-xs text-neutral-400 mb-1">1일 수익률</p>
          <p className="text-sm font-mono tabular-nums">
            {formatPct(detail.return_1d)} <HitBadge hit={detail.hit_1d} />
          </p>
        </div>
        <div>
          <p className="text-xs text-neutral-400 mb-1">3일 수익률</p>
          <p className="text-sm font-mono tabular-nums">
            {formatPct(detail.return_3d)} <HitBadge hit={detail.hit_3d} />
          </p>
        </div>
        <div>
          <p className="text-xs text-neutral-400 mb-1">5일 수익률</p>
          <p className="text-sm font-mono tabular-nums">
            {formatPct(detail.return_5d)} <HitBadge hit={detail.hit_5d} />
          </p>
        </div>
      </div>
    </Card>
  )
}
