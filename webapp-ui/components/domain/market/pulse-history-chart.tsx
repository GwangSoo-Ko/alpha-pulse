"use client"
import { useState } from "react"
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip,
  ReferenceArea, ReferenceLine,
} from "recharts"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"

export type HistoryItem = {
  date: string    // YYYYMMDD
  score: number
  signal: string
}

const RANGES: { days: number; label: string }[] = [
  { days: 30, label: "30일" },
  { days: 60, label: "60일" },
  { days: 90, label: "90일" },
]

function formatDateTick(yyyymmdd: string): string {
  return `${yyyymmdd.slice(4, 6)}/${yyyymmdd.slice(6)}`
}

export function PulseHistoryChart({
  items,
  onRangeChange,
  initialRange = 30,
}: {
  items: HistoryItem[]
  onRangeChange?: (days: number) => void
  initialRange?: number
}) {
  const [range, setRange] = useState(initialRange)

  return (
    <Card className="p-4">
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-sm text-neutral-300">Pulse Score 추이</h2>
        <div className="flex gap-1">
          {RANGES.map((r) => (
            <Button
              key={r.days}
              size="sm"
              variant={range === r.days ? "default" : "outline"}
              onClick={() => {
                setRange(r.days)
                onRangeChange?.(r.days)
              }}
            >
              {r.label}
            </Button>
          ))}
        </div>
      </div>
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={items}>
            <XAxis
              dataKey="date" tickFormatter={formatDateTick}
              stroke="#888" fontSize={11}
            />
            <YAxis
              domain={[-100, 100]} stroke="#888" fontSize={11}
              ticks={[-100, -60, -20, 20, 60, 100]}
            />
            <ReferenceArea y1={60} y2={100} fill="#22c55e" fillOpacity={0.08} />
            <ReferenceArea y1={20} y2={60} fill="#10b981" fillOpacity={0.06} />
            <ReferenceArea y1={-19} y2={20} fill="#eab308" fillOpacity={0.06} />
            <ReferenceArea y1={-59} y2={-19} fill="#f97316" fillOpacity={0.06} />
            <ReferenceArea y1={-100} y2={-59} fill="#ef4444" fillOpacity={0.08} />
            <ReferenceLine y={0} stroke="#555" strokeDasharray="3 3" />
            <Tooltip
              contentStyle={{
                background: "#1f1f1f", border: "1px solid #333",
                fontSize: 12,
              }}
              labelFormatter={formatDateTick}
              formatter={(v: number) => [v.toFixed(1), "Score"]}
            />
            <Line
              type="monotone" dataKey="score" stroke="#60a5fa"
              strokeWidth={2} dot={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </Card>
  )
}
