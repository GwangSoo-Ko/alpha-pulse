import Link from "next/link"
import { Card } from "@/components/ui/card"
import { fmtPct } from "@/lib/format"

type Props = {
  risk: {
    report: {
      var_95?: number
      cvar_95?: number
      drawdown_status?: string
      alerts?: { level: string; message: string }[]
    }
  } | null
}

export function RiskStatusWidget({ risk }: Props) {
  const r = risk?.report
  const status = r?.drawdown_status ?? "-"
  const statusColor =
    status === "NORMAL" ? "text-green-400"
    : status === "WARN" ? "text-yellow-400"
    : status === "DELEVERAGE" ? "text-red-400"
    : "text-neutral-400"
  return (
    <Card className="p-4 space-y-2">
      <div className="flex justify-between items-center">
        <h3 className="font-medium">리스크 상태</h3>
        <Link href="/risk" className="text-xs text-blue-400 hover:underline">상세 →</Link>
      </div>
      <div className="flex justify-between text-sm">
        <span className="text-neutral-400">DD</span>
        <span className={`font-medium ${statusColor}`}>{status}</span>
      </div>
      <div className="flex justify-between text-sm">
        <span className="text-neutral-400">VaR95</span>
        <span className="font-mono">{r?.var_95 !== undefined ? fmtPct(r.var_95) : "-"}</span>
      </div>
      <div className="flex justify-between text-sm">
        <span className="text-neutral-400">CVaR95</span>
        <span className="font-mono">{r?.cvar_95 !== undefined ? fmtPct(r.cvar_95) : "-"}</span>
      </div>
      <div className="flex justify-between text-sm">
        <span className="text-neutral-400">경고</span>
        <span className="font-mono">{r?.alerts?.length ?? 0}건</span>
      </div>
    </Card>
  )
}
