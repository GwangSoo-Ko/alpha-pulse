"use client"
import { useEffect, useState } from "react"

/** 한국 시간 기준 장중 여부(평일 09:00~15:30). 주말/휴일 체크 없음. */
export function isMarketHours(now: Date = new Date()): boolean {
  const kst = new Date(
    now.toLocaleString("en-US", { timeZone: "Asia/Seoul" }),
  )
  const day = kst.getDay()  // 0: Sun, 6: Sat
  if (day === 0 || day === 6) return false
  const h = kst.getHours()
  const m = kst.getMinutes()
  const minutes = h * 60 + m
  return minutes >= 9 * 60 && minutes <= 15 * 60 + 30
}

export function useMarketHours(): boolean {
  const [open, setOpen] = useState(() => isMarketHours())
  useEffect(() => {
    const id = setInterval(() => setOpen(isMarketHours()), 60_000)
    return () => clearInterval(id)
  }, [])
  return open
}
