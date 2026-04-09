# Trading System Phase 1: Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the foundational layer of the AlphaPulse Trading System — core data models, stock-level data collectors, and multi-factor screening engine.

**Architecture:** Modular plugin architecture under `alphapulse/trading/`. Protocol-based interfaces enable future subsystems (strategy, portfolio, risk, broker) to plug in without modifying this foundation. All modules are SYNC (no asyncio) matching the existing market/ pattern.

**Tech Stack:** Python 3.11+, pykrx, pandas, numpy, SQLite, pytest, dataclasses, StrEnum

**Spec:** `docs/superpowers/specs/2026-04-09-trading-system-design.md`

**Scope:** Phase ①②③ (Core + Data + Screening) of 10-phase plan. Subsequent phases planned separately.

---

## File Structure

### New Files to Create

```
alphapulse/trading/
├── __init__.py
├── core/
│   ├── __init__.py
│   ├── enums.py              # Task 1: StrEnum 열거형
│   ├── models.py             # Task 2: 공유 데이터 클래스
│   ├── calendar.py           # Task 3: KRX 마켓 캘린더
│   ├── cost_model.py         # Task 4: 거래 비용 모델
│   ├── audit.py              # Task 5: 감사 추적 로거
│   ├── interfaces.py         # Task 6: Protocol 인터페이스
│   └── adapters.py           # Task 6: 기존 시스템 어댑터
├── data/
│   ├── __init__.py
│   ├── store.py              # Task 7: 종목 데이터 SQLite 저장소
│   ├── stock_collector.py    # Task 8: OHLCV + 시가총액 수집
│   ├── fundamental_collector.py  # Task 9: 재무제표 수집
│   ├── flow_collector.py     # Task 10: 종목별 수급 수집
│   ├── short_collector.py    # Task 10: 공매도/신용 수집
│   └── universe.py           # Task 11: 투자 유니버스 관리
└── screening/
    ├── __init__.py
    ├── factors.py            # Task 12: 팩터 계산
    ├── filter.py             # Task 13: 투자 제외 필터
    └── ranker.py             # Task 14: 멀티팩터 랭킹

tests/trading/
├── __init__.py
├── conftest.py               # 공유 픽스처
├── core/
│   ├── __init__.py
│   ├── test_enums.py
│   ├── test_models.py
│   ├── test_calendar.py
│   ├── test_cost_model.py
│   ├── test_audit.py
│   └── test_adapters.py
├── data/
│   ├── __init__.py
│   ├── test_store.py
│   ├── test_stock_collector.py
│   ├── test_fundamental_collector.py
│   ├── test_flow_collector.py
│   ├── test_short_collector.py
│   └── test_universe.py
└── screening/
    ├── __init__.py
    ├── test_factors.py
    ├── test_filter.py
    └── test_ranker.py
```

### Files to Modify

- `alphapulse/cli.py` — Task 15: `ap trading screen` CLI 명령 추가

---

## Task 1: 열거형 + 패키지 구조

**Files:**
- Create: `alphapulse/trading/__init__.py`
- Create: `alphapulse/trading/core/__init__.py`
- Create: `alphapulse/trading/core/enums.py`
- Test: `tests/trading/__init__.py`
- Test: `tests/trading/core/__init__.py`
- Test: `tests/trading/core/test_enums.py`

- [ ] **Step 1: Create package structure**

```bash
mkdir -p alphapulse/trading/core
mkdir -p alphapulse/trading/data
mkdir -p alphapulse/trading/screening
mkdir -p tests/trading/core
mkdir -p tests/trading/data
mkdir -p tests/trading/screening
```

Create empty `__init__.py` files:

`alphapulse/trading/__init__.py`:
```python
"""AlphaPulse 자동 매매 시스템."""
```

`alphapulse/trading/core/__init__.py`:
```python
"""Trading 핵심 데이터 모델 및 인터페이스."""

from .enums import (
    DrawdownAction,
    OrderType,
    RebalanceFreq,
    RiskAction,
    Side,
    TradingMode,
)

__all__ = [
    "Side",
    "OrderType",
    "TradingMode",
    "RebalanceFreq",
    "RiskAction",
    "DrawdownAction",
]
```

`tests/trading/__init__.py`, `tests/trading/core/__init__.py`, `tests/trading/data/__init__.py`, `tests/trading/screening/__init__.py`: empty files.

- [ ] **Step 2: Write failing test for enums**

`tests/trading/core/test_enums.py`:
```python
"""Trading 열거형 테스트."""

from alphapulse.trading.core.enums import (
    DrawdownAction,
    OrderType,
    RebalanceFreq,
    RiskAction,
    Side,
    TradingMode,
)


class TestSide:
    def test_values(self):
        assert Side.BUY == "BUY"
        assert Side.SELL == "SELL"

    def test_is_string(self):
        assert isinstance(Side.BUY, str)


class TestOrderType:
    def test_values(self):
        assert OrderType.MARKET == "MARKET"
        assert OrderType.LIMIT == "LIMIT"


class TestTradingMode:
    def test_values(self):
        assert TradingMode.BACKTEST == "backtest"
        assert TradingMode.PAPER == "paper"
        assert TradingMode.LIVE == "live"


class TestRebalanceFreq:
    def test_values(self):
        assert RebalanceFreq.DAILY == "daily"
        assert RebalanceFreq.WEEKLY == "weekly"
        assert RebalanceFreq.SIGNAL_DRIVEN == "signal_driven"


class TestRiskAction:
    def test_values(self):
        assert RiskAction.APPROVE == "APPROVE"
        assert RiskAction.REDUCE_SIZE == "REDUCE_SIZE"
        assert RiskAction.REJECT == "REJECT"


class TestDrawdownAction:
    def test_values(self):
        assert DrawdownAction.NORMAL == "NORMAL"
        assert DrawdownAction.WARN == "WARN"
        assert DrawdownAction.DELEVERAGE == "DELEVERAGE"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/trading/core/test_enums.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'alphapulse.trading.core.enums'`

- [ ] **Step 4: Implement enums**

`alphapulse/trading/core/enums.py`:
```python
"""Trading 시스템 열거형 정의."""

from enum import StrEnum


class Side(StrEnum):
    """매매 방향."""
    BUY = "BUY"
    SELL = "SELL"


class OrderType(StrEnum):
    """주문 유형."""
    MARKET = "MARKET"
    LIMIT = "LIMIT"


class TradingMode(StrEnum):
    """실행 모드."""
    BACKTEST = "backtest"
    PAPER = "paper"
    LIVE = "live"


class RebalanceFreq(StrEnum):
    """리밸런싱 주기."""
    DAILY = "daily"
    WEEKLY = "weekly"
    SIGNAL_DRIVEN = "signal_driven"


class RiskAction(StrEnum):
    """리스크 검증 결과."""
    APPROVE = "APPROVE"
    REDUCE_SIZE = "REDUCE_SIZE"
    REJECT = "REJECT"


class DrawdownAction(StrEnum):
    """드로다운 대응 수준."""
    NORMAL = "NORMAL"
    WARN = "WARN"
    DELEVERAGE = "DELEVERAGE"
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/trading/core/test_enums.py -v`
Expected: 6 passed

- [ ] **Step 6: Commit**

```bash
git add alphapulse/trading/ tests/trading/
git commit -m "feat(trading): add package structure + enums"
```

---

## Task 2: 공유 데이터 모델

**Files:**
- Create: `alphapulse/trading/core/models.py`
- Test: `tests/trading/core/test_models.py`

- [ ] **Step 1: Write failing test**

`tests/trading/core/test_models.py`:
```python
"""Trading 데이터 모델 테스트."""

from datetime import datetime

from alphapulse.trading.core.models import (
    OHLCV,
    Order,
    OrderResult,
    PortfolioSnapshot,
    Position,
    Signal,
    Stock,
    StockOpinion,
    StrategySynthesis,
)


class TestStock:
    def test_creation(self):
        stock = Stock(code="005930", name="삼성전자", market="KOSPI")
        assert stock.code == "005930"
        assert stock.name == "삼성전자"
        assert stock.market == "KOSPI"
        assert stock.sector == ""

    def test_frozen(self):
        """Stock은 불변(frozen)이어야 한다."""
        stock = Stock(code="005930", name="삼성전자", market="KOSPI")
        try:
            stock.code = "000660"
            assert False, "frozen dataclass should raise"
        except AttributeError:
            pass

    def test_equality(self):
        s1 = Stock(code="005930", name="삼성전자", market="KOSPI")
        s2 = Stock(code="005930", name="삼성전자", market="KOSPI")
        assert s1 == s2

    def test_with_sector(self):
        stock = Stock(code="005930", name="삼성전자", market="KOSPI", sector="반도체")
        assert stock.sector == "반도체"


class TestOHLCV:
    def test_creation(self):
        bar = OHLCV(date="20260409", open=72000, high=73000,
                     low=71500, close=72500, volume=10_000_000)
        assert bar.close == 72500
        assert bar.market_cap == 0  # default

    def test_with_market_cap(self):
        bar = OHLCV(date="20260409", open=72000, high=73000,
                     low=71500, close=72500, volume=10_000_000,
                     market_cap=430_000_000_000_000)
        assert bar.market_cap == 430_000_000_000_000


class TestPosition:
    def test_creation(self):
        stock = Stock(code="005930", name="삼성전자", market="KOSPI")
        pos = Position(stock=stock, quantity=100, avg_price=72000,
                        current_price=73000, unrealized_pnl=100000,
                        weight=0.05, strategy_id="momentum")
        assert pos.quantity == 100
        assert pos.strategy_id == "momentum"


class TestOrder:
    def test_market_order(self):
        stock = Stock(code="005930", name="삼성전자", market="KOSPI")
        order = Order(stock=stock, side="BUY", order_type="MARKET",
                       quantity=100, price=None, strategy_id="momentum")
        assert order.price is None
        assert order.reason == ""

    def test_limit_order_with_reason(self):
        stock = Stock(code="005930", name="삼성전자", market="KOSPI")
        order = Order(stock=stock, side="SELL", order_type="LIMIT",
                       quantity=50, price=73000, strategy_id="value",
                       reason="리밸런싱")
        assert order.price == 73000
        assert order.reason == "리밸런싱"


class TestSignal:
    def test_creation(self):
        stock = Stock(code="005930", name="삼성전자", market="KOSPI")
        signal = Signal(stock=stock, score=75.0,
                         factors={"momentum": 0.8, "value": 0.3},
                         strategy_id="momentum")
        assert signal.score == 75.0
        assert isinstance(signal.timestamp, datetime)


class TestPortfolioSnapshot:
    def test_creation(self):
        snap = PortfolioSnapshot(
            date="20260409", cash=50_000_000,
            positions=[], total_value=100_000_000,
            daily_return=0.5, cumulative_return=8.3, drawdown=-2.1,
        )
        assert snap.total_value == 100_000_000
        assert snap.positions == []


class TestStrategySynthesis:
    def test_creation(self):
        syn = StrategySynthesis(
            market_view="매수 우위",
            conviction_level=0.72,
            allocation_adjustment={"topdown_etf": 0.3},
            stock_opinions=[],
            risk_warnings=["변동성 확대"],
            reasoning="외국인 순매수 지속",
        )
        assert syn.conviction_level == 0.72


class TestStockOpinion:
    def test_creation(self):
        stock = Stock(code="005930", name="삼성전자", market="KOSPI")
        opinion = StockOpinion(
            stock=stock, action="매수",
            reason="외국인 수급 전환", confidence=0.8,
        )
        assert opinion.action == "매수"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/trading/core/test_models.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement models**

`alphapulse/trading/core/models.py`:
```python
"""Trading 시스템 공유 데이터 모델."""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class Stock:
    """종목 식별자.

    Attributes:
        code: 종목코드 (예: "005930").
        name: 종목명 (예: "삼성전자").
        market: 시장 구분 ("KOSPI" | "KOSDAQ" | "ETF").
        sector: 업종 (ETF는 빈 문자열).
    """
    code: str
    name: str
    market: str
    sector: str = ""


@dataclass
class OHLCV:
    """일봉 데이터.

    Attributes:
        date: 날짜 (YYYYMMDD).
        open: 시가.
        high: 고가.
        low: 저가.
        close: 종가.
        volume: 거래량 (주).
        market_cap: 시가총액 (원).
    """
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int
    market_cap: float = 0


@dataclass
class Position:
    """보유 포지션.

    Attributes:
        stock: 종목.
        quantity: 보유 수량.
        avg_price: 평균 매수가.
        current_price: 현재가 (최종 종가).
        unrealized_pnl: 미실현 손익 (원).
        weight: 포트폴리오 내 비중 (0~1).
        strategy_id: 보유 전략 ID.
    """
    stock: Stock
    quantity: int
    avg_price: float
    current_price: float
    unrealized_pnl: float
    weight: float
    strategy_id: str


@dataclass
class Order:
    """매매 주문.

    Attributes:
        stock: 종목.
        side: 매매 방향 ("BUY" | "SELL").
        order_type: 주문 유형 ("MARKET" | "LIMIT").
        quantity: 주문 수량.
        price: 지정가 (LIMIT일 때만, MARKET은 None).
        strategy_id: 발생 전략 ID.
        reason: 주문 사유 (감사 추적용).
    """
    stock: Stock
    side: str
    order_type: str
    quantity: int
    price: float | None
    strategy_id: str
    reason: str = ""


@dataclass
class OrderResult:
    """주문 체결 결과.

    Attributes:
        order_id: 주문 번호.
        order: 원래 주문.
        status: 체결 상태 ("filled" | "partial" | "rejected" | "pending").
        filled_quantity: 체결 수량.
        filled_price: 체결가.
        commission: 수수료 (원).
        tax: 세금 (원).
        filled_at: 체결 시각.
    """
    order_id: str
    order: Order
    status: str
    filled_quantity: int
    filled_price: float
    commission: float
    tax: float
    filled_at: datetime | None


@dataclass
class Signal:
    """종목 매매 시그널.

    Attributes:
        stock: 종목.
        score: 종합 점수 (-100 ~ +100).
        factors: 팩터별 점수 딕셔너리.
        strategy_id: 발생 전략 ID.
        timestamp: 생성 시각.
    """
    stock: Stock
    score: float
    factors: dict
    strategy_id: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class PortfolioSnapshot:
    """특정 시점의 포트폴리오 상태.

    Attributes:
        date: 날짜 (YYYYMMDD).
        cash: 현금 (원).
        positions: 보유 포지션 목록.
        total_value: 총 자산 (현금 + 평가액).
        daily_return: 일간 수익률 (%).
        cumulative_return: 누적 수익률 (%).
        drawdown: 고점 대비 하락률 (%).
    """
    date: str
    cash: float
    positions: list[Position]
    total_value: float
    daily_return: float
    cumulative_return: float
    drawdown: float


@dataclass
class StockOpinion:
    """AI 종목별 의견.

    Attributes:
        stock: 종목.
        action: 매매 의견 ("강력매수" | "매수" | "유지" | "축소" | "매도").
        reason: 근거.
        confidence: 확신도 (0~1).
    """
    stock: Stock
    action: str
    reason: str
    confidence: float


@dataclass
class StrategySynthesis:
    """AI 종합 판단 결과.

    Attributes:
        market_view: 시장 전체 판단 요약.
        conviction_level: 확신도 (0~1).
        allocation_adjustment: 전략 배분 조정 제안.
        stock_opinions: 종목별 AI 의견 목록.
        risk_warnings: 리스크 경고 목록.
        reasoning: 판단 근거.
    """
    market_view: str
    conviction_level: float
    allocation_adjustment: dict
    stock_opinions: list[StockOpinion]
    risk_warnings: list[str]
    reasoning: str
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/trading/core/test_models.py -v`
Expected: 11 passed

- [ ] **Step 5: Update core __init__.py and commit**

Update `alphapulse/trading/core/__init__.py` to export models:
```python
"""Trading 핵심 데이터 모델 및 인터페이스."""

from .enums import (
    DrawdownAction,
    OrderType,
    RebalanceFreq,
    RiskAction,
    Side,
    TradingMode,
)
from .models import (
    OHLCV,
    Order,
    OrderResult,
    PortfolioSnapshot,
    Position,
    Signal,
    Stock,
    StockOpinion,
    StrategySynthesis,
)

__all__ = [
    "Side",
    "OrderType",
    "TradingMode",
    "RebalanceFreq",
    "RiskAction",
    "DrawdownAction",
    "Stock",
    "OHLCV",
    "Position",
    "Order",
    "OrderResult",
    "Signal",
    "PortfolioSnapshot",
    "StockOpinion",
    "StrategySynthesis",
]
```

```bash
git add alphapulse/trading/core/ tests/trading/core/
git commit -m "feat(trading): add core data models"
```

---

## Task 3: KRX 마켓 캘린더

**Files:**
- Create: `alphapulse/trading/core/calendar.py`
- Test: `tests/trading/core/test_calendar.py`

- [ ] **Step 1: Write failing test**

`tests/trading/core/test_calendar.py`:
```python
"""KRX 마켓 캘린더 테스트."""

from alphapulse.trading.core.calendar import KRXCalendar


class TestKRXCalendar:
    def setup_method(self):
        self.cal = KRXCalendar()

    def test_weekday_is_trading_day(self):
        """평일은 거래일이다 (공휴일 아닌 경우)."""
        # 2026-04-06 월요일
        assert self.cal.is_trading_day("20260406") is True

    def test_saturday_is_not_trading_day(self):
        assert self.cal.is_trading_day("20260411") is False  # 토요일

    def test_sunday_is_not_trading_day(self):
        assert self.cal.is_trading_day("20260412") is False  # 일요일

    def test_new_years_day_is_not_trading_day(self):
        """신정은 공휴일이다."""
        assert self.cal.is_trading_day("20260101") is False

    def test_chuseok_is_not_trading_day(self):
        """추석 연휴는 공휴일이다."""
        # 2026년 추석: 9/24(목), 9/25(금) 추석당일, 9/26(토)
        assert self.cal.is_trading_day("20260924") is False
        assert self.cal.is_trading_day("20260925") is False

    def test_next_trading_day_from_friday(self):
        """금요일 다음 거래일은 월요일."""
        # 2026-04-10 금요일 → 2026-04-13 월요일
        assert self.cal.next_trading_day("20260410") == "20260413"

    def test_next_trading_day_skips_holiday(self):
        """공휴일을 건너뛴다."""
        # 2025-12-31(수) → 2026-01-02(금) (1/1 신정 건너뜀)
        assert self.cal.next_trading_day("20251231") == "20260102"

    def test_prev_trading_day_from_monday(self):
        """월요일 이전 거래일은 금요일."""
        # 2026-04-13 월요일 → 2026-04-10 금요일
        assert self.cal.prev_trading_day("20260413") == "20260410"

    def test_trading_days_between(self):
        """구간 거래일 목록."""
        # 2026-04-06(월) ~ 2026-04-10(금) = 5 영업일
        days = self.cal.trading_days_between("20260406", "20260410")
        assert len(days) == 5
        assert days[0] == "20260406"
        assert days[-1] == "20260410"

    def test_trading_days_between_excludes_weekend(self):
        """주말 포함 구간에서 주말은 제외."""
        # 2026-04-09(목) ~ 2026-04-14(화) = 4일 (토일 제외)
        days = self.cal.trading_days_between("20260409", "20260414")
        assert len(days) == 4
        assert "20260411" not in days  # 토
        assert "20260412" not in days  # 일
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/trading/core/test_calendar.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement calendar**

`alphapulse/trading/core/calendar.py`:
```python
"""한국거래소(KRX) 영업일 캘린더.

pykrx의 내장 캘린더를 활용하되, 폴백으로 자체 공휴일 테이블을 유지한다.
"""

from datetime import datetime, timedelta


# 한국 고정 공휴일 (월/일)
_FIXED_HOLIDAYS = {
    (1, 1),    # 신정
    (3, 1),    # 삼일절
    (5, 5),    # 어린이날
    (6, 6),    # 현충일
    (8, 15),   # 광복절
    (10, 3),   # 개천절
    (10, 9),   # 한글날
    (12, 25),  # 크리스마스
}

# 연도별 변동 공휴일 (음력 명절, 대체공휴일 등)
# 매년 초에 KRX 공시 기반으로 갱신해야 한다.
_VARIABLE_HOLIDAYS: dict[int, set[tuple[int, int]]] = {
    2025: {
        (1, 28), (1, 29), (1, 30),   # 설날 연휴
        (5, 6),                        # 대체공휴일
        (10, 5), (10, 6), (10, 7),    # 추석 연휴
    },
    2026: {
        (2, 16), (2, 17), (2, 18),   # 설날 연휴
        (5, 6),                        # 대체공휴일
        (9, 24), (9, 25), (9, 26),   # 추석 연휴 (26은 토요일)
    },
}


class KRXCalendar:
    """한국거래소 영업일 관리.

    평일이면서 공휴일이 아닌 날을 거래일로 판단한다.
    """

    def is_trading_day(self, date: str) -> bool:
        """해당 날짜가 거래일인지 판단한다.

        Args:
            date: 날짜 문자열 (YYYYMMDD).

        Returns:
            거래일이면 True.
        """
        dt = self._parse(date)
        if dt.weekday() >= 5:  # 토(5), 일(6)
            return False
        return not self._is_holiday(dt)

    def next_trading_day(self, date: str) -> str:
        """다음 거래일을 반환한다.

        Args:
            date: 기준 날짜 (YYYYMMDD).

        Returns:
            다음 거래일 문자열 (YYYYMMDD).
        """
        dt = self._parse(date) + timedelta(days=1)
        while not self.is_trading_day(dt.strftime("%Y%m%d")):
            dt += timedelta(days=1)
        return dt.strftime("%Y%m%d")

    def prev_trading_day(self, date: str) -> str:
        """이전 거래일을 반환한다.

        Args:
            date: 기준 날짜 (YYYYMMDD).

        Returns:
            이전 거래일 문자열 (YYYYMMDD).
        """
        dt = self._parse(date) - timedelta(days=1)
        while not self.is_trading_day(dt.strftime("%Y%m%d")):
            dt -= timedelta(days=1)
        return dt.strftime("%Y%m%d")

    def trading_days_between(self, start: str, end: str) -> list[str]:
        """구간 내 거래일 목록을 반환한다.

        Args:
            start: 시작일 (YYYYMMDD, 포함).
            end: 종료일 (YYYYMMDD, 포함).

        Returns:
            거래일 문자열 리스트.
        """
        result = []
        dt = self._parse(start)
        end_dt = self._parse(end)
        while dt <= end_dt:
            date_str = dt.strftime("%Y%m%d")
            if self.is_trading_day(date_str):
                result.append(date_str)
            dt += timedelta(days=1)
        return result

    def _is_holiday(self, dt: datetime) -> bool:
        """공휴일 여부를 확인한다."""
        md = (dt.month, dt.day)
        if md in _FIXED_HOLIDAYS:
            return True
        year_holidays = _VARIABLE_HOLIDAYS.get(dt.year, set())
        return md in year_holidays

    @staticmethod
    def _parse(date: str) -> datetime:
        """YYYYMMDD 문자열을 datetime으로 변환한다."""
        return datetime.strptime(date, "%Y%m%d")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/trading/core/test_calendar.py -v`
Expected: 10 passed

- [ ] **Step 5: Commit**

```bash
git add alphapulse/trading/core/calendar.py tests/trading/core/test_calendar.py
git commit -m "feat(trading): add KRX market calendar"
```

---

## Task 4: 거래 비용 모델

**Files:**
- Create: `alphapulse/trading/core/cost_model.py`
- Test: `tests/trading/core/test_cost_model.py`

- [ ] **Step 1: Write failing test**

`tests/trading/core/test_cost_model.py`:
```python
"""거래 비용 모델 테스트."""

import pytest

from alphapulse.trading.core.cost_model import CostModel
from alphapulse.trading.core.models import Order, Stock


@pytest.fixture
def model():
    return CostModel()


@pytest.fixture
def samsung():
    return Stock(code="005930", name="삼성전자", market="KOSPI")


@pytest.fixture
def kodex200():
    return Stock(code="069500", name="KODEX 200", market="ETF")


class TestCommission:
    def test_default_rate(self, model):
        """기본 수수료율 0.015%."""
        assert model.calculate_commission(10_000_000) == pytest.approx(1500)

    def test_custom_rate(self):
        model = CostModel(commission_rate=0.0003)
        assert model.calculate_commission(10_000_000) == pytest.approx(3000)


class TestTax:
    def test_stock_sell_tax(self, model):
        """주식 매도세 0.18%."""
        assert model.calculate_tax(10_000_000, is_etf=False) == pytest.approx(18000)

    def test_etf_no_tax(self, model):
        """ETF는 매도세 면제."""
        assert model.calculate_tax(10_000_000, is_etf=True) == 0


class TestSlippage:
    def test_no_slippage_model(self):
        model = CostModel(slippage_model="none")
        order = Order(stock=Stock(code="005930", name="삼성전자", market="KOSPI"),
                       side="BUY", order_type="MARKET", quantity=100,
                       price=72000, strategy_id="test")
        assert model.estimate_slippage(order, avg_volume=1_000_000) == 0.0

    def test_small_order_no_slippage(self, model, samsung):
        """거래대금 1% 미만 → 슬리피지 0."""
        order = Order(stock=samsung, side="BUY", order_type="MARKET",
                       quantity=10, price=72000, strategy_id="test")
        # 주문: 720,000원 / 일평균: 72,000,000,000원 < 1%
        result = model.estimate_slippage(order, avg_volume=1_000_000)
        assert result == 0.0

    def test_medium_order_slippage(self, model, samsung):
        """거래대금 1~5% → 0.1% 슬리피지."""
        order = Order(stock=samsung, side="BUY", order_type="MARKET",
                       quantity=20_000, price=72000, strategy_id="test")
        # 주문: 1,440,000,000원 / 일평균: 72,000,000,000원 = 2%
        result = model.estimate_slippage(order, avg_volume=1_000_000)
        assert result == 0.001

    def test_large_order_slippage(self, model, samsung):
        """거래대금 5%+ → 0.3% 슬리피지."""
        order = Order(stock=samsung, side="BUY", order_type="MARKET",
                       quantity=100_000, price=72000, strategy_id="test")
        # 주문: 7,200,000,000원 / 일평균: 72,000,000,000원 = 10%
        result = model.estimate_slippage(order, avg_volume=1_000_000)
        assert result == 0.003

    def test_zero_volume_max_slippage(self, model, samsung):
        """거래량 없으면 최대 슬리피지."""
        order = Order(stock=samsung, side="BUY", order_type="MARKET",
                       quantity=100, price=72000, strategy_id="test")
        result = model.estimate_slippage(order, avg_volume=0)
        assert result == 0.003


class TestTotalCost:
    def test_buy_order(self, model, samsung):
        """매수 → 수수료만, 세금 없음."""
        order = Order(stock=samsung, side="BUY", order_type="MARKET",
                       quantity=100, price=72000, strategy_id="test")
        cost = model.total_cost(order, filled_price=72000,
                                 is_etf=False, avg_volume=1_000_000)
        assert cost["commission"] == pytest.approx(1080)  # 7,200,000 * 0.00015
        assert cost["tax"] == 0

    def test_sell_stock(self, model, samsung):
        """주식 매도 → 수수료 + 세금."""
        order = Order(stock=samsung, side="SELL", order_type="MARKET",
                       quantity=100, price=72000, strategy_id="test")
        cost = model.total_cost(order, filled_price=72000,
                                 is_etf=False, avg_volume=1_000_000)
        assert cost["commission"] == pytest.approx(1080)
        assert cost["tax"] == pytest.approx(12960)  # 7,200,000 * 0.0018

    def test_sell_etf_no_tax(self, model, kodex200):
        """ETF 매도 → 수수료만, 세금 면제."""
        order = Order(stock=kodex200, side="SELL", order_type="MARKET",
                       quantity=100, price=35000, strategy_id="test")
        cost = model.total_cost(order, filled_price=35000,
                                 is_etf=True, avg_volume=500_000)
        assert cost["tax"] == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/trading/core/test_cost_model.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement cost model**

`alphapulse/trading/core/cost_model.py`:
```python
"""거래 비용 모델.

수수료, 세금, 슬리피지를 계산한다. 백테스트/Paper/실매매 모두 동일 모델을 사용한다.
"""

from dataclasses import dataclass

from alphapulse.trading.core.models import Order


@dataclass
class CostModel:
    """거래 비용 모델.

    Attributes:
        commission_rate: 수수료율 (매수+매도 양방향). 기본 0.015%.
        tax_rate_stock: 주식 매도세. 기본 0.18%.
        tax_rate_etf: ETF 매도세. 기본 0% (면제).
        slippage_model: 슬리피지 모델 ("volume_based" | "fixed" | "none").
    """
    commission_rate: float = 0.00015
    tax_rate_stock: float = 0.0018
    tax_rate_etf: float = 0.0
    slippage_model: str = "volume_based"

    def calculate_commission(self, amount: float) -> float:
        """수수료를 계산한다.

        Args:
            amount: 거래 금액 (원).

        Returns:
            수수료 (원).
        """
        return amount * self.commission_rate

    def calculate_tax(self, amount: float, is_etf: bool) -> float:
        """매도세를 계산한다.

        Args:
            amount: 거래 금액 (원).
            is_etf: ETF 여부.

        Returns:
            세금 (원). ETF는 0.
        """
        rate = self.tax_rate_etf if is_etf else self.tax_rate_stock
        return amount * rate

    def estimate_slippage(self, order: Order, avg_volume: int) -> float:
        """체결가 대비 예상 슬리피지를 추정한다.

        거래대금 대비 주문량 비율로 시장 충격(market impact)을 추정한다.

        Args:
            order: 주문.
            avg_volume: 일평균 거래량 (주).

        Returns:
            슬리피지 비율 (0.001 = 0.1%).
        """
        if self.slippage_model == "none":
            return 0.0
        if self.slippage_model == "fixed":
            return 0.001

        price = order.price or 0
        order_amount = order.quantity * price
        avg_daily_amount = avg_volume * price
        if avg_daily_amount == 0:
            return 0.003

        impact_ratio = order_amount / avg_daily_amount
        if impact_ratio < 0.01:
            return 0.0
        elif impact_ratio < 0.05:
            return 0.001
        else:
            return 0.003

    def total_cost(self, order: Order, filled_price: float,
                   is_etf: bool, avg_volume: int) -> dict:
        """주문 총 비용을 계산한다.

        Args:
            order: 주문.
            filled_price: 체결가 (원).
            is_etf: ETF 여부.
            avg_volume: 일평균 거래량 (주).

        Returns:
            {"commission": float, "tax": float, "slippage": float}.
        """
        amount = order.quantity * filled_price
        return {
            "commission": self.calculate_commission(amount),
            "tax": self.calculate_tax(amount, is_etf) if order.side == "SELL" else 0,
            "slippage": self.estimate_slippage(order, avg_volume),
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/trading/core/test_cost_model.py -v`
Expected: 9 passed

- [ ] **Step 5: Commit**

```bash
git add alphapulse/trading/core/cost_model.py tests/trading/core/test_cost_model.py
git commit -m "feat(trading): add cost model (commission, tax, slippage)"
```

---

## Task 5: 감사 추적 로거

**Files:**
- Create: `alphapulse/trading/core/audit.py`
- Test: `tests/trading/core/test_audit.py`

- [ ] **Step 1: Write failing test**

`tests/trading/core/test_audit.py`:
```python
"""감사 추적 로거 테스트."""

import json

import pytest

from alphapulse.trading.core.audit import AuditLogger
from alphapulse.trading.core.enums import TradingMode


@pytest.fixture
def audit(tmp_path):
    return AuditLogger(db_path=tmp_path / "test_audit.db")


class TestAuditLogger:
    def test_log_and_query(self, audit):
        """이벤트를 기록하고 조회한다."""
        audit.log("signal", "momentum_strategy",
                   {"stock": "005930", "score": 75},
                   mode=TradingMode.BACKTEST)

        results = audit.query()
        assert len(results) == 1
        assert results[0]["event_type"] == "signal"
        assert results[0]["component"] == "momentum_strategy"
        data = json.loads(results[0]["data"])
        assert data["stock"] == "005930"

    def test_query_by_event_type(self, audit):
        """이벤트 유형으로 필터링한다."""
        audit.log("signal", "comp1", {"a": 1}, mode=TradingMode.PAPER)
        audit.log("order", "comp2", {"b": 2}, mode=TradingMode.PAPER)
        audit.log("signal", "comp3", {"c": 3}, mode=TradingMode.PAPER)

        signals = audit.query(event_type="signal")
        assert len(signals) == 2

        orders = audit.query(event_type="order")
        assert len(orders) == 1

    def test_query_by_date_range(self, audit):
        """날짜 범위로 필터링한다."""
        audit.log("signal", "comp1", {"a": 1}, mode=TradingMode.LIVE)
        results = audit.query(start="20260101", end="20261231")
        assert len(results) == 1

    def test_empty_query(self, audit):
        """레코드 없으면 빈 리스트."""
        assert audit.query() == []

    def test_mode_stored(self, audit):
        """실행 모드가 저장된다."""
        audit.log("order", "broker", {"id": "123"}, mode=TradingMode.LIVE)
        results = audit.query()
        assert results[0]["mode"] == "live"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/trading/core/test_audit.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement audit logger**

`alphapulse/trading/core/audit.py`:
```python
"""감사 추적 로거.

모든 매매 의사결정(시그널, AI 판단, 리스크 결정, 주문)을 SQLite에 기록한다.
"""

import json
import sqlite3
import time
from pathlib import Path


class AuditLogger:
    """감사 추적 로거.

    Attributes:
        db_path: SQLite 데이터베이스 경로.
    """

    def __init__(self, db_path: str | Path) -> None:
        """AuditLogger를 초기화한다.

        Args:
            db_path: 데이터베이스 파일 경로.
        """
        self.db_path = str(db_path)
        self._create_table()

    def _create_table(self) -> None:
        """audit_log 테이블이 없으면 생성한다."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    event_type TEXT NOT NULL,
                    component TEXT NOT NULL,
                    data TEXT NOT NULL,
                    mode TEXT NOT NULL
                )
                """
            )

    def log(self, event_type: str, component: str,
            data: dict, mode: str) -> None:
        """이벤트를 기록한다.

        Args:
            event_type: 이벤트 유형 ("signal", "order", "risk_decision" 등).
            component: 발생 컴포넌트 ("momentum_strategy", "risk_manager" 등).
            data: 이벤트 상세 데이터 딕셔너리.
            mode: 실행 모드 ("backtest", "paper", "live").
        """
        data_json = json.dumps(data, ensure_ascii=False, default=str)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO audit_log (timestamp, event_type, component, data, mode) "
                "VALUES (?, ?, ?, ?, ?)",
                (time.time(), event_type, component, data_json, str(mode)),
            )

    def query(self, event_type: str | None = None,
              start: str | None = None,
              end: str | None = None) -> list[dict]:
        """이벤트를 조회한다.

        Args:
            event_type: 필터링할 이벤트 유형 (None이면 전체).
            start: 시작일 YYYYMMDD (None이면 제한 없음).
            end: 종료일 YYYYMMDD (None이면 제한 없음).

        Returns:
            이벤트 딕셔너리 리스트 (최신순).
        """
        conditions = []
        params: list = []

        if event_type is not None:
            conditions.append("event_type = ?")
            params.append(event_type)

        if start is not None:
            # YYYYMMDD → 해당일 00:00의 timestamp 근사
            from datetime import datetime
            start_ts = datetime.strptime(start, "%Y%m%d").timestamp()
            conditions.append("timestamp >= ?")
            params.append(start_ts)

        if end is not None:
            from datetime import datetime, timedelta
            end_ts = (datetime.strptime(end, "%Y%m%d") + timedelta(days=1)).timestamp()
            conditions.append("timestamp < ?")
            params.append(end_ts)

        where = ""
        if conditions:
            where = "WHERE " + " AND ".join(conditions)

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                f"SELECT * FROM audit_log {where} ORDER BY id DESC",
                params,
            )
            return [dict(row) for row in cursor.fetchall()]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/trading/core/test_audit.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add alphapulse/trading/core/audit.py tests/trading/core/test_audit.py
git commit -m "feat(trading): add audit logger for decision tracking"
```

---

## Task 6: Protocol 인터페이스 + 어댑터

**Files:**
- Create: `alphapulse/trading/core/interfaces.py`
- Create: `alphapulse/trading/core/adapters.py`
- Test: `tests/trading/core/test_adapters.py`

- [ ] **Step 1: Create interfaces (no test needed — Protocol definitions only)**

`alphapulse/trading/core/interfaces.py`:
```python
"""Trading 시스템 Protocol 인터페이스.

모든 서브시스템은 이 인터페이스를 통해 소통한다.
구현체 교체가 자유롭다 (예: SimBroker → KISBroker).
"""

from typing import Protocol, runtime_checkable

from alphapulse.trading.core.models import (
    OHLCV,
    Order,
    OrderResult,
    PortfolioSnapshot,
    Position,
    Signal,
    Stock,
)


@runtime_checkable
class DataProvider(Protocol):
    """종목 데이터 소스 인터페이스."""

    def get_ohlcv(self, code: str, start: str, end: str) -> list[OHLCV]:
        """일봉 데이터를 조회한다."""
        ...

    def get_financials(self, code: str) -> dict:
        """재무제표 데이터를 조회한다."""
        ...

    def get_investor_flow(self, code: str, days: int) -> dict:
        """종목별 투자자 수급을 조회한다."""
        ...

    def get_short_interest(self, code: str, days: int) -> dict:
        """공매도/신용 잔고를 조회한다."""
        ...


@runtime_checkable
class Broker(Protocol):
    """주문 집행 인터페이스."""

    def submit_order(self, order: Order) -> OrderResult:
        """주문을 제출한다."""
        ...

    def cancel_order(self, order_id: str) -> bool:
        """주문을 취소한다."""
        ...

    def get_balance(self) -> dict:
        """계좌 잔고를 조회한다."""
        ...

    def get_positions(self) -> list[Position]:
        """보유 포지션을 조회한다."""
        ...

    def get_order_status(self, order_id: str) -> OrderResult:
        """주문 상태를 조회한다."""
        ...
```

- [ ] **Step 2: Write failing test for adapters**

`tests/trading/core/test_adapters.py`:
```python
"""기존 시스템 어댑터 테스트."""

from alphapulse.trading.core.adapters import PulseResultAdapter


class TestPulseResultAdapter:
    def test_to_market_context(self):
        """SignalEngine 결과를 market_context로 변환한다."""
        pulse_result = {
            "date": "20260409",
            "score": 35.2,
            "signal": "매수 우위 (Moderately Bullish)",
            "indicator_scores": {
                "investor_flow": 42,
                "vkospi": -25,
            },
            "details": {
                "investor_flow": {"score": 42, "foreign_net": 3000},
            },
            "period": "daily",
        }

        ctx = PulseResultAdapter.to_market_context(pulse_result)

        assert ctx["date"] == "20260409"
        assert ctx["pulse_score"] == 35.2
        assert ctx["pulse_signal"] == "매수 우위 (Moderately Bullish)"
        assert ctx["indicator_scores"]["investor_flow"] == 42
        assert "details" in ctx

    def test_to_feedback_context(self):
        """피드백 평가 결과를 문자열로 변환한다."""
        hit_rates = {
            "hit_rate_1d": 0.65,
            "hit_rate_3d": 0.60,
            "hit_rate_5d": 0.58,
            "total_evaluated": 20,
        }

        result = PulseResultAdapter.to_feedback_context(hit_rates, correlation=0.42)

        assert "65.0%" in result
        assert "0.42" in result
        assert "20건" in result

    def test_to_feedback_context_insufficient_data(self):
        """평가 데이터 부족 시 안내 문자열."""
        hit_rates = {"total_evaluated": 0}
        result = PulseResultAdapter.to_feedback_context(hit_rates, correlation=None)
        assert "부족" in result or "없" in result
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/trading/core/test_adapters.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 4: Implement adapters**

`alphapulse/trading/core/adapters.py`:
```python
"""기존 AlphaPulse 시스템 → Trading 데이터 모델 변환 어댑터."""


class PulseResultAdapter:
    """기존 SignalEngine dict → trading 데이터 모델 변환."""

    @staticmethod
    def to_market_context(pulse_result: dict) -> dict:
        """SignalEngine.run() 결과를 전략이 소비하는 형태로 변환한다.

        Args:
            pulse_result: SignalEngine.run() 반환 딕셔너리.

        Returns:
            market_context 딕셔너리.
        """
        return {
            "date": pulse_result["date"],
            "pulse_score": pulse_result["score"],
            "pulse_signal": pulse_result["signal"],
            "indicator_scores": pulse_result["indicator_scores"],
            "details": pulse_result.get("details", {}),
        }

    @staticmethod
    def to_feedback_context(hit_rates: dict,
                            correlation: float | None) -> str:
        """FeedbackEvaluator 결과를 AI 입력 문자열로 변환한다.

        Args:
            hit_rates: 적중률 딕셔너리 (hit_rate_1d, total_evaluated 등).
            correlation: 시그널-수익률 상관계수.

        Returns:
            AI 프롬프트에 주입할 피드백 컨텍스트 문자열.
        """
        total = hit_rates.get("total_evaluated", 0)
        if total < 5:
            return "피드백 데이터가 부족합니다 (5건 미만). 정량 시그널 기반으로 판단하세요."

        rate_1d = hit_rates.get("hit_rate_1d", 0)
        rate_3d = hit_rates.get("hit_rate_3d", 0)
        rate_5d = hit_rates.get("hit_rate_5d", 0)
        corr_str = f"{correlation:.2f}" if correlation is not None else "N/A"

        return (
            f"과거 시그널 성과 ({total}건 평가): "
            f"1일 적중률 {rate_1d * 100:.1f}%, "
            f"3일 {rate_3d * 100:.1f}%, "
            f"5일 {rate_5d * 100:.1f}%. "
            f"시그널-수익률 상관계수: {corr_str}."
        )
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/trading/core/test_adapters.py -v`
Expected: 3 passed

- [ ] **Step 6: Commit**

```bash
git add alphapulse/trading/core/interfaces.py alphapulse/trading/core/adapters.py tests/trading/core/test_adapters.py
git commit -m "feat(trading): add Protocol interfaces + PulseResult adapter"
```

---

## Task 7: 종목 데이터 저장소

**Files:**
- Create: `alphapulse/trading/data/__init__.py`
- Create: `alphapulse/trading/data/store.py`
- Test: `tests/trading/data/test_store.py`

- [ ] **Step 1: Write failing test**

`tests/trading/data/test_store.py`:
```python
"""종목 데이터 저장소 테스트."""

import pytest

from alphapulse.trading.data.store import TradingStore


@pytest.fixture
def store(tmp_path):
    return TradingStore(tmp_path / "test_trading.db")


class TestStocks:
    def test_upsert_and_get_stock(self, store):
        store.upsert_stock("005930", "삼성전자", "KOSPI", "반도체", 430e12)
        stock = store.get_stock("005930")
        assert stock is not None
        assert stock["name"] == "삼성전자"
        assert stock["market"] == "KOSPI"

    def test_get_missing_stock(self, store):
        assert store.get_stock("999999") is None

    def test_get_all_stocks(self, store):
        store.upsert_stock("005930", "삼성전자", "KOSPI", "반도체", 430e12)
        store.upsert_stock("000660", "SK하이닉스", "KOSPI", "반도체", 120e12)
        stocks = store.get_all_stocks(market="KOSPI")
        assert len(stocks) == 2


class TestOHLCV:
    def test_save_and_get_ohlcv(self, store):
        rows = [
            ("005930", "20260409", 72000, 73000, 71500, 72500, 10_000_000, 430e12),
            ("005930", "20260410", 72500, 74000, 72000, 73500, 12_000_000, 435e12),
        ]
        store.save_ohlcv_bulk(rows)

        result = store.get_ohlcv("005930", "20260409", "20260410")
        assert len(result) == 2
        assert result[0]["close"] == 72500
        assert result[1]["close"] == 73500

    def test_get_ohlcv_empty(self, store):
        result = store.get_ohlcv("005930", "20260409", "20260410")
        assert result == []


class TestFundamentals:
    def test_save_and_get(self, store):
        store.save_fundamental("005930", "20260331", per=12.5, pbr=1.3,
                                roe=15.2, revenue=300e12, operating_profit=50e12,
                                net_income=40e12, debt_ratio=35.0,
                                dividend_yield=2.1)
        result = store.get_fundamentals("005930")
        assert result is not None
        assert result["per"] == 12.5
        assert result["roe"] == 15.2


class TestInvestorFlow:
    def test_save_and_get(self, store):
        rows = [
            ("005930", "20260409", 50e9, 30e9, -80e9, 55.2),
            ("005930", "20260410", -20e9, 10e9, 10e9, 55.0),
        ]
        store.save_investor_flow_bulk(rows)

        result = store.get_investor_flow("005930", days=2)
        assert len(result) == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/trading/data/test_store.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement store**

`alphapulse/trading/data/__init__.py`:
```python
"""종목 데이터 수집 및 저장."""
```

`alphapulse/trading/data/store.py`:
```python
"""종목 데이터 SQLite 저장소.

OHLCV, 재무제표, 수급, 공매도 데이터를 trading.db에 저장한다.
"""

import json
import sqlite3
import time
from pathlib import Path


class TradingStore:
    """종목 데이터 저장소.

    Attributes:
        db_path: SQLite 데이터베이스 경로.
    """

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = str(db_path)
        self._create_tables()

    def _create_tables(self) -> None:
        """필요한 테이블을 모두 생성한다."""
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS stocks (
                    code TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    market TEXT NOT NULL,
                    sector TEXT DEFAULT '',
                    market_cap REAL DEFAULT 0,
                    is_tradable INTEGER DEFAULT 1,
                    updated_at REAL
                );

                CREATE TABLE IF NOT EXISTS ohlcv (
                    code TEXT NOT NULL,
                    date TEXT NOT NULL,
                    open REAL, high REAL, low REAL, close REAL,
                    volume INTEGER,
                    market_cap REAL DEFAULT 0,
                    PRIMARY KEY (code, date)
                );

                CREATE TABLE IF NOT EXISTS fundamentals (
                    code TEXT NOT NULL,
                    date TEXT NOT NULL,
                    per REAL, pbr REAL, roe REAL,
                    revenue REAL, operating_profit REAL,
                    net_income REAL, debt_ratio REAL,
                    dividend_yield REAL,
                    PRIMARY KEY (code, date)
                );

                CREATE TABLE IF NOT EXISTS stock_investor_flow (
                    code TEXT NOT NULL,
                    date TEXT NOT NULL,
                    foreign_net REAL,
                    institutional_net REAL,
                    individual_net REAL,
                    foreign_holding_pct REAL,
                    PRIMARY KEY (code, date)
                );

                CREATE TABLE IF NOT EXISTS short_interest (
                    code TEXT NOT NULL,
                    date TEXT NOT NULL,
                    short_volume INTEGER,
                    short_balance INTEGER,
                    short_ratio REAL,
                    credit_balance REAL,
                    lending_balance REAL,
                    PRIMARY KEY (code, date)
                );

                CREATE TABLE IF NOT EXISTS etf_info (
                    code TEXT PRIMARY KEY,
                    name TEXT,
                    category TEXT,
                    underlying TEXT,
                    expense_ratio REAL,
                    nav REAL,
                    updated_at REAL
                );
                """
            )

    # ── Stocks ─────────────────────────────────────────────────────

    def upsert_stock(self, code: str, name: str, market: str,
                     sector: str = "", market_cap: float = 0) -> None:
        """종목 정보를 저장(upsert)한다."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO stocks (code, name, market, sector, market_cap, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(code) DO UPDATE SET
                    name=excluded.name, market=excluded.market,
                    sector=excluded.sector, market_cap=excluded.market_cap,
                    updated_at=excluded.updated_at
                """,
                (code, name, market, sector, market_cap, time.time()),
            )

    def get_stock(self, code: str) -> dict | None:
        """종목 정보를 조회한다."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM stocks WHERE code = ?", (code,)
            ).fetchone()
        return dict(row) if row else None

    def get_all_stocks(self, market: str | None = None) -> list[dict]:
        """전체 종목 목록을 조회한다."""
        query = "SELECT * FROM stocks WHERE is_tradable = 1"
        params: list = []
        if market:
            query += " AND market = ?"
            params.append(market)
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]

    # ── OHLCV ──────────────────────────────────────────────────────

    def save_ohlcv_bulk(self, rows: list[tuple]) -> None:
        """OHLCV 데이터를 대량 저장한다.

        Args:
            rows: (code, date, open, high, low, close, volume, market_cap) 튜플 리스트.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.executemany(
                """
                INSERT OR REPLACE INTO ohlcv
                    (code, date, open, high, low, close, volume, market_cap)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )

    def get_ohlcv(self, code: str, start: str, end: str) -> list[dict]:
        """OHLCV 데이터를 조회한다."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM ohlcv WHERE code = ? AND date BETWEEN ? AND ? ORDER BY date",
                (code, start, end),
            ).fetchall()
        return [dict(r) for r in rows]

    # ── Fundamentals ───────────────────────────────────────────────

    def save_fundamental(self, code: str, date: str, **kwargs) -> None:
        """재무제표 데이터를 저장한다."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO fundamentals
                    (code, date, per, pbr, roe, revenue, operating_profit,
                     net_income, debt_ratio, dividend_yield)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (code, date,
                 kwargs.get("per"), kwargs.get("pbr"), kwargs.get("roe"),
                 kwargs.get("revenue"), kwargs.get("operating_profit"),
                 kwargs.get("net_income"), kwargs.get("debt_ratio"),
                 kwargs.get("dividend_yield")),
            )

    def get_fundamentals(self, code: str) -> dict | None:
        """가장 최근 재무제표를 조회한다."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM fundamentals WHERE code = ? ORDER BY date DESC LIMIT 1",
                (code,),
            ).fetchone()
        return dict(row) if row else None

    # ── Investor Flow ──────────────────────────────────────────────

    def save_investor_flow_bulk(self, rows: list[tuple]) -> None:
        """종목별 수급 데이터를 대량 저장한다.

        Args:
            rows: (code, date, foreign_net, institutional_net,
                   individual_net, foreign_holding_pct) 튜플 리스트.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.executemany(
                """
                INSERT OR REPLACE INTO stock_investor_flow
                    (code, date, foreign_net, institutional_net,
                     individual_net, foreign_holding_pct)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                rows,
            )

    def get_investor_flow(self, code: str, days: int = 20) -> list[dict]:
        """종목별 수급 데이터를 조회한다."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM stock_investor_flow "
                "WHERE code = ? ORDER BY date DESC LIMIT ?",
                (code, days),
            ).fetchall()
        return [dict(r) for r in rows]

    # ── Short Interest ─────────────────────────────────────────────

    def save_short_interest_bulk(self, rows: list[tuple]) -> None:
        """공매도/신용 데이터를 대량 저장한다.

        Args:
            rows: (code, date, short_volume, short_balance,
                   short_ratio, credit_balance, lending_balance) 튜플 리스트.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.executemany(
                """
                INSERT OR REPLACE INTO short_interest
                    (code, date, short_volume, short_balance,
                     short_ratio, credit_balance, lending_balance)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )

    def get_short_interest(self, code: str, days: int = 20) -> list[dict]:
        """공매도/신용 데이터를 조회한다."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM short_interest "
                "WHERE code = ? ORDER BY date DESC LIMIT ?",
                (code, days),
            ).fetchall()
        return [dict(r) for r in rows]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/trading/data/test_store.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add alphapulse/trading/data/ tests/trading/data/
git commit -m "feat(trading): add TradingStore with OHLCV, fundamentals, flow tables"
```

---

## Task 8: 주가 수집기 (OHLCV + 시가총액)

**Files:**
- Create: `alphapulse/trading/data/stock_collector.py`
- Test: `tests/trading/data/test_stock_collector.py`

- [ ] **Step 1: Write failing test**

`tests/trading/data/test_stock_collector.py`:
```python
"""주가 수집기 테스트."""

import pandas as pd
import pytest
from unittest.mock import patch, MagicMock

from alphapulse.trading.data.stock_collector import StockCollector


@pytest.fixture
def collector(tmp_path):
    return StockCollector(db_path=tmp_path / "test.db")


@pytest.fixture
def sample_ohlcv_df():
    """pykrx가 반환하는 OHLCV DataFrame 형식."""
    return pd.DataFrame({
        "시가": [72000, 72500],
        "고가": [73000, 74000],
        "저가": [71500, 72000],
        "종가": [72500, 73500],
        "거래량": [10_000_000, 12_000_000],
    }, index=pd.to_datetime(["2026-04-09", "2026-04-10"]))


@pytest.fixture
def sample_cap_df():
    """pykrx가 반환하는 시가총액 DataFrame."""
    return pd.DataFrame({
        "시가총액": [430_000_000_000_000, 435_000_000_000_000],
        "상장주식수": [5_969_782_550, 5_969_782_550],
    }, index=pd.to_datetime(["2026-04-09", "2026-04-10"]))


class TestStockCollector:
    @patch("alphapulse.trading.data.stock_collector.stock")
    def test_collect_ohlcv(self, mock_stock, collector,
                            sample_ohlcv_df, sample_cap_df):
        """OHLCV + 시가총액을 수집하여 DB에 저장한다."""
        mock_stock.get_market_ohlcv.return_value = sample_ohlcv_df
        mock_stock.get_market_cap.return_value = sample_cap_df

        collector.collect_ohlcv("005930", "20260409", "20260410")

        result = collector.store.get_ohlcv("005930", "20260409", "20260410")
        assert len(result) == 2
        assert result[0]["close"] == 72500
        assert result[0]["market_cap"] == 430_000_000_000_000

    @patch("alphapulse.trading.data.stock_collector.stock")
    def test_collect_ohlcv_empty(self, mock_stock, collector):
        """데이터가 없으면 저장하지 않는다."""
        mock_stock.get_market_ohlcv.return_value = pd.DataFrame()
        mock_stock.get_market_cap.return_value = pd.DataFrame()

        collector.collect_ohlcv("005930", "20260409", "20260410")

        result = collector.store.get_ohlcv("005930", "20260409", "20260410")
        assert result == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/trading/data/test_stock_collector.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement stock collector**

`alphapulse/trading/data/stock_collector.py`:
```python
"""주가 수집기.

pykrx를 사용하여 종목별 OHLCV 및 시가총액을 수집한다.
"""

import logging
from pathlib import Path

from pykrx import stock

from alphapulse.trading.data.store import TradingStore

logger = logging.getLogger(__name__)


class StockCollector:
    """종목별 주가 데이터 수집기.

    Attributes:
        store: TradingStore 인스턴스.
    """

    def __init__(self, db_path: str | Path) -> None:
        self.store = TradingStore(db_path)

    def collect_ohlcv(self, code: str, start: str, end: str) -> None:
        """OHLCV + 시가총액을 수집하여 DB에 저장한다.

        Args:
            code: 종목코드 (예: "005930").
            start: 시작일 (YYYYMMDD).
            end: 종료일 (YYYYMMDD).
        """
        try:
            ohlcv_df = stock.get_market_ohlcv(start, end, code)
            cap_df = stock.get_market_cap(start, end, code)
        except Exception:
            logger.warning("OHLCV 수집 실패: %s (%s~%s)", code, start, end)
            return

        if ohlcv_df.empty:
            return

        rows = []
        for dt in ohlcv_df.index:
            date_str = dt.strftime("%Y%m%d")
            o = ohlcv_df.loc[dt]
            mcap = 0
            if not cap_df.empty and dt in cap_df.index:
                mcap = cap_df.loc[dt].get("시가총액", 0)
            rows.append((
                code, date_str,
                float(o["시가"]), float(o["고가"]),
                float(o["저가"]), float(o["종가"]),
                int(o["거래량"]), float(mcap),
            ))

        if rows:
            self.store.save_ohlcv_bulk(rows)
            logger.info("OHLCV 저장: %s (%d건)", code, len(rows))

    def collect_stock_list(self, date: str, market: str = "KOSPI") -> list[dict]:
        """특정 시장의 전 종목 목록을 수집하여 DB에 저장한다.

        Args:
            date: 기준일 (YYYYMMDD).
            market: 시장 ("KOSPI" | "KOSDAQ").

        Returns:
            종목 정보 딕셔너리 리스트.
        """
        try:
            tickers = stock.get_market_ticker_list(date, market=market)
        except Exception:
            logger.warning("종목 목록 수집 실패: %s %s", market, date)
            return []

        results = []
        for ticker in tickers:
            name = stock.get_market_ticker_name(ticker)
            self.store.upsert_stock(ticker, name, market)
            results.append({"code": ticker, "name": name, "market": market})

        logger.info("%s 종목 %d개 저장", market, len(results))
        return results
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/trading/data/test_stock_collector.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add alphapulse/trading/data/stock_collector.py tests/trading/data/test_stock_collector.py
git commit -m "feat(trading): add StockCollector for OHLCV + market cap"
```

---

## Task 9: 재무제표 수집기

**Files:**
- Create: `alphapulse/trading/data/fundamental_collector.py`
- Test: `tests/trading/data/test_fundamental_collector.py`

- [ ] **Step 1: Write failing test**

`tests/trading/data/test_fundamental_collector.py`:
```python
"""재무제표 수집기 테스트."""

import pandas as pd
import pytest
from unittest.mock import patch

from alphapulse.trading.data.fundamental_collector import FundamentalCollector


@pytest.fixture
def collector(tmp_path):
    return FundamentalCollector(db_path=tmp_path / "test.db")


@pytest.fixture
def sample_fundamental_df():
    """pykrx가 반환하는 펀더멘털 DataFrame."""
    return pd.DataFrame({
        "BPS": [65000],
        "PER": [12.5],
        "PBR": [1.3],
        "EPS": [5800],
        "DIV": [2.1],
        "DPS": [1500],
    }, index=["005930"])


class TestFundamentalCollector:
    @patch("alphapulse.trading.data.fundamental_collector.stock")
    def test_collect_fundamentals(self, mock_stock, collector,
                                    sample_fundamental_df):
        """PER/PBR/배당수익률을 수집하여 DB에 저장한다."""
        mock_stock.get_market_fundamental_by_ticker.return_value = sample_fundamental_df

        collector.collect("20260409", codes=["005930"])

        result = collector.store.get_fundamentals("005930")
        assert result is not None
        assert result["per"] == 12.5
        assert result["pbr"] == 1.3
        assert result["dividend_yield"] == 2.1

    @patch("alphapulse.trading.data.fundamental_collector.stock")
    def test_collect_empty(self, mock_stock, collector):
        """데이터가 없으면 저장하지 않는다."""
        mock_stock.get_market_fundamental_by_ticker.return_value = pd.DataFrame()

        collector.collect("20260409", codes=["005930"])

        assert collector.store.get_fundamentals("005930") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/trading/data/test_fundamental_collector.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement fundamental collector**

`alphapulse/trading/data/fundamental_collector.py`:
```python
"""재무제표 수집기.

pykrx를 사용하여 PER, PBR, 배당수익률 등을 수집한다.
ROE/매출/영업이익은 pykrx로 직접 제공되지 않으므로 추후 소스 확장 필요.
"""

import logging
from pathlib import Path

from pykrx import stock

from alphapulse.trading.data.store import TradingStore

logger = logging.getLogger(__name__)


class FundamentalCollector:
    """재무제표 데이터 수집기.

    Attributes:
        store: TradingStore 인스턴스.
    """

    def __init__(self, db_path: str | Path) -> None:
        self.store = TradingStore(db_path)

    def collect(self, date: str, codes: list[str] | None = None,
                market: str = "KOSPI") -> None:
        """PER/PBR/배당수익률을 수집하여 DB에 저장한다.

        Args:
            date: 기준일 (YYYYMMDD).
            codes: 종목코드 리스트 (None이면 전 시장).
            market: 시장 (codes=None일 때 사용).
        """
        try:
            df = stock.get_market_fundamental_by_ticker(date, market=market)
        except Exception:
            logger.warning("재무제표 수집 실패: %s %s", market, date)
            return

        if df.empty:
            return

        target_codes = codes if codes else df.index.tolist()

        for code in target_codes:
            if code not in df.index:
                continue
            row = df.loc[code]
            per = float(row.get("PER", 0)) or None
            pbr = float(row.get("PBR", 0)) or None
            div_yield = float(row.get("DIV", 0)) or None

            self.store.save_fundamental(
                code=code,
                date=date,
                per=per,
                pbr=pbr,
                dividend_yield=div_yield,
            )

        logger.info("재무제표 저장: %d종목 (%s)", len(target_codes), date)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/trading/data/test_fundamental_collector.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add alphapulse/trading/data/fundamental_collector.py tests/trading/data/test_fundamental_collector.py
git commit -m "feat(trading): add FundamentalCollector for PER/PBR/dividend"
```

---

## Task 10: 수급 + 공매도 수집기

**Files:**
- Create: `alphapulse/trading/data/flow_collector.py`
- Create: `alphapulse/trading/data/short_collector.py`
- Test: `tests/trading/data/test_flow_collector.py`
- Test: `tests/trading/data/test_short_collector.py`

- [ ] **Step 1: Write failing tests**

`tests/trading/data/test_flow_collector.py`:
```python
"""종목별 수급 수집기 테스트."""

import pandas as pd
import pytest
from unittest.mock import patch

from alphapulse.trading.data.flow_collector import FlowCollector


@pytest.fixture
def collector(tmp_path):
    return FlowCollector(db_path=tmp_path / "test.db")


@pytest.fixture
def sample_trading_df():
    """pykrx 종목별 거래실적 DataFrame."""
    return pd.DataFrame({
        "기관합계": [50e9, -30e9],
        "기타법인": [5e9, -2e9],
        "개인": [-80e9, 50e9],
        "외국인합계": [25e9, -18e9],
    }, index=pd.to_datetime(["2026-04-09", "2026-04-10"]))


class TestFlowCollector:
    @patch("alphapulse.trading.data.flow_collector.stock")
    def test_collect(self, mock_stock, collector, sample_trading_df):
        """종목별 수급을 수집하여 DB에 저장한다."""
        mock_stock.get_market_trading_value_by_date.return_value = sample_trading_df

        collector.collect("005930", "20260409", "20260410")

        result = collector.store.get_investor_flow("005930", days=2)
        assert len(result) == 2
        assert result[0]["foreign_net"] == -18e9  # DESC 정렬 (최근순)

    @patch("alphapulse.trading.data.flow_collector.stock")
    def test_collect_empty(self, mock_stock, collector):
        mock_stock.get_market_trading_value_by_date.return_value = pd.DataFrame()
        collector.collect("005930", "20260409", "20260410")
        assert collector.store.get_investor_flow("005930") == []
```

`tests/trading/data/test_short_collector.py`:
```python
"""공매도/신용 수집기 테스트."""

import pytest

from alphapulse.trading.data.short_collector import ShortCollector


@pytest.fixture
def collector(tmp_path):
    return ShortCollector(db_path=tmp_path / "test.db")


class TestShortCollector:
    def test_save_and_get(self, collector):
        """수동 저장 + 조회 테스트 (스크래퍼 구현 전)."""
        collector.store.save_short_interest_bulk([
            ("005930", "20260409", 500_000, 10_000_000, 0.5, 100e9, 5_000_000),
        ])

        result = collector.store.get_short_interest("005930", days=1)
        assert len(result) == 1
        assert result[0]["short_ratio"] == 0.5
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/trading/data/test_flow_collector.py tests/trading/data/test_short_collector.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement collectors**

`alphapulse/trading/data/flow_collector.py`:
```python
"""종목별 투자자 수급 수집기.

pykrx를 사용하여 외국인/기관/개인 순매수를 수집한다.
"""

import logging
from pathlib import Path

from pykrx import stock

from alphapulse.trading.data.store import TradingStore

logger = logging.getLogger(__name__)


class FlowCollector:
    """종목별 수급 수집기.

    Attributes:
        store: TradingStore 인스턴스.
    """

    def __init__(self, db_path: str | Path) -> None:
        self.store = TradingStore(db_path)

    def collect(self, code: str, start: str, end: str) -> None:
        """종목별 투자자 수급을 수집하여 DB에 저장한다.

        Args:
            code: 종목코드.
            start: 시작일 (YYYYMMDD).
            end: 종료일 (YYYYMMDD).
        """
        try:
            df = stock.get_market_trading_value_by_date(start, end, code)
        except Exception:
            logger.warning("수급 수집 실패: %s (%s~%s)", code, start, end)
            return

        if df.empty:
            return

        rows = []
        for dt in df.index:
            date_str = dt.strftime("%Y%m%d")
            row = df.loc[dt]
            rows.append((
                code, date_str,
                float(row.get("외국인합계", 0)),
                float(row.get("기관합계", 0)),
                float(row.get("개인", 0)),
                None,  # foreign_holding_pct — 별도 API 필요
            ))

        if rows:
            self.store.save_investor_flow_bulk(rows)
            logger.info("수급 저장: %s (%d건)", code, len(rows))
```

`alphapulse/trading/data/short_collector.py`:
```python
"""공매도/신용잔고 수집기.

현재는 저장소 인터페이스만 제공한다.
실제 데이터 수집은 KRX/네이버 스크래퍼 구현 후 추가한다.
데이터 소스 검증 프로토콜에 따라 구현 단계에서 소스를 확정한다.
"""

import logging
from pathlib import Path

from alphapulse.trading.data.store import TradingStore

logger = logging.getLogger(__name__)


class ShortCollector:
    """공매도/신용잔고 수집기.

    Attributes:
        store: TradingStore 인스턴스.
    """

    def __init__(self, db_path: str | Path) -> None:
        self.store = TradingStore(db_path)

    def collect(self, code: str, start: str, end: str) -> None:
        """공매도/신용잔고를 수집하여 DB에 저장한다.

        TODO: KRX 정보데이터시스템 또는 네이버 금융 스크래퍼 구현 필요.
              구현 시 데이터 소스 검증 프로토콜 준수:
              1. 1순위 소스 API 호출 테스트
              2. 반환 데이터 형식/품질 확인
              3. 실패 시 2순위 폴백

        Args:
            code: 종목코드.
            start: 시작일 (YYYYMMDD).
            end: 종료일 (YYYYMMDD).
        """
        logger.warning("공매도 수집기 미구현: %s. 데이터 소스 확정 후 구현 예정.", code)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/trading/data/test_flow_collector.py tests/trading/data/test_short_collector.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add alphapulse/trading/data/flow_collector.py alphapulse/trading/data/short_collector.py tests/trading/data/test_flow_collector.py tests/trading/data/test_short_collector.py
git commit -m "feat(trading): add FlowCollector + ShortCollector stub"
```

---

## Task 11: 투자 유니버스 관리

**Files:**
- Create: `alphapulse/trading/data/universe.py`
- Test: `tests/trading/data/test_universe.py`

- [ ] **Step 1: Write failing test**

`tests/trading/data/test_universe.py`:
```python
"""투자 유니버스 관리 테스트."""

import pytest

from alphapulse.trading.core.models import Stock
from alphapulse.trading.data.store import TradingStore
from alphapulse.trading.data.universe import Universe


@pytest.fixture
def store(tmp_path):
    s = TradingStore(tmp_path / "test.db")
    # 테스트 종목 등록
    s.upsert_stock("005930", "삼성전자", "KOSPI", "반도체", 430e12)
    s.upsert_stock("000660", "SK하이닉스", "KOSPI", "반도체", 120e12)
    s.upsert_stock("035720", "카카오", "KOSPI", "IT", 20e12)
    s.upsert_stock("069500", "KODEX 200", "ETF", "", 50e12)
    s.upsert_stock("999999", "소형주", "KOSDAQ", "기타", 5e9)  # 시총 50억
    # OHLCV (거래대금 계산용)
    s.save_ohlcv_bulk([
        ("005930", "20260409", 72000, 73000, 71500, 72500, 10_000_000, 430e12),
        ("000660", "20260409", 180000, 185000, 178000, 183000, 3_000_000, 120e12),
        ("035720", "20260409", 50000, 51000, 49500, 50500, 500_000, 20e12),
        ("069500", "20260409", 35000, 35500, 34800, 35200, 200_000, 50e12),
        ("999999", "20260409", 1000, 1050, 980, 1020, 1000, 5e9),
    ])
    return s


@pytest.fixture
def universe(store):
    return Universe(store)


class TestUniverse:
    def test_get_all(self, universe):
        """전체 종목을 Stock 리스트로 반환한다."""
        stocks = universe.get_all()
        assert len(stocks) == 5
        assert all(isinstance(s, Stock) for s in stocks)

    def test_get_by_market(self, universe):
        """시장별 종목 조회."""
        kospi = universe.get_by_market("KOSPI")
        assert len(kospi) == 3  # 삼성전자, SK하이닉스, 카카오

        etfs = universe.get_by_market("ETF")
        assert len(etfs) == 1

    def test_filter_by_market_cap(self, universe):
        """시가총액 필터링."""
        filtered = universe.filter_stocks(
            universe.get_all(),
            min_market_cap=10e12,  # 10조 이상
        )
        codes = [s.code for s in filtered]
        assert "005930" in codes
        assert "000660" in codes
        assert "999999" not in codes  # 50억 → 제외

    def test_filter_by_avg_volume(self, universe):
        """일평균 거래대금 필터링."""
        filtered = universe.filter_stocks(
            universe.get_all(),
            min_avg_volume=1e9,  # 10억 이상
        )
        codes = [s.code for s in filtered]
        assert "005930" in codes  # 7250억
        assert "999999" not in codes  # 100만원

    def test_filter_combined(self, universe):
        """복합 필터링 (시총 + 거래대금)."""
        filtered = universe.filter_stocks(
            universe.get_all(),
            min_market_cap=10e12,
            min_avg_volume=1e9,
        )
        # 삼성전자, SK하이닉스, 카카오(시총20조, 거래대금 252.5억)
        assert len(filtered) >= 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/trading/data/test_universe.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement universe**

`alphapulse/trading/data/universe.py`:
```python
"""투자 유니버스 관리.

종목 목록 조회, 필터링, Stock 변환을 담당한다.
"""

import logging

from alphapulse.trading.core.models import Stock
from alphapulse.trading.data.store import TradingStore

logger = logging.getLogger(__name__)


class Universe:
    """투자 유니버스 관리자.

    Attributes:
        store: TradingStore 인스턴스.
    """

    def __init__(self, store: TradingStore) -> None:
        self.store = store

    def get_all(self) -> list[Stock]:
        """전체 종목을 Stock 리스트로 반환한다."""
        rows = self.store.get_all_stocks()
        return [self._to_stock(r) for r in rows]

    def get_by_market(self, market: str) -> list[Stock]:
        """특정 시장 종목만 조회한다.

        Args:
            market: "KOSPI" | "KOSDAQ" | "ETF".
        """
        rows = self.store.get_all_stocks(market=market)
        return [self._to_stock(r) for r in rows]

    def filter_stocks(
        self,
        stocks: list[Stock],
        min_market_cap: float | None = None,
        min_avg_volume: float | None = None,
    ) -> list[Stock]:
        """종목을 조건에 따라 필터링한다.

        Args:
            stocks: 필터링할 종목 리스트.
            min_market_cap: 최소 시가총액 (원).
            min_avg_volume: 최소 일평균 거래대금 (원).

        Returns:
            필터 통과한 종목 리스트.
        """
        result = []
        for s in stocks:
            if min_market_cap is not None:
                info = self.store.get_stock(s.code)
                if info and info.get("market_cap", 0) < min_market_cap:
                    continue

            if min_avg_volume is not None:
                avg_vol = self._get_avg_trading_value(s.code)
                if avg_vol < min_avg_volume:
                    continue

            result.append(s)
        return result

    def _get_avg_trading_value(self, code: str, days: int = 20) -> float:
        """최근 N일 평균 거래대금을 계산한다."""
        rows = self.store.get_ohlcv(code, "00000000", "99999999")
        if not rows:
            return 0
        recent = rows[-days:]  # 날짜 오름차순
        total = sum(r["close"] * r["volume"] for r in recent)
        return total / len(recent) if recent else 0

    @staticmethod
    def _to_stock(row: dict) -> Stock:
        """DB 딕셔너리를 Stock으로 변환한다."""
        return Stock(
            code=row["code"],
            name=row["name"],
            market=row["market"],
            sector=row.get("sector", ""),
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/trading/data/test_universe.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add alphapulse/trading/data/universe.py tests/trading/data/test_universe.py
git commit -m "feat(trading): add Universe manager with market cap + volume filters"
```

---

## Task 12: 팩터 계산

**Files:**
- Create: `alphapulse/trading/screening/__init__.py`
- Create: `alphapulse/trading/screening/factors.py`
- Test: `tests/trading/screening/test_factors.py`
- Create: `tests/trading/conftest.py`

- [ ] **Step 1: Create shared test fixtures**

`tests/trading/conftest.py`:
```python
"""Trading 모듈 공유 테스트 픽스처."""

import pytest

from alphapulse.trading.data.store import TradingStore


@pytest.fixture
def trading_store(tmp_path):
    """OHLCV + 재무 + 수급 데이터가 미리 로드된 TradingStore."""
    store = TradingStore(tmp_path / "test.db")

    # 종목
    store.upsert_stock("005930", "삼성전자", "KOSPI", "반도체", 430e12)
    store.upsert_stock("000660", "SK하이닉스", "KOSPI", "반도체", 120e12)

    # OHLCV (20일치 시뮬레이션 — 삼성전자는 상승, SK하이닉스는 하락)
    samsung_prices = [70000 + i * 200 for i in range(20)]  # 70000 → 73800
    hynix_prices = [190000 - i * 300 for i in range(20)]   # 190000 → 184300
    dates = [f"202604{d:02d}" for d in range(1, 21)]

    samsung_ohlcv = []
    hynix_ohlcv = []
    for i, date in enumerate(dates):
        sp = samsung_prices[i]
        samsung_ohlcv.append(
            ("005930", date, sp - 500, sp + 500, sp - 800, sp, 10_000_000, 430e12)
        )
        hp = hynix_prices[i]
        hynix_ohlcv.append(
            ("000660", date, hp - 1000, hp + 1000, hp - 1500, hp, 3_000_000, 120e12)
        )

    store.save_ohlcv_bulk(samsung_ohlcv + hynix_ohlcv)

    # 재무제표
    store.save_fundamental("005930", "20260331", per=12.5, pbr=1.3,
                           roe=15.2, dividend_yield=2.1)
    store.save_fundamental("000660", "20260331", per=8.0, pbr=1.0,
                           roe=12.0, dividend_yield=1.5)

    # 수급 (삼성: 외국인 순매수, SK: 외국인 순매도)
    samsung_flow = [
        ("005930", date, 50e9 if i % 2 == 0 else -10e9, 20e9, -70e9, 55.0)
        for i, date in enumerate(dates)
    ]
    hynix_flow = [
        ("000660", date, -30e9, -10e9, 40e9, 30.0)
        for date in dates
    ]
    store.save_investor_flow_bulk(samsung_flow + hynix_flow)

    return store
```

- [ ] **Step 2: Write failing test for factors**

`alphapulse/trading/screening/__init__.py`:
```python
"""종목 스크리닝 및 랭킹."""
```

`tests/trading/screening/test_factors.py`:
```python
"""팩터 계산 테스트."""

import pytest

from alphapulse.trading.screening.factors import FactorCalculator


class TestMomentum:
    def test_positive_return(self, trading_store):
        """상승 종목은 양수 모멘텀."""
        calc = FactorCalculator(trading_store)
        result = calc.momentum("005930", lookback=20)
        assert result > 0  # 70000 → 73800 상승

    def test_negative_return(self, trading_store):
        """하락 종목은 음수 모멘텀."""
        calc = FactorCalculator(trading_store)
        result = calc.momentum("000660", lookback=20)
        assert result < 0  # 190000 → 184300 하락


class TestValue:
    def test_lower_per_higher_score(self, trading_store):
        """PER이 낮을수록 밸류 점수가 높다."""
        calc = FactorCalculator(trading_store)
        samsung = calc.value("005930")  # PER 12.5
        hynix = calc.value("000660")    # PER 8.0
        assert hynix > samsung  # PER 낮은 SK하이닉스가 더 높은 밸류 점수


class TestQuality:
    def test_higher_roe_higher_score(self, trading_store):
        """ROE가 높을수록 퀄리티 점수가 높다."""
        calc = FactorCalculator(trading_store)
        samsung = calc.quality("005930")  # ROE 15.2
        hynix = calc.quality("000660")    # ROE 12.0
        assert samsung > hynix


class TestFlow:
    def test_net_buy_positive(self, trading_store):
        """외국인 순매수 종목은 양수 수급 점수."""
        calc = FactorCalculator(trading_store)
        samsung = calc.flow("005930", days=20)
        assert samsung > 0  # 외국인 순매수 우세

    def test_net_sell_negative(self, trading_store):
        """외국인 순매도 종목은 음수 수급 점수."""
        calc = FactorCalculator(trading_store)
        hynix = calc.flow("000660", days=20)
        assert hynix < 0  # 외국인 순매도


class TestVolatility:
    def test_returns_positive(self, trading_store):
        """변동성은 항상 양수."""
        calc = FactorCalculator(trading_store)
        vol = calc.volatility("005930", days=20)
        assert vol > 0

    def test_missing_data_returns_none(self, trading_store):
        """데이터 없으면 None."""
        calc = FactorCalculator(trading_store)
        vol = calc.volatility("999999", days=20)
        assert vol is None
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/trading/screening/test_factors.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 4: Implement factors**

`alphapulse/trading/screening/factors.py`:
```python
"""팩터 계산기.

종목별 모멘텀, 밸류, 퀄리티, 수급, 변동성 팩터를 계산한다.
각 팩터는 원시값을 반환한다. percentile 정규화는 Ranker에서 수행한다.
"""

import math

from alphapulse.trading.data.store import TradingStore


class FactorCalculator:
    """개별 팩터 점수 계산기.

    Attributes:
        store: TradingStore 인스턴스.
    """

    def __init__(self, store: TradingStore) -> None:
        self.store = store

    def momentum(self, code: str, lookback: int = 60) -> float | None:
        """모멘텀 팩터 — lookback 기간 수익률 (%).

        Args:
            code: 종목코드.
            lookback: 조회 기간 (영업일).

        Returns:
            수익률 (%). 데이터 부족 시 None.
        """
        rows = self.store.get_ohlcv(code, "00000000", "99999999")
        if len(rows) < 2:
            return None
        recent = rows[-lookback:] if len(rows) >= lookback else rows
        start_price = recent[0]["close"]
        end_price = recent[-1]["close"]
        if start_price == 0:
            return None
        return (end_price - start_price) / start_price * 100

    def value(self, code: str) -> float | None:
        """밸류 팩터 — PER 역수 (E/P, %).

        PER이 낮을수록 값이 크다 (저평가).

        Args:
            code: 종목코드.

        Returns:
            E/P 비율 (%). 데이터 없으면 None.
        """
        fund = self.store.get_fundamentals(code)
        if fund is None or fund.get("per") is None or fund["per"] <= 0:
            return None
        return (1.0 / fund["per"]) * 100

    def quality(self, code: str) -> float | None:
        """퀄리티 팩터 — ROE (%).

        Args:
            code: 종목코드.

        Returns:
            ROE (%). 데이터 없으면 None.
        """
        fund = self.store.get_fundamentals(code)
        if fund is None or fund.get("roe") is None:
            return None
        return fund["roe"]

    def flow(self, code: str, days: int = 20) -> float | None:
        """수급 팩터 — 외국인 순매수 누적 (원).

        Args:
            code: 종목코드.
            days: 조회 기간 (영업일).

        Returns:
            외국인 순매수 누적 (원). 데이터 없으면 None.
        """
        rows = self.store.get_investor_flow(code, days=days)
        if not rows:
            return None
        return sum(r.get("foreign_net", 0) or 0 for r in rows)

    def volatility(self, code: str, days: int = 60) -> float | None:
        """변동성 팩터 — 일간 수익률의 표준편차 (연환산, %).

        Args:
            code: 종목코드.
            days: 조회 기간 (영업일).

        Returns:
            연환산 변동성 (%). 데이터 부족 시 None.
        """
        rows = self.store.get_ohlcv(code, "00000000", "99999999")
        if len(rows) < 5:
            return None
        recent = rows[-days:] if len(rows) >= days else rows
        returns = []
        for i in range(1, len(recent)):
            prev_close = recent[i - 1]["close"]
            if prev_close == 0:
                continue
            daily_ret = (recent[i]["close"] - prev_close) / prev_close
            returns.append(daily_ret)

        if len(returns) < 3:
            return None

        mean = sum(returns) / len(returns)
        variance = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
        daily_vol = math.sqrt(variance)
        annual_vol = daily_vol * math.sqrt(252)
        return annual_vol * 100

    def dividend_yield(self, code: str) -> float | None:
        """배당수익률 팩터 (%).

        Args:
            code: 종목코드.

        Returns:
            배당수익률 (%). 데이터 없으면 None.
        """
        fund = self.store.get_fundamentals(code)
        if fund is None or fund.get("dividend_yield") is None:
            return None
        return fund["dividend_yield"]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/trading/screening/test_factors.py -v`
Expected: 7 passed

- [ ] **Step 6: Commit**

```bash
git add alphapulse/trading/screening/ tests/trading/screening/ tests/trading/conftest.py
git commit -m "feat(trading): add FactorCalculator (momentum, value, quality, flow, volatility)"
```

---

## Task 13: 투자 제외 필터

**Files:**
- Create: `alphapulse/trading/screening/filter.py`
- Test: `tests/trading/screening/test_filter.py`

- [ ] **Step 1: Write failing test**

`tests/trading/screening/test_filter.py`:
```python
"""투자 제외 필터 테스트."""

import pytest

from alphapulse.trading.core.models import Stock
from alphapulse.trading.screening.filter import StockFilter


@pytest.fixture
def stocks():
    return [
        Stock(code="005930", name="삼성전자", market="KOSPI", sector="반도체"),
        Stock(code="000660", name="SK하이닉스", market="KOSPI", sector="반도체"),
        Stock(code="035720", name="카카오", market="KOSPI", sector="IT"),
        Stock(code="069500", name="KODEX 200", market="ETF"),
    ]


@pytest.fixture
def stock_data():
    """종목별 시총/거래대금 정보 (필터가 참조하는 데이터)."""
    return {
        "005930": {"market_cap": 430e12, "avg_volume": 500e9},
        "000660": {"market_cap": 120e12, "avg_volume": 200e9},
        "035720": {"market_cap": 20e12, "avg_volume": 25e9},
        "069500": {"market_cap": 50e12, "avg_volume": 7e9},
    }


class TestStockFilter:
    def test_no_filter(self, stocks, stock_data):
        """필터 없으면 전체 통과."""
        f = StockFilter({})
        result = f.apply(stocks, stock_data)
        assert len(result) == 4

    def test_min_market_cap(self, stocks, stock_data):
        """시가총액 필터."""
        f = StockFilter({"min_market_cap": 50e12})
        result = f.apply(stocks, stock_data)
        codes = [s.code for s in result]
        assert "005930" in codes
        assert "000660" in codes
        assert "035720" not in codes  # 20조 < 50조

    def test_min_avg_volume(self, stocks, stock_data):
        """일평균 거래대금 필터."""
        f = StockFilter({"min_avg_volume": 10e9})
        result = f.apply(stocks, stock_data)
        codes = [s.code for s in result]
        assert "005930" in codes
        assert "069500" not in codes  # 70억 < 100억

    def test_exclude_sectors(self, stocks, stock_data):
        """섹터 제외."""
        f = StockFilter({"exclude_sectors": ["IT"]})
        result = f.apply(stocks, stock_data)
        codes = [s.code for s in result]
        assert "035720" not in codes  # IT 섹터 제외

    def test_combined(self, stocks, stock_data):
        """복합 필터."""
        f = StockFilter({
            "min_market_cap": 100e12,
            "exclude_sectors": ["IT"],
        })
        result = f.apply(stocks, stock_data)
        codes = [s.code for s in result]
        assert codes == ["005930", "000660"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/trading/screening/test_filter.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement filter**

`alphapulse/trading/screening/filter.py`:
```python
"""투자 제외 필터.

유동성, 시가총액, 섹터 기반으로 투자 부적격 종목을 제외한다.
"""

from alphapulse.trading.core.models import Stock


class StockFilter:
    """투자 제외 필터.

    Attributes:
        config: 필터 설정 딕셔너리.
    """

    def __init__(self, config: dict) -> None:
        """StockFilter를 초기화한다.

        Args:
            config: 필터 설정. 지원 키:
                min_market_cap (float): 최소 시가총액 (원).
                min_avg_volume (float): 최소 일평균 거래대금 (원).
                exclude_sectors (list[str]): 제외 섹터 목록.
        """
        self.min_market_cap = config.get("min_market_cap")
        self.min_avg_volume = config.get("min_avg_volume")
        self.exclude_sectors = set(config.get("exclude_sectors", []))

    def apply(self, stocks: list[Stock],
              stock_data: dict[str, dict]) -> list[Stock]:
        """필터를 적용하여 부적격 종목을 제외한다.

        Args:
            stocks: 필터링할 종목 리스트.
            stock_data: 종목코드 → {"market_cap", "avg_volume"} 매핑.

        Returns:
            필터 통과한 종목 리스트.
        """
        result = []
        for s in stocks:
            data = stock_data.get(s.code, {})

            if self.min_market_cap is not None:
                if data.get("market_cap", 0) < self.min_market_cap:
                    continue

            if self.min_avg_volume is not None:
                if data.get("avg_volume", 0) < self.min_avg_volume:
                    continue

            if s.sector in self.exclude_sectors:
                continue

            result.append(s)
        return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/trading/screening/test_filter.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add alphapulse/trading/screening/filter.py tests/trading/screening/test_filter.py
git commit -m "feat(trading): add StockFilter for market cap, volume, sector exclusion"
```

---

## Task 14: 멀티팩터 랭킹

**Files:**
- Create: `alphapulse/trading/screening/ranker.py`
- Test: `tests/trading/screening/test_ranker.py`

- [ ] **Step 1: Write failing test**

`tests/trading/screening/test_ranker.py`:
```python
"""멀티팩터 랭킹 테스트."""

import pytest

from alphapulse.trading.core.models import Stock
from alphapulse.trading.screening.ranker import MultiFactorRanker


@pytest.fixture
def factor_data():
    """종목별 팩터 원시값 (FactorCalculator 출력 형식)."""
    return {
        "005930": {"momentum": 5.4, "value": 8.0, "quality": 15.2, "flow": 400e9, "volatility": 25.0},
        "000660": {"momentum": -3.0, "value": 12.5, "quality": 12.0, "flow": -600e9, "volatility": 35.0},
        "035720": {"momentum": 2.0, "value": 5.0, "quality": 10.0, "flow": 100e9, "volatility": 40.0},
    }


@pytest.fixture
def stocks():
    return [
        Stock(code="005930", name="삼성전자", market="KOSPI"),
        Stock(code="000660", name="SK하이닉스", market="KOSPI"),
        Stock(code="035720", name="카카오", market="KOSPI"),
    ]


class TestMultiFactorRanker:
    def test_rank_returns_sorted(self, stocks, factor_data):
        """점수 내림차순 정렬."""
        ranker = MultiFactorRanker(
            weights={"momentum": 0.3, "value": 0.3, "quality": 0.2, "flow": 0.1, "volatility": 0.1}
        )
        signals = ranker.rank(stocks, factor_data, strategy_id="test")

        assert len(signals) == 3
        # 점수 내림차순 확인
        assert signals[0].score >= signals[1].score >= signals[2].score

    def test_rank_signal_fields(self, stocks, factor_data):
        """Signal 필드가 올바르게 설정된다."""
        ranker = MultiFactorRanker(
            weights={"momentum": 0.5, "value": 0.5}
        )
        signals = ranker.rank(stocks, factor_data, strategy_id="momentum")

        for sig in signals:
            assert sig.strategy_id == "momentum"
            assert -100 <= sig.score <= 100
            assert "momentum" in sig.factors
            assert "value" in sig.factors

    def test_rank_with_missing_factor(self, stocks):
        """팩터 데이터 누락 시 해당 종목은 0점 처리."""
        factor_data = {
            "005930": {"momentum": 5.0},
            "000660": {"momentum": -3.0},
            # 035720은 아예 없음
        }
        ranker = MultiFactorRanker(weights={"momentum": 1.0})
        signals = ranker.rank(stocks, factor_data, strategy_id="test")
        assert len(signals) == 3

    def test_rank_single_stock(self, factor_data):
        """종목 1개일 때도 동작한다."""
        stocks = [Stock(code="005930", name="삼성전자", market="KOSPI")]
        ranker = MultiFactorRanker(weights={"momentum": 1.0})
        signals = ranker.rank(stocks, factor_data, strategy_id="test")
        assert len(signals) == 1

    def test_volatility_inverse_scoring(self, stocks, factor_data):
        """변동성은 역순 — 낮을수록 높은 점수."""
        ranker = MultiFactorRanker(weights={"volatility": 1.0})
        signals = ranker.rank(stocks, factor_data, strategy_id="test")
        # 삼성(25%) < SK(35%) < 카카오(40%) → 삼성 점수 최고
        assert signals[0].stock.code == "005930"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/trading/screening/test_ranker.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement ranker**

`alphapulse/trading/screening/ranker.py`:
```python
"""멀티팩터 종목 랭킹.

팩터별 percentile 정규화 → 가중 합산 → 종합 점수 산출.
"""

from datetime import datetime

from alphapulse.trading.core.models import Signal, Stock

# 높을수록 좋은 팩터 vs 낮을수록 좋은 팩터
_INVERSE_FACTORS = {"volatility"}


class MultiFactorRanker:
    """멀티팩터 종합 랭킹.

    Attributes:
        weights: 팩터별 가중치 딕셔너리 (합계 1.0 권장).
    """

    def __init__(self, weights: dict[str, float]) -> None:
        self.weights = weights

    def rank(self, stocks: list[Stock],
             factor_data: dict[str, dict],
             strategy_id: str) -> list[Signal]:
        """종목별 종합 점수를 계산하고 내림차순 정렬한다.

        Args:
            stocks: 대상 종목 리스트.
            factor_data: 종목코드 → {팩터명: 원시값} 매핑.
            strategy_id: 전략 ID.

        Returns:
            점수 내림차순 Signal 리스트.
        """
        factor_names = list(self.weights.keys())

        # 1. 팩터별 percentile 계산
        percentiles = self._calculate_percentiles(stocks, factor_data, factor_names)

        # 2. 가중 합산 → 종합 점수 (-100 ~ +100)
        signals = []
        for s in stocks:
            code_pcts = percentiles.get(s.code, {})
            total_weight = 0
            weighted_sum = 0

            factor_scores = {}
            for factor in factor_names:
                pct = code_pcts.get(factor)
                if pct is None:
                    continue
                w = self.weights[factor]
                weighted_sum += pct * w
                total_weight += w
                factor_scores[factor] = round(pct, 1)

            if total_weight > 0:
                # 0~100 percentile → -100~+100 스케일
                raw_score = weighted_sum / total_weight
                score = (raw_score - 50) * 2
            else:
                score = 0

            score = max(-100, min(100, round(score, 1)))

            signals.append(Signal(
                stock=s,
                score=score,
                factors=factor_scores,
                strategy_id=strategy_id,
                timestamp=datetime.now(),
            ))

        signals.sort(key=lambda sig: sig.score, reverse=True)
        return signals

    def _calculate_percentiles(
        self,
        stocks: list[Stock],
        factor_data: dict[str, dict],
        factor_names: list[str],
    ) -> dict[str, dict[str, float]]:
        """팩터별 percentile(0~100)을 계산한다.

        Args:
            stocks: 종목 리스트.
            factor_data: 팩터 원시값.
            factor_names: 계산할 팩터 이름 목록.

        Returns:
            종목코드 → {팩터명: percentile} 매핑.
        """
        result: dict[str, dict[str, float]] = {s.code: {} for s in stocks}

        for factor in factor_names:
            # 해당 팩터의 값이 있는 종목만 수집
            values: list[tuple[str, float]] = []
            for s in stocks:
                data = factor_data.get(s.code, {})
                val = data.get(factor)
                if val is not None:
                    values.append((s.code, val))

            if not values:
                continue

            # 정렬 (inverse 팩터는 역순)
            reverse = factor not in _INVERSE_FACTORS
            sorted_vals = sorted(values, key=lambda x: x[1], reverse=reverse)

            # percentile 할당 (순위 기반)
            n = len(sorted_vals)
            for rank_idx, (code, _) in enumerate(sorted_vals):
                if n == 1:
                    pct = 50.0
                else:
                    pct = (1 - rank_idx / (n - 1)) * 100
                result[code][factor] = pct

        return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/trading/screening/test_ranker.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add alphapulse/trading/screening/ranker.py tests/trading/screening/test_ranker.py
git commit -m "feat(trading): add MultiFactorRanker with percentile normalization"
```

---

## Task 15: CLI 명령 + 전체 통합 테스트

**Files:**
- Modify: `alphapulse/cli.py`
- Test: `tests/trading/test_integration.py`

- [ ] **Step 1: Write integration test**

`tests/trading/test_integration.py`:
```python
"""Trading Phase 1 통합 테스트.

Core → Data → Screening 전체 파이프라인을 검증한다.
"""

from alphapulse.trading.core.models import Stock
from alphapulse.trading.data.store import TradingStore
from alphapulse.trading.data.universe import Universe
from alphapulse.trading.screening.factors import FactorCalculator
from alphapulse.trading.screening.filter import StockFilter
from alphapulse.trading.screening.ranker import MultiFactorRanker


def test_full_screening_pipeline(trading_store):
    """데이터 → 유니버스 → 팩터 → 필터 → 랭킹 전체 흐름."""
    # 1. 유니버스 조회
    universe = Universe(trading_store)
    all_stocks = universe.get_all()
    assert len(all_stocks) == 2  # conftest에서 2종목

    # 2. 팩터 계산
    calc = FactorCalculator(trading_store)
    factor_data = {}
    for s in all_stocks:
        factor_data[s.code] = {
            "momentum": calc.momentum(s.code, lookback=20),
            "value": calc.value(s.code),
            "quality": calc.quality(s.code),
            "flow": calc.flow(s.code, days=20),
            "volatility": calc.volatility(s.code, days=20),
        }

    # 3. 팩터 값 검증
    assert factor_data["005930"]["momentum"] > 0  # 상승
    assert factor_data["000660"]["momentum"] < 0  # 하락

    # 4. 랭킹
    ranker = MultiFactorRanker(
        weights={"momentum": 0.3, "value": 0.25, "quality": 0.2,
                 "flow": 0.15, "volatility": 0.1}
    )
    signals = ranker.rank(all_stocks, factor_data, strategy_id="multi_factor")
    assert len(signals) == 2
    assert signals[0].score >= signals[1].score
    assert signals[0].strategy_id == "multi_factor"

    # 5. 필터 (시가총액 200조 이상만)
    stock_data = {
        "005930": {"market_cap": 430e12, "avg_volume": 500e9},
        "000660": {"market_cap": 120e12, "avg_volume": 200e9},
    }
    stock_filter = StockFilter({"min_market_cap": 200e12})
    filtered = stock_filter.apply(all_stocks, stock_data)
    assert len(filtered) == 1
    assert filtered[0].code == "005930"
```

- [ ] **Step 2: Run integration test**

Run: `pytest tests/trading/test_integration.py -v`
Expected: 1 passed

- [ ] **Step 3: Add CLI command**

Add `trading` group to `alphapulse/cli.py`. Find the end of the existing CLI groups and add:

```python
# ── Trading 명령어 ──────────────────────────────────────────────
@cli.group()
def trading():
    """자동 매매 시스템"""
    pass


@trading.command()
@click.option("--market", default="KOSPI", help="시장 (KOSPI/KOSDAQ)")
@click.option("--top", default=20, help="상위 N종목")
@click.option("--factor", default="momentum", help="주요 팩터")
def screen(market, top, factor):
    """종목 스크리닝 — 팩터 기반 종목 랭킹"""
    from alphapulse.core.config import Config
    from alphapulse.trading.data.store import TradingStore
    from alphapulse.trading.data.universe import Universe
    from alphapulse.trading.screening.factors import FactorCalculator
    from alphapulse.trading.screening.ranker import MultiFactorRanker

    cfg = Config()
    db_path = cfg.DATA_DIR / "trading.db"
    store = TradingStore(db_path)
    universe = Universe(store)

    stocks = universe.get_by_market(market)
    if not stocks:
        click.echo(f"{market} 종목 데이터가 없습니다. 먼저 데이터를 수집하세요.")
        return

    calc = FactorCalculator(store)
    factor_data = {}
    for s in stocks:
        factor_data[s.code] = {
            "momentum": calc.momentum(s.code),
            "value": calc.value(s.code),
            "quality": calc.quality(s.code),
            "flow": calc.flow(s.code),
            "volatility": calc.volatility(s.code),
        }

    # 팩터별 가중치 프리셋
    weight_presets = {
        "momentum": {"momentum": 0.6, "flow": 0.3, "volatility": 0.1},
        "value": {"value": 0.4, "quality": 0.3, "momentum": 0.2, "flow": 0.1},
        "quality": {"quality": 0.4, "momentum": 0.3, "value": 0.2, "flow": 0.1},
        "balanced": {"momentum": 0.25, "value": 0.25, "quality": 0.2, "flow": 0.15, "volatility": 0.15},
    }
    weights = weight_presets.get(factor, weight_presets["balanced"])

    ranker = MultiFactorRanker(weights=weights)
    signals = ranker.rank(stocks, factor_data, strategy_id=factor)

    click.echo(f"\n{'='*60}")
    click.echo(f" {market} 종목 스크리닝 (팩터: {factor}, 상위 {top})")
    click.echo(f"{'='*60}")
    click.echo(f" {'순위':>4}  {'종목코드':>8}  {'종목명':<12}  {'점수':>6}  {'주요팩터'}")
    click.echo(f" {'-'*56}")

    for i, sig in enumerate(signals[:top], 1):
        top_factor = max(sig.factors, key=sig.factors.get) if sig.factors else "-"
        click.echo(
            f" {i:>4}  {sig.stock.code:>8}  {sig.stock.name:<12}  "
            f"{sig.score:>+6.1f}  {top_factor}"
        )
```

- [ ] **Step 4: Run full test suite**

Run: `pytest tests/trading/ -v`
Expected: All tests pass (approximately 43 tests)

- [ ] **Step 5: Run existing tests to verify no regressions**

Run: `pytest tests/ -v --tb=short`
Expected: 275 + ~43 = ~318 tests pass. No failures.

- [ ] **Step 6: Commit**

```bash
git add alphapulse/cli.py tests/trading/test_integration.py
git commit -m "feat(trading): add CLI screen command + integration test"
```

---

## Verification Checklist

After completing all tasks, verify:

- [ ] `pytest tests/trading/ -v` — All trading tests pass
- [ ] `pytest tests/ -v` — No regression in existing 275 tests
- [ ] `ruff check alphapulse/trading/` — No lint errors
- [ ] `ap trading screen --help` — CLI command works
- [ ] All files follow project conventions (sync-only, Korean docstrings, 200-line limit)

---

## Next Plans

After Phase 1 completion, the following plans will be created:

| Plan | Phases | Description |
|------|--------|-------------|
| **Plan 2** | ④⑤⑥ | Strategy framework + Portfolio manager + Risk engine |
| **Plan 3** | ⑦⑧ | Backtest engine + AI synthesis agent |
| **Plan 4** | ⑨⑩ | KIS broker integration + Trading orchestrator |

Each plan depends on the previous one. Start Plan 2 only after Plan 1 is fully verified.
