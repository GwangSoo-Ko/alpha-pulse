import Link from "next/link"
import { signalStyle } from "@/lib/market-labels"

export type BriefingSummary = {
  date: string
  score: number
  signal: string
  has_synthesis: boolean
  has_commentary: boolean
  created_at: number
}

function formatDate(yyyymmdd: string): string {
  return `${yyyymmdd.slice(0, 4)}-${yyyymmdd.slice(4, 6)}-${yyyymmdd.slice(6)}`
}

export function BriefingSummaryRow({ item }: { item: BriefingSummary }) {
  const style = signalStyle(item.signal)
  const sign = item.score >= 0 ? "+" : ""
  return (
    <tr className="border-t border-neutral-800 hover:bg-neutral-900">
      <td className="px-3 py-2">
        <Link
          href={`/briefings/${item.date}`}
          className="text-blue-400 hover:underline font-mono"
        >
          {formatDate(item.date)}
        </Link>
      </td>
      <td className="px-3 py-2 text-sm font-mono tabular-nums">
        {sign}{item.score.toFixed(1)}
      </td>
      <td className="px-3 py-2">
        <span className={`inline-block px-2 py-0.5 rounded-full text-xs ${style.badge}`}>
          {style.label}
        </span>
      </td>
      <td className="px-3 py-2 text-sm">
        {item.has_synthesis ? "✓" : "✗"}
      </td>
    </tr>
  )
}
