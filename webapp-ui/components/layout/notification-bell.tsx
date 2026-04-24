"use client"
import Link from "next/link"
import { useEffect, useState } from "react"

import { apiFetch, apiMutate } from "@/lib/api-client"

export type Notification = {
  id: number
  kind: "job" | "briefing" | "risk" | "pulse"
  level: "info" | "warn" | "error"
  title: string
  body: string | null
  link: string | null
  created_at: number
  is_read: number
}

const POLL_INTERVAL_MS = 30_000
const LIST_LIMIT = 20

function formatTimeAgo(epoch: number): string {
  const diff = Date.now() / 1000 - epoch
  if (diff < 60) return "방금 전"
  if (diff < 3600) return `${Math.floor(diff / 60)}분 전`
  if (diff < 86400) return `${Math.floor(diff / 3600)}시간 전`
  return `${Math.floor(diff / 86400)}일 전`
}

function levelColor(level: string): string {
  if (level === "error") return "text-rose-400"
  if (level === "warn") return "text-amber-400"
  return "text-emerald-400"
}

export function NotificationBell() {
  const [count, setCount] = useState(0)
  const [items, setItems] = useState<Notification[]>([])
  const [open, setOpen] = useState(false)

  useEffect(() => {
    let cancelled = false
    async function tick() {
      try {
        const r = await apiFetch<{ count: number }>(
          "/api/v1/notifications/unread-count",
        )
        if (!cancelled) setCount(r.count)
      } catch {
        // ignore transient errors — 다음 폴링에서 재시도
      }
    }
    tick()
    const id = setInterval(tick, POLL_INTERVAL_MS)
    return () => {
      cancelled = true
      clearInterval(id)
    }
  }, [])

  async function openDropdown() {
    setOpen(true)
    try {
      const r = await apiFetch<{ items: Notification[] }>(
        `/api/v1/notifications?limit=${LIST_LIMIT}`,
      )
      setItems(r.items)
    } catch {
      // ignore — 드롭다운은 이미 열림, 빈 상태 표시
    }
  }

  async function markAllRead() {
    try {
      await apiMutate("/api/v1/notifications/read-all", "POST")
      setCount(0)
      setItems((prev) => prev.map((i) => ({ ...i, is_read: 1 })))
    } catch {
      // ignore
    }
  }

  async function handleItemClick(n: Notification) {
    if (!n.is_read) {
      try {
        await apiMutate(
          `/api/v1/notifications/${n.id}/read`,
          "POST",
        )
        setCount((c) => Math.max(0, c - 1))
        setItems((prev) =>
          prev.map((i) => (i.id === n.id ? { ...i, is_read: 1 } : i)),
        )
      } catch {
        // ignore — 그래도 드롭다운은 닫아 사용자가 navigate 가능
      }
    }
    setOpen(false)
  }

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => (open ? setOpen(false) : openDropdown())}
        aria-label={`알림 ${count}건`}
        className="relative p-2 rounded hover:bg-neutral-800 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-500"
      >
        <span className="text-lg" aria-hidden="true">🔔</span>
        {count > 0 && (
          <span className="absolute -top-1 -right-1 bg-rose-500 text-white text-[10px] rounded-full min-w-[16px] h-[16px] px-1 flex items-center justify-center">
            {count > 99 ? "99+" : count}
          </span>
        )}
      </button>
      {open && (
        <div className="absolute right-0 top-full mt-2 w-80 rounded border border-neutral-800 bg-neutral-900 shadow-lg z-50">
          <div className="flex items-center justify-between px-3 py-2 border-b border-neutral-800">
            <span className="text-sm font-semibold">알림</span>
            {count > 0 && (
              <button
                type="button"
                onClick={markAllRead}
                className="text-xs text-neutral-400 hover:text-neutral-200"
              >
                모두 읽음
              </button>
            )}
          </div>
          <ul className="max-h-96 overflow-y-auto">
            {items.length === 0 ? (
              <li className="px-3 py-4 text-sm text-neutral-500 text-center">
                알림 없음
              </li>
            ) : (
              items.map((n) => (
                <NotificationRow
                  key={n.id}
                  n={n}
                  onClick={() => handleItemClick(n)}
                />
              ))
            )}
          </ul>
        </div>
      )}
    </div>
  )
}

function NotificationRow({
  n,
  onClick,
}: {
  n: Notification
  onClick: () => void
}) {
  const content = (
    <div
      className={`px-3 py-2 border-b border-neutral-800 hover:bg-neutral-800 ${
        !n.is_read ? "bg-neutral-900" : ""
      }`}
    >
      <div className="flex items-start gap-2">
        {!n.is_read && (
          <span
            aria-hidden="true"
            className="w-1.5 h-1.5 mt-1.5 rounded-full bg-emerald-500 shrink-0"
          />
        )}
        <div className="flex-1 min-w-0">
          <p className={`text-sm font-medium ${levelColor(n.level)}`}>
            {n.title}
          </p>
          {n.body && (
            <p className="text-xs text-neutral-300 line-clamp-2">{n.body}</p>
          )}
          <p className="text-[10px] text-neutral-500 mt-1">
            {formatTimeAgo(n.created_at)}
          </p>
        </div>
      </div>
    </div>
  )
  if (n.link) {
    return (
      <li>
        <Link href={n.link} onClick={onClick} className="block">
          {content}
        </Link>
      </li>
    )
  }
  return (
    <li>
      <button
        type="button"
        onClick={onClick}
        className="block w-full text-left"
      >
        {content}
      </button>
    </li>
  )
}
