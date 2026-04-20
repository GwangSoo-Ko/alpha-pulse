"use client"
import Link from "next/link"
import { useRouter, useSearchParams } from "next/navigation"
import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import type { RunList } from "@/lib/types"

const fmtPct = (n: number | undefined) =>
  n === undefined ? "-" : `${n >= 0 ? "+" : ""}${n.toFixed(2)}%`

export function RunsTable({
  data,
  currentPage,
  currentName,
}: {
  data: RunList
  currentPage: number
  currentName: string
}) {
  const router = useRouter()
  const params = useSearchParams()
  const [name, setName] = useState(currentName)

  const updateQuery = (patch: Record<string, string | undefined>) => {
    const sp = new URLSearchParams(params.toString())
    for (const [k, v] of Object.entries(patch)) {
      if (v === undefined || v === "") sp.delete(k)
      else sp.set(k, v)
    }
    router.push(`/backtest?${sp.toString()}`)
  }

  const totalPages = Math.max(1, Math.ceil(data.total / data.size))

  return (
    <div className="space-y-4">
      <form
        onSubmit={(e) => {
          e.preventDefault()
          updateQuery({ name, page: "1" })
        }}
        className="flex gap-2"
      >
        <Input
          placeholder="이름 검색"
          value={name}
          onChange={(e) => setName(e.target.value)}
          className="max-w-sm"
        />
        <Button type="submit" variant="outline">
          검색
        </Button>
      </form>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>ID</TableHead>
            <TableHead>이름</TableHead>
            <TableHead>기간</TableHead>
            <TableHead className="text-right">총수익률</TableHead>
            <TableHead className="text-right">샤프</TableHead>
            <TableHead className="text-right">MDD</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {data.items.map((r) => (
            <TableRow key={r.run_id} className="cursor-pointer">
              <TableCell>
                <Link
                  href={`/backtest/${r.run_id.slice(0, 8)}`}
                  className="font-mono text-xs"
                >
                  {r.run_id.slice(0, 8)}
                </Link>
              </TableCell>
              <TableCell>{r.name || "-"}</TableCell>
              <TableCell className="text-neutral-400">
                {r.start_date}~{r.end_date}
              </TableCell>
              <TableCell className="text-right font-mono">
                {fmtPct(r.metrics.total_return)}
              </TableCell>
              <TableCell className="text-right font-mono">
                {r.metrics.sharpe_ratio?.toFixed(2) ?? "-"}
              </TableCell>
              <TableCell className="text-right font-mono text-red-400">
                {fmtPct(r.metrics.max_drawdown)}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>

      <div className="flex items-center justify-between text-sm">
        <span className="text-neutral-500">
          총 {data.total}건, {currentPage}/{totalPages} 페이지
        </span>
        <div className="space-x-2">
          <Button
            size="sm"
            variant="outline"
            disabled={currentPage <= 1}
            onClick={() => updateQuery({ page: String(currentPage - 1) })}
          >
            이전
          </Button>
          <Button
            size="sm"
            variant="outline"
            disabled={currentPage >= totalPages}
            onClick={() => updateQuery({ page: String(currentPage + 1) })}
          >
            다음
          </Button>
        </div>
      </div>
    </div>
  )
}
