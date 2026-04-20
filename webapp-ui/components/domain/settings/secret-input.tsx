"use client"
import { useState } from "react"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"

type Props = {
  label: string
  displayValue: string         // 이미 마스킹됨
  isSecret: boolean
  onChange: (newValue: string, currentPassword: string) => Promise<void>
}

export function SecretInput({ label, displayValue, isSecret, onChange }: Props) {
  const [editing, setEditing] = useState(false)
  const [newValue, setNewValue] = useState("")
  const [currentPw, setCurrentPw] = useState("")
  const [err, setErr] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const save = async () => {
    setSaving(true); setErr(null)
    try {
      await onChange(newValue, currentPw)
      setEditing(false); setNewValue(""); setCurrentPw("")
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed")
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="py-2">
      <div className="flex justify-between items-center">
        <span className="text-sm text-neutral-400">{label}</span>
        {!editing && (
          <Button size="sm" variant="outline" onClick={() => setEditing(true)}>
            수정
          </Button>
        )}
      </div>
      {!editing && (
        <div className="mt-1 font-mono text-sm">{displayValue || "(없음)"}</div>
      )}
      {editing && (
        <div className="mt-2 space-y-2">
          <Input
            type={isSecret ? "password" : "text"}
            placeholder="새 값"
            value={newValue}
            onChange={(e) => setNewValue(e.target.value)}
          />
          <Input
            type="password"
            placeholder="현재 비밀번호 (확인)"
            value={currentPw}
            onChange={(e) => setCurrentPw(e.target.value)}
          />
          {err && <p className="text-sm text-red-400">{err}</p>}
          <div className="flex gap-2">
            <Button size="sm" onClick={save} disabled={saving || !newValue || !currentPw}>
              {saving ? "..." : "저장"}
            </Button>
            <Button size="sm" variant="outline" onClick={() => { setEditing(false); setNewValue(""); setCurrentPw("") }}>
              취소
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
