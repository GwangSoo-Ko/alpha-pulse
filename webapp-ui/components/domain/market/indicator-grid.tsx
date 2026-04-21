"use client"
import { IndicatorCard } from "./indicator-card"
import { INDICATOR_LABELS, INDICATOR_ORDER } from "@/lib/market-labels"

export function IndicatorGrid({
  scores,
  descriptions,
  expandAll = false,
}: {
  scores: Record<string, number | null>
  descriptions: Record<string, string | null>
  expandAll?: boolean
}) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
      {INDICATOR_ORDER.map((key) => (
        <IndicatorCard
          key={key}
          koreanName={INDICATOR_LABELS[key] ?? key}
          score={scores[key] ?? null}
          description={descriptions[key] ?? null}
          defaultExpanded={expandAll}
        />
      ))}
    </div>
  )
}
