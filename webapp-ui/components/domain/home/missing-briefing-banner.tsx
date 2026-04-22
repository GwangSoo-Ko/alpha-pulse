"use client"
import { useState } from "react"
import { Button } from "@/components/ui/button"
import { apiFetch } from "@/lib/api-client"

function formatDate(yyyymmdd: string): string {
  if (yyyymmdd.length !== 8) return yyyymmdd
  return `${yyyymmdd.slice(0, 4)}-${yyyymmdd.slice(4, 6)}-${yyyymmdd.slice(6)}`
}

function todayYYYYMMDD(): string {
  const d = new Date()
  return `${d.getFullYear()}${String(d.getMonth() + 1).padStart(2, "0")}${String(d.getDate()).padStart(2, "0")}`
}

export function MissingBriefingBanner({ latestDate }: { latestDate: string | null }) {
  const [running, setRunning] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const today = todayYYYYMMDD()
  const todayPretty = formatDate(today)

  async function onRun() {
    setRunning(true)
    setMessage(null)
    try {
      await apiFetch("/api/v1/briefings/run", { method: "POST" })
      setMessage("브리핑 작업이 시작되었습니다. 잠시 후 새로고침하세요.")
    } catch (e) {
      setMessage(`실행 실패: ${e instanceof Error ? e.message : String(e)}`)
    } finally {
      setRunning(false)
    }
  }

  const text = latestDate
    ? `⚠ 오늘(${todayPretty}) 브리핑 미생성 · 어제(${formatDate(latestDate)}) 기준 표시 중`
    : `⚠ 브리핑 데이터가 없습니다.`

  return (
    <div className="rounded-md border border-amber-900/40 bg-amber-950/30 px-4 py-3 flex items-center justify-between gap-4 flex-wrap">
      <p className="text-sm text-amber-300">{text}</p>
      <div className="flex items-center gap-3">
        {message && <span className="text-xs text-neutral-400">{message}</span>}
        <Button onClick={onRun} disabled={running} variant="default" size="sm">
          {running ? "실행 중..." : "지금 실행"}
        </Button>
      </div>
    </div>
  )
}
