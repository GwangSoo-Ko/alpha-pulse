import Link from "next/link"
import { Card } from "@/components/ui/card"
import { fmtPct } from "@/lib/format"

type Props = {
  items: {
    run_id: string
    name: string
    start_date: string
    end_date: string
    metrics: Record<string, number>
  }[]
}

export function RecentBacktestsWidget({ items }: Props) {
  return (
    <Card className="p-4 space-y-2">
      <div className="flex justify-between items-center">
        <h3 className="font-medium">최근 백테스트</h3>
        <Link href="/backtest" className="text-xs text-blue-400 hover:underline">전체 →</Link>
      </div>
      {items.length === 0 ? (
        <p className="text-xs text-neutral-500">없음.</p>
      ) : (
        <ul className="space-y-1 text-sm">
          {items.slice(0, 3).map((r) => (
            <li key={r.run_id} className="flex justify-between">
              <Link href={`/backtest/${r.run_id.slice(0, 8)}`} className="hover:underline truncate">
                {r.name || r.run_id.slice(0, 8)}
              </Link>
              <span className={`font-mono ${(r.metrics.total_return ?? 0) >= 0 ? "text-green-400" : "text-red-400"}`}>
                {fmtPct(r.metrics.total_return)}
              </span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}
