"use client"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"

export function NoReports({
  mode,
  onRun,
}: {
  mode: "empty" | "filtered"
  onRun?: () => void
}) {
  if (mode === "filtered") {
    return (
      <Card className="p-8 text-center text-neutral-400">
        조건에 맞는 리포트가 없습니다.
      </Card>
    )
  }
  return (
    <Card className="p-8 text-center space-y-4">
      <h3 className="text-lg font-semibold">리포트가 없습니다</h3>
      <p className="text-sm text-neutral-400">
        아직 BlogPulse 수집이 실행된 적이 없거나 대상 카테고리 글이 없었습니다.<br />
        지금 바로 수집을 시작해보세요.
      </p>
      {onRun && (
        <div className="flex justify-center">
          <Button onClick={onRun}>지금 실행</Button>
        </div>
      )}
      <p className="text-xs text-neutral-500">
        CLI: <code className="px-1 bg-neutral-800 rounded">ap content monitor</code>
      </p>
    </Card>
  )
}
