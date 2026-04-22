"use client"
import { ReportMarkdownView } from "@/components/domain/content/report-markdown-view"

export function BriefingPostAnalysisSection({
  postAnalysis,
}: {
  postAnalysis: Record<string, unknown> | null
}) {
  if (!postAnalysis) {
    return (
      <section className="space-y-2">
        <h2 className="text-lg font-semibold">사후 분석</h2>
        <p className="text-sm text-neutral-500">생성되지 않음</p>
      </section>
    )
  }
  const seniorSynthesis = typeof postAnalysis.senior_synthesis === "string"
    ? postAnalysis.senior_synthesis : ""
  const blindSpots = typeof postAnalysis.blind_spots === "string"
    ? postAnalysis.blind_spots : ""

  return (
    <section className="space-y-3">
      <h2 className="text-lg font-semibold">사후 분석</h2>
      {seniorSynthesis && (
        <div className="space-y-1">
          <h3 className="text-sm font-semibold text-neutral-300">종합</h3>
          <ReportMarkdownView body={seniorSynthesis} />
        </div>
      )}
      {blindSpots && (
        <div className="space-y-1">
          <h3 className="text-sm font-semibold text-neutral-300">사각지대</h3>
          <ReportMarkdownView body={blindSpots} />
        </div>
      )}
      {!seniorSynthesis && !blindSpots && (
        <p className="text-sm text-neutral-500">내용 없음</p>
      )}
    </section>
  )
}
