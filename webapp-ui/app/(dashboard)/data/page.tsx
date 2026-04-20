import { cookies } from "next/headers"
import { apiFetch } from "@/lib/api-client"
import { StatusTable } from "@/components/domain/data/status-table"
import { GapDetector } from "@/components/domain/data/gap-detector"

export const dynamic = "force-dynamic"

export default async function DataPage() {
  const cookieStore = await cookies()
  const h = {
    cookie: cookieStore
      .getAll()
      .map((c) => `${c.name}=${c.value}`)
      .join("; "),
  }
  const data = await apiFetch<{
    tables: {
      name: string
      row_count: number
      latest_date: string | null
      distinct_codes: number
    }[]
    gaps: { code: string; last_date: string }[]
  }>("/api/v1/data/status", { headers: h, cache: "no-store" })
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">데이터 수집 현황</h1>
      <StatusTable tables={data.tables} />
      <GapDetector gaps={data.gaps} />
    </div>
  )
}
