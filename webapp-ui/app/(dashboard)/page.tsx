import { cookies } from "next/headers"
import { apiFetch } from "@/lib/api-client"
import { BriefingHeroPlus, type BriefingHero } from "@/components/domain/home/briefing-hero-plus"
import { MissingBriefingBanner } from "@/components/domain/home/missing-briefing-banner"
import { PulseWidget, type PulseData } from "@/components/domain/home/pulse-widget"
import { FeedbackWidget, type FeedbackData } from "@/components/domain/home/feedback-widget"
import { ContentWidget, type ContentData } from "@/components/domain/home/content-widget"
import { PortfolioWidget } from "@/components/domain/home/portfolio-widget"
import { RiskStatusWidget } from "@/components/domain/home/risk-status-widget"
import { DataHealthWidget } from "@/components/domain/home/data-health-widget"

export const dynamic = "force-dynamic"

type PortfolioSnapshot = {
  date: string
  cash: number
  total_value: number
  daily_return: number
  cumulative_return: number
  drawdown: number
  positions: { code: string; name: string; quantity: number; current_price: number }[]
}

type HomeData = {
  briefing: BriefingHero | null
  pulse: PulseData | null
  feedback: FeedbackData | null
  content: ContentData
  portfolio: PortfolioSnapshot | null
  portfolio_history: { date: string; total_value: number }[]
  risk: { report?: { alerts?: { level: string; message: string }[] } } | null
  data_status: {
    tables: { name: string; row_count: number; latest_date: string | null }[]
    gaps_count: number
  }
}

export default async function HomePage() {
  const cookieStore = await cookies()
  const h = { cookie: cookieStore.getAll().map((c) => `${c.name}=${c.value}`).join("; ") }
  const data = await apiFetch<HomeData>("/api/v1/dashboard/home", {
    headers: h, cache: "no-store",
  })
  const showBanner = !data.briefing || !data.briefing.is_today
  return (
    <div className="space-y-4">
      {showBanner && (
        <MissingBriefingBanner latestDate={data.briefing?.date ?? null} />
      )}
      <BriefingHeroPlus hero={data.briefing} />
      <div className="grid gap-4 grid-cols-1 md:grid-cols-2 lg:grid-cols-3">
        <PulseWidget data={data.pulse} />
        <FeedbackWidget data={data.feedback} />
        <ContentWidget data={data.content} />
        <PortfolioWidget portfolio={data.portfolio} history={data.portfolio_history} />
        <RiskStatusWidget risk={data.risk} />
        <DataHealthWidget status={data.data_status} />
      </div>
    </div>
  )
}
