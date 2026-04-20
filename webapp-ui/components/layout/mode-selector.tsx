"use client"
import { useMode } from "@/hooks/use-mode"
import type { Mode } from "@/lib/types"

const LABELS: Record<Mode, string> = {
  paper: "Paper",
  live: "Live",
  backtest: "Backtest",
}

const COLORS: Record<Mode, string> = {
  paper: "bg-sky-900/40 text-sky-300",
  live: "bg-red-900/40 text-red-300",
  backtest: "bg-neutral-800 text-neutral-300",
}

export function ModeSelector() {
  const { mode, setMode } = useMode()
  return (
    <select
      value={mode}
      onChange={(e) => setMode(e.target.value as Mode)}
      className={
        "rounded px-2 py-1 text-xs font-medium border-0 focus:ring-1 " +
        COLORS[mode]
      }
      aria-label="Mode selector"
    >
      {(Object.keys(LABELS) as Mode[]).map((m) => (
        <option key={m} value={m}>
          {LABELS[m]}
        </option>
      ))}
    </select>
  )
}
