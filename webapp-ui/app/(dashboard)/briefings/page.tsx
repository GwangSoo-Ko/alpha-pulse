import { cookies } from "next/headers"
import { apiFetch } from "@/lib/api-client"
import { BriefingsTable } from "@/components/domain/briefing/briefings-table"
import { NoBriefings } from "@/components/domain/briefing/no-briefings"
import { RunBriefingButton } from "@/components/domain/briefing/run-briefing-button"
import type { BriefingSummary } from "@/components/domain/briefing/briefing-summary-row"

export const dynamic = "force-dynamic"

type Props = { searchParams: Promise<{ page?: string }> }

export default async function BriefingsPage({ searchParams }: Props) {
  const sp = await searchParams
  const page = Number(sp.page || 1)
  const cookieStore = await cookies()
  const h = {
    cookie: cookieStore.getAll().map((c) => `${c.name}=${c.value}`).join("; "),
  }
  const data = await apiFetch<{
    items: BriefingSummary[]
    page: number
    size: number
    total: number
  }>(`/api/v1/briefings?page=${page}&size=20`, { headers: h, cache: "no-store" })

  // "오늘 이미 저장된 브리핑이 있는지" — RunConfirmModal 트리거 용
  const latestToday = data.items.find((i) => {
    const now = new Date()
    const ymd = `${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, "0")}${String(now.getDate()).padStart(2, "0")}`
    return i.date === ymd
  }) ?? null

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-semibold">브리핑</h1>
        <RunBriefingButton latestToday={latestToday} />
      </div>
      {data.total === 0 ? (
        <NoBriefings />
      ) : (
        <BriefingsTable data={data} />
      )}
    </div>
  )
}
