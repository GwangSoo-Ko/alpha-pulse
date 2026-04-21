import Link from "next/link"

const TABS: { slug: string; label: string }[] = [
  { slug: "api-keys", label: "API 키" },
  { slug: "risk-limits", label: "리스크 리밋" },
  { slug: "notifications", label: "알림" },
  { slug: "backtest-defaults", label: "백테스트 기본값" },
]

export function SettingsTabs({ active }: { active: string }) {
  return (
    <nav className="flex gap-2 border-b border-neutral-800 pb-2">
      {TABS.map((t) => (
        <Link
          key={t.slug}
          href={`/settings/${t.slug}`}
          className={
            "px-3 py-1 text-sm rounded " +
            (active === t.slug
              ? "bg-neutral-800 text-neutral-100"
              : "text-neutral-400 hover:text-neutral-200")
          }
        >
          {t.label}
        </Link>
      ))}
    </nav>
  )
}
