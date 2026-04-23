"use client"

export function SortableTh<K extends string>({
  label,
  sortKey,
  currentSort,
  currentDir,
  onSort,
  className,
}: {
  label: string
  sortKey: K
  currentSort: K | null
  currentDir: "asc" | "desc"
  onSort: (key: K) => void
  className?: string
}) {
  const active = currentSort === sortKey
  const ariaSort: "ascending" | "descending" | "none" = active
    ? currentDir === "asc"
      ? "ascending"
      : "descending"
    : "none"
  const arrow = active ? (currentDir === "asc" ? " ▲" : " ▼") : ""
  return (
    <th
      scope="col"
      aria-sort={ariaSort}
      className={`cursor-pointer select-none ${className ?? ""}`}
      onClick={() => onSort(sortKey)}
    >
      {label}{arrow}
    </th>
  )
}
