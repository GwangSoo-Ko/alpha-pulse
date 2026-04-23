# Briefing 비교 뷰 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 임의의 두 날짜 브리핑을 side-by-side 비교하는 `/briefings/compare` 페이지 추가. `/briefings` 목록에서 체크박스로 2개 선택 → 비교 버튼 → 비교 페이지 이동.

**Architecture:** 신규 API 없음. 기존 `GET /api/v1/briefings/{date}` 를 `Promise.all` 로 두 번 호출해 SSR. 컴포넌트 3개(Hero / IndicatorDiffTable / TextCompareSection)로 결과를 렌더. 목록 테이블에 체크박스 컬럼 추가 + 비교 버튼 client component 신규.

**Tech Stack:** Next.js 15 App Router, shadcn/ui, Tailwind (프로젝트에 Vitest 미도입 → E2E 만 검증).

**Branch:** `feature/briefing-compare` (spec 커밋 `d00d3e5` 완료 상태)

**Spec:** `docs/superpowers/specs/2026-04-23-briefing-compare-design.md`

---

## File Structure

### Frontend (신규)
- **Create:** `webapp-ui/app/(dashboard)/briefings/compare/page.tsx` — SSR, searchParam 검증, Promise.all, 3 섹션 렌더
- **Create:** `webapp-ui/components/domain/briefing/briefing-compare-hero.tsx` — 3 grid (A / Δ / B), score+signal 비교
- **Create:** `webapp-ui/components/domain/briefing/indicator-diff-table.tsx` — 11개 지표 테이블, 정렬 가능
- **Create:** `webapp-ui/components/domain/briefing/text-compare-section.tsx` — daily_result_msg + commentary side-by-side
- **Create:** `webapp-ui/components/domain/briefing/briefings-compare-button.tsx` — 선택 상태 기반 비교 버튼 (client)

### Frontend (수정)
- **Modify:** `webapp-ui/components/domain/briefing/briefings-table.tsx` — 체크박스 컬럼 + 선택 상태 + CompareButton 연결

### E2E
- **Create:** `webapp-ui/e2e/briefings-compare.spec.ts`

### Backend
- 변경 없음. `/api/v1/briefings/{date}` 기존 사용.

---

## Conventions

- 프로젝트에 Vitest `.test.tsx` 미도입 → 각 컴포넌트는 `pnpm lint` + `pnpm tsc --noEmit` + 빌드로 검증, 최종 Playwright E2E 로 통합 검증
- 각 Task 완료마다 개별 커밋
- `@/` 절대 경로 import
- `signalStyle` 은 기존 `webapp-ui/lib/market-labels.ts` 재사용 (라벨/키 양쪽 모두 견고 처리 완료)
- `INDICATOR_LABELS` 도 같은 파일에서 재사용

---

## Task 1: BriefingCompareHero 컴포넌트

**Files:**
- Create: `webapp-ui/components/domain/briefing/briefing-compare-hero.tsx`

- [ ] **Step 1.1: 파일 생성**

```tsx
"use client"
import { Card } from "@/components/ui/card"
import { signalStyle } from "@/lib/market-labels"

export type BriefingCompareItem = {
  date: string
  score: number
  signal: string
} | null

function formatDate(yyyymmdd: string): string {
  if (yyyymmdd.length !== 8) return yyyymmdd
  return `${yyyymmdd.slice(0, 4)}-${yyyymmdd.slice(4, 6)}-${yyyymmdd.slice(6)}`
}

function sign(v: number): string {
  return v >= 0 ? "+" : ""
}

function deltaColor(d: number): string {
  if (d > 0) return "text-emerald-400"
  if (d < 0) return "text-rose-400"
  return "text-neutral-400"
}

function SideCard({
  label, item, aria,
}: {
  label: string
  item: BriefingCompareItem
  aria: string
}) {
  if (!item) {
    return (
      <Card className="p-5 text-center" aria-label={aria}>
        <p className="text-xs text-neutral-500 mb-2">{label}</p>
        <p className="text-sm text-neutral-400">해당 날짜 브리핑 없음</p>
      </Card>
    )
  }
  const style = signalStyle(item.signal)
  const textColor = style.badge.split(" ").find((c) => c.startsWith("text-"))
  return (
    <Card className="p-5 text-center" aria-label={aria}>
      <p className="text-xs text-neutral-500 mb-2">
        {label} · <span className="font-mono">{formatDate(item.date)}</span>
      </p>
      <div className={`text-4xl font-bold font-mono mb-2 ${textColor}`}>
        {sign(item.score)}{item.score.toFixed(1)}
      </div>
      <span className={`inline-block px-3 py-1 rounded-full text-xs ${style.badge}`}>
        {style.label}
      </span>
    </Card>
  )
}

export function BriefingCompareHero({
  a, b,
}: {
  a: BriefingCompareItem
  b: BriefingCompareItem
}) {
  const delta = a && b ? b.score - a.score : null
  return (
    <div className="grid gap-3 grid-cols-1 md:grid-cols-[1fr_auto_1fr] items-center">
      <SideCard label="A" item={a} aria="Briefing A" />
      <div className="text-center px-3">
        <p className="text-xs text-neutral-500 mb-1">Δ (B − A)</p>
        {delta === null ? (
          <p className="text-2xl font-mono text-neutral-500">—</p>
        ) : (
          <p className={`text-2xl font-bold font-mono ${deltaColor(delta)}`}>
            {sign(delta)}{delta.toFixed(1)}
          </p>
        )}
      </div>
      <SideCard label="B" item={b} aria="Briefing B" />
    </div>
  )
}
```

- [ ] **Step 1.2: 린트 + tsc 검증**

```bash
cd /Users/gwangsoo/alpha-pulse/webapp-ui
pnpm lint
pnpm tsc --noEmit 2>&1 | grep briefing-compare-hero || echo "no type errors"
```

Expected: no errors.

- [ ] **Step 1.3: 커밋**

```bash
cd /Users/gwangsoo/alpha-pulse
git add webapp-ui/components/domain/briefing/briefing-compare-hero.tsx
git commit -m "feat(webapp-ui): BriefingCompareHero — score/signal Δ 3열 카드"
```

---

## Task 2: IndicatorDiffTable 컴포넌트

**Files:**
- Create: `webapp-ui/components/domain/briefing/indicator-diff-table.tsx`

- [ ] **Step 2.1: 파일 생성**

```tsx
"use client"
import { useState } from "react"
import { Card } from "@/components/ui/card"
import { INDICATOR_LABELS } from "@/lib/market-labels"

type IndicatorRow = {
  key: string
  label: string
  a: number | null
  b: number | null
  delta: number | null
}

type SortKey = "label" | "a" | "b" | "delta"
type SortDir = "asc" | "desc"

function toNumberOrNull(v: unknown): number | null {
  if (typeof v === "number") return v
  return null
}

function buildRows(
  scoresA: Record<string, unknown>,
  scoresB: Record<string, unknown>,
): IndicatorRow[] {
  const keys = Array.from(new Set([...Object.keys(scoresA), ...Object.keys(scoresB)]))
  return keys.map((key) => {
    const a = toNumberOrNull(scoresA[key])
    const b = toNumberOrNull(scoresB[key])
    const delta = a !== null && b !== null ? b - a : null
    return {
      key,
      label: INDICATOR_LABELS[key] ?? key,
      a, b, delta,
    }
  })
}

function compare(
  x: IndicatorRow, y: IndicatorRow, by: SortKey, dir: SortDir,
): number {
  let xv: number | string | null
  let yv: number | string | null
  if (by === "label") {
    xv = x.label
    yv = y.label
  } else if (by === "delta") {
    // |delta| 기준, null 은 맨 아래
    xv = x.delta === null ? null : Math.abs(x.delta)
    yv = y.delta === null ? null : Math.abs(y.delta)
  } else {
    xv = x[by]
    yv = y[by]
  }
  // null 은 항상 맨 아래 (정렬 방향 무관)
  if (xv === null && yv === null) return 0
  if (xv === null) return 1
  if (yv === null) return -1
  if (xv < yv) return dir === "asc" ? -1 : 1
  if (xv > yv) return dir === "asc" ? 1 : -1
  return 0
}

function ScoreCell({ v }: { v: number | null }) {
  if (v === null) return <span className="text-neutral-600">—</span>
  const cls = v > 0 ? "text-emerald-400" : v < 0 ? "text-rose-400" : "text-neutral-400"
  return (
    <span className={`font-mono tabular-nums ${cls}`}>
      {v >= 0 ? "+" : ""}{v.toFixed(1)}
    </span>
  )
}

function DeltaCell({ v }: { v: number | null }) {
  if (v === null) return <span className="text-neutral-600">—</span>
  if (v === 0) return <span className="text-neutral-400 font-mono">0.0 ·</span>
  const cls = v > 0 ? "text-emerald-400" : "text-rose-400"
  const arrow = v > 0 ? "↑" : "↓"
  return (
    <span className={`font-mono tabular-nums font-semibold ${cls}`}>
      {v > 0 ? "+" : ""}{v.toFixed(1)} {arrow}
    </span>
  )
}

export function IndicatorDiffTable({
  scoresA, scoresB, dateALabel, dateBLabel,
}: {
  scoresA: Record<string, unknown>
  scoresB: Record<string, unknown>
  dateALabel: string
  dateBLabel: string
}) {
  const [sortBy, setSortBy] = useState<SortKey>("delta")
  const [dir, setDir] = useState<SortDir>("desc")

  const rows = buildRows(scoresA, scoresB)
  const sorted = [...rows].sort((x, y) => compare(x, y, sortBy, dir))

  function toggleSort(key: SortKey) {
    if (sortBy === key) {
      setDir(dir === "asc" ? "desc" : "asc")
    } else {
      setSortBy(key)
      setDir(key === "delta" ? "desc" : "asc")
    }
  }

  if (rows.length === 0) {
    return (
      <Card className="p-6">
        <p className="text-sm text-neutral-500">지표 데이터 없음</p>
      </Card>
    )
  }

  const indicator = (key: SortKey) =>
    sortBy === key ? (dir === "asc" ? " ▲" : " ▼") : ""

  return (
    <Card className="p-4 overflow-x-auto">
      <table className="w-full text-sm border-collapse">
        <thead>
          <tr className="text-left text-xs text-neutral-400">
            <th className="px-3 py-2 cursor-pointer select-none"
                onClick={() => toggleSort("label")}>
              지표{indicator("label")}
            </th>
            <th className="px-3 py-2 text-right cursor-pointer select-none"
                onClick={() => toggleSort("a")}>
              {dateALabel}{indicator("a")}
            </th>
            <th className="px-3 py-2 text-right cursor-pointer select-none"
                onClick={() => toggleSort("b")}>
              {dateBLabel}{indicator("b")}
            </th>
            <th className="px-3 py-2 text-right cursor-pointer select-none"
                onClick={() => toggleSort("delta")}>
              Δ{indicator("delta")}
            </th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((r) => (
            <tr key={r.key} className="border-t border-neutral-800 hover:bg-neutral-900">
              <td className="px-3 py-2">{r.label}</td>
              <td className="px-3 py-2 text-right"><ScoreCell v={r.a} /></td>
              <td className="px-3 py-2 text-right"><ScoreCell v={r.b} /></td>
              <td className="px-3 py-2 text-right"><DeltaCell v={r.delta} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  )
}
```

- [ ] **Step 2.2: 린트 + tsc**

```bash
cd /Users/gwangsoo/alpha-pulse/webapp-ui
pnpm lint
pnpm tsc --noEmit 2>&1 | grep indicator-diff-table || echo "no type errors"
```

- [ ] **Step 2.3: 커밋**

```bash
cd /Users/gwangsoo/alpha-pulse
git add webapp-ui/components/domain/briefing/indicator-diff-table.tsx
git commit -m "feat(webapp-ui): IndicatorDiffTable — 11개 지표 비교 + 정렬"
```

---

## Task 3: TextCompareSection 컴포넌트

**Files:**
- Create: `webapp-ui/components/domain/briefing/text-compare-section.tsx`

- [ ] **Step 3.1: 파일 생성**

```tsx
"use client"
import { Card } from "@/components/ui/card"

type TextCompareItem = {
  date: string
  daily_result_msg: string
  commentary: string | null
} | null

function formatDate(yyyymmdd: string): string {
  if (yyyymmdd.length !== 8) return yyyymmdd
  return `${yyyymmdd.slice(0, 4)}-${yyyymmdd.slice(4, 6)}-${yyyymmdd.slice(6)}`
}

function Column({
  title, item,
}: {
  title: string
  item: TextCompareItem
}) {
  if (!item) {
    return (
      <Card className="p-4">
        <p className="text-xs text-neutral-500 mb-2">{title}</p>
        <p className="text-sm text-neutral-500">데이터 없음</p>
      </Card>
    )
  }
  return (
    <Card className="p-4 space-y-4">
      <p className="text-xs text-neutral-500">
        {title} · <span className="font-mono">{formatDate(item.date)}</span>
      </p>
      <section className="space-y-1">
        <p className="text-[11px] uppercase text-neutral-400 tracking-wide">
          daily_result_msg
        </p>
        {item.daily_result_msg ? (
          <pre className="text-xs text-neutral-300 whitespace-pre-wrap rounded border border-neutral-800 bg-neutral-900 p-3">
            {item.daily_result_msg}
          </pre>
        ) : (
          <p className="text-sm text-neutral-600">—</p>
        )}
      </section>
      <section className="space-y-1">
        <p className="text-[11px] uppercase text-neutral-400 tracking-wide">
          commentary
        </p>
        {item.commentary ? (
          <p className="text-sm text-neutral-300 whitespace-pre-wrap leading-relaxed">
            {item.commentary}
          </p>
        ) : (
          <p className="text-sm text-neutral-600">—</p>
        )}
      </section>
    </Card>
  )
}

export function TextCompareSection({
  a, b,
}: {
  a: TextCompareItem
  b: TextCompareItem
}) {
  return (
    <div className="grid gap-4 grid-cols-1 md:grid-cols-2">
      <Column title="A" item={a} />
      <Column title="B" item={b} />
    </div>
  )
}
```

- [ ] **Step 3.2: 린트 + tsc**

```bash
cd /Users/gwangsoo/alpha-pulse/webapp-ui
pnpm lint
pnpm tsc --noEmit 2>&1 | grep text-compare-section || echo "no type errors"
```

- [ ] **Step 3.3: 커밋**

```bash
cd /Users/gwangsoo/alpha-pulse
git add webapp-ui/components/domain/briefing/text-compare-section.tsx
git commit -m "feat(webapp-ui): TextCompareSection — daily_result_msg + commentary 2열"
```

---

## Task 4: Compare Page (SSR + 에러 처리)

**Files:**
- Create: `webapp-ui/app/(dashboard)/briefings/compare/page.tsx`

- [ ] **Step 4.1: 파일 생성**

```tsx
import Link from "next/link"
import { cookies } from "next/headers"
import { notFound, redirect } from "next/navigation"
import { ApiError, apiFetch } from "@/lib/api-client"
import { Button } from "@/components/ui/button"
import { BriefingCompareHero } from "@/components/domain/briefing/briefing-compare-hero"
import { IndicatorDiffTable } from "@/components/domain/briefing/indicator-diff-table"
import { TextCompareSection } from "@/components/domain/briefing/text-compare-section"

export const dynamic = "force-dynamic"

type BriefingDetail = {
  date: string
  created_at: number
  pulse_result: { score?: number; signal?: string; indicator_scores?: Record<string, unknown> } & Record<string, unknown>
  daily_result_msg: string
  commentary: string | null
}

type Props = { searchParams: Promise<{ a?: string; b?: string }> }

const DATE_RE = /^\d{8}$/

async function load(date: string, cookieHeader: string): Promise<BriefingDetail | null> {
  try {
    return await apiFetch<BriefingDetail>(`/api/v1/briefings/${date}`, {
      headers: { cookie: cookieHeader }, cache: "no-store",
    })
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) return null
    throw e
  }
}

function formatDateShort(yyyymmdd: string): string {
  return `${yyyymmdd.slice(4, 6)}-${yyyymmdd.slice(6)}`
}

export default async function BriefingComparePage({ searchParams }: Props) {
  const { a, b } = await searchParams
  if (!a || !b) redirect("/briefings")
  if (!DATE_RE.test(a) || !DATE_RE.test(b)) notFound()
  if (a === b) redirect(`/briefings/${a}`)

  const cookieStore = await cookies()
  const cookieHeader = cookieStore.getAll().map((c) => `${c.name}=${c.value}`).join("; ")

  const [aDetail, bDetail] = await Promise.all([load(a, cookieHeader), load(b, cookieHeader)])

  if (!aDetail && !bDetail) {
    return (
      <div className="space-y-4">
        <Link href="/briefings">
          <Button variant="outline" size="sm">← 목록으로</Button>
        </Link>
        <h1 className="text-2xl font-semibold">브리핑 비교</h1>
        <p className="text-sm text-neutral-500">두 날짜 모두 브리핑이 없습니다.</p>
      </div>
    )
  }

  const aItem = aDetail
    ? { date: a, score: Number(aDetail.pulse_result?.score ?? 0), signal: String(aDetail.pulse_result?.signal ?? "neutral") }
    : null
  const bItem = bDetail
    ? { date: b, score: Number(bDetail.pulse_result?.score ?? 0), signal: String(bDetail.pulse_result?.signal ?? "neutral") }
    : null

  const scoresA = (aDetail?.pulse_result?.indicator_scores ?? {}) as Record<string, unknown>
  const scoresB = (bDetail?.pulse_result?.indicator_scores ?? {}) as Record<string, unknown>

  const aText = aDetail
    ? { date: a, daily_result_msg: aDetail.daily_result_msg ?? "", commentary: aDetail.commentary }
    : null
  const bText = bDetail
    ? { date: b, daily_result_msg: bDetail.daily_result_msg ?? "", commentary: bDetail.commentary }
    : null

  return (
    <div className="space-y-6">
      <Link href="/briefings">
        <Button variant="outline" size="sm">← 목록으로</Button>
      </Link>
      <h1 className="text-2xl font-semibold">브리핑 비교</h1>
      <BriefingCompareHero a={aItem} b={bItem} />
      <IndicatorDiffTable
        scoresA={scoresA}
        scoresB={scoresB}
        dateALabel={formatDateShort(a)}
        dateBLabel={formatDateShort(b)}
      />
      <TextCompareSection a={aText} b={bText} />
    </div>
  )
}
```

- [ ] **Step 4.2: 린트 + tsc**

```bash
cd /Users/gwangsoo/alpha-pulse/webapp-ui
pnpm lint
pnpm tsc --noEmit 2>&1 | grep "briefings/compare" || echo "no type errors"
```

- [ ] **Step 4.3: 커밋**

```bash
cd /Users/gwangsoo/alpha-pulse
git add webapp-ui/app/\(dashboard\)/briefings/compare/page.tsx
git commit -m "feat(webapp-ui): /briefings/compare 페이지 — SSR + 3 섹션 조립"
```

---

## Task 5: BriefingsCompareButton + 목록 테이블 체크박스

**Files:**
- Create: `webapp-ui/components/domain/briefing/briefings-compare-button.tsx`
- Modify: `webapp-ui/components/domain/briefing/briefings-table.tsx` — 체크박스 컬럼 + 선택 상태

- [ ] **Step 5.1: `briefings-compare-button.tsx` 생성**

```tsx
"use client"
import Link from "next/link"
import { Button } from "@/components/ui/button"

export function BriefingsCompareButton({ selected }: { selected: string[] }) {
  if (selected.length !== 2) {
    return (
      <Button size="sm" variant="outline" disabled>
        비교하기 {selected.length > 0 && `(${selected.length}/2)`}
      </Button>
    )
  }
  const [a, b] = [...selected].sort()
  return (
    <Link href={`/briefings/compare?a=${a}&b=${b}`}>
      <Button size="sm" variant="default">비교하기</Button>
    </Link>
  )
}
```

- [ ] **Step 5.2: `briefings-table.tsx` 수정**

파일 전체를 다음으로 교체:

```tsx
"use client"
import Link from "next/link"
import { useState } from "react"
import { useSearchParams } from "next/navigation"
import { signalStyle } from "@/lib/market-labels"
import { Button } from "@/components/ui/button"
import { BriefingsCompareButton } from "./briefings-compare-button"
import type { BriefingSummary } from "./briefing-summary-row"

type ListData = {
  items: BriefingSummary[]
  page: number
  size: number
  total: number
}

function pageHref(sp: URLSearchParams, page: number): string {
  const next = new URLSearchParams(sp)
  if (page > 1) next.set("page", String(page))
  else next.delete("page")
  return `/briefings?${next}`
}

function formatDate(yyyymmdd: string): string {
  return `${yyyymmdd.slice(0, 4)}-${yyyymmdd.slice(4, 6)}-${yyyymmdd.slice(6)}`
}

export function BriefingsTable({ data }: { data: ListData }) {
  const sp = useSearchParams()
  const spParams = new URLSearchParams(sp?.toString() ?? "")
  const totalPages = Math.max(1, Math.ceil(data.total / data.size))
  const [selected, setSelected] = useState<string[]>([])

  function toggle(date: string) {
    setSelected((prev) => {
      if (prev.includes(date)) {
        return prev.filter((d) => d !== date)
      }
      if (prev.length >= 2) {
        // FIFO: 가장 오래 선택한 것 제거
        return [...prev.slice(1), date]
      }
      return [...prev, date]
    })
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-sm text-neutral-400">
          전체 {data.total}건 · 페이지 {data.page}/{totalPages}
        </p>
        <BriefingsCompareButton selected={selected} />
      </div>
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="text-left text-xs text-neutral-400">
            <th className="px-3 py-2 w-8"></th>
            <th className="px-3 py-2">날짜</th>
            <th className="px-3 py-2">점수</th>
            <th className="px-3 py-2">시그널</th>
            <th className="px-3 py-2">종합</th>
          </tr>
        </thead>
        <tbody>
          {data.items.map((i) => {
            const style = signalStyle(i.signal)
            const sign = i.score >= 0 ? "+" : ""
            const checked = selected.includes(i.date)
            return (
              <tr key={i.date} className="border-t border-neutral-800 hover:bg-neutral-900">
                <td className="px-3 py-2">
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => toggle(i.date)}
                    aria-label={`${i.date} 선택`}
                    className="cursor-pointer"
                  />
                </td>
                <td className="px-3 py-2">
                  <Link
                    href={`/briefings/${i.date}`}
                    className="text-blue-400 hover:underline font-mono"
                  >
                    {formatDate(i.date)}
                  </Link>
                </td>
                <td className="px-3 py-2 text-sm font-mono tabular-nums">
                  {sign}{i.score.toFixed(1)}
                </td>
                <td className="px-3 py-2">
                  <span className={`inline-block px-2 py-0.5 rounded-full text-xs ${style.badge}`}>
                    {style.label}
                  </span>
                </td>
                <td className="px-3 py-2 text-sm">
                  {i.has_synthesis ? "✓" : "✗"}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
      {totalPages > 1 && (
        <div className="flex justify-center gap-1">
          {data.page > 1 ? (
            <Link href={pageHref(spParams, data.page - 1)}>
              <Button size="sm" variant="outline">← 이전</Button>
            </Link>
          ) : (
            <Button size="sm" variant="outline" disabled>← 이전</Button>
          )}
          <span className="px-3 py-1 text-sm">{data.page} / {totalPages}</span>
          {data.page < totalPages ? (
            <Link href={pageHref(spParams, data.page + 1)}>
              <Button size="sm" variant="outline">다음 →</Button>
            </Link>
          ) : (
            <Button size="sm" variant="outline" disabled>다음 →</Button>
          )}
        </div>
      )}
    </div>
  )
}
```

**주의**: 기존에는 `BriefingSummaryRow` 를 import 해서 행을 렌더했지만, 체크박스 통합을 위해 테이블 내에 인라인으로 row 를 구성한다. `briefing-summary-row.tsx` 는 `BriefingSummary` 타입만 re-export 용도로 남겨 둔다 (`type` import 만 유지).

- [ ] **Step 5.3: 린트 + tsc**

```bash
cd /Users/gwangsoo/alpha-pulse/webapp-ui
pnpm lint
pnpm tsc --noEmit 2>&1 | grep "briefings-table\|briefings-compare-button" || echo "no type errors"
```

- [ ] **Step 5.4: 빌드 검증**

```bash
pnpm build 2>&1 | tail -5
```
Expected: success.

- [ ] **Step 5.5: 커밋**

```bash
cd /Users/gwangsoo/alpha-pulse
git add webapp-ui/components/domain/briefing/briefings-compare-button.tsx webapp-ui/components/domain/briefing/briefings-table.tsx
git commit -m "feat(webapp-ui): 브리핑 목록 체크박스 + 비교 버튼"
```

---

## Task 6: Playwright E2E 스모크

**Files:**
- Create: `webapp-ui/e2e/briefings-compare.spec.ts`

- [ ] **Step 6.1: 파일 생성**

```typescript
import { expect, test } from "@playwright/test"

const EMAIL = process.env.E2E_ADMIN_EMAIL ?? "test@example.com"
const PASSWORD = process.env.E2E_ADMIN_PASSWORD ?? "test-password-12!"

test.describe("Briefing Compare", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/login")
    await page.fill('input[type="email"]', EMAIL)
    await page.fill('input[type="password"]', PASSWORD)
    await page.click('button[type="submit"]')
    await expect(page).toHaveURL(/\/(?!login)/)
  })

  test("체크박스 0개면 비교 버튼 disabled", async ({ page }) => {
    await page.goto("/briefings")
    const btn = page.getByRole("button", { name: /비교하기/ })
    await expect(btn).toBeDisabled()
  })

  test("같은 날짜 URL 직접 진입 → 상세 리다이렉트", async ({ page }) => {
    await page.goto("/briefings/compare?a=20260421&b=20260421")
    await expect(page).toHaveURL(/\/briefings\/20260421$/)
  })

  test("a 파라미터 누락 → 목록으로 리다이렉트", async ({ page }) => {
    await page.goto("/briefings/compare?b=20260421")
    await expect(page).toHaveURL(/\/briefings($|\?)/)
  })

  test("두 날짜 모두 존재하지 않는 경우 empty state", async ({ page }) => {
    await page.goto("/briefings/compare?a=19990101&b=19990102")
    await expect(
      page.getByText("두 날짜 모두 브리핑이 없습니다"),
    ).toBeVisible()
  })
})
```

- [ ] **Step 6.2: 린트**

```bash
cd /Users/gwangsoo/alpha-pulse/webapp-ui
pnpm lint
```

- [ ] **Step 6.3: 커밋**

```bash
cd /Users/gwangsoo/alpha-pulse
git add webapp-ui/e2e/briefings-compare.spec.ts
git commit -m "test(webapp-ui): Briefing Compare E2E 스모크"
```

---

## Task 7: 전체 CI Gate 검증

**목적:** pytest 회귀 없음 + ruff clean + pnpm build 성공 확인.

- [ ] **Step 7.1: pytest**

```bash
cd /Users/gwangsoo/alpha-pulse
pytest tests/ -x -q --tb=short 2>&1 | tail -5
```
Expected: 1255+ passed (이번 변경은 BE 영향 없음).

- [ ] **Step 7.2: ruff**

```bash
ruff check alphapulse/ 2>&1 | tail -3
```
Expected: `All checks passed!`

- [ ] **Step 7.3: FE 빌드**

```bash
cd /Users/gwangsoo/alpha-pulse/webapp-ui
pnpm lint
pnpm build 2>&1 | tail -10
```
Expected: 빌드 성공, `/briefings/compare` 라우트 목록에 등장.

- [ ] **Step 7.4: 커밋 없음** — 모든 검증 통과 후 병합 단계로

---

## Spec Coverage 체크

- [x] §2 레이아웃 → Task 4 (page.tsx) 에서 조립
- [x] §3.1 목록 체크박스 + 비교 버튼 → Task 5
- [x] §3.2 비교 페이지 SSR + validation → Task 4
- [x] §3.3 BriefingCompareHero → Task 1
- [x] §3.4 IndicatorDiffTable (정렬, |Δ| desc 기본) → Task 2
- [x] §3.5 TextCompareSection → Task 3
- [x] §4 데이터 흐름 (Promise.all, 404 → null) → Task 4
- [x] §5 에러 처리 (redirect / notFound / 부분 렌더 / empty) → Task 4, Task 1~3 빈 상태
- [x] §6.1 백엔드 테스트 변경 없음 → 확인됨
- [x] §6.2 FE 단위 테스트 생략 → 확인됨
- [x] §6.3 Playwright E2E → Task 6
- [x] §7 성공 기준 → Task 7 CI Gate

## Implementation Notes

1. **순서 준수**: Task 1~3 (컴포넌트 독립) → Task 4 (페이지 조립, 1~3 필요) → Task 5 (목록 수정, 독립) → Task 6 (E2E) → Task 7 (검증).
2. **Task 5 Step 5.2 비파괴**: 기존 `briefing-summary-row.tsx` 는 `BriefingSummary` 타입 export 를 위해 남긴다. `BriefingSummaryRow` 컴포넌트는 이제 테이블에서 직접 안 쓰이지만 다른 import 가 있는지 grep 으로 확인:
   ```bash
   grep -rn "BriefingSummaryRow" webapp-ui/ --include="*.tsx" --include="*.ts"
   ```
   결과에 `briefing-summary-row.tsx` 자신과 `briefings-table.tsx`(수정 후 없음) 외 다른 참조가 있으면 그대로 둠. 없으면 `BriefingSummaryRow` export 만 제거하고 타입은 유지.
3. **signalStyle 입력**: Hero 카드의 `signal` 은 `pulse_result.signal` 그대로 사용. 기존 Korean label 이든 enum key 든 `signalStyle()` 이 normalize 해 줌 (tech debt #5 로 견고화됨).
4. **FIFO 선택**: 3번째 클릭 시 가장 오래된 것 제거. 별도 알림 없음 (자연스러운 UX).
5. **정렬 기준 |Δ|**: 기본 정렬은 `|delta|` 절대값 내림차순. `delta === null` 항목은 항상 맨 아래.
6. **Indicator 정렬 재클릭**: 같은 컬럼 재클릭 시 방향 토글. 다른 컬럼 클릭 시 기본 방향 (delta 는 desc, 나머지는 asc).
7. **URL 정규화**: Task 5 의 CompareButton 은 `[...selected].sort()` 로 날짜 문자열 비교 → 더 오래된 게 a, 최신이 b 로 배치. YYYYMMDD 는 문자열 정렬 = 날짜 정렬.
