import { cookies } from "next/headers"
import { apiFetch } from "@/lib/api-client"
import { StressTable } from "@/components/domain/risk/stress-table"
import { CustomStressForm } from "@/components/domain/risk/custom-stress-form"

export const dynamic = "force-dynamic"

type Props = { searchParams: Promise<{ mode?: string }> }

export default async function StressPage({ searchParams }: Props) {
  const sp = await searchParams
  const mode = sp.mode || "paper"
  const cookieStore = await cookies()
  const h = { cookie: cookieStore.getAll().map((c) => `${c.name}=${c.value}`).join("; ") }
  const data = await apiFetch<{
    stress: Record<string, number>
  } | null>(`/api/v1/risk/stress?mode=${mode}`, {
    headers: h, cache: "no-store",
  })
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">스트레스 테스트 ({mode})</h1>
      <StressTable scenarios={data?.stress ?? {}} />
      <CustomStressForm mode={mode} />
    </div>
  )
}
