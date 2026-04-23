"use client"
import { Card } from "@/components/ui/card"
import { normalizeSignalKey, signalStyle } from "@/lib/market-labels"

export type SignalBreakdownRow = {
  signal: string
  count: number
  hit_rate_1d: number | null
  hit_rate_3d: number | null
  hit_rate_5d: number | null
}

const SIGNAL_ORDER: Record<string, number> = {
  strong_bullish: 0,
  moderately_bullish: 1,
  neutral: 2,
  moderately_bearish: 3,
  strong_bearish: 4,
}

function formatRate(v: number | null): string {
  if (v === null) return "—"
  return `${(v * 100).toFixed(1)}%`
}

export function SignalBreakdownTable({ rows }: { rows: SignalBreakdownRow[] }) {
  if (rows.length === 0) {
    return (
      <Card className="p-6">
        <h3 className="text-sm font-semibold mb-1">시그널 분포</h3>
        <p className="text-sm text-neutral-500">시그널 분포 없음</p>
      </Card>
    )
  }

  // 정규화된 key 기준으로 정렬
  const sorted = [...rows].sort(
    (a, b) => (SIGNAL_ORDER[normalizeSignalKey(a.signal)] ?? 99) - (SIGNAL_ORDER[normalizeSignalKey(b.signal)] ?? 99),
  )

  return (
    <Card className="p-4">
      <h3 className="text-sm font-semibold mb-3">시그널 분포</h3>
      <table className="w-full text-sm border-collapse">
        <thead>
          <tr className="text-left text-xs text-neutral-400">
            <th scope="col" className="px-3 py-2">시그널</th>
            <th scope="col" className="px-3 py-2 text-right">건수</th>
            <th scope="col" className="px-3 py-2 text-right">적중 1d</th>
            <th scope="col" className="px-3 py-2 text-right">적중 3d</th>
            <th scope="col" className="px-3 py-2 text-right">적중 5d</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((r) => {
            const style = signalStyle(r.signal)
            return (
              <tr key={r.signal} className="border-t border-neutral-800">
                <td className="px-3 py-2">
                  <span className={`inline-block px-2 py-0.5 rounded-full text-xs ${style.badge}`}>
                    {style.label}
                  </span>
                </td>
                <td className="px-3 py-2 text-right font-mono tabular-nums">{r.count}</td>
                <td className="px-3 py-2 text-right font-mono tabular-nums">{formatRate(r.hit_rate_1d)}</td>
                <td className="px-3 py-2 text-right font-mono tabular-nums">{formatRate(r.hit_rate_3d)}</td>
                <td className="px-3 py-2 text-right font-mono tabular-nums">{formatRate(r.hit_rate_5d)}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </Card>
  )
}
