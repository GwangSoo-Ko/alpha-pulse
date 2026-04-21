"use client"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { signalStyle } from "@/lib/market-labels"

export type PulseSnapshot = {
  date: string
  score: number
  signal: string
  indicator_scores: Record<string, number | null>
  indicator_descriptions: Record<string, string | null>
  period: string
  created_at: number
}

function formatDate(yyyymmdd: string): string {
  return `${yyyymmdd.slice(0, 4)}-${yyyymmdd.slice(4, 6)}-${yyyymmdd.slice(6)}`
}

function formatTime(epochSeconds: number): string {
  const d = new Date(epochSeconds * 1000)
  const hh = String(d.getHours()).padStart(2, "0")
  const mm = String(d.getMinutes()).padStart(2, "0")
  return `${hh}:${mm}`
}

export function ScoreHeroCard({
  snapshot,
  onRun,
  running = false,
}: {
  snapshot: PulseSnapshot
  onRun?: () => void
  running?: boolean
}) {
  const style = signalStyle(snapshot.signal)
  const sign = snapshot.score >= 0 ? "+" : ""

  return (
    <Card className="p-6 flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
      <div>
        <p className="text-xs text-neutral-400 mb-1">
          K-Market Pulse · {formatDate(snapshot.date)} · {formatTime(snapshot.created_at)} 저장
        </p>
        <div className="flex items-baseline gap-4">
          <span className={`text-5xl font-bold font-mono ${style.badge.split(" ").find((c) => c.startsWith("text-"))}`}>
            {sign}{snapshot.score.toFixed(1)}
          </span>
          <span className={`inline-block px-3 py-1 rounded-full text-sm ${style.badge}`}>
            {style.label}
          </span>
        </div>
      </div>
      {onRun && (
        <Button onClick={onRun} disabled={running}>
          {running ? "실행 중…" : "지금 실행"}
        </Button>
      )}
    </Card>
  )
}
