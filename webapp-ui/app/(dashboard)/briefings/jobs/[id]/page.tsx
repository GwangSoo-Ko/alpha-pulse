import { BriefingJobProgress } from "@/components/domain/briefing/briefing-job-progress"

type Props = { params: Promise<{ id: string }> }

export default async function BriefingJobPage({ params }: Props) {
  const { id } = await params
  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <h1 className="text-2xl font-semibold">브리핑 생성 중</h1>
      <BriefingJobProgress jobId={id} />
    </div>
  )
}
