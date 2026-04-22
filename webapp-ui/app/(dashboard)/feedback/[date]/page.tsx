import Link from "next/link"
import { cookies } from "next/headers"
import { notFound } from "next/navigation"
import { ApiError, apiFetch } from "@/lib/api-client"
import {
  FeedbackDetailCard,
  type FeedbackDetail,
} from "@/components/domain/feedback/feedback-detail-card"
import { NewsSummarySection } from "@/components/domain/feedback/news-summary-section"
import { PostAnalysisSection } from "@/components/domain/feedback/post-analysis-section"
import { Button } from "@/components/ui/button"

export const dynamic = "force-dynamic"

type Props = { params: Promise<{ date: string }> }

export default async function FeedbackDetailPage({ params }: Props) {
  const { date } = await params
  const cookieStore = await cookies()
  const h = {
    cookie: cookieStore.getAll().map((c) => `${c.name}=${c.value}`).join("; "),
  }

  try {
    const detail = await apiFetch<FeedbackDetail>(
      `/api/v1/feedback/${date}`,
      { headers: h, cache: "no-store" },
    )
    return (
      <div className="space-y-6">
        <Link href="/feedback">
          <Button variant="outline" size="sm">← 피드백 대시보드로</Button>
        </Link>
        <FeedbackDetailCard detail={detail} />
        <NewsSummarySection newsSummary={detail.news_summary} />
        <PostAnalysisSection
          postAnalysis={detail.post_analysis}
          blindSpots={detail.blind_spots}
        />
        <div className="pt-4 border-t border-neutral-800">
          <Link href={`/briefings/${date}`}>
            <Button variant="outline" size="sm">
              → 이 날짜 브리핑 전체 보기
            </Button>
          </Link>
        </div>
      </div>
    )
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound()
    throw e
  }
}
