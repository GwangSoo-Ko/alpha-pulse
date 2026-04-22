"use client"
import Link from "next/link"
import { useSearchParams } from "next/navigation"
import { Button } from "@/components/ui/button"
import { signalStyle } from "@/lib/market-labels"

export type SignalHistoryItem = {
  date: string
  score: number
  signal: string
  kospi_change_pct: number | null
  return_1d: number | null
  return_3d: number | null
  return_5d: number | null
  hit_1d: boolean | null
  hit_3d: boolean | null
  hit_5d: boolean | null
}

type ListData = {
  items: SignalHistoryItem[]
  page: number
  size: number
  total: number
}

function formatDate(yyyymmdd: string): string {
  return `${yyyymmdd.slice(0, 4)}-${yyyymmdd.slice(4, 6)}-${yyyymmdd.slice(6)}`
}

function formatPct(v: number | null): string {
  if (v === null) return "-"
  const sign = v >= 0 ? "+" : ""
  return `${sign}${v.toFixed(2)}%`
}

function hitIcon(hit: boolean | null): string {
  if (hit === null) return "-"
  return hit ? "✓" : "✗"
}

function hitClass(hit: boolean | null): string {
  if (hit === null) return "text-neutral-500"
  return hit ? "text-green-400" : "text-red-400"
}

function pageHref(sp: URLSearchParams, page: number): string {
  const next = new URLSearchParams(sp)
  if (page > 1) next.set("page", String(page))
  else next.delete("page")
  return `/feedback?${next}`
}

export function SignalHistoryTable({ data }: { data: ListData }) {
  const sp = useSearchParams()
  const spParams = new URLSearchParams(sp?.toString() ?? "")
  const totalPages = Math.max(1, Math.ceil(data.total / data.size))
  const sign = (v: number) => (v >= 0 ? "+" : "")

  return (
    <div className="space-y-3">
      <p className="text-sm text-neutral-400">
        전체 {data.total}건 · 페이지 {data.page}/{totalPages}
      </p>
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="text-left text-xs text-neutral-400">
            <th className="px-3 py-2">날짜</th>
            <th className="px-3 py-2">시그널</th>
            <th className="px-3 py-2">점수</th>
            <th className="px-3 py-2">KOSPI</th>
            <th className="px-3 py-2">1D</th>
            <th className="px-3 py-2">3D</th>
            <th className="px-3 py-2">5D</th>
            <th className="px-3 py-2">적중 1/3/5</th>
          </tr>
        </thead>
        <tbody>
          {data.items.map((i) => {
            const style = signalStyle(i.signal)
            return (
              <tr key={i.date} className="border-t border-neutral-800 hover:bg-neutral-900">
                <td className="px-3 py-2">
                  <Link
                    href={`/feedback/${i.date}`}
                    className="text-blue-400 hover:underline font-mono"
                  >
                    {formatDate(i.date)}
                  </Link>
                </td>
                <td className="px-3 py-2">
                  <span className={`inline-block px-2 py-0.5 rounded-full text-xs ${style.badge}`}>
                    {style.label}
                  </span>
                </td>
                <td className="px-3 py-2 font-mono tabular-nums">
                  {sign(i.score)}{i.score.toFixed(1)}
                </td>
                <td className="px-3 py-2 font-mono tabular-nums text-xs text-neutral-400">
                  {formatPct(i.kospi_change_pct)}
                </td>
                <td className="px-3 py-2 font-mono tabular-nums text-xs">
                  {formatPct(i.return_1d)}
                </td>
                <td className="px-3 py-2 font-mono tabular-nums text-xs">
                  {formatPct(i.return_3d)}
                </td>
                <td className="px-3 py-2 font-mono tabular-nums text-xs">
                  {formatPct(i.return_5d)}
                </td>
                <td className="px-3 py-2 text-xs">
                  <span className={hitClass(i.hit_1d)}>{hitIcon(i.hit_1d)}</span>
                  <span className="mx-1 text-neutral-600">/</span>
                  <span className={hitClass(i.hit_3d)}>{hitIcon(i.hit_3d)}</span>
                  <span className="mx-1 text-neutral-600">/</span>
                  <span className={hitClass(i.hit_5d)}>{hitIcon(i.hit_5d)}</span>
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
