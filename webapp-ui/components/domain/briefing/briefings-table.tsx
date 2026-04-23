"use client"
import Link from "next/link"
import { useState } from "react"
import { useSearchParams } from "next/navigation"
import { signalStyle } from "@/lib/market-labels"
import { Button } from "@/components/ui/button"
import { BriefingsCompareButton } from "./briefings-compare-button"
import type { BriefingSummary } from "./briefing-summary-row"

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

function formatDate(yyyymmdd: string): string {
  return `${yyyymmdd.slice(0, 4)}-${yyyymmdd.slice(4, 6)}-${yyyymmdd.slice(6)}`
}

export function BriefingsTable({ data }: { data: ListData }) {
  const sp = useSearchParams()
  const spParams = new URLSearchParams(sp?.toString() ?? "")
  const totalPages = Math.max(1, Math.ceil(data.total / data.size))
  const [selected, setSelected] = useState<string[]>([])

  function toggle(date: string) {
    setSelected((prev) => {
      if (prev.includes(date)) {
        return prev.filter((d) => d !== date)
      }
      if (prev.length >= 2) {
        // FIFO: 가장 오래 선택한 것 제거
        return [...prev.slice(1), date]
      }
      return [...prev, date]
    })
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-sm text-neutral-400">
          전체 {data.total}건 · 페이지 {data.page}/{totalPages}
        </p>
        <BriefingsCompareButton selected={selected} />
      </div>
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="text-left text-xs text-neutral-400">
            <th scope="col" className="px-3 py-2 w-8">
              <span className="sr-only">선택</span>
            </th>
            <th scope="col" className="px-3 py-2">날짜</th>
            <th scope="col" className="px-3 py-2">점수</th>
            <th scope="col" className="px-3 py-2">시그널</th>
            <th scope="col" className="px-3 py-2">종합</th>
          </tr>
        </thead>
        <tbody>
          {data.items.map((i) => {
            const style = signalStyle(i.signal)
            const sign = i.score >= 0 ? "+" : ""
            const checked = selected.includes(i.date)
            return (
              <tr key={i.date} className="border-t border-neutral-800 hover:bg-neutral-900">
                <td className="px-3 py-2">
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => toggle(i.date)}
                    aria-label={`${i.date} 선택`}
                    className="cursor-pointer"
                  />
                </td>
                <td className="px-3 py-2">
                  <Link
                    href={`/briefings/${i.date}`}
                    className="text-blue-400 hover:underline font-mono"
                  >
                    {formatDate(i.date)}
                  </Link>
                </td>
                <td className="px-3 py-2 text-sm font-mono tabular-nums">
                  {sign}{i.score.toFixed(1)}
                </td>
                <td className="px-3 py-2">
                  <span className={`inline-block px-2 py-0.5 rounded-full text-xs ${style.badge}`}>
                    {style.label}
                  </span>
                </td>
                <td className="px-3 py-2 text-sm">
                  {i.has_synthesis ? "✓" : "✗"}
                </td>
              </tr>
            )
          })}
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
