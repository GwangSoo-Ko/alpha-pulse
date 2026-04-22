"use client"
import { ReportMarkdownView } from "@/components/domain/content/report-markdown-view"

export function BriefingSynthesisSection({ synthesis }: { synthesis: string | null }) {
  return (
    <section className="space-y-2">
      <h2 className="text-lg font-semibold">종합 판단</h2>
      {synthesis ? (
        <ReportMarkdownView body={synthesis} />
      ) : (
        <p className="text-sm text-neutral-500">생성되지 않음</p>
      )}
    </section>
  )
}
