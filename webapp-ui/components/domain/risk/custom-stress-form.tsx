"use client"
import { useState } from "react"
import { apiMutate } from "@/lib/api-client"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Card } from "@/components/ui/card"
import { fmtPct } from "@/lib/format"

export function CustomStressForm({ mode }: { mode: string }) {
  const [kospi, setKospi] = useState("-0.10")
  const [kosdaq, setKosdaq] = useState("-0.15")
  const [result, setResult] = useState<Record<string, number> | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleRun = async () => {
    setLoading(true); setError(null); setResult(null)
    try {
      const r = await apiMutate<{ results: Record<string, number> }>(
        "/api/v1/risk/stress/custom", "POST",
        {
          mode,
          shocks: { KOSPI: parseFloat(kospi), KOSDAQ: parseFloat(kosdaq) },
        },
      )
      setResult(r.results)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed")
    } finally {
      setLoading(false)
    }
  }

  return (
    <Card className="p-4 space-y-3">
      <h2 className="font-medium">커스텀 시나리오</h2>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <Label htmlFor="kospi">KOSPI 충격</Label>
          <Input
            id="kospi" type="number" step="0.01"
            value={kospi} onChange={(e) => setKospi(e.target.value)}
          />
        </div>
        <div>
          <Label htmlFor="kosdaq">KOSDAQ 충격</Label>
          <Input
            id="kosdaq" type="number" step="0.01"
            value={kosdaq} onChange={(e) => setKosdaq(e.target.value)}
          />
        </div>
      </div>
      <Button onClick={handleRun} disabled={loading}>
        {loading ? "계산 중..." : "실행"}
      </Button>
      {error && <p className="text-sm text-red-400">{error}</p>}
      {result && (
        <div className="text-sm">
          {Object.entries(result).map(([k, v]) => (
            <div key={k} className="flex justify-between">
              <span>{k}</span>
              <span className={`font-mono ${v >= 0 ? "text-green-400" : "text-red-400"}`}>
                {fmtPct(v)}
              </span>
            </div>
          ))}
        </div>
      )}
    </Card>
  )
}
