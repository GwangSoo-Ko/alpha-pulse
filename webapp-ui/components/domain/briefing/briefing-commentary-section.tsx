"use client"
import { ReportMarkdownView } from "@/components/domain/content/report-markdown-view"

export function BriefingCommentarySection({ commentary }: { commentary: string | null }) {
  return (
    <section className="space-y-2">
      <h2 className="text-lg font-semibold">AI 해설</h2>
      {commentary ? (
        <ReportMarkdownView body={commentary} />
      ) : (
        <p className="text-sm text-neutral-500">생성되지 않음</p>
      )}
    </section>
  )
}
