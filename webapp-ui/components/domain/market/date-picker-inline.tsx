"use client"
import Link from "next/link"
import { Button } from "@/components/ui/button"

function formatDate(yyyymmdd: string): string {
  return `${yyyymmdd.slice(0, 4)}-${yyyymmdd.slice(4, 6)}-${yyyymmdd.slice(6)}`
}

export function DatePickerInline({
  currentDate,
  availableDates,
}: {
  currentDate: string
  availableDates: string[]  // 오름차순 YYYYMMDD
}) {
  const idx = availableDates.indexOf(currentDate)
  const prev = idx > 0 ? availableDates[idx - 1] : null
  const next = idx >= 0 && idx < availableDates.length - 1
    ? availableDates[idx + 1] : null

  return (
    <div className="flex items-center gap-2">
      {prev ? (
        <Link href={`/market/pulse/${prev}`}>
          <Button variant="outline" size="sm">← 이전</Button>
        </Link>
      ) : (
        <Button variant="outline" size="sm" disabled>← 이전</Button>
      )}
      <span className="text-lg font-mono px-3">{formatDate(currentDate)}</span>
      {next ? (
        <Link href={`/market/pulse/${next}`}>
          <Button variant="outline" size="sm">다음 →</Button>
        </Link>
      ) : (
        <Button variant="outline" size="sm" disabled>다음 →</Button>
      )}
      <Link href="/market/pulse">
        <Button variant="ghost" size="sm">최신으로</Button>
      </Link>
    </div>
  )
}
