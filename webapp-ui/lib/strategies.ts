/** 백테스트 전략 + 스크리닝 프리셋 설명 데이터. */

export type FactorWeight = {
  key: string
  label: string
  weight: number
}

export type StrategyInfo = {
  id: string
  label: string
  summary: string          // 한 줄 요약
  universe: string         // 대상 유니버스
  rebalance: string        // 리밸런싱 주기
  marketReaction: string   // 시장 상황 대응
  weights: FactorWeight[]  // 팩터 가중치 (ETF는 빈 배열)
  details: string          // 상세 동작 방식
}

export const FACTOR_LABELS: Record<string, string> = {
  momentum: "모멘텀",
  value: "밸류",
  quality: "퀄리티",
  growth: "성장성",
  flow: "수급",
  volatility: "변동성",
}

/** 6개 팩터의 의미. */
export const FACTOR_DESCRIPTIONS: Record<string, string> = {
  momentum: "최근 1/3/6개월 수익률 가중 평균. 높을수록 추세 강함.",
  value: "PER·PBR의 역수 + 배당수익률 + 시가총액 하위 프리미엄. 저평가일수록 높음.",
  quality: "ROE + 영업이익 성장률 + 낮은 부채비율. 우량 기업일수록 높음.",
  growth: "매출·영업이익·순이익 YoY 성장률. 실적 개선 기업일수록 높음.",
  flow: "외국인·기관 순매수 추세 + 공매도 감소. 수급 우호적일수록 높음.",
  volatility: "연환산 일간 수익률 표준편차. 낮을수록 안정적 (역팩터).",
}

/** 백테스트 전략 4종. id는 `ap trading backtest run --strategy <id>` 와 일치. */
export const BACKTEST_STRATEGIES: StrategyInfo[] = [
  {
    id: "momentum",
    label: "모멘텀 (Momentum)",
    summary: "상승 추세 종목을 쫓아가는 공격적 전략",
    universe: "KOSPI/KOSDAQ 전체 (시장 선택 가능)",
    rebalance: "주간 (매주 월요일)",
    marketReaction:
      "Market Pulse가 매도 우위(moderately_bearish / strong_bearish)이면 시그널 강도 50% 축소",
    weights: [
      { key: "momentum", label: "모멘텀", weight: 0.6 },
      { key: "flow", label: "수급", weight: 0.3 },
      { key: "volatility", label: "변동성(역)", weight: 0.1 },
    ],
    details:
      "MultiFactorRanker가 유니버스 전체 종목의 모멘텀·수급·변동성을 0~100 백분위로 정규화하여 가중 합산 후 상위 N종목을 선정. " +
      "모멘텀은 최근 1/3/6개월 수익률, 수급은 외국인·기관 순매수 누적, 변동성은 역팩터로 낮을수록 고득점. " +
      "강세장에서 최고 성과를 내지만 급락장 회복 구간에서 드로다운이 큼.",
  },
  {
    id: "value",
    label: "밸류 (Value)",
    summary: "저평가된 우량주를 발굴하는 방어적 전략",
    universe: "KOSPI/KOSDAQ 전체 (시장 선택 가능)",
    rebalance: "주간 (매주 월요일)",
    marketReaction: "시장 신호에 덜 민감. 약세장에서 상대강세를 보이는 경향",
    weights: [
      { key: "value", label: "밸류", weight: 0.4 },
      { key: "quality", label: "퀄리티", weight: 0.3 },
      { key: "momentum", label: "모멘텀", weight: 0.2 },
      { key: "flow", label: "수급", weight: 0.15 },
      { key: "volatility", label: "변동성(역)", weight: 0.05 },
    ],
    details:
      "PER/PBR이 낮고 ROE·영업이익 성장이 탄탄한 저평가주 선호. " +
      "다만 순수 밸류 트랩을 피하기 위해 모멘텀·수급을 보조 팩터로 포함. " +
      "하락장/횡보장에서 꾸준한 성과, 강세 모멘텀 구간엔 모멘텀 전략 대비 뒤처질 수 있음.",
  },
  {
    id: "quality_momentum",
    label: "퀄리티+모멘텀 (Quality Momentum)",
    summary: "우량 성장주를 쫓는 균형형 전략",
    universe: "KOSPI/KOSDAQ 전체 (시장 선택 가능)",
    rebalance: "주간 (매주 월요일)",
    marketReaction: "매도 우위 시 시그널 50% 축소 (모멘텀 전략과 동일 방어 로직)",
    weights: [
      { key: "quality", label: "퀄리티", weight: 0.35 },
      { key: "momentum", label: "모멘텀", weight: 0.35 },
      { key: "flow", label: "수급", weight: 0.2 },
      { key: "volatility", label: "변동성(역)", weight: 0.1 },
    ],
    details:
      "ROE·저부채·이익성장 우수 + 최근 상승 추세가 살아있는 종목을 선정. " +
      "퀄리티 단독은 따분한 대형주, 모멘텀 단독은 변동성이 과도한데 둘을 35:35로 결합하여 위험 대비 수익률을 개선. " +
      "대부분의 시장 환경에서 무난한 성과, 초강세 단기 급등장은 모멘텀 전략에 뒤처짐.",
  },
  {
    id: "topdown_etf",
    label: "탑다운 ETF (Top-down ETF)",
    summary: "시장 Pulse Score 기반 ETF 비중 배분 전략",
    universe: "KODEX ETF 5종 (레버리지 / 200 / 단기채 / 인버스 / 선물인버스2X)",
    rebalance: "시그널 드리븐 — 시장 신호 레벨이 변경될 때만",
    marketReaction:
      "Market Pulse 5단계에 따라 공격/방어 ETF 비중 동적 결정 (개별 종목 선정 없음)",
    weights: [],
    details:
      "Market Pulse Score를 5단계(강한 매수 / 매수 우위 / 중립 / 매도 우위 / 강한 매도)로 분류하여 비중 결정. " +
      "• 강한 매수: KODEX 레버리지 70%, KODEX 200 30%  " +
      "• 매수 우위: KODEX 200 80%, 단기채 20%  " +
      "• 중립: 단기채 50%, KODEX 200 30%  " +
      "• 매도 우위: KODEX 인버스 50%, 단기채 30%  " +
      "• 강한 매도: KODEX 200선물인버스2X 40%, 단기채 30%  " +
      "개별 기업 분석 불필요, 거시 방향성에 베팅하는 전술. 시그널 변경 전까지 매매 없음.",
  },
]

/** 스크리닝 프리셋 4종. screening-form.tsx의 PRESETS와 일치. */
export const SCREENING_PRESETS: StrategyInfo[] = [
  {
    id: "momentum",
    label: "모멘텀 (Momentum)",
    summary: "현재 상승 추세가 강한 종목 찾기",
    universe: "선택한 시장 (KOSPI/KOSDAQ/ALL)",
    rebalance: "일회성 스크리닝",
    marketReaction: "시장 컨텍스트(Pulse) 정보만 기록, 자동 조정 없음",
    weights: [
      { key: "momentum", label: "모멘텀", weight: 0.5 },
      { key: "flow", label: "수급", weight: 0.3 },
      { key: "volatility", label: "변동성(역)", weight: 0.2 },
    ],
    details:
      "단기~중기 수익률이 높고 외국인·기관 순매수가 유입되며 변동성이 상대적으로 낮은 종목을 선정. " +
      "'지금 잘 오르는 주식' 후보군 탐색용.",
  },
  {
    id: "value",
    label: "밸류 (Value)",
    summary: "저평가 + 펀더멘탈 우수한 종목 찾기",
    universe: "선택한 시장 (KOSPI/KOSDAQ/ALL)",
    rebalance: "일회성 스크리닝",
    marketReaction: "시장 조정 없음",
    weights: [
      { key: "value", label: "밸류", weight: 0.4 },
      { key: "quality", label: "퀄리티", weight: 0.2 },
      { key: "momentum", label: "모멘텀", weight: 0.2 },
      { key: "flow", label: "수급", weight: 0.15 },
      { key: "volatility", label: "변동성(역)", weight: 0.05 },
    ],
    details:
      "PER·PBR이 낮고 ROE·저부채 조건을 갖춘 종목 중 최근 수급이 들어오기 시작한 '살아나는 저평가주' 발굴. " +
      "가치 투자 후보 리스트업용.",
  },
  {
    id: "quality",
    label: "퀄리티 (Quality)",
    summary: "실적 우수 + 성장 중인 우량주 찾기",
    universe: "선택한 시장 (KOSPI/KOSDAQ/ALL)",
    rebalance: "일회성 스크리닝",
    marketReaction: "시장 조정 없음",
    weights: [
      { key: "quality", label: "퀄리티", weight: 0.35 },
      { key: "growth", label: "성장성", weight: 0.2 },
      { key: "value", label: "밸류", weight: 0.15 },
      { key: "momentum", label: "모멘텀", weight: 0.2 },
      { key: "flow", label: "수급", weight: 0.1 },
    ],
    details:
      "ROE·저부채 재무 + 매출/이익 YoY 성장 + 합리적인 밸류에이션 + 상승 추세를 모두 겸비한 우량 성장주 탐색. " +
      "장기 보유 후보 리스트업용.",
  },
  {
    id: "balanced",
    label: "밸런스드 (Balanced)",
    summary: "모든 팩터 고른 종합 평가",
    universe: "선택한 시장 (KOSPI/KOSDAQ/ALL)",
    rebalance: "일회성 스크리닝",
    marketReaction: "시장 조정 없음",
    weights: [
      { key: "momentum", label: "모멘텀", weight: 0.25 },
      { key: "flow", label: "수급", weight: 0.25 },
      { key: "value", label: "밸류", weight: 0.2 },
      { key: "quality", label: "퀄리티", weight: 0.15 },
      { key: "growth", label: "성장성", weight: 0.1 },
      { key: "volatility", label: "변동성(역)", weight: 0.05 },
    ],
    details:
      "어느 한 팩터에 편중되지 않고 6개 팩터를 종합 평가. 각 팩터 백분위 점수의 가중 평균을 기준으로 선정. " +
      "스타일을 특정하지 않는 일반 탐색용.",
  },
]

export function findBacktestStrategy(id: string): StrategyInfo | undefined {
  return BACKTEST_STRATEGIES.find((s) => s.id === id)
}

export function findScreeningPreset(id: string): StrategyInfo | undefined {
  return SCREENING_PRESETS.find((s) => s.id === id)
}
