import Link from "next/link"
import { cookies } from "next/headers"
import { apiFetch } from "@/lib/api-client"
import { Button } from "@/components/ui/button"
import { RunsTable } from "@/components/domain/screening/runs-table"

export const dynamic = "force-dynamic"

type Props = { searchParams: Promise<{ page?: string }> }

export default async function ScreeningListPage({ searchParams }: Props) {
  const sp = await searchParams
  const page = Number(sp.page || 1)
  const cookieStore = await cookies()
  const h = { cookie: cookieStore.getAll().map((c) => `${c.name}=${c.value}`).join("; ") }
  const data = await apiFetch<{
    items: { run_id: string; name: string; market: string; strategy: string; top_n: number; created_at: number }[]
    page: number; size: number; total: number
  }>(`/api/v1/screening/runs?page=${page}&size=20`, {
    headers: h, cache: "no-store",
  })
  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-semibold">스크리닝 결과</h1>
        <Link href="/screening/new">
          <Button>새 스크리닝</Button>
        </Link>
      </div>
      <RunsTable data={data} currentPage={page} />
    </div>
  )
}
