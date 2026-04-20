import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"

type TableStatus = {
  name: string
  row_count: number
  latest_date: string | null
  distinct_codes: number
}

export function StatusTable({ tables }: { tables: TableStatus[] }) {
  if (tables.length === 0) {
    return <p className="text-sm text-neutral-500">데이터 없음.</p>
  }
  return (
    <div className="rounded-md border border-neutral-800 text-sm">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>테이블</TableHead>
            <TableHead className="text-right">행 수</TableHead>
            <TableHead className="text-right">종목 수</TableHead>
            <TableHead>최신 날짜</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {tables.map((t) => (
            <TableRow key={t.name}>
              <TableCell className="font-mono">{t.name}</TableCell>
              <TableCell className="text-right">
                {t.row_count.toLocaleString()}
              </TableCell>
              <TableCell className="text-right">
                {t.distinct_codes.toLocaleString()}
              </TableCell>
              <TableCell className="font-mono">{t.latest_date || "-"}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}
