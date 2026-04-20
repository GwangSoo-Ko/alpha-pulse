/** FastAPI 호출 래퍼. 서버 컴포넌트/클라이언트 모두 사용 가능. */

const BASE = process.env.NEXT_PUBLIC_API_BASE ?? ""

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
  const url = new URL(
    `${BASE}${path.startsWith("/") ? path : `/${path}`}`,
    typeof window === "undefined" ? "http://localhost" : window.location.origin,
  )
  if (init?.searchParams) {
    for (const [k, v] of Object.entries(init.searchParams)) {
      if (v !== undefined && v !== "") url.searchParams.set(k, v)
    }
  }
  const res = await fetch(url.toString(), {
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    ...init,
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
