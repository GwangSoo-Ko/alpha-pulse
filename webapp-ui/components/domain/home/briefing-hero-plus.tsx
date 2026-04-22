"use client"
import Link from "next/link"
import { Card } from "@/components/ui/card"
import { signalStyle } from "@/lib/market-labels"

export type HighlightBadge = {
  name: string
  direction: "up" | "down" | "neutral"
  sentiment: "positive" | "negative" | "neutral"
}

export type BriefingHero = {
  date: string
  created_at: number
  score: number
  signal: string
  summary_line: string
  highlight_badges: HighlightBadge[]
  is_today: boolean
}

function formatDate(yyyymmdd: string): string {
  if (yyyymmdd.length !== 8) return yyyymmdd
  return `${yyyymmdd.slice(0, 4)}-${yyyymmdd.slice(4, 6)}-${yyyymmdd.slice(6)}`
}

function formatTime(epoch: number): string {
  if (!epoch) return ""
  const d = new Date(epoch * 1000)
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`
}

function directionArrow(d: HighlightBadge["direction"]): string {
  if (d === "up") return "↑"
  if (d === "down") return "↓"
  return "·"
}

function badgeClass(b: HighlightBadge): string {
  if (b.sentiment === "positive") return "bg-emerald-900/30 text-emerald-400"
  if (b.sentiment === "negative") return "bg-rose-900/30 text-rose-400"
  return "bg-amber-900/30 text-amber-400"
}

export function BriefingHeroPlus({ hero }: { hero: BriefingHero | null }) {
  if (!hero) {
    return (
      <Card className="p-6">
        <p className="text-sm text-neutral-400">
          브리핑 데이터가 없습니다. 먼저 브리핑을 생성하세요.
        </p>
      </Card>
    )
  }
  const style = signalStyle(hero.signal)
  const sign = hero.score >= 0 ? "+" : ""
  const timeText = formatTime(hero.created_at)
  return (
    <Card className="p-6 space-y-3">
      <div className="flex items-start justify-between gap-4">
        <div className="space-y-2">
          <p className="text-xs text-neutral-400">
            브리핑 · {formatDate(hero.date)}{timeText && ` · ${timeText} 저장`}
          </p>
          <div className="flex items-baseline gap-4 flex-wrap">
            <span className={`text-4xl font-bold font-mono ${style.badge.split(" ").find((c) => c.startsWith("text-"))}`}>
              {sign}{hero.score.toFixed(1)}
            </span>
            <span className={`inline-block px-3 py-1 rounded-full text-sm ${style.badge}`}>
              {style.label}
            </span>
          </div>
          {hero.summary_line && (
            <p className="text-sm text-neutral-300">{hero.summary_line}</p>
          )}
          {hero.highlight_badges.length > 0 && (
            <div className="flex gap-2 flex-wrap pt-1">
              {hero.highlight_badges.map((b) => (
                <span key={b.name} className={`px-2 py-1 text-xs rounded ${badgeClass(b)}`}>
                  {b.name} {directionArrow(b.direction)}
                </span>
              ))}
            </div>
          )}
        </div>
        <Link
          href={`/briefings/${hero.date}`}
          className="text-sm text-neutral-400 hover:text-neutral-200 shrink-0"
        >
          → 상세 보기
        </Link>
      </div>
    </Card>
  )
}
