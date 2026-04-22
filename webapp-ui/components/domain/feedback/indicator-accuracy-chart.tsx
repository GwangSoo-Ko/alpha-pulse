"use client"
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, Cell as BarCell,
} from "recharts"
import { Card } from "@/components/ui/card"
import { INDICATOR_LABELS } from "@/lib/market-labels"

export type IndicatorAccuracy = {
  key: string
  accuracy: number
  count: number
}

function color(accuracy: number, count: number): string {
  if (count < 5) return "#737373"          // neutral-500, 데이터 부족
  if (accuracy >= 0.70) return "#22c55e"   // green-500
  if (accuracy >= 0.50) return "#eab308"   // yellow-500
  return "#ef4444"                          // red-500
}

function fmtTick(v: number): string {
  return `${(v * 100).toFixed(0)}%`
}

export function IndicatorAccuracyChart({
  items,
}: {
  items: IndicatorAccuracy[]
}) {
  if (items.length === 0) {
    return (
      <Card className="p-6 text-sm text-neutral-500">
        지표별 적중률 데이터 없음 (극단값 시그널 누적 필요)
      </Card>
    )
  }

  const data = items.map((i) => ({
    label: INDICATOR_LABELS[i.key] ?? i.key,
    accuracy: i.accuracy,
    count: i.count,
    color: color(i.accuracy, i.count),
  }))

  return (
    <Card className="p-4">
      <h2 className="text-sm text-neutral-300 mb-4">지표별 적중률 (극단값 기준)</h2>
      <div style={{ height: Math.max(220, data.length * 28) }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} layout="vertical" margin={{ left: 100 }}>
            <XAxis
              type="number" domain={[0, 1]}
              tickFormatter={fmtTick}
              stroke="#888" fontSize={11}
            />
            <YAxis
              type="category" dataKey="label" width={100}
              stroke="#888" fontSize={11}
            />
            <Tooltip
              contentStyle={{
                background: "#1f1f1f", border: "1px solid #333", fontSize: 12,
              }}
              formatter={(v: number, _name, ctx) => [
                `${(v * 100).toFixed(0)}% · ${ctx.payload.count}건`,
                "정확도",
              ]}
            />
            <Bar dataKey="accuracy">
              {data.map((d, i) => (
                <BarCell key={i} fill={d.color} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </Card>
  )
}
