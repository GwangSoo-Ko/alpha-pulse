"use client"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"

function formatTime(epochSeconds: number): string {
  const d = new Date(epochSeconds * 1000)
  const hh = String(d.getHours()).padStart(2, "0")
  const mm = String(d.getMinutes()).padStart(2, "0")
  return `${hh}:${mm}`
}

export function RunConfirmModal({
  existingSavedAt,
  onConfirm,
  onCancel,
}: {
  existingSavedAt: number
  onConfirm: () => void
  onCancel: () => void
}) {
  return (
    <div
      className="fixed inset-0 bg-black/60 flex items-center justify-center z-50"
      onClick={onCancel}
    >
      <Card
        className="p-6 max-w-md w-full m-4 space-y-4"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 className="text-lg font-semibold">재실행 확인</h3>
        <p className="text-sm text-neutral-300">
          오늘 날짜의 Pulse 는 <span className="font-mono">{formatTime(existingSavedAt)}</span>
          에 이미 계산되어 있습니다. 재실행하면 기존 값이 덮어씌워집니다.
        </p>
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={onCancel}>취소</Button>
          <Button onClick={onConfirm}>재실행</Button>
        </div>
      </Card>
    </div>
  )
}
