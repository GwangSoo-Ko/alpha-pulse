"use client"
import { useRouter } from "next/navigation"
import { useState } from "react"
import { useForm, useWatch } from "react-hook-form"
import { z } from "zod"
import { zodResolver } from "@hookform/resolvers/zod"
import { apiMutate } from "@/lib/api-client"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { BACKTEST_STRATEGIES, findBacktestStrategy } from "@/lib/strategies"
import { StrategyInfoCard } from "@/components/domain/strategy-info-card"

const schema = z.object({
  strategy: z.enum(["momentum", "value", "quality_momentum", "topdown_etf"]),
  start: z.string().regex(/^\d{8}$/, "YYYYMMDD"),
  end: z.string().regex(/^\d{8}$/, "YYYYMMDD"),
  capital: z.coerce.number().int().min(1_000_000).max(100_000_000_000),
  market: z.enum(["KOSPI", "KOSDAQ"]),
  top: z.coerce.number().int().min(1).max(100),
  name: z.string().max(100).optional(),
})
type FormData = z.infer<typeof schema>

export function BacktestForm() {
  const router = useRouter()
  const [error, setError] = useState<string | null>(null)
  const {
    register, handleSubmit, control,
    formState: { errors, isSubmitting },
  } = useForm<FormData>({
    resolver: zodResolver(schema),
    defaultValues: {
      strategy: "momentum", market: "KOSPI", top: 20,
      capital: 100_000_000,
      start: "20240101",
      end: new Date().toISOString().slice(0, 10).replace(/-/g, ""),
    },
  })
  const selectedStrategy = useWatch({ control, name: "strategy" })
  const strategyInfo = findBacktestStrategy(selectedStrategy)

  const onSubmit = async (data: FormData) => {
    setError(null)
    try {
      const r = await apiMutate<{ job_id: string }>(
        "/api/v1/backtest/run", "POST", data,
      )
      router.push(`/backtest/jobs/${r.job_id}`)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed")
    }
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
      <div>
        <Label htmlFor="strategy">전략</Label>
        <select
          id="strategy" {...register("strategy")}
          className="mt-1 block w-full rounded border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm"
        >
          {BACKTEST_STRATEGIES.map((s) => (
            <option key={s.id} value={s.id}>{s.label}</option>
          ))}
        </select>
      </div>

      {strategyInfo && <StrategyInfoCard info={strategyInfo} />}

      <div>
        <Label htmlFor="market">시장</Label>
        <select
          id="market" {...register("market")}
          className="mt-1 block w-full rounded border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm"
        >
          {["KOSPI", "KOSDAQ"].map((v) => (
            <option key={v} value={v}>{v}</option>
          ))}
        </select>
      </div>

      {(["start", "end"] as const).map((key) => (
        <div key={key}>
          <Label htmlFor={key}>{key === "start" ? "시작일" : "종료일"} (YYYYMMDD)</Label>
          <Input id={key} {...register(key)} />
          {errors[key] && <p className="text-sm text-red-400">{errors[key]?.message}</p>}
        </div>
      ))}
      {(["capital", "top"] as const).map((key) => (
        <div key={key}>
          <Label htmlFor={key}>{key === "capital" ? "초기 자본 (원)" : "Top N"}</Label>
          <Input id={key} type="number" {...register(key)} />
          {errors[key] && <p className="text-sm text-red-400">{errors[key]?.message}</p>}
        </div>
      ))}
      <div>
        <Label htmlFor="name">이름 (선택)</Label>
        <Input id="name" {...register("name")} />
      </div>
      {error && <p className="text-sm text-red-400">{error}</p>}
      <Button type="submit" disabled={isSubmitting} className="w-full">
        {isSubmitting ? "..." : "실행"}
      </Button>
    </form>
  )
}
