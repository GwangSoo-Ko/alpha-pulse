"use client"
import { useMemo, useState } from "react"
import { useRouter, useSearchParams, usePathname } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { SortableTh } from "@/components/ui/sortable-th"
import { ExportButton } from "@/components/ui/export-button"
import type { Trade } from "@/lib/types"

type SortKey = "buy_date" | "code" | "pnl" | "return_pct" | "holding_days"
type SortDir = "asc" | "desc"

export function TradesTable({
  runId,
  trades,
  initialFilters,
}: {
  runId: string
  trades: Trade[]
  initialFilters: { code?: string; winner?: string }
}) {
  const router = useRouter()
  const path = usePathname()
  const params = useSearchParams()
  const [code, setCode] = useState(initialFilters.code ?? "")
  const [sort, setSort] = useState<{ col: SortKey; dir: SortDir }>({
    col: "buy_date",
    dir: "desc",
  })

  const apply = (patch: Record<string, string | undefined>) => {
    const sp = new URLSearchParams(params.toString())
    for (const [k, v] of Object.entries(patch)) {
      if (!v) sp.delete(k)
      else sp.set(k, v)
    }
    router.push(`${path}?${sp.toString()}`)
  }

  function onSort(col: SortKey) {
    setSort((prev) =>
      prev.col === col
        ? { col, dir: prev.dir === "asc" ? "desc" : "asc" }
        : { col, dir: col === "code" ? "asc" : "desc" },
    )
  }

  const sorted = useMemo(() => {
    const copy = [...trades]
    copy.sort((a, b) => {
      const av = (a as Record<string, unknown>)[sort.col]
      const bv = (b as Record<string, unknown>)[sort.col]
      if (av == null && bv == null) return 0
      if (av == null) return 1
      if (bv == null) return -1
      const cmp = av < bv ? -1 : av > bv ? 1 : 0
      return sort.dir === "asc" ? cmp : -cmp
    })
    return copy
  }, [trades, sort])

  const totalPnl = trades.reduce((s, t) => s + t.pnl, 0)
  const wins = trades.filter((t) => t.pnl > 0).length
  const losses = trades.length - wins
  const avgHold = trades.length
    ? trades.reduce((s, t) => s + t.holding_days, 0) / trades.length
    : 0

  const exportHref = `/api/v1/backtest/runs/${runId}/trades/export`

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
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
        <ExportButton href={exportHref} />
      </div>

      <div className="rounded-md border border-neutral-800 text-sm">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>#</TableHead>
              <SortableTh
                label="종목"
                sortKey="code"
                currentSort={sort.col}
                currentDir={sort.dir}
                onSort={onSort}
                className="px-3 py-2 text-left"
              />
              <TableHead>이름</TableHead>
              <SortableTh
                label="매수일"
                sortKey="buy_date"
                currentSort={sort.col}
                currentDir={sort.dir}
                onSort={onSort}
                className="px-3 py-2 text-left"
              />
              <TableHead className="text-right">매수가</TableHead>
              <TableHead>매도일</TableHead>
              <TableHead className="text-right">매도가</TableHead>
              <SortableTh
                label="수익률"
                sortKey="return_pct"
                currentSort={sort.col}
                currentDir={sort.dir}
                onSort={onSort}
                className="px-3 py-2 text-right"
              />
              <SortableTh
                label="보유일"
                sortKey="holding_days"
                currentSort={sort.col}
                currentDir={sort.dir}
                onSort={onSort}
                className="px-3 py-2 text-right"
              />
              <SortableTh
                label="손익"
                sortKey="pnl"
                currentSort={sort.col}
                currentDir={sort.dir}
                onSort={onSort}
                className="px-3 py-2 text-right"
              />
            </TableRow>
          </TableHeader>
          <TableBody>
            {sorted.map((t, i) => (
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
