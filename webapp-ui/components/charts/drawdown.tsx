"use client"
import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip } from "recharts"
import type { Snapshot } from "@/lib/types"

export function Drawdown({ snapshots }: { snapshots: Snapshot[] }) {
  const data = snapshots.map((s) => ({
    date: s.date,
    dd: s.drawdown, // 음수
  }))
  return (
    <ResponsiveContainer width="100%" height={240}>
      <AreaChart data={data}>
        <XAxis dataKey="date" tick={{ fill: "#a3a3a3", fontSize: 11 }} />
        <YAxis tickFormatter={(v) => `${v}%`} tick={{ fill: "#a3a3a3", fontSize: 11 }} />
        <Tooltip
          contentStyle={{ background: "#171717", border: "1px solid #404040" }}
          formatter={(v: number) => [`${v.toFixed(2)}%`, "Drawdown"]}
        />
        <Area type="monotone" dataKey="dd" stroke="#ef4444" fill="#ef4444" fillOpacity={0.2} />
      </AreaChart>
    </ResponsiveContainer>
  )
}
