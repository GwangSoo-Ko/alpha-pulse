"use client"
import Link from "next/link"
import { useRouter, useSearchParams } from "next/navigation"
import { useState } from "react"
import { Button } from "@/components/ui/button"
import { ExportButton } from "@/components/ui/export-button"
import { Input } from "@/components/ui/input"
import { SortableTh } from "@/components/ui/sortable-th"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import type { RunList } from "@/lib/types"

type SortKey = "created_at" | "name" | "start_date" | "final_return"

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

  const currentSort = (params?.get("sort") ?? "created_at") as SortKey
  const currentDir = (params?.get("dir") ?? "desc") as "asc" | "desc"

  const updateQuery = (patch: Record<string, string | undefined>) => {
    const sp = new URLSearchParams(params?.toString() ?? "")
    for (const [k, v] of Object.entries(patch)) {
      if (v === undefined || v === "") sp.delete(k)
      else sp.set(k, v)
    }
    router.push(`/backtest?${sp.toString()}`)
  }

  function onSort(key: SortKey) {
    const sp = new URLSearchParams(params?.toString() ?? "")
    if (currentSort === key) {
      sp.set("dir", currentDir === "asc" ? "desc" : "asc")
    } else {
      sp.set("sort", key)
      sp.set("dir", "desc")
    }
    sp.delete("page")
    router.push(`/backtest?${sp}`)
  }

  const exportQs = new URLSearchParams(params?.toString() ?? "")
  exportQs.delete("page")
  const exportHref = `/api/v1/backtest/runs/export?${exportQs}`

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

      <div className="flex items-center justify-between">
        <p className="text-sm text-neutral-400">
          총 {data.total}건 · 페이지 {currentPage}/{totalPages}
        </p>
        <ExportButton href={exportHref} />
      </div>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>ID</TableHead>
            <SortableTh
              label="이름"
              sortKey="name"
              currentSort={currentSort}
              currentDir={currentDir}
              onSort={onSort}
              className="px-4 py-2"
            />
            <SortableTh
              label="시작일"
              sortKey="start_date"
              currentSort={currentSort}
              currentDir={currentDir}
              onSort={onSort}
              className="px-4 py-2"
            />
            <SortableTh
              label="총수익률"
              sortKey="final_return"
              currentSort={currentSort}
              currentDir={currentDir}
              onSort={onSort}
              className="px-4 py-2 text-right"
            />
            <TableHead className="text-right">샤프</TableHead>
            <TableHead className="text-right">MDD</TableHead>
            <SortableTh
              label="생성일"
              sortKey="created_at"
              currentSort={currentSort}
              currentDir={currentDir}
              onSort={onSort}
              className="px-4 py-2"
            />
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
              <TableCell className="text-neutral-400 text-xs">
                {r.created_at
                  ? new Date(r.created_at * 1000).toISOString().slice(0, 10)
                  : "-"}
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
