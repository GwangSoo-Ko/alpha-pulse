"use client"
import { useQuery } from "@tanstack/react-query"
import { apiFetch } from "@/lib/api-client"
import type { Job } from "@/lib/types"

export function useJobStatus(jobId: string) {
  return useQuery<Job>({
    queryKey: ["job", jobId],
    queryFn: () => apiFetch<Job>(`/api/v1/jobs/${jobId}`),
    refetchInterval: (query) => {
      const s = query.state.data?.status
      return s === "done" || s === "failed" || s === "cancelled"
        ? false : 2000
    },
  })
}
