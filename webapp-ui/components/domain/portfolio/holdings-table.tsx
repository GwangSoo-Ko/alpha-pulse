import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table"
import { fmtKrw, fmtPct } from "@/lib/format"

type Position = {
  code: string; name: string; quantity: number
  avg_price: number; current_price: number
  unrealized_pnl: number; weight: number
}

export function HoldingsTable({ positions }: { positions: Position[] }) {
  if (positions.length === 0) {
    return <p className="text-sm text-neutral-500">보유 종목 없음.</p>
  }
  return (
    <div className="rounded-md border border-neutral-800 text-sm">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>종목</TableHead>
            <TableHead>이름</TableHead>
            <TableHead className="text-right">수량</TableHead>
            <TableHead className="text-right">평단</TableHead>
            <TableHead className="text-right">현재가</TableHead>
            <TableHead className="text-right">평가손익</TableHead>
            <TableHead className="text-right">비중</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {positions.map((p) => (
            <TableRow key={p.code}>
              <TableCell className="font-mono">{p.code}</TableCell>
              <TableCell>{p.name}</TableCell>
              <TableCell className="text-right">{p.quantity.toLocaleString()}</TableCell>
              <TableCell className="text-right font-mono">{fmtKrw(p.avg_price)}</TableCell>
              <TableCell className="text-right font-mono">{fmtKrw(p.current_price)}</TableCell>
              <TableCell className={`text-right font-mono ${p.unrealized_pnl >= 0 ? "text-green-400" : "text-red-400"}`}>
                {p.unrealized_pnl >= 0 ? "+" : ""}{p.unrealized_pnl.toLocaleString()}
              </TableCell>
              <TableCell className="text-right font-mono">{fmtPct(p.weight * 100, 1)}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}
