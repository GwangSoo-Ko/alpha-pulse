"use client"
import { useState } from "react"
import { Card } from "@/components/ui/card"
import { INDICATOR_LABELS } from "@/lib/market-labels"

type IndicatorRow = {
  key: string
  label: string
  a: number | null
  b: number | null
  delta: number | null
}

type SortKey = "label" | "a" | "b" | "delta"
type SortDir = "asc" | "desc"

function toNumberOrNull(v: unknown): number | null {
  if (typeof v === "number") return v
  return null
}

function buildRows(
  scoresA: Record<string, unknown>,
  scoresB: Record<string, unknown>,
): IndicatorRow[] {
  const keys = Array.from(new Set([...Object.keys(scoresA), ...Object.keys(scoresB)]))
  return keys.map((key) => {
    const a = toNumberOrNull(scoresA[key])
    const b = toNumberOrNull(scoresB[key])
    const delta = a !== null && b !== null ? b - a : null
    return {
      key,
      label: INDICATOR_LABELS[key] ?? key,
      a, b, delta,
    }
  })
}

function compare(
  x: IndicatorRow, y: IndicatorRow, by: SortKey, dir: SortDir,
): number {
  let xv: number | string | null
  let yv: number | string | null
  if (by === "label") {
    xv = x.label
    yv = y.label
  } else if (by === "delta") {
    // |delta| 기준, null 은 맨 아래
    xv = x.delta === null ? null : Math.abs(x.delta)
    yv = y.delta === null ? null : Math.abs(y.delta)
  } else {
    xv = x[by]
    yv = y[by]
  }
  // null 은 항상 맨 아래 (정렬 방향 무관)
  if (xv === null && yv === null) return 0
  if (xv === null) return 1
  if (yv === null) return -1
  if (xv < yv) return dir === "asc" ? -1 : 1
  if (xv > yv) return dir === "asc" ? 1 : -1
  return 0
}

function ScoreCell({ v }: { v: number | null }) {
  if (v === null) return <span className="text-neutral-600">—</span>
  const cls = v > 0 ? "text-emerald-400" : v < 0 ? "text-rose-400" : "text-neutral-400"
  return (
    <span className={`font-mono tabular-nums ${cls}`}>
      {v > 0 ? "+" : ""}{v.toFixed(1)}
    </span>
  )
}

function DeltaCell({ v }: { v: number | null }) {
  if (v === null) return <span className="text-neutral-600">—</span>
  if (v === 0) return <span className="text-neutral-400 font-mono">0.0 ·</span>
  const cls = v > 0 ? "text-emerald-400" : "text-rose-400"
  const arrow = v > 0 ? "↑" : "↓"
  return (
    <span className={`font-mono tabular-nums font-semibold ${cls}`}>
      {v > 0 ? "+" : ""}{v.toFixed(1)} {arrow}
    </span>
  )
}

export function IndicatorDiffTable({
  scoresA, scoresB, dateALabel, dateBLabel,
}: {
  scoresA: Record<string, unknown>
  scoresB: Record<string, unknown>
  dateALabel: string
  dateBLabel: string
}) {
  const [sortBy, setSortBy] = useState<SortKey>("delta")
  const [dir, setDir] = useState<SortDir>("desc")

  const rows = buildRows(scoresA, scoresB)
  const sorted = [...rows].sort((x, y) => compare(x, y, sortBy, dir))

  function toggleSort(key: SortKey) {
    if (sortBy === key) {
      setDir(dir === "asc" ? "desc" : "asc")
    } else {
      setSortBy(key)
      setDir(key === "delta" ? "desc" : "asc")
    }
  }

  if (rows.length === 0) {
    return (
      <Card className="p-6">
        <p className="text-sm text-neutral-500">지표 데이터 없음</p>
      </Card>
    )
  }

  const indicator = (key: SortKey) =>
    sortBy === key ? (dir === "asc" ? " ▲" : " ▼") : ""

  const ariaSort = (key: SortKey): "ascending" | "descending" | "none" => {
    if (sortBy !== key) return "none"
    return dir === "asc" ? "ascending" : "descending"
  }

  return (
    <Card className="p-4 overflow-x-auto">
      <table className="w-full text-sm border-collapse">
        <thead>
          <tr className="text-left text-xs text-neutral-400">
            <th
              scope="col"
              aria-sort={ariaSort("label")}
              className="px-3 py-2 cursor-pointer select-none"
              onClick={() => toggleSort("label")}
            >
              지표{indicator("label")}
            </th>
            <th
              scope="col"
              aria-sort={ariaSort("a")}
              className="px-3 py-2 text-right cursor-pointer select-none"
              onClick={() => toggleSort("a")}
            >
              {dateALabel}{indicator("a")}
            </th>
            <th
              scope="col"
              aria-sort={ariaSort("b")}
              className="px-3 py-2 text-right cursor-pointer select-none"
              onClick={() => toggleSort("b")}
            >
              {dateBLabel}{indicator("b")}
            </th>
            <th
              scope="col"
              aria-sort={ariaSort("delta")}
              className="px-3 py-2 text-right cursor-pointer select-none"
              onClick={() => toggleSort("delta")}
            >
              Δ{indicator("delta")}
            </th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((r) => (
            <tr key={r.key} className="border-t border-neutral-800 hover:bg-neutral-900">
              <td className="px-3 py-2">{r.label}</td>
              <td className="px-3 py-2 text-right"><ScoreCell v={r.a} /></td>
              <td className="px-3 py-2 text-right"><ScoreCell v={r.b} /></td>
              <td className="px-3 py-2 text-right"><DeltaCell v={r.delta} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  )
}
