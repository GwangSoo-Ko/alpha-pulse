"use client"
import Link from "next/link"
import { useRouter, useSearchParams } from "next/navigation"
import { ReportSummaryRow, type ReportSummary } from "./report-summary-row"
import { Button } from "@/components/ui/button"
import { ExportButton } from "@/components/ui/export-button"
import { SortableTh } from "@/components/ui/sortable-th"

type ListData = {
  items: ReportSummary[]
  page: number
  size: number
  total: number
}

type SortKey = "analyzed_at" | "published" | "title" | "category"

function pageHref(sp: URLSearchParams, page: number): string {
  const next = new URLSearchParams(sp)
  if (page > 1) next.set("page", String(page))
  else next.delete("page")
  return `/content?${next}`
}

export function ReportsTable({ data }: { data: ListData }) {
  const router = useRouter()
  const sp = useSearchParams()
  const spParams = new URLSearchParams(sp?.toString() ?? "")
  const totalPages = Math.max(1, Math.ceil(data.total / data.size))

  const rawSort = sp?.get("sort") ?? "newest"
  // "newest" / "oldest" 는 analyzed_at 매핑
  const effectiveSort: SortKey = (
    rawSort === "newest" || rawSort === "oldest" ? "analyzed_at" : rawSort
  ) as SortKey
  const currentDir = (sp?.get("dir") ?? "desc") as "asc" | "desc"

  function onSort(key: SortKey) {
    const next = new URLSearchParams(sp?.toString() ?? "")
    if (effectiveSort === key) {
      next.set("dir", currentDir === "asc" ? "desc" : "asc")
    } else {
      next.set("sort", key)
      // 텍스트 컬럼 asc 기본, 날짜는 desc
      next.set("dir", key === "title" || key === "category" ? "asc" : "desc")
    }
    next.delete("page")
    router.push(`/content?${next}`)
  }

  const exportQs = new URLSearchParams(sp?.toString() ?? "")
  exportQs.delete("page")
  const exportHref = `/api/v1/content/reports/export?${exportQs}`

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-sm text-neutral-400">
          전체 {data.total}건 · 페이지 {data.page}/{totalPages}
        </p>
        <ExportButton href={exportHref} />
      </div>
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="text-left text-xs text-neutral-400">
            <SortableTh
              label="제목"
              sortKey="title"
              currentSort={effectiveSort}
              currentDir={currentDir}
              onSort={onSort}
              className="px-3 py-2"
            />
            <SortableTh
              label="카테고리"
              sortKey="category"
              currentSort={effectiveSort}
              currentDir={currentDir}
              onSort={onSort}
              className="px-3 py-2"
            />
            <SortableTh
              label="발행일"
              sortKey="published"
              currentSort={effectiveSort}
              currentDir={currentDir}
              onSort={onSort}
              className="px-3 py-2"
            />
            <SortableTh
              label="분석시각"
              sortKey="analyzed_at"
              currentSort={effectiveSort}
              currentDir={currentDir}
              onSort={onSort}
              className="px-3 py-2"
            />
          </tr>
        </thead>
        <tbody>
          {data.items.map((i) => (
            <ReportSummaryRow key={i.filename} item={i} />
          ))}
        </tbody>
      </table>
      {totalPages > 1 && (
        <div className="flex justify-center gap-1">
          {data.page > 1 ? (
            <Link href={pageHref(spParams, data.page - 1)}>
              <Button size="sm" variant="outline">← 이전</Button>
            </Link>
          ) : (
            <Button size="sm" variant="outline" disabled>← 이전</Button>
          )}
          <span className="px-3 py-1 text-sm">{data.page} / {totalPages}</span>
          {data.page < totalPages ? (
            <Link href={pageHref(spParams, data.page + 1)}>
              <Button size="sm" variant="outline">다음 →</Button>
            </Link>
          ) : (
            <Button size="sm" variant="outline" disabled>다음 →</Button>
          )}
        </div>
      )}
    </div>
  )
}
