# 03. 전략, 포트폴리오, 리스크 관리 운영 레퍼런스

AlphaPulse 자동 매매 시스템의 전략 생성부터 포트폴리오 구성, 리스크 관리까지의 전체
파이프라인을 다룬다. 모든 수치와 임계값은 소스코드에서 직접 추출한 실측치이다.

---

## 목차

1. [개요](#1-개요)
2. [기본 전략 4종](#2-기본-전략-4종)
3. [리밸런싱 규칙](#3-리밸런싱-규칙)
4. [전략 배분기 (Allocator)](#4-전략-배분기-allocator)
5. [AI 종합 판단](#5-ai-종합-판단)
6. [포트폴리오 관리](#6-포트폴리오-관리)
7. [리스크 관리](#7-리스크-관리)
8. [드로다운 관리](#8-드로다운-관리)
9. [VaR / CVaR](#9-var--cvar)
10. [스트레스 테스트](#10-스트레스-테스트)

---

## 1. 개요

### 전략 시스템 아키텍처

AlphaPulse 매매 시스템은 **Strategy -> Portfolio -> Risk** 3단계 파이프라인으로 구성된다.

```
[Market Pulse 11개 지표]
         |
         v
+-------------------+     +-------------------+     +-------------------+
|    Strategy 계층   | --> |  Portfolio 계층    | --> |    Risk 계층       |
+-------------------+     +-------------------+     +-------------------+
| 4개 전략 시그널 생성 |     | 목표 비중 산출     |     | 주문 5단계 검증    |
| AI 종합 판단       |     | 리밸런싱 주문 생성  |     | 드로다운 모니터링   |
| 전략 배분 조정     |     | 포지션 사이징      |     | VaR/CVaR 계산     |
+-------------------+     +-------------------+     +-------------------+
         |                         |                         |
         v                         v                         v
   StrategyAllocator        PortfolioManager           RiskManager
   StrategyAISynthesizer    PositionSizer              DrawdownManager
                            Rebalancer                 VaRCalculator
                            PortfolioOptimizer         StressTest
```

### 데이터 흐름 요약

1. **Strategy 계층**: Market Pulse 시그널과 팩터 데이터를 입력받아 종목별 매매 시그널을 생성한다.
2. **Portfolio 계층**: 전략별 시그널과 배분 비율을 결합하여 목표 포트폴리오를 산출하고, 현재 대비 차이를 주문으로 변환한다.
3. **Risk 계층**: 생성된 주문이 리스크 한도 내에 있는지 5단계 검증을 수행하고, 포트폴리오 전체의 리스크 상태를 모니터링한다.

### 동기/비동기 구분

| 모듈 | 실행 모드 | 비고 |
|------|----------|------|
| Strategy (4종) | **Sync** | 팩터 계산, 시그널 생성 |
| StrategyAISynthesizer | **Async** | `asyncio.to_thread()`로 Gemini API 호출 |
| Portfolio (전체) | **Sync** | 비중 계산, 주문 생성 |
| Risk (전체) | **Sync** | 리스크 검증, VaR 계산 |
| Orchestrator | **Async** | 전체 파이프라인 통합 |

### 핵심 열거형 (`core/enums.py`)

| 열거형 | 값 | 용도 |
|--------|-----|------|
| `Side` | `BUY`, `SELL` | 매매 방향 |
| `OrderType` | `MARKET`, `LIMIT` | 주문 유형 |
| `TradingMode` | `backtest`, `paper`, `live` | 실행 모드 |
| `RebalanceFreq` | `daily`, `weekly`, `signal_driven` | 리밸런싱 주기 |
| `RiskAction` | `APPROVE`, `REDUCE_SIZE`, `REJECT` | 리스크 검증 결과 |
| `DrawdownAction` | `NORMAL`, `WARN`, `DELEVERAGE` | 드로다운 대응 수준 |

---

## 2. 기본 전략 4종

### 2.1 MomentumStrategy (모멘텀 전략)

**소스**: `alphapulse/trading/strategy/momentum.py`

| 항목 | 값 |
|------|-----|
| `strategy_id` | `"momentum"` |
| `rebalance_freq` | `WEEKLY` (주간) |
| `top_n` | `20` (기본값, config에서 변경 가능) |

**팩터 가중치**:

| 팩터 | 가중치 |
|------|--------|
| `momentum` | 0.6 |
| `flow` | 0.3 |
| `volatility` | 0.1 |

**시그널 생성 로직**:

1. `MultiFactorRanker`에 universe와 factor_data를 전달하여 종목 점수를 산출한다.
2. 상위 `top_n`(20)개 종목을 선정한다.
3. 시장 약세 시 시그널 강도를 감쇠(dampening)한다.

**약세 시 감쇠 규칙**:

- `pulse_signal`이 `"moderately_bearish"` 또는 `"strong_bearish"`이면 시그널 점수를 **0.5배**로 축소한다.
- 감쇠 대상 시그널 집합: `{"moderately_bearish", "strong_bearish"}`

### 2.2 ValueStrategy (밸류 전략)

**소스**: `alphapulse/trading/strategy/value.py`

| 항목 | 값 |
|------|-----|
| `strategy_id` | `"value"` |
| `rebalance_freq` | `WEEKLY` (주간) |
| `top_n` | `15` (기본값) |

**팩터 가중치**:

| 팩터 | 가중치 |
|------|--------|
| `value` | 0.4 |
| `quality` | 0.3 |
| `momentum` | 0.2 |
| `flow` | 0.1 |

**시그널 생성 로직**:

1. `MultiFactorRanker`로 밸류+퀄리티 중심 종목 점수를 산출한다.
2. 상위 `top_n`(15)개 종목을 선정한다.
3. 중립 시장에서 시그널 강도를 증가시킨다.

**중립 시장 강화 규칙**:

- `pulse_signal`이 `"neutral"`이면 시그널 점수를 **1.2배** 증가시킨다.
- 상한 cap: `min(score * 1.2, 100.0)` -- 100점을 초과하지 않는다.
- 근거: 불확실성 시 가치주 선호 경향 반영.

### 2.3 QualityMomentumStrategy (퀄리티+모멘텀 복합 전략)

**소스**: `alphapulse/trading/strategy/quality_momentum.py`

| 항목 | 값 |
|------|-----|
| `strategy_id` | `"quality_momentum"` |
| `rebalance_freq` | `WEEKLY` (주간) |
| `top_n` | `15` (기본값) |

**팩터 가중치**:

| 팩터 | 가중치 |
|------|--------|
| `quality` | 0.35 |
| `momentum` | 0.35 |
| `flow` | 0.2 |
| `volatility` | 0.1 |

**시그널 생성 로직**:

1. `MultiFactorRanker`로 퀄리티+모멘텀 복합 점수를 산출한다.
2. 상위 `top_n`(15)개 종목을 선정한다.
3. 시장 상황에 따라 정밀한 다단계 감쇠를 적용한다.

**감쇠 계수 매핑 (`_get_dampening`)**:

| pulse_signal | 감쇠 계수 | 효과 |
|-------------|-----------|------|
| `strong_bullish` | 1.0 | 변동 없음 |
| `moderately_bullish` | 1.0 | 변동 없음 |
| `neutral` | 1.0 | 변동 없음 |
| `moderately_bearish` | 0.5 | 시그널 50% 축소 |
| `strong_bearish` | 0.3 | 시그널 70% 축소 |

알 수 없는 시그널에 대해서는 기본값 1.0(변동 없음)을 반환한다.

### 2.4 TopDownETFStrategy (탑다운 ETF 전략)

**소스**: `alphapulse/trading/strategy/topdown_etf.py`

| 항목 | 값 |
|------|-----|
| `strategy_id` | `"topdown_etf"` |
| `rebalance_freq` | `SIGNAL_DRIVEN` (시그널 기반) |

**ETF 코드 매핑**:

| ETF 이름 | 종목코드 | 특성 |
|---------|----------|------|
| KODEX 레버리지 | 122630 | KOSPI 200 2배 레버리지 |
| KODEX 200 | 069500 | KOSPI 200 추종 |
| KODEX 단기채권 | 153130 | 방어형 (단기 채권) |
| KODEX 인버스 | 114800 | KOSPI 200 역추종 |
| KODEX 200선물인버스2X | 252670 | KOSPI 200 2배 역추종 |

**ETF_MAP (시그널 레벨별 ETF 비중 매핑)**:

| 시그널 레벨 | ETF 구성 | 비중 합계 | 내재 현금 |
|-----------|---------|----------|----------|
| `strong_bullish` | KODEX 레버리지 70%, KODEX 200 30% | 100% | 0% |
| `moderately_bullish` | KODEX 200 80%, KODEX 단기채권 20% | 100% | 0% |
| `neutral` | KODEX 단기채권 50%, KODEX 200 30% | 80% | 20% |
| `moderately_bearish` | KODEX 인버스 50%, KODEX 단기채권 30% | 80% | 20% |
| `strong_bearish` | KODEX 200선물인버스2X 40%, KODEX 단기채권 30% | 70% | 30% |

**시그널 점수 변환 로직**:

- 비중을 점수(-100 ~ +100)로 변환: `weight * 100 * direction`
- `direction`: `pulse_score >= 0`이면 1.0, 아니면 -1.0
- 인버스 ETF: 방향 반전 (`weight * 100 * (-direction)`)
- 최종 점수는 `abs(score)`로 절대값 적용

**시그널 기반 리밸런싱**:

- `should_rebalance_signal_driven(prev_signal, curr_signal)`: 이전 시그널과 현재 시그널이 다를 때만 `True` 반환
- 알 수 없는 시그널은 `neutral`로 폴백 처리

### 전략 비교 요약

| 전략 | ID | 주기 | 종목 수 | 주요 팩터 | 약세 시 대응 |
|------|-----|------|--------|----------|------------|
| Momentum | `momentum` | 주간 | 20 | 모멘텀 60% | 0.5배 축소 |
| Value | `value` | 주간 | 15 | 밸류 40% + 퀄리티 30% | 중립 시 1.2배 강화 |
| Quality Momentum | `quality_momentum` | 주간 | 15 | 퀄리티 35% + 모멘텀 35% | 5단계 감쇠 (0.3~1.0) |
| TopDown ETF | `topdown_etf` | 시그널 기반 | ETF | Market Pulse 시그널 | ETF 구성 자체 전환 |

---

## 3. 리밸런싱 규칙

**소스**: `alphapulse/trading/strategy/base.py` -- `BaseStrategy.should_rebalance()`

### should_rebalance() 로직

`should_rebalance(last_rebalance, current_date, market_context)` 메서드는
`RebalanceFreq` 열거형에 따라 분기한다.

| RebalanceFreq | 판정 로직 | 적용 전략 |
|--------------|----------|----------|
| `DAILY` | 항상 `True` | (현재 사용 전략 없음) |
| `WEEKLY` | `current_date`를 파싱하여 `weekday() == 0` (월요일)이면 `True` | Momentum, Value, QualityMomentum |
| `SIGNAL_DRIVEN` | BaseStrategy에서는 항상 `False` 반환 -- 서브클래스에서 오버라이드 | TopDown ETF |

### 상세 동작

```
DAILY:
  -> 무조건 True

WEEKLY:
  -> current_date (YYYYMMDD 형식)를 datetime으로 파싱
  -> dt.weekday() == 0 (월요일)이면 True, 아니면 False

SIGNAL_DRIVEN:
  -> BaseStrategy: False (서브클래스 위임)
  -> TopDownETFStrategy.should_rebalance_signal_driven():
     prev_signal != curr_signal 이면 True
```

### 날짜 형식

- `last_rebalance`: `YYYYMMDD` 문자열
- `current_date`: `YYYYMMDD` 문자열
- Python `datetime.strptime(current_date, "%Y%m%d")`로 파싱

---

## 4. 전략 배분기 (Allocator)

**소스**: `alphapulse/trading/strategy/allocator.py`

### 기본 구조

`StrategyAllocator`는 멀티전략 간 자금 배분 비율을 관리한다. 생성 시 `base_allocations`
(전략ID -> 배분비율, 합계 1.0)를 받으며, 시장 상황에 따라 동적 조정한다.

### 배분 조정 2단계 프로세스

`adjust_by_market_regime(pulse_score, ai_synthesis)`:

**1단계: 규칙 기반 조정 (`_rule_based_adjustment`)**

| 조건 | 동작 | 세부 사항 |
|------|------|----------|
| `pulse_score > 50` | 종목 전략 비중 증가 | ETF 비중에서 0.10 차감 (하한 0.10), 차감분을 종목 전략에 균등 배분 |
| `pulse_score < -50` | ETF 비중 증가 | ETF 비중에 0.15 가산 (상한 0.60), 가산분을 종목 전략에서 균등 차감 (하한 0.05) |
| `-10 <= pulse_score <= 10` | 밸류 비중 강화 | `"value"` 전략에 0.05 가산, 나머지 종목 전략에서 균등 차감 |
| 그 외 | 변동 없음 | base_allocations 유지 |

**2단계: AI 종합 판단 반영**

AI 반영 조건 (모두 충족해야 함):
- `ai_synthesis`가 `None`이 아닐 것
- `ai_synthesis.conviction_level >= 0.3` (`_MIN_AI_CONVICTION`)
- `ai_synthesis.allocation_adjustment`가 존재할 것

AI 블렌딩 공식:
```
adjusted[key] = rule_val * (1 - 0.4) + ai_val * 0.4
```

| 파라미터 | 값 | 설명 |
|---------|-----|------|
| `_AI_BLEND_WEIGHT` | 0.4 | AI 배분 가중치 |
| `_MIN_AI_CONVICTION` | 0.3 | AI 반영 최소 확신도 |

**3단계: 정규화**

최종 배분 비율은 합계가 1.0이 되도록 정규화한다. 모든 값의 합이 0 이하이면
전략 수의 역수로 균등 배분한다.

### 자금 산출

`get_capital(strategy_id, total_capital)`:
```
할당 자금 = total_capital * current_allocations[strategy_id]
```

---

## 5. AI 종합 판단

**소스**: `alphapulse/trading/strategy/ai_synthesizer.py`

### StrategyAISynthesizer 개요

정량(Market Pulse, 팩터 랭킹, 전략 시그널) + 정성(콘텐츠 분석) + 피드백을
Google Gemini LLM으로 종합하여 최종 전략 배분 및 종목 의견을 도출한다.

### synthesize() 흐름

```
1. _build_prompt()   : 5개 입력 카테고리를 구조화된 프롬프트로 조합
2. _call_llm()       : asyncio.to_thread()로 Gemini API 동기 호출을 비동기 래핑
3. _parse_response() : JSON 응답 파싱 -> StrategySynthesis 데이터클래스 변환
4. 실패 시 _fallback(): 규칙 기반 보수적 기본값 반환
```

### 입력 5개 카테고리

| 번호 | 카테고리 | 내용 |
|------|---------|------|
| 1 | 시장 상황 (Market Pulse) | 날짜, 종합 점수, 시그널 레벨, 11개 지표별 상세 |
| 2 | 팩터 분석 | 상위 20개 종목 코드, 이름, 점수, 팩터별 상세 |
| 3 | 전략별 시그널 | 전략ID별 종목 수, 상위 5개 종목 이름+점수 |
| 4 | 정성 분석 | 콘텐츠 분석 결과 요약 리스트 |
| 5 | 과거 성과 피드백 | 적중률, 피드백 텍스트 |

추가로 현재 포트폴리오 상태(총 자산, 현금, 일간 수익률, 누적 수익률, 드로다운)를
포함한다.

### LLM 호출 설정

| 파라미터 | 값 |
|---------|-----|
| API | Google Gemini (`google-genai`) |
| 모델 | `Config().GEMINI_MODEL` |
| `max_output_tokens` | 4096 |
| `temperature` | 0.2 |
| 호출 방식 | `asyncio.to_thread(_sync_call)` |

### 프롬프트 핵심 규칙

1. 정량 데이터를 기본으로 하되, 정성 분석과 상충하면 양쪽 근거를 명시한다.
2. `conviction_level` 0.3 미만이면 현금 비중 상향 권고.
3. 리스크 경고는 반드시 1개 이상 포함.
4. 모든 판단에 구체적 수치 근거를 인용.
5. 한국어로 작성.

### 출력 (StrategySynthesis)

| 필드 | 타입 | 설명 |
|------|------|------|
| `market_view` | `str` | 시장 전체 판단 요약 (2~3문장) |
| `conviction_level` | `float` | 확신도 (0.0~1.0) |
| `allocation_adjustment` | `dict[str, float]` | 전략별 배분 비율 조정 |
| `stock_opinions` | `list[StockOpinion]` | 종목별 의견 (코드, 이름, action, reason, confidence) |
| `risk_warnings` | `list[str]` | 리스크 경고 리스트 |
| `reasoning` | `str` | 판단 근거 (3~5문장) |

`StockOpinion.action` 가능 값: `"강력매수"`, `"매수"`, `"유지"`, `"축소"`, `"매도"`

### Fallback (LLM 실패 시)

- `market_view`: `"AI 분석 불가 -- 정량 시그널 기반 실행"`
- `conviction_level`: 0.5
- `allocation_adjustment`: 전략 수 기반 균등 배분
- `stock_opinions`: 빈 리스트
- `risk_warnings`: `["AI 종합 판단 실패. 규칙 기반으로 실행됨."]`

---

## 6. 포트폴리오 관리

### 6.1 PortfolioManager

**소스**: `alphapulse/trading/portfolio/manager.py`

`PortfolioManager`는 `PositionSizer`, `PortfolioOptimizer`, `Rebalancer`, `CostModel`을
통합하여 목표 포트폴리오 산출과 리밸런싱 주문 생성을 담당한다.

#### update_target()

전략별 시그널과 배분 비율을 결합하여 목표 포트폴리오(`TargetPortfolio`)를 산출한다.

**처리 흐름**:

1. 전략별 시그널을 순회한다.
2. 각 전략의 배분 비율(`allocations[strategy_id]`)을 확인하고, 0 이하이면 건너뛴다.
3. 전략 내 종목별 균등 배분: `PositionSizer.equal_weight(n_stocks)` = `1.0 / n_stocks`
4. 종목별 목표 비중 = `alloc_ratio * per_stock_weight`
5. 동일 종목이 다수 전략에 포함되면 비중을 합산한다.
6. 현금 비중 = `max(0.0, 1.0 - 총 포지션 비중)`

**반환**: `TargetPortfolio(date, positions, cash_weight, strategy_allocations)`

#### generate_orders()

`Rebalancer.generate_orders()`에 위임한다.

### 6.2 PositionSizer

**소스**: `alphapulse/trading/portfolio/position_sizer.py`

4가지 포지션 사이징 방법을 제공한다.

| 메서드 | 설명 | 핵심 파라미터 |
|--------|------|-------------|
| `equal_weight(n_stocks)` | 균등 배분 (`1.0 / n_stocks`) | n_stocks |
| `volatility_adjusted(volatilities, target_vol)` | 변동성 역수 비중 (낮은 변동성 = 높은 비중) | `target_vol` 기본값 0.15 |
| `kelly(win_rate, avg_win, avg_loss)` | 켈리 기준 (half-kelly 적용) | 승률, 평균 손익 |
| `ai_adjusted(base_weight, opinion, max_weight)` | AI 확신도 반영 조정 | `max_weight` 기본값 0.10 |

**ai_adjusted() 상세**:

| 조건 | 조정 |
|------|------|
| `opinion.action`이 `"매도"` 또는 `"강력매도"` | 비중 0.0 (전량 매도) |
| `opinion.confidence > 0.7` | 기본 비중 * 1.2 |
| `opinion.confidence < 0.3` | 기본 비중 * 0.7 |
| 그 외 | 기본 비중 유지 |
| 최종 | `min(adjusted, max_weight)` -- 상한 cap 적용 |

**kelly() (Half-Kelly 공식)**:
```
kelly_fraction = win_rate - (1 - win_rate) / (avg_win / avg_loss)
결과 = max(0.0, kelly_fraction * 0.5)
```

### 6.3 Rebalancer

**소스**: `alphapulse/trading/portfolio/rebalancer.py`

| 항목 | 값 |
|------|-----|
| `min_trade_amount` | 100,000원 (기본값) |
| 주문 순서 | **매도 먼저, 매수 나중** |
| 주문 유형 | `MARKET` (시장가) |

#### generate_orders() 처리 흐름

**매도 주문 생성** (1단계):
1. 현재 보유 종목을 순회한다.
2. `target_weight - current_weight`로 비중 차이를 계산한다.
3. 차이 금액(`diff_w * total_value`)이 `-min_trade_amount` 미만이면 매도 주문을 생성한다.
4. 목표 비중이 0.0이면 전량 매도(`holding["quantity"]`).
5. 부분 매도 수량: `int(abs(diff_amount) / price)`

**매수 주문 생성** (2단계):
1. 목표 포트폴리오의 종목을 순회한다.
2. 비중 차이 금액이 `+min_trade_amount` 초과이면 매수 주문을 생성한다.
3. 매수 수량: `int(diff_amount / price)`

**최종 반환**: `sell_orders + buy_orders` (매도가 항상 앞에 위치)

### 6.4 PortfolioOptimizer

**소스**: `alphapulse/trading/portfolio/optimizer.py`

`scipy.optimize.minimize` (SLSQP)를 사용한 수학적 최적화를 제공한다.

| 최적화 방법 | 목적함수 | 제약 조건 |
|-----------|---------|----------|
| `mean_variance` | 최대 Sharpe Ratio | 비중 합계=1.0, 종목당 [0, max_weight] |
| `risk_parity` | 리스크 기여도 균등화 | 비중 합계=1.0, 종목당 [0.01, 1.0] |
| `min_variance` | 포트폴리오 분산 최소화 | 비중 합계=1.0, 종목당 [0, 1.0] |

**mean_variance 파라미터**:

| 파라미터 | 기본값 |
|---------|--------|
| `max_weight` | 1.0 |
| `risk_free_rate` | 0.035 (3.5%) |
| `maxiter` | 1000 |

**자동 선택 규칙 (`select_method`)**:

| pulse_signal | 선택되는 방법 |
|-------------|-------------|
| `strong_bullish`, `moderately_bullish` | `mean_variance` |
| `strong_bearish` | `min_variance` |
| 그 외 (`neutral`, `moderately_bearish`) | `risk_parity` |

모든 최적화 실패 시 균등 배분(`np.ones(n) / n`)으로 폴백한다.

---

## 7. 리스크 관리

**소스**: `alphapulse/trading/risk/manager.py`, `alphapulse/trading/risk/limits.py`

### 7.1 RiskLimits (절대 제약 조건)

**AI, 전략, 사용자 모두 오버라이드 불가.**

| 한도 | 필드명 | 기본값 | 설명 |
|------|--------|--------|------|
| 종목당 최대 비중 | `max_position_weight` | **10%** (0.10) | 단일 종목 집중 방지 |
| 섹터당 최대 비중 | `max_sector_weight` | **30%** (0.30) | 섹터 집중 방지 |
| 레버리지 ETF 최대 비중 | `max_etf_leverage` | **20%** (0.20) | 레버리지/인버스 ETF 제한 |
| 총 노출도 상한 | `max_total_exposure` | **100%** (1.0) | 차입 매수 방지 |
| 소프트 드로다운 한도 | `max_drawdown_soft` | **10%** (0.10) | 경고 발생 기준 |
| 하드 드로다운 한도 | `max_drawdown_hard` | **15%** (0.15) | 강제 디레버리징 기준 |
| 일간 최대 손실 | `max_daily_loss` | **3%** (0.03) | 일간 손실 차단 |
| 최소 현금 비율 | `min_cash_ratio` | **5%** (0.05) | 유동성 확보 |
| 단일 주문 비율 상한 | `max_single_order_pct` | **5%** (0.05) | 단일 주문 금액 제한 |
| 주문/거래량 비율 상한 | `max_order_to_volume` | **10%** (0.10) | 유동성 리스크 방지 |
| 95% VaR 상한 | `max_portfolio_var_95` | **3%** (0.03) | 포트폴리오 VaR 제한 |

### 7.2 check_order() -- 5단계 주문 검증

`RiskManager.check_order(order, portfolio)` -> `RiskDecision`

모든 매수 주문은 아래 5단계를 순서대로 통과해야 한다. 매도 주문은 1~2단계만 통과하면 승인된다.

```
[주문]
  |
  v
[1단계: 일간 손실 한도] --위반--> REJECT "일간 손실 한도 초과"
  |
  v
[2단계: 드로다운 상태]  --WARN+매수--> REJECT "드로다운 경고 상태"
  |                     --DELEVERAGE+매수--> REJECT "디레버리징 모드"
  v
[매도 주문?] --예--> APPROVE "매도 주문 승인"
  |
  v (매수만)
[3단계: 최소 현금 비율] --위반--> REJECT "최소 현금 비율 미달"
  |
  v
[4단계: 종목 비중 한도] --초과--> REDUCE_SIZE (수량 축소) 또는 REJECT
  |
  v
[5단계: 단일 주문 금액] --초과--> REDUCE_SIZE (수량 축소) 또는 REJECT
  |
  v
APPROVE "모든 한도 이내"
```

**각 단계 상세**:

**1단계: 일간 손실 한도**
- 조건: `abs(portfolio.daily_return) >= max_daily_loss * 100`
- 결과: `REJECT`
- 매도/매수 구분 없이 적용

**2단계: 드로다운 상태**
- `DrawdownManager.check(portfolio)` 호출
- `WARN` + 매수: `REJECT` ("드로다운 경고 상태 -- 신규 매수 중단")
- `DELEVERAGE` + 매수: `REJECT` ("드로다운 한도 초과 -- 디레버리징 모드")
- 매도 주문은 드로다운 상태와 무관하게 다음 단계로 진행

**3단계: 최소 현금 비율** (매수만)
- 조건: `cash / total_value < min_cash_ratio`
- 결과: `REJECT`

**4단계: 종목 비중 한도** (매수만)
- 새로운 비중 계산: `(current_qty + order.quantity) * price / total_value`
- 초과 시: `max_value / price - current_qty`로 수량 축소
- 축소 수량 <= 0이면 `REJECT`, 아니면 `REDUCE_SIZE`

**5단계: 단일 주문 금액 한도** (매수만)
- 주문 비율: `order.quantity * price / total_value`
- 초과 시: `max_amount / price`로 수량 축소
- 축소 수량 <= 0이면 `REJECT`, 아니면 `REDUCE_SIZE`

### 7.3 check_portfolio() -- 포트폴리오 전체 점검

`RiskManager.check_portfolio(portfolio)` -> `list[RiskAlert]`

점검 항목:

1. **섹터 집중도**: `RiskReportGenerator.check_concentration_alerts()`로 `max_sector_weight`(30%) 초과 확인
2. **종목 집중도**: 각 포지션의 비중이 `max_position_weight`(10%) 초과 시 경고
3. **드로다운 상태**: `WARN` -> WARNING 레벨, `DELEVERAGE` -> CRITICAL 레벨

### 7.4 RiskDecision / RiskAlert

**RiskDecision** (주문 검증 결과):

| 필드 | 타입 | 설명 |
|------|------|------|
| `action` | `RiskAction` | `APPROVE`, `REDUCE_SIZE`, `REJECT` |
| `reason` | `str` | 사유 |
| `adjusted_quantity` | `int \| None` | `REDUCE_SIZE`일 때 조정된 수량 |

**RiskAlert** (포트폴리오 경고):

| 필드 | 타입 | 설명 |
|------|------|------|
| `level` | `str` | `"INFO"`, `"WARNING"`, `"CRITICAL"` |
| `category` | `str` | `"drawdown"`, `"concentration"`, `"var"`, `"liquidity"` |
| `message` | `str` | 경고 메시지 |
| `current_value` | `float` | 현재값 |
| `limit_value` | `float` | 한도값 |

---

## 8. 드로다운 관리

**소스**: `alphapulse/trading/risk/drawdown.py`

### DrawdownManager 개요

포트폴리오 역대 최고치(peak) 대비 하락률을 실시간 모니터링하고, 한도 초과 시
자동 디레버리징 주문을 생성한다.

### 상태 전이

```
                  drawdown < 10% (soft)
              +---------------------+
              |                     |
              v                     |
         [NORMAL] ------drawdown >= 10%-----> [WARN]
              ^                                  |
              |                                  |
              +---drawdown < 10%---+             |
                                   |    drawdown >= 15% (hard)
                                   |             |
                                   |             v
                                   +------- [DELEVERAGE]
```

| 상태 | 조건 | 효과 |
|------|------|------|
| `NORMAL` | `drawdown < max_drawdown_soft (10%)` | 정상 운영 |
| `WARN` | `max_drawdown_soft (10%) <= drawdown < max_drawdown_hard (15%)` | 신규 매수 중단, 매도만 허용 |
| `DELEVERAGE` | `drawdown >= max_drawdown_hard (15%)` | 전 포지션 50% 강제 축소 |

### 드로다운 계산

```
drawdown = (peak_value - current_value) / peak_value
```

- `peak_value`는 `update_peak(current_value)`로 자동 갱신된다.
- `check()` 호출 시 내부적으로 `update_peak()`이 먼저 실행된다.

### 자동 디레버리징 (`generate_deleverage_orders`)

`DELEVERAGE` 상태에서 호출되며, 다음 규칙에 따라 매도 주문을 생성한다.

1. **정렬**: 미실현 손실(`unrealized_pnl`)이 큰(음수) 포지션부터 우선 매도
2. **축소 비율**: 각 포지션의 **50%** (`pos.quantity // 2`)
3. **주문 유형**: `MARKET` (시장가)
4. **주문 사유**: `"디레버리징: 드로다운 한도 초과 -- 50% 축소"`
5. 보유 수량이 1주(축소 수량 0)인 경우 건너뛴다.

---

## 9. VaR / CVaR

**소스**: `alphapulse/trading/risk/var.py`

### VaRCalculator

3가지 리스크 측정 방법을 제공한다.

### 9.1 Historical VaR

과거 수익률 분포에서 직접 퍼센타일을 산출한다.

```
percentile = (1 - confidence) * 100
VaR = -np.percentile(returns, percentile)
```

| 파라미터 | 기본값 | 설명 |
|---------|--------|------|
| `confidence` | 0.95 | 95% 신뢰수준 |
| 반환값 | 양수 | 손실 크기 (5% 확률로 이 금액 이상 손실 가능) |

예시: 95% 신뢰수준에서 Historical VaR = 2.5%이면, 하루에 2.5% 이상 손실할 확률이 5%라는 의미이다.

### 9.2 Parametric VaR

정규분포를 가정한 분산-공분산 방법이다.

```
portfolio_vol = sqrt(weights @ cov_matrix @ weights)
VaR = portfolio_vol * z_score(confidence)
```

- 95% 신뢰수준의 z-score: `norm.ppf(0.95)` = 약 1.645
- scipy의 `norm.ppf()`를 사용한다.

### 9.3 CVaR (Conditional VaR / Expected Shortfall)

VaR를 초과하는 손실의 평균으로, 꼬리 리스크를 반영한다.

```
1. Historical VaR 계산
2. returns 중 -VaR 이하인 값들을 추출 (tail_losses)
3. CVaR = -mean(tail_losses)
4. 꼬리 데이터가 없으면 VaR 값을 반환
```

CVaR는 항상 VaR 이상이며, "최악의 경우" 평균 손실을 의미한다.

### 일일 리포트에서의 활용

`RiskManager.daily_report()`에서:
- 수익률 이력이 20일 이상이면 VaR/CVaR를 계산한다.
- 95% 신뢰수준(`confidence=0.95`)을 사용한다.
- `max_portfolio_var_95`(3%)와 비교하여 한도 초과를 모니터링한다.

---

## 10. 스트레스 테스트

**소스**: `alphapulse/trading/risk/stress_test.py`

### StressTest 개요

사전 정의된 위기 시나리오를 포트폴리오에 적용하여 예상 손실을 시뮬레이션한다.
`run_all()`로 전 시나리오 일괄 실행도 지원하며, `add_custom_scenario()`로
사용자 정의 시나리오를 추가할 수 있다.

### 사전 정의 시나리오 (5종)

| 시나리오 ID | 설명 | KOSPI 충격 | KOSDAQ 충격 | ETF 충격 |
|-----------|------|-----------|------------|---------|
| `2020_covid` | COVID-19 급락 (2020.03) | -35% | -40% | -35% |
| `2022_rate_hike` | 금리 인상기 하락 (2022) | -25% | -35% | -25% |
| `flash_crash` | 일간 급락 (Flash Crash) | -10% | -15% | -10% |
| `won_crisis` | 원화 위기 + 외국인 이탈 | -20% | -25% | -20% |
| `sector_collapse` | 특정 섹터 붕괴 | -10% | -15% | -10% |

`sector_collapse` 시나리오의 특수 규칙: `sector` 속성이 존재하는 포지션에는
`specific_sector` 충격(-50%)이 적용된다.

### 충격 적용 로직

포지션별로 시장 유형에 따라 충격을 차등 적용한다.

```
for pos in portfolio.positions:
    if "specific_sector" in shocks and pos.stock.sector:
        shock = shocks["specific_sector"]       # -50%
    elif market == "ETF":
        shock = shocks.get("etf", ...)
    elif market == "KOSDAQ":
        shock = shocks.get("kosdaq", ...)
    else:
        shock = shocks.get("kospi", ...)

    position_loss = position_value * shock
```

### StressResult 구조

| 필드 | 타입 | 설명 |
|------|------|------|
| `scenario_name` | `str` | 시나리오 이름 |
| `description` | `str` | 시나리오 설명 |
| `estimated_loss` | `float` | 예상 손실 금액 (원, 음수) |
| `loss_pct` | `float` | 예상 손실률 (%, 음수) |
| `contributions` | `dict[str, float]` | 종목코드별 손실 기여 금액 |

### 결과 해석 가이드

| 항목 | 해석 기준 |
|------|----------|
| `loss_pct > -10%` | 양호 -- 대부분 시나리오에서 소프트 드로다운 한도 이내 |
| `-10% >= loss_pct > -15%` | 주의 -- 일부 시나리오에서 WARN 상태 진입 가능 |
| `loss_pct <= -15%` | 위험 -- DELEVERAGE 트리거 가능, 포트폴리오 방어력 부족 |
| `contributions` 집중 | 특정 종목의 기여가 과도하면 종목/섹터 집중 리스크 존재 |

### 일일 리포트 통합

`RiskManager.daily_report()`에서 `stress_test.run_all(portfolio)`를 자동 실행하여
5개 시나리오 전체 결과를 일일 리스크 리포트에 포함한다.

---

## 부록: 소스 파일 참조

| 모듈 | 파일 경로 |
|------|----------|
| BaseStrategy | `alphapulse/trading/strategy/base.py` |
| MomentumStrategy | `alphapulse/trading/strategy/momentum.py` |
| ValueStrategy | `alphapulse/trading/strategy/value.py` |
| QualityMomentumStrategy | `alphapulse/trading/strategy/quality_momentum.py` |
| TopDownETFStrategy | `alphapulse/trading/strategy/topdown_etf.py` |
| StrategyAllocator | `alphapulse/trading/strategy/allocator.py` |
| StrategyAISynthesizer | `alphapulse/trading/strategy/ai_synthesizer.py` |
| PortfolioManager | `alphapulse/trading/portfolio/manager.py` |
| PositionSizer | `alphapulse/trading/portfolio/position_sizer.py` |
| Rebalancer | `alphapulse/trading/portfolio/rebalancer.py` |
| PortfolioOptimizer | `alphapulse/trading/portfolio/optimizer.py` |
| RiskManager | `alphapulse/trading/risk/manager.py` |
| RiskLimits | `alphapulse/trading/risk/limits.py` |
| DrawdownManager | `alphapulse/trading/risk/drawdown.py` |
| VaRCalculator | `alphapulse/trading/risk/var.py` |
| StressTest | `alphapulse/trading/risk/stress_test.py` |
| 열거형 (enums) | `alphapulse/trading/core/enums.py` |
