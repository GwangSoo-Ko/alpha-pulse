"use client"
import { useState } from "react"
import { signalStyle, scoreToSignal } from "@/lib/market-labels"

export function IndicatorCard({
  koreanName,
  score,
  description,
  defaultExpanded = false,
}: {
  koreanName: string
  score: number | null
  description: string | null
  defaultExpanded?: boolean
}) {
  const [expanded, setExpanded] = useState(defaultExpanded)

  if (score === null) {
    return (
      <div className="rounded border border-neutral-800 bg-neutral-900 p-3">
        <p className="text-sm text-neutral-300">{koreanName}</p>
        <p className="text-xs text-neutral-500 mt-1">데이터 없음</p>
      </div>
    )
  }

  const style = signalStyle(scoreToSignal(score))
  const normalized = Math.max(0, Math.min(1, (score + 100) / 200))
  const sign = score >= 0 ? "+" : ""

  return (
    <button
      type="button"
      onClick={() => setExpanded((v) => !v)}
      className="text-left w-full rounded border border-neutral-800 bg-neutral-900 p-3 hover:border-neutral-600 transition"
    >
      <div className="flex justify-between items-center mb-2">
        <p className="text-sm text-neutral-300">{koreanName}</p>
        <p className="text-sm font-mono tabular-nums">
          {sign}{score.toFixed(1)}
        </p>
      </div>
      <div className="h-1.5 rounded bg-neutral-800 overflow-hidden">
        <div
          className={`h-full ${style.bar}`}
          style={{ width: `${normalized * 100}%` }}
        />
      </div>
      {expanded && (
        <div className="mt-3 text-xs text-neutral-400 whitespace-pre-line">
          {description ?? "설명 저장 이전 날짜 — '지금 실행' 으로 재계산하세요"}
        </div>
      )}
    </button>
  )
}
