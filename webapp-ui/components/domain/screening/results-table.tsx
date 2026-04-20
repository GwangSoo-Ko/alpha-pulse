import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"

type Result = {
  code: string; name: string; market: string
  score: number
  factors: Record<string, number>
}

export function ResultsTable({ results }: { results: Result[] }) {
  if (results.length === 0) {
    return <p className="text-sm text-neutral-500">결과 없음.</p>
  }
  return (
    <div className="rounded-md border border-neutral-800 text-sm">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>순위</TableHead>
            <TableHead>종목</TableHead>
            <TableHead>이름</TableHead>
            <TableHead>시장</TableHead>
            <TableHead className="text-right">점수</TableHead>
            <TableHead>주요 팩터</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {results.map((r, i) => {
            const topFactor = Object.entries(r.factors).sort((a, b) => b[1] - a[1])[0]
            return (
              <TableRow key={`${r.code}-${i}`}>
                <TableCell className="font-mono">{i + 1}</TableCell>
                <TableCell className="font-mono">{r.code}</TableCell>
                <TableCell>{r.name}</TableCell>
                <TableCell>{r.market}</TableCell>
                <TableCell className="text-right font-mono">
                  {r.score >= 0 ? "+" : ""}{r.score.toFixed(1)}
                </TableCell>
                <TableCell className="font-mono text-xs">
                  {topFactor ? `${topFactor[0]}(${topFactor[1].toFixed(0)})` : "-"}
                </TableCell>
              </TableRow>
            )
          })}
        </TableBody>
      </Table>
    </div>
  )
}
