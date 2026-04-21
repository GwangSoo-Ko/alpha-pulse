import Link from "next/link"

export type ReportSummary = {
  filename: string
  title: string
  category: string
  published: string
  analyzed_at: string
  source: string
  source_tag: string
}

export function ReportSummaryRow({ item }: { item: ReportSummary }) {
  return (
    <tr className="border-t border-neutral-800 hover:bg-neutral-900">
      <td className="px-3 py-2">
        <Link
          href={`/content/reports/${encodeURIComponent(item.filename)}`}
          className="text-blue-400 hover:underline"
        >
          {item.title}
        </Link>
      </td>
      <td className="px-3 py-2">
        <span className="inline-block rounded bg-neutral-800 px-2 py-0.5 text-xs">
          {item.category}
        </span>
      </td>
      <td className="px-3 py-2 text-sm text-neutral-400">{item.published || "-"}</td>
      <td className="px-3 py-2 text-sm text-neutral-400">{item.analyzed_at || "-"}</td>
    </tr>
  )
}
