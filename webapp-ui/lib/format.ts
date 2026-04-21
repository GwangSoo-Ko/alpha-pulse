export function fmtPct(n: number | undefined, digits = 2): string {
  if (n === undefined || n === null || Number.isNaN(n)) return "-"
  return `${n >= 0 ? "+" : ""}${n.toFixed(digits)}%`
}

export function fmtNum(
  n: number | undefined,
  digits = 0,
): string {
  if (n === undefined || n === null || Number.isNaN(n)) return "-"
  return n.toLocaleString("ko-KR", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })
}

export function fmtKrw(n: number | undefined): string {
  if (n === undefined || n === null || Number.isNaN(n)) return "-"
  return `${n.toLocaleString("ko-KR", { maximumFractionDigits: 0 })}원`
}

export function fmtDate(yyyymmdd: string | undefined): string {
  if (!yyyymmdd || yyyymmdd.length !== 8) return yyyymmdd ?? "-"
  return `${yyyymmdd.slice(0, 4)}-${yyyymmdd.slice(4, 6)}-${yyyymmdd.slice(6, 8)}`
}
