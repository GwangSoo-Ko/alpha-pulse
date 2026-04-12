# 백테스트 시스템 운영 레퍼런스

> **모듈**: `alphapulse/trading/backtest/`
> **최종 갱신**: 2026-04-11

---

## 1. 개요

AlphaPulse 백테스트 시스템은 **이벤트 드리븐(Event-Driven)** 아키텍처로 설계된
과거 시뮬레이션 엔진이다. 거래일을 1일 단위로 순회하면서 다음 파이프라인을
반복 실행한다.

```
거래일 루프
  advance_to(date) -> 전략 시그널 생성 -> 주문 생성 -> SimBroker 체결 -> 스냅샷 저장
```

**핵심 설계 원칙:**

| 원칙 | 구현 |
|------|------|
| Look-Ahead Bias 방지 | `advance_to()`로 현재 날짜 이후 데이터 접근 차단 |
| 비용 현실성 | CostModel로 수수료/세금/슬리피지를 실거래 수준으로 반영 |
| 전략 독립성 | StrategyProtocol + order_generator 주입으로 전략-엔진 분리 |
| 동기(Sync) 실행 | 엔진 전체가 동기 코드. AI 종합 판단만 Async |

**주요 클래스 의존 관계:**

```
BacktestEngine
  |- BacktestConfig         (설정: 기간, 자본, 비용, 벤치마크)
  |- HistoricalDataFeed     (데이터 피드 인터페이스)
  |    `- TradingStoreDataFeed  (SQLite 기반 실구현체)
  |- SimBroker              (가상 체결 브로커)
  |    `- CostModel         (수수료/세금/슬리피지)
  |- KRXCalendar            (한국거래소 거래일)
  |- BacktestMetrics        (성과 지표 계산)
  `- order_generator        (시그널 -> 주문 변환 callable)
```

---

## 2. 실행 흐름

`BacktestEngine.run()` 메서드가 백테스트 전체 흐름을 제어한다.

### 2.1 전체 시퀀스

```python
# engine.py BacktestEngine.run() 핵심 로직
def run(self) -> BacktestResult:
    trading_days = self._calendar.trading_days_between(start_date, end_date)

    for date in trading_days:
        # (1) 데이터 피드 전진 -- 미래 데이터 차단
        self.data_feed.advance_to(date)

        # (2) 전략별 시그널 수집
        for strategy in self.strategies:
            if strategy.should_rebalance(last, date, market_context):
                signals = strategy.generate_signals(universe, market_context)
                all_signals.extend(signals)

        # (3) 현재 스냅샷 생성 (주문 전 상태)
        snapshot = self._take_snapshot(date, snapshots)

        # (4) 주문 생성 및 체결
        orders = self.order_generator(all_signals, snapshot, self.broker)
        for order in orders:
            self.broker.submit_order(order)

        # (5) 체결 후 최종 스냅샷 저장
        final_snapshot = self._take_snapshot(date, snapshots)
        snapshots.append(final_snapshot)

    # (6) 벤치마크 수익률 + 성과 지표 계산
    metrics = self._metrics_calc.calculate(snapshots, benchmark_returns, ...)
    return BacktestResult(snapshots, trades, metrics, config)
```

### 2.2 단계별 상세

#### (1) advance_to(date)

데이터 피드의 `current_date`를 해당 거래일로 설정한다. 이후 모든 데이터
조회에서 이 날짜 이후의 데이터는 접근이 차단된다.

#### (2) 시그널 생성

각 전략의 `should_rebalance(last_date, current_date, market_context)`로
리밸런싱 여부를 판단한 후, `generate_signals(universe, market_context)`로
매매 시그널을 생성한다. `last_rebalance` 딕셔너리가 전략별 마지막 리밸런싱
날짜를 추적한다.

시장 컨텍스트는 `data_feed.get_market_context(date)`로 획득하며,
`TradingStoreDataFeed`에서는 백테스트 환경에서 중립값을 반환한다.

```python
# store_feed.py -- 백테스트 시장 컨텍스트 (중립)
{"date": date, "pulse_score": 0.0, "pulse_signal": "중립 (Neutral)", ...}
```

#### (3) 스냅샷 생성

`SimBroker.get_balance()`로 현금 + 포지션 평가액을 합산하고,
이전 스냅샷 대비 일간 수익률, 누적 수익률, 드로다운을 계산한다.

```
daily_return  = (total_value - prev_value) / prev_value * 100
cumulative    = (total_value - initial_capital) / initial_capital * 100
drawdown      = -(peak - total_value) / peak * 100
```

#### (4) 주문 생성 및 체결

주입된 `order_generator(signals, snapshot, broker)`가 시그널을 주문 리스트로
변환하고, `SimBroker.submit_order(order)`가 각 주문을 즉시 체결 처리한다.

#### (5) 최종 스냅샷

체결 후 변경된 현금/포지션을 반영한 스냅샷을 저장한다.

#### (6) 성과 지표 계산

전체 거래일 순회가 완료되면 `BacktestMetrics.calculate()`로 수익률, 리스크,
벤치마크 비교 지표를 일괄 산출한다.

---

## 3. Look-Ahead Bias 방지

백테스트의 신뢰성을 보장하는 핵심 메커니즘이다. 세 가지 계층으로 미래 데이터
유출을 차단한다.

### 3.1 advance_to 메커니즘

```python
# data_feed.py HistoricalDataFeed
def advance_to(self, date: str) -> None:
    self.current_date = date
```

엔진이 각 거래일 루프 시작 시 `advance_to(date)`를 호출하여 시뮬레이션 시계를
전진시킨다. 이후 모든 데이터 조회는 이 날짜 이전 데이터만 반환한다.

### 3.2 get_ohlcv의 end 체크

두 가지 구현체 모두 동일한 패턴으로 미래 접근을 차단한다.

**HistoricalDataFeed (인메모리):**

```python
def get_ohlcv(self, code, start, end):
    assert end <= self.current_date, \
        f"Look-ahead bias! Requested {end} but current date is {self.current_date}"
    return [bar for bar in bars if start <= bar.date <= end]
```

**TradingStoreDataFeed (SQLite):**

```python
def get_ohlcv(self, code, start, end):
    if self.current_date and end > self.current_date:
        raise AssertionError(
            f"Look-ahead bias: requested end={end} > current={self.current_date}"
        )
    rows = self.store.get_ohlcv(code, start, end)
    return [OHLCV(...) for r in rows]
```

`end > current_date`이면 `AssertionError`가 발생하여 백테스트가 즉시
중단된다. 이는 의도적으로 assertion을 사용하여 개발 단계에서 미래 참조 버그를
조기에 발견하도록 설계되었다.

### 3.3 수급 데이터 필터링

`TradingStoreDataFeed.get_investor_flow()`는 DB에서 가져온 수급 데이터 중
`current_date` 이후 레코드를 추가로 필터링한다.

```python
def get_investor_flow(self, code, days):
    rows = self.store.get_investor_flow(code, days=days)
    if self.current_date:
        rows = [r for r in rows if r.get("date", "") <= self.current_date]
    # foreign_net, institutional_net, individual_net 합산
```

---

## 4. 시뮬레이션 브로커 (SimBroker)

`SimBroker`는 Broker Protocol을 구현하는 가상 체결 엔진이다. 실제 증권사 API
없이 주문 체결, 포지션 관리, 잔고 관리를 시뮬레이션한다.

### 4.1 체결 규칙

#### MARKET 주문

당일 **종가(close)**로 체결한다. 이는 보수적 가정으로, 실매매에서 장중
시점을 정확히 알 수 없으므로 종가를 사용한다.

```python
if order.order_type == OrderType.MARKET:
    return bar.close
```

#### LIMIT 매수

당일 **저가(low) <= 지정가**이면 **지정가**로 체결된다. 저가가 지정가보다
높으면 미체결(rejected, "LIMIT 미체결 (저가 > 지정가)").

```python
if order.side == Side.BUY:
    if bar.low <= order.price:
        return order.price  # 지정가로 체결
    return None             # 미체결
```

#### LIMIT 매도

당일 **고가(high) >= 지정가**이면 **지정가**로 체결된다. 고가가 지정가보다
낮으면 미체결(rejected, "LIMIT 미체결 (고가 < 지정가)").

```python
if order.side == Side.SELL:
    if bar.high >= order.price:
        return order.price  # 지정가로 체결
    return None             # 미체결
```

### 4.2 슬리피지 (Slippage)

`CostModel.estimate_slippage()`가 주문량 대비 일평균 거래대금 비율로
시장 충격(Market Impact)을 추정한다.

**volume_based 모델 (기본값):**

```
impact_ratio = (주문수량 * 가격) / (일평균거래량 * 가격)
```

| impact_ratio | 슬리피지 |
|:---:|:---:|
| < 0.01 (1% 미만) | 0.0% |
| 0.01 ~ 0.05 (1~5%) | 0.1% |
| >= 0.05 (5% 이상) | 0.3% |
| 거래대금 0 | 0.3% (폴백) |

**다른 슬리피지 모델:**

| 모델 | 동작 |
|------|------|
| `"volume_based"` | 위 테이블에 따른 거래량 비례 슬리피지 |
| `"fixed"` | 일률 0.1% |
| `"none"` | 슬리피지 없음 (0%) |

슬리피지 적용 방향:
- **매수**: `adjusted_price = fill_price * (1 + slippage_pct)` -- 불리하게 높은 가격
- **매도**: `adjusted_price = fill_price * (1 - slippage_pct)` -- 불리하게 낮은 가격

### 4.3 수수료 및 세금

`CostModel` 기본값 (소스코드 및 Config 환경변수 기준):

| 항목 | 비율 | 환경변수 | 비고 |
|------|------|----------|------|
| 수수료 (`commission_rate`) | **0.015%** (0.00015) | `BACKTEST_COMMISSION` | 매수/매도 양방향 부과 |
| 주식 매도세 (`tax_rate_stock`) | **0.18%** (0.0018) | `BACKTEST_TAX` | 매도 시에만 부과 |
| ETF 매도세 (`tax_rate_etf`) | **0%** (0.0) | -- | ETF 거래세 면제 |

**수수료 계산:**

```python
commission = amount * commission_rate
# 예: 1억원 매수 시 수수료 = 100,000,000 * 0.00015 = 15,000원
```

**세금 계산:**

```python
tax = amount * (tax_rate_etf if is_etf else tax_rate_stock)
# 예: 1억원 주식 매도 시 세금 = 100,000,000 * 0.0018 = 180,000원
# ETF 매도 시 세금 = 0원
```

ETF 판별 기준: `order.stock.market == "ETF"`

**비용 반영 순서:**

매수:
```
total_amount = quantity * adjusted_price
commission = total_amount * commission_rate
total_cost = total_amount + commission
cash -= total_cost
```

매도:
```
total_amount = quantity * adjusted_price
commission = total_amount * commission_rate
tax = total_amount * tax_rate_stock  (ETF이면 0)
cash += total_amount - commission - tax
```

### 4.4 현금/보유수량 검증

- **매수**: `total_cost > cash`이면 거부 ("현금 부족")
- **매도**: 해당 종목 미보유 또는 `보유수량 < 주문수량`이면 거부 ("보유 수량 부족")
- **데이터 없음**: 당일 OHLCV 바가 없으면 거부 ("당일 데이터 없음")

### 4.5 포지션 관리

**매수 시 평균단가 가중평균:**

```python
total_qty = 기존수량 + 신규수량
avg_price = (기존평균가 * 기존수량 + 체결가 * 신규수량) / total_qty
```

**매도 시 수량 차감:**

```python
position.quantity -= 매도수량
if position.quantity == 0:
    del positions[code]   # 완전 청산 시 포지션 삭제
```

**평가액 계산:**

```python
positions_value = sum(수량 * data_feed.get_latest_price(code) for code in positions)
total_value = cash + positions_value
```

---

## 5. 주문 생성기 (Order Generator)

`BacktestEngine`은 시그널에서 주문으로의 변환을 외부에 위임한다.
`order_generator` callable을 주입받아 전략-엔진 간 결합도를 최소화한다.

### 5.1 make_default_order_generator (균등비중)

**시그니처:**

```python
make_default_order_generator(top_n: int = 20, initial_capital: float = 100_000_000)
```

**동작 순서:**

1. 모든 시그널을 **점수(score) 내림차순** 정렬
2. 상위 `top_n`개 선택
3. **균등 비중** 계산: `per_weight = 1.0 / len(top_signals)`
4. 종목별 목표 금액: `per_position_value = total_value * per_weight`
5. **매도 주문 생성**: 보유 중이지만 타깃이 아닌 종목 전량 MARKET 매도
6. **매수 주문 생성**: 타깃이지만 미보유/비중 미달 종목 MARKET 매수
   - `target_qty = int(per_position_value / price)`
   - `buy_qty = target_qty - current_qty`

모든 주문은 `OrderType.MARKET`으로 생성된다 (종가 체결).

### 5.2 make_risk_checked_order_generator (리스크 검증)

**시그니처:**

```python
make_risk_checked_order_generator(portfolio_manager, risk_manager, top_n: int = 20)
```

내부적으로 `make_default_order_generator()`가 raw 주문을 생성하고,
`risk_manager.check_order(order, snapshot)`가 각 주문을 검증한다.

| RiskAction | 처리 |
|:---:|------|
| `APPROVE` | 주문 그대로 통과 |
| `REDUCE_SIZE` | `adjusted_quantity`로 수량 축소 후 통과 |
| `REJECT` | 주문 폐기 (스킵) |

리스크 체크 예외 발생 시 해당 주문은 **통과 처리**된다 (방어적 설계).

### 5.3 _get_price 폴백 체인

주문 생성 시 현재가 조회에 4단계 폴백을 적용한다.

```
(1) broker.execution_prices[code]  -- SimBroker 테스트용 가격 맵
    |
    v (없으면)
(2) broker.get_current_price(code)  -- 직접 가격 조회 메서드
    |
    v (없으면)
(3) broker.data_feed.get_latest_price(code)  -- 데이터 피드 종가
    |
    v (없으면)
(4) broker.data_feed.get_bar(code).close  -- OHLCV 바의 종가
    |
    v (없으면)
(5) None 반환 -> 해당 종목 매수 스킵
```

---

## 6. 성과 지표 (BacktestMetrics)

`BacktestMetrics.calculate()`가 반환하는 모든 지표와 계산 공식이다.
연환산 기준 영업일: **252일**.

### 6.1 수익률 지표

| 지표 | 키 | 공식 | 단위 |
|------|----|------|------|
| 총 수익률 | `total_return` | `(최종값 - 시작값) / 시작값 * 100` | % |
| 연환산 수익률 (CAGR) | `cagr` | `((최종값 / 시작값) ^ (1 / years) - 1) * 100` | % |
| 월별 수익률 | `monthly_returns` | 일간 수익률을 월(YYYYMM) 단위 그룹화 후 복리 계산: `(prod(1 + r_daily) - 1) * 100` | list[%] |

- `years = n_days / 252`
- `daily_returns = diff(values) / values[:-1]`

### 6.2 리스크 지표

| 지표 | 키 | 공식 | 단위 |
|------|----|------|------|
| 변동성 | `volatility` | `std(daily_returns, ddof=1) * sqrt(252) * 100` | % (연환산) |
| 최대 낙폭 (MDD) | `max_drawdown` | `-(peak - trough) / peak * 100` | % (음수) |
| MDD 지속 기간 | `max_drawdown_duration` | 고점에서 MDD 최저점까지 영업일 수 | 일 |
| 하방 편차 | `downside_deviation` | `std(negative_returns, ddof=1) * sqrt(252) * 100` | % (연환산) |

MDD 계산은 running peak 방식: 배열을 순회하며 누적 최고점을 갱신하고,
각 시점의 하락폭을 추적한다.

### 6.3 리스크 조정 수익 지표

| 지표 | 키 | 공식 | 단위 |
|------|----|------|------|
| 샤프 비율 | `sharpe_ratio` | `mean(excess_daily) / std(excess_daily, ddof=1) * sqrt(252)` | 비율 |
| 소르티노 비율 | `sortino_ratio` | `mean(excess_daily) / std(negative_returns, ddof=1) * sqrt(252)` | 비율 |
| 칼마 비율 | `calmar_ratio` | `CAGR / abs(MDD)` | 비율 |

- `excess_daily = daily_returns - (risk_free_rate / 252)`
- `risk_free_rate` 기본값: **3.5%** (연율, `BacktestConfig.risk_free_rate`)

### 6.4 거래 분석 지표

매수-매도 쌍(Round Trip)으로 라운드트립을 구성하여 계산한다. 종목별로
매수를 FIFO 순서로 매도와 매칭한다.

| 지표 | 키 | 공식 | 단위 |
|------|----|------|------|
| 총 거래 수 | `total_trades` | 완성된 라운드트립 횟수 | 건 |
| 승률 | `win_rate` | `wins / total_trades * 100` | % |
| 수익 팩터 | `profit_factor` | `total_profit / total_loss` | 비율 |
| 평균 이익 | `avg_win` | `total_profit / wins` | 원 |
| 평균 손실 | `avg_loss` | `total_loss / losses` | 원 |
| 회전율 | `turnover` | `total_traded_amount / initial_capital` | 비율 |

라운드트립 손익:
```
pnl = (매도체결가 - 매수체결가) * 매도수량 - 매도수수료 - 매도세금 - 매수수수료
```

### 6.5 벤치마크 비교 지표

| 지표 | 키 | 공식 | 단위 |
|------|----|------|------|
| 벤치마크 수익률 | `benchmark_return` | `(prod(1 + br) - 1) * 100` | % |
| 초과 수익률 | `excess_return` | `portfolio_total - benchmark_total` | % |
| 베타 | `beta` | `Cov(Rp, Rb) / Var(Rb)` | 비율 |
| 알파 (젠센) | `alpha` | `[mean(Rp) - (Rf_daily + beta * (mean(Rb) - Rf_daily))] * 252 * 100` | % (연환산) |
| 추적 오차 | `tracking_error` | `std(Rp - Rb, ddof=1) * sqrt(252) * 100` | % (연환산) |
| 정보 비율 | `information_ratio` | `mean(Rp - Rb) / std(Rp - Rb, ddof=1) * sqrt(252)` | 비율 |

- `Rp` = 포트폴리오 일간 수익률, `Rb` = 벤치마크 일간 수익률
- `Rf_daily` = `risk_free_rate / 252`
- 벤치마크 기본값: `"KOSPI"` (`BacktestConfig.benchmark`)

**스냅샷 부족 시 (1개 이하):** 모든 지표가 0.0으로 반환된다.

---

## 7. 거래일 캘린더 (KRXCalendar)

`KRXCalendar`는 한국거래소(KRX) 영업일을 관리한다.

### 7.1 거래일 판별 기준

```
거래일 = 평일(월~금) AND NOT 공휴일
```

**고정 공휴일 (매년 동일):**

| 날짜 | 명칭 |
|------|------|
| 1/1 | 신정 |
| 3/1 | 삼일절 |
| 5/5 | 어린이날 |
| 6/6 | 현충일 |
| 8/15 | 광복절 |
| 10/3 | 개천절 |
| 10/9 | 한글날 |
| 12/25 | 크리스마스 |

**변동 공휴일 (음력 명절, 대체공휴일 등):**

현재 2025~2026년이 등록되어 있다. 매년 초 KRX 공시 기반으로 갱신해야 한다.

- 2025: 설날(1/28~30), 대체공휴일(5/6), 추석(10/5~7)
- 2026: 설날(2/16~18), 대체공휴일(5/6), 추석(9/24~26)

### 7.2 trading_days_between

```python
def trading_days_between(self, start: str, end: str) -> list[str]:
```

시작일부터 종료일까지 (양 끝 포함) 모든 거래일을 `YYYYMMDD` 문자열
리스트로 반환한다. `BacktestEngine.run()`이 이 리스트를 순회하며 일별
시뮬레이션을 실행한다.

### 7.3 기타 메서드

| 메서드 | 설명 |
|--------|------|
| `is_trading_day(date)` | 해당 날짜가 거래일인지 판단 |
| `next_trading_day(date)` | 다음 거래일 반환 |
| `prev_trading_day(date)` | 이전 거래일 반환 |
| `is_half_day(date)` | 반일장 여부 (현재 항상 `False`, 스텁) |

---

## 8. CLI 명령어

### 8.1 기본 사용법

```bash
ap trading backtest [OPTIONS]
```

### 8.2 옵션

| 옵션 | 타입 | 기본값 | 설명 |
|------|------|--------|------|
| `--strategy` | str | `"momentum"` | 전략 ID |
| `--start` | str | 3년 전 | 시작일 (YYYYMMDD) |
| `--end` | str | 오늘 | 종료일 (YYYYMMDD) |
| `--capital` | int | `100,000,000` (1억) | 초기 투자금 (원) |
| `--market` | str | `"KOSPI"` | 시장 (KOSPI/KOSDAQ) |
| `--top` | int | `20` | 상위 N종목 편입 |

**지원 전략:**

| 전략 ID | 클래스 | 설명 |
|---------|--------|------|
| `momentum` | `MomentumStrategy` | 모멘텀 전략 |
| `value` | `ValueStrategy` | 가치 전략 |
| `quality_momentum` | `QualityMomentumStrategy` | 퀄리티+모멘텀 복합 전략 |

### 8.3 실행 예시

```bash
# 기본 실행 (모멘텀, 최근 3년, KOSPI, 상위 20종목, 1억원)
ap trading backtest

# 가치 전략, 기간 지정, 자본금 2억
ap trading backtest --strategy value --start 20230101 --end 20260410 --capital 200000000

# 퀄리티모멘텀, 상위 15종목
ap trading backtest --strategy quality_momentum --top 15

# KOSDAQ 시장
ap trading backtest --market KOSDAQ
```

### 8.4 출력 포맷

```
============================================================
 백테스트 시작
============================================================
 전략:    momentum
 기간:    20230101 ~ 20260410
 자본금:  100,000,000원
 시장:    KOSPI
 상위 N:  20
============================================================

[1/4] 데이터 피드 로드...
  -> 842종목
[2/4] 전략 초기화...
  -> momentum 로드
[3/4] 엔진 실행...

[4/4] 결과 리포트

============================================================
 성과 지표
============================================================
 총 수익률:        +45.23%
 CAGR:             +13.21%
 샤프 비율:        +1.15
 소르티노 비율:    +1.78
 최대 낙폭 (MDD):  -18.45%
 변동성 (연환산):  15.32%
 승률:             62.5%
 총 거래 수:       184
 스냅샷 수:        732
============================================================
 시작 자산: 100,000,000원 (20230102)
 최종 자산: 145,230,000원 (20260410)
```

### 8.5 실행 과정

CLI 내부 실행 순서:

1. **데이터 피드 로드** -- `TradingStoreDataFeed(db_path, market=market)`
2. **전략 초기화** -- `MultiFactorRanker` + `FactorCalculator` + 전략 클래스 생성
3. **엔진 실행** -- `BacktestConfig` + `CostModel` + `BacktestEngine.run()`
4. **결과 출력** -- `BacktestResult.metrics` 딕셔너리에서 지표 추출

CostModel 생성 시 Config에서 수수료/세율을 읽는다:
```python
cost_model = CostModel(
    commission_rate=cfg.BACKTEST_COMMISSION,   # 환경변수 또는 기본 0.00015
    tax_rate_stock=cfg.BACKTEST_TAX,           # 환경변수 또는 기본 0.0018
)
```

---

## 9. 제약 사항 및 개선 계획

### 9.1 현재 제약 사항

| 항목 | 설명 | 영향도 |
|------|------|--------|
| **일봉 전용** | 분봉/틱 데이터 미지원. OHLCV가 일봉 기준. | 장중 전략 백테스트 불가 |
| **MARKET 주문 = 종가 체결** | 보수적 가정이지만 장중 매매를 정확히 반영하지 못함 | 실매매와 체결가 괴리 가능 |
| **벤치마크 데이터 의존** | `data_feed.get_bar("KOSPI")` 호출. 벤치마크가 데이터 피드에 없으면 벤치마크 수익률 0으로 산출 | 벤치마크 지표 부정확 가능 |
| **시장 컨텍스트 중립** | `TradingStoreDataFeed.get_market_context()`가 백테스트에서 항상 중립값 반환 | 시장 상황 반영 전략의 정확도 저하 |
| **반일장 미지원** | `KRXCalendar.is_half_day()` 항상 False | 단축거래일 미반영 |
| **변동 공휴일 수동 갱신** | 2025-2026년만 등록. 이외 연도는 고정 공휴일만 적용 | 거래일 판단 오류 가능 |
| **FIFO 라운드트립** | 거래 분석이 종목별 FIFO 기준 매수-매도 매칭 | 실제 세금 계산과 다를 수 있음 |
| **공매도 불가** | SimBroker가 롱 포지션만 지원 (매도 시 보유 수량 검증) | 숏 전략 백테스트 불가 |
| **주문 취소 불가** | `SimBroker.cancel_order()`는 항상 False (즉시 체결) | LIMIT 주문 관리 제한 |

### 9.2 BacktestConfig 기본값 요약

| 파라미터 | 기본값 | 설명 |
|----------|--------|------|
| `initial_capital` | `100,000,000` (1억) | Config에서 설정 가능 |
| `benchmark` | `"KOSPI"` | 벤치마크 지수 코드 |
| `use_ai` | `False` | AI 종합 판단 사용 여부 |
| `risk_free_rate` | `0.035` (3.5%) | 무위험 이자율 (연율) |

### 9.3 환경변수

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `BACKTEST_INITIAL_CAPITAL` | `100000000` | 초기 투자금 |
| `BACKTEST_COMMISSION` | `0.00015` | 수수료율 (0.015%) |
| `BACKTEST_TAX` | `0.0018` | 주식 매도세율 (0.18%) |

### 9.4 향후 개선 방향

- 분봉 데이터 지원 확대
- 과거 시장 컨텍스트 재구축 (Market Pulse 히스토리)
- 벤치마크 데이터 자동 수집/검증
- KRX 공휴일 자동 업데이트 (API 또는 크롤링)
- 공매도 포지션 시뮬레이션
- 복수 벤치마크 비교
- 시나리오 분석 (What-if) 지원

---

## 소스 파일 참조

| 파일 | 설명 |
|------|------|
| `alphapulse/trading/backtest/engine.py` | BacktestEngine, BacktestConfig, BacktestResult |
| `alphapulse/trading/backtest/sim_broker.py` | SimBroker (가상 체결) |
| `alphapulse/trading/backtest/data_feed.py` | HistoricalDataFeed (인메모리 데이터 피드) |
| `alphapulse/trading/backtest/store_feed.py` | TradingStoreDataFeed (SQLite 데이터 피드) |
| `alphapulse/trading/backtest/order_gen.py` | 주문 생성기 (default, risk_checked) |
| `alphapulse/trading/backtest/metrics.py` | BacktestMetrics (성과 지표) |
| `alphapulse/trading/core/calendar.py` | KRXCalendar (거래일 캘린더) |
| `alphapulse/trading/core/cost_model.py` | CostModel (수수료/세금/슬리피지) |
| `alphapulse/trading/core/models.py` | OHLCV, Order, OrderResult, Signal, PortfolioSnapshot |
| `alphapulse/trading/core/enums.py` | Side, OrderType, RiskAction |
| `alphapulse/cli.py` | `ap trading backtest` CLI 명령어 |
