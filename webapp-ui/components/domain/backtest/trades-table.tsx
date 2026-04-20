"use client"
import { useRouter, useSearchParams, usePathname } from "next/navigation"
import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import type { Trade } from "@/lib/types"

export function TradesTable({
  trades, initialFilters,
}: { trades: Trade[]; initialFilters: { code?: string; winner?: string } }) {
  const router = useRouter()
  const path = usePathname()
  const params = useSearchParams()
  const [code, setCode] = useState(initialFilters.code ?? "")

  const apply = (patch: Record<string, string | undefined>) => {
    const sp = new URLSearchParams(params.toString())
    for (const [k, v] of Object.entries(patch)) {
      if (!v) sp.delete(k); else sp.set(k, v)
    }
    router.push(`${path}?${sp.toString()}`)
  }

  const totalPnl = trades.reduce((s, t) => s + t.pnl, 0)
  const wins = trades.filter((t) => t.pnl > 0).length
  const losses = trades.length - wins
  const avgHold = trades.length
    ? trades.reduce((s, t) => s + t.holding_days, 0) / trades.length
    : 0

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <Input
          placeholder="종목코드"
          value={code}
          onChange={(e) => setCode(e.target.value)}
          className="max-w-xs"
        />
        <Button variant="outline" onClick={() => apply({ code, winner: undefined })}>
          전체
        </Button>
        <Button variant="outline" onClick={() => apply({ code, winner: "true" })}>
          승리만
        </Button>
        <Button variant="outline" onClick={() => apply({ code, winner: "false" })}>
          패배만
        </Button>
      </div>

      <div className="rounded-md border border-neutral-800 text-sm">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>#</TableHead>
              <TableHead>종목</TableHead>
              <TableHead>이름</TableHead>
              <TableHead>매수일</TableHead>
              <TableHead className="text-right">매수가</TableHead>
              <TableHead>매도일</TableHead>
              <TableHead className="text-right">매도가</TableHead>
              <TableHead className="text-right">수익률</TableHead>
              <TableHead className="text-right">보유일</TableHead>
              <TableHead className="text-right">손익</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {trades.map((t, i) => (
              <TableRow key={`${t.code}-${t.buy_date}-${i}`}>
                <TableCell className="font-mono">{i + 1}</TableCell>
                <TableCell className="font-mono">{t.code}</TableCell>
                <TableCell>{t.name}</TableCell>
                <TableCell>{t.buy_date}</TableCell>
                <TableCell className="text-right font-mono">{t.buy_price.toLocaleString()}</TableCell>
                <TableCell>{t.sell_date}</TableCell>
                <TableCell className="text-right font-mono">{t.sell_price.toLocaleString()}</TableCell>
                <TableCell className={`text-right font-mono ${t.pnl > 0 ? "text-green-400" : "text-red-400"}`}>
                  {t.return_pct >= 0 ? "+" : ""}{t.return_pct.toFixed(1)}%
                </TableCell>
                <TableCell className="text-right">{t.holding_days}일</TableCell>
                <TableCell className={`text-right font-mono ${t.pnl > 0 ? "text-green-400" : "text-red-400"}`}>
                  {t.pnl >= 0 ? "+" : ""}{t.pnl.toLocaleString()}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      <div className="text-sm text-neutral-400">
        총 {trades.length}건 (승 {wins} / 패 {losses})
        · 총 손익 <span className={totalPnl >= 0 ? "text-green-400" : "text-red-400"}>
          {totalPnl >= 0 ? "+" : ""}{totalPnl.toLocaleString()}원
        </span>
        · 평균 보유 {avgHold.toFixed(0)}일
      </div>
    </div>
  )
}
