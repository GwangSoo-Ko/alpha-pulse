"use client"
import { Card } from "@/components/ui/card"
import { signalStyle } from "@/lib/market-labels"

export type BriefingDetail = {
  date: string
  created_at: number
  pulse_result: Record<string, unknown>
  content_summaries: string[]
  commentary: string | null
  synthesis: string | null
  quant_msg: string
  synth_msg: string
  feedback_context: Record<string, unknown> | null
  daily_result_msg: string
  news: { articles: Array<Record<string, unknown>> }
  post_analysis: Record<string, unknown> | null
  generated_at: string
}

function formatDate(yyyymmdd: string): string {
  return `${yyyymmdd.slice(0, 4)}-${yyyymmdd.slice(4, 6)}-${yyyymmdd.slice(6)}`
}

function formatTime(epoch: number): string {
  const d = new Date(epoch * 1000)
  const hh = String(d.getHours()).padStart(2, "0")
  const mm = String(d.getMinutes()).padStart(2, "0")
  return `${hh}:${mm}`
}

export function BriefingHeroCard({ detail }: { detail: BriefingDetail }) {
  const pulse = detail.pulse_result as { score?: number; signal?: string }
  const score = typeof pulse.score === "number" ? pulse.score : 0
  const signal = typeof pulse.signal === "string" ? pulse.signal : "neutral"
  const style = signalStyle(signal)
  const sign = score >= 0 ? "+" : ""

  return (
    <Card className="p-6 space-y-3">
      <div>
        <p className="text-xs text-neutral-400 mb-1">
          브리핑 · {formatDate(detail.date)} · {formatTime(detail.created_at)} 저장
        </p>
        <div className="flex items-baseline gap-4">
          <span className={`text-4xl font-bold font-mono ${style.badge.split(" ").find((c) => c.startsWith("text-"))}`}>
            {sign}{score.toFixed(1)}
          </span>
          <span className={`inline-block px-3 py-1 rounded-full text-sm ${style.badge}`}>
            {style.label}
          </span>
        </div>
      </div>
      {detail.daily_result_msg && (
        <div className="text-sm text-neutral-300 whitespace-pre-line border-t border-neutral-800 pt-3">
          {detail.daily_result_msg}
        </div>
      )}
    </Card>
  )
}
