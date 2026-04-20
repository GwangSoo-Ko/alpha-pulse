import Link from "next/link"
import { Card } from "@/components/ui/card"
import { fmtKrw, fmtPct } from "@/lib/format"

type Props = {
  portfolio: {
    date: string
    cash: number
    total_value: number
    daily_return: number
    cumulative_return: number
    drawdown: number
    positions: { code: string; name: string; quantity: number; current_price: number }[]
  } | null
  history: { date: string; total_value: number }[]
}

export function PortfolioWidget({ portfolio, history }: Props) {
  if (!portfolio) {
    return (
      <Card className="p-6 h-full">
        <h2 className="text-lg font-semibold mb-2">포트폴리오</h2>
        <p className="text-sm text-neutral-500">
          포트폴리오 스냅샷 없음. 매매 실행 전 상태.
        </p>
      </Card>
    )
  }
  const top5 = portfolio.positions.slice(0, 5)
  return (
    <Card className="p-6 h-full space-y-4">
      <div className="flex justify-between items-start">
        <div>
          <h2 className="text-lg font-semibold">포트폴리오</h2>
          <p className="text-xs text-neutral-500">{portfolio.date}</p>
        </div>
        <Link href="/portfolio" className="text-xs text-blue-400 hover:underline">상세 →</Link>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <div className="text-xs text-neutral-400">총 자산</div>
          <div className="text-xl font-mono font-semibold">{fmtKrw(portfolio.total_value)}</div>
        </div>
        <div>
          <div className="text-xs text-neutral-400">현금</div>
          <div className="text-lg font-mono">{fmtKrw(portfolio.cash)}</div>
        </div>
        <div>
          <div className="text-xs text-neutral-400">일간</div>
          <div className={`text-lg font-mono ${portfolio.daily_return >= 0 ? "text-green-400" : "text-red-400"}`}>
            {fmtPct(portfolio.daily_return)}
          </div>
        </div>
        <div>
          <div className="text-xs text-neutral-400">누적</div>
          <div className={`text-lg font-mono ${portfolio.cumulative_return >= 0 ? "text-green-400" : "text-red-400"}`}>
            {fmtPct(portfolio.cumulative_return)}
          </div>
        </div>
      </div>
      {history.length > 0 && <Sparkline points={history.map((h) => h.total_value)} />}
      <div>
        <h3 className="text-sm font-medium mb-2">상위 5 보유 종목</h3>
        {top5.length === 0 ? (
          <p className="text-xs text-neutral-500">보유 종목 없음.</p>
        ) : (
          <ul className="text-sm space-y-1">
            {top5.map((p) => (
              <li key={p.code} className="flex justify-between">
                <span className="font-mono text-xs">{p.code} {p.name}</span>
                <span className="font-mono">{p.quantity}주 @ {fmtKrw(p.current_price)}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </Card>
  )
}

function Sparkline({ points }: { points: number[] }) {
  if (points.length === 0) return null
  const min = Math.min(...points)
  const max = Math.max(...points)
  const range = max - min || 1
  const w = 300
  const h = 60
  const step = w / Math.max(1, points.length - 1)
  const d = points
    .map((v, i) => {
      const x = i * step
      const y = h - ((v - min) / range) * h
      return `${i === 0 ? "M" : "L"} ${x.toFixed(1)} ${y.toFixed(1)}`
    })
    .join(" ")
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full h-16">
      <path d={d} stroke="#22c55e" strokeWidth="2" fill="none" />
    </svg>
  )
}
