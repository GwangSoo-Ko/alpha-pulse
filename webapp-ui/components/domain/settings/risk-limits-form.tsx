"use client"
import { apiMutate } from "@/lib/api-client"
import { Card } from "@/components/ui/card"
import { SecretInput } from "@/components/domain/settings/secret-input"

const LABELS: Record<string, string> = {
  MAX_POSITION_WEIGHT: "종목당 최대 비중 (0-1)",
  MAX_DRAWDOWN_SOFT: "MDD soft 임계값 (0-1)",
  MAX_DRAWDOWN_HARD: "MDD hard 임계값 (0-1)",
  MAX_DAILY_ORDERS: "일일 주문 한도 (회)",
  MAX_DAILY_AMOUNT: "일일 금액 한도 (원)",
}

type Item = {
  key: string; value: string; is_secret: boolean; category: string; updated_at: number
}

export function RiskLimitsForm({ items }: { items: Item[] }) {
  const handleUpdate = async (key: string, newValue: string, currentPw: string) => {
    await apiMutate(`/api/v1/settings/${key}`, "PUT", {
      value: newValue, current_password: currentPw,
    })
  }
  const sorted = [...items].sort((a, b) => a.key.localeCompare(b.key))
  if (sorted.length === 0) {
    return (
      <Card className="p-6">
        <p className="text-sm text-neutral-500">
          리스크 리밋 설정 없음. <code>ap webapp import-env</code>로 초기화하세요.
        </p>
      </Card>
    )
  }
  return (
    <Card className="p-6 space-y-1">
      {sorted.map((item) => (
        <SecretInput
          key={item.key}
          label={LABELS[item.key] || item.key}
          displayValue={item.value}
          isSecret={false}
          onChange={(v, pw) => handleUpdate(item.key, v, pw)}
        />
      ))}
    </Card>
  )
}
