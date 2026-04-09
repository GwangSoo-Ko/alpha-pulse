# Trading System Phase 3: Backtest + AI Synthesis

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 백테스트 엔진(Phase 7)과 AI 전략 종합(Phase 8)을 구현한다. 백테스트 엔진은 히스토리 데이터를 시간 순서대로 순회하며 전략 파이프라인을 시뮬레이션하고, 포괄적 성과 지표와 리포트를 생성한다. AI 종합은 Phase 2에서 스텁으로 남긴 `StrategyAISynthesizer`를 Google Gemini 기반으로 완전 구현한다.

**Architecture:** `trading/backtest/`는 완전 Sync. SimBroker가 Broker Protocol을 구현하여 전략/포트폴리오/리스크 코드 변경 없이 브로커만 교체하는 구조. `trading/strategy/ai_synthesizer.py`만 Async (asyncio.to_thread 패턴).

**Tech Stack:** Python 3.11+, numpy, pandas, sqlite3, pytest, dataclasses, google-genai (AI Synthesizer만)

**Spec:** `docs/superpowers/specs/2026-04-09-trading-system-design.md` (Section 9 + 6.5)

**Depends on:** Phase 1 + Phase 2 must be completed first.

---

## File Structure

### New Files to Create

```
alphapulse/trading/backtest/
├── __init__.py
├── data_feed.py         # Task 1: HistoricalDataFeed (look-ahead bias 방지)
├── sim_broker.py        # Task 2: SimBroker (가상 체결)
├── metrics.py           # Task 3: BacktestMetrics (성과 지표)
├── engine.py            # Task 4: BacktestEngine (메인 루프)
├── report.py            # Task 5: BacktestReport (터미널 + HTML)
└── store.py             # Task 6: BacktestStore (backtest.db)

tests/trading/backtest/
├── __init__.py
├── test_data_feed.py
├── test_sim_broker.py
├── test_metrics.py
├── test_engine.py
├── test_report.py
└── test_store.py

tests/trading/strategy/
└── test_ai_synthesizer.py   # Task 7: AI Synthesizer 전용 테스트
```

### Files to Modify

- `alphapulse/trading/strategy/ai_synthesizer.py` — Task 7: Phase 2 스텁 → 완전 구현

---

## Task 1: HistoricalDataFeed (look-ahead bias 방지)

**Files:**
- Create: `alphapulse/trading/backtest/__init__.py`
- Create: `alphapulse/trading/backtest/data_feed.py`
- Test: `tests/trading/backtest/__init__.py`
- Test: `tests/trading/backtest/test_data_feed.py`

- [ ] **Step 1: Create package structure**

```bash
mkdir -p alphapulse/trading/backtest
mkdir -p tests/trading/backtest
```

Create empty `__init__.py` files:

`alphapulse/trading/backtest/__init__.py`:
```python
"""백테스트 엔진 — 히스토리 시뮬레이션."""
```

`tests/trading/backtest/__init__.py`: empty file.

- [ ] **Step 2: Write failing test**

`tests/trading/backtest/test_data_feed.py`:
```python
"""HistoricalDataFeed 테스트 — look-ahead bias 방지 검증."""

import pytest

from alphapulse.trading.backtest.data_feed import HistoricalDataFeed
from alphapulse.trading.core.models import OHLCV


@pytest.fixture
def sample_data():
    """삼성전자 5일치 OHLCV 데이터."""
    return {
        "005930": [
            OHLCV(date="20260406", open=72000, high=73000, low=71500, close=72500, volume=10_000_000),
            OHLCV(date="20260407", open=72500, high=74000, low=72000, close=73500, volume=12_000_000),
            OHLCV(date="20260408", open=73500, high=75000, low=73000, close=74000, volume=11_000_000),
            OHLCV(date="20260409", open=74000, high=74500, low=72500, close=73000, volume=9_000_000),
            OHLCV(date="20260410", open=73000, high=73500, low=71000, close=71500, volume=15_000_000),
        ],
        "000660": [
            OHLCV(date="20260406", open=150000, high=155000, low=149000, close=153000, volume=3_000_000),
            OHLCV(date="20260407", open=153000, high=157000, low=152000, close=156000, volume=4_000_000),
            OHLCV(date="20260408", open=156000, high=158000, low=154000, close=155000, volume=3_500_000),
            OHLCV(date="20260409", open=155000, high=156000, low=150000, close=151000, volume=5_000_000),
            OHLCV(date="20260410", open=151000, high=152000, low=148000, close=149000, volume=6_000_000),
        ],
    }


class TestHistoricalDataFeed:
    def test_advance_to_sets_current_date(self, sample_data):
        """advance_to로 현재 날짜를 전진시킨다."""
        feed = HistoricalDataFeed(sample_data)
        feed.advance_to("20260407")
        assert feed.current_date == "20260407"

    def test_get_ohlcv_within_current_date(self, sample_data):
        """현재 날짜 이전 데이터는 정상 반환한다."""
        feed = HistoricalDataFeed(sample_data)
        feed.advance_to("20260408")
        result = feed.get_ohlcv("005930", "20260406", "20260408")
        assert len(result) == 3
        assert result[0].date == "20260406"
        assert result[-1].date == "20260408"

    def test_look_ahead_bias_raises(self, sample_data):
        """미래 데이터 요청 시 AssertionError를 발생시킨다."""
        feed = HistoricalDataFeed(sample_data)
        feed.advance_to("20260407")
        with pytest.raises(AssertionError, match="Look-ahead bias"):
            feed.get_ohlcv("005930", "20260406", "20260409")

    def test_get_ohlcv_exact_current_date(self, sample_data):
        """현재 날짜와 동일한 end는 허용한다."""
        feed = HistoricalDataFeed(sample_data)
        feed.advance_to("20260409")
        result = feed.get_ohlcv("005930", "20260409", "20260409")
        assert len(result) == 1
        assert result[0].close == 73000

    def test_get_ohlcv_unknown_code_returns_empty(self, sample_data):
        """존재하지 않는 종목은 빈 리스트를 반환한다."""
        feed = HistoricalDataFeed(sample_data)
        feed.advance_to("20260410")
        result = feed.get_ohlcv("999999", "20260406", "20260410")
        assert result == []

    def test_get_latest_price(self, sample_data):
        """현재 날짜의 종가를 반환한다."""
        feed = HistoricalDataFeed(sample_data)
        feed.advance_to("20260408")
        assert feed.get_latest_price("005930") == 74000

    def test_get_latest_price_no_data_returns_zero(self, sample_data):
        """데이터 없는 종목은 0을 반환한다."""
        feed = HistoricalDataFeed(sample_data)
        feed.advance_to("20260408")
        assert feed.get_latest_price("999999") == 0.0

    def test_get_bar_returns_current_date_ohlcv(self, sample_data):
        """현재 날짜의 OHLCV 바를 반환한다."""
        feed = HistoricalDataFeed(sample_data)
        feed.advance_to("20260407")
        bar = feed.get_bar("005930")
        assert bar is not None
        assert bar.date == "20260407"
        assert bar.close == 73500

    def test_get_bar_no_data_returns_none(self, sample_data):
        """현재 날짜에 데이터 없는 종목은 None을 반환한다."""
        feed = HistoricalDataFeed(sample_data)
        feed.advance_to("20260407")
        assert feed.get_bar("999999") is None

    def test_get_available_codes(self, sample_data):
        """등록된 종목 코드 목록을 반환한다."""
        feed = HistoricalDataFeed(sample_data)
        codes = feed.get_available_codes()
        assert set(codes) == {"005930", "000660"}

    def test_initial_state_before_advance(self, sample_data):
        """advance_to 호출 전에는 current_date가 빈 문자열이다."""
        feed = HistoricalDataFeed(sample_data)
        assert feed.current_date == ""
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/trading/backtest/test_data_feed.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'alphapulse.trading.backtest.data_feed'`

- [ ] **Step 4: Implement HistoricalDataFeed**

`alphapulse/trading/backtest/data_feed.py`:
```python
"""히스토리 데이터 피드 — look-ahead bias 방지.

HistoricalDataFeed는 현재 날짜를 추적하며, 미래 데이터 접근을 차단한다.
백테스트 엔진이 advance_to()로 날짜를 전진시키고, 전략/포트폴리오가 데이터를 요청한다.
"""

from alphapulse.trading.core.models import OHLCV


class HistoricalDataFeed:
    """히스토리 데이터 피드.

    미래 데이터 접근을 차단하여 look-ahead bias를 방지한다.
    advance_to()로 현재 날짜를 전진시키며, end > current_date인 요청은 거부한다.

    Attributes:
        current_date: 현재 시뮬레이션 날짜 (YYYYMMDD).
    """

    def __init__(self, all_data: dict[str, list[OHLCV]]) -> None:
        """초기화.

        Args:
            all_data: 종목코드 → OHLCV 리스트 매핑. 날짜순 정렬 가정.
        """
        self._all_data = all_data
        self.current_date: str = ""

    def advance_to(self, date: str) -> None:
        """현재 날짜를 전진시킨다.

        이 날짜 이후 데이터는 접근 불가.

        Args:
            date: 새로운 현재 날짜 (YYYYMMDD).
        """
        self.current_date = date

    def get_ohlcv(self, code: str, start: str, end: str) -> list[OHLCV]:
        """OHLCV 데이터를 반환한다. 미래 데이터 요청 시 AssertionError.

        Args:
            code: 종목코드.
            start: 시작일 (YYYYMMDD, 포함).
            end: 종료일 (YYYYMMDD, 포함).

        Returns:
            해당 구간의 OHLCV 리스트.

        Raises:
            AssertionError: end > current_date인 경우.
        """
        assert end <= self.current_date, (
            f"Look-ahead bias! Requested {end} but current date is {self.current_date}"
        )
        bars = self._all_data.get(code, [])
        return [bar for bar in bars if start <= bar.date <= end]

    def get_latest_price(self, code: str) -> float:
        """현재 날짜의 종가를 반환한다.

        Args:
            code: 종목코드.

        Returns:
            종가. 데이터 없으면 0.0.
        """
        bar = self.get_bar(code)
        return bar.close if bar else 0.0

    def get_bar(self, code: str) -> OHLCV | None:
        """현재 날짜의 OHLCV 바를 반환한다.

        Args:
            code: 종목코드.

        Returns:
            OHLCV 또는 None.
        """
        bars = self._all_data.get(code, [])
        for bar in bars:
            if bar.date == self.current_date:
                return bar
        return None

    def get_available_codes(self) -> list[str]:
        """등록된 종목 코드 목록을 반환한다."""
        return list(self._all_data.keys())

    # --- DataProvider Protocol stub methods ---
    # HistoricalDataFeed는 백테스트 데이터 피드이므로 재무, 수급, 공매도 데이터를
    # 직접 제공하지 않는다. DataProvider Protocol 구조적 호환을 위해 빈 dict 반환.

    def get_financials(self, code: str) -> dict:
        """재무제표 (DataProvider stub — 백테스트에서는 미사용)."""
        return {}

    def get_investor_flow(self, code: str, days: int) -> dict:
        """투자자별 매매동향 (DataProvider stub — 백테스트에서는 미사용)."""
        return {}

    def get_short_interest(self, code: str, days: int) -> dict:
        """공매도 잔고 (DataProvider stub — 백테스트에서는 미사용)."""
        return {}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/trading/backtest/test_data_feed.py -v`
Expected: 11 passed

- [ ] **Step 6: Commit**

```bash
git add alphapulse/trading/backtest/ tests/trading/backtest/
git commit -m "feat(trading/backtest): add HistoricalDataFeed with look-ahead bias prevention"
```

---

## Task 2: SimBroker (가상 체결 엔진)

**Files:**
- Create: `alphapulse/trading/backtest/sim_broker.py`
- Test: `tests/trading/backtest/test_sim_broker.py`

- [ ] **Step 1: Write failing test**

`tests/trading/backtest/test_sim_broker.py`:
```python
"""SimBroker 테스트 — 가상 체결 엔진."""

import pytest

from alphapulse.trading.backtest.data_feed import HistoricalDataFeed
from alphapulse.trading.backtest.sim_broker import SimBroker
from alphapulse.trading.core.cost_model import CostModel
from alphapulse.trading.core.enums import OrderType, Side
from alphapulse.trading.core.models import OHLCV, Order, Stock


@pytest.fixture
def samsung():
    return Stock(code="005930", name="삼성전자", market="KOSPI")


@pytest.fixture
def kodex200():
    return Stock(code="069500", name="KODEX 200", market="ETF")


@pytest.fixture
def sample_feed():
    """5일치 데이터를 가진 HistoricalDataFeed."""
    data = {
        "005930": [
            OHLCV(date="20260406", open=72000, high=73000, low=71500, close=72500, volume=10_000_000),
            OHLCV(date="20260407", open=72500, high=74000, low=72000, close=73500, volume=12_000_000),
            OHLCV(date="20260408", open=73500, high=75000, low=73000, close=74000, volume=11_000_000),
        ],
        "069500": [
            OHLCV(date="20260406", open=35000, high=35500, low=34800, close=35200, volume=5_000_000),
            OHLCV(date="20260407", open=35200, high=36000, low=35000, close=35800, volume=6_000_000),
            OHLCV(date="20260408", open=35800, high=36200, low=35500, close=35900, volume=5_500_000),
        ],
    }
    feed = HistoricalDataFeed(data)
    return feed


@pytest.fixture
def broker(sample_feed):
    """기본 SimBroker (슬리피지 없음)."""
    cost_model = CostModel(slippage_model="none")
    return SimBroker(cost_model=cost_model, data_feed=sample_feed, initial_cash=100_000_000)


class TestSimBrokerInit:
    def test_initial_cash(self, broker):
        """초기 현금이 설정된다."""
        assert broker.cash == 100_000_000

    def test_initial_no_positions(self, broker):
        """초기 포지션은 비어있다."""
        assert broker.get_positions() == []

    def test_get_balance(self, broker):
        """잔고 조회."""
        balance = broker.get_balance()
        assert balance["cash"] == 100_000_000
        assert balance["total_value"] == 100_000_000
        assert balance["positions_value"] == 0


class TestMarketOrder:
    def test_buy_market_executes_at_close(self, broker, samsung, sample_feed):
        """MARKET 매수 — 당일 종가로 체결."""
        sample_feed.advance_to("20260406")
        order = Order(
            stock=samsung, side=Side.BUY, order_type=OrderType.MARKET,
            quantity=100, price=None, strategy_id="test",
        )
        result = broker.submit_order(order)
        assert result.status == "filled"
        assert result.filled_price == 72500  # 당일 종가
        assert result.filled_quantity == 100
        assert result.commission > 0

    def test_buy_reduces_cash(self, broker, samsung, sample_feed):
        """매수 후 현금이 감소한다."""
        sample_feed.advance_to("20260406")
        order = Order(
            stock=samsung, side=Side.BUY, order_type=OrderType.MARKET,
            quantity=100, price=None, strategy_id="test",
        )
        broker.submit_order(order)
        expected_cost = 100 * 72500  # 7,250,000
        assert broker.cash < 100_000_000
        assert broker.cash < 100_000_000 - expected_cost + 1  # 수수료까지

    def test_buy_creates_position(self, broker, samsung, sample_feed):
        """매수 후 포지션이 생성된다."""
        sample_feed.advance_to("20260406")
        order = Order(
            stock=samsung, side=Side.BUY, order_type=OrderType.MARKET,
            quantity=100, price=None, strategy_id="test",
        )
        broker.submit_order(order)
        positions = broker.get_positions()
        assert len(positions) == 1
        assert positions[0].stock.code == "005930"
        assert positions[0].quantity == 100

    def test_sell_market_executes_at_close(self, broker, samsung, sample_feed):
        """MARKET 매도 — 당일 종가로 체결."""
        sample_feed.advance_to("20260406")
        buy = Order(
            stock=samsung, side=Side.BUY, order_type=OrderType.MARKET,
            quantity=100, price=None, strategy_id="test",
        )
        broker.submit_order(buy)

        sample_feed.advance_to("20260407")
        sell = Order(
            stock=samsung, side=Side.SELL, order_type=OrderType.MARKET,
            quantity=100, price=None, strategy_id="test",
        )
        result = broker.submit_order(sell)
        assert result.status == "filled"
        assert result.filled_price == 73500  # 20260407 종가
        assert result.filled_quantity == 100

    def test_sell_removes_position(self, broker, samsung, sample_feed):
        """전량 매도 후 포지션이 제거된다."""
        sample_feed.advance_to("20260406")
        buy = Order(
            stock=samsung, side=Side.BUY, order_type=OrderType.MARKET,
            quantity=100, price=None, strategy_id="test",
        )
        broker.submit_order(buy)

        sample_feed.advance_to("20260407")
        sell = Order(
            stock=samsung, side=Side.SELL, order_type=OrderType.MARKET,
            quantity=100, price=None, strategy_id="test",
        )
        broker.submit_order(sell)
        assert broker.get_positions() == []

    def test_sell_tax_on_stock(self, broker, samsung, sample_feed):
        """주식 매도 시 세금이 부과된다."""
        sample_feed.advance_to("20260406")
        buy = Order(
            stock=samsung, side=Side.BUY, order_type=OrderType.MARKET,
            quantity=100, price=None, strategy_id="test",
        )
        broker.submit_order(buy)

        sample_feed.advance_to("20260407")
        sell = Order(
            stock=samsung, side=Side.SELL, order_type=OrderType.MARKET,
            quantity=100, price=None, strategy_id="test",
        )
        result = broker.submit_order(sell)
        assert result.tax > 0  # 주식 매도세 존재

    def test_sell_etf_no_tax(self, broker, kodex200, sample_feed):
        """ETF 매도 시 세금이 면제된다."""
        sample_feed.advance_to("20260406")
        buy = Order(
            stock=kodex200, side=Side.BUY, order_type=OrderType.MARKET,
            quantity=100, price=None, strategy_id="test",
        )
        broker.submit_order(buy)

        sample_feed.advance_to("20260407")
        sell = Order(
            stock=kodex200, side=Side.SELL, order_type=OrderType.MARKET,
            quantity=100, price=None, strategy_id="test",
        )
        result = broker.submit_order(sell)
        assert result.tax == 0


class TestLimitOrder:
    def test_buy_limit_filled_when_low_hits(self, broker, samsung, sample_feed):
        """매수 LIMIT — 저가 <= 지정가이면 체결."""
        sample_feed.advance_to("20260406")
        # 20260406 저가 71500, 지정가 72000 → 체결
        order = Order(
            stock=samsung, side=Side.BUY, order_type=OrderType.LIMIT,
            quantity=100, price=72000, strategy_id="test",
        )
        result = broker.submit_order(order)
        assert result.status == "filled"
        assert result.filled_price == 72000  # 지정가로 체결

    def test_buy_limit_rejected_when_low_above(self, broker, samsung, sample_feed):
        """매수 LIMIT — 저가 > 지정가이면 미체결."""
        sample_feed.advance_to("20260406")
        # 20260406 저가 71500, 지정가 71000 → 미체결
        order = Order(
            stock=samsung, side=Side.BUY, order_type=OrderType.LIMIT,
            quantity=100, price=71000, strategy_id="test",
        )
        result = broker.submit_order(order)
        assert result.status == "rejected"
        assert result.filled_quantity == 0

    def test_sell_limit_filled_when_high_hits(self, broker, samsung, sample_feed):
        """매도 LIMIT — 고가 >= 지정가이면 체결."""
        sample_feed.advance_to("20260406")
        buy = Order(
            stock=samsung, side=Side.BUY, order_type=OrderType.MARKET,
            quantity=100, price=None, strategy_id="test",
        )
        broker.submit_order(buy)
        # 20260406 고가 73000, 지정가 73000 → 체결
        sell = Order(
            stock=samsung, side=Side.SELL, order_type=OrderType.LIMIT,
            quantity=100, price=73000, strategy_id="test",
        )
        result = broker.submit_order(sell)
        assert result.status == "filled"
        assert result.filled_price == 73000

    def test_sell_limit_rejected_when_high_below(self, broker, samsung, sample_feed):
        """매도 LIMIT — 고가 < 지정가이면 미체결."""
        sample_feed.advance_to("20260406")
        buy = Order(
            stock=samsung, side=Side.BUY, order_type=OrderType.MARKET,
            quantity=100, price=None, strategy_id="test",
        )
        broker.submit_order(buy)
        # 20260406 고가 73000, 지정가 74000 → 미체결
        sell = Order(
            stock=samsung, side=Side.SELL, order_type=OrderType.LIMIT,
            quantity=100, price=74000, strategy_id="test",
        )
        result = broker.submit_order(sell)
        assert result.status == "rejected"
        assert result.filled_quantity == 0


class TestEdgeCases:
    def test_insufficient_cash_rejected(self, sample_feed):
        """현금 부족 시 매수 거부."""
        cost_model = CostModel(slippage_model="none")
        broker = SimBroker(cost_model=cost_model, data_feed=sample_feed, initial_cash=1_000_000)
        sample_feed.advance_to("20260406")
        order = Order(
            stock=Stock(code="005930", name="삼성전자", market="KOSPI"),
            side=Side.BUY, order_type=OrderType.MARKET,
            quantity=100, price=None, strategy_id="test",
        )
        result = broker.submit_order(order)
        # 72500 * 100 = 7,250,000 > 1,000,000
        assert result.status == "rejected"

    def test_sell_more_than_held_rejected(self, broker, samsung, sample_feed):
        """보유 수량 초과 매도 거부."""
        sample_feed.advance_to("20260406")
        buy = Order(
            stock=samsung, side=Side.BUY, order_type=OrderType.MARKET,
            quantity=100, price=None, strategy_id="test",
        )
        broker.submit_order(buy)
        sell = Order(
            stock=samsung, side=Side.SELL, order_type=OrderType.MARKET,
            quantity=200, price=None, strategy_id="test",
        )
        result = broker.submit_order(sell)
        assert result.status == "rejected"

    def test_sell_nonexistent_position_rejected(self, broker, samsung, sample_feed):
        """미보유 종목 매도 거부."""
        sample_feed.advance_to("20260406")
        sell = Order(
            stock=samsung, side=Side.SELL, order_type=OrderType.MARKET,
            quantity=100, price=None, strategy_id="test",
        )
        result = broker.submit_order(sell)
        assert result.status == "rejected"

    def test_no_bar_data_rejected(self, broker, sample_feed):
        """당일 데이터 없는 종목 주문 거부."""
        sample_feed.advance_to("20260406")
        unknown = Stock(code="999999", name="없는종목", market="KOSPI")
        order = Order(
            stock=unknown, side=Side.BUY, order_type=OrderType.MARKET,
            quantity=10, price=None, strategy_id="test",
        )
        result = broker.submit_order(order)
        assert result.status == "rejected"

    def test_multiple_buys_accumulate(self, broker, samsung, sample_feed):
        """동일 종목 복수 매수 시 포지션이 누적된다."""
        sample_feed.advance_to("20260406")
        for _ in range(3):
            order = Order(
                stock=samsung, side=Side.BUY, order_type=OrderType.MARKET,
                quantity=50, price=None, strategy_id="test",
            )
            broker.submit_order(order)
        positions = broker.get_positions()
        assert len(positions) == 1
        assert positions[0].quantity == 150

    def test_partial_sell(self, broker, samsung, sample_feed):
        """일부 매도 시 남은 수량이 유지된다."""
        sample_feed.advance_to("20260406")
        buy = Order(
            stock=samsung, side=Side.BUY, order_type=OrderType.MARKET,
            quantity=100, price=None, strategy_id="test",
        )
        broker.submit_order(buy)
        sell = Order(
            stock=samsung, side=Side.SELL, order_type=OrderType.MARKET,
            quantity=30, price=None, strategy_id="test",
        )
        broker.submit_order(sell)
        positions = broker.get_positions()
        assert positions[0].quantity == 70

    def test_trade_log(self, broker, samsung, sample_feed):
        """체결 이력이 기록된다."""
        sample_feed.advance_to("20260406")
        order = Order(
            stock=samsung, side=Side.BUY, order_type=OrderType.MARKET,
            quantity=100, price=None, strategy_id="test",
        )
        broker.submit_order(order)
        assert len(broker.trade_log) == 1
        assert broker.trade_log[0].order.stock.code == "005930"


class TestSlippage:
    def test_slippage_applied_to_buy(self, sample_feed, samsung):
        """매수 시 슬리피지가 가격에 가산된다."""
        cost_model = CostModel(slippage_model="fixed")
        broker = SimBroker(cost_model=cost_model, data_feed=sample_feed, initial_cash=100_000_000)
        sample_feed.advance_to("20260406")
        order = Order(
            stock=samsung, side=Side.BUY, order_type=OrderType.MARKET,
            quantity=100, price=None, strategy_id="test",
        )
        result = broker.submit_order(order)
        # fixed 슬리피지: 종가 * (1 + slippage) → 72500보다 높아야
        assert result.filled_price >= 72500


class TestProtocolConformance:
    def test_implements_broker_protocol(self, broker):
        """SimBroker가 Broker Protocol을 구현한다."""
        from alphapulse.trading.core.interfaces import Broker

        assert isinstance(broker, Broker)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/trading/backtest/test_sim_broker.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement SimBroker**

`alphapulse/trading/backtest/sim_broker.py`:
```python
"""시뮬레이션 브로커 — 가상 체결 엔진.

Broker Protocol을 구현하여 백테스트에서 사용한다.
MARKET 주문은 당일 종가, LIMIT 주문은 고가/저가 범위로 체결 여부를 결정한다.
"""

import uuid
from datetime import datetime

from alphapulse.trading.backtest.data_feed import HistoricalDataFeed
from alphapulse.trading.core.cost_model import CostModel
from alphapulse.trading.core.enums import OrderType, Side
from alphapulse.trading.core.models import Order, OrderResult, Position, Stock


class SimBroker:
    """가상 체결 브로커.

    내부에 현금과 포지션 상태를 관리하며, 데이터 피드에서 가격을 가져와 체결한다.
    CostModel을 통해 수수료, 세금, 슬리피지를 반영한다.

    Attributes:
        cash: 보유 현금 (원).
        trade_log: 체결 이력 (OrderResult 리스트).
    """

    def __init__(self, cost_model: CostModel, data_feed: HistoricalDataFeed,
                 initial_cash: float) -> None:
        """초기화.

        Args:
            cost_model: 거래 비용 모델.
            data_feed: 히스토리 데이터 피드.
            initial_cash: 초기 투자금 (원).
        """
        self.cost_model = cost_model
        self.data_feed = data_feed
        self.cash: float = initial_cash
        self._positions: dict[str, dict] = {}  # code → {stock, quantity, avg_price, strategy_id}
        self.trade_log: list[OrderResult] = []

    def submit_order(self, order: Order) -> OrderResult:
        """주문을 체결한다.

        MARKET: 당일 종가로 체결 (보수적 가정).
        LIMIT 매수: 저가 <= 지정가이면 지정가로 체결.
        LIMIT 매도: 고가 >= 지정가이면 지정가로 체결.

        Args:
            order: 매매 주문.

        Returns:
            체결 결과.
        """
        bar = self.data_feed.get_bar(order.stock.code)
        if bar is None:
            return self._rejected(order, "당일 데이터 없음")

        if order.side == Side.BUY:
            return self._execute_buy(order, bar)
        else:
            return self._execute_sell(order, bar)

    def cancel_order(self, order_id: str) -> bool:
        """주문 취소 (SimBroker는 즉시 체결이므로 항상 False)."""
        return False

    def get_balance(self) -> dict:
        """잔고 정보를 반환한다."""
        positions_value = sum(
            p["quantity"] * self.data_feed.get_latest_price(code)
            for code, p in self._positions.items()
        )
        return {
            "cash": self.cash,
            "positions_value": positions_value,
            "total_value": self.cash + positions_value,
        }

    def get_positions(self) -> list[Position]:
        """보유 포지션 목록을 반환한다."""
        result = []
        for code, p in self._positions.items():
            current_price = self.data_feed.get_latest_price(code)
            pnl = (current_price - p["avg_price"]) * p["quantity"]
            total = self.get_balance()["total_value"]
            weight = (p["quantity"] * current_price) / total if total > 0 else 0.0
            result.append(Position(
                stock=p["stock"],
                quantity=p["quantity"],
                avg_price=p["avg_price"],
                current_price=current_price,
                unrealized_pnl=pnl,
                weight=weight,
                strategy_id=p["strategy_id"],
            ))
        return result

    def get_order_status(self, order_id: str) -> OrderResult:
        """주문 상태를 조회한다."""
        for trade in self.trade_log:
            if trade.order_id == order_id:
                return trade
        return self._rejected(
            Order(stock=Stock(code="", name="", market=""),
                  side=Side.BUY, order_type=OrderType.MARKET,
                  quantity=0, price=None, strategy_id=""),
            "주문 없음",
        )

    def _execute_buy(self, order: Order, bar) -> OrderResult:
        """매수 체결 로직."""
        fill_price = self._determine_fill_price(order, bar)
        if fill_price is None:
            return self._rejected(order, "LIMIT 미체결 (저가 > 지정가)")

        slippage_pct = self.cost_model.estimate_slippage(order, bar.volume)
        adjusted_price = fill_price * (1 + slippage_pct)

        total_amount = order.quantity * adjusted_price
        commission = self.cost_model.calculate_commission(total_amount)
        total_cost = total_amount + commission

        if total_cost > self.cash:
            return self._rejected(order, "현금 부족")

        self.cash -= total_cost
        self._update_position_buy(order, adjusted_price)

        result = OrderResult(
            order_id=str(uuid.uuid4()),
            order=order,
            status="filled",
            filled_quantity=order.quantity,
            filled_price=adjusted_price,
            commission=commission,
            tax=0.0,
            filled_at=datetime.now(),
        )
        self.trade_log.append(result)
        return result

    def _execute_sell(self, order: Order, bar) -> OrderResult:
        """매도 체결 로직."""
        pos = self._positions.get(order.stock.code)
        if pos is None or pos["quantity"] < order.quantity:
            return self._rejected(order, "보유 수량 부족")

        fill_price = self._determine_fill_price(order, bar)
        if fill_price is None:
            return self._rejected(order, "LIMIT 미체결 (고가 < 지정가)")

        slippage_pct = self.cost_model.estimate_slippage(order, bar.volume)
        adjusted_price = fill_price * (1 - slippage_pct)

        total_amount = order.quantity * adjusted_price
        is_etf = order.stock.market == "ETF"
        commission = self.cost_model.calculate_commission(total_amount)
        tax = self.cost_model.calculate_tax(total_amount, is_etf=is_etf)

        self.cash += total_amount - commission - tax
        self._update_position_sell(order)

        result = OrderResult(
            order_id=str(uuid.uuid4()),
            order=order,
            status="filled",
            filled_quantity=order.quantity,
            filled_price=adjusted_price,
            commission=commission,
            tax=tax,
            filled_at=datetime.now(),
        )
        self.trade_log.append(result)
        return result

    def _determine_fill_price(self, order: Order, bar) -> float | None:
        """체결가를 결정한다.

        MARKET: 종가.
        LIMIT 매수: 저가 <= 지정가이면 지정가, 아니면 None.
        LIMIT 매도: 고가 >= 지정가이면 지정가, 아니면 None.
        """
        if order.order_type == OrderType.MARKET:
            return bar.close

        if order.side == Side.BUY:
            if bar.low <= order.price:
                return order.price
            return None
        else:
            if bar.high >= order.price:
                return order.price
            return None

    def _update_position_buy(self, order: Order, fill_price: float) -> None:
        """매수로 포지션을 갱신한다."""
        code = order.stock.code
        if code in self._positions:
            pos = self._positions[code]
            total_qty = pos["quantity"] + order.quantity
            pos["avg_price"] = (
                (pos["avg_price"] * pos["quantity"] + fill_price * order.quantity)
                / total_qty
            )
            pos["quantity"] = total_qty
        else:
            self._positions[code] = {
                "stock": order.stock,
                "quantity": order.quantity,
                "avg_price": fill_price,
                "strategy_id": order.strategy_id,
            }

    def _update_position_sell(self, order: Order) -> None:
        """매도로 포지션을 갱신한다."""
        code = order.stock.code
        pos = self._positions[code]
        pos["quantity"] -= order.quantity
        if pos["quantity"] == 0:
            del self._positions[code]

    @staticmethod
    def _rejected(order: Order, reason: str) -> OrderResult:
        """거부 결과를 생성한다."""
        return OrderResult(
            order_id=str(uuid.uuid4()),
            order=order,
            status="rejected",
            filled_quantity=0,
            filled_price=0.0,
            commission=0.0,
            tax=0.0,
            filled_at=None,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/trading/backtest/test_sim_broker.py -v`
Expected: 23 passed

- [ ] **Step 5: Commit**

```bash
git add alphapulse/trading/backtest/sim_broker.py tests/trading/backtest/test_sim_broker.py
git commit -m "feat(trading/backtest): add SimBroker virtual execution engine"
```

---

## Task 3: BacktestMetrics (성과 지표 계산)

**Files:**
- Create: `alphapulse/trading/backtest/metrics.py`
- Test: `tests/trading/backtest/test_metrics.py`

- [ ] **Step 1: Write failing test**

`tests/trading/backtest/test_metrics.py`:
```python
"""BacktestMetrics 테스트 — 성과 지표 계산."""

import numpy as np
import pytest

from alphapulse.trading.backtest.metrics import BacktestMetrics
from alphapulse.trading.core.models import OrderResult, PortfolioSnapshot


@pytest.fixture
def metrics():
    return BacktestMetrics()


@pytest.fixture
def sample_snapshots():
    """20일치 스냅샷 — 초기 1억, 약간의 변동."""
    dates = [f"202604{d:02d}" for d in range(6, 30) if d not in (11, 12, 18, 19, 25, 26)]
    # 약 16 영업일
    values = [
        100_000_000,  # day 1
        100_500_000,  # +0.5%
        101_200_000,  # +0.7%
        100_800_000,  # -0.4%
        101_500_000,  # +0.7%
        102_000_000,  # +0.5%
        101_000_000,  # -1.0%
        100_000_000,  # -1.0%
        99_000_000,   # -1.0% (최대 낙폭 구간)
        100_200_000,  # +1.2%
        101_000_000,  # +0.8%
        102_500_000,  # +1.5%
        103_000_000,  # +0.5%
        103_500_000,  # +0.5%
        104_000_000,  # +0.5%
        104_500_000,  # +0.5%
    ]
    snapshots = []
    peak = values[0]
    for i, (date, value) in enumerate(zip(dates[:len(values)], values)):
        peak = max(peak, value)
        daily_ret = 0.0 if i == 0 else (value - values[i - 1]) / values[i - 1] * 100
        cum_ret = (value - values[0]) / values[0] * 100
        dd = (peak - value) / peak * 100
        snapshots.append(PortfolioSnapshot(
            date=date, cash=value * 0.1, positions=[],
            total_value=value, daily_return=daily_ret,
            cumulative_return=cum_ret, drawdown=-dd,
        ))
    return snapshots


@pytest.fixture
def benchmark_returns():
    """벤치마크 일간 수익률 (KOSPI)."""
    return np.array([
        0.003, 0.005, -0.002, 0.004, 0.003,
        -0.008, -0.005, -0.007, 0.010, 0.006,
        0.012, 0.004, 0.003, 0.002, 0.001,
    ])


@pytest.fixture
def sample_trades():
    """체결 이력 — 승패 혼합."""
    from alphapulse.trading.core.models import Order, Stock

    stock = Stock(code="005930", name="삼성전자", market="KOSPI")
    trades = []
    # 승리 거래 3건 (매수→매도 쌍으로 가정, 여기서는 매도 체결만)
    for price_pair in [(72000, 74000), (73000, 75000), (71000, 73500)]:
        buy_order = Order(stock=stock, side="BUY", order_type="MARKET",
                          quantity=100, price=None, strategy_id="test")
        sell_order = Order(stock=stock, side="SELL", order_type="MARKET",
                           quantity=100, price=None, strategy_id="test")
        trades.append(OrderResult(
            order_id="b1", order=buy_order, status="filled",
            filled_quantity=100, filled_price=price_pair[0],
            commission=108, tax=0, filled_at=None,
        ))
        trades.append(OrderResult(
            order_id="s1", order=sell_order, status="filled",
            filled_quantity=100, filled_price=price_pair[1],
            commission=111, tax=1332, filled_at=None,
        ))
    # 패배 거래 2건
    for price_pair in [(74000, 72000), (75000, 73000)]:
        buy_order = Order(stock=stock, side="BUY", order_type="MARKET",
                          quantity=100, price=None, strategy_id="test")
        sell_order = Order(stock=stock, side="SELL", order_type="MARKET",
                           quantity=100, price=None, strategy_id="test")
        trades.append(OrderResult(
            order_id="b2", order=buy_order, status="filled",
            filled_quantity=100, filled_price=price_pair[0],
            commission=111, tax=0, filled_at=None,
        ))
        trades.append(OrderResult(
            order_id="s2", order=sell_order, status="filled",
            filled_quantity=100, filled_price=price_pair[1],
            commission=108, tax=1296, filled_at=None,
        ))
    return trades


class TestReturnMetrics:
    def test_total_return(self, metrics, sample_snapshots):
        """총 수익률이 올바르게 계산된다."""
        result = metrics.calculate(sample_snapshots, np.array([0.003] * 15))
        assert result["total_return"] == pytest.approx(4.5, abs=0.1)

    def test_cagr(self, metrics, sample_snapshots):
        """CAGR이 양수이다."""
        result = metrics.calculate(sample_snapshots, np.array([0.003] * 15))
        assert result["cagr"] > 0


class TestMonthlyReturns:
    def test_monthly_returns_is_list(self, metrics, sample_snapshots):
        """monthly_returns가 리스트로 반환된다."""
        result = metrics.calculate(sample_snapshots, np.array([0.003] * 15))
        assert "monthly_returns" in result
        assert isinstance(result["monthly_returns"], list)

    def test_monthly_returns_empty_on_single_snapshot(self, metrics):
        """스냅샷 1개 → monthly_returns 빈 리스트."""
        snap = PortfolioSnapshot(
            date="20260406", cash=100_000_000, positions=[],
            total_value=100_000_000, daily_return=0.0,
            cumulative_return=0.0, drawdown=0.0,
        )
        result = metrics.calculate([snap], np.array([0.0]))
        assert result["monthly_returns"] == []


class TestRiskMetrics:
    def test_max_drawdown(self, metrics, sample_snapshots):
        """최대 낙폭(MDD)이 계산된다."""
        result = metrics.calculate(sample_snapshots, np.array([0.003] * 15))
        assert result["max_drawdown"] < 0

    def test_max_drawdown_duration(self, metrics, sample_snapshots):
        """MDD 지속 기간이 양수이다."""
        result = metrics.calculate(sample_snapshots, np.array([0.003] * 15))
        assert result["max_drawdown_duration"] >= 1

    def test_volatility(self, metrics, sample_snapshots):
        """변동성이 양수이다."""
        result = metrics.calculate(sample_snapshots, np.array([0.003] * 15))
        assert result["volatility"] > 0


class TestRiskAdjusted:
    def test_sharpe_ratio(self, metrics, sample_snapshots, benchmark_returns):
        """샤프 비율이 계산된다."""
        result = metrics.calculate(sample_snapshots, benchmark_returns)
        assert "sharpe_ratio" in result
        assert isinstance(result["sharpe_ratio"], float)

    def test_sortino_ratio(self, metrics, sample_snapshots, benchmark_returns):
        """소르티노 비율이 계산된다."""
        result = metrics.calculate(sample_snapshots, benchmark_returns)
        assert "sortino_ratio" in result

    def test_calmar_ratio(self, metrics, sample_snapshots, benchmark_returns):
        """칼마 비율이 계산된다."""
        result = metrics.calculate(sample_snapshots, benchmark_returns)
        assert "calmar_ratio" in result


class TestTradeMetrics:
    def test_win_rate(self, metrics, sample_snapshots, benchmark_returns, sample_trades):
        """승률이 올바르게 계산된다."""
        result = metrics.calculate(
            sample_snapshots, benchmark_returns, trades=sample_trades,
        )
        # 3승 2패 → 60%
        assert result["win_rate"] == pytest.approx(60.0, abs=1.0)

    def test_profit_factor(self, metrics, sample_snapshots, benchmark_returns, sample_trades):
        """이익 팩터가 1 이상이다 (순이익)."""
        result = metrics.calculate(
            sample_snapshots, benchmark_returns, trades=sample_trades,
        )
        assert result["profit_factor"] > 1.0

    def test_total_trades(self, metrics, sample_snapshots, benchmark_returns, sample_trades):
        """총 거래 횟수가 올바르다."""
        result = metrics.calculate(
            sample_snapshots, benchmark_returns, trades=sample_trades,
        )
        # 매수+매도 쌍 = 5 라운드트립
        assert result["total_trades"] == 5


class TestBenchmarkMetrics:
    def test_benchmark_return(self, metrics, sample_snapshots, benchmark_returns):
        """벤치마크 수익률이 계산된다."""
        result = metrics.calculate(sample_snapshots, benchmark_returns)
        assert "benchmark_return" in result

    def test_alpha(self, metrics, sample_snapshots, benchmark_returns):
        """알파가 계산된다."""
        result = metrics.calculate(sample_snapshots, benchmark_returns)
        assert "alpha" in result

    def test_beta(self, metrics, sample_snapshots, benchmark_returns):
        """베타가 계산된다."""
        result = metrics.calculate(sample_snapshots, benchmark_returns)
        assert "beta" in result

    def test_information_ratio(self, metrics, sample_snapshots, benchmark_returns):
        """정보 비율이 계산된다."""
        result = metrics.calculate(sample_snapshots, benchmark_returns)
        assert "information_ratio" in result

    def test_tracking_error(self, metrics, sample_snapshots, benchmark_returns):
        """추적 오차가 계산된다."""
        result = metrics.calculate(sample_snapshots, benchmark_returns)
        assert "tracking_error" in result
        assert result["tracking_error"] >= 0


class TestEdgeCases:
    def test_single_snapshot(self, metrics):
        """스냅샷 1개 → 최소 결과 반환."""
        snap = PortfolioSnapshot(
            date="20260406", cash=100_000_000, positions=[],
            total_value=100_000_000, daily_return=0.0,
            cumulative_return=0.0, drawdown=0.0,
        )
        result = metrics.calculate([snap], np.array([0.0]))
        assert result["total_return"] == 0.0
        assert result["sharpe_ratio"] == 0.0

    def test_empty_trades(self, metrics, sample_snapshots, benchmark_returns):
        """거래 없음 → 승률 0, profit_factor 0."""
        result = metrics.calculate(sample_snapshots, benchmark_returns, trades=[])
        assert result["win_rate"] == 0.0
        assert result["profit_factor"] == 0.0
        assert result["total_trades"] == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/trading/backtest/test_metrics.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement BacktestMetrics**

`alphapulse/trading/backtest/metrics.py`:
```python
"""백테스트 성과 지표 계산.

수익률, 리스크, 거래 분석, 벤치마크 비교 지표를 모두 계산한다.
"""

import numpy as np

from alphapulse.trading.core.models import OrderResult, PortfolioSnapshot


class BacktestMetrics:
    """백테스트 결과 분석.

    스냅샷 목록, 벤치마크 수익률, 체결 이력을 입력받아
    포괄적 성과 지표를 계산한다.
    """

    def calculate(
        self,
        snapshots: list[PortfolioSnapshot],
        benchmark_returns: np.ndarray,
        risk_free_rate: float = 0.035,
        trades: list[OrderResult] | None = None,
    ) -> dict:
        """성과 지표를 계산한다.

        Args:
            snapshots: 일별 포트폴리오 스냅샷 목록.
            benchmark_returns: 벤치마크 일간 수익률 배열.
            risk_free_rate: 무위험 이자율 (연율, 기본 3.5%).
            trades: 체결 이력 (없으면 거래 지표 0).

        Returns:
            모든 성과 지표를 담은 딕셔너리.
        """
        if len(snapshots) <= 1:
            return self._empty_metrics()

        values = np.array([s.total_value for s in snapshots])
        dates = [s.date for s in snapshots]
        daily_returns = np.diff(values) / values[:-1]
        n_days = len(daily_returns)
        annualization = 252

        # 월별 수익률 — 일간 수익률을 월 단위로 복리 계산
        monthly_returns = self._calculate_monthly_returns(dates, daily_returns)

        # 수익률
        total_return = (values[-1] - values[0]) / values[0] * 100
        years = n_days / annualization
        cagr = ((values[-1] / values[0]) ** (1 / years) - 1) * 100 if years > 0 else 0.0

        # 리스크
        volatility = float(np.std(daily_returns, ddof=1) * np.sqrt(annualization) * 100)
        mdd, mdd_duration = self._max_drawdown(values)
        downside_returns = daily_returns[daily_returns < 0]
        downside_dev = float(np.std(downside_returns, ddof=1) * np.sqrt(annualization) * 100) if len(downside_returns) > 1 else 0.0

        # 리스크 조정 수익
        daily_rf = risk_free_rate / annualization
        excess_daily = daily_returns - daily_rf
        sharpe = float(np.mean(excess_daily) / np.std(excess_daily, ddof=1) * np.sqrt(annualization)) if np.std(excess_daily, ddof=1) > 0 else 0.0
        sortino = float(np.mean(excess_daily) / (np.std(downside_returns, ddof=1)) * np.sqrt(annualization)) if len(downside_returns) > 1 and np.std(downside_returns, ddof=1) > 0 else 0.0
        calmar = cagr / abs(mdd) if mdd != 0 else 0.0

        # 거래 분석
        trade_metrics = self._calculate_trade_metrics(trades or [], values[0])

        # 벤치마크 비교
        bench_metrics = self._calculate_benchmark_metrics(
            daily_returns, benchmark_returns[:n_days], risk_free_rate, annualization,
        )

        return {
            "total_return": round(total_return, 4),
            "cagr": round(cagr, 4),
            "monthly_returns": monthly_returns,
            "volatility": round(volatility, 4),
            "max_drawdown": round(mdd, 4),
            "max_drawdown_duration": mdd_duration,
            "downside_deviation": round(downside_dev, 4),
            "sharpe_ratio": round(sharpe, 4),
            "sortino_ratio": round(sortino, 4),
            "calmar_ratio": round(calmar, 4),
            **trade_metrics,
            **bench_metrics,
        }

    def _max_drawdown(self, values: np.ndarray) -> tuple[float, int]:
        """최대 낙폭(MDD)과 지속 기간을 계산한다.

        Returns:
            (MDD 비율 (음수, %), 지속 기간 (영업일)).
        """
        peak = values[0]
        max_dd = 0.0
        dd_start = 0
        max_duration = 0
        current_duration = 0

        for i in range(len(values)):
            if values[i] > peak:
                peak = values[i]
                current_duration = 0
            else:
                dd = (peak - values[i]) / peak
                current_duration += 1
                if dd > max_dd:
                    max_dd = dd
                    max_duration = current_duration

        return -round(max_dd * 100, 4), max(max_duration, 0)

    @staticmethod
    def _calculate_monthly_returns(
        dates: list[str], daily_returns: np.ndarray,
    ) -> list[float]:
        """일간 수익률을 월별로 그룹화하여 복리 수익률을 계산한다.

        Args:
            dates: 스냅샷 날짜 리스트 (YYYYMMDD). daily_returns보다 1개 더 많음.
            daily_returns: 일간 수익률 배열.

        Returns:
            월별 복리 수익률 리스트 (%).
        """
        if len(daily_returns) == 0:
            return []

        # 월(YYYYMM) 기준으로 일간 수익률 그룹화 (dates[1:]과 daily_returns 대응)
        monthly: dict[str, list[float]] = {}
        for i, ret in enumerate(daily_returns):
            month_key = dates[i + 1][:6]  # YYYYMM
            monthly.setdefault(month_key, []).append(float(ret))

        # 월별 복리 수익률
        result = []
        for month_key in sorted(monthly.keys()):
            compound = float(np.prod([1 + r for r in monthly[month_key]]) - 1) * 100
            result.append(round(compound, 4))

        return result

    def _calculate_trade_metrics(self, trades: list[OrderResult],
                                  initial_capital: float) -> dict:
        """거래 분석 지표를 계산한다.

        매수-매도 쌍으로 라운드트립을 구성하여 승패를 판단한다.
        """
        if not trades:
            return {
                "total_trades": 0,
                "win_rate": 0.0,
                "profit_factor": 0.0,
                "avg_win": 0.0,
                "avg_loss": 0.0,
                "turnover": 0.0,
            }

        # 종목별 매수→매도 쌍으로 라운드트립 추출
        buys: dict[str, list[OrderResult]] = {}
        round_trips: list[float] = []
        total_traded_amount = 0.0

        for trade in trades:
            if trade.status != "filled":
                continue
            code = trade.order.stock.code
            total_traded_amount += trade.filled_quantity * trade.filled_price

            if trade.order.side == "BUY":
                buys.setdefault(code, []).append(trade)
            else:  # SELL
                if code in buys and buys[code]:
                    buy_trade = buys[code].pop(0)
                    pnl = (trade.filled_price - buy_trade.filled_price) * trade.filled_quantity
                    pnl -= (trade.commission + trade.tax + buy_trade.commission)
                    round_trips.append(pnl)

        total_trades = len(round_trips)
        if total_trades == 0:
            return {
                "total_trades": 0,
                "win_rate": 0.0,
                "profit_factor": 0.0,
                "avg_win": 0.0,
                "avg_loss": 0.0,
                "turnover": 0.0,
            }

        wins = [pnl for pnl in round_trips if pnl > 0]
        losses = [pnl for pnl in round_trips if pnl <= 0]

        win_rate = len(wins) / total_trades * 100
        total_profit = sum(wins) if wins else 0.0
        total_loss = abs(sum(losses)) if losses else 0.0
        profit_factor = total_profit / total_loss if total_loss > 0 else 0.0

        avg_win = (total_profit / len(wins)) if wins else 0.0
        avg_loss = (total_loss / len(losses)) if losses else 0.0

        turnover = total_traded_amount / initial_capital if initial_capital > 0 else 0.0

        return {
            "total_trades": total_trades,
            "win_rate": round(win_rate, 2),
            "profit_factor": round(profit_factor, 4),
            "avg_win": round(avg_win, 2),
            "avg_loss": round(avg_loss, 2),
            "turnover": round(turnover, 4),
        }

    def _calculate_benchmark_metrics(
        self,
        portfolio_returns: np.ndarray,
        benchmark_returns: np.ndarray,
        risk_free_rate: float,
        annualization: int,
    ) -> dict:
        """벤치마크 비교 지표를 계산한다."""
        n = min(len(portfolio_returns), len(benchmark_returns))
        if n < 2:
            return {
                "benchmark_return": 0.0,
                "excess_return": 0.0,
                "beta": 0.0,
                "alpha": 0.0,
                "information_ratio": 0.0,
                "tracking_error": 0.0,
            }

        pr = portfolio_returns[:n]
        br = benchmark_returns[:n]

        benchmark_total = float(np.prod(1 + br) - 1) * 100
        portfolio_total = float(np.prod(1 + pr) - 1) * 100
        excess = portfolio_total - benchmark_total

        # 베타 = Cov(Rp, Rb) / Var(Rb)
        cov_matrix = np.cov(pr, br)
        beta = float(cov_matrix[0, 1] / cov_matrix[1, 1]) if cov_matrix[1, 1] > 0 else 0.0

        # 알파 (젠센 알파) = Rp - [Rf + beta * (Rb - Rf)]
        daily_rf = risk_free_rate / annualization
        alpha = float(np.mean(pr) - (daily_rf + beta * (np.mean(br) - daily_rf))) * annualization * 100

        # 추적 오차
        active_returns = pr - br
        tracking_error = float(np.std(active_returns, ddof=1) * np.sqrt(annualization) * 100)

        # 정보 비율
        information_ratio = float(np.mean(active_returns) / np.std(active_returns, ddof=1) * np.sqrt(annualization)) if np.std(active_returns, ddof=1) > 0 else 0.0

        return {
            "benchmark_return": round(benchmark_total, 4),
            "excess_return": round(excess, 4),
            "beta": round(beta, 4),
            "alpha": round(alpha, 4),
            "information_ratio": round(information_ratio, 4),
            "tracking_error": round(tracking_error, 4),
        }

    @staticmethod
    def _empty_metrics() -> dict:
        """스냅샷 부족 시 빈 지표를 반환한다."""
        return {
            "total_return": 0.0,
            "cagr": 0.0,
            "monthly_returns": [],
            "volatility": 0.0,
            "max_drawdown": 0.0,
            "max_drawdown_duration": 0,
            "downside_deviation": 0.0,
            "sharpe_ratio": 0.0,
            "sortino_ratio": 0.0,
            "calmar_ratio": 0.0,
            "total_trades": 0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "avg_win": 0.0,
            "avg_loss": 0.0,
            "turnover": 0.0,
            "benchmark_return": 0.0,
            "excess_return": 0.0,
            "beta": 0.0,
            "alpha": 0.0,
            "information_ratio": 0.0,
            "tracking_error": 0.0,
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/trading/backtest/test_metrics.py -v`
Expected: 19 passed

- [ ] **Step 5: Commit**

```bash
git add alphapulse/trading/backtest/metrics.py tests/trading/backtest/test_metrics.py
git commit -m "feat(trading/backtest): add BacktestMetrics performance calculation"
```

---

## Task 4: BacktestEngine (메인 루프)

**Files:**
- Create: `alphapulse/trading/backtest/engine.py`
- Test: `tests/trading/backtest/test_engine.py`

- [ ] **Step 1: Write failing test**

`tests/trading/backtest/test_engine.py`:
```python
"""BacktestEngine 테스트 — 메인 시뮬레이션 루프."""

from dataclasses import dataclass, field
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from alphapulse.trading.backtest.data_feed import HistoricalDataFeed
from alphapulse.trading.backtest.engine import BacktestConfig, BacktestEngine, BacktestResult
from alphapulse.trading.core.cost_model import CostModel
from alphapulse.trading.core.enums import Side
from alphapulse.trading.core.models import OHLCV, Order, PortfolioSnapshot, Signal, Stock


@pytest.fixture
def samsung():
    return Stock(code="005930", name="삼성전자", market="KOSPI")


@pytest.fixture
def sample_data(samsung):
    """5 거래일 데이터."""
    return {
        "005930": [
            OHLCV(date="20260406", open=72000, high=73000, low=71500, close=72500, volume=10_000_000),
            OHLCV(date="20260407", open=72500, high=74000, low=72000, close=73500, volume=12_000_000),
            OHLCV(date="20260408", open=73500, high=75000, low=73000, close=74000, volume=11_000_000),
            OHLCV(date="20260409", open=74000, high=74500, low=72500, close=73000, volume=9_000_000),
            OHLCV(date="20260410", open=73000, high=73500, low=71000, close=71500, volume=15_000_000),
        ],
    }


@pytest.fixture
def mock_strategy(samsung):
    """매일 삼성전자 매수 시그널을 생성하는 모의 전략."""
    strategy = MagicMock()
    strategy.strategy_id = "test_strategy"
    strategy.generate_signals.return_value = [
        Signal(stock=samsung, score=80.0, factors={"momentum": 0.8},
               strategy_id="test_strategy"),
    ]
    strategy.should_rebalance.return_value = True
    return strategy


@pytest.fixture
def benchmark_data():
    """KOSPI 벤치마크 데이터."""
    return {
        "KOSPI": [
            OHLCV(date="20260406", open=2700, high=2720, low=2690, close=2710, volume=500_000_000),
            OHLCV(date="20260407", open=2710, high=2740, low=2700, close=2730, volume=480_000_000),
            OHLCV(date="20260408", open=2730, high=2750, low=2720, close=2740, volume=510_000_000),
            OHLCV(date="20260409", open=2740, high=2745, low=2710, close=2720, volume=490_000_000),
            OHLCV(date="20260410", open=2720, high=2725, low=2680, close=2690, volume=520_000_000),
        ],
    }


class TestBacktestConfig:
    def test_creation(self):
        """설정 객체 생성."""
        config = BacktestConfig(
            initial_capital=100_000_000,
            start_date="20260406",
            end_date="20260410",
            cost_model=CostModel(slippage_model="none"),
            benchmark="KOSPI",
        )
        assert config.initial_capital == 100_000_000
        assert config.benchmark == "KOSPI"


class TestBacktestResult:
    def test_creation(self):
        """결과 객체 생성."""
        result = BacktestResult(
            snapshots=[], trades=[], metrics={},
            config=BacktestConfig(
                initial_capital=100_000_000,
                start_date="20260406",
                end_date="20260410",
                cost_model=CostModel(),
            ),
        )
        assert result.snapshots == []


class TestBacktestEngine:
    @patch("alphapulse.trading.backtest.engine.KRXCalendar")
    def test_run_returns_result(self, mock_cal_cls, sample_data, mock_strategy, benchmark_data):
        """run()이 BacktestResult를 반환한다."""
        mock_cal = mock_cal_cls.return_value
        mock_cal.trading_days_between.return_value = [
            "20260406", "20260407", "20260408", "20260409", "20260410",
        ]

        all_data = {**sample_data, **benchmark_data}
        config = BacktestConfig(
            initial_capital=100_000_000,
            start_date="20260406",
            end_date="20260410",
            cost_model=CostModel(slippage_model="none"),
            benchmark="KOSPI",
        )
        engine = BacktestEngine(
            config=config,
            data_feed=HistoricalDataFeed(all_data),
            strategies=[mock_strategy],
            order_generator=self._simple_order_generator,
        )
        result = engine.run()
        assert isinstance(result, BacktestResult)
        assert len(result.snapshots) == 5
        assert isinstance(result.metrics, dict)

    @patch("alphapulse.trading.backtest.engine.KRXCalendar")
    def test_snapshots_have_correct_dates(self, mock_cal_cls, sample_data, mock_strategy, benchmark_data):
        """스냅샷 날짜가 거래일과 일치한다."""
        trading_days = ["20260406", "20260407", "20260408", "20260409", "20260410"]
        mock_cal = mock_cal_cls.return_value
        mock_cal.trading_days_between.return_value = trading_days

        all_data = {**sample_data, **benchmark_data}
        config = BacktestConfig(
            initial_capital=100_000_000,
            start_date="20260406",
            end_date="20260410",
            cost_model=CostModel(slippage_model="none"),
            benchmark="KOSPI",
        )
        engine = BacktestEngine(
            config=config,
            data_feed=HistoricalDataFeed(all_data),
            strategies=[mock_strategy],
            order_generator=self._simple_order_generator,
        )
        result = engine.run()
        dates = [s.date for s in result.snapshots]
        assert dates == trading_days

    @patch("alphapulse.trading.backtest.engine.KRXCalendar")
    def test_initial_value_preserved(self, mock_cal_cls, sample_data, benchmark_data):
        """전략이 주문 없으면 초기 자본이 유지된다."""
        mock_cal = mock_cal_cls.return_value
        mock_cal.trading_days_between.return_value = [
            "20260406", "20260407", "20260408",
        ]

        no_signal_strategy = MagicMock()
        no_signal_strategy.strategy_id = "empty"
        no_signal_strategy.generate_signals.return_value = []
        no_signal_strategy.should_rebalance.return_value = True

        all_data = {**sample_data, **benchmark_data}
        config = BacktestConfig(
            initial_capital=100_000_000,
            start_date="20260406",
            end_date="20260408",
            cost_model=CostModel(slippage_model="none"),
            benchmark="KOSPI",
        )
        engine = BacktestEngine(
            config=config,
            data_feed=HistoricalDataFeed(all_data),
            strategies=[no_signal_strategy],
            order_generator=lambda signals, snap, broker: [],
        )
        result = engine.run()
        assert result.snapshots[0].total_value == 100_000_000
        assert result.snapshots[-1].total_value == 100_000_000

    @patch("alphapulse.trading.backtest.engine.KRXCalendar")
    def test_metrics_calculated(self, mock_cal_cls, sample_data, mock_strategy, benchmark_data):
        """결과에 metrics가 포함된다."""
        mock_cal = mock_cal_cls.return_value
        mock_cal.trading_days_between.return_value = [
            "20260406", "20260407", "20260408", "20260409", "20260410",
        ]

        all_data = {**sample_data, **benchmark_data}
        config = BacktestConfig(
            initial_capital=100_000_000,
            start_date="20260406",
            end_date="20260410",
            cost_model=CostModel(slippage_model="none"),
            benchmark="KOSPI",
        )
        engine = BacktestEngine(
            config=config,
            data_feed=HistoricalDataFeed(all_data),
            strategies=[mock_strategy],
            order_generator=self._simple_order_generator,
        )
        result = engine.run()
        assert "total_return" in result.metrics
        assert "sharpe_ratio" in result.metrics
        assert "max_drawdown" in result.metrics

    @patch("alphapulse.trading.backtest.engine.KRXCalendar")
    def test_trades_recorded(self, mock_cal_cls, sample_data, mock_strategy, benchmark_data):
        """체결 이력이 기록된다."""
        mock_cal = mock_cal_cls.return_value
        mock_cal.trading_days_between.return_value = [
            "20260406", "20260407", "20260408", "20260409", "20260410",
        ]

        all_data = {**sample_data, **benchmark_data}
        config = BacktestConfig(
            initial_capital=100_000_000,
            start_date="20260406",
            end_date="20260410",
            cost_model=CostModel(slippage_model="none"),
            benchmark="KOSPI",
        )
        engine = BacktestEngine(
            config=config,
            data_feed=HistoricalDataFeed(all_data),
            strategies=[mock_strategy],
            order_generator=self._simple_order_generator,
        )
        result = engine.run()
        assert len(result.trades) > 0

    @staticmethod
    def _simple_order_generator(signals, snapshot, broker):
        """테스트용 간단한 주문 생성기 — 매수 시그널 → MARKET 매수."""
        orders = []
        for signal in signals:
            if signal.score > 50:
                order = Order(
                    stock=signal.stock,
                    side=Side.BUY,
                    order_type="MARKET",
                    quantity=10,
                    price=None,
                    strategy_id=signal.strategy_id,
                )
                orders.append(order)
        return orders
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/trading/backtest/test_engine.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement BacktestEngine**

`alphapulse/trading/backtest/engine.py`:
```python
"""백테스트 엔진 — 시간 순서대로 전략 파이프라인 시뮬레이션.

거래일을 순회하며 데이터 피드 전진 → 시그널 생성 → 주문 생성 → 체결 → 스냅샷 저장.
"""

from dataclasses import dataclass, field
from typing import Callable

import numpy as np

from alphapulse.trading.backtest.data_feed import HistoricalDataFeed
from alphapulse.trading.backtest.metrics import BacktestMetrics
from alphapulse.trading.backtest.sim_broker import SimBroker
from alphapulse.trading.core.calendar import KRXCalendar
from alphapulse.trading.core.cost_model import CostModel
from alphapulse.trading.core.models import Order, OrderResult, PortfolioSnapshot, Signal


@dataclass
class BacktestConfig:
    """백테스트 설정.

    Attributes:
        initial_capital: 초기 투자금 (원).
        start_date: 시작일 (YYYYMMDD).
        end_date: 종료일 (YYYYMMDD).
        cost_model: 거래 비용 모델.
        benchmark: 벤치마크 코드 (기본 KOSPI).
        use_ai: AI 종합 판단 사용 여부 (기본 False).
        risk_free_rate: 무위험 이자율 (연율, 기본 3.5%).
    """

    initial_capital: float
    start_date: str
    end_date: str
    cost_model: CostModel
    benchmark: str = "KOSPI"
    use_ai: bool = False
    risk_free_rate: float = 0.035


@dataclass
class BacktestResult:
    """백테스트 결과.

    Attributes:
        snapshots: 일별 포트폴리오 스냅샷 목록.
        trades: 체결 이력.
        metrics: 성과 지표 딕셔너리.
        config: 백테스트 설정.
    """

    snapshots: list[PortfolioSnapshot]
    trades: list[OrderResult]
    metrics: dict
    config: BacktestConfig


class BacktestEngine:
    """백테스트 엔진.

    거래일을 순회하며 전략 파이프라인을 시뮬레이션한다.
    데이터 피드, 전략, 주문 생성기를 주입받아 동작한다.

    **설계 의도 (Phase 3 Simplification):**
    이 엔진은 order_generator callable을 주입받아 시그널 → 주문 변환을 외부에 위임한다.
    이는 의도적인 단순화이다. Phase 3에서는 PortfolioManager, RiskManager 없이도
    백테스트 루프 자체를 독립적으로 테스트할 수 있게 한다. Phase 4 (TradingEngine)에서
    PortfolioManager.rebalance() → RiskManager.check_order() → order 생성 파이프라인을
    order_generator로 주입하여 완전한 통합을 달성한다.

    Attributes:
        config: 백테스트 설정.
        data_feed: 히스토리 데이터 피드.
        broker: 시뮬레이션 브로커.
    """

    def __init__(
        self,
        config: BacktestConfig,
        data_feed: HistoricalDataFeed,
        strategies: list,
        order_generator: Callable[[list[Signal], PortfolioSnapshot, SimBroker], list[Order]],
    ) -> None:
        """초기화.

        Args:
            config: 백테스트 설정.
            data_feed: 히스토리 데이터 피드.
            strategies: 전략 리스트 (Strategy Protocol 구현체).
            order_generator: 시그널 → 주문 변환 함수.
        """
        self.config = config
        self.data_feed = data_feed
        self.strategies = strategies
        self.order_generator = order_generator
        self.broker = SimBroker(
            cost_model=config.cost_model,
            data_feed=data_feed,
            initial_cash=config.initial_capital,
        )
        self._calendar = KRXCalendar()
        self._metrics_calc = BacktestMetrics()

    def run(self) -> BacktestResult:
        """백테스트를 실행한다.

        거래일을 순회하며:
        1. data_feed.advance_to(date) — 미래 데이터 차단.
        2. 전략별 시그널 생성.
        3. 주문 생성 → SimBroker 체결.
        4. 일별 스냅샷 저장.

        Returns:
            BacktestResult (스냅샷, 체결 이력, 성과 지표).
        """
        trading_days = self._calendar.trading_days_between(
            self.config.start_date, self.config.end_date,
        )

        snapshots: list[PortfolioSnapshot] = []
        peak_value = self.config.initial_capital

        for date in trading_days:
            self.data_feed.advance_to(date)

            # 전략별 시그널 수집
            all_signals: list[Signal] = []
            for strategy in self.strategies:
                if strategy.should_rebalance("", date, {}):
                    signals = strategy.generate_signals([], {})
                    all_signals.extend(signals)

            # 현재 스냅샷 생성 (주문 전)
            snapshot = self._take_snapshot(date, snapshots)

            # 주문 생성 및 체결
            orders = self.order_generator(all_signals, snapshot, self.broker)
            for order in orders:
                self.broker.submit_order(order)

            # 체결 후 최종 스냅샷
            final_snapshot = self._take_snapshot(date, snapshots)
            snapshots.append(final_snapshot)

        # 벤치마크 수익률 계산
        benchmark_returns = self._get_benchmark_returns(trading_days)

        # 성과 지표 계산
        metrics = self._metrics_calc.calculate(
            snapshots,
            benchmark_returns,
            risk_free_rate=self.config.risk_free_rate,
            trades=self.broker.trade_log,
        )

        return BacktestResult(
            snapshots=snapshots,
            trades=self.broker.trade_log,
            metrics=metrics,
            config=self.config,
        )

    def _take_snapshot(self, date: str,
                       prev_snapshots: list[PortfolioSnapshot]) -> PortfolioSnapshot:
        """현재 포트폴리오 스냅샷을 생성한다."""
        balance = self.broker.get_balance()
        total_value = balance["total_value"]

        if prev_snapshots:
            prev_value = prev_snapshots[-1].total_value
            daily_return = (total_value - prev_value) / prev_value * 100 if prev_value > 0 else 0.0
        else:
            daily_return = 0.0

        initial = self.config.initial_capital
        cumulative_return = (total_value - initial) / initial * 100

        peak = max([s.total_value for s in prev_snapshots] + [initial, total_value])
        drawdown = -(peak - total_value) / peak * 100 if peak > 0 else 0.0

        return PortfolioSnapshot(
            date=date,
            cash=balance["cash"],
            positions=self.broker.get_positions(),
            total_value=total_value,
            daily_return=round(daily_return, 4),
            cumulative_return=round(cumulative_return, 4),
            drawdown=round(drawdown, 4),
        )

    def _get_benchmark_returns(self, trading_days: list[str]) -> np.ndarray:
        """벤치마크 일간 수익률 배열을 생성한다."""
        prices = []
        for date in trading_days:
            self.data_feed.advance_to(date)
            bar = self.data_feed.get_bar(self.config.benchmark)
            if bar:
                prices.append(bar.close)
            else:
                prices.append(prices[-1] if prices else 0)

        if len(prices) < 2:
            return np.array([0.0])

        prices_arr = np.array(prices, dtype=float)
        returns = np.diff(prices_arr) / prices_arr[:-1]
        return returns
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/trading/backtest/test_engine.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add alphapulse/trading/backtest/engine.py tests/trading/backtest/test_engine.py
git commit -m "feat(trading/backtest): add BacktestEngine main simulation loop"
```

---

## Task 5: BacktestReport (터미널 + HTML 리포트)

**Files:**
- Create: `alphapulse/trading/backtest/report.py`
- Test: `tests/trading/backtest/test_report.py`

- [ ] **Step 1: Write failing test**

`tests/trading/backtest/test_report.py`:
```python
"""BacktestReport 테스트 — 터미널 + HTML 출력."""

import os

import pytest

from alphapulse.trading.backtest.engine import BacktestConfig, BacktestResult
from alphapulse.trading.backtest.report import BacktestReport
from alphapulse.trading.core.cost_model import CostModel
from alphapulse.trading.core.models import PortfolioSnapshot


@pytest.fixture
def sample_result():
    """간단한 백테스트 결과."""
    snapshots = [
        PortfolioSnapshot(
            date="20260406", cash=90_000_000, positions=[],
            total_value=100_000_000, daily_return=0.0,
            cumulative_return=0.0, drawdown=0.0,
        ),
        PortfolioSnapshot(
            date="20260407", cash=89_000_000, positions=[],
            total_value=101_000_000, daily_return=1.0,
            cumulative_return=1.0, drawdown=0.0,
        ),
        PortfolioSnapshot(
            date="20260408", cash=88_000_000, positions=[],
            total_value=102_500_000, daily_return=1.49,
            cumulative_return=2.5, drawdown=0.0,
        ),
    ]
    config = BacktestConfig(
        initial_capital=100_000_000,
        start_date="20260406",
        end_date="20260408",
        cost_model=CostModel(slippage_model="none"),
        benchmark="KOSPI",
    )
    metrics = {
        "total_return": 2.5,
        "cagr": 15.3,
        "volatility": 12.5,
        "max_drawdown": -3.2,
        "max_drawdown_duration": 3,
        "sharpe_ratio": 1.22,
        "sortino_ratio": 1.85,
        "calmar_ratio": 4.78,
        "total_trades": 10,
        "win_rate": 65.0,
        "profit_factor": 1.95,
        "avg_win": 150000,
        "avg_loss": 80000,
        "turnover": 3.2,
        "benchmark_return": 1.8,
        "excess_return": 0.7,
        "beta": 0.85,
        "alpha": 5.2,
        "information_ratio": 0.92,
        "tracking_error": 8.5,
        "downside_deviation": 8.0,
    }
    return BacktestResult(
        snapshots=snapshots,
        trades=[],
        metrics=metrics,
        config=config,
    )


@pytest.fixture
def reporter():
    return BacktestReport()


class TestTerminalReport:
    def test_to_terminal_returns_string(self, reporter, sample_result):
        """터미널 리포트가 문자열을 반환한다."""
        output = reporter.to_terminal(sample_result)
        assert isinstance(output, str)
        assert len(output) > 0

    def test_terminal_contains_key_metrics(self, reporter, sample_result):
        """터미널 리포트에 핵심 지표가 포함된다."""
        output = reporter.to_terminal(sample_result)
        assert "2.5" in output  # total_return
        assert "1.22" in output  # sharpe
        assert "-3.2" in output  # max_drawdown
        assert "65.0" in output  # win_rate

    def test_terminal_contains_period_info(self, reporter, sample_result):
        """기간 정보가 포함된다."""
        output = reporter.to_terminal(sample_result)
        assert "20260406" in output
        assert "20260408" in output

    def test_terminal_contains_benchmark_info(self, reporter, sample_result):
        """벤치마크 비교 정보가 포함된다."""
        output = reporter.to_terminal(sample_result)
        assert "0.85" in output  # beta
        assert "KOSPI" in output


class TestHTMLReport:
    def test_to_html_returns_string(self, reporter, sample_result):
        """HTML 리포트가 문자열을 반환한다."""
        html = reporter.to_html(sample_result)
        assert isinstance(html, str)
        assert "<html" in html

    def test_html_contains_metrics(self, reporter, sample_result):
        """HTML에 지표가 포함된다."""
        html = reporter.to_html(sample_result)
        assert "2.5" in html
        assert "1.22" in html

    def test_save_html(self, reporter, sample_result, tmp_path):
        """HTML 파일을 저장한다."""
        output_path = tmp_path / "report.html"
        reporter.save_html(sample_result, str(output_path))
        assert output_path.exists()
        content = output_path.read_text(encoding="utf-8")
        assert "<html" in content
        assert "2.5" in content

    def test_html_contains_equity_data(self, reporter, sample_result):
        """HTML에 자산 곡선 데이터가 포함된다."""
        html = reporter.to_html(sample_result)
        assert "100000000" in html or "100,000,000" in html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/trading/backtest/test_report.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement BacktestReport**

`alphapulse/trading/backtest/report.py`:
```python
"""백테스트 리포트 — 터미널 + HTML 출력.

성과 지표, 자산 곡선, 거래 요약을 포맷팅한다.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from alphapulse.trading.backtest.engine import BacktestResult


class BacktestReport:
    """백테스트 결과를 터미널 텍스트 또는 HTML로 포맷팅한다."""

    def to_terminal(self, result: BacktestResult) -> str:
        """터미널용 텍스트 리포트를 생성한다.

        Args:
            result: 백테스트 결과.

        Returns:
            포맷된 텍스트 문자열.
        """
        m = result.metrics
        c = result.config
        lines = [
            "=" * 60,
            "  백테스트 결과 리포트",
            "=" * 60,
            "",
            f"  기간: {c.start_date} ~ {c.end_date}",
            f"  초기 자본: {c.initial_capital:,.0f}원",
            f"  최종 자산: {result.snapshots[-1].total_value:,.0f}원" if result.snapshots else "",
            f"  벤치마크: {c.benchmark}",
            "",
            "--- 수익률 ---",
            f"  총 수익률:     {m.get('total_return', 0):.4f}%",
            f"  CAGR:          {m.get('cagr', 0):.4f}%",
            f"  변동성:        {m.get('volatility', 0):.4f}%",
            "",
            "--- 리스크 ---",
            f"  최대 낙폭:     {m.get('max_drawdown', 0):.4f}%",
            f"  MDD 지속:      {m.get('max_drawdown_duration', 0)}일",
            f"  하방 변동성:   {m.get('downside_deviation', 0):.4f}%",
            "",
            "--- 리스크 조정 ---",
            f"  샤프 비율:     {m.get('sharpe_ratio', 0):.4f}",
            f"  소르티노:      {m.get('sortino_ratio', 0):.4f}",
            f"  칼마 비율:     {m.get('calmar_ratio', 0):.4f}",
            "",
            "--- 거래 ---",
            f"  총 거래:       {m.get('total_trades', 0)}회",
            f"  승률:          {m.get('win_rate', 0):.1f}%",
            f"  이익 팩터:     {m.get('profit_factor', 0):.4f}",
            f"  평균 수익:     {m.get('avg_win', 0):,.2f}원",
            f"  평균 손실:     {m.get('avg_loss', 0):,.2f}원",
            f"  회전율:        {m.get('turnover', 0):.4f}",
            "",
            f"--- 벤치마크 ({c.benchmark}) ---",
            f"  벤치마크 수익: {m.get('benchmark_return', 0):.4f}%",
            f"  초과 수익:     {m.get('excess_return', 0):.4f}%",
            f"  베타:          {m.get('beta', 0):.4f}",
            f"  알파:          {m.get('alpha', 0):.4f}%",
            f"  정보 비율:     {m.get('information_ratio', 0):.4f}",
            f"  추적 오차:     {m.get('tracking_error', 0):.4f}%",
            "",
            "=" * 60,
        ]
        return "\n".join(lines)

    def to_html(self, result: BacktestResult) -> str:
        """HTML 리포트를 생성한다.

        Args:
            result: 백테스트 결과.

        Returns:
            HTML 문자열.
        """
        m = result.metrics
        c = result.config

        # 자산 곡선 데이터
        dates_js = ", ".join(f'"{s.date}"' for s in result.snapshots)
        values_js = ", ".join(str(int(s.total_value)) for s in result.snapshots)

        html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="utf-8">
    <title>백테스트 리포트 | {c.start_date} ~ {c.end_date}</title>
    <style>
        body {{ font-family: 'Pretendard', -apple-system, sans-serif; margin: 40px; background: #f8f9fa; }}
        h1 {{ color: #1a1a2e; }}
        .metric-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin: 20px 0; }}
        .metric-card {{ background: white; padding: 16px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
        .metric-label {{ font-size: 0.85em; color: #666; }}
        .metric-value {{ font-size: 1.4em; font-weight: 700; color: #1a1a2e; }}
        .metric-value.positive {{ color: #e74c3c; }}
        .metric-value.negative {{ color: #3498db; }}
        .section {{ margin: 30px 0; }}
        .section h2 {{ border-bottom: 2px solid #1a1a2e; padding-bottom: 8px; }}
        table {{ width: 100%; border-collapse: collapse; background: white; border-radius: 8px; overflow: hidden; }}
        th, td {{ padding: 10px 16px; text-align: left; border-bottom: 1px solid #eee; }}
        th {{ background: #1a1a2e; color: white; }}
        .equity-chart {{ background: white; padding: 20px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
    </style>
</head>
<body>
    <h1>백테스트 결과 리포트</h1>
    <p>기간: {c.start_date} ~ {c.end_date} | 초기 자본: {c.initial_capital:,.0f}원 | 벤치마크: {c.benchmark}</p>

    <div class="metric-grid">
        <div class="metric-card">
            <div class="metric-label">총 수익률</div>
            <div class="metric-value {'positive' if m.get('total_return', 0) >= 0 else 'negative'}">{m.get('total_return', 0):.4f}%</div>
        </div>
        <div class="metric-card">
            <div class="metric-label">CAGR</div>
            <div class="metric-value">{m.get('cagr', 0):.4f}%</div>
        </div>
        <div class="metric-card">
            <div class="metric-label">샤프 비율</div>
            <div class="metric-value">{m.get('sharpe_ratio', 0):.4f}</div>
        </div>
        <div class="metric-card">
            <div class="metric-label">소르티노 비율</div>
            <div class="metric-value">{m.get('sortino_ratio', 0):.4f}</div>
        </div>
        <div class="metric-card">
            <div class="metric-label">최대 낙폭</div>
            <div class="metric-value negative">{m.get('max_drawdown', 0):.4f}%</div>
        </div>
        <div class="metric-card">
            <div class="metric-label">승률</div>
            <div class="metric-value">{m.get('win_rate', 0):.1f}%</div>
        </div>
    </div>

    <div class="section">
        <h2>자산 곡선</h2>
        <div class="equity-chart">
            <canvas id="equityChart" width="800" height="300"></canvas>
        </div>
    </div>

    <div class="section">
        <h2>상세 지표</h2>
        <table>
            <tr><th>카테고리</th><th>지표</th><th>값</th></tr>
            <tr><td>수익률</td><td>총 수익률</td><td>{m.get('total_return', 0):.4f}%</td></tr>
            <tr><td>수익률</td><td>CAGR</td><td>{m.get('cagr', 0):.4f}%</td></tr>
            <tr><td>수익률</td><td>변동성</td><td>{m.get('volatility', 0):.4f}%</td></tr>
            <tr><td>리스크</td><td>최대 낙폭</td><td>{m.get('max_drawdown', 0):.4f}%</td></tr>
            <tr><td>리스크</td><td>MDD 지속</td><td>{m.get('max_drawdown_duration', 0)}일</td></tr>
            <tr><td>리스크</td><td>하방 변동성</td><td>{m.get('downside_deviation', 0):.4f}%</td></tr>
            <tr><td>리스크 조정</td><td>샤프 비율</td><td>{m.get('sharpe_ratio', 0):.4f}</td></tr>
            <tr><td>리스크 조정</td><td>소르티노 비율</td><td>{m.get('sortino_ratio', 0):.4f}</td></tr>
            <tr><td>리스크 조정</td><td>칼마 비율</td><td>{m.get('calmar_ratio', 0):.4f}</td></tr>
            <tr><td>거래</td><td>총 거래</td><td>{m.get('total_trades', 0)}회</td></tr>
            <tr><td>거래</td><td>승률</td><td>{m.get('win_rate', 0):.1f}%</td></tr>
            <tr><td>거래</td><td>이익 팩터</td><td>{m.get('profit_factor', 0):.4f}</td></tr>
            <tr><td>거래</td><td>회전율</td><td>{m.get('turnover', 0):.4f}</td></tr>
            <tr><td>벤치마크</td><td>벤치마크 수익</td><td>{m.get('benchmark_return', 0):.4f}%</td></tr>
            <tr><td>벤치마크</td><td>초과 수익</td><td>{m.get('excess_return', 0):.4f}%</td></tr>
            <tr><td>벤치마크</td><td>베타</td><td>{m.get('beta', 0):.4f}</td></tr>
            <tr><td>벤치마크</td><td>알파</td><td>{m.get('alpha', 0):.4f}%</td></tr>
            <tr><td>벤치마크</td><td>정보 비율</td><td>{m.get('information_ratio', 0):.4f}</td></tr>
            <tr><td>벤치마크</td><td>추적 오차</td><td>{m.get('tracking_error', 0):.4f}%</td></tr>
        </table>
    </div>

    <script>
        // 자산 곡선 — 간단한 Canvas 차트
        const dates = [{dates_js}];
        const values = [{values_js}];
        const canvas = document.getElementById('equityChart');
        const ctx = canvas.getContext('2d');
        const w = canvas.width, h = canvas.height;
        const padding = 60;
        const minV = Math.min(...values) * 0.995;
        const maxV = Math.max(...values) * 1.005;
        const xStep = (w - padding * 2) / (values.length - 1 || 1);

        ctx.strokeStyle = '#1a1a2e';
        ctx.lineWidth = 2;
        ctx.beginPath();
        values.forEach((v, i) => {{
            const x = padding + i * xStep;
            const y = h - padding - ((v - minV) / (maxV - minV)) * (h - padding * 2);
            i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
        }});
        ctx.stroke();

        // 축 레이블
        ctx.fillStyle = '#666';
        ctx.font = '11px sans-serif';
        ctx.fillText(dates[0], padding, h - 10);
        ctx.fillText(dates[dates.length - 1], w - padding - 60, h - 10);
        ctx.fillText(minV.toLocaleString(), 0, h - padding);
        ctx.fillText(maxV.toLocaleString(), 0, padding + 10);
    </script>
</body>
</html>"""
        return html

    def save_html(self, result: BacktestResult, path: str) -> None:
        """HTML 리포트를 파일로 저장한다.

        Args:
            result: 백테스트 결과.
            path: 저장 경로.
        """
        html = self.to_html(result)
        Path(path).write_text(html, encoding="utf-8")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/trading/backtest/test_report.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add alphapulse/trading/backtest/report.py tests/trading/backtest/test_report.py
git commit -m "feat(trading/backtest): add BacktestReport terminal + HTML output"
```

---

## Task 6: BacktestStore (backtest.db 저장소)

**Files:**
- Create: `alphapulse/trading/backtest/store.py`
- Test: `tests/trading/backtest/test_store.py`

- [ ] **Step 1: Write failing test**

`tests/trading/backtest/test_store.py`:
```python
"""BacktestStore 테스트 — backtest.db 결과 저장."""

import json

import pytest

from alphapulse.trading.backtest.engine import BacktestConfig, BacktestResult
from alphapulse.trading.backtest.store import BacktestStore
from alphapulse.trading.core.cost_model import CostModel
from alphapulse.trading.core.models import PortfolioSnapshot


@pytest.fixture
def store(tmp_path):
    """임시 DB로 초기화된 BacktestStore."""
    db_path = tmp_path / "backtest.db"
    return BacktestStore(str(db_path))


@pytest.fixture
def sample_result():
    """간단한 백테스트 결과."""
    config = BacktestConfig(
        initial_capital=100_000_000,
        start_date="20260406",
        end_date="20260410",
        cost_model=CostModel(slippage_model="none"),
        benchmark="KOSPI",
    )
    snapshots = [
        PortfolioSnapshot(
            date="20260406", cash=100_000_000, positions=[],
            total_value=100_000_000, daily_return=0.0,
            cumulative_return=0.0, drawdown=0.0,
        ),
        PortfolioSnapshot(
            date="20260407", cash=95_000_000, positions=[],
            total_value=101_500_000, daily_return=1.5,
            cumulative_return=1.5, drawdown=0.0,
        ),
        PortfolioSnapshot(
            date="20260408", cash=93_000_000, positions=[],
            total_value=103_000_000, daily_return=1.48,
            cumulative_return=3.0, drawdown=0.0,
        ),
    ]
    metrics = {
        "total_return": 3.0,
        "sharpe_ratio": 1.5,
        "max_drawdown": -2.0,
    }
    return BacktestResult(
        snapshots=snapshots,
        trades=[],
        metrics=metrics,
        config=config,
    )


class TestBacktestStore:
    def test_save_run_returns_run_id(self, store, sample_result):
        """저장 시 run_id를 반환한다."""
        run_id = store.save_run(sample_result, name="테스트 실행")
        assert isinstance(run_id, str)
        assert len(run_id) > 0

    def test_get_run(self, store, sample_result):
        """저장된 실행을 조회한다."""
        run_id = store.save_run(sample_result, name="테스트 실행")
        run = store.get_run(run_id)
        assert run is not None
        assert run["name"] == "테스트 실행"
        assert run["start_date"] == "20260406"
        assert run["end_date"] == "20260410"

    def test_get_run_metrics(self, store, sample_result):
        """저장된 지표를 조회한다."""
        run_id = store.save_run(sample_result)
        run = store.get_run(run_id)
        metrics = json.loads(run["metrics"])
        assert metrics["total_return"] == 3.0
        assert metrics["sharpe_ratio"] == 1.5

    def test_get_run_not_found(self, store):
        """존재하지 않는 run_id는 None."""
        assert store.get_run("nonexistent") is None

    def test_list_runs(self, store, sample_result):
        """실행 목록을 조회한다."""
        store.save_run(sample_result, name="실행1")
        store.save_run(sample_result, name="실행2")
        runs = store.list_runs()
        assert len(runs) == 2

    def test_list_runs_empty(self, store):
        """실행 없으면 빈 리스트."""
        assert store.list_runs() == []

    def test_save_snapshots(self, store, sample_result):
        """스냅샷이 저장된다."""
        run_id = store.save_run(sample_result, name="스냅샷 테스트")
        snapshots = store.get_snapshots(run_id)
        assert len(snapshots) == 3
        assert snapshots[0]["date"] == "20260406"
        assert snapshots[-1]["total_value"] == 103_000_000

    def test_delete_run(self, store, sample_result):
        """실행을 삭제한다."""
        run_id = store.save_run(sample_result)
        store.delete_run(run_id)
        assert store.get_run(run_id) is None
        assert store.get_snapshots(run_id) == []

    def test_get_initial_and_final_value(self, store, sample_result):
        """초기/최종 자산이 올바르게 저장된다."""
        run_id = store.save_run(sample_result)
        run = store.get_run(run_id)
        assert run["initial_capital"] == 100_000_000
        assert run["final_value"] == 103_000_000

    def test_save_strategies_and_allocations(self, store, sample_result):
        """전략 목록과 배분이 저장/조회된다."""
        strategies = ["momentum", "value"]
        allocations = {"momentum": 0.6, "value": 0.4}
        run_id = store.save_run(
            sample_result, name="전략 테스트",
            strategies=strategies, allocations=allocations,
        )
        run = store.get_run(run_id)
        assert json.loads(run["strategies"]) == ["momentum", "value"]
        assert json.loads(run["allocations"]) == {"momentum": 0.6, "value": 0.4}

    def test_default_strategies_and_allocations(self, store, sample_result):
        """strategies/allocations 미지정 시 빈 기본값이 저장된다."""
        run_id = store.save_run(sample_result)
        run = store.get_run(run_id)
        assert json.loads(run["strategies"]) == []
        assert json.loads(run["allocations"]) == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/trading/backtest/test_store.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement BacktestStore**

`alphapulse/trading/backtest/store.py`:
```python
"""백테스트 결과 SQLite 저장소.

백테스트 실행 이력, 스냅샷을 backtest.db에 저장한다.
"""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from alphapulse.trading.backtest.engine import BacktestResult


class BacktestStore:
    """백테스트 결과 저장소.

    Attributes:
        db_path: SQLite 데이터베이스 경로.
    """

    def __init__(self, db_path: str | Path) -> None:
        """초기화.

        Args:
            db_path: 데이터베이스 파일 경로.
        """
        self.db_path = str(db_path)
        self._create_tables()

    def _create_tables(self) -> None:
        """필요한 테이블을 생성한다."""
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    name TEXT DEFAULT '',
                    strategies TEXT DEFAULT '[]',
                    allocations TEXT DEFAULT '{}',
                    start_date TEXT NOT NULL,
                    end_date TEXT NOT NULL,
                    initial_capital REAL NOT NULL,
                    final_value REAL NOT NULL,
                    benchmark TEXT DEFAULT 'KOSPI',
                    params TEXT DEFAULT '{}',
                    metrics TEXT DEFAULT '{}',
                    created_at REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS snapshots (
                    run_id TEXT NOT NULL,
                    date TEXT NOT NULL,
                    cash REAL,
                    total_value REAL,
                    daily_return REAL,
                    cumulative_return REAL,
                    drawdown REAL,
                    PRIMARY KEY (run_id, date),
                    FOREIGN KEY (run_id) REFERENCES runs(run_id)
                );
                """
            )

    def save_run(self, result: BacktestResult, name: str = "",
                 strategies: list[str] | None = None,
                 allocations: dict[str, float] | None = None) -> str:
        """백테스트 결과를 저장한다.

        Args:
            result: 백테스트 결과.
            name: 사용자 지정 이름 (선택).
            strategies: 전략 ID 목록 (선택).
            allocations: 전략별 배분 비율 (선택).

        Returns:
            생성된 run_id.
        """
        run_id = str(uuid.uuid4())
        config = result.config
        final_value = result.snapshots[-1].total_value if result.snapshots else config.initial_capital

        params = {
            "initial_capital": config.initial_capital,
            "start_date": config.start_date,
            "end_date": config.end_date,
            "benchmark": config.benchmark,
            "use_ai": config.use_ai,
            "risk_free_rate": config.risk_free_rate,
        }

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO runs (run_id, name, strategies, allocations,
                    start_date, end_date,
                    initial_capital, final_value, benchmark, params, metrics, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    name,
                    json.dumps(strategies or [], ensure_ascii=False),
                    json.dumps(allocations or {}, ensure_ascii=False),
                    config.start_date,
                    config.end_date,
                    config.initial_capital,
                    final_value,
                    config.benchmark,
                    json.dumps(params, ensure_ascii=False),
                    json.dumps(result.metrics, ensure_ascii=False),
                    time.time(),
                ),
            )

            # 스냅샷 저장
            snapshot_rows = [
                (
                    run_id,
                    s.date,
                    s.cash,
                    s.total_value,
                    s.daily_return,
                    s.cumulative_return,
                    s.drawdown,
                )
                for s in result.snapshots
            ]
            conn.executemany(
                """
                INSERT INTO snapshots (run_id, date, cash, total_value,
                    daily_return, cumulative_return, drawdown)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                snapshot_rows,
            )

        return run_id

    def get_run(self, run_id: str) -> dict | None:
        """실행 정보를 조회한다.

        Args:
            run_id: 실행 ID.

        Returns:
            실행 정보 딕셔너리 또는 None.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM runs WHERE run_id = ?", (run_id,)
            ).fetchone()
        return dict(row) if row else None

    def list_runs(self) -> list[dict]:
        """모든 실행 목록을 조회한다.

        Returns:
            실행 정보 딕셔너리 리스트 (최신순).
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM runs ORDER BY created_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def get_snapshots(self, run_id: str) -> list[dict]:
        """실행의 스냅샷 목록을 조회한다.

        Args:
            run_id: 실행 ID.

        Returns:
            스냅샷 딕셔너리 리스트 (날짜순).
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM snapshots WHERE run_id = ? ORDER BY date",
                (run_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def delete_run(self, run_id: str) -> None:
        """실행과 관련 스냅샷을 삭제한다.

        Args:
            run_id: 실행 ID.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM snapshots WHERE run_id = ?", (run_id,))
            conn.execute("DELETE FROM runs WHERE run_id = ?", (run_id,))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/trading/backtest/test_store.py -v`
Expected: 11 passed

- [ ] **Step 5: Update backtest __init__.py and commit**

Update `alphapulse/trading/backtest/__init__.py`:
```python
"""백테스트 엔진 — 히스토리 시뮬레이션."""

from .data_feed import HistoricalDataFeed
from .engine import BacktestConfig, BacktestEngine, BacktestResult
from .metrics import BacktestMetrics
from .report import BacktestReport
from .sim_broker import SimBroker
from .store import BacktestStore

__all__ = [
    "BacktestConfig",
    "BacktestEngine",
    "BacktestMetrics",
    "BacktestReport",
    "BacktestResult",
    "BacktestStore",
    "HistoricalDataFeed",
    "SimBroker",
]
```

```bash
git add alphapulse/trading/backtest/ tests/trading/backtest/
git commit -m "feat(trading/backtest): add BacktestStore result persistence"
```

---

## Task 7: StrategyAISynthesizer (AI 전략 종합 완전 구현)

**Files:**
- Modify: `alphapulse/trading/strategy/ai_synthesizer.py` (Phase 2 스텁 → 완전 구현)
- Create: `tests/trading/strategy/test_ai_synthesizer.py`

- [ ] **Step 1: Write failing test**

`tests/trading/strategy/test_ai_synthesizer.py`:
```python
"""StrategyAISynthesizer 테스트 — AI 전략 종합.

asyncio.run()은 CLI entry에서만 사용 (CLAUDE.md 규칙). 테스트는 pytest-asyncio를 사용한다.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from alphapulse.trading.core.models import (
    PortfolioSnapshot,
    Signal,
    Stock,
    StockOpinion,
    StrategySynthesis,
)
from alphapulse.trading.strategy.ai_synthesizer import (
    STRATEGY_SYNTHESIS_PROMPT,
    StrategyAISynthesizer,
)


@pytest.fixture
def samsung():
    return Stock(code="005930", name="삼성전자", market="KOSPI")


@pytest.fixture
def synthesizer():
    return StrategyAISynthesizer()


@pytest.fixture
def pulse_result():
    """Market Pulse 결과."""
    return {
        "date": "20260409",
        "score": 62,
        "signal": "매수 우위",
        "indicator_scores": {
            "kospi_ma_trend": 80,
            "vkospi_level": -30,
            "foreign_flow": 60,
        },
        "details": {},
    }


@pytest.fixture
def ranked_stocks(samsung):
    """팩터 스크리닝 상위 종목."""
    return [
        Signal(stock=samsung, score=85.0, factors={"momentum": 0.9, "value": 0.7},
               strategy_id="screening"),
    ]


@pytest.fixture
def strategy_signals(samsung):
    """전략별 시그널."""
    return {
        "momentum": [
            Signal(stock=samsung, score=78.0, factors={"momentum": 0.85},
                   strategy_id="momentum"),
        ],
        "value": [],
    }


@pytest.fixture
def portfolio():
    """현재 포트폴리오."""
    return PortfolioSnapshot(
        date="20260409", cash=50_000_000, positions=[],
        total_value=100_000_000, daily_return=0.5,
        cumulative_return=3.0, drawdown=-1.2,
    )


@pytest.fixture
def llm_response():
    """LLM 응답 JSON."""
    return json.dumps({
        "market_view": "글로벌 유동성 회복과 외국인 순매수 지속으로 매수 우위 판단",
        "conviction_level": 0.72,
        "allocation_adjustment": {
            "topdown_etf": 0.25,
            "momentum": 0.45,
            "value": 0.30,
        },
        "stock_opinions": [
            {
                "code": "005930",
                "name": "삼성전자",
                "action": "매수",
                "reason": "AI 반도체 수요 회복 + 외국인 순매수 전환",
                "confidence": 0.78,
            },
        ],
        "risk_warnings": ["미중 갈등 재점화 리스크"],
        "reasoning": "정량 62점 매수우위 + 외국인 3일 연속 순매수 + AI 반도체 테마 강세",
    }, ensure_ascii=False)


class TestPromptConstruction:
    def test_prompt_template_exists(self):
        """프롬프트 템플릿이 존재한다."""
        assert isinstance(STRATEGY_SYNTHESIS_PROMPT, str)
        assert len(STRATEGY_SYNTHESIS_PROMPT) > 100

    def test_build_prompt_includes_pulse(self, synthesizer, pulse_result, ranked_stocks,
                                          strategy_signals, portfolio):
        """프롬프트에 Market Pulse 정보가 포함된다."""
        prompt = synthesizer._build_prompt(
            pulse_result, ranked_stocks, strategy_signals,
            [], None, portfolio,
        )
        assert "62" in prompt  # pulse score
        assert "매수 우위" in prompt

    def test_build_prompt_includes_factors(self, synthesizer, pulse_result, ranked_stocks,
                                            strategy_signals, portfolio):
        """프롬프트에 팩터 랭킹이 포함된다."""
        prompt = synthesizer._build_prompt(
            pulse_result, ranked_stocks, strategy_signals,
            [], None, portfolio,
        )
        assert "삼성전자" in prompt
        assert "85.0" in prompt or "85" in prompt

    def test_build_prompt_includes_strategy_signals(self, synthesizer, pulse_result, ranked_stocks,
                                                     strategy_signals, portfolio):
        """프롬프트에 전략별 시그널이 포함된다."""
        prompt = synthesizer._build_prompt(
            pulse_result, ranked_stocks, strategy_signals,
            [], None, portfolio,
        )
        assert "momentum" in prompt

    def test_build_prompt_includes_content(self, synthesizer, pulse_result, ranked_stocks,
                                            strategy_signals, portfolio):
        """프롬프트에 정성 분석이 포함된다."""
        content = ["반도체 업황 회복 전망", "미국 기술주 강세"]
        prompt = synthesizer._build_prompt(
            pulse_result, ranked_stocks, strategy_signals,
            content, None, portfolio,
        )
        assert "반도체 업황 회복 전망" in prompt

    def test_build_prompt_includes_feedback(self, synthesizer, pulse_result, ranked_stocks,
                                             strategy_signals, portfolio):
        """프롬프트에 피드백 컨텍스트가 포함된다."""
        feedback = "최근 5일 적중률: 72%. 외국인 수급 지표 정확도 높음."
        prompt = synthesizer._build_prompt(
            pulse_result, ranked_stocks, strategy_signals,
            [], feedback, portfolio,
        )
        assert "72%" in prompt

    def test_build_prompt_includes_portfolio(self, synthesizer, pulse_result, ranked_stocks,
                                              strategy_signals, portfolio):
        """프롬프트에 현재 포트폴리오 상태가 포함된다."""
        prompt = synthesizer._build_prompt(
            pulse_result, ranked_stocks, strategy_signals,
            [], None, portfolio,
        )
        assert "100,000,000" in prompt or "100000000" in prompt


class TestSynthesizeSuccess:
    @pytest.mark.asyncio
    @patch("alphapulse.trading.strategy.ai_synthesizer.StrategyAISynthesizer._call_llm")
    async def test_synthesize_returns_strategy_synthesis(self, mock_llm, synthesizer,
                                                    pulse_result, ranked_stocks,
                                                    strategy_signals, portfolio,
                                                    llm_response):
        """synthesize()가 StrategySynthesis를 반환한다."""
        mock_llm.return_value = llm_response
        result = await synthesizer.synthesize(
            pulse_result, ranked_stocks, strategy_signals,
            [], None, portfolio,
        )
        assert isinstance(result, StrategySynthesis)
        assert result.conviction_level == 0.72

    @pytest.mark.asyncio
    @patch("alphapulse.trading.strategy.ai_synthesizer.StrategyAISynthesizer._call_llm")
    async def test_synthesize_parses_market_view(self, mock_llm, synthesizer,
                                            pulse_result, ranked_stocks,
                                            strategy_signals, portfolio,
                                            llm_response):
        """market_view가 올바르게 파싱된다."""
        mock_llm.return_value = llm_response
        result = await synthesizer.synthesize(
            pulse_result, ranked_stocks, strategy_signals,
            [], None, portfolio,
        )
        assert "유동성" in result.market_view

    @pytest.mark.asyncio
    @patch("alphapulse.trading.strategy.ai_synthesizer.StrategyAISynthesizer._call_llm")
    async def test_synthesize_parses_stock_opinions(self, mock_llm, synthesizer,
                                               pulse_result, ranked_stocks,
                                               strategy_signals, portfolio,
                                               llm_response):
        """종목별 의견이 StockOpinion으로 파싱된다."""
        mock_llm.return_value = llm_response
        result = await synthesizer.synthesize(
            pulse_result, ranked_stocks, strategy_signals,
            [], None, portfolio,
        )
        assert len(result.stock_opinions) == 1
        assert isinstance(result.stock_opinions[0], StockOpinion)
        assert result.stock_opinions[0].action == "매수"

    @pytest.mark.asyncio
    @patch("alphapulse.trading.strategy.ai_synthesizer.StrategyAISynthesizer._call_llm")
    async def test_synthesize_parses_allocation(self, mock_llm, synthesizer,
                                           pulse_result, ranked_stocks,
                                           strategy_signals, portfolio,
                                           llm_response):
        """전략 배분 조정이 파싱된다."""
        mock_llm.return_value = llm_response
        result = await synthesizer.synthesize(
            pulse_result, ranked_stocks, strategy_signals,
            [], None, portfolio,
        )
        assert "momentum" in result.allocation_adjustment
        assert result.allocation_adjustment["momentum"] == 0.45

    @pytest.mark.asyncio
    @patch("alphapulse.trading.strategy.ai_synthesizer.StrategyAISynthesizer._call_llm")
    async def test_synthesize_parses_risk_warnings(self, mock_llm, synthesizer,
                                              pulse_result, ranked_stocks,
                                              strategy_signals, portfolio,
                                              llm_response):
        """리스크 경고가 파싱된다."""
        mock_llm.return_value = llm_response
        result = await synthesizer.synthesize(
            pulse_result, ranked_stocks, strategy_signals,
            [], None, portfolio,
        )
        assert len(result.risk_warnings) >= 1
        assert "미중" in result.risk_warnings[0]


class TestFallback:
    @pytest.mark.asyncio
    @patch("alphapulse.trading.strategy.ai_synthesizer.StrategyAISynthesizer._call_llm")
    async def test_fallback_on_llm_failure(self, mock_llm, synthesizer,
                                      pulse_result, ranked_stocks,
                                      strategy_signals, portfolio):
        """LLM 실패 시 _fallback()이 호출된다."""
        mock_llm.side_effect = Exception("API Error")
        result = await synthesizer.synthesize(
            pulse_result, ranked_stocks, strategy_signals,
            [], None, portfolio,
        )
        assert isinstance(result, StrategySynthesis)
        assert result.conviction_level == 0.5
        assert "실패" in result.risk_warnings[0] or "실패" in result.reasoning

    @pytest.mark.asyncio
    @patch("alphapulse.trading.strategy.ai_synthesizer.StrategyAISynthesizer._call_llm")
    async def test_fallback_on_invalid_json(self, mock_llm, synthesizer,
                                       pulse_result, ranked_stocks,
                                       strategy_signals, portfolio):
        """잘못된 JSON 응답 시 _fallback()이 호출된다."""
        mock_llm.return_value = "이것은 유효하지 않은 JSON입니다"
        result = await synthesizer.synthesize(
            pulse_result, ranked_stocks, strategy_signals,
            [], None, portfolio,
        )
        assert isinstance(result, StrategySynthesis)
        assert result.conviction_level == 0.5

    def test_fallback_returns_valid_synthesis(self, synthesizer, strategy_signals):
        """_fallback()이 유효한 StrategySynthesis를 반환한다."""
        result = synthesizer._fallback(strategy_signals)
        assert isinstance(result, StrategySynthesis)
        assert 0.0 <= result.conviction_level <= 1.0
        assert isinstance(result.allocation_adjustment, dict)
        assert isinstance(result.stock_opinions, list)
        assert isinstance(result.risk_warnings, list)


class TestParseResponse:
    def test_parse_valid_json(self, synthesizer, llm_response):
        """올바른 JSON을 파싱한다."""
        result = synthesizer._parse_response(llm_response)
        assert isinstance(result, StrategySynthesis)
        assert result.conviction_level == 0.72

    def test_parse_json_in_markdown_block(self, synthesizer, llm_response):
        """마크다운 코드 블록 안의 JSON도 파싱한다."""
        wrapped = f"```json\n{llm_response}\n```"
        result = synthesizer._parse_response(wrapped)
        assert isinstance(result, StrategySynthesis)

    def test_parse_invalid_json_raises(self, synthesizer):
        """잘못된 JSON은 ValueError를 발생시킨다."""
        with pytest.raises(ValueError):
            synthesizer._parse_response("not json")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/trading/strategy/test_ai_synthesizer.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Implement StrategyAISynthesizer (Phase 2 스텁 완전 교체)**

`alphapulse/trading/strategy/ai_synthesizer.py`:
```python
"""AI 전략 종합 — LLM 기반 최종 전략 판단.

정량(Market Pulse, 팩터 랭킹, 전략 시그널) + 정성(콘텐츠 분석) + 피드백을
Google Gemini LLM으로 종합하여 최종 전략 배분 및 종목 의견을 도출한다.

기존 에이전트 패턴 동일: asyncio.to_thread(), try/except, _fallback().
"""

import asyncio
import json
import logging
import re

from alphapulse.core.config import Config
from alphapulse.trading.core.models import (
    PortfolioSnapshot,
    Signal,
    Stock,
    StockOpinion,
    StrategySynthesis,
)

logger = logging.getLogger(__name__)

STRATEGY_SYNTHESIS_PROMPT = """당신은 20년 경력의 수석 투자 전략가입니다.
아래 다섯 가지 입력을 종합하여 최종 전략 판단을 JSON으로 출력하세요.

핵심 규칙:
1. 정량 데이터(Market Pulse, 팩터 분석)를 기본으로 하되 정성 분석과 상충하면 양쪽 근거 명시
2. conviction_level 0.3 미만이면 현금 비중 상향 권고
3. 리스크 경고는 반드시 1개 이상 포함
4. 모든 판단에 구체적 수치 근거를 인용
5. 한국어로 작성

=== 1. 시장 상황 (Market Pulse) ===
날짜: {date}
종합 점수: {pulse_score} ({pulse_signal})
지표별 상세:
{indicator_details}

=== 2. 팩터 분석 (상위 종목 랭킹) ===
{factor_rankings}

=== 3. 전략별 시그널 ===
{strategy_signals}

=== 4. 정성 분석 (콘텐츠) ===
{content_summaries}

=== 5. 과거 성과 피드백 ===
{feedback_context}

=== 현재 포트폴리오 ===
총 자산: {total_value}원
현금: {cash}원
일간 수익률: {daily_return}%
누적 수익률: {cumulative_return}%
드로다운: {drawdown}%

출력 형식 (반드시 유효한 JSON):
{{
  "market_view": "시장 전체 판단 요약 (2~3문장)",
  "conviction_level": 0.0~1.0,
  "allocation_adjustment": {{"topdown_etf": 0.0~1.0, "momentum": 0.0~1.0, "value": 0.0~1.0}},
  "stock_opinions": [
    {{"code": "종목코드", "name": "종목명", "action": "강력매수|매수|유지|축소|매도", "reason": "근거", "confidence": 0.0~1.0}}
  ],
  "risk_warnings": ["경고1", "경고2"],
  "reasoning": "판단 근거 (3~5문장)"
}}
"""


class StrategyAISynthesizer:
    """정량 + 정성 분석을 LLM으로 종합하여 최종 전략 판단.

    Google Gemini API를 asyncio.to_thread()로 호출한다.
    LLM 실패 시 _fallback()으로 규칙 기반 안전 실행.
    """

    def __init__(self) -> None:
        """초기화."""
        self.config = Config()

    async def synthesize(
        self,
        pulse_result: dict,
        ranked_stocks: list[Signal],
        strategy_signals: dict[str, list[Signal]],
        content_summaries: list[str],
        feedback_context: str | None,
        current_portfolio: PortfolioSnapshot,
    ) -> StrategySynthesis:
        """AI 종합 판단을 생성한다.

        Args:
            pulse_result: Market Pulse 11개 지표 결과.
            ranked_stocks: 팩터 스크리닝 상위 종목 시그널.
            strategy_signals: 전략별 시그널 딕셔너리.
            content_summaries: 정성 분석 결과 요약 리스트.
            feedback_context: 적중률/피드백 텍스트 (선택).
            current_portfolio: 현재 포트폴리오 스냅샷.

        Returns:
            StrategySynthesis 데이터클래스.
        """
        prompt = self._build_prompt(
            pulse_result, ranked_stocks, strategy_signals,
            content_summaries, feedback_context, current_portfolio,
        )
        try:
            response = await self._call_llm(prompt)
            return self._parse_response(response)
        except Exception as e:
            logger.error(f"AI 전략 종합 실패: {e}")
            return self._fallback(strategy_signals)

    def _build_prompt(
        self,
        pulse_result: dict,
        ranked_stocks: list[Signal],
        strategy_signals: dict[str, list[Signal]],
        content_summaries: list[str],
        feedback_context: str | None,
        current_portfolio: PortfolioSnapshot,
    ) -> str:
        """LLM 프롬프트를 구성한다.

        5가지 입력 카테고리를 구조화된 프롬프트로 조합한다.
        """
        # 1. 지표 상세
        indicator_details = "\n".join(
            f"  {k}: {v:+.0f}" if isinstance(v, (int, float)) else f"  {k}: {v}"
            for k, v in pulse_result.get("indicator_scores", {}).items()
        )
        if not indicator_details:
            indicator_details = "  (지표 데이터 없음)"

        # 2. 팩터 랭킹
        if ranked_stocks:
            factor_lines = []
            for i, sig in enumerate(ranked_stocks[:20], 1):
                factors_str = ", ".join(f"{k}={v:.2f}" for k, v in sig.factors.items())
                factor_lines.append(
                    f"  {i}. {sig.stock.name}({sig.stock.code}) "
                    f"점수={sig.score:.1f} [{factors_str}]"
                )
            factor_rankings = "\n".join(factor_lines)
        else:
            factor_rankings = "  (팩터 분석 결과 없음)"

        # 3. 전략별 시그널
        strategy_lines = []
        for strat_id, signals in strategy_signals.items():
            if signals:
                top = signals[:5]
                names = ", ".join(f"{s.stock.name}({s.score:.0f})" for s in top)
                strategy_lines.append(f"  {strat_id}: {len(signals)}종목 — 상위: {names}")
            else:
                strategy_lines.append(f"  {strat_id}: 시그널 없음")
        strategy_signals_text = "\n".join(strategy_lines) if strategy_lines else "  (전략 시그널 없음)"

        # 4. 정성 분석
        if content_summaries:
            content_text = "\n".join(f"  - {s}" for s in content_summaries)
        else:
            content_text = "  (정성 분석 없음 — 정량 데이터만으로 판단)"

        # 5. 피드백
        feedback_text = feedback_context if feedback_context else "  (피드백 데이터 없음)"

        return STRATEGY_SYNTHESIS_PROMPT.format(
            date=pulse_result.get("date", ""),
            pulse_score=pulse_result.get("score", 0),
            pulse_signal=pulse_result.get("signal", ""),
            indicator_details=indicator_details,
            factor_rankings=factor_rankings,
            strategy_signals=strategy_signals_text,
            content_summaries=content_text,
            feedback_context=feedback_text,
            total_value=f"{current_portfolio.total_value:,.0f}",
            cash=f"{current_portfolio.cash:,.0f}",
            daily_return=f"{current_portfolio.daily_return:.2f}",
            cumulative_return=f"{current_portfolio.cumulative_return:.2f}",
            drawdown=f"{current_portfolio.drawdown:.2f}",
        )

    async def _call_llm(self, prompt: str) -> str:
        """asyncio.to_thread()로 sync genai API를 호출한다.

        Args:
            prompt: LLM 프롬프트.

        Returns:
            LLM 응답 텍스트.
        """
        from google import genai

        def _sync_call():
            client = genai.Client(api_key=self.config.GEMINI_API_KEY)
            response = client.models.generate_content(
                model=self.config.GEMINI_MODEL,
                contents=prompt,
                config=genai.types.GenerateContentConfig(
                    max_output_tokens=4096,
                    temperature=0.2,
                ),
            )
            return response.text

        return await asyncio.to_thread(_sync_call)

    def _parse_response(self, response: str) -> StrategySynthesis:
        """LLM 응답을 StrategySynthesis로 파싱한다.

        JSON 응답을 파싱하여 구조화된 데이터클래스로 변환한다.
        마크다운 코드 블록 내부 JSON도 처리한다.

        Args:
            response: LLM 응답 텍스트.

        Returns:
            StrategySynthesis 데이터클래스.

        Raises:
            ValueError: 유효하지 않은 JSON.
        """
        # 마크다운 코드 블록 제거
        json_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", response, re.DOTALL)
        json_str = json_match.group(1) if json_match else response

        try:
            data = json.loads(json_str.strip())
        except json.JSONDecodeError as e:
            raise ValueError(f"LLM 응답 JSON 파싱 실패: {e}") from e

        # StockOpinion 변환
        stock_opinions = []
        for op in data.get("stock_opinions", []):
            stock = Stock(
                code=op.get("code", ""),
                name=op.get("name", ""),
                market="KOSPI",  # 기본값
            )
            stock_opinions.append(StockOpinion(
                stock=stock,
                action=op.get("action", "유지"),
                reason=op.get("reason", ""),
                confidence=float(op.get("confidence", 0.5)),
            ))

        return StrategySynthesis(
            market_view=data.get("market_view", ""),
            conviction_level=float(data.get("conviction_level", 0.5)),
            allocation_adjustment=data.get("allocation_adjustment", {}),
            stock_opinions=stock_opinions,
            risk_warnings=data.get("risk_warnings", []),
            reasoning=data.get("reasoning", ""),
        )

    def _fallback(self, strategy_signals: dict[str, list[Signal]]) -> StrategySynthesis:
        """LLM 실패 시 규칙 기반 기본 판단.

        정량 시그널만으로 보수적인 기본값을 반환한다.

        Args:
            strategy_signals: 전략별 시그널.

        Returns:
            StrategySynthesis (기본 보수적 배분).
        """
        # 전략별 균등 배분
        strategy_ids = list(strategy_signals.keys()) if strategy_signals else []
        if strategy_ids:
            equal_weight = round(1.0 / len(strategy_ids), 2)
            allocation = {sid: equal_weight for sid in strategy_ids}
        else:
            allocation = {}

        return StrategySynthesis(
            market_view="AI 분석 불가 — 정량 시그널 기반 실행",
            conviction_level=0.5,
            allocation_adjustment=allocation,
            stock_opinions=[],
            risk_warnings=["AI 종합 판단 실패. 규칙 기반으로 실행됨."],
            reasoning="LLM 호출 실패로 정량 시그널만 사용",
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/trading/strategy/test_ai_synthesizer.py -v`
Expected: 17 passed

- [ ] **Step 5: Commit**

```bash
git add alphapulse/trading/strategy/ai_synthesizer.py tests/trading/strategy/test_ai_synthesizer.py
git commit -m "feat(trading/strategy): fully implement StrategyAISynthesizer with Gemini integration"
```

---

## Verification Checklist

After completing all tasks, verify:

- [ ] `pytest tests/trading/backtest/ -v` — 모든 백테스트 테스트 통과 (~76개)
- [ ] `pytest tests/trading/strategy/test_ai_synthesizer.py -v` — AI 종합 테스트 통과 (~17개)
- [ ] `pytest tests/trading/ -v` — 모든 trading 테스트 통과 (Phase 1 + 2 + 3)
- [ ] `pytest tests/ -v` — 기존 275개 + trading 테스트 전체 회귀 없음
- [ ] `ruff check alphapulse/trading/backtest/` — 린트 에러 없음
- [ ] `ruff check alphapulse/trading/strategy/ai_synthesizer.py` — 린트 에러 없음
- [ ] 모든 파일이 프로젝트 컨벤션 준수 (sync-only for backtest, async for AI, 한국어 독스트링, 200줄 제한)
- [ ] `asyncio.run()` 사용 없음 (CLI entry 제외) — hook이 자동 검사
- [ ] SimBroker가 Broker Protocol의 5개 메서드를 모두 구현
- [ ] HistoricalDataFeed가 look-ahead bias를 AssertionError로 차단
- [ ] BacktestMetrics가 모든 22개 지표를 계산 (수익률 3 + monthly_returns, 리스크 3, 리스크조정 3, 거래 6, 벤치마크 6)
- [ ] AI Synthesizer가 _call_llm 실패 시 _fallback() 반환
- [ ] AI Synthesizer 테스트에서 `asyncio.run()` 미사용 (pytest-asyncio 패턴)
- [ ] HistoricalDataFeed가 DataProvider Protocol 스텁 메서드 구현 (get_financials, get_investor_flow, get_short_interest)
- [ ] BacktestStore의 runs 테이블에 strategies, allocations 컬럼 존재
- [ ] SimBroker가 `isinstance(broker, Broker)` 프로토콜 적합성 테스트 통과

---

## CLI Commands

```bash
# 백테스트 모듈 테스트
pytest tests/trading/backtest/ -v

# AI 종합 테스트
pytest tests/trading/strategy/test_ai_synthesizer.py -v

# 전체 trading 테스트
pytest tests/trading/ -v

# 커버리지
pytest tests/trading/backtest/ --cov=alphapulse.trading.backtest

# 린트
ruff check alphapulse/trading/backtest/ alphapulse/trading/strategy/ai_synthesizer.py
```

---

## Next Plans

After Phase 3 completion, the following plan will be created:

| Plan | Phases | Description |
|------|--------|-------------|
| **Plan 4** | ⑨⑩ | KIS 증권사 API 연동 (broker/) + 트레이딩 오케스트레이터 (orchestrator/) — 실매매/모의투자 브로커, 안전장치, 일일 파이프라인, 스케줄러, 텔레그램 알림, CLI 확장 |

Plan 4 is the final plan. Start Plan 4 only after Plan 3 is fully verified.
