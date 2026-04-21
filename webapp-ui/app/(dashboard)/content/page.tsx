import { cookies } from "next/headers"
import { apiFetch } from "@/lib/api-client"
import { ReportsFilterBar } from "@/components/domain/content/reports-filter-bar"
import { ReportsTable } from "@/components/domain/content/reports-table"
import { NoReports } from "@/components/domain/content/no-reports"
import { RunContentButton } from "@/components/domain/content/run-content-button"
import type { ReportSummary } from "@/components/domain/content/report-summary-row"

export const dynamic = "force-dynamic"

type Props = {
  searchParams: Promise<{
    page?: string
    category?: string | string[]
    from?: string
    to?: string
    q?: string
    sort?: string
  }>
}

export default async function ContentPage({ searchParams }: Props) {
  const sp = await searchParams
  const query = new URLSearchParams()
  if (sp.page) query.set("page", sp.page)
  const cats = Array.isArray(sp.category)
    ? sp.category
    : sp.category ? [sp.category] : []
  cats.forEach((c) => query.append("category", c))
  if (sp.from) query.set("from", sp.from)
  if (sp.to) query.set("to", sp.to)
  if (sp.q) query.set("q", sp.q)
  if (sp.sort) query.set("sort", sp.sort)

  const cookieStore = await cookies()
  const h = {
    cookie: cookieStore.getAll().map((c) => `${c.name}=${c.value}`).join("; "),
  }

  const data = await apiFetch<{
    items: ReportSummary[]
    page: number
    size: number
    total: number
    categories: string[]
  }>(`/api/v1/content/reports?${query}`, { headers: h, cache: "no-store" })

  const hasFilters = cats.length > 0 || !!sp.from || !!sp.to || !!sp.q

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-semibold">콘텐츠</h1>
        <RunContentButton />
      </div>
      <ReportsFilterBar categories={data.categories} />
      {data.total === 0 ? (
        <NoReports mode={hasFilters ? "filtered" : "empty"} />
      ) : (
        <ReportsTable data={data} />
      )}
    </div>
  )
}
