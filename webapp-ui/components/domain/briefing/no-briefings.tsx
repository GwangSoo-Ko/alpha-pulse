"use client"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"

export function NoBriefings({ onRun }: { onRun?: () => void }) {
  return (
    <Card className="p-8 text-center space-y-4">
      <h3 className="text-lg font-semibold">브리핑이 없습니다</h3>
      <p className="text-sm text-neutral-400">
        아직 저장된 브리핑이 없습니다. 지금 바로 실행하거나
        <code className="px-1 mx-1 bg-neutral-800 rounded">ap briefing</code>
        CLI 로 생성할 수 있습니다.
      </p>
      {onRun && (
        <div className="flex justify-center">
          <Button onClick={onRun}>지금 실행</Button>
        </div>
      )}
      <p className="text-xs text-neutral-500">
        Daemon: <code className="px-1 bg-neutral-800 rounded">ap briefing --daemon</code>
      </p>
    </Card>
  )
}
