"use client"
import { useRouter, useSearchParams, usePathname } from "next/navigation"
import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"

type Event = {
  id: number; timestamp: number; event_type: string; component: string
  data: Record<string, unknown>; mode: string
}

type Props = {
  data: { items: Event[]; page: number; size: number; total: number }
  currentPage: number
  currentActionPrefix: string
  currentActor: string
}

export function AuditTable({ data, currentPage, currentActionPrefix, currentActor }: Props) {
  const router = useRouter()
  const path = usePathname()
  const params = useSearchParams()
  const [prefix, setPrefix] = useState(currentActionPrefix)
  const [actor, setActor] = useState(currentActor)

  const apply = () => {
    const sp = new URLSearchParams(params.toString())
    if (prefix) sp.set("action_prefix", prefix); else sp.delete("action_prefix")
    if (actor) sp.set("actor", actor); else sp.delete("actor")
    sp.set("page", "1")
    router.push(`${path}?${sp.toString()}`)
  }
  const go = (p: number) => {
    const sp = new URLSearchParams(params.toString())
    sp.set("page", String(p))
    router.push(`${path}?${sp.toString()}`)
  }
  const totalPages = Math.max(1, Math.ceil(data.total / data.size))

  return (
    <div className="space-y-4">
      <div className="flex gap-2 items-end">
        <div>
          <label className="text-xs text-neutral-400 block mb-1">Action prefix</label>
          <Input value={prefix} onChange={(e) => setPrefix(e.target.value)} placeholder="webapp.settings" />
        </div>
        <div>
          <label className="text-xs text-neutral-400 block mb-1">Actor email</label>
          <Input value={actor} onChange={(e) => setActor(e.target.value)} />
        </div>
        <Button onClick={apply}>필터</Button>
      </div>
      <div className="rounded-md border border-neutral-800 text-sm">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>시각</TableHead>
              <TableHead>이벤트</TableHead>
              <TableHead>모드</TableHead>
              <TableHead>데이터</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.items.map((e) => (
              <TableRow key={e.id}>
                <TableCell className="font-mono text-xs">
                  {new Date(e.timestamp * 1000).toISOString().slice(0, 19).replace("T", " ")}
                </TableCell>
                <TableCell className="font-mono">{e.event_type}</TableCell>
                <TableCell>{e.mode}</TableCell>
                <TableCell className="font-mono text-xs truncate max-w-md">
                  {JSON.stringify(e.data)}
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
