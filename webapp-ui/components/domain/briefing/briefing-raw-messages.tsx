"use client"

export function BriefingRawMessages({
  quantMsg,
  synthMsg,
}: {
  quantMsg: string
  synthMsg: string
}) {
  return (
    <details className="rounded border border-neutral-800 bg-neutral-900 p-3">
      <summary className="text-sm cursor-pointer text-neutral-300">
        텔레그램 메시지 원문
      </summary>
      <div className="mt-3 space-y-3">
        {quantMsg && (
          <div className="space-y-1">
            <p className="text-xs text-neutral-500">정량 메시지</p>
            <pre className="text-xs text-neutral-300 whitespace-pre-wrap">{quantMsg}</pre>
          </div>
        )}
        {synthMsg && (
          <div className="space-y-1">
            <p className="text-xs text-neutral-500">종합 메시지</p>
            <pre className="text-xs text-neutral-300 whitespace-pre-wrap">{synthMsg}</pre>
          </div>
        )}
      </div>
    </details>
  )
}
