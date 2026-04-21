"use client"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"

export function NoPulseSnapshot({ onRun }: { onRun?: () => void }) {
  return (
    <Card className="p-8 text-center space-y-4">
      <h3 className="text-lg font-semibold">Pulse 이력이 없습니다</h3>
      <p className="text-sm text-neutral-400">
        아직 K-Market Pulse 가 계산된 적이 없습니다.<br />
        Daily briefing 을 실행하거나 지금 바로 계산해보세요.
      </p>
      <div className="flex justify-center gap-2">
        {onRun && <Button onClick={onRun}>지금 실행</Button>}
      </div>
      <p className="text-xs text-neutral-500">
        CLI: <code className="px-1 bg-neutral-800 rounded">ap market pulse</code> 또는 <code className="px-1 bg-neutral-800 rounded">ap briefing</code>
      </p>
    </Card>
  )
}
