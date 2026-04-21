import Link from "next/link"
import { Card } from "@/components/ui/card"

type Props = {
  status: {
    tables: { name: string; row_count: number; latest_date: string | null }[]
    gaps_count: number
  }
}

export function DataStatusWidget({ status }: Props) {
  const ohlcv = status.tables.find((t) => t.name === "ohlcv")
  return (
    <Card className="p-4 space-y-2">
      <div className="flex justify-between items-center">
        <h3 className="font-medium">데이터</h3>
        <Link href="/data" className="text-xs text-blue-400 hover:underline">상세 →</Link>
      </div>
      <div className="flex justify-between text-sm">
        <span className="text-neutral-400">OHLCV 최신</span>
        <span className="font-mono">{ohlcv?.latest_date ?? "-"}</span>
      </div>
      <div className="flex justify-between text-sm">
        <span className="text-neutral-400">갭 감지</span>
        <span className={`font-mono ${status.gaps_count > 0 ? "text-yellow-400" : "text-green-400"}`}>
          {status.gaps_count}종목
        </span>
      </div>
    </Card>
  )
}
