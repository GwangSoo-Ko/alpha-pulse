// 11개 Market Pulse 지표 한글명 + 시그널 색상 매핑
// 기준: alphapulse/market/reporters/terminal.py INDICATOR_NAMES

export const INDICATOR_LABELS: Record<string, string> = {
  investor_flow: "외국인+기관 수급",
  spot_futures_align: "선물 베이시스",
  futures_flow: "선물 수급",
  program_trade: "프로그램 비차익",
  sector_momentum: "업종 모멘텀",
  exchange_rate: "환율 (USD/KRW)",
  vkospi: "V-KOSPI",
  interest_rate_diff: "한미 금리차",
  global_market: "글로벌 시장",
  fund_flow: "증시 자금",
  adr_volume: "ADR + 거래량",
}

export const INDICATOR_ORDER: string[] = [
  "investor_flow", "spot_futures_align", "futures_flow",
  "program_trade", "sector_momentum", "exchange_rate",
  "vkospi", "interest_rate_diff", "global_market",
  "fund_flow", "adr_volume",
]

export type SignalLevel =
  | "strong_bullish" | "moderately_bullish" | "neutral"
  | "moderately_bearish" | "strong_bearish"

export const SIGNAL_STYLE: Record<SignalLevel, {
  bar: string; badge: string; label: string
}> = {
  strong_bullish: {
    bar: "bg-green-500",
    badge: "bg-green-500/20 text-green-300",
    label: "강한 강세",
  },
  moderately_bullish: {
    bar: "bg-emerald-500",
    badge: "bg-emerald-500/20 text-emerald-300",
    label: "중립-강세",
  },
  neutral: {
    bar: "bg-yellow-500",
    badge: "bg-yellow-500/20 text-yellow-300",
    label: "중립",
  },
  moderately_bearish: {
    bar: "bg-orange-500",
    badge: "bg-orange-500/20 text-orange-300",
    label: "중립-약세",
  },
  strong_bearish: {
    bar: "bg-red-500",
    badge: "bg-red-500/20 text-red-300",
    label: "강한 약세",
  },
}

export function scoreToSignal(score: number): SignalLevel {
  if (score >= 60) return "strong_bullish"
  if (score >= 20) return "moderately_bullish"
  if (score >= -19) return "neutral"
  if (score >= -59) return "moderately_bearish"
  return "strong_bearish"
}

// 백엔드 Config.get_signal_label() 이 반환하는 한글 라벨 → SignalLevel 키 역방향 매핑.
// 기존 저장소(pulse_history, briefings)는 label 을 그대로 저장해 두었고,
// 새로 시리얼라이즈되는 Phase 3 응답은 key 를 직접 내려주길 권장.
const SIGNAL_LABEL_PREFIX_MAP: Array<[string, SignalLevel]> = [
  ["강한 매수", "strong_bullish"],
  ["매수 우위", "moderately_bullish"],
  ["중립", "neutral"],
  ["매도 우위", "moderately_bearish"],
  ["강한 매도", "strong_bearish"],
]

export function normalizeSignalKey(signal: string): SignalLevel {
  // 1) 이미 enum 키면 그대로
  if (signal in SIGNAL_STYLE) return signal as SignalLevel
  // 2) "강한 매수 (Strong Bullish)" 류 한글 라벨 prefix 매치
  for (const [prefix, key] of SIGNAL_LABEL_PREFIX_MAP) {
    if (signal.startsWith(prefix)) return key
  }
  // 3) 영어 소문자 포함 매치 (legacy / 혼합 입력)
  const lower = signal.toLowerCase()
  if (lower.includes("strong_bullish") || lower.includes("strong bullish")) return "strong_bullish"
  if (lower.includes("moderately_bullish") || lower.includes("moderately bullish")) return "moderately_bullish"
  if (lower.includes("moderately_bearish") || lower.includes("moderately bearish")) return "moderately_bearish"
  if (lower.includes("strong_bearish") || lower.includes("strong bearish")) return "strong_bearish"
  return "neutral"
}

export function signalStyle(signal: string) {
  return SIGNAL_STYLE[normalizeSignalKey(signal)]
}
