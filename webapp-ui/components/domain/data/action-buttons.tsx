"use client"
import { useState } from "react"
import { useRouter } from "next/navigation"
import { apiMutate } from "@/lib/api-client"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"

const DISABLED_TOOLTIP =
  "초기 1회 전종목 수집은 리소스가 큼. CLI `ap trading data collect`에서만 실행 가능. 웹에서는 안전상 차단."

export function ActionButtons() {
  const router = useRouter()
  const [err, setErr] = useState<string | null>(null)
  const [loading, setLoading] = useState<string | null>(null)

  const trigger = async (path: string, body: object, label: string) => {
    setLoading(label)
    setErr(null)
    try {
      const r = await apiMutate<{ job_id: string }>(path, "POST", body)
      router.push(`/data/jobs/${r.job_id}`)
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed")
    } finally {
      setLoading(null)
    }
  }

  return (
    <Card className="p-4 space-y-3">
      <h2 className="font-medium">수집 액션</h2>
      <div className="flex flex-wrap gap-2">
        <Button
          onClick={() =>
            trigger("/api/v1/data/update", { markets: ["KOSPI", "KOSDAQ"] }, "update")
          }
          disabled={loading !== null}
        >
          {loading === "update" ? "..." : "증분 업데이트"}
        </Button>
        <Button
          variant="outline"
          onClick={() =>
            trigger("/api/v1/data/collect-financials", { market: "KOSPI", top: 100 }, "financials")
          }
          disabled={loading !== null}
        >
          {loading === "financials" ? "..." : "재무 재수집"}
        </Button>
        <Button
          variant="outline"
          onClick={() =>
            trigger(
              "/api/v1/data/collect-wisereport",
              { market: "KOSPI", top: 100 },
              "wisereport",
            )
          }
          disabled={loading !== null}
        >
          {loading === "wisereport" ? "..." : "Wisereport 재수집"}
        </Button>
        <Button
          variant="outline"
          onClick={() =>
            trigger("/api/v1/data/collect-short", { market: "KOSPI", top: 100 }, "short")
          }
          disabled={loading !== null}
        >
          {loading === "short" ? "..." : "공매도 재수집"}
        </Button>
        <Button
          variant="outline"
          disabled
          title={DISABLED_TOOLTIP}
          className="cursor-not-allowed opacity-50"
        >
          전종목 수집 (비활성)
        </Button>
      </div>
      <p className="text-xs text-neutral-500">
        💡 전종목 수집은 CLI <code>ap trading data collect</code>에서만 실행 가능합니다. 리소스
        보호 및 실수 방지.
      </p>
      {err && <p className="text-sm text-red-400">{err}</p>}
    </Card>
  )
}
