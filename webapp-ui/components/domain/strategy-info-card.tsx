import { Card } from "@/components/ui/card"
import type { StrategyInfo } from "@/lib/strategies"
import { FACTOR_DESCRIPTIONS } from "@/lib/strategies"

export function StrategyInfoCard({ info }: { info: StrategyInfo }) {
  const hasWeights = info.weights.length > 0
  const weightsTotal = info.weights.reduce((s, w) => s + w.weight, 0)

  return (
    <Card className="p-4 space-y-3 bg-neutral-900/50">
      <div>
        <h3 className="font-medium text-base">{info.label}</h3>
        <p className="text-sm text-neutral-400 mt-1">{info.summary}</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-xs">
        <div>
          <span className="text-neutral-500">유니버스</span>
          <div className="text-neutral-200 mt-0.5">{info.universe}</div>
        </div>
        <div>
          <span className="text-neutral-500">리밸런싱</span>
          <div className="text-neutral-200 mt-0.5">{info.rebalance}</div>
        </div>
        <div className="md:col-span-2">
          <span className="text-neutral-500">시장 상황 대응</span>
          <div className="text-neutral-200 mt-0.5">{info.marketReaction}</div>
        </div>
      </div>

      {hasWeights && (
        <div>
          <div className="text-xs text-neutral-500 mb-2">
            팩터 가중치 (합계 {(weightsTotal * 100).toFixed(0)}%)
          </div>
          <div className="space-y-1">
            {info.weights.map((w) => (
              <div key={w.key} className="flex items-center gap-2 text-xs">
                <span className="w-20 text-neutral-400" title={FACTOR_DESCRIPTIONS[w.key] || ""}>
                  {w.label}
                </span>
                <div className="flex-1 h-1.5 bg-neutral-800 rounded overflow-hidden">
                  <div
                    className="h-full bg-green-600"
                    style={{ width: `${(w.weight / Math.max(0.01, weightsTotal)) * 100}%` }}
                  />
                </div>
                <span className="w-12 text-right font-mono text-neutral-300">
                  {(w.weight * 100).toFixed(0)}%
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div>
        <div className="text-xs text-neutral-500 mb-1">동작 방식</div>
        <p className="text-xs text-neutral-300 leading-relaxed whitespace-pre-line">
          {info.details}
        </p>
      </div>
    </Card>
  )
}
