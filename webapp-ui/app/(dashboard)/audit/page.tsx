import { cookies } from "next/headers"
import { apiFetch } from "@/lib/api-client"
import { AuditTable } from "@/components/domain/audit/audit-table"

export const dynamic = "force-dynamic"

type Props = { searchParams: Promise<{ page?: string; action_prefix?: string; actor?: string }> }

export default async function AuditPage({ searchParams }: Props) {
  const sp = await searchParams
  const page = Number(sp.page || 1)
  const cookieStore = await cookies()
  const h = { cookie: cookieStore.getAll().map((c) => `${c.name}=${c.value}`).join("; ") }
  const qs = new URLSearchParams({ page: String(page), size: "50" })
  if (sp.action_prefix) qs.set("action_prefix", sp.action_prefix)
  if (sp.actor) qs.set("actor", sp.actor)
  const data = await apiFetch<{
    items: { id: number; timestamp: number; event_type: string; component: string; data: Record<string, unknown>; mode: string }[]
    page: number; size: number; total: number
  }>(`/api/v1/audit/events?${qs.toString()}`, { headers: h, cache: "no-store" })
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">감사 로그</h1>
      <AuditTable
        data={data} currentPage={page}
        currentActionPrefix={sp.action_prefix ?? ""}
        currentActor={sp.actor ?? ""}
      />
    </div>
  )
}
