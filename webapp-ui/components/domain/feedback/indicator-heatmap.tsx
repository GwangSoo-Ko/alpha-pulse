"use client"
import { Card } from "@/components/ui/card"
import { INDICATOR_LABELS, INDICATOR_ORDER } from "@/lib/market-labels"

export type IndicatorHeatmapCell = {
  date: string
  indicator: string
  score: number
}

function formatDateShort(yyyymmdd: string): string {
  if (yyyymmdd.length !== 8) return yyyymmdd
  return `${yyyymmdd.slice(4, 6)}-${yyyymmdd.slice(6)}`
}

function cellColor(score: number | null): string {
  if (score === null) return "bg-neutral-900"
  const abs = Math.abs(score)
  if (score === 0) return "bg-neutral-800"
  if (score > 0) {
    if (abs >= 66) return "bg-emerald-700"
    if (abs >= 33) return "bg-emerald-500"
    return "bg-emerald-300/60"
  }
  if (abs >= 66) return "bg-rose-700"
  if (abs >= 33) return "bg-rose-500"
  return "bg-rose-300/60"
}

export function IndicatorHeatmap({ cells }: { cells: IndicatorHeatmapCell[] }) {
  if (cells.length === 0) {
    return (
      <Card className="p-6">
        <h3 className="text-sm font-semibold mb-1">지표 히트맵</h3>
        <p className="text-sm text-neutral-500">지표 데이터 없음</p>
      </Card>
    )
  }

  // cells → scoreMap[indicator][date] = score, dates 정렬
  const scoreMap: Record<string, Record<string, number>> = {}
  const dateSet = new Set<string>()
  for (const c of cells) {
    if (!scoreMap[c.indicator]) scoreMap[c.indicator] = {}
    scoreMap[c.indicator][c.date] = c.score
    dateSet.add(c.date)
  }
  const dates = Array.from(dateSet).sort()

  // 7일 간격 label
  const labelStep = Math.max(1, Math.ceil(dates.length / 10))

  return (
    <Card className="p-4">
      <h3 className="text-sm font-semibold mb-3">지표 히트맵</h3>
      <div className="overflow-x-auto">
        <table className="border-collapse text-xs">
          <thead>
            <tr>
              <th scope="col" className="pr-3 text-left text-neutral-400 font-normal sticky left-0 bg-[var(--card)] z-10"></th>
              {dates.map((d, i) => (
                <th
                  key={d}
                  scope="col"
                  className="text-[10px] text-neutral-500 font-normal px-0.5"
                  style={{ minWidth: 16 }}
                >
                  {i % labelStep === 0 ? formatDateShort(d) : ""}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {INDICATOR_ORDER.map((key) => (
              <tr key={key}>
                <th scope="row" className="pr-3 text-left text-neutral-300 font-normal whitespace-nowrap sticky left-0 bg-[var(--card)] z-10">
                  {INDICATOR_LABELS[key] ?? key}
                </th>
                {dates.map((d) => {
                  const score = scoreMap[key]?.[d] ?? null
                  return (
                    <td
                      key={d}
                      className={`${cellColor(score)} w-4 h-6 p-0`}
                      title={`${d}: ${INDICATOR_LABELS[key] ?? key} = ${score !== null ? score.toFixed(1) : "—"}`}
                    />
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  )
}
