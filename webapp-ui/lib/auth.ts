import { cookies } from "next/headers"
import { apiFetch, ApiError } from "./api-client"
import type { User } from "./types"

/** 서버 컴포넌트에서 현재 사용자 조회. 없으면 null. */
export async function getCurrentUser(): Promise<User | null> {
  try {
    const cookieStore = await cookies()
    const cookieHeader = cookieStore
      .getAll()
      .map((c) => `${c.name}=${c.value}`)
      .join("; ")
    const r = await apiFetch<User>("/api/v1/auth/me", {
      headers: { cookie: cookieHeader },
      cache: "no-store",
    })
    return r
  } catch (e) {
    if (e instanceof ApiError && e.status === 401) return null
    throw e
  }
}
