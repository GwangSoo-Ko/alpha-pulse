"use client"

export function BriefingFeedbackSection({
  feedbackContext,
  dailyResultMsg,
}: {
  feedbackContext: Record<string, unknown> | string | null
  dailyResultMsg: string
}) {
  if (!feedbackContext && !dailyResultMsg) {
    return (
      <section className="space-y-2">
        <h2 className="text-lg font-semibold">피드백 컨텍스트</h2>
        <p className="text-sm text-neutral-500">피드백 데이터 없음</p>
      </section>
    )
  }
  const contextText = typeof feedbackContext === "string"
    ? feedbackContext
    : feedbackContext
      ? JSON.stringify(feedbackContext, null, 2)
      : null
  return (
    <section className="space-y-2">
      <h2 className="text-lg font-semibold">피드백 컨텍스트</h2>
      {dailyResultMsg && (
        <pre className="text-xs text-neutral-300 whitespace-pre-wrap rounded border border-neutral-800 bg-neutral-900 p-3">
          {dailyResultMsg}
        </pre>
      )}
      {contextText && (
        <pre className="text-xs text-neutral-400 whitespace-pre-wrap rounded border border-neutral-800 bg-neutral-900 p-3">
          {contextText}
        </pre>
      )}
    </section>
  )
}
