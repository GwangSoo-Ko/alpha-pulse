import { Card } from "@/components/ui/card"
import { fmtPct } from "@/lib/format"

type Props = {
  report: { drawdown_status: string; var_95: number; cvar_95: number; alerts: unknown[] }
  cached: boolean
}

export function RiskCards({ report, cached }: Props) {
  const ddColor =
    report.drawdown_status === "NORMAL" ? "text-green-400"
    : report.drawdown_status === "WARN" ? "text-yellow-400"
    : report.drawdown_status === "DELEVERAGE" ? "text-red-400"
    : "text-neutral-100"
  return (
    <div className="space-y-2">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card className="p-4">
          <div className="text-xs text-neutral-400">드로다운 상태</div>
          <div className={`mt-1 text-xl font-semibold ${ddColor}`}>{report.drawdown_status}</div>
        </Card>
        <Card className="p-4">
          <div className="text-xs text-neutral-400">VaR 95%</div>
          <div className="mt-1 text-xl font-semibold font-mono text-red-400">{fmtPct(report.var_95)}</div>
        </Card>
        <Card className="p-4">
          <div className="text-xs text-neutral-400">CVaR 95%</div>
          <div className="mt-1 text-xl font-semibold font-mono text-red-400">{fmtPct(report.cvar_95)}</div>
        </Card>
        <Card className="p-4">
          <div className="text-xs text-neutral-400">경고</div>
          <div className="mt-1 text-xl font-semibold font-mono">{report.alerts.length}건</div>
        </Card>
      </div>
      {cached && <p className="text-xs text-neutral-500">캐시된 결과.</p>}
    </div>
  )
}
