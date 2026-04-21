"use client"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"

export function ReportMarkdownView({ body }: { body: string }) {
  return (
    <article className="prose prose-invert max-w-none">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{body}</ReactMarkdown>
    </article>
  )
}
