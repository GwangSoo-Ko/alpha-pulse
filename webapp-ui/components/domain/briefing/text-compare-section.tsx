"use client"
import { Card } from "@/components/ui/card"

type TextCompareItem = {
  date: string
  daily_result_msg: string
  commentary: string | null
} | null

function formatDate(yyyymmdd: string): string {
  if (yyyymmdd.length !== 8) return yyyymmdd
  return `${yyyymmdd.slice(0, 4)}-${yyyymmdd.slice(4, 6)}-${yyyymmdd.slice(6)}`
}

function Column({
  title, item,
}: {
  title: string
  item: TextCompareItem
}) {
  if (!item) {
    return (
      <Card className="p-4">
        <p className="text-xs text-neutral-500 mb-2">{title}</p>
        <p className="text-sm text-neutral-500">데이터 없음</p>
      </Card>
    )
  }
  return (
    <Card className="p-4 space-y-4">
      <p className="text-xs text-neutral-500">
        {title} · <span className="font-mono">{formatDate(item.date)}</span>
      </p>
      <section className="space-y-1">
        <p className="text-[11px] uppercase text-neutral-400 tracking-wide">
          daily_result_msg
        </p>
        {item.daily_result_msg ? (
          <pre className="text-xs text-neutral-300 whitespace-pre-wrap rounded border border-neutral-800 bg-neutral-900 p-3">
            {item.daily_result_msg}
          </pre>
        ) : (
          <p className="text-sm text-neutral-600">—</p>
        )}
      </section>
      <section className="space-y-1">
        <p className="text-[11px] uppercase text-neutral-400 tracking-wide">
          commentary
        </p>
        {item.commentary ? (
          <p className="text-sm text-neutral-300 whitespace-pre-wrap leading-relaxed">
            {item.commentary}
          </p>
        ) : (
          <p className="text-sm text-neutral-600">—</p>
        )}
      </section>
    </Card>
  )
}

export function TextCompareSection({
  a, b,
}: {
  a: TextCompareItem
  b: TextCompareItem
}) {
  return (
    <div className="grid gap-4 grid-cols-1 md:grid-cols-2">
      <Column title="A" item={a} />
      <Column title="B" item={b} />
    </div>
  )
}
