"use client"
import Link from "next/link"
import { Card } from "@/components/ui/card"
import { signalStyle } from "@/lib/market-labels"

export type PulsePoint = { date: string; score: number; signal: string }
export type PulseData = {
  latest: PulsePoint | null
  history7: PulsePoint[]
}

export function PulseWidget({ data }: { data: PulseData | null }) {
  if (!data || data.latest === null) {
    return (
      <Link href="/market/pulse" className="block">
        <Card className="p-4 min-h-[160px] hover:border-neutral-600 transition">
          <div className="text-xs text-neutral-400 uppercase tracking-wide mb-2">Market Pulse</div>
          <p className="text-sm text-neutral-500">데이터 없음</p>
        </Card>
      </Link>
    )
  }
  const style = signalStyle(data.latest.signal)
  const max = Math.max(100, ...data.history7.map((p) => Math.abs(p.score)))
  return (
    <Link href="/market/pulse" className="block">
      <Card className="p-4 min-h-[160px] hover:border-neutral-600 transition">
        <div className="text-xs text-neutral-400 uppercase tracking-wide mb-2">Market Pulse</div>
        <div className="flex items-baseline gap-3 mb-3">
          <span className={`text-2xl font-bold font-mono ${style.badge.split(" ").find((c) => c.startsWith("text-"))}`}>
            {data.latest.score >= 0 ? "+" : ""}{data.latest.score.toFixed(1)}
          </span>
          <span className={`text-xs px-2 py-0.5 rounded-full ${style.badge}`}>{style.label}</span>
        </div>
        <div className="flex items-end gap-1 h-12">
          {data.history7.map((p) => {
            const height = Math.max(4, (Math.abs(p.score) / max) * 100)
            return (
              <div
                key={p.date}
                className={`flex-1 rounded-sm ${signalStyle(p.signal).bar}`}
                style={{ height: `${height}%` }}
                title={`${p.date}: ${p.score.toFixed(1)}`}
              />
            )
          })}
        </div>
        <p className="text-[10px] text-neutral-500 mt-2">최근 7일</p>
      </Card>
    </Link>
  )
}
