import Link from "next/link"
import { cookies } from "next/headers"
import { notFound } from "next/navigation"
import { ApiError, apiFetch } from "@/lib/api-client"
import { ReportMarkdownView } from "@/components/domain/content/report-markdown-view"
import { Button } from "@/components/ui/button"

export const dynamic = "force-dynamic"

type Props = { params: Promise<{ filename: string }> }

type ReportDetail = {
  filename: string
  title: string
  category: string
  published: string
  analyzed_at: string
  source: string
  source_tag: string
  body: string
}

// Next.js 15 dynamic route params 에는 URL-encoded 또는 decoded 가 혼재해
// 올 수 있음. decode → encode 로 정규화 idempotent 처리.
function safeEncode(name: string): string {
  let decoded = name
  try { decoded = decodeURIComponent(name) } catch { decoded = name }
  return encodeURIComponent(decoded)
}

// 상단에 원문 링크 버튼이 있으므로 본문 말미의 "<details>원문 전문</details>"
// 블록은 중복. 웹 UI 에서만 잘라내어 AI 분석 내용만 노출한다.
// (ReportWriter 의 파일 저장 포맷은 유지 — CLI 사용자는 영향 없음.)
function stripOriginalSection(body: string): string {
  const idx = body.indexOf("<details>")
  if (idx < 0) return body
  return body.slice(0, idx).replace(/\n*---\s*\n*$/, "").trimEnd()
}

export default async function ReportDetailPage({ params }: Props) {
  const { filename } = await params
  const cookieStore = await cookies()
  const h = {
    cookie: cookieStore.getAll().map((c) => `${c.name}=${c.value}`).join("; "),
  }

  try {
    const detail = await apiFetch<ReportDetail>(
      `/api/v1/content/reports/${safeEncode(filename)}`,
      { headers: h, cache: "no-store" },
    )
    return (
      <div className="space-y-4">
        <Link href="/content">
          <Button variant="outline" size="sm">← 콘텐츠 목록으로</Button>
        </Link>
        <header className="space-y-2">
          <h1 className="text-2xl font-semibold">{detail.title}</h1>
          <div className="flex flex-wrap items-center gap-2 text-sm text-neutral-400">
            <span className="inline-block rounded bg-neutral-800 px-2 py-0.5 text-xs">
              {detail.category}
            </span>
            {detail.published && <span>발행 {detail.published}</span>}
            {detail.analyzed_at && <span>· 분석 {detail.analyzed_at}</span>}
            {detail.source && (
              <a
                href={detail.source}
                target="_blank" rel="noopener noreferrer"
                className="text-blue-400 hover:underline"
              >
                원문 →
              </a>
            )}
          </div>
        </header>
        <ReportMarkdownView body={stripOriginalSection(detail.body)} />
      </div>
    )
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound()
    throw e
  }
}
