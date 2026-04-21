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
    return <PortfolioEmptyState />
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

function PortfolioEmptyState() {
  return (
    <Card className="p-6 h-full space-y-4">
      <div>
        <h2 className="text-lg font-semibold mb-1">포트폴리오</h2>
        <p className="text-sm text-neutral-500">
          아직 매매 실행 이력이 없어 표시할 스냅샷이 없습니다.
        </p>
      </div>

      <div className="rounded-lg border border-neutral-800 bg-neutral-900/50 p-4 space-y-3">
        <h3 className="text-sm font-medium text-neutral-200">시작하는 방법</h3>
        <ol className="list-decimal list-inside space-y-2 text-xs text-neutral-400">
          <li>
            <span className="text-neutral-200">데이터 준비</span> — 최신 시세/재무 데이터가 DB에 있는지 확인
            <div className="ml-4 mt-1">
              <Link href="/data" className="text-blue-400 hover:underline">
                → /data 페이지에서 현황 확인
              </Link>
            </div>
          </li>
          <li>
            <span className="text-neutral-200">Paper 모드 1회 실행</span> — 가상 계좌로 전체 파이프라인 동작 검증
            <div className="mt-1 ml-4 font-mono text-xs text-neutral-500 bg-neutral-950 px-2 py-1 rounded">
              uv run ap trading run --mode paper
            </div>
            <p className="ml-4 mt-1 text-[11px] text-neutral-500">
              실제 돈은 움직이지 않습니다. 데이터 수집 → 전략 → 시그널 → 가상 주문 → 스냅샷까지 한 번에 실행.
            </p>
          </li>
          <li>
            <span className="text-neutral-200">결과 확인</span> — 이 페이지 새로고침 or{" "}
            <Link href="/portfolio" className="text-blue-400 hover:underline">/portfolio</Link>
          </li>
        </ol>
      </div>

      <div className="rounded-lg border border-neutral-800 bg-neutral-900/50 p-4 space-y-2">
        <h3 className="text-sm font-medium text-neutral-200">먼저 해볼 것들</h3>
        <div className="flex flex-wrap gap-2 text-xs">
          <Link
            href="/backtest/new"
            className="px-3 py-1.5 rounded border border-neutral-700 hover:bg-neutral-800"
          >
            백테스트 실행 →
          </Link>
          <Link
            href="/screening/new"
            className="px-3 py-1.5 rounded border border-neutral-700 hover:bg-neutral-800"
          >
            스크리닝 실행 →
          </Link>
          <Link
            href="/data"
            className="px-3 py-1.5 rounded border border-neutral-700 hover:bg-neutral-800"
          >
            데이터 현황 →
          </Link>
        </div>
      </div>
    </Card>
  )
}
