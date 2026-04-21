import { Card } from "@/components/ui/card"
import { fmtKrw, fmtPct } from "@/lib/format"

type Snapshot = {
  date: string; cash: number; total_value: number
  daily_return: number; cumulative_return: number; drawdown: number
}

export function SummaryCard({ snapshot }: { snapshot: Snapshot }) {
  const items: Array<{ label: string; value: string; color?: string }> = [
    { label: "총 자산", value: fmtKrw(snapshot.total_value) },
    { label: "현금", value: fmtKrw(snapshot.cash) },
    {
      label: "일간 수익률",
      value: fmtPct(snapshot.daily_return),
      color: snapshot.daily_return >= 0 ? "text-green-400" : "text-red-400",
    },
    {
      label: "누적 수익률",
      value: fmtPct(snapshot.cumulative_return),
      color: snapshot.cumulative_return >= 0 ? "text-green-400" : "text-red-400",
    },
    {
      label: "드로다운",
      value: fmtPct(snapshot.drawdown),
      color: "text-red-400",
    },
  ]
  return (
    <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
      {items.map((it) => (
        <Card key={it.label} className="p-4">
          <div className="text-xs text-neutral-400">{it.label}</div>
          <div className={`mt-1 text-xl font-semibold font-mono ${it.color ?? "text-neutral-100"}`}>
            {it.value}
          </div>
        </Card>
      ))}
    </div>
  )
}
