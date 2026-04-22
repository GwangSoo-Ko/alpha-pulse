import Link from "next/link"
import { cookies } from "next/headers"
import { notFound } from "next/navigation"
import { ApiError, apiFetch } from "@/lib/api-client"
import { BriefingHeroCard, type BriefingDetail } from "@/components/domain/briefing/briefing-hero-card"
import { BriefingSynthesisSection } from "@/components/domain/briefing/briefing-synthesis-section"
import { BriefingCommentarySection } from "@/components/domain/briefing/briefing-commentary-section"
import { BriefingNewsSection } from "@/components/domain/briefing/briefing-news-section"
import { BriefingPostAnalysisSection } from "@/components/domain/briefing/briefing-post-analysis-section"
import { BriefingFeedbackSection } from "@/components/domain/briefing/briefing-feedback-section"
import { BriefingRawMessages } from "@/components/domain/briefing/briefing-raw-messages"
import { Button } from "@/components/ui/button"

export const dynamic = "force-dynamic"

type Props = { params: Promise<{ date: string }> }

export default async function BriefingDetailPage({ params }: Props) {
  const { date } = await params
  const cookieStore = await cookies()
  const h = {
    cookie: cookieStore.getAll().map((c) => `${c.name}=${c.value}`).join("; "),
  }

  try {
    const detail = await apiFetch<BriefingDetail>(
      `/api/v1/briefings/${date}`,
      { headers: h, cache: "no-store" },
    )
    return (
      <div className="space-y-6">
        <Link href="/briefings">
          <Button variant="outline" size="sm">← 브리핑 목록으로</Button>
        </Link>
        <BriefingHeroCard detail={detail} />
        <BriefingSynthesisSection synthesis={detail.synthesis} />
        <BriefingCommentarySection commentary={detail.commentary} />
        <BriefingNewsSection news={detail.news} />
        <BriefingPostAnalysisSection postAnalysis={detail.post_analysis} />
        <BriefingFeedbackSection
          feedbackContext={detail.feedback_context}
          dailyResultMsg={detail.daily_result_msg}
        />
        <BriefingRawMessages
          quantMsg={detail.quant_msg}
          synthMsg={detail.synth_msg}
        />
      </div>
    )
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound()
    throw e
  }
}
