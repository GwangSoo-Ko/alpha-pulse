"use client"
import Link from "next/link"
import { Card } from "@/components/ui/card"

type DataStatus = {
  tables: { name: string; row_count: number; latest_date: string | null }[]
  gaps_count: number
}

export function DataHealthWidget({ status }: { status: DataStatus }) {
  const gaps = status.gaps_count
  const latest = status.tables[0]?.latest_date ?? null
  return (
    <Link href="/data" className="block">
      <Card className="p-4 min-h-[160px] hover:border-neutral-600 transition">
        <div className="text-xs text-neutral-400 uppercase tracking-wide mb-2">Data Health</div>
        {gaps === 0 ? (
          <div className="text-2xl font-bold text-emerald-400 mb-2">✓ 정상</div>
        ) : (
          <div className="text-2xl font-bold text-rose-400 mb-2">갭 {gaps}건</div>
        )}
        <p className="text-xs text-neutral-500">
          {latest ? `최신 수집: ${latest}` : "수집 기록 없음"}
        </p>
      </Card>
    </Link>
  )
}
