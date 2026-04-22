"use client"
import Link from "next/link"
import { Card } from "@/components/ui/card"

type PortfolioSnapshot = {
  date: string
  cash: number
  total_value: number
  daily_return: number
  cumulative_return: number
  drawdown: number
  positions: { code: string; name: string; quantity: number; current_price: number }[]
}

function formatKRW(v: number): string {
  if (Math.abs(v) >= 1e8) return `${(v / 1e8).toFixed(2)}억`
  if (Math.abs(v) >= 1e4) return `${(v / 1e4).toFixed(0)}만`
  return v.toLocaleString()
}

function pctColor(v: number): string {
  if (v > 0) return "text-emerald-400"
  if (v < 0) return "text-rose-400"
  return "text-neutral-400"
}

export function PortfolioWidget({
  portfolio,
  history: _history,
}: {
  portfolio: PortfolioSnapshot | null
  history?: { date: string; total_value: number }[]
}) {
  if (!portfolio) {
    return (
      <Link href="/portfolio" className="block">
        <Card className="p-4 min-h-[160px] hover:border-neutral-600 transition">
          <div className="text-xs text-neutral-400 uppercase tracking-wide mb-2">Portfolio</div>
          <p className="text-sm text-neutral-500">포트폴리오 스냅샷 없음</p>
        </Card>
      </Link>
    )
  }
  const sign = (v: number) => (v >= 0 ? "+" : "")
  return (
    <Link href="/portfolio" className="block">
      <Card className="p-4 min-h-[160px] hover:border-neutral-600 transition">
        <div className="text-xs text-neutral-400 uppercase tracking-wide mb-2">Portfolio</div>
        <div className="text-2xl font-bold font-mono mb-2">₩{formatKRW(portfolio.total_value)}</div>
        <div className="space-y-1 text-xs">
          <div className="flex justify-between">
            <span className="text-neutral-400">일간</span>
            <span className={`font-mono ${pctColor(portfolio.daily_return)}`}>
              {sign(portfolio.daily_return)}{portfolio.daily_return.toFixed(2)}%
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-neutral-400">누적</span>
            <span className={`font-mono ${pctColor(portfolio.cumulative_return)}`}>
              {sign(portfolio.cumulative_return)}{portfolio.cumulative_return.toFixed(2)}%
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-neutral-400">드로다운</span>
            <span className={`font-mono ${pctColor(portfolio.drawdown)}`}>
              {portfolio.drawdown.toFixed(2)}%
            </span>
          </div>
        </div>
      </Card>
    </Link>
  )
}
