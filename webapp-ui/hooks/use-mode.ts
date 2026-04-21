"use client"
import { useSearchParams, useRouter, usePathname } from "next/navigation"
import { useCallback } from "react"
import type { Mode } from "@/lib/types"

const MODES: Mode[] = ["paper", "live", "backtest"]

export function useMode(): {
  mode: Mode
  setMode: (m: Mode) => void
} {
  const params = useSearchParams()
  const router = useRouter()
  const path = usePathname()
  const raw = params.get("mode") ?? "paper"
  const mode: Mode = MODES.includes(raw as Mode) ? (raw as Mode) : "paper"

  const setMode = useCallback(
    (m: Mode) => {
      const sp = new URLSearchParams(params.toString())
      sp.set("mode", m)
      router.replace(`${path}?${sp.toString()}`)
    },
    [params, router, path],
  )

  return { mode, setMode }
}
