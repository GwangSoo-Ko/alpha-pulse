"use client"

type Article = {
  title?: string
  url?: string
  source?: string
  published_at?: string
  [key: string]: unknown
}

export function BriefingNewsSection({
  news,
}: {
  news: { articles?: Article[] }
}) {
  const articles = news.articles ?? []
  return (
    <section className="space-y-2">
      <h2 className="text-lg font-semibold">장 후 뉴스</h2>
      {articles.length === 0 ? (
        <p className="text-sm text-neutral-500">수집된 뉴스 없음</p>
      ) : (
        <ul className="space-y-1.5">
          {articles.map((a, i) => (
            <li key={i} className="text-sm">
              {a.url ? (
                <a
                  href={a.url} target="_blank" rel="noopener noreferrer"
                  className="text-blue-400 hover:underline"
                >
                  {a.title || a.url}
                </a>
              ) : (
                <span>{a.title || "(제목 없음)"}</span>
              )}
              {a.source && (
                <span className="ml-2 text-xs text-neutral-500">· {a.source}</span>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
