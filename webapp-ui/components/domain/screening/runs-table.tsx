"use client"
import Link from "next/link"
import { useRouter, useSearchParams, usePathname } from "next/navigation"
import { Button } from "@/components/ui/button"
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table"

type Props = {
  data: {
    items: { run_id: string; name: string; market: string; strategy: string; top_n: number; created_at: number }[]
    page: number; size: number; total: number
  }
  currentPage: number
}

export function RunsTable({ data, currentPage }: Props) {
  const router = useRouter()
  const path = usePathname()
  const params = useSearchParams()
  const totalPages = Math.max(1, Math.ceil(data.total / data.size))

  const go = (page: number) => {
    const sp = new URLSearchParams(params.toString())
    sp.set("page", String(page))
    router.push(`${path}?${sp.toString()}`)
  }
  return (
    <div className="space-y-4">
      <div className="rounded-md border border-neutral-800 text-sm">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>ID</TableHead>
              <TableHead>이름</TableHead>
              <TableHead>시장</TableHead>
              <TableHead>전략</TableHead>
              <TableHead className="text-right">Top N</TableHead>
              <TableHead>생성 시각</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.items.map((r) => (
              <TableRow key={r.run_id}>
                <TableCell className="font-mono">
                  <Link href={`/screening/${r.run_id}`} className="hover:underline">
                    {r.run_id.slice(0, 8)}
                  </Link>
                </TableCell>
                <TableCell>{r.name || "-"}</TableCell>
                <TableCell>{r.market}</TableCell>
                <TableCell>{r.strategy}</TableCell>
                <TableCell className="text-right">{r.top_n}</TableCell>
                <TableCell className="text-neutral-400 text-xs">
                  {new Date(r.created_at * 1000).toISOString().slice(0, 19).replace("T", " ")}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      <div className="flex justify-between items-center text-sm">
        <span>총 {data.total}건 · {currentPage}/{totalPages}</span>
        <div className="space-x-2">
          <Button size="sm" variant="outline" disabled={currentPage <= 1} onClick={() => go(currentPage - 1)}>이전</Button>
          <Button size="sm" variant="outline" disabled={currentPage >= totalPages} onClick={() => go(currentPage + 1)}>다음</Button>
        </div>
      </div>
    </div>
  )
}
