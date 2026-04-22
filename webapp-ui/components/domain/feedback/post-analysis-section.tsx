"use client"
import { ReportMarkdownView } from "@/components/domain/content/report-markdown-view"

export function PostAnalysisSection({
  postAnalysis,
  blindSpots,
}: {
  postAnalysis: string | null
  blindSpots: string | null
}) {
  const hasAny = !!(postAnalysis || blindSpots)
  if (!hasAny) {
    return (
      <section className="space-y-2">
        <h2 className="text-lg font-semibold">사후 분석</h2>
        <p className="text-sm text-neutral-500">아직 생성되지 않음</p>
      </section>
    )
  }
  return (
    <section className="space-y-4">
      <h2 className="text-lg font-semibold">사후 분석</h2>
      {postAnalysis && (
        <div className="space-y-1">
          <h3 className="text-sm font-semibold text-neutral-300">종합</h3>
          <ReportMarkdownView body={postAnalysis} />
        </div>
      )}
      {blindSpots && (
        <div className="space-y-1">
          <h3 className="text-sm font-semibold text-neutral-300">사각지대</h3>
          <ReportMarkdownView body={blindSpots} />
        </div>
      )}
    </section>
  )
}
