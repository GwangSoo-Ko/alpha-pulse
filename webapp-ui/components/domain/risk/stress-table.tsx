import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table"
import { fmtPct } from "@/lib/format"

const SCENARIO_LABELS: Record<string, string> = {
  "2020_covid": "2020 코로나",
  "2022_rate_hike": "2022 금리 인상",
  "flash_crash": "Flash Crash",
  "won_crisis": "원화 위기",
  "sector_collapse": "섹터 붕괴",
}

export function StressTable({ scenarios }: { scenarios: Record<string, number> }) {
  const entries = Object.entries(scenarios)
  if (entries.length === 0) {
    return <p className="text-sm text-neutral-500">스트레스 결과 없음.</p>
  }
  return (
    <div className="rounded-md border border-neutral-800">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>시나리오</TableHead>
            <TableHead className="text-right">예상 영향 (%)</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {entries.map(([k, v]) => (
            <TableRow key={k}>
              <TableCell>{SCENARIO_LABELS[k] || k}</TableCell>
              <TableCell className={`text-right font-mono ${v >= 0 ? "text-green-400" : "text-red-400"}`}>
                {fmtPct(v)}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}
