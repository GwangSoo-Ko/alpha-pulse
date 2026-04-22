"use client"
import { Card } from "@/components/ui/card"

function describeCorrelation(r: number): string {
  const a = Math.abs(r)
  const dir = r > 0 ? "양" : "음"
  if (a < 0.1) return "상관관계 거의 없음"
  if (a < 0.3) return `약한 ${dir}의 상관`
  if (a < 0.5) return `중간 ${dir}의 상관`
  if (a < 0.7) return `상당한 ${dir}의 상관`
  return `강한 ${dir}의 상관`
}

export function CorrelationCard({ correlation }: { correlation: number | null }) {
  if (correlation === null) {
    return (
      <Card className="p-4 space-y-1">
        <p className="text-xs text-neutral-400">Score ↔ 1일 수익률 상관</p>
        <p className="text-3xl font-bold font-mono text-neutral-500">-</p>
        <p className="text-xs text-neutral-500">데이터 부족</p>
      </Card>
    )
  }
  return (
    <Card className="p-4 space-y-1">
      <p className="text-xs text-neutral-400">Score ↔ 1일 수익률 상관</p>
      <p className="text-3xl font-bold font-mono">{correlation.toFixed(2)}</p>
      <p className="text-xs text-neutral-500">{describeCorrelation(correlation)}</p>
    </Card>
  )
}
