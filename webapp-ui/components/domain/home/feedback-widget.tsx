"use client"
import Link from "next/link"
import { Card } from "@/components/ui/card"

export type FeedbackIndicator = { name: string; hit_rate: number }
export type FeedbackData = {
  hit_rate_7d: number | null
  top_indicators: FeedbackIndicator[]
}

export function FeedbackWidget({ data }: { data: FeedbackData | null }) {
  if (!data || data.hit_rate_7d === null) {
    return (
      <Link href="/feedback" className="block">
        <Card className="p-4 min-h-[160px] hover:border-neutral-600 transition">
          <div className="text-xs text-neutral-400 uppercase tracking-wide mb-2">Feedback</div>
          <p className="text-sm text-neutral-500">피드백 데이터 없음</p>
        </Card>
      </Link>
    )
  }
  const pct = (data.hit_rate_7d * 100).toFixed(1)
  return (
    <Link href="/feedback" className="block">
      <Card className="p-4 min-h-[160px] hover:border-neutral-600 transition">
        <div className="text-xs text-neutral-400 uppercase tracking-wide mb-2">Feedback · 7일</div>
        <div className="text-3xl font-bold font-mono text-emerald-400 mb-2">{pct}%</div>
        <p className="text-xs text-neutral-500 mb-3">시그널 적중률 (1일)</p>
        {data.top_indicators.length > 0 ? (
          <ul className="space-y-1">
            {data.top_indicators.map((i) => (
              <li key={i.name} className="flex items-center justify-between text-xs">
                <span className="text-neutral-400">{i.name}</span>
                <span className="font-mono text-neutral-300">{(i.hit_rate * 100).toFixed(0)}%</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-xs text-neutral-500">지표별 집계 없음</p>
        )}
      </Card>
    </Link>
  )
}
