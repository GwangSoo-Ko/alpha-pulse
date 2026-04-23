"use client"
import { Card } from "@/components/ui/card"
import { signalStyle } from "@/lib/market-labels"

export type BriefingCompareItem = {
  date: string
  score: number
  signal: string
} | null

function formatDate(yyyymmdd: string): string {
  if (yyyymmdd.length !== 8) return yyyymmdd
  return `${yyyymmdd.slice(0, 4)}-${yyyymmdd.slice(4, 6)}-${yyyymmdd.slice(6)}`
}

function sign(v: number): string {
  return v >= 0 ? "+" : ""
}

function deltaColor(d: number): string {
  if (d > 0) return "text-emerald-400"
  if (d < 0) return "text-rose-400"
  return "text-neutral-400"
}

function SideCard({
  label, item, aria,
}: {
  label: string
  item: BriefingCompareItem
  aria: string
}) {
  if (!item) {
    return (
      <Card className="p-5 text-center" aria-label={aria}>
        <p className="text-xs text-neutral-500 mb-2">{label}</p>
        <p className="text-sm text-neutral-400">해당 날짜 브리핑 없음</p>
      </Card>
    )
  }
  const style = signalStyle(item.signal)
  const textColor = style.badge.split(" ").find((c) => c.startsWith("text-"))
  return (
    <Card className="p-5 text-center" aria-label={aria}>
      <p className="text-xs text-neutral-500 mb-2">
        {label} · <span className="font-mono">{formatDate(item.date)}</span>
      </p>
      <div className={`text-4xl font-bold font-mono mb-2 ${textColor}`}>
        {sign(item.score)}{item.score.toFixed(1)}
      </div>
      <span className={`inline-block px-3 py-1 rounded-full text-xs ${style.badge}`}>
        {style.label}
      </span>
    </Card>
  )
}

export function BriefingCompareHero({
  a, b,
}: {
  a: BriefingCompareItem
  b: BriefingCompareItem
}) {
  const delta = a && b ? b.score - a.score : null
  return (
    <div className="grid gap-3 grid-cols-1 md:grid-cols-[1fr_auto_1fr] items-center">
      <SideCard label="A" item={a} aria="Briefing A" />
      <div className="text-center px-3">
        <p className="text-xs text-neutral-500 mb-1">Δ (B − A)</p>
        {delta === null ? (
          <p className="text-2xl font-mono text-neutral-500">—</p>
        ) : (
          <p className={`text-2xl font-bold font-mono ${deltaColor(delta)}`}>
            {sign(delta)}{delta.toFixed(1)}
          </p>
        )}
      </div>
      <SideCard label="B" item={b} aria="Briefing B" />
    </div>
  )
}
