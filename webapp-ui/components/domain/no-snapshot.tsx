import Link from "next/link"
import { Card } from "@/components/ui/card"

export function NoSnapshot({ mode }: { mode: string }) {
  const isPaper = mode === "paper"
  return (
    <Card className="p-6 space-y-4">
      <div>
        <h2 className="text-lg font-semibold mb-1">스냅샷 없음 ({mode})</h2>
        <p className="text-sm text-neutral-500">
          {isPaper
            ? "아직 Paper 모드 매매 실행 이력이 없습니다."
            : `${mode} 모드 스냅샷이 없습니다.`}
        </p>
      </div>

      {isPaper && (
        <div className="rounded-lg border border-neutral-800 bg-neutral-900/50 p-4 space-y-3">
          <h3 className="text-sm font-medium text-neutral-200">시작하기</h3>
          <p className="text-xs text-neutral-400">
            CLI에서 아래 명령으로 전체 매매 파이프라인을 1회 실행하면 스냅샷이 생성됩니다.
            실제 돈은 움직이지 않으며, 데이터 수집 → 전략 → 시그널 → 가상 주문 → 스냅샷까지 한 번에 실행.
          </p>
          <div className="font-mono text-xs text-neutral-300 bg-neutral-950 px-3 py-2 rounded">
            uv run ap trading run --mode paper
          </div>
          <p className="text-xs text-neutral-500">
            실행 후 이 페이지 새로고침.
          </p>
        </div>
      )}

      <div className="flex flex-wrap gap-2 text-xs">
        <Link
          href="/backtest/new"
          className="px-3 py-1.5 rounded border border-neutral-700 hover:bg-neutral-800"
        >
          백테스트 실행 →
        </Link>
        <Link
          href="/data"
          className="px-3 py-1.5 rounded border border-neutral-700 hover:bg-neutral-800"
        >
          데이터 현황 →
        </Link>
      </div>
    </Card>
  )
}
