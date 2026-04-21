"use client"
import { apiMutate } from "@/lib/api-client"
import { Button } from "@/components/ui/button"
import { ModeSelector } from "@/components/layout/mode-selector"
import type { User } from "@/lib/types"

export function Topbar({ user }: { user: User }) {
  const handleLogout = async () => {
    await apiMutate("/api/v1/auth/logout", "POST")
    window.location.href = "/login"
  }
  return (
    <div className="flex items-center justify-between border-b border-neutral-800 px-4 py-2">
      <div>
        <ModeSelector />
      </div>
      <div className="flex items-center gap-3 text-sm">
        <span className="text-neutral-400">{user.email}</span>
        <Button size="sm" variant="outline" onClick={handleLogout}>
          Logout
        </Button>
      </div>
    </div>
  )
}
