"use client"

import React from "react"

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
  const handleKey = (e: React.KeyboardEvent<HTMLTableCellElement>) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault()
      onSort(sortKey)
    }
  }
  return (
    <th
      scope="col"
      aria-sort={ariaSort}
      role="columnheader"
      tabIndex={0}
      className={`cursor-pointer select-none focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-emerald-500 ${className ?? ""}`}
      onClick={() => onSort(sortKey)}
      onKeyDown={handleKey}
    >
      {label}{arrow}
    </th>
  )
}
