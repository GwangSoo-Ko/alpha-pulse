import Link from "next/link"
import { Card } from "@/components/ui/card"

type Props = {
  items: { id: number; timestamp: number; event_type: string }[]
}

export function RecentAuditWidget({ items }: Props) {
  return (
    <Card className="p-4 space-y-2">
      <div className="flex justify-between items-center">
        <h3 className="font-medium">감사</h3>
        <Link href="/audit" className="text-xs text-blue-400 hover:underline">전체 →</Link>
      </div>
      {items.length === 0 ? (
        <p className="text-xs text-neutral-500">없음.</p>
      ) : (
        <ul className="space-y-1 text-xs font-mono text-neutral-400">
          {items.slice(0, 5).map((e) => (
            <li key={e.id} className="truncate">
              {new Date(e.timestamp * 1000).toISOString().slice(11, 19)} {e.event_type}
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}
