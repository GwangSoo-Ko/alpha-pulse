import { Card } from "@/components/ui/card"

const FIELDS: Array<{
  key: string
  label: string
  format: (n: number) => string
  color?: "red" | "green" | "neutral"
}> = [
  {
    key: "total_return",
    label: "총 수익률",
    format: (n) => `${n >= 0 ? "+" : ""}${n.toFixed(2)}%`,
    color: "green",
  },
  {
    key: "cagr",
    label: "CAGR",
    format: (n) => `${n >= 0 ? "+" : ""}${n.toFixed(2)}%`,
    color: "green",
  },
  {
    key: "sharpe_ratio",
    label: "샤프",
    format: (n) => n.toFixed(2),
    color: "neutral",
  },
  {
    key: "max_drawdown",
    label: "MDD",
    format: (n) => `${n.toFixed(2)}%`,
    color: "red",
  },
  {
    key: "win_rate",
    label: "승률",
    format: (n) => `${n.toFixed(1)}%`,
    color: "neutral",
  },
  {
    key: "turnover",
    label: "턴오버",
    format: (n) => `${n.toFixed(2)}x`,
    color: "neutral",
  },
]

export function MetricsCards({ metrics }: { metrics: Record<string, number> }) {
  return (
    <div className="grid grid-cols-2 gap-4 md:grid-cols-6">
      {FIELDS.map((f) => {
        const raw = metrics[f.key]
        const val = raw === undefined ? "-" : f.format(raw)
        const cls =
          f.color === "green" && raw !== undefined
            ? raw >= 0
              ? "text-green-400"
              : "text-red-400"
            : f.color === "red"
              ? "text-red-400"
              : "text-neutral-100"
        return (
          <Card key={f.key} className="p-4">
            <div className="text-xs text-neutral-500">{f.label}</div>
            <div className={`mt-1 text-xl font-semibold ${cls}`}>{val}</div>
          </Card>
        )
      })}
    </div>
  )
}
