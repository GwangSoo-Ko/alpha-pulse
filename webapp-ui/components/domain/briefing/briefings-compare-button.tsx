"use client"
import Link from "next/link"
import { Button } from "@/components/ui/button"

export function BriefingsCompareButton({ selected }: { selected: string[] }) {
  if (selected.length !== 2) {
    return (
      <Button size="sm" variant="outline" disabled>
        비교하기 {selected.length > 0 && `(${selected.length}/2)`}
      </Button>
    )
  }
  const [a, b] = [...selected].sort()
  return (
    <Link href={`/briefings/compare?a=${a}&b=${b}`}>
      <Button size="sm" variant="default">비교하기</Button>
    </Link>
  )
}
