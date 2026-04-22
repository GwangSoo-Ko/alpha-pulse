"use client"
import { Card } from "@/components/ui/card"

export function NoFeedback() {
  return (
    <Card className="p-8 text-center space-y-4">
      <h3 className="text-lg font-semibold">평가된 시그널이 없습니다</h3>
      <p className="text-sm text-neutral-400">
        브리핑 발행 이후 시장 결과가 채워지기까지 최소 1영업일 필요합니다.<br />
        매일 브리핑 실행 시 자동으로 피드백이 축적됩니다.
      </p>
      <p className="text-xs text-neutral-500">
        수동 평가: <code className="px-1 bg-neutral-800 rounded">ap feedback evaluate</code>
      </p>
    </Card>
  )
}
