"use client"
import Link from "next/link"
import { useSearchParams } from "next/navigation"
import { BriefingSummaryRow, type BriefingSummary } from "./briefing-summary-row"
import { Button } from "@/components/ui/button"

type ListData = {
  items: BriefingSummary[]
  page: number
  size: number
  total: number
}

function pageHref(sp: URLSearchParams, page: number): string {
  const next = new URLSearchParams(sp)
  if (page > 1) next.set("page", String(page))
  else next.delete("page")
  return `/briefings?${next}`
}

export function BriefingsTable({ data }: { data: ListData }) {
  const sp = useSearchParams()
  const spParams = new URLSearchParams(sp?.toString() ?? "")
  const totalPages = Math.max(1, Math.ceil(data.total / data.size))

  return (
    <div className="space-y-3">
      <p className="text-sm text-neutral-400">
        전체 {data.total}건 · 페이지 {data.page}/{totalPages}
      </p>
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="text-left text-xs text-neutral-400">
            <th className="px-3 py-2">날짜</th>
            <th className="px-3 py-2">점수</th>
            <th className="px-3 py-2">시그널</th>
            <th className="px-3 py-2">종합</th>
          </tr>
        </thead>
        <tbody>
          {data.items.map((i) => (
            <BriefingSummaryRow key={i.date} item={i} />
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
