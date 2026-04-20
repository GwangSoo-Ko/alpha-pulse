import Link from "next/link"

const ITEMS = [
  { href: "/backtest", label: "Backtest" },
  { href: "/portfolio", label: "Portfolio", disabled: true },
  { href: "/risk", label: "Risk", disabled: true },
  { href: "/market", label: "Market", disabled: true },
]

export function Sidebar() {
  return (
    <aside className="w-56 border-r border-neutral-800 p-4">
      <div className="mb-6 text-lg font-bold">AlphaPulse</div>
      <nav className="space-y-1">
        {ITEMS.map((it) => (
          <Link
            key={it.href}
            href={it.disabled ? "#" : it.href}
            className={
              "block rounded px-3 py-2 text-sm " +
              (it.disabled
                ? "cursor-not-allowed text-neutral-600"
                : "hover:bg-neutral-800")
            }
          >
            {it.label}
            {it.disabled && <span className="ml-2 text-xs">(soon)</span>}
          </Link>
        ))}
      </nav>
    </aside>
  )
}
