"use client"
import { useEffect } from "react"
import { useRouter } from "next/navigation"
import { useJobStatus } from "@/hooks/use-job-status"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"

export function BriefingJobProgress({ jobId }: { jobId: string }) {
  const router = useRouter()
  const { data: job, error } = useJobStatus(jobId)

  useEffect(() => {
    if (job?.status === "done") {
      const dest = job.result_ref && /^\d{8}$/.test(job.result_ref)
        ? `/briefings/${job.result_ref}`
        : "/briefings"
      router.replace(dest)
    }
  }, [job, router])

  if (error) return <div className="text-red-400">오류: {String(error)}</div>
  if (!job) return <Card className="p-6">로딩 중...</Card>

  const pct = (job.progress * 100).toFixed(0)

  return (
    <Card className="space-y-4 p-6">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-neutral-400">상태</p>
          <p className="text-lg font-semibold">{job.status}</p>
        </div>
        <div className="text-right">
          <p className="text-sm text-neutral-400">진행률</p>
          <p className="text-2xl font-mono">{pct}%</p>
        </div>
      </div>
      <div className="h-2 overflow-hidden rounded bg-neutral-800">
        <div className="h-full bg-green-500 transition-all" style={{ width: `${pct}%` }} />
      </div>
      <p className="text-sm text-neutral-400">{job.progress_text || "-"}</p>
      <p className="text-xs text-neutral-500">
        정량분석 + AI Commentary + Senior Synthesis 로 3~10분 소요됩니다.
        브라우저 닫아도 백그라운드에서 계속 실행되며, 완료 후 브리핑 목록에서 확인할 수 있습니다.
      </p>
      {job.status === "failed" && (
        <div className="space-y-2">
          <p className="text-red-400">실패: {job.error}</p>
          <Button variant="outline" onClick={() => router.push("/briefings")}>
            돌아가기
          </Button>
        </div>
      )}
    </Card>
  )
}
