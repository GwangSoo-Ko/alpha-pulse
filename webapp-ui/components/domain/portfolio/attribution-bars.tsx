"use client"
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip } from "recharts"

type Props = { title: string; data: Record<string, number> }

export function AttributionBars({ title, data }: Props) {
  const entries = Object.entries(data).map(([name, value]) => ({ name, value }))
  if (entries.length === 0) {
    return (
      <div className="rounded-lg border border-neutral-800 p-4">
        <h2 className="mb-4 text-lg">{title}</h2>
        <p className="text-sm text-neutral-500">데이터 없음.</p>
      </div>
    )
  }
  return (
    <div className="rounded-lg border border-neutral-800 p-4">
      <h2 className="mb-4 text-lg">{title}</h2>
      <ResponsiveContainer width="100%" height={Math.max(180, entries.length * 30)}>
        <BarChart data={entries} layout="vertical">
          <XAxis type="number" tickFormatter={(v) => v.toFixed(1) + "%"} tick={{ fill: "#a3a3a3", fontSize: 11 }} />
          <YAxis dataKey="name" type="category" tick={{ fill: "#a3a3a3", fontSize: 11 }} width={100} />
          <Tooltip contentStyle={{ background: "#171717", border: "1px solid #404040" }} formatter={(v: number) => `${v.toFixed(2)}%`} />
          <Bar dataKey="value" fill="#22c55e" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
