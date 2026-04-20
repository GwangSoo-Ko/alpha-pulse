import type { Metadata } from "next"
import "./globals.css"

export const metadata: Metadata = {
  title: "AlphaPulse",
  description: "AI 기반 투자 인텔리전스 플랫폼",
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="ko" className="dark">
      <body>{children}</body>
    </html>
  )
}
