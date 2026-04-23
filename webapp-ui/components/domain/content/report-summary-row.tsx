import Link from "next/link"
import { Fragment } from "react"

export type ReportSummary = {
  filename: string
  title: string
  category: string
  published: string
  analyzed_at: string
  source: string
  source_tag: string
  highlight?: string | null
}

// Security: HTML is generated server-side by SQLite snippet() — only <mark> tags
// are inserted into trusted report text. XSS risk assessed acceptable (spec §4.5).
function HighlightSnippet({ html }: { html: string }) {
  return (
    <span
      className="[&_mark]:bg-yellow-700/40 [&_mark]:text-yellow-200 [&_mark]:rounded [&_mark]:px-0.5"
      dangerouslySetInnerHTML={{ __html: html }} // eslint-disable-line react/no-danger
    />
  )
}

export function ReportSummaryRow({ item }: { item: ReportSummary }) {
  return (
    <Fragment>
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
      {item.highlight ? (
        <tr>
          <td colSpan={4} className="px-3 pb-2 text-xs text-neutral-400">
            <HighlightSnippet html={item.highlight} />
          </td>
        </tr>
      ) : null}
    </Fragment>
  )
}
