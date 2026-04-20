/** FastAPI 호출 래퍼. 서버 컴포넌트/클라이언트 모두 사용 가능.
 *
 * - 클라이언트: same-origin (브라우저 → Next.js). rewrites가 /api/* 를 FastAPI로 프록시.
 * - 서버 컴포넌트: INTERNAL_API_BASE 직접 호출 (기본 http://127.0.0.1:8000).
 *   Next.js rewrites가 서버 사이드 fetch엔 적용되지 않으므로 절대 URL 필요.
 */

const CLIENT_BASE = process.env.NEXT_PUBLIC_API_BASE ?? ""
const SERVER_BASE = process.env.INTERNAL_API_BASE ?? "http://127.0.0.1:8000"

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly body: unknown,
    message: string,
  ) {
    super(message)
  }
}

export async function apiFetch<T>(
  path: string,
  init?: RequestInit & { searchParams?: Record<string, string | undefined> },
): Promise<T> {
  const isServer = typeof window === "undefined"
  const base = isServer ? SERVER_BASE : CLIENT_BASE
  const origin = isServer ? SERVER_BASE : window.location.origin
  const url = new URL(
    `${base}${path.startsWith("/") ? path : `/${path}`}`,
    origin,
  )
  if (init?.searchParams) {
    for (const [k, v] of Object.entries(init.searchParams)) {
      if (v !== undefined && v !== "") url.searchParams.set(k, v)
    }
  }
  const { headers: initHeaders, searchParams: _sp, ...restInit } = init ?? {}
  const res = await fetch(url.toString(), {
    ...restInit,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(initHeaders ?? {}),
    },
  })
  const ct = res.headers.get("content-type") ?? ""
  const body = ct.includes("json") ? await res.json() : await res.text()
  if (!res.ok) {
    throw new ApiError(
      res.status, body,
      typeof body === "object" && body && "detail" in body
        ? String(body.detail) : res.statusText,
    )
  }
  return body as T
}

export async function csrfToken(): Promise<string> {
  const r = await apiFetch<{ token: string }>("/api/v1/csrf-token")
  return r.token
}

/** CSRF 토큰을 자동으로 붙이는 헬퍼 — mutations에서 사용. */
export async function apiMutate<T>(
  path: string,
  method: "POST" | "PUT" | "DELETE",
  body?: unknown,
): Promise<T> {
  const token = await csrfToken()
  return apiFetch<T>(path, {
    method,
    headers: { "X-CSRF-Token": token },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
}
