import { Card } from "@/components/ui/card"

export function EncryptKeyMissing() {
  return (
    <Card className="p-6 space-y-3">
      <h2 className="font-medium text-yellow-400">
        ⚠️ Settings 비활성화됨
      </h2>
      <p className="text-sm text-neutral-400">
        <code>WEBAPP_ENCRYPT_KEY</code>가 설정되지 않아 Settings 저장소를
        사용할 수 없습니다.
      </p>
      <div className="text-sm text-neutral-300 space-y-2">
        <p className="font-medium">초기 설정 절차:</p>
        <ol className="list-decimal list-inside space-y-1 text-xs text-neutral-400">
          <li>
            CLI에서 <code className="text-neutral-200">uv run ap webapp init-encrypt-key</code> 실행
          </li>
          <li>출력된 키를 <code>.env</code>의 <code>WEBAPP_ENCRYPT_KEY</code>에 추가</li>
          <li>FastAPI 재시작</li>
          <li>
            (선택) <code className="text-neutral-200">uv run ap webapp import-env</code>로 기존 <code>.env</code> 값 이관
          </li>
        </ol>
      </div>
    </Card>
  )
}
