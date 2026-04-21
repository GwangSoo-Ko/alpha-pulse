import { ContentJobProgress } from "@/components/domain/content/content-job-progress"

type Props = { params: Promise<{ id: string }> }

export default async function ContentJobPage({ params }: Props) {
  const { id } = await params
  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <h1 className="text-2xl font-semibold">BlogPulse 수집 중</h1>
      <ContentJobProgress jobId={id} />
    </div>
  )
}
