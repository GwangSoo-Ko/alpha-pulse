"use client"
import { Card } from "@/components/ui/card"

export type HitRates = {
  total_evaluated: number
  hit_rate_1d: number | null
  hit_rate_3d: number | null
  hit_rate_5d: number | null
  count_1d: number
  count_3d: number
  count_5d: number
}

function pct(rate: number | null): string {
  if (rate === null) return "-"
  return `${(rate * 100).toFixed(0)}%`
}

function colorClass(rate: number | null): string {
  if (rate === null) return "text-neutral-500"
  if (rate >= 0.6) return "text-green-400"
  if (rate >= 0.5) return "text-yellow-400"
  return "text-red-400"
}

function Cell({ label, rate, count }: { label: string; rate: number | null; count: number }) {
  return (
    <Card className="p-4 space-y-1">
      <p className="text-xs text-neutral-400">{label}</p>
      <p className={`text-3xl font-bold font-mono ${colorClass(rate)}`}>
        {pct(rate)}
      </p>
      <p className="text-xs text-neutral-500">{count}건 평가</p>
    </Card>
  )
}

export function HitRateCards({ rates }: { rates: HitRates }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
      <Cell label="1일 적중률" rate={rates.hit_rate_1d} count={rates.count_1d} />
      <Cell label="3일 적중률" rate={rates.hit_rate_3d} count={rates.count_3d} />
      <Cell label="5일 적중률" rate={rates.hit_rate_5d} count={rates.count_5d} />
    </div>
  )
}
