"use client"
import type { Snapshot } from "@/lib/types"

/** 스냅샷에서 월별 수익률을 계산해 히트맵 렌더. */
function computeMonthly(snaps: Snapshot[]): { month: string; ret: number }[] {
  if (snaps.length === 0) return []
  const byMonth = new Map<string, { first: number; last: number }>()
  for (const s of snaps) {
    const m = s.date.slice(0, 6)
    const v = byMonth.get(m)
    if (!v) byMonth.set(m, { first: s.total_value, last: s.total_value })
    else v.last = s.total_value
  }
  return [...byMonth.entries()].map(([m, v]) => ({
    month: m,
    ret: (v.last / v.first - 1) * 100,
  }))
}

function color(ret: number): string {
  if (ret === 0) return "bg-neutral-800"
  const mag = Math.min(10, Math.abs(ret)) / 10
  const alpha = 0.15 + mag * 0.7
  return ret > 0
    ? `rgba(34, 197, 94, ${alpha})`
    : `rgba(239, 68, 68, ${alpha})`
}

export function MonthlyHeatmap({ snapshots }: { snapshots: Snapshot[] }) {
  const rows = computeMonthly(snapshots)
  return (
    <div className="grid grid-cols-12 gap-1">
      {rows.map((r) => (
        <div
          key={r.month}
          className="flex h-14 flex-col items-center justify-center rounded text-xs"
          style={{ backgroundColor: color(r.ret) }}
          title={`${r.month}: ${r.ret.toFixed(2)}%`}
        >
          <span className="text-[10px] text-neutral-400">{r.month.slice(4)}</span>
          <span className="font-mono">
            {r.ret >= 0 ? "+" : ""}
            {r.ret.toFixed(1)}%
          </span>
        </div>
      ))}
    </div>
  )
}
