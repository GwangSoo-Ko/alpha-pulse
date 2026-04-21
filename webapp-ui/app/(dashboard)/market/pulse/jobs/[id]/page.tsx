import { MarketJobProgress } from "@/components/domain/market/market-job-progress"

type Props = { params: Promise<{ id: string }> }

export default async function MarketPulseJobPage({ params }: Props) {
  const { id } = await params
  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <h1 className="text-2xl font-semibold">Market Pulse 실행 중</h1>
      <MarketJobProgress jobId={id} />
    </div>
  )
}
