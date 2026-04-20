"use client"
import { apiMutate } from "@/lib/api-client"
import { Card } from "@/components/ui/card"
import { SecretInput } from "@/components/domain/settings/secret-input"

type Item = {
  key: string; value: string; is_secret: boolean; category: string; updated_at: number
}

export function CategorySettingsForm({
  items, labels,
}: { items: Item[]; labels: Record<string, string> }) {
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
          설정 없음. <code>ap webapp import-env</code>로 초기화하세요.
        </p>
      </Card>
    )
  }
  return (
    <Card className="p-6 space-y-1">
      {sorted.map((item) => (
        <SecretInput
          key={item.key}
          label={labels[item.key] || item.key}
          displayValue={item.value}
          isSecret={item.is_secret}
          onChange={(v, pw) => handleUpdate(item.key, v, pw)}
        />
      ))}
    </Card>
  )
}
