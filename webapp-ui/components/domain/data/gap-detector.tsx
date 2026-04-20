import { Card } from "@/components/ui/card"

export function GapDetector({
  gaps,
}: {
  gaps: { code: string; last_date: string }[]
}) {
  return (
    <Card className="p-4">
      <h2 className="font-medium mb-2">갭 감지 (최근 5일 이내 미업데이트)</h2>
      {gaps.length === 0 ? (
        <p className="text-sm text-green-400">갭 없음.</p>
      ) : (
        <div>
          <p className="text-sm text-yellow-400 mb-2">
            {gaps.length}종목 갭 발견.
          </p>
          <div className="grid grid-cols-6 gap-1 text-xs font-mono">
            {gaps.slice(0, 60).map((g) => (
              <div key={g.code} className="text-neutral-400">
                {g.code} ({g.last_date})
              </div>
            ))}
          </div>
          {gaps.length > 60 && (
            <p className="text-xs text-neutral-500 mt-2">
              ... +{gaps.length - 60} more
            </p>
          )}
        </div>
      )}
    </Card>
  )
}
