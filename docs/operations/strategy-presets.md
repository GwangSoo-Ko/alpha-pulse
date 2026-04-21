# Strategy Presets — 백테스트 전략 + 스크리닝 프리셋 레퍼런스

AlphaPulse 웹/CLI에서 제공하는 전략 프리셋의 동작 방식, 팩터 구성, 시장 대응 로직을 정리한 문서.
UI의 StrategyInfoCard 컴포넌트와 동일 내용(`webapp-ui/lib/strategies.ts`).

---

## 공통 — 팩터 (Factor) 6종

모든 전략·프리셋은 아래 6개 팩터의 조합으로 구성된다. `alphapulse/trading/screening/factors.py`의 `FactorCalculator` 클래스가 실제 수치 계산 담당.

| 팩터 | 의미 | 계산 방식(요약) |
|------|------|-----------------|
| **모멘텀** (momentum) | 추세 강도 | 최근 1/3/6개월 수익률의 가중 평균 |
| **밸류** (value) | 저평가 정도 | PER·PBR 역수 + 배당수익률 + 시가총액 하위 프리미엄 |
| **퀄리티** (quality) | 재무 건전성 | ROE + 영업이익 성장률 + 저부채 |
| **성장성** (growth) | 실적 개선 | 매출·영업이익·순이익 YoY 성장률 |
| **수급** (flow) | 수급 방향 | 외국인·기관 순매수 추세 + 공매도 감소 |
| **변동성** (volatility, 역팩터) | 안정성 | 연환산 일간 수익률 표준편차 (낮을수록 고득점) |

### MultiFactorRanker 동작

`alphapulse/trading/screening/ranker.py`:

1. **백분위 정규화** — 유니버스 내 각 종목의 팩터값을 0~100 백분위로 변환 (동률 허용).
2. **가중 합산** — 전략별 `factor_weights`로 곱하여 종합 점수 산출.
3. **스케일 변환** — `(raw - 50) * 2` 로 -100 ~ +100 스코어로 변환.
4. **정렬** — 내림차순 정렬, 상위 N개 선정.

---

## 백테스트 전략 (BacktestEngine에서 사용)

CLI: `ap trading backtest run --strategy <id>`

### 1. 모멘텀 (`momentum`)

**파일:** `alphapulse/trading/strategy/momentum.py`

- **컨셉:** 상승 추세 종목을 쫓아가는 공격적 전략
- **팩터 가중치:**
  - 모멘텀 60%
  - 수급 30%
  - 변동성(역) 10%
- **리밸런싱:** 주간 (매주 월요일, `RebalanceFreq.WEEKLY`)
- **유니버스:** KOSPI/KOSDAQ 전체
- **시장 대응:** `Market Pulse`가 `moderately_bearish` 또는 `strong_bearish`일 때 시그널 강도 50% 축소
- **특징:** 강세장 최고 성과, 급락 회복 구간에서 드로다운 큼

### 2. 밸류 (`value`)

**파일:** `alphapulse/trading/strategy/value.py`

- **컨셉:** 저평가된 우량주 발굴, 방어적 성향
- **팩터 가중치:**
  - 밸류 40%
  - 퀄리티 30%
  - 모멘텀 20%
  - 수급 15%
  - 변동성(역) 5%
- **리밸런싱:** 주간
- **유니버스:** KOSPI/KOSDAQ 전체
- **시장 대응:** 시장 신호에 덜 민감
- **특징:** 하락장/횡보장 상대강세, 강세 단기 급등장에서 모멘텀 전략 대비 뒤처질 수 있음

### 3. 퀄리티+모멘텀 (`quality_momentum`)

**파일:** `alphapulse/trading/strategy/quality_momentum.py`

- **컨셉:** 우량 성장주, 균형형 전략
- **팩터 가중치:**
  - 퀄리티 35%
  - 모멘텀 35%
  - 수급 20%
  - 변동성(역) 10%
- **리밸런싱:** 주간
- **유니버스:** KOSPI/KOSDAQ 전체
- **시장 대응:** 매도 우위 시 시그널 50% 축소 (모멘텀 전략과 동일)
- **특징:** 대부분 시장 환경에서 무난한 성과

### 4. 탑다운 ETF (`topdown_etf`)

**파일:** `alphapulse/trading/strategy/topdown_etf.py`

- **컨셉:** Market Pulse Score로 ETF 비중 배분
- **팩터 가중치:** 없음 (개별 종목 팩터 분석 불필요)
- **리밸런싱:** 신호 변경 시만 (`RebalanceFreq.SIGNAL_DRIVEN`)
- **유니버스:** KODEX ETF 5종 (레버리지 / 200 / 단기채 / 인버스 / 선물인버스2X)
- **시장 대응:** Market Pulse 5단계에 따른 동적 비중
  | Pulse Signal | ETF 배분 |
  |---|---|
  | `strong_bullish` | KODEX 레버리지 70%, KODEX 200 30% |
  | `moderately_bullish` | KODEX 200 80%, 단기채 20% |
  | `neutral` | 단기채 50%, KODEX 200 30% |
  | `moderately_bearish` | KODEX 인버스 50%, 단기채 30% |
  | `strong_bearish` | KODEX 200선물인버스2X 40%, 단기채 30% |
- **특징:** 거시 방향성 베팅, 시그널 변경 전까지 매매 없음

---

## 스크리닝 프리셋 (`MultiFactorRanker`에 적용)

CLI: `ap trading screen --strategy <preset>` 또는 웹 UI `/screening/new`

### 1. `momentum`
- 가중치: 모멘텀 50% + 수급 30% + 변동성(역) 20%
- 용도: 지금 상승 중인 기술적 추세주 찾기

### 2. `value`
- 가중치: 밸류 40% + 퀄리티 20% + 모멘텀 20% + 수급 15% + 변동성(역) 5%
- 용도: 저평가 + 펀더멘탈 우수 + 살아나는 수급 종목 발굴

### 3. `quality`
- 가중치: 퀄리티 35% + 성장성 20% + 밸류 15% + 모멘텀 20% + 수급 10%
- 용도: 실적 우수 + 성장 중인 우량주 찾기 (장기 보유 후보)

### 4. `balanced`
- 가중치: 모멘텀 25% + 수급 25% + 밸류 20% + 퀄리티 15% + 성장성 10% + 변동성(역) 5%
- 용도: 어느 한 팩터에 편중되지 않는 종합 탐색

---

## 백테스트 전략 vs 스크리닝 프리셋 차이

| 항목 | 백테스트 전략 | 스크리닝 프리셋 |
|---|---|---|
| **구현 계층** | `Strategy` 클래스 (상속) | `factor_weights` dict만 전달 |
| **리밸런싱 주기 제어** | 있음 (`rebalance_freq`) | 없음 (일회성 조회) |
| **시장 대응 로직** | 있음 (Market Pulse 기반 시그널 조정) | 없음 (정적 가중치만) |
| **결과 용도** | 시뮬레이션 백테스트 → 수익률/리스크 지표 | 현재 시점 상위 N종목 리스트 |
| **저장** | `backtest.db` runs/trades/positions | `webapp.db` screening_runs |

---

## 참고 파일

- 백테스트 전략: `alphapulse/trading/strategy/{momentum,value,quality_momentum,topdown_etf}.py`
- 팩터 계산: `alphapulse/trading/screening/factors.py`
- 랭커: `alphapulse/trading/screening/ranker.py`
- 웹 UI 설명 데이터: `webapp-ui/lib/strategies.ts`
- 웹 UI 카드 컴포넌트: `webapp-ui/components/domain/strategy-info-card.tsx`
