import Link from "next/link"
import { cookies } from "next/headers"
import { notFound, redirect } from "next/navigation"
import { ApiError, apiFetch } from "@/lib/api-client"
import { Button } from "@/components/ui/button"
import { BriefingCompareHero } from "@/components/domain/briefing/briefing-compare-hero"
import { IndicatorDiffTable } from "@/components/domain/briefing/indicator-diff-table"
import { TextCompareSection } from "@/components/domain/briefing/text-compare-section"

export const dynamic = "force-dynamic"

type BriefingDetail = {
  date: string
  created_at: number
  pulse_result: { score?: number; signal?: string; indicator_scores?: Record<string, unknown> } & Record<string, unknown>
  daily_result_msg: string
  commentary: string | null
}

type Props = { searchParams: Promise<{ a?: string; b?: string }> }

const DATE_RE = /^\d{8}$/

async function load(date: string, cookieHeader: string): Promise<BriefingDetail | null> {
  try {
    return await apiFetch<BriefingDetail>(`/api/v1/briefings/${date}`, {
      headers: { cookie: cookieHeader }, cache: "no-store",
    })
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) return null
    throw e
  }
}

function formatDateShort(yyyymmdd: string): string {
  return `${yyyymmdd.slice(4, 6)}-${yyyymmdd.slice(6)}`
}

export default async function BriefingComparePage({ searchParams }: Props) {
  const { a, b } = await searchParams
  if (!a || !b) redirect("/briefings")
  if (!DATE_RE.test(a) || !DATE_RE.test(b)) notFound()
  if (a === b) redirect(`/briefings/${a}`)

  const cookieStore = await cookies()
  const cookieHeader = cookieStore.getAll().map((c) => `${c.name}=${c.value}`).join("; ")

  const [aDetail, bDetail] = await Promise.all([load(a, cookieHeader), load(b, cookieHeader)])

  if (!aDetail && !bDetail) {
    return (
      <div className="space-y-4">
        <Link href="/briefings">
          <Button variant="outline" size="sm">← 목록으로</Button>
        </Link>
        <h1 className="text-2xl font-semibold">브리핑 비교</h1>
        <p className="text-sm text-neutral-500">두 날짜 모두 브리핑이 없습니다.</p>
      </div>
    )
  }

  const aItem = aDetail
    ? { date: a, score: Number(aDetail.pulse_result?.score ?? 0), signal: String(aDetail.pulse_result?.signal ?? "neutral") }
    : null
  const bItem = bDetail
    ? { date: b, score: Number(bDetail.pulse_result?.score ?? 0), signal: String(bDetail.pulse_result?.signal ?? "neutral") }
    : null

  const scoresA = (aDetail?.pulse_result?.indicator_scores ?? {}) as Record<string, unknown>
  const scoresB = (bDetail?.pulse_result?.indicator_scores ?? {}) as Record<string, unknown>

  const aText = aDetail
    ? { date: a, daily_result_msg: aDetail.daily_result_msg ?? "", commentary: aDetail.commentary }
    : null
  const bText = bDetail
    ? { date: b, daily_result_msg: bDetail.daily_result_msg ?? "", commentary: bDetail.commentary }
    : null

  return (
    <div className="space-y-6">
      <Link href="/briefings">
        <Button variant="outline" size="sm">← 목록으로</Button>
      </Link>
      <h1 className="text-2xl font-semibold">브리핑 비교</h1>
      <BriefingCompareHero a={aItem} b={bItem} />
      <IndicatorDiffTable
        scoresA={scoresA}
        scoresB={scoresB}
        dateALabel={formatDateShort(a)}
        dateBLabel={formatDateShort(b)}
      />
      <TextCompareSection a={aText} b={bText} />
    </div>
  )
}
