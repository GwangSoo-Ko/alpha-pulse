import { ScreeningForm } from "@/components/domain/screening/screening-form"

export default function NewScreeningPage() {
  return (
    <div className="mx-auto max-w-xl space-y-6">
      <h1 className="text-2xl font-semibold">새 스크리닝</h1>
      <ScreeningForm />
    </div>
  )
}
