"use client"

export function NewsSummarySection({
  newsSummary,
}: {
  newsSummary: string | null
}) {
  if (!newsSummary) return null
  return (
    <section className="space-y-2">
      <h2 className="text-lg font-semibold">장 후 뉴스 요약</h2>
      <pre className="text-sm text-neutral-300 whitespace-pre-wrap rounded border border-neutral-800 bg-neutral-900 p-3">
        {newsSummary}
      </pre>
    </section>
  )
}
