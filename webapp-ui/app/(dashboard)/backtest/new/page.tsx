import { BacktestForm } from "@/components/domain/backtest/backtest-form"

export default function NewBacktestPage() {
  return (
    <div className="mx-auto max-w-lg space-y-6">
      <h1 className="text-2xl font-semibold">새 백테스트</h1>
      <BacktestForm />
    </div>
  )
}
