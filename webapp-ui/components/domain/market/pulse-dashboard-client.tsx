"use client"
import { useState } from "react"
import { useRouter } from "next/navigation"
import { apiMutate } from "@/lib/api-client"
import { ScoreHeroCard, type PulseSnapshot } from "./score-hero-card"
import { PulseHistoryChart, type HistoryItem } from "./pulse-history-chart"
import { IndicatorGrid } from "./indicator-grid"
import { RunConfirmModal } from "./run-confirm-modal"
import { NoPulseSnapshot } from "./no-pulse-snapshot"

function isToday(yyyymmdd: string): boolean {
  const now = new Date()
  const yyyy = String(now.getFullYear())
  const mm = String(now.getMonth() + 1).padStart(2, "0")
  const dd = String(now.getDate()).padStart(2, "0")
  return yyyymmdd === `${yyyy}${mm}${dd}`
}

export function PulseDashboardClient({
  latest,
  history,
}: {
  latest: PulseSnapshot | null
  history: HistoryItem[]
}) {
  const router = useRouter()
  const [running, setRunning] = useState(false)
  const [showConfirm, setShowConfirm] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const doRun = async () => {
    setRunning(true)
    setShowConfirm(false)
    setError(null)
    try {
      const r = await apiMutate<{ job_id: string; reused: boolean }>(
        "/api/v1/market/pulse/run", "POST", {},
      )
      router.push(`/market/pulse/jobs/${r.job_id}`)
    } catch (e) {
      setError(e instanceof Error ? e.message : "실행 실패")
      setRunning(false)
    }
  }

  const handleRunClick = () => {
    if (latest && isToday(latest.date)) {
      setShowConfirm(true)
    } else {
      doRun()
    }
  }

  if (!latest) {
    return <NoPulseSnapshot onRun={handleRunClick} />
  }

  return (
    <div className="space-y-6">
      <ScoreHeroCard snapshot={latest} onRun={handleRunClick} running={running} />
      {error && <p className="text-sm text-red-400">{error}</p>}
      <PulseHistoryChart items={history} />
      <IndicatorGrid
        scores={latest.indicator_scores}
        descriptions={latest.indicator_descriptions}
      />
      {showConfirm && (
        <RunConfirmModal
          existingSavedAt={latest.created_at}
          onConfirm={doRun}
          onCancel={() => setShowConfirm(false)}
        />
      )}
    </div>
  )
}
