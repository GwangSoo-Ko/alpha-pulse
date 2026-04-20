import Link from "next/link"
import { cookies } from "next/headers"
import { apiFetch } from "@/lib/api-client"
import { Button } from "@/components/ui/button"
import { RunsTable } from "@/components/domain/backtest/runs-table"
import type { RunList } from "@/lib/types"

export const dynamic = "force-dynamic" // 사용자별 데이터 — 캐시 금지

type Props = { searchParams: Promise<{ page?: string; name?: string }> }

export default async function BacktestListPage({ searchParams }: Props) {
  const sp = await searchParams
  const page = Number(sp.page ?? 1)
  const name = sp.name ?? ""

  const cookieStore = await cookies()
  const cookieHeader = cookieStore
    .getAll()
    .map((c) => `${c.name}=${c.value}`)
    .join("; ")
  const runs = await apiFetch<RunList>("/api/v1/backtest/runs", {
    headers: { cookie: cookieHeader },
    searchParams: { page: String(page), size: "20", name: name || undefined },
    cache: "no-store",
  })

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">백테스트 결과</h1>
        <Link href="/backtest/new">
          <Button>새 백테스트</Button>
        </Link>
      </div>
      <RunsTable data={runs} currentPage={page} currentName={name} />
    </div>
  )
}
