"use client"
import { useState } from "react"
import { useRouter, useSearchParams, usePathname } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import type { Position } from "@/lib/types"

export function PositionViewer({
  positions, initialDate, initialCode, startDate, endDate,
}: {
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

  const apply = () => {
    const sp = new URLSearchParams(params.toString())
    if (date) sp.set("date", date); else sp.delete("date")
    if (code) sp.set("code", code); else sp.delete("code")
    router.push(`${path}?${sp.toString()}`)
  }

  // 날짜 유니크 리스트 (최근 20개만 슬라이스용)
  const uniqueDates = [...new Set(positions.map((p) => p.date))].sort()

  const total = positions.reduce((s, p) => s + p.unrealized_pnl, 0)

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
              <TableHead>날짜</TableHead>
              <TableHead>종목</TableHead>
              <TableHead>이름</TableHead>
              <TableHead className="text-right">수량</TableHead>
              <TableHead className="text-right">평단가</TableHead>
              <TableHead className="text-right">현재가</TableHead>
              <TableHead className="text-right">평가손익</TableHead>
              <TableHead className="text-right">비중</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {positions.map((p, i) => (
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
