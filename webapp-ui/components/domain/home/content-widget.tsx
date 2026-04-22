"use client"
import Link from "next/link"
import { Card } from "@/components/ui/card"

export type ContentItem = { date: string; filename: string; title: string }
export type ContentData = { recent: ContentItem[] }

export function ContentWidget({ data }: { data: ContentData }) {
  return (
    <Link href="/content/reports" className="block">
      <Card className="p-4 min-h-[160px] hover:border-neutral-600 transition">
        <div className="text-xs text-neutral-400 uppercase tracking-wide mb-2">Content 최근</div>
        {data.recent.length === 0 ? (
          <p className="text-sm text-neutral-500">신규 리포트 없음</p>
        ) : (
          <ul className="space-y-2">
            {data.recent.map((r) => (
              <li key={r.filename} className="text-sm">
                <div className="text-neutral-200 truncate" title={r.title}>{r.title}</div>
                <div className="text-[10px] text-neutral-500">{r.date}</div>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </Link>
  )
}
