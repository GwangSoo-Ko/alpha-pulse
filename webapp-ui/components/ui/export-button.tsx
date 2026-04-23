import Link from "next/link"
import { Button } from "@/components/ui/button"

export function ExportButton({
  href,
  label = "내보내기",
}: {
  href: string
  label?: string
}) {
  return (
    <Link href={href}>
      <Button size="sm" variant="outline">📥 {label}</Button>
    </Link>
  )
}
