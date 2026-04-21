"use client"
import { useRouter, useSearchParams } from "next/navigation"
import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"

export function ReportsFilterBar({ categories }: { categories: string[] }) {
  const router = useRouter()
  const params = useSearchParams()

  const initialSelected = new Set(params.getAll("category"))
  const [selected, setSelected] = useState<Set<string>>(initialSelected)
  const [from, setFrom] = useState(params.get("from") ?? "")
  const [to, setTo] = useState(params.get("to") ?? "")
  const [q, setQ] = useState(params.get("q") ?? "")

  const toggleCategory = (cat: string) => {
    const next = new Set(selected)
    if (next.has(cat)) next.delete(cat)
    else next.add(cat)
    setSelected(next)
  }

  const apply = () => {
    const sp = new URLSearchParams()
    selected.forEach((c) => sp.append("category", c))
    if (from) sp.set("from", from)
    if (to) sp.set("to", to)
    if (q) sp.set("q", q)
    router.push(`/content?${sp}`)
  }

  const clear = () => {
    setSelected(new Set())
    setFrom("")
    setTo("")
    setQ("")
    router.push("/content")
  }

  return (
    <div className="space-y-3 rounded border border-neutral-800 bg-neutral-900 p-4">
      <div>
        <Label className="text-xs text-neutral-400">카테고리</Label>
        <div className="mt-1 flex flex-wrap gap-2">
          {categories.length === 0 && (
            <span className="text-sm text-neutral-500">카테고리 없음</span>
          )}
          {categories.map((cat) => (
            <label key={cat} className="inline-flex items-center gap-1 text-sm">
              <input
                type="checkbox"
                checked={selected.has(cat)}
                onChange={() => toggleCategory(cat)}
                className="h-4 w-4"
              />
              {cat}
            </label>
          ))}
        </div>
      </div>
      <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
        <div>
          <Label htmlFor="from" className="text-xs text-neutral-400">
            발행일 시작 (YYYYMMDD)
          </Label>
          <Input
            id="from"
            value={from}
            onChange={(e) => setFrom(e.target.value)}
            placeholder="20260301"
          />
        </div>
        <div>
          <Label htmlFor="to" className="text-xs text-neutral-400">
            발행일 종료 (YYYYMMDD)
          </Label>
          <Input
            id="to"
            value={to}
            onChange={(e) => setTo(e.target.value)}
            placeholder="20260430"
          />
        </div>
        <div>
          <Label htmlFor="q" className="text-xs text-neutral-400">
            제목 검색
          </Label>
          <Input
            id="q"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="검색어"
          />
        </div>
      </div>
      <div className="flex gap-2">
        <Button size="sm" onClick={apply}>
          적용
        </Button>
        <Button size="sm" variant="outline" onClick={clear}>
          초기화
        </Button>
      </div>
    </div>
  )
}
