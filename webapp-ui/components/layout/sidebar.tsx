import Link from "next/link"

const ITEMS: { href: string; label: string }[] = [
  { href: "/", label: "홈" },
  { href: "/market/pulse", label: "시황" },
  { href: "/content", label: "콘텐츠" },
  { href: "/portfolio", label: "포트폴리오" },
  { href: "/risk", label: "리스크" },
  { href: "/screening", label: "스크리닝" },
  { href: "/backtest", label: "백테스트" },
  { href: "/data", label: "데이터" },
  { href: "/settings", label: "설정" },
  { href: "/audit", label: "감사" },
]

export function Sidebar() {
  return (
    <aside className="w-56 border-r border-neutral-800 p-4">
      <div className="mb-6 text-lg font-bold">AlphaPulse</div>
      <nav className="space-y-1">
        {ITEMS.map((it) => (
          <Link
            key={it.href}
            href={it.href}
            className="block rounded px-3 py-2 text-sm hover:bg-neutral-800"
          >
            {it.label}
          </Link>
        ))}
      </nav>
    </aside>
  )
}
