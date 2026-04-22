"use client"
import { useRouter, useSearchParams } from "next/navigation"
import { Button } from "@/components/ui/button"

const OPTIONS = [30, 60, 90]

export function PeriodToggle({ current }: { current: number }) {
  const router = useRouter()
  const sp = useSearchParams()

  const pick = (days: number) => {
    const next = new URLSearchParams(sp?.toString() ?? "")
    next.set("days", String(days))
    next.delete("page")
    router.push(`/feedback?${next}`)
  }

  return (
    <div className="flex gap-1">
      {OPTIONS.map((d) => (
        <Button
          key={d} size="sm"
          variant={current === d ? "default" : "outline"}
          onClick={() => pick(d)}
        >
          {d}일
        </Button>
      ))}
    </div>
  )
}
