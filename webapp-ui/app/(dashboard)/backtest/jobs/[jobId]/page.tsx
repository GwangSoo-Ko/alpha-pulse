import { JobProgress } from "@/components/domain/backtest/job-progress"

type Props = { params: Promise<{ jobId: string }> }

export default async function JobPage({ params }: Props) {
  const { jobId } = await params
  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <h1 className="text-2xl font-semibold">백테스트 실행 중</h1>
      <JobProgress jobId={jobId} />
    </div>
  )
}
