"use client"
import { apiMutate } from "@/lib/api-client"
import { Card } from "@/components/ui/card"
import { SecretInput } from "@/components/domain/settings/secret-input"

type Item = {
  key: string; value: string; is_secret: boolean; category: string; updated_at: number
}

const LABELS: Record<string, string> = {
  KIS_APP_KEY: "KIS APP KEY",
  KIS_APP_SECRET: "KIS APP SECRET",
  KIS_ACCOUNT_NO: "KIS 계좌번호",
  GEMINI_API_KEY: "Gemini API Key",
}

export function ApiKeysForm({ items }: { items: Item[] }) {
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
          저장된 API 키 없음. <code>ap webapp import-env</code> 또는 CLI <code>ap webapp set</code>으로 초기화하세요.
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
          isSecret={item.is_secret}
          onChange={(v, pw) => handleUpdate(item.key, v, pw)}
        />
      ))}
    </Card>
  )
}
