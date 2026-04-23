"use client"
import { Card } from "@/components/ui/card"
import {
  CartesianGrid, ReferenceLine, ResponsiveContainer, Scatter, ScatterChart,
  Tooltip, XAxis, YAxis,
} from "recharts"
import { normalizeSignalKey, SIGNAL_STYLE } from "@/lib/market-labels"

export type ScoreReturnPoint = {
  date: string
  score: number
  return_1d: number
  signal: string
}

// Tailwind bg-* class → 실제 hex (dot fill 에 쓰기 위해)
const SIGNAL_HEX: Record<string, string> = {
  strong_bullish: "#22c55e",
  moderately_bullish: "#10b981",
  neutral: "#eab308",
  moderately_bearish: "#f97316",
  strong_bearish: "#ef4444",
}

export function ScoreReturnScatter({ points }: { points: ScoreReturnPoint[] }) {
  if (points.length === 0) {
    return (
      <Card className="p-6">
        <h3 className="text-sm font-semibold mb-1">Score vs Return (1d)</h3>
        <p className="text-sm text-neutral-500">평가된 데이터 없음</p>
      </Card>
    )
  }

  // signal 별 그룹핑 (정규화된 key 기준)
  const groups: Record<string, ScoreReturnPoint[]> = {}
  for (const p of points) {
    const key = normalizeSignalKey(p.signal)
    if (!groups[key]) groups[key] = []
    groups[key].push(p)
  }

  const orderedKeys = ["strong_bullish", "moderately_bullish", "neutral", "moderately_bearish", "strong_bearish"]

  return (
    <Card className="p-4">
      <h3 className="text-sm font-semibold mb-3">Score vs Return (1d)</h3>
      <ResponsiveContainer width="100%" height={320}>
        <ScatterChart margin={{ top: 10, right: 20, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#262626" />
          <XAxis
            dataKey="score"
            type="number"
            domain={[-100, 100]}
            stroke="#9ca3af"
            tick={{ fontSize: 11 }}
            name="Score"
          />
          <YAxis
            dataKey="return_1d"
            type="number"
            stroke="#9ca3af"
            tick={{ fontSize: 11 }}
            tickFormatter={(v) => `${v}%`}
            name="Return 1d"
          />
          <ReferenceLine x={0} stroke="#404040" />
          <ReferenceLine y={0} stroke="#404040" />
          <Tooltip
            cursor={{ strokeDasharray: "3 3" }}
            contentStyle={{ background: "#0f0f12", border: "1px solid #2a2a2f" }}
            formatter={(v: number, name: string) => {
              if (name === "Return 1d") return [`${v.toFixed(2)}%`, name]
              if (name === "Score") return [v.toFixed(1), name]
              return [v, name]
            }}
            labelFormatter={() => ""}
          />
          {orderedKeys.map((key) =>
            groups[key] ? (
              <Scatter
                key={key}
                name={SIGNAL_STYLE[key as keyof typeof SIGNAL_STYLE].label}
                data={groups[key].map((p) => ({ date: p.date, score: p.score, return_1d: p.return_1d }))}
                fill={SIGNAL_HEX[key]}
              />
            ) : null,
          )}
        </ScatterChart>
      </ResponsiveContainer>
    </Card>
  )
}
