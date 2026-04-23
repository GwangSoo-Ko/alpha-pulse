"use client"
import { useMemo, useState } from "react"
import { useRouter, useSearchParams, usePathname } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { SortableTh } from "@/components/ui/sortable-th"
import { ExportButton } from "@/components/ui/export-button"
import type { Position } from "@/lib/types"

type SortKey = "date" | "code" | "quantity" | "avg_price" | "current_price" | "unrealized_pnl" | "weight"
type SortDir = "asc" | "desc"

export function PositionViewer({
  runId,
  positions, initialDate, initialCode, startDate, endDate,
}: {
  runId: string
  positions: Position[]
  initialDate?: string
  initialCode?: string
  startDate: string
  endDate: string
}) {
  const router = useRouter()
  const path = usePathname()
  const params = useSearchParams()
  const [date, setDate] = useState(initialDate ?? "")
  const [code, setCode] = useState(initialCode ?? "")
  const [sort, setSort] = useState<{ col: SortKey; dir: SortDir }>({
    col: "date", dir: "desc",
  })

  const apply = () => {
    const sp = new URLSearchParams(params.toString())
    if (date) sp.set("date", date); else sp.delete("date")
    if (code) sp.set("code", code); else sp.delete("code")
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
    const copy = [...positions]
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
  }, [positions, sort])

  // 날짜 유니크 리스트 (최근 20개만 슬라이스용)
  const uniqueDates = [...new Set(positions.map((p) => p.date))].sort()

  const total = positions.reduce((s, p) => s + p.unrealized_pnl, 0)

  const exportHref = `/api/v1/backtest/runs/${runId}/positions/export`

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-2">
        <div>
          <label className="mb-1 block text-xs text-neutral-400">날짜 (YYYYMMDD)</label>
          <Input
            value={date} onChange={(e) => setDate(e.target.value)}
            placeholder={`${startDate}~${endDate}`} className="w-40"
          />
        </div>
        <div>
          <label className="mb-1 block text-xs text-neutral-400">종목코드</label>
          <Input value={code} onChange={(e) => setCode(e.target.value)} className="w-40" />
        </div>
        <Button onClick={apply}>필터</Button>
        <Button
          variant="outline"
          onClick={() => {
            setDate(""); setCode("")
            router.push(path)
          }}
        >초기화</Button>
        <div className="ml-auto">
          <ExportButton href={exportHref} />
        </div>
      </div>

      {uniqueDates.length > 1 && !date && (
        <div className="text-xs text-neutral-500">
          전 기간 보유 이력 표시 중. 날짜 하나를 지정하면 해당일 스냅샷만 표시.
        </div>
      )}

      <div className="rounded-md border border-neutral-800 text-sm">
        <Table>
          <TableHeader>
            <TableRow>
              <SortableTh<SortKey>
                label="날짜"
                sortKey="date"
                currentSort={sort.col}
                currentDir={sort.dir}
                onSort={onSort}
              />
              <SortableTh<SortKey>
                label="종목"
                sortKey="code"
                currentSort={sort.col}
                currentDir={sort.dir}
                onSort={onSort}
              />
              <TableHead>이름</TableHead>
              <SortableTh<SortKey>
                label="수량"
                sortKey="quantity"
                currentSort={sort.col}
                currentDir={sort.dir}
                onSort={onSort}
                className="text-right"
              />
              <SortableTh<SortKey>
                label="평단가"
                sortKey="avg_price"
                currentSort={sort.col}
                currentDir={sort.dir}
                onSort={onSort}
                className="text-right"
              />
              <SortableTh<SortKey>
                label="현재가"
                sortKey="current_price"
                currentSort={sort.col}
                currentDir={sort.dir}
                onSort={onSort}
                className="text-right"
              />
              <SortableTh<SortKey>
                label="평가손익"
                sortKey="unrealized_pnl"
                currentSort={sort.col}
                currentDir={sort.dir}
                onSort={onSort}
                className="text-right"
              />
              <SortableTh<SortKey>
                label="비중"
                sortKey="weight"
                currentSort={sort.col}
                currentDir={sort.dir}
                onSort={onSort}
                className="text-right"
              />
            </TableRow>
          </TableHeader>
          <TableBody>
            {sorted.map((p, i) => (
              <TableRow key={`${p.date}-${p.code}-${i}`}>
                <TableCell>{p.date}</TableCell>
                <TableCell className="font-mono">{p.code}</TableCell>
                <TableCell>{p.name}</TableCell>
                <TableCell className="text-right font-mono">{p.quantity}</TableCell>
                <TableCell className="text-right font-mono">{p.avg_price.toLocaleString()}</TableCell>
                <TableCell className="text-right font-mono">{p.current_price.toLocaleString()}</TableCell>
                <TableCell className={`text-right font-mono ${p.unrealized_pnl >= 0 ? "text-green-400" : "text-red-400"}`}>
                  {p.unrealized_pnl >= 0 ? "+" : ""}{p.unrealized_pnl.toLocaleString()}
                </TableCell>
                <TableCell className="text-right font-mono">
                  {(p.weight * 100).toFixed(1)}%
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      <div className="text-sm text-neutral-400">
        총 {positions.length}행 · 합계 평가손익
        <span className={total >= 0 ? " text-green-400" : " text-red-400"}>
          {" "}{total >= 0 ? "+" : ""}{total.toLocaleString()}원
        </span>
      </div>
    </div>
  )
}
