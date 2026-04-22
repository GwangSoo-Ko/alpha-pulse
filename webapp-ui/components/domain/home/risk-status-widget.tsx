"use client"
import Link from "next/link"
import { Card } from "@/components/ui/card"

type RiskReport = {
  report?: {
    var_95?: number
    cvar_95?: number
    drawdown_status?: string
    alerts?: { level: string; message: string }[]
  }
}

export function RiskStatusWidget({ risk }: { risk: RiskReport | null }) {
  const alerts = risk?.report?.alerts ?? []
  return (
    <Link href="/risk" className="block">
      <Card className="p-4 min-h-[160px] hover:border-neutral-600 transition">
        <div className="text-xs text-neutral-400 uppercase tracking-wide mb-2">Risk</div>
        {!risk ? (
          <p className="text-sm text-neutral-500">리스크 데이터 없음</p>
        ) : alerts.length === 0 ? (
          <>
            <div className="text-2xl font-bold text-emerald-400 mb-2">정상</div>
            <p className="text-xs text-neutral-500">경고 없음</p>
          </>
        ) : (
          <>
            <div className="text-2xl font-bold text-amber-400 mb-2">⚠ {alerts.length}건</div>
            <p className="text-xs text-neutral-300 line-clamp-2">{alerts[0].message}</p>
          </>
        )}
      </Card>
    </Link>
  )
}
