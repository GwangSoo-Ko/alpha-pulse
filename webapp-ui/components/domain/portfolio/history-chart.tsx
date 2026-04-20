"use client"
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, BarChart, Bar,
} from "recharts"

type Snapshot = {
  date: string
  total_value: number
  daily_return: number
}

export function HistoryChart({ snapshots }: { snapshots: Snapshot[] }) {
  if (snapshots.length === 0) {
    return <p className="text-sm text-neutral-500">이력 없음.</p>
  }
  return (
    <div className="space-y-6">
      <div className="rounded-lg border border-neutral-800 p-4">
        <h2 className="mb-4 text-lg">자산 곡선</h2>
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={snapshots}>
            <XAxis dataKey="date" tick={{ fill: "#a3a3a3", fontSize: 11 }} />
            <YAxis tickFormatter={(v) => (v / 1e6).toFixed(0) + "M"} tick={{ fill: "#a3a3a3", fontSize: 11 }} />
            <Tooltip contentStyle={{ background: "#171717", border: "1px solid #404040" }} />
            <Line type="monotone" dataKey="total_value" stroke="#22c55e" strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <div className="rounded-lg border border-neutral-800 p-4">
        <h2 className="mb-4 text-lg">일별 수익률</h2>
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={snapshots}>
            <XAxis dataKey="date" tick={{ fill: "#a3a3a3", fontSize: 11 }} />
            <YAxis tickFormatter={(v) => v.toFixed(1) + "%"} tick={{ fill: "#a3a3a3", fontSize: 11 }} />
            <Tooltip contentStyle={{ background: "#171717", border: "1px solid #404040" }} />
            <Bar dataKey="daily_return" fill="#22c55e" />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
