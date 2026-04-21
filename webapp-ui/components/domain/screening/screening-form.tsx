"use client"
import { useState } from "react"
import { useRouter } from "next/navigation"
import { apiMutate } from "@/lib/api-client"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { SCREENING_PRESETS, findScreeningPreset } from "@/lib/strategies"
import { StrategyInfoCard } from "@/components/domain/strategy-info-card"

const PRESETS: Record<string, Record<string, number>> = {
  momentum: { momentum: 0.5, flow: 0.3, volatility: 0.2 },
  value: { value: 0.4, quality: 0.2, momentum: 0.2, flow: 0.15, volatility: 0.05 },
  quality: { quality: 0.35, growth: 0.2, value: 0.15, momentum: 0.2, flow: 0.1 },
  balanced: {
    momentum: 0.25, flow: 0.25, value: 0.2,
    quality: 0.15, growth: 0.1, volatility: 0.05,
  },
}

export function ScreeningForm() {
  const router = useRouter()
  const [market, setMarket] = useState<"KOSPI" | "KOSDAQ" | "ALL">("KOSPI")
  const [strategy, setStrategy] = useState("momentum")
  const [topN, setTopN] = useState("20")
  const [name, setName] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const presetInfo = findScreeningPreset(strategy)

  const handle = async () => {
    setSubmitting(true); setError(null)
    try {
      const r = await apiMutate<{ job_id: string }>(
        "/api/v1/screening/run", "POST",
        {
          market, strategy, top_n: Number(topN), name,
          factor_weights: PRESETS[strategy] || PRESETS.momentum,
        },
      )
      router.push(`/screening/jobs/${r.job_id}`)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed")
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="space-y-4">
      <div>
        <Label>시장</Label>
        <select
          value={market}
          onChange={(e) => setMarket(e.target.value as typeof market)}
          className="mt-1 block w-full rounded border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm"
        >
          <option value="KOSPI">KOSPI</option>
          <option value="KOSDAQ">KOSDAQ</option>
          <option value="ALL">ALL</option>
        </select>
      </div>
      <div>
        <Label>전략 preset</Label>
        <select
          value={strategy} onChange={(e) => setStrategy(e.target.value)}
          className="mt-1 block w-full rounded border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm"
        >
          {SCREENING_PRESETS.map((p) => (
            <option key={p.id} value={p.id}>{p.label}</option>
          ))}
        </select>
      </div>

      {presetInfo && <StrategyInfoCard info={presetInfo} />}

      <div>
        <Label>Top N</Label>
        <Input type="number" value={topN} onChange={(e) => setTopN(e.target.value)} />
      </div>
      <div>
        <Label>이름 (선택)</Label>
        <Input value={name} onChange={(e) => setName(e.target.value)} />
      </div>
      {error && <p className="text-sm text-red-400">{error}</p>}
      <Button onClick={handle} disabled={submitting} className="w-full">
        {submitting ? "실행 중..." : "실행"}
      </Button>
    </div>
  )
}
