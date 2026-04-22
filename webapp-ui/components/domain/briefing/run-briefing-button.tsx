"use client"
import { useState } from "react"
import { useRouter } from "next/navigation"
import { apiMutate } from "@/lib/api-client"
import { Button } from "@/components/ui/button"
import { RunConfirmModal } from "@/components/domain/market/run-confirm-modal"
import type { BriefingSummary } from "./briefing-summary-row"

function todayYmd(): string {
  const d = new Date()
  const yyyy = String(d.getFullYear())
  const mm = String(d.getMonth() + 1).padStart(2, "0")
  const dd = String(d.getDate()).padStart(2, "0")
  return `${yyyy}${mm}${dd}`
}

export function RunBriefingButton({
  latestToday,
}: {
  latestToday: BriefingSummary | null
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
        "/api/v1/briefings/run", "POST", {},
      )
      router.push(`/briefings/jobs/${r.job_id}`)
    } catch (e) {
      setError(e instanceof Error ? e.message : "실행 실패")
      setRunning(false)
    }
  }

  const handleClick = () => {
    if (latestToday && latestToday.date === todayYmd()) {
      setShowConfirm(true)
    } else {
      doRun()
    }
  }

  return (
    <div>
      <Button onClick={handleClick} disabled={running}>
        {running ? "실행 중…" : "지금 실행"}
      </Button>
      {error && <p className="mt-2 text-sm text-red-400">{error}</p>}
      {showConfirm && latestToday && (
        <RunConfirmModal
          existingSavedAt={latestToday.created_at}
          onConfirm={doRun}
          onCancel={() => setShowConfirm(false)}
        />
      )}
    </div>
  )
}
