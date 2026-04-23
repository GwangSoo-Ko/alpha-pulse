"use client"
import { Card } from "@/components/ui/card"
import {
  CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts"

export type HitRateTrendPoint = {
  date: string
  rolling_hit_rate_1d: number | null
}

function formatDateShort(yyyymmdd: string): string {
  if (yyyymmdd.length !== 8) return yyyymmdd
  return `${yyyymmdd.slice(4, 6)}-${yyyymmdd.slice(6)}`
}

export function HitRateTrendChart({ points }: { points: HitRateTrendPoint[] }) {
  if (points.length === 0) {
    return (
      <Card className="p-6">
        <h3 className="text-sm font-semibold mb-1">적중률 추이 (7일 이동평균)</h3>
        <p className="text-sm text-neutral-500">추이 데이터 없음</p>
      </Card>
    )
  }

  const data = points.map((p) => ({
    date: formatDateShort(p.date),
    hit_rate: p.rolling_hit_rate_1d !== null ? p.rolling_hit_rate_1d * 100 : null,
  }))

  return (
    <Card className="p-4">
      <h3 className="text-sm font-semibold mb-3">적중률 추이 (7일 이동평균)</h3>
      <ResponsiveContainer width="100%" height={260}>
        <LineChart data={data} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#262626" />
          <XAxis dataKey="date" stroke="#9ca3af" tick={{ fontSize: 11 }} />
          <YAxis
            domain={[0, 100]}
            stroke="#9ca3af"
            tick={{ fontSize: 11 }}
            tickFormatter={(v) => `${v}%`}
          />
          <Tooltip
            contentStyle={{ background: "#0f0f12", border: "1px solid #2a2a2f" }}
            formatter={(v: number) => [`${v.toFixed(1)}%`, "적중률"]}
          />
          <Line
            type="monotone"
            dataKey="hit_rate"
            stroke="#10b981"
            strokeWidth={2}
            connectNulls={false}
            dot={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </Card>
  )
}
