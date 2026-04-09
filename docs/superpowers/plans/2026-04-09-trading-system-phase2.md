# Trading System Phase 2: Strategy + Portfolio + Risk

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 전략 프레임워크(④), 포트폴리오 관리(⑤), 리스크 엔진(⑥)을 구현하여, Phase 1에서 만든 스크리닝 결과를 실제 매매 시그널 → 목표 포트폴리오 → 주문 생성 → 리스크 검증까지 이어지는 파이프라인을 완성한다.

**Architecture:** 전략이 시그널을 생성하고, 포트폴리오 매니저가 목표 비중을 산출하며, 리스크 엔진이 모든 주문을 사전 검증한다. AI 종합 판단(ai_synthesizer)만 async이고, 나머지는 모두 sync이다.

**Tech Stack:** Python 3.11+, numpy, scipy.optimize, sqlite3, pytest, dataclasses, StrEnum

**Spec:** `docs/superpowers/specs/2026-04-09-trading-system-design.md`

**Depends on:** Phase 1 (Core + Data + Screening) must be completed first.

---

## File Structure

### New Files to Create

```
alphapulse/trading/strategy/
├── __init__.py
├── base.py              # Task 1: BaseStrategy ABC
├── topdown_etf.py       # Task 2: TopDownETF 전략
├── momentum.py          # Task 3: Momentum 전략
├── value.py             # Task 4: Value 전략
├── quality_momentum.py  # Task 5: QualityMomentum 전략
├── registry.py          # Task 6: StrategyRegistry
├── allocator.py         # Task 7: StrategyAllocator
└── ai_synthesizer.py    # Task 8: AI 종합 판단 (async)

alphapulse/trading/portfolio/
├── __init__.py
├── position_sizer.py    # Task 9: PositionSizer
├── optimizer.py         # Task 10: PortfolioOptimizer (mean-variance, risk parity)
├── rebalancer.py        # Task 11: Rebalancer (주문 생성)
├── store.py             # Task 12: PortfolioStore (portfolio.db)
├── attribution.py       # Task 13: PerformanceAttribution
└── manager.py           # Task 14: PortfolioManager (통합)

alphapulse/trading/risk/
├── __init__.py
├── limits.py            # Task 15: RiskLimits + RiskDecision + RiskAlert
├── var.py               # Task 16: VaRCalculator
├── drawdown.py          # Task 17: DrawdownManager
├── stress_test.py       # Task 18: StressTest
├── report.py            # Task 19: RiskReport
└── manager.py           # Task 20: RiskManager (통합)

tests/trading/strategy/
├── __init__.py
├── test_base.py
├── test_topdown_etf.py
├── test_momentum.py
├── test_value.py
├── test_quality_momentum.py
├── test_registry.py
���── test_allocator.py
└── test_ai_synthesizer.py

tests/trading/portfolio/
├── __init__.py
├── test_position_sizer.py
├── test_optimizer.py
├── test_rebalancer.py
├── test_store.py
├── test_attribution.py
└─��� test_manager.py

tests/trading/risk/
├── __init__.py
├── test_limits.py
├── test_var.py
├── test_drawdown.py
├── test_stress_test.py
├── test_report.py
└── test_manager.py
```

---

## Phase ④: Strategy Framework

---

### Task 1: BaseStrategy ABC + 패키지 구조

**Files:**
- Create: `alphapulse/trading/strategy/__init__.py`
- Create: `alphapulse/trading/strategy/base.py`
- Test: `tests/trading/strategy/__init__.py`
- Test: `tests/trading/strategy/test_base.py`

- [ ] **Step 1: Create package directories**

```bash
mkdir -p alphapulse/trading/strategy
mkdir -p tests/trading/strategy
```

Create `tests/trading/strategy/__init__.py` (빈 파일).

`alphapulse/trading/strategy/__init__.py`:
```python
"""전략 프레임워크."""
```

- [ ] **Step 2: Write failing test**

`tests/trading/strategy/test_base.py`:
```python
"""BaseStrategy ABC 테스트."""

from abc import ABC

from alphapulse.trading.core.enums import RebalanceFreq
from alphapulse.trading.core.models import Signal, Stock
from alphapulse.trading.strategy.base import BaseStrategy


class DummyStrategy(BaseStrategy):
    """테스트용 전략 구현체."""

    strategy_id = "dummy"
    rebalance_freq = RebalanceFreq.WEEKLY

    def generate_signals(self, universe, market_context):
        return [
            Signal(
                stock=universe[0],
                score=80.0,
                factors={"test": 0.8},
                strategy_id=self.strategy_id,
            )
        ]


class TestBaseStrategy:
    def test_is_abstract(self):
        """BaseStrategy는 ABC여야 한다."""
        assert issubclass(BaseStrategy, ABC)

    def test_cannot_instantiate_directly(self):
        """BaseStrategy를 직접 인스턴스화할 수 없다."""
        try:
            BaseStrategy(config={})
            assert False, "ABC를 직접 인스턴스화하면 안 된다"
        except TypeError:
            pass

    def test_subclass_works(self):
        """구현체는 정상 동작한다."""
        strategy = DummyStrategy(config={"top_n": 10})
        assert strategy.strategy_id == "dummy"
        assert strategy.rebalance_freq == RebalanceFreq.WEEKLY
        assert strategy.config == {"top_n": 10}

    def test_generate_signals(self):
        """시그널 생성이 올바르게 동작한다."""
        strategy = DummyStrategy(config={})
        stock = Stock(code="005930", name="삼성전자", market="KOSPI")
        signals = strategy.generate_signals([stock], {})
        assert len(signals) == 1
        assert signals[0].score == 80.0
        assert signals[0].strategy_id == "dummy"

    def test_should_rebalance_daily(self):
        """DAILY 전략은 항상 True."""
        strategy = DummyStrategy(config={})
        strategy.rebalance_freq = RebalanceFreq.DAILY
        assert strategy.should_rebalance("20260406", "20260407") is True

    def test_should_rebalance_weekly_monday(self):
        """WEEKLY 전략은 월요일에 True."""
        strategy = DummyStrategy(config={})
        # 2026-04-06은 월요일
        assert strategy.should_rebalance("20260401", "20260406") is True

    def test_should_rebalance_weekly_non_monday(self):
        """WEEKLY 전략은 월요일이 아니면 False."""
        strategy = DummyStrategy(config={})
        # 2026-04-07은 화요일
        assert strategy.should_rebalance("20260406", "20260407") is False
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/trading/strategy/test_base.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'alphapulse.trading.strategy.base'`

- [ ] **Step 4: Implement**

`alphapulse/trading/strategy/base.py`:
```python
"""전략 기본 클래스(ABC).

모든 매매 전략은 이 클래스를 상속한다.
"""

from abc import ABC, abstractmethod
from datetime import datetime

from alphapulse.trading.core.enums import RebalanceFreq
from alphapulse.trading.core.models import Signal, Stock


class BaseStrategy(ABC):
    """모든 전략의 기본 클래스.

    Attributes:
        strategy_id: 전략 고유 식별자.
        rebalance_freq: 리밸런싱 주기.
        config: 전략별 파라미터 딕셔너리.
    """

    strategy_id: str
    rebalance_freq: RebalanceFreq

    def __init__(self, config: dict) -> None:
        """BaseStrategy를 ��기화한다.

        Args:
            config: 전략별 파라미터 (top_n, factor_weights ���).
        """
        self.config = config

    @abstractmethod
    def generate_signals(
        self,
        universe: list[Stock],
        market_context: dict,
    ) -> list[Signal]:
        """종목별 매�� 시그널을 생성한다.

        Args:
            universe: 투자 유니버스 종목 리스트.
            market_context: Market Pulse 등 시장 상황 딕셔너리.

        Returns:
            종목별 Signal 리스트 (점수순 정렬).
        """
        ...

    def should_rebalance(
        self,
        last_rebalance: str,
        current_date: str,
    ) -> bool:
        """리밸런싱 시점인지 판단���다.

        Args:
            last_rebalance: 마지막 리밸런싱 날짜 (YYYYMMDD).
            current_date: 현재 날짜 (YYYYMMDD).

        Returns:
            리밸런싱해야 하면 True.
        """
        if self.rebalance_freq == RebalanceFreq.DAILY:
            return True
        elif self.rebalance_freq == RebalanceFreq.WEEKLY:
            dt = datetime.strptime(current_date, "%Y%m%d")
            return dt.weekday() == 0  # 월요일
        elif self.rebalance_freq == RebalanceFreq.SIGNAL_DRIVEN:
            return False  # 서브클래스에서 오버라이드
        return False
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/trading/strategy/test_base.py -v`
Expected: 7 passed

- [ ] **Step 6: Commit**

```bash
git add alphapulse/trading/strategy/ tests/trading/strategy/
git commit -m "feat(trading): add BaseStrategy ABC with rebalance logic"
```

---

### Task 2: TopDownETF 전략

**Files:**
- Create: `alphapulse/trading/strategy/topdown_etf.py`
- Test: `tests/trading/strategy/test_topdown_etf.py`

- [ ] **Step 1: Write failing test**

`tests/trading/strategy/test_topdown_etf.py`:
```python
"""TopDownETF 전략 테스트."""

from alphapulse.trading.core.enums import RebalanceFreq
from alphapulse.trading.core.models import Stock
from alphapulse.trading.strategy.base import BaseStrategy
from alphapulse.trading.strategy.topdown_etf import TopDownETFStrategy


class TestTopDownETFStrategy:
    def setup_method(self):
        self.strategy = TopDownETFStrategy(config={})
        self.etf_universe = [
            Stock(code="122630", name="KODEX 레버리지", market="ETF"),
            Stock(code="069500", name="KODEX 200", market="ETF"),
            Stock(code="153130", name="KODEX 단기채권", market="ETF"),
            Stock(code="114800", name="KODEX 인버스", market="ETF"),
            Stock(code="252670", name="KODEX 200선물인버스2X", market="ETF"),
        ]

    def test_is_base_strategy(self):
        """BaseStrategy를 상속한다."""
        assert isinstance(self.strategy, BaseStrategy)

    def test_strategy_id(self):
        assert self.strategy.strategy_id == "topdown_etf"

    def test_rebalance_freq(self):
        assert self.strategy.rebalance_freq == RebalanceFreq.SIGNAL_DRIVEN

    def test_strong_bullish_signals(self):
        """강한 매수 시그널 → 레버리지 + KODEX 200."""
        ctx = {"pulse_signal": "strong_bullish", "pulse_score": 80}
        signals = self.strategy.generate_signals(self.etf_universe, ctx)
        assert len(signals) > 0
        codes = [s.stock.code for s in signals]
        assert "122630" in codes  # 레��리지
        assert all(s.score > 0 for s in signals)

    def test_strong_bearish_signals(self):
        """강한 매도 시그널 → 인버스 + 채권 + 현금."""
        ctx = {"pulse_signal": "strong_bearish", "pulse_score": -80}
        signals = self.strategy.generate_signals(self.etf_universe, ctx)
        codes = [s.stock.code for s in signals]
        assert "252670" in codes  # 인버스2X
        assert "153130" in codes  # 단기채권

    def test_neutral_signals(self):
        """중립 시그널 → 채권 + KODEX 200 소량."""
        ctx = {"pulse_signal": "neutral", "pulse_score": 0}
        signals = self.strategy.generate_signals(self.etf_universe, ctx)
        assert len(signals) > 0
        # 채권이 가장 높은 비중
        bond_signal = [s for s in signals if s.stock.code == "153130"]
        assert len(bond_signal) == 1

    def test_should_rebalance_on_signal_change(self):
        """시그널 레벨 변경 시 리밸런싱."""
        assert self.strategy.should_rebalance_signal_driven(
            prev_signal="neutral", curr_signal="strong_bullish"
        ) is True

    def test_no_rebalance_same_signal(self):
        """시그널 레벨 동일하면 리밸런싱 안 함."""
        assert self.strategy.should_rebalance_signal_driven(
            prev_signal="neutral", curr_signal="neutral"
        ) is False

    def test_unknown_signal_fallback(self):
        """알 수 없는 시그널 → neutral로 폴백."""
        ctx = {"pulse_signal": "unknown_signal", "pulse_score": 0}
        signals = self.strategy.generate_signals(self.etf_universe, ctx)
        assert len(signals) > 0  # neutral 매핑 적용
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/trading/strategy/test_topdown_etf.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement**

`alphapulse/trading/strategy/topdown_etf.py`:
```python
"""탑다운 ETF 전략.

Market Pulse Score → ETF 포지션 결정.
시그널 레벨 변경 시에만 ���밸런싱 (SIGNAL_DRIVEN).
"""

import logging

from alphapulse.trading.core.enums import RebalanceFreq
from alphapulse.trading.core.models import Signal, Stock
from alphapulse.trading.strategy.base import BaseStrategy

logger = logging.getLogger(__name__)

# ETF 코드 매핑 (이름 → 코드)
_ETF_CODES = {
    "KODEX 레버리지": "122630",
    "KODEX 200": "069500",
    "KODEX 단기채권": "153130",
    "KODEX 인버���": "114800",
    "KODEX 200선물인���스2X": "252670",
}


class TopDownETFStrategy(BaseStrategy):
    """Market Pulse Score 기반 탑다운 ETF 전략.

    시장 시그널 레벨에 따라 공격/방어 ETF 비중을 결정한다.

    Attributes:
        ETF_MAP: 시그널 레벨별 ETF 비중 매핑.
    """

    strategy_id = "topdown_etf"
    rebalance_freq = RebalanceFreq.SIGNAL_DRIVEN

    ETF_MAP: dict[str, dict[str, float]] = {
        "strong_bullish": {"KODEX 레버리지": 0.7, "KODEX 200": 0.3},
        "moderately_bullish": {"KODEX 200": 0.8, "KODEX 단기채권": 0.2},
        "neutral": {"KODEX 단기채권": 0.5, "KODEX 200": 0.3},
        "moderately_bearish": {"KODEX 인버스": 0.5, "KODEX 단기채권": 0.3},
        "strong_bearish": {
            "KODEX 200선물인버스2X": 0.4,
            "KODEX 단기채권": 0.3,
        },
    }

    def generate_signals(
        self,
        universe: list[Stock],
        market_context: dict,
    ) -> list[Signal]:
        """Market Pulse 시그널에 따라 ETF 매매 시그널을 생성한다.

        Args:
            universe: ETF 유니버스.
            market_context: {"pulse_signal": str, "pulse_score": float}.

        Returns:
            ETF별 목표 비중을 점수로 변환한 Signal 리스트.
        """
        pulse_signal = market_context.get("pulse_signal", "neutral")
        pulse_score = market_context.get("pulse_score", 0)

        etf_weights = self.ETF_MAP.get(pulse_signal, self.ETF_MAP["neutral"])
        if pulse_signal not in self.ETF_MAP:
            logger.warning("알 수 없는 시그널 '%s' → neutral 폴백", pulse_signal)

        # 유니버스에서 코드 → Stock 매핑 생성
        code_to_stock = {s.code: s for s in universe}

        signals = []
        for etf_name, weight in etf_weights.items():
            code = _ETF_CODES.get(etf_name)
            if code is None or code not in code_to_stock:
                continue
            # 비중을 점수(-100~+100)로 변환: 비중 * pulse_score 방향성
            direction = 1.0 if pulse_score >= 0 else -1.0
            score = weight * 100 * direction
            # 인버스 ETF는 방향 반전
            if "인버스" in etf_name:
                score = weight * 100 * (-direction)
            signals.append(
                Signal(
                    stock=code_to_stock[code],
                    score=abs(score),
                    factors={"pulse_signal": pulse_signal, "weight": weight},
                    strategy_id=self.strategy_id,
                )
            )

        signals.sort(key=lambda s: s.score, reverse=True)
        return signals

    def should_rebalance_signal_driven(
        self,
        prev_signal: str,
        curr_signal: str,
    ) -> bool:
        """시그널 레벨이 변경되었을 때만 리밸런싱한다.

        Args:
            prev_signal: 이전 시그널 레벨.
            curr_signal: 현재 시그널 레벨.

        Returns:
            레벨이 변경되었으면 True.
        """
        return prev_signal != curr_signal
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/trading/strategy/test_topdown_etf.py -v`
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add alphapulse/trading/strategy/topdown_etf.py tests/trading/strategy/test_topdown_etf.py
git commit -m "feat(trading): add TopDownETFStrategy with signal-driven rebalancing"
```

---

### Task 3: Momentum 전략

**Files:**
- Create: `alphapulse/trading/strategy/momentum.py`
- Test: `tests/trading/strategy/test_momentum.py`

- [ ] **Step 1: Write failing test**

`tests/trading/strategy/test_momentum.py`:
```python
"""Momentum 전략 테스트."""

from unittest.mock import MagicMock

from alphapulse.trading.core.enums import RebalanceFreq
from alphapulse.trading.core.models import Signal, Stock
from alphapulse.trading.strategy.base import BaseStrategy
from alphapulse.trading.strategy.momentum import MomentumStrategy


class TestMomentumStrategy:
    def setup_method(self):
        self.ranker = MagicMock()
        self.config = {"top_n": 3}
        self.strategy = MomentumStrategy(
            ranker=self.ranker,
            config=self.config,
        )
        self.universe = [
            Stock(code="005930", name="삼성전자", market="KOSPI"),
            Stock(code="000660", name="SK하이닉스", market="KOSPI"),
            Stock(code="035720", name="카카오", market="KOSPI"),
            Stock(code="051910", name="LG화학", market="KOSPI"),
            Stock(code="006400", name="삼성SDI", market="KOSPI"),
        ]

    def test_is_base_strategy(self):
        assert isinstance(self.strategy, BaseStrategy)

    def test_strategy_id(self):
        assert self.strategy.strategy_id == "momentum"

    def test_rebalance_freq(self):
        assert self.strategy.rebalance_freq == RebalanceFreq.WEEKLY

    def test_top_n_default(self):
        s = MomentumStrategy(ranker=self.ranker, config={})
        assert s.top_n == 20

    def test_generate_signals_bullish(self):
        """매수 우위 시 상위 N종목 시그널 반환."""
        ranked = [
            Signal(stock=self.universe[0], score=90.0,
                   factors={"momentum": 0.9}, strategy_id="momentum"),
            Signal(stock=self.universe[1], score=75.0,
                   factors={"momentum": 0.7}, strategy_id="momentum"),
            Signal(stock=self.universe[2], score=60.0,
                   factors={"momentum": 0.6}, strategy_id="momentum"),
            Signal(stock=self.universe[3], score=40.0,
                   factors={"momentum": 0.4}, strategy_id="momentum"),
            Signal(stock=self.universe[4], score=20.0,
                   factors={"momentum": 0.2}, strategy_id="momentum"),
        ]
        self.ranker.rank.return_value = ranked

        ctx = {"pulse_signal": "moderately_bullish", "pulse_score": 40}
        signals = self.strategy.generate_signals(self.universe, ctx)

        assert len(signals) == 3  # top_n=3
        assert signals[0].stock.code == "005930"
        self.ranker.rank.assert_called_once()

    def test_generate_signals_bearish_reduces_strength(self):
        """매도 우위 시 시그널 강도 축소 (0.5배)."""
        ranked = [
            Signal(stock=self.universe[0], score=80.0,
                   factors={"momentum": 0.8}, strategy_id="momentum"),
        ]
        self.ranker.rank.return_value = ranked

        ctx = {"pulse_signal": "moderately_bearish", "pulse_score": -40}
        signals = self.strategy.generate_signals(self.universe, ctx)

        assert len(signals) >= 1
        assert signals[0].score == 40.0  # 80 * 0.5

    def test_factor_weights(self):
        """모멘텀 팩터 가중치 프리셋."""
        assert self.strategy.factor_weights["momentum"] == 0.6
        assert self.strategy.factor_weights["flow"] == 0.3
        assert self.strategy.factor_weights["volatility"] == 0.1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/trading/strategy/test_momentum.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement**

`alphapulse/trading/strategy/momentum.py`:
```python
"""모멘텀 전략.

상위 모멘텀 종목 롱 — 주간 리밸런싱.
시장 시그널이 매도 우위 이하면 시그널 강도를 축소한다.
"""

import logging

from alphapulse.trading.core.enums import RebalanceFreq
from alphapulse.trading.core.models import Signal, Stock
from alphapulse.trading.screening.ranker import MultiFactorRanker
from alphapulse.trading.strategy.base import BaseStrategy

logger = logging.getLogger(__name__)

_BEARISH_SIGNALS = {"moderately_bearish", "strong_bearish"}


class MomentumStrategy(BaseStrategy):
    """모멘텀 팩터 기반 종목 선정 전략.

    Attributes:
        strategy_id: "momentum".
        rebalance_freq: 주간 (WEEKLY).
        top_n: 상위 선정 종목 수.
        factor_weights: 팩터별 가중치.
        ranker: MultiFactorRanker 인스턴스.
    """

    strategy_id = "momentum"
    rebalance_freq = RebalanceFreq.WEEKLY

    def __init__(self, ranker: MultiFactorRanker, config: dict) -> None:
        """MomentumStrategy를 초기화한다.

        Args:
            ranker: 멀티팩터 랭커.
            config: 전략 설정. top_n(기본 20) 등.
        """
        super().__init__(config=config)
        self.ranker = ranker
        self.top_n: int = config.get("top_n", 20)
        self.factor_weights: dict[str, float] = {
            "momentum": 0.6,
            "flow": 0.3,
            "volatility": 0.1,
        }

    def generate_signals(
        self,
        universe: list[Stock],
        market_context: dict,
    ) -> list[Signal]:
        """모멘텀 상위 종목 시그널을 생성한다.

        Args:
            universe: 투자 유니버스.
            market_context: {"pulse_signal": str, "pulse_score": float}.

        Returns:
            상위 top_n 종목의 Signal 리스트 (점수순).
        """
        pulse_signal = market_context.get("pulse_signal", "neutral")

        # 랭커로 종목 점수 산출
        ranked = self.ranker.rank(universe, strategy_id=self.strategy_id)

        # 상위 N 선정
        top_signals = ranked[: self.top_n]

        # 매도 우위 시 강도 축소 (0.5배)
        if pulse_signal in _BEARISH_SIGNALS:
            top_signals = [
                Signal(
                    stock=s.stock,
                    score=s.score * 0.5,
                    factors=s.factors,
                    strategy_id=s.strategy_id,
                    timestamp=s.timestamp,
                )
                for s in top_signals
            ]
            logger.info("매도 우위 — 모멘텀 시그널 강도 0.5배 축소")

        return top_signals
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/trading/strategy/test_momentum.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add alphapulse/trading/strategy/momentum.py tests/trading/strategy/test_momentum.py
git commit -m "feat(trading): add MomentumStrategy with bearish dampening"
```

---

### Task 4: Value 전략

**Files:**
- Create: `alphapulse/trading/strategy/value.py`
- Test: `tests/trading/strategy/test_value.py`

- [ ] **Step 1: Write failing test**

`tests/trading/strategy/test_value.py`:
```python
"""Value 전략 테스트."""

from unittest.mock import MagicMock

from alphapulse.trading.core.enums import RebalanceFreq
from alphapulse.trading.core.models import Signal, Stock
from alphapulse.trading.strategy.base import BaseStrategy
from alphapulse.trading.strategy.value import ValueStrategy


class TestValueStrategy:
    def setup_method(self):
        self.ranker = MagicMock()
        self.config = {"top_n": 5}
        self.strategy = ValueStrategy(
            ranker=self.ranker,
            config=self.config,
        )
        self.universe = [
            Stock(code="005930", name="삼성전자", market="KOSPI"),
            Stock(code="000660", name="SK하이닉스", market="KOSPI"),
            Stock(code="035720", name="카카오", market="KOSPI"),
        ]

    def test_is_base_strategy(self):
        assert isinstance(self.strategy, BaseStrategy)

    def test_strategy_id(self):
        assert self.strategy.strategy_id == "value"

    def test_rebalance_freq(self):
        assert self.strategy.rebalance_freq == RebalanceFreq.WEEKLY

    def test_top_n_default(self):
        s = ValueStrategy(ranker=self.ranker, config={})
        assert s.top_n == 15

    def test_factor_weights(self):
        """밸류 팩터 가중치 프리셋."""
        assert self.strategy.factor_weights["value"] == 0.4
        assert self.strategy.factor_weights["quality"] == 0.3
        assert self.strategy.factor_weights["momentum"] == 0.2
        assert self.strategy.factor_weights["flow"] == 0.1

    def test_generate_signals(self):
        """밸류 랭킹 기반 시그널 반환."""
        ranked = [
            Signal(stock=self.universe[0], score=85.0,
                   factors={"value": 0.9}, strategy_id="value"),
            Signal(stock=self.universe[1], score=70.0,
                   factors={"value": 0.7}, strategy_id="value"),
            Signal(stock=self.universe[2], score=55.0,
                   factors={"value": 0.5}, strategy_id="value"),
        ]
        self.ranker.rank.return_value = ranked

        ctx = {"pulse_signal": "neutral", "pulse_score": 0}
        signals = self.strategy.generate_signals(self.universe, ctx)

        assert len(signals) == 3  # 3 < top_n=5
        assert signals[0].score == 85.0

    def test_neutral_boosts_score(self):
        """중립 시장에서 밸류 전략 강도 1.2배 증가."""
        ranked = [
            Signal(stock=self.universe[0], score=80.0,
                   factors={"value": 0.8}, strategy_id="value"),
        ]
        self.ranker.rank.return_value = ranked

        ctx = {"pulse_signal": "neutral", "pulse_score": 5}
        signals = self.strategy.generate_signals(self.universe, ctx)

        assert signals[0].score == 96.0  # 80 * 1.2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/trading/strategy/test_value.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement**

`alphapulse/trading/strategy/value.py`:
```python
"""밸류 전략.

저평가 + 퀄리티 복합 — 주간 리밸런싱.
중립 시장에서 강도가 증가한다 (불확실성 시 가치주 선호).
"""

import logging

from alphapulse.trading.core.enums import RebalanceFreq
from alphapulse.trading.core.models import Signal, Stock
from alphapulse.trading.screening.ranker import MultiFactorRanker
from alphapulse.trading.strategy.base import BaseStrategy

logger = logging.getLogger(__name__)


class ValueStrategy(BaseStrategy):
    """저평가 + 퀄리티 복합 전략.

    Attributes:
        strategy_id: "value".
        rebalance_freq: 주간 (WEEKLY).
        top_n: 상위 선정 종목 수 (기본 15).
        factor_weights: 팩터별 가중치.
        ranker: MultiFactorRanker 인스턴스.
    """

    strategy_id = "value"
    rebalance_freq = RebalanceFreq.WEEKLY

    def __init__(self, ranker: MultiFactorRanker, config: dict) -> None:
        """ValueStrategy를 초기화한다.

        Args:
            ranker: 멀티팩터 랭커.
            config: 전략 설정. top_n(기본 15) 등.
        """
        super().__init__(config=config)
        self.ranker = ranker
        self.top_n: int = config.get("top_n", 15)
        self.factor_weights: dict[str, float] = {
            "value": 0.4,
            "quality": 0.3,
            "momentum": 0.2,
            "flow": 0.1,
        }

    def generate_signals(
        self,
        universe: list[Stock],
        market_context: dict,
    ) -> list[Signal]:
        """밸류 ���킹 기반 시그널을 생성한다.

        Args:
            universe: 투자 유니버스.
            market_context: {"pulse_signal": str, "pulse_score": float}.

        Returns:
            상위 top_n 종목의 Signal 리스트.
        """
        pulse_signal = market_context.get("pulse_signal", "neutral")

        ranked = self.ranker.rank(universe, strategy_id=self.strategy_id)
        top_signals = ranked[: self.top_n]

        # 중립 시장 → 밸류 전략 강도 1.2배 (불확실성 시 가치주 선호)
        if pulse_signal == "neutral":
            top_signals = [
                Signal(
                    stock=s.stock,
                    score=min(s.score * 1.2, 100.0),
                    factors=s.factors,
                    strategy_id=s.strategy_id,
                    timestamp=s.timestamp,
                )
                for s in top_signals
            ]
            logger.info("중립 시장 — 밸류 시그널 강도 1.2배 증가")

        return top_signals
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/trading/strategy/test_value.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add alphapulse/trading/strategy/value.py tests/trading/strategy/test_value.py
git commit -m "feat(trading): add ValueStrategy with neutral market boost"
```

---

### Task 5: QualityMomentum 전략

**Files:**
- Create: `alphapulse/trading/strategy/quality_momentum.py`
- Test: `tests/trading/strategy/test_quality_momentum.py`

- [ ] **Step 1: Write failing test**

`tests/trading/strategy/test_quality_momentum.py`:
```python
"""QualityMomentum 전략 테스트."""

from unittest.mock import MagicMock

from alphapulse.trading.core.enums import RebalanceFreq
from alphapulse.trading.core.models import Signal, Stock
from alphapulse.trading.strategy.base import BaseStrategy
from alphapulse.trading.strategy.quality_momentum import QualityMomentumStrategy


class TestQualityMomentumStrategy:
    def setup_method(self):
        self.ranker = MagicMock()
        self.config = {"top_n": 5}
        self.strategy = QualityMomentumStrategy(
            ranker=self.ranker,
            config=self.config,
        )
        self.universe = [
            Stock(code="005930", name="삼성전자", market="KOSPI"),
            Stock(code="000660", name="SK하이닉스", market="KOSPI"),
        ]

    def test_is_base_strategy(self):
        assert isinstance(self.strategy, BaseStrategy)

    def test_strategy_id(self):
        assert self.strategy.strategy_id == "quality_momentum"

    def test_rebalance_freq(self):
        assert self.strategy.rebalance_freq == RebalanceFreq.WEEKLY

    def test_top_n_default(self):
        s = QualityMomentumStrategy(ranker=self.ranker, config={})
        assert s.top_n == 15

    def test_factor_weights(self):
        """퀄리티+모멘텀 복합 가중치."""
        assert self.strategy.factor_weights["quality"] == 0.35
        assert self.strategy.factor_weights["momentum"] == 0.35
        assert self.strategy.factor_weights["flow"] == 0.2
        assert self.strategy.factor_weights["volatility"] == 0.1

    def test_generate_signals(self):
        """랭킹 기반 시그널 반환."""
        ranked = [
            Signal(stock=self.universe[0], score=88.0,
                   factors={"quality": 0.9, "momentum": 0.8},
                   strategy_id="quality_momentum"),
            Signal(stock=self.universe[1], score=72.0,
                   factors={"quality": 0.7, "momentum": 0.7},
                   strategy_id="quality_momentum"),
        ]
        self.ranker.rank.return_value = ranked

        ctx = {"pulse_signal": "moderately_bullish", "pulse_score": 40}
        signals = self.strategy.generate_signals(self.universe, ctx)

        assert len(signals) == 2
        assert signals[0].score == 88.0

    def test_strong_bearish_halves_and_reduces(self):
        """강한 매도 우위 → 시그널 강도 0.3배 축소."""
        ranked = [
            Signal(stock=self.universe[0], score=80.0,
                   factors={"quality": 0.8, "momentum": 0.8},
                   strategy_id="quality_momentum"),
        ]
        self.ranker.rank.return_value = ranked

        ctx = {"pulse_signal": "strong_bearish", "pulse_score": -80}
        signals = self.strategy.generate_signals(self.universe, ctx)

        assert signals[0].score == 24.0  # 80 * 0.3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/trading/strategy/test_quality_momentum.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement**

`alphapulse/trading/strategy/quality_momentum.py`:
```python
"""퀄리티+모멘텀 복합 전략.

퀄리티(ROE, 이익 성장)와 모멘텀을 결합 — 주간 리밸런싱.
강한 매도 우위 시 시그널 강도를 크게 축소한다.
"""

import logging

from alphapulse.trading.core.enums import RebalanceFreq
from alphapulse.trading.core.models import Signal, Stock
from alphapulse.trading.screening.ranker import MultiFactorRanker
from alphapulse.trading.strategy.base import BaseStrategy

logger = logging.getLogger(__name__)


class QualityMomentumStrategy(BaseStrategy):
    """���리티 + ��멘텀 복합 전략.

    Attributes:
        strategy_id: "quality_momentum".
        rebalance_freq: 주간 (WEEKLY).
        top_n: 상위 선정 종목 수 (기본 15).
        factor_weights: 팩터별 가중치.
        ranker: MultiFactorRanker 인스턴스.
    """

    strategy_id = "quality_momentum"
    rebalance_freq = RebalanceFreq.WEEKLY

    def __init__(self, ranker: MultiFactorRanker, config: dict) -> None:
        """QualityMomentumStrategy를 초기화한다.

        Args:
            ranker: 멀티팩터 랭커.
            config: 전략 설정. top_n(기본 15) 등.
        """
        super().__init__(config=config)
        self.ranker = ranker
        self.top_n: int = config.get("top_n", 15)
        self.factor_weights: dict[str, float] = {
            "quality": 0.35,
            "momentum": 0.35,
            "flow": 0.2,
            "volatility": 0.1,
        }

    def generate_signals(
        self,
        universe: list[Stock],
        market_context: dict,
    ) -> list[Signal]:
        """퀄리티+모멘텀 랭킹 기반 시그널을 생성한다.

        Args:
            universe: 투자 유니버스.
            market_context: {"pulse_signal": str, "pulse_score": float}.

        Returns:
            상위 top_n 종목의 Signal 리스트.
        """
        pulse_signal = market_context.get("pulse_signal", "neutral")

        ranked = self.ranker.rank(universe, strategy_id=self.strategy_id)
        top_signals = ranked[: self.top_n]

        # 시장 방향에 따른 강도 조정
        dampening = self._get_dampening(pulse_signal)
        if dampening != 1.0:
            top_signals = [
                Signal(
                    stock=s.stock,
                    score=s.score * dampening,
                    factors=s.factors,
                    strategy_id=s.strategy_id,
                    timestamp=s.timestamp,
                )
                for s in top_signals
            ]
            logger.info(
                "시장 상황 '%s' — 퀄리티모멘텀 시그널 강도 %.1f배",
                pulse_signal,
                dampening,
            )

        return top_signals

    @staticmethod
    def _get_dampening(pulse_signal: str) -> float:
        """시장 시그널에 따른 강도 계수를 반환한다.

        Args:
            pulse_signal: Market Pulse 시그널 레���.

        Returns:
            강도 계수 (1.0 = 변동 없음).
        """
        dampening_map = {
            "strong_bullish": 1.0,
            "moderately_bullish": 1.0,
            "neutral": 1.0,
            "moderately_bearish": 0.5,
            "strong_bearish": 0.3,
        }
        return dampening_map.get(pulse_signal, 1.0)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/trading/strategy/test_quality_momentum.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add alphapulse/trading/strategy/quality_momentum.py tests/trading/strategy/test_quality_momentum.py
git commit -m "feat(trading): add QualityMomentumStrategy with market-adaptive dampening"
```

---

### Task 6: StrategyRegistry

**Files:**
- Create: `alphapulse/trading/strategy/registry.py`
- Test: `tests/trading/strategy/test_registry.py`

- [ ] **Step 1: Write failing test**

`tests/trading/strategy/test_registry.py`:
```python
"""StrategyRegistry 테스트."""

import pytest

from alphapulse.trading.core.enums import RebalanceFreq
from alphapulse.trading.core.models import Signal, Stock
from alphapulse.trading.strategy.base import BaseStrategy
from alphapulse.trading.strategy.registry import StrategyRegistry


class StubStrategy(BaseStrategy):
    """테스트용 스텁 전략."""

    strategy_id = "stub"
    rebalance_freq = RebalanceFreq.DAILY

    def generate_signals(self, universe, market_context):
        return []


class AnotherStub(BaseStrategy):
    strategy_id = "another"
    rebalance_freq = RebalanceFreq.WEEKLY

    def generate_signals(self, universe, market_context):
        return []


class TestStrategyRegistry:
    def setup_method(self):
        self.registry = StrategyRegistry()

    def test_register_and_get(self):
        """전략을 등록하고 조회한다."""
        strategy = StubStrategy(config={})
        self.registry.register(strategy)
        assert self.registry.get("stub") is strategy

    def test_get_unknown_raises(self):
        """미등록 전략 조회 시 KeyError."""
        with pytest.raises(KeyError):
            self.registry.get("unknown")

    def test_list_all(self):
        """등록된 전략 ID 목록을 반환한다."""
        self.registry.register(StubStrategy(config={}))
        self.registry.register(AnotherStub(config={}))
        ids = self.registry.list_all()
        assert sorted(ids) == ["another", "stub"]

    def test_list_all_empty(self):
        """빈 레지스트리는 빈 리스트."""
        assert self.registry.list_all() == []

    def test_register_duplicate_overwrites(self):
        """동일 ID 재등록 시 덮어쓴다."""
        s1 = StubStrategy(config={"v": 1})
        s2 = StubStrategy(config={"v": 2})
        self.registry.register(s1)
        self.registry.register(s2)
        assert self.registry.get("stub").config == {"v": 2}

    def test_contains(self):
        """전략 존재 여부 확인."""
        self.registry.register(StubStrategy(config={}))
        assert self.registry.contains("stub") is True
        assert self.registry.contains("missing") is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/trading/strategy/test_registry.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement**

`alphapulse/trading/strategy/registry.py`:
```python
"""전략 레지스트리.

전략 인스턴스를 등록/조회하는 중앙 관리자.
"""

from alphapulse.trading.strategy.base import BaseStrategy


class StrategyRegistry:
    """전략 등록/조회 레지스트리.

    Attributes:
        _strategies: strategy_id → BaseStrategy 매핑.
    """

    def __init__(self) -> None:
        self._strategies: dict[str, BaseStrategy] = {}

    def register(self, strategy: BaseStrategy) -> None:
        """전략을 등록한다.

        Args:
            strategy: 등록할 전략 인스턴스.
        """
        self._strategies[strategy.strategy_id] = strategy

    def get(self, strategy_id: str) -> BaseStrategy:
        """전략을 조회한다.

        Args:
            strategy_id: 전략 고유 식별자.

        Returns:
            등록된 전략 인스턴스.

        Raises:
            KeyError: 미등록 전략.
        """
        if strategy_id not in self._strategies:
            raise KeyError(f"미등록 전략: {strategy_id}")
        return self._strategies[strategy_id]

    def list_all(self) -> list[str]:
        """등록된 전략 ID 목록을 반환한다."""
        return list(self._strategies.keys())

    def contains(self, strategy_id: str) -> bool:
        """전략 등록 여부를 확인한다.

        Args:
            strategy_id: 전략 고�� 식별자.

        Returns:
            등록되어 있으면 True.
        """
        return strategy_id in self._strategies
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/trading/strategy/test_registry.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add alphapulse/trading/strategy/registry.py tests/trading/strategy/test_registry.py
git commit -m "feat(trading): add StrategyRegistry for strategy management"
```

---

### Task 7: StrategyAllocator

**Files:**
- Create: `alphapulse/trading/strategy/allocator.py`
- Test: `tests/trading/strategy/test_allocator.py`

- [ ] **Step 1: Write failing test**

`tests/trading/strategy/test_allocator.py`:
```python
"""StrategyAllocator ���스트."""

import pytest

from alphapulse.trading.core.models import StrategySynthesis
from alphapulse.trading.strategy.allocator import StrategyAllocator


class TestStrategyAllocator:
    def setup_method(self):
        self.base = {
            "topdown_etf": 0.30,
            "momentum": 0.40,
            "value": 0.30,
        }
        self.allocator = StrategyAllocator(base_allocations=self.base)

    def test_base_allocations(self):
        """기본 배분을 반환한다."""
        result = self.allocator.get_allocations()
        assert result == self.base

    def test_allocations_sum_to_one(self):
        """배분 합계는 1.0��다."""
        result = self.allocator.get_allocations()
        assert abs(sum(result.values()) - 1.0) < 1e-9

    def test_get_capital(self):
        """전략별 할당 가능 자금."""
        capital = self.allocator.get_capital("momentum", total_capital=100_000_000)
        assert capital == 40_000_000  # 40%

    def test_adjust_strong_bullish(self):
        """강한 매수 → 종목 전략 비중 증가, ETF 비중 감소."""
        adjusted = self.allocator.adjust_by_market_regime(
            pulse_score=80, ai_synthesis=None,
        )
        assert adjusted["momentum"] > self.base["momentum"]
        assert adjusted["topdown_etf"] < self.base["topdown_etf"]
        assert abs(sum(adjusted.values()) - 1.0) < 1e-9

    def test_adjust_strong_bearish(self):
        """강한 매도 → ETF 비중 증가, 종목 전략 비중 감소."""
        adjusted = self.allocator.adjust_by_market_regime(
            pulse_score=-80, ai_synthesis=None,
        )
        assert adjusted["topdown_etf"] > self.base["topdown_etf"]
        assert adjusted["momentum"] < self.base["momentum"]
        assert abs(sum(adjusted.values()) - 1.0) < 1e-9

    def test_adjust_neutral(self):
        """중립 → 밸류 비중 증가."""
        adjusted = self.allocator.adjust_by_market_regime(
            pulse_score=5, ai_synthesis=None,
        )
        assert adjusted["value"] >= self.base["value"]
        assert abs(sum(adjusted.values()) - 1.0) < 1e-9

    def test_ai_synthesis_adjustment(self):
        """AI 종합 판단의 allocation_adjustment를 반영한다."""
        synthesis = StrategySynthesis(
            market_view="매수 우위",
            conviction_level=0.8,
            allocation_adjustment={"topdown_etf": 0.20, "momentum": 0.50, "value": 0.30},
            stock_opinions=[],
            risk_warnings=[],
            reasoning="외국인 순매수 지속",
        )
        adjusted = self.allocator.adjust_by_market_regime(
            pulse_score=40, ai_synthesis=synthesis,
        )
        # AI 조정이 반영되어 momentum이 증가해야 함
        assert adjusted["momentum"] > self.base["momentum"]
        assert abs(sum(adjusted.values()) - 1.0) < 1e-9

    def test_ai_low_conviction_ignored(self):
        """AI 확신도 0.3 미만 → AI 조정 무��."""
        synthesis = StrategySynthesis(
            market_view="불확실",
            conviction_level=0.2,
            allocation_adjustment={"topdown_etf": 0.10, "momentum": 0.80, "value": 0.10},
            stock_opinions=[],
            risk_warnings=["확신도 매우 낮음"],
            reasoning="불확실",
        )
        adjusted = self.allocator.adjust_by_market_regime(
            pulse_score=40, ai_synthesis=synthesis,
        )
        # 확신도 낮아서 AI 조정 무시 → 규칙 기반만 적용
        # momentum이 0.80까지 올라가지 않아야 함
        assert adjusted["momentum"] < 0.70

    def test_update_allocations(self):
        """배분 비율을 갱신한다."""
        new = {"topdown_etf": 0.40, "momentum": 0.30, "value": 0.30}
        self.allocator.update_allocations(new)
        assert self.allocator.get_allocations() == new
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/trading/strategy/test_allocator.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement**

`alphapulse/trading/strategy/allocator.py`:
```python
"""멀티전략 자금 배분기.

Market Pulse + AI 종합 판단에 따라 전략별 자금을 동적 배분한다.
"""

import logging

from alphapulse.trading.core.models import StrategySynthesis

logger = logging.getLogger(__name__)

# AI 확신도 최소 임계값 — 이 이하면 AI 조정 무시
_MIN_AI_CONVICTION = 0.3

# AI 배분 가중치 (규칙 기반과의 블렌딩)
_AI_BLEND_WEIGHT = 0.4


class StrategyAllocator:
    """멀티전략 간 자금 배분 관리자.

    Attributes:
        base_allocations: 기본 배분 비율 (합계 1.0).
        current_allocations: 현재 적용 중인 배분 비율.
    """

    def __init__(self, base_allocations: dict[str, float]) -> None:
        """StrategyAllocator를 초기화한다.

        Args:
            base_allocations: 전략ID → 배분비율 딕셔너리 (합계 1.0).
        """
        self.base_allocations = dict(base_allocations)
        self.current_allocations = dict(base_allocations)

    def get_allocations(self) -> dict[str, float]:
        """현재 배분 비율을 반환한다."""
        return dict(self.current_allocations)

    def get_capital(self, strategy_id: str, total_capital: float) -> float:
        """전략별 할당 가능 자금을 반���한다.

        Args:
            strategy_id: 전략 ID.
            total_capital: 총 투자 자본.

        Returns:
            해당 전략에 배분된 자금 (원).
        """
        ratio = self.current_allocations.get(strategy_id, 0)
        return total_capital * ratio

    def adjust_by_market_regime(
        self,
        pulse_score: float,
        ai_synthesis: StrategySynthesis | None,
    ) -> dict[str, float]:
        """시장 상황에 따라 배분을 동적 조정한다.

        Args:
            pulse_score: Market Pulse 점수 (-100 ~ +100).
            ai_synthesis: AI 종합 판단 결과 (없으면 None).

        Returns:
            조정된 배분 비율 딕셔너리 (합계 1.0).
        """
        # 1단계: 규칙 기반 조정
        adjusted = self._rule_based_adjustment(pulse_score)

        # 2단계: AI 종합 판단 반영
        if (
            ai_synthesis is not None
            and ai_synthesis.conviction_level >= _MIN_AI_CONVICTION
            and ai_synthesis.allocation_adjustment
        ):
            ai_alloc = ai_synthesis.allocation_adjustment
            # 규칙 기반과 AI 제안의 가중 평균
            for key in adjusted:
                if key in ai_alloc:
                    rule_val = adjusted[key]
                    ai_val = ai_alloc[key]
                    adjusted[key] = (
                        rule_val * (1 - _AI_BLEND_WEIGHT)
                        + ai_val * _AI_BLEND_WEIGHT
                    )
            logger.info(
                "AI 종합 판단 반영 (확신도: %.2f)", ai_synthesis.conviction_level
            )

        # 정규화 (합계 = 1.0)
        adjusted = self._normalize(adjusted)
        self.current_allocations = adjusted
        return dict(adjusted)

    def update_allocations(self, new_allocations: dict[str, float]) -> None:
        """배분 비율을 직접 갱신한다.

        Args:
            new_allocations: 새 배분 비율 (합계 1.0).
        """
        self.current_allocations = dict(new_allocations)

    def _rule_based_adjustment(
        self, pulse_score: float
    ) -> dict[str, float]:
        """규칙 기반 배분 조정을 수행한다.

        Args:
            pulse_score: Market Pulse 점수 (-100 ~ +100).

        Returns:
            조정된 배분 딕셔너리.
        """
        adjusted = dict(self.base_allocations)

        etf_key = "topdown_etf"
        stock_keys = [k for k in adjusted if k != etf_key]

        if pulse_score > 50:
            # 강한 매수 → 종목 전략 비중 증가
            shift = 0.10
            adjusted[etf_key] = max(adjusted[etf_key] - shift, 0.10)
            bonus = shift / len(stock_keys) if stock_keys else 0
            for k in stock_keys:
                adjusted[k] += bonus
        elif pulse_score < -50:
            # 강한 매도 → ETF 비중 증가
            shift = 0.15
            adjusted[etf_key] = min(adjusted[etf_key] + shift, 0.60)
            penalty = shift / len(stock_keys) if stock_keys else 0
            for k in stock_keys:
                adjusted[k] = max(adjusted[k] - penalty, 0.05)
        elif -10 <= pulse_score <= 10:
            # 중립 → 밸류 비중 약간 증가
            if "value" in adjusted:
                shift = 0.05
                adjusted["value"] += shift
                for k in stock_keys:
                    if k != "value":
                        adjusted[k] -= shift / (len(stock_keys) - 1)

        return adjusted

    @staticmethod
    def _normalize(allocations: dict[str, float]) -> dict[str, float]:
        """배분 비율을 정규화하여 합계 1.0으로 만든다."""
        total = sum(allocations.values())
        if total <= 0:
            n = len(allocations)
            return {k: 1.0 / n for k in allocations}
        return {k: v / total for k, v in allocations.items()}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/trading/strategy/test_allocator.py -v`
Expected: 9 passed

- [ ] **Step 5: Commit**

```bash
git add alphapulse/trading/strategy/allocator.py tests/trading/strategy/test_allocator.py
git commit -m "feat(trading): add StrategyAllocator with AI synthesis blending"
```

---

### Task 8: AI Strategy Synthesizer (async)

**Files:**
- Create: `alphapulse/trading/strategy/ai_synthesizer.py`
- Test: `tests/trading/strategy/test_ai_synthesizer.py`

- [ ] **Step 1: Write failing test**

`tests/trading/strategy/test_ai_synthesizer.py`:
```python
"""AI Strategy Synthesizer 테스트."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from alphapulse.trading.core.models import (
    PortfolioSnapshot,
    Signal,
    Stock,
    StockOpinion,
    StrategySynthesis,
)
from alphapulse.trading.strategy.ai_synthesizer import StrategyAISynthesizer


@pytest.fixture
def synthesizer():
    return StrategyAISynthesizer()


@pytest.fixture
def sample_inputs():
    stock = Stock(code="005930", name="삼성전자", market="KOSPI")
    return {
        "pulse_result": {
            "date": "20260409",
            "score": 35.2,
            "signal": "매수 우위 (Moderately Bullish)",
            "indicator_scores": {"investor_flow": 42},
            "details": {},
        },
        "ranked_stocks": [
            Signal(stock=stock, score=80.0,
                   factors={"momentum": 0.8}, strategy_id="momentum"),
        ],
        "strategy_signals": {
            "momentum": [
                Signal(stock=stock, score=80.0,
                       factors={"momentum": 0.8}, strategy_id="momentum"),
            ],
        },
        "content_summaries": ["외국인 순매수 지속"],
        "feedback_context": "적중률 65%",
        "current_portfolio": PortfolioSnapshot(
            date="20260409", cash=50_000_000, positions=[],
            total_value=100_000_000, daily_return=0.5,
            cumulative_return=8.3, drawdown=-2.1,
        ),
    }


class TestStrategyAISynthesizer:
    def test_fallback_returns_valid_synthesis(self, synthesizer):
        """LLM 실패 시 _fallback()이 유효한 StrategySynthesis를 반환한다."""
        result = synthesizer._fallback()
        assert isinstance(result, StrategySynthesis)
        assert result.conviction_level == 0.5
        assert "실패" in result.risk_warnings[0] or "규칙" in result.reasoning

    def test_build_prompt(self, synthesizer, sample_inputs):
        """프롬프트가 주요 정보를 포함한다."""
        prompt = synthesizer._build_prompt(**sample_inputs)
        assert "35.2" in prompt  # pulse_score
        assert "삼성전자" in prompt
        assert "외국인" in prompt

    def test_parse_response_valid(self, synthesizer):
        """유효한 LLM 응답을 StrategySynthesis로 파싱한다."""
        response_text = (
            '{"market_view": "매수 우위", "conviction_level": 0.72, '
            '"allocation_adjustment": {"topdown_etf": 0.3, "momentum": 0.4, "value": 0.3}, '
            '"stock_opinions": [], "risk_warnings": ["변동성 주의"], '
            '"reasoning": "외국인 매수 지속"}'
        )
        result = synthesizer._parse_response(response_text)
        assert isinstance(result, StrategySynthesis)
        assert result.conviction_level == 0.72
        assert result.market_view == "매수 우위"

    def test_parse_response_invalid_falls_back(self, synthesizer):
        """잘못된 LLM 응답 시 None을 반환한다."""
        result = synthesizer._parse_response("this is not json")
        assert result is None

    def test_synthesize_llm_failure_uses_fallback(self, synthesizer, sample_inputs):
        """LLM 호출 실패 시 _fallback()을 사용한다."""
        with patch.object(
            synthesizer, "_call_llm", side_effect=Exception("LLM 에러")
        ):
            result = asyncio.run(synthesizer.synthesize(**sample_inputs))
            assert isinstance(result, StrategySynthesis)
            assert result.conviction_level == 0.5

    def test_synthesize_success(self, synthesizer, sample_inputs):
        """LLM 성공 시 정상 StrategySynthesis를 반환한다."""
        mock_response = (
            '{"market_view": "매수 우위", "conviction_level": 0.8, '
            '"allocation_adjustment": {"topdown_etf": 0.25}, '
            '"stock_opinions": [], "risk_warnings": [], '
            '"reasoning": "분석 완료"}'
        )
        with patch.object(
            synthesizer, "_call_llm", return_value=mock_response
        ):
            result = asyncio.run(synthesizer.synthesize(**sample_inputs))
            assert result.conviction_level == 0.8
            assert result.market_view == "매수 우위"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/trading/strategy/test_ai_synthesizer.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement**

`alphapulse/trading/strategy/ai_synthesizer.py`:
```python
"""AI 전략 종합 판단.

정량(시그널, 팩터) + 정성(콘텐츠) 분석을 LLM으로 종합하여
최종 전략 배분 및 종목 의견을 생성한다.

LLM 호출은 asyncio.to_thread()로 non-blocking 래핑한다.
"""

import asyncio
import json
import logging

from alphapulse.trading.core.models import (
    PortfolioSnapshot,
    Signal,
    StockOpinion,
    StrategySynthesis,
)

logger = logging.getLogger(__name__)


class StrategyAISynthesizer:
    """LLM 기반 전략 종합 판단.

    LLM 실패 시 규칙 기반 _fallback()으로 안전하게 실행��다.
    """

    def __init__(self) -> None:
        self._client = None  # google.genai.Client — lazy init
        self._model_name = "gemini-2.0-flash"

    async def synthesize(
        self,
        pulse_result: dict,
        ranked_stocks: list[Signal],
        strategy_signals: dict[str, list[Signal]],
        content_summaries: list[str],
        feedback_context: str | None,
        current_portfolio: PortfolioSnapshot,
    ) -> StrategySynthesis:
        """전체 분석 결과를 종합하여 최종 전략 판단을 생��한다.

        Args:
            pulse_result: Market Pulse 11개 지표 결과.
            ranked_stocks: 팩터 스크리닝 상위 종목 시그널.
            strategy_signals: 전략별 시그널 딕셔너리.
            content_summaries: 콘텐츠 분석 결과 문자열 리스��.
            feedback_context: 적중률/피드백 문자열 (없으면 None).
            current_portfolio: 현재 포트폴리오 스냅샷.

        Returns:
            AI 종합 판단 결과.
        """
        try:
            prompt = self._build_prompt(
                pulse_result=pulse_result,
                ranked_stocks=ranked_stocks,
                strategy_signals=strategy_signals,
                content_summaries=content_summaries,
                feedback_context=feedback_context,
                current_portfolio=current_portfolio,
            )
            response_text = await self._call_llm(prompt)
            result = self._parse_response(response_text)
            if result is None:
                logger.warning("LLM 응답 파싱 실패 → _fallback() 사용")
                return self._fallback()
            return result
        except Exception:
            logger.exception("AI 종합 판단 실패 → _fallback() 사용")
            return self._fallback()

    async def _call_llm(self, prompt: str) -> str:
        """asyncio.to_thread()로 sync genai API를 non-blocking 호출한다.

        Args:
            prompt: LLM 프롬프트 ��자열.

        Returns:
            LLM 응답 텍스��.
        """
        if self._client is None:
            from google import genai

            self._client = genai.Client()

        response = await asyncio.to_thread(
            self._client.models.generate_content,
            model=self._model_name,
            contents=prompt,
        )
        return response.text

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

        Args:
            pulse_result: Market Pulse 결과.
            ranked_stocks: 상위 종목 시그널.
            strategy_signals: 전략별 시그널.
            content_summaries: 콘텐츠 분석.
            feedback_context: 피드백 문���.
            current_portfolio: 현재 포트폴리��.

        Returns:
            프롬프트 문자열.
        """
        # 상위 종목 요약
        top_stocks = ""
        for s in ranked_stocks[:10]:
            top_stocks += f"  - {s.stock.name}({s.stock.code}): 점수 {s.score:.1f}\n"

        # 전략별 시그널 요약
        strategy_summary = ""
        for sid, sigs in strategy_signals.items():
            strategy_summary += f"  [{sid}] {len(sigs)}개 시그널\n"

        # 콘텐츠 요약
        content_text = "\n".join(
            f"  - {c}" for c in content_summaries
        ) if content_summaries else "  (없음)"

        # 피드백
        feedback_text = feedback_context or "(피드백 데이터 없음)"

        return f"""당신은 한국 주식시장 투자 전략 분석가입니다.

아래 정량/정성 분석 결과를 종합하여 JSON으로 응답하세요.

## 시장 상황 (Market Pulse)
- 점수: {pulse_result.get("score", 0)}
- 시그널: {pulse_result.get("signal", "N/A")}
- 지표: {json.dumps(pulse_result.get("indicator_scores", {}), ensure_ascii=False)}

## 팩터 스크리닝 상위 종목
{top_stocks}

## 전략별 시그널
{strategy_summary}

## 콘텐츠 분석
{content_text}

## 과거 성과 피드백
{feedback_text}

## 현재 포트폴리오
- 총 자산: {current_portfolio.total_value:,.0f}원
- 현금: {current_portfolio.cash:,.0f}원
- 일간 수익률: {current_portfolio.daily_return:.2f}%
- 누적 수익률: {current_portfolio.cumulative_return:.2f}%
- 드로다운: {current_portfolio.drawdown:.2f}%

## 응답 형식 (JSON)
{{
    "market_view": "시장 판단 요약",
    "conviction_level": 0.0~1.0,
    "allocation_adjustment": {{"topdown_etf": 0.3, "momentum": 0.4, "value": 0.3}},
    "stock_opinions": [],
    "risk_warnings": ["경고 메시지"],
    "reasoning": "판단 근거"
}}"""

    def _parse_response(self, response_text: str) -> StrategySynthesis | None:
        """LLM 응답 텍스트를 StrategySynthesis로 파싱한다.

        Args:
            response_text: LLM 응답 텍스트 (JSON).

        Returns:
            파싱된 StrategySynthesis. 실패 시 None.
        """
        try:
            # JSON 블록 추출 (마크다운 코드블록 처리)
            text = response_text.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()

            data = json.loads(text)
            return StrategySynthesis(
                market_view=data.get("market_view", ""),
                conviction_level=float(data.get("conviction_level", 0.5)),
                allocation_adjustment=data.get("allocation_adjustment", {}),
                stock_opinions=[
                    StockOpinion(
                        stock=Stock(
                            code=op.get("code", ""),
                            name=op.get("name", ""),
                            market=op.get("market", "KOSPI"),
                        ),
                        action=op.get("action", "유지"),
                        reason=op.get("reason", ""),
                        confidence=float(op.get("confidence", 0.5)),
                    )
                    for op in data.get("stock_opinions", [])
                ],
                risk_warnings=data.get("risk_warnings", []),
                reasoning=data.get("reasoning", ""),
            )
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            logger.warning("LLM 응답 파싱 실패: %s", response_text[:200])
            return None

    def _fallback(self) -> StrategySynthesis:
        """LLM 실패 시 규칙 기반 기본 판단을 반환한다.

        Returns:
            안전한 기본 StrategySynthesis.
        """
        return StrategySynthesis(
            market_view="AI 분석 불가 — 정량 시그널 기반 실행",
            conviction_level=0.5,
            allocation_adjustment={},
            stock_opinions=[],
            risk_warnings=["AI 종합 판단 실패. 규칙 기반으로 실행됨."],
            reasoning="LLM 호출 실패로 정량 시그널만 사용",
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/trading/strategy/test_ai_synthesizer.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add alphapulse/trading/strategy/ai_synthesizer.py tests/trading/strategy/test_ai_synthesizer.py
git commit -m "feat(trading): add StrategyAISynthesizer with async LLM + fallback"
```

---

## Phase ⑤: Portfolio Management

---

### Task 9: PositionSizer

**Files:**
- Create: `alphapulse/trading/portfolio/__init__.py`
- Create: `alphapulse/trading/portfolio/position_sizer.py`
- Test: `tests/trading/portfolio/__init__.py`
- Test: `tests/trading/portfolio/test_position_sizer.py`

- [ ] **Step 1: Create package directories**

```bash
mkdir -p alphapulse/trading/portfolio
mkdir -p tests/trading/portfolio
```

Create `tests/trading/portfolio/__init__.py` (빈 파일).

`alphapulse/trading/portfolio/__init__.py`:
```python
"""포트폴리오 관리."""
```

- [ ] **Step 2: Write failing test**

`tests/trading/portfolio/test_position_sizer.py`:
```python
"""PositionSizer 테스트."""

import pytest

from alphapulse.trading.core.models import Stock, StockOpinion
from alphapulse.trading.portfolio.position_sizer import PositionSizer


@pytest.fixture
def sizer():
    return PositionSizer()


class TestEqualWeight:
    def test_equal_weight_10(self, sizer):
        """10종목 균등 배분 → 각 10%."""
        assert sizer.equal_weight(10) == pytest.approx(0.1)

    def test_equal_weight_1(self, sizer):
        """1종목 → 100%."""
        assert sizer.equal_weight(1) == pytest.approx(1.0)


class TestVolatilityAdjusted:
    def test_basic(self, sizer):
        """변동성 낮을수록 비중 높음."""
        vols = {
            "005930": 0.20,  # 낮은 변동성 → 높은 비중
            "035720": 0.40,  # 높은 변동성 → ��은 비중
        }
        weights = sizer.volatility_adjusted(vols, target_vol=0.15)
        assert weights["005930"] > weights["035720"]
        assert abs(sum(weights.values()) - 1.0) < 1e-9

    def test_single_stock(self, sizer):
        """1종목이면 비중 100%."""
        weights = sizer.volatility_adjusted({"005930": 0.3})
        assert weights["005930"] == pytest.approx(1.0)


class TestKelly:
    def test_positive_edge(self, sizer):
        """양의 엣지 → 양의 비중 (half-kelly)."""
        weight = sizer.kelly(win_rate=0.6, avg_win=0.03, avg_loss=0.02)
        assert weight > 0

    def test_no_edge(self, sizer):
        """엣지 없음 → 비중 0."""
        weight = sizer.kelly(win_rate=0.5, avg_win=0.02, avg_loss=0.02)
        assert weight == 0.0

    def test_negative_edge(self, sizer):
        """음의 엣지 → 비중 0 (음수 방지)."""
        weight = sizer.kelly(win_rate=0.3, avg_win=0.02, avg_loss=0.03)
        assert weight == 0.0

    def test_half_kelly(self, sizer):
        """half-kelly 적용 확인."""
        # full kelly = 0.6 - 0.4/(0.04/0.02) = 0.6 - 0.2 = 0.4
        # half kelly = 0.2
        weight = sizer.kelly(win_rate=0.6, avg_win=0.04, avg_loss=0.02)
        assert weight == pytest.approx(0.2)


class TestAIAdjusted:
    def test_high_confidence_boosts(self, sizer):
        """높은 확신도 → 비중 1.2배."""
        stock = Stock(code="005930", name="삼성전자", market="KOSPI")
        opinion = StockOpinion(stock=stock, action="매수",
                               reason="강세", confidence=0.8)
        adjusted = sizer.ai_adjusted(0.05, opinion, max_weight=0.10)
        assert adjusted == pytest.approx(0.06)  # 0.05 * 1.2

    def test_low_confidence_reduces(self, sizer):
        """낮은 확신도 → 비중 0.7배."""
        stock = Stock(code="005930", name="삼성전자", market="KOSPI")
        opinion = StockOpinion(stock=stock, action="유지",
                               reason="불��실", confidence=0.2)
        adjusted = sizer.ai_adjusted(0.05, opinion, max_weight=0.10)
        assert adjusted == pytest.approx(0.035)  # 0.05 * 0.7

    def test_sell_opinion_zero(self, sizer):
        """매도 의견 → 비중 0."""
        stock = Stock(code="005930", name="삼성전자", market="KOSPI")
        opinion = StockOpinion(stock=stock, action="매도",
                               reason="하락 전환", confidence=0.9)
        adjusted = sizer.ai_adjusted(0.05, opinion, max_weight=0.10)
        assert adjusted == 0.0

    def test_max_weight_cap(self, sizer):
        """최대 비중 상한 적용."""
        stock = Stock(code="005930", name="삼성전자", market="KOSPI")
        opinion = StockOpinion(stock=stock, action="강력매수",
                               reason="최강", confidence=0.95)
        adjusted = sizer.ai_adjusted(0.09, opinion, max_weight=0.10)
        assert adjusted <= 0.10
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/trading/portfolio/test_position_sizer.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 4: Implement**

`alphapulse/trading/portfolio/position_sizer.py`:
```python
"""포지션 사이징.

종목당 투자 비중을 결정하는 다양한 방법을 제공한다.
"""

import logging

from alphapulse.trading.core.models import StockOpinion

logger = logging.getLogger(__name__)


class PositionSizer:
    """종목당 투자 비중 결정 도구.

    균등 배분, 변동성 조정, 켈리 기준, AI 조정을 지원한다.
    """

    def equal_weight(self, n_stocks: int) -> float:
        """균등 배분 비중을 계산한다.

        Args:
            n_stocks: 종목 수.

        Returns:
            종목당 비중 (0~1).
        """
        if n_stocks <= 0:
            return 0.0
        return 1.0 / n_stocks

    def volatility_adjusted(
        self,
        volatilities: dict[str, float],
        target_vol: float = 0.15,
    ) -> dict[str, float]:
        """변동성 역수 비중을 계산한다.

        변동성이 낮을수록 비중이 높아��다.

        Args:
            volatilities: 종목코드 → 연 변동성 매핑.
            target_vol: 포트폴리오 목표 변동성 (참조용).

        Returns:
            종목코드 → 비중 매핑 (합계 1.0).
        """
        inv_vols = {}
        for code, vol in volatilities.items():
            inv_vols[code] = 1.0 / vol if vol > 0 else 0.0

        total = sum(inv_vols.values())
        if total <= 0:
            n = len(volatilities)
            return {k: 1.0 / n for k in volatilities} if n > 0 else {}

        return {k: v / total for k, v in inv_vols.items()}

    def kelly(
        self,
        win_rate: float,
        avg_win: float,
        avg_loss: float,
    ) -> float:
        """켈리 기준 최적 비중을 계산한다 (half-kelly).

        Args:
            win_rate: 승률 (0~1).
            avg_win: 평균 수익 (양수).
            avg_loss: 평균 손실 (양수).

        Returns:
            최적 투자 비중 (0 이상, half-kelly).
        """
        if avg_loss <= 0 or avg_win <= 0:
            return 0.0
        kelly_fraction = win_rate - (1 - win_rate) / (avg_win / avg_loss)
        return max(0.0, kelly_fraction * 0.5)

    def ai_adjusted(
        self,
        base_weight: float,
        opinion: StockOpinion,
        max_weight: float = 0.10,
    ) -> float:
        """AI 확신도를 반영하여 비중을 조정한다.

        Args:
            base_weight: ���본 비중 (0~1).
            opinion: AI 종목별 의견.
            max_weight: 최대 허용 비중.

        Returns:
            조정된 비중 (0~max_weight).
        """
        if opinion.action in ("매도", "강력매도"):
            return 0.0

        if opinion.confidence > 0.7:
            adjusted = base_weight * 1.2
        elif opinion.confidence < 0.3:
            adjusted = base_weight * 0.7
        else:
            adjusted = base_weight

        return min(adjusted, max_weight)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/trading/portfolio/test_position_sizer.py -v`
Expected: 10 passed

- [ ] **Step 6: Commit**

```bash
git add alphapulse/trading/portfolio/ tests/trading/portfolio/
git commit -m "feat(trading): add PositionSizer (equal, volatility, kelly, AI-adjusted)"
```

---

### Task 10: PortfolioOptimizer (mean-variance, risk parity)

**Files:**
- Create: `alphapulse/trading/portfolio/optimizer.py`
- Test: `tests/trading/portfolio/test_optimizer.py`

- [ ] **Step 1: Write failing test**

`tests/trading/portfolio/test_optimizer.py`:
```python
"""PortfolioOptimizer 테스트."""

import numpy as np
import pytest

from alphapulse.trading.portfolio.optimizer import PortfolioOptimizer


@pytest.fixture
def optimizer():
    return PortfolioOptimizer()


@pytest.fixture
def cov_matrix():
    """2종목 공분산 행렬."""
    return np.array([
        [0.04, 0.01],   # 종목A: 변동성 20%
        [0.01, 0.09],   # 종목B: 변동성 30%
    ])


@pytest.fixture
def expected_returns():
    """2종목 기대수���률."""
    return np.array([0.10, 0.15])


class TestMeanVariance:
    def test_weights_sum_to_one(self, optimizer, expected_returns, cov_matrix):
        """비중 합계가 1.0이다."""
        weights = optimizer.mean_variance(expected_returns, cov_matrix)
        assert abs(sum(weights) - 1.0) < 1e-6

    def test_no_negative_weights(self, optimizer, expected_returns, cov_matrix):
        """롱 온리 — 음수 비중 없음."""
        weights = optimizer.mean_variance(expected_returns, cov_matrix)
        assert all(w >= -1e-9 for w in weights)

    def test_max_weight_constraint(self, optimizer, expected_returns, cov_matrix):
        """종목당 최대 비중 제약."""
        weights = optimizer.mean_variance(
            expected_returns, cov_matrix, max_weight=0.60,
        )
        assert all(w <= 0.60 + 1e-6 for w in weights)

    def test_single_stock(self, optimizer):
        """1종목이면 비중 100%."""
        ret = np.array([0.10])
        cov = np.array([[0.04]])
        weights = optimizer.mean_variance(ret, cov)
        assert weights[0] == pytest.approx(1.0, abs=1e-4)


class TestRiskParity:
    def test_weights_sum_to_one(self, optimizer, cov_matrix):
        """비중 합계가 1.0이다."""
        weights = optimizer.risk_parity(cov_matrix)
        assert abs(sum(weights) - 1.0) < 1e-6

    def test_risk_contributions_equal(self, optimizer, cov_matrix):
        """리스크 기여도가 균등해야 한다."""
        weights = optimizer.risk_parity(cov_matrix)
        # 리스크 기여도 = w_i * (Sigma @ w)_i / sigma_p
        marginal = cov_matrix @ weights
        risk_contrib = weights * marginal
        # 균등 검증 (상대 오차 20% 이내)
        avg_rc = np.mean(risk_contrib)
        for rc in risk_contrib:
            assert abs(rc - avg_rc) / avg_rc < 0.20

    def test_low_vol_gets_more_weight(self, optimizer, cov_matrix):
        """변동성 낮은 종목이 더 큰 비중."""
        weights = optimizer.risk_parity(cov_matrix)
        assert weights[0] > weights[1]  # 종목A(20%) > 종목B(30%)


class TestMinVariance:
    def test_weights_sum_to_one(self, optimizer, cov_matrix):
        weights = optimizer.min_variance(cov_matrix)
        assert abs(sum(weights) - 1.0) < 1e-6

    def test_no_negative_weights(self, optimizer, cov_matrix):
        weights = optimizer.min_variance(cov_matrix)
        assert all(w >= -1e-9 for w in weights)


class TestSelectMethod:
    def test_strong_bullish(self, optimizer):
        ctx = {"pulse_signal": "strong_bullish", "pulse_score": 80}
        assert optimizer.select_method(ctx) == "mean_variance"

    def test_neutral(self, optimizer):
        ctx = {"pulse_signal": "neutral", "pulse_score": 0}
        assert optimizer.select_method(ctx) == "risk_parity"

    def test_strong_bearish(self, optimizer):
        ctx = {"pulse_signal": "strong_bearish", "pulse_score": -80}
        assert optimizer.select_method(ctx) == "min_variance"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/trading/portfolio/test_optimizer.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement**

`alphapulse/trading/portfolio/optimizer.py`:
```python
"""포트폴리오 최적화.

평균-분산(Markowitz), 리스크 패리티, 최소 분산 최적화를 제공한다.
scipy.optimize를 사용한다.
"""

import logging

import numpy as np
from scipy.optimize import minimize

logger = logging.getLogger(__name__)


class PortfolioOptimizer:
    """수학적 포트폴리오 최적화.

    세 가지 최적화 방법을 제공하며, 시장 상황에 따라 자동 선택한다.
    """

    def mean_variance(
        self,
        expected_returns: np.ndarray,
        cov_matrix: np.ndarray,
        max_weight: float = 1.0,
        risk_free_rate: float = 0.035,
    ) -> np.ndarray:
        """마코위츠 평균-분산 최적화 (최대 샤프 비율).

        Args:
            expected_returns: 종목별 기대수익률 벡터.
            cov_matrix: 공분산 행렬.
            max_weight: 종목당 최대 비중.
            risk_free_rate: 무위험 이자율 (연).

        Returns:
            최적 비중 배열 (합계 1.0).
        """
        n = len(expected_returns)
        if n == 1:
            return np.array([1.0])

        def neg_sharpe(w):
            port_ret = w @ expected_returns
            port_vol = np.sqrt(w @ cov_matrix @ w)
            if port_vol < 1e-10:
                return 0.0
            return -(port_ret - risk_free_rate) / port_vol

        constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]
        bounds = [(0.0, max_weight)] * n
        x0 = np.ones(n) / n

        result = minimize(
            neg_sharpe,
            x0,
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
            options={"maxiter": 1000},
        )

        if result.success:
            weights = np.maximum(result.x, 0)
            return weights / weights.sum()

        logger.warning("평균-분산 최적화 실패 → 균등 배분")
        return np.ones(n) / n

    def risk_parity(self, cov_matrix: np.ndarray) -> np.ndarray:
        """리스크 패리티 최적화.

        각 종목의 리스크 기여도를 균등화한다.

        Args:
            cov_matrix: 공분산 행렬.

        Returns:
            최적 비중 배열 (합계 1.0).
        """
        n = cov_matrix.shape[0]
        if n == 1:
            return np.array([1.0])

        def risk_parity_obj(w):
            sigma_p = np.sqrt(w @ cov_matrix @ w)
            if sigma_p < 1e-10:
                return 0.0
            marginal = cov_matrix @ w
            risk_contrib = w * marginal / sigma_p
            target_rc = sigma_p / n
            return np.sum((risk_contrib - target_rc) ** 2)

        constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]
        bounds = [(0.01, 1.0)] * n
        x0 = np.ones(n) / n

        result = minimize(
            risk_parity_obj,
            x0,
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
            options={"maxiter": 1000},
        )

        if result.success:
            weights = np.maximum(result.x, 0)
            return weights / weights.sum()

        logger.warning("리스크 패리티 최적화 실패 → 균등 배분")
        return np.ones(n) / n

    def min_variance(self, cov_matrix: np.ndarray) -> np.ndarray:
        """최소 분산 포트폴리오.

        포트폴리오 전체 변동성을 최소화한다.

        Args:
            cov_matrix: ��분산 행렬.

        Returns:
            최적 비중 배열 (합계 1.0).
        """
        n = cov_matrix.shape[0]
        if n == 1:
            return np.array([1.0])

        def portfolio_variance(w):
            return w @ cov_matrix @ w

        constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]
        bounds = [(0.0, 1.0)] * n
        x0 = np.ones(n) / n

        result = minimize(
            portfolio_variance,
            x0,
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
            options={"maxiter": 1000},
        )

        if result.success:
            weights = np.maximum(result.x, 0)
            return weights / weights.sum()

        logger.warning("최소 분산 최적화 실패 → 균등 배분")
        return np.ones(n) / n

    def select_method(self, market_context: dict) -> str:
        """시장 상황에 따라 최적화 방법을 자동 선택한다.

        Args:
            market_context: {"pulse_signal": str, "pulse_score": float}.

        Returns:
            최적화 방법 문자열 ("mean_variance" | "risk_parity" | "min_variance").
        """
        signal = market_context.get("pulse_signal", "neutral")

        if signal in ("strong_bullish", "moderately_bullish"):
            return "mean_variance"
        elif signal in ("strong_bearish",):
            return "min_variance"
        else:
            return "risk_parity"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/trading/portfolio/test_optimizer.py -v`
Expected: 10 passed

- [ ] **Step 5: Commit**

```bash
git add alphapulse/trading/portfolio/optimizer.py tests/trading/portfolio/test_optimizer.py
git commit -m "feat(trading): add PortfolioOptimizer (mean-variance, risk parity, min variance)"
```

---

### Task 11: Rebalancer (주문 생성)

**Files:**
- Create: `alphapulse/trading/portfolio/rebalancer.py`
- Test: `tests/trading/portfolio/test_rebalancer.py`

- [ ] **Step 1: Write failing test**

`tests/trading/portfolio/test_rebalancer.py`:
```python
"""Rebalancer 테스트."""

import pytest

from alphapulse.trading.core.enums import Side
from alphapulse.trading.core.models import Order, PortfolioSnapshot, Position, Stock
from alphapulse.trading.portfolio.rebalancer import Rebalancer


@pytest.fixture
def samsung():
    return Stock(code="005930", name="삼성전자", market="KOSPI")


@pytest.fixture
def hynix():
    return Stock(code="000660", name="SK하이닉스", market="KOSPI")


@pytest.fixture
def kakao():
    return Stock(code="035720", name="카카오", market="KOSPI")


@pytest.fixture
def rebalancer():
    return Rebalancer(min_trade_amount=100_000)


class TestGenerateOrders:
    def test_buy_new_stock(self, rebalancer, samsung):
        """신규 종목 매수 주문 생성."""
        current = PortfolioSnapshot(
            date="20260409", cash=10_000_000, positions=[],
            total_value=10_000_000, daily_return=0.0,
            cumulative_return=0.0, drawdown=0.0,
        )
        target_weights = {"005930": 0.50}
        prices = {"005930": 72000}

        orders = rebalancer.generate_orders(
            target_weights=target_weights,
            current=current,
            prices=prices,
            strategy_id="momentum",
        )

        assert len(orders) == 1
        assert orders[0].side == Side.BUY
        assert orders[0].stock.code == "005930"
        assert orders[0].quantity > 0

    def test_sell_removed_stock(self, rebalancer, samsung):
        """목표에서 빠진 종목 전량 매도."""
        pos = Position(
            stock=samsung, quantity=100, avg_price=72000,
            current_price=73000, unrealized_pnl=100000,
            weight=0.50, strategy_id="momentum",
        )
        current = PortfolioSnapshot(
            date="20260409", cash=5_000_000,
            positions=[pos], total_value=12_300_000,
            daily_return=0.0, cumulative_return=0.0, drawdown=0.0,
        )
        target_weights = {}  # 삼성전자 빠짐
        prices = {"005930": 73000}

        orders = rebalancer.generate_orders(
            target_weights=target_weights,
            current=current,
            prices=prices,
            strategy_id="momentum",
        )

        assert len(orders) == 1
        assert orders[0].side == Side.SELL
        assert orders[0].quantity == 100

    def test_rebalance_increase(self, rebalancer, samsung):
        """비중 증가 → 추가 매수."""
        pos = Position(
            stock=samsung, quantity=50, avg_price=72000,
            current_price=72000, unrealized_pnl=0,
            weight=0.36, strategy_id="momentum",
        )
        current = PortfolioSnapshot(
            date="20260409", cash=6_400_000,
            positions=[pos], total_value=10_000_000,
            daily_return=0.0, cumulative_return=0.0, drawdown=0.0,
        )
        target_weights = {"005930": 0.70}
        prices = {"005930": 72000}

        orders = rebalancer.generate_orders(
            target_weights=target_weights,
            current=current,
            prices=prices,
            strategy_id="momentum",
        )

        assert len(orders) == 1
        assert orders[0].side == Side.BUY

    def test_sells_before_buys(self, rebalancer, samsung, hynix, kakao):
        """매도 주문이 매수 주문보다 먼저 온다 (자금 확보)."""
        pos = Position(
            stock=samsung, quantity=100, avg_price=72000,
            current_price=72000, unrealized_pnl=0,
            weight=0.72, strategy_id="momentum",
        )
        current = PortfolioSnapshot(
            date="20260409", cash=2_800_000,
            positions=[pos], total_value=10_000_000,
            daily_return=0.0, cumulative_return=0.0, drawdown=0.0,
        )
        target_weights = {"005930": 0.30, "000660": 0.40}
        prices = {"005930": 72000, "000660": 180000}

        orders = rebalancer.generate_orders(
            target_weights=target_weights,
            current=current,
            prices=prices,
            strategy_id="momentum",
        )

        sell_indices = [i for i, o in enumerate(orders) if o.side == Side.SELL]
        buy_indices = [i for i, o in enumerate(orders) if o.side == Side.BUY]
        if sell_indices and buy_indices:
            assert max(sell_indices) < min(buy_indices)

    def test_skip_small_trades(self, rebalancer, samsung):
        """최소 거래금액 미만 차이는 무시."""
        pos = Position(
            stock=samsung, quantity=100, avg_price=72000,
            current_price=72000, unrealized_pnl=0,
            weight=0.72, strategy_id="momentum",
        )
        current = PortfolioSnapshot(
            date="20260409", cash=2_800_000,
            positions=[pos], total_value=10_000_000,
            daily_return=0.0, cumulative_return=0.0, drawdown=0.0,
        )
        # 목표 비중이 현재와 거의 동일 → 거래 불필요
        target_weights = {"005930": 0.72}
        prices = {"005930": 72000}

        orders = rebalancer.generate_orders(
            target_weights=target_weights,
            current=current,
            prices=prices,
            strategy_id="momentum",
        )

        assert len(orders) == 0

    def test_empty_targets_sells_all(self, rebalancer, samsung):
        """빈 목표 → 전량 매도."""
        pos = Position(
            stock=samsung, quantity=100, avg_price=72000,
            current_price=72000, unrealized_pnl=0,
            weight=1.0, strategy_id="momentum",
        )
        current = PortfolioSnapshot(
            date="20260409", cash=0,
            positions=[pos], total_value=7_200_000,
            daily_return=0.0, cumulative_return=0.0, drawdown=0.0,
        )

        orders = rebalancer.generate_orders(
            target_weights={},
            current=current,
            prices={"005930": 72000},
            strategy_id="momentum",
        )

        assert len(orders) == 1
        assert orders[0].side == Side.SELL
        assert orders[0].quantity == 100
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/trading/portfolio/test_rebalancer.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement**

`alphapulse/trading/portfolio/rebalancer.py`:
```python
"""포트폴리오 리밸런서.

목표 비중과 현재 포트폴리오의 차이를 주문으로 변환한다.
매도 → 매수 순서로 정렬하여 자금을 확보한다.
"""

import logging

from alphapulse.trading.core.enums import OrderType, Side
from alphapulse.trading.core.models import Order, PortfolioSnapshot, Stock

logger = logging.getLogger(__name__)


class Rebalancer:
    """목표 포트폴리오와 현재 포트폴리오의 차이를 주문으로 변환한다.

    Attributes:
        min_trade_amount: 최소 거래금액 (이하 무시).
    """

    def __init__(self, min_trade_amount: float = 100_000) -> None:
        """Rebalancer를 초기화한다.

        Args:
            min_trade_amount: 최소 거래금액 (원). 이하 차이는 무시.
        """
        self.min_trade_amount = min_trade_amount

    def generate_orders(
        self,
        target_weights: dict[str, float],
        current: PortfolioSnapshot,
        prices: dict[str, float],
        strategy_id: str,
    ) -> list[Order]:
        """현재 → 목표 차이를 주문 리스트로 변환한다.

        Args:
            target_weights: 종목코드 → 목표 비중 매핑.
            current: 현재 포트폴리오 스냅���.
            prices: 종목코드 → 현재가 매핑.
            strategy_id: 전략 ID.

        Returns:
            Order 리스트 (매도 먼저, 매수 나중).
        """
        total_value = current.total_value
        if total_value <= 0:
            return []

        # 현재 포지션 매핑
        current_holdings: dict[str, dict] = {}
        for pos in current.positions:
            current_holdings[pos.stock.code] = {
                "stock": pos.stock,
                "quantity": pos.quantity,
                "weight": pos.weight,
            }

        sell_orders: list[Order] = []
        buy_orders: list[Order] = []

        # 1. 매도 주문: 현재 보유 중이나 목표에 없거나 비중 감소
        for code, holding in current_holdings.items():
            target_w = target_weights.get(code, 0.0)
            current_w = holding["weight"]
            diff_w = target_w - current_w
            price = prices.get(code, 0)

            if price <= 0:
                continue

            diff_amount = diff_w * total_value
            if diff_amount < -self.min_trade_amount:
                sell_qty = int(abs(diff_amount) / price)
                if target_w == 0.0:
                    sell_qty = holding["quantity"]  # 전량 매도
                if sell_qty > 0:
                    sell_orders.append(
                        Order(
                            stock=holding["stock"],
                            side=Side.SELL,
                            order_type=OrderType.MARKET,
                            quantity=sell_qty,
                            price=None,
                            strategy_id=strategy_id,
                            reason=f"리밸런싱: {current_w:.1%} → {target_w:.1%}",
                        )
                    )

        # 2. 매수 주문: 목표에 있으나 미보유이거나 비중 증가
        for code, target_w in target_weights.items():
            current_w = current_holdings.get(code, {}).get("weight", 0.0)
            diff_w = target_w - current_w
            price = prices.get(code, 0)

            if price <= 0:
                continue

            diff_amount = diff_w * total_value
            if diff_amount > self.min_trade_amount:
                buy_qty = int(diff_amount / price)
                if buy_qty > 0:
                    stock = current_holdings.get(code, {}).get(
                        "stock",
                        Stock(code=code, name=code, market="KOSPI"),
                    )
                    buy_orders.append(
                        Order(
                            stock=stock,
                            side=Side.BUY,
                            order_type=OrderType.MARKET,
                            quantity=buy_qty,
                            price=None,
                            strategy_id=strategy_id,
                            reason=f"리��런싱: {current_w:.1%} → {target_w:.1%}",
                        )
                    )

        # 매도 먼저 → 매수 나중 (자금 확보)
        return sell_orders + buy_orders
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/trading/portfolio/test_rebalancer.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add alphapulse/trading/portfolio/rebalancer.py tests/trading/portfolio/test_rebalancer.py
git commit -m "feat(trading): add Rebalancer with sell-first order generation"
```

---

### Task 12: PortfolioStore (portfolio.db)

**Files:**
- Create: `alphapulse/trading/portfolio/store.py`
- Test: `tests/trading/portfolio/test_store.py`

- [ ] **Step 1: Write failing test**

`tests/trading/portfolio/test_store.py`:
```python
"""PortfolioStore 테스트."""

import json

import pytest

from alphapulse.trading.portfolio.store import PortfolioStore


@pytest.fixture
def store(tmp_path):
    return PortfolioStore(tmp_path / "portfolio.db")


class TestSnapshots:
    def test_save_and_get(self, store):
        """스냅샷 저장 및 조회."""
        positions = [
            {"code": "005930", "quantity": 100, "avg_price": 72000,
             "weight": 0.5, "strategy_id": "momentum"},
        ]
        store.save_snapshot(
            date="20260409", mode="paper", cash=5_000_000,
            total_value=12_200_000, positions=positions,
            daily_return=0.5, cumulative_return=8.3, drawdown=-2.1,
        )

        snap = store.get_snapshot("20260409", mode="paper")
        assert snap is not None
        assert snap["cash"] == 5_000_000
        assert snap["total_value"] == 12_200_000
        assert snap["daily_return"] == 0.5
        parsed = json.loads(snap["positions"])
        assert len(parsed) == 1
        assert parsed[0]["code"] == "005930"

    def test_get_snapshots_range(self, store):
        """기간별 스냅샷 조회."""
        for i, date in enumerate(["20260407", "20260408", "20260409"]):
            store.save_snapshot(
                date=date, mode="paper", cash=5_000_000,
                total_value=10_000_000 + i * 100_000,
                positions=[], daily_return=0.1 * i,
                cumulative_return=0.3 * i, drawdown=0.0,
            )

        snaps = store.get_snapshots("20260407", "20260409", mode="paper")
        assert len(snaps) == 3
        assert snaps[0]["date"] == "20260407"
        assert snaps[2]["date"] == "20260409"

    def test_get_missing_snapshot(self, store):
        """존재하지 않는 스냅샷 → None."""
        assert store.get_snapshot("20260409", mode="paper") is None


class TestOrders:
    def test_save_and_get(self, store):
        """주문 저장 및 조회."""
        store.save_order(
            order_id="ORD001", mode="paper", date="20260409",
            stock_code="005930", stock_name="삼성전자",
            side="BUY", order_type="MARKET", quantity=100, price=72000,
            strategy_id="momentum", reason="리밸런싱",
            status="filled", filled_quantity=100, filled_price=72000,
            commission=1080, tax=0,
        )

        orders = store.get_orders("20260409", mode="paper")
        assert len(orders) == 1
        assert orders[0]["order_id"] == "ORD001"
        assert orders[0]["status"] == "filled"

    def test_get_orders_empty(self, store):
        assert store.get_orders("20260409", mode="paper") == []


class TestTrades:
    def test_save_and_get(self, store):
        """거래 저장 및 조회."""
        store.save_trade(
            trade_id="TRD001", order_id="ORD001", mode="paper",
            date="20260409", stock_code="005930", side="BUY",
            quantity=100, price=72000, commission=1080, tax=0,
            strategy_id="momentum", realized_pnl=0,
        )

        trades = store.get_trades("20260409", mode="paper")
        assert len(trades) == 1
        assert trades[0]["trade_id"] == "TRD001"


class TestAttribution:
    def test_save_and_get(self, store):
        """성과 귀속 저장 및 조회."""
        store.save_attribution(
            date="20260409", mode="paper",
            strategy_returns={"momentum": 0.012, "value": -0.003},
            factor_returns={"momentum_factor": 0.009},
            sector_returns={"반도체": 0.005},
        )

        attr = store.get_attribution("20260409", mode="paper")
        assert attr is not None
        parsed = json.loads(attr["strategy_returns"])
        assert parsed["momentum"] == 0.012
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/trading/portfolio/test_store.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement**

`alphapulse/trading/portfolio/store.py`:
```python
"""포트폴리오 이력 SQLite 저장소.

스냅샷, 주문, 거래, 성과 귀속을 portfolio.db에 저장한다.
"""

import json
import sqlite3
import time
from pathlib import Path


class PortfolioStore:
    """포트폴리오 이력 저장소.

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
                CREATE TABLE IF NOT EXISTS snapshots (
                    date TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    run_id TEXT DEFAULT '',
                    cash REAL,
                    total_value REAL,
                    positions TEXT,
                    daily_return REAL,
                    cumulative_return REAL,
                    drawdown REAL,
                    PRIMARY KEY (date, mode, run_id)
                );

                CREATE TABLE IF NOT EXISTS orders (
                    order_id TEXT PRIMARY KEY,
                    mode TEXT NOT NULL,
                    run_id TEXT DEFAULT '',
                    date TEXT,
                    stock_code TEXT,
                    stock_name TEXT,
                    side TEXT,
                    order_type TEXT,
                    quantity INTEGER,
                    price REAL,
                    strategy_id TEXT,
                    reason TEXT,
                    status TEXT,
                    filled_quantity INTEGER,
                    filled_price REAL,
                    commission REAL,
                    tax REAL,
                    created_at REAL,
                    filled_at REAL
                );

                CREATE TABLE IF NOT EXISTS trades (
                    trade_id TEXT PRIMARY KEY,
                    order_id TEXT,
                    mode TEXT NOT NULL,
                    run_id TEXT DEFAULT '',
                    date TEXT,
                    stock_code TEXT,
                    side TEXT,
                    quantity INTEGER,
                    price REAL,
                    commission REAL,
                    tax REAL,
                    strategy_id TEXT,
                    realized_pnl REAL
                );

                CREATE TABLE IF NOT EXISTS attribution (
                    date TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    run_id TEXT DEFAULT '',
                    strategy_returns TEXT,
                    factor_returns TEXT,
                    sector_returns TEXT,
                    PRIMARY KEY (date, mode, run_id)
                );
                """
            )

    # ── Snapshots ─────────────────────────────────────────────────

    def save_snapshot(
        self,
        date: str,
        mode: str,
        cash: float,
        total_value: float,
        positions: list[dict],
        daily_return: float,
        cumulative_return: float,
        drawdown: float,
        run_id: str = "",
    ) -> None:
        """포트폴리오 스냅샷을 저장한다.

        Args:
            date: 날짜 (YYYYMMDD).
            mode: 실행 모드 ("backtest" | "paper" | "live").
            cash: 현금 (원).
            total_value: 총 자산 (원).
            positions: 포지션 리스트 (딕셔너리).
            daily_return: 일간 수익률 (%).
            cumulative_return: 누적 수익률 (%).
            drawdown: 드로다운 (%).
            run_id: 백테스트 실행 ID.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO snapshots
                    (date, mode, run_id, cash, total_value, positions,
                     daily_return, cumulative_return, drawdown)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    date, mode, run_id, cash, total_value,
                    json.dumps(positions, ensure_ascii=False),
                    daily_return, cumulative_return, drawdown,
                ),
            )

    def get_snapshot(
        self, date: str, mode: str, run_id: str = ""
    ) -> dict | None:
        """특정 날짜 스냅샷을 조회한다.

        Args:
            date: 날짜 (YYYYMMDD).
            mode: 실행 모드.
            run_id: 백테스트 실행 ID.

        Returns:
            스냅샷 딕셔너리. 없으면 None.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM snapshots WHERE date=? AND mode=? AND run_id=?",
                (date, mode, run_id),
            ).fetchone()
        return dict(row) if row else None

    def get_snapshots(
        self, start: str, end: str, mode: str, run_id: str = ""
    ) -> list[dict]:
        """기간별 스냅샷을 조회한다.

        Args:
            start: 시작일 (YYYYMMDD).
            end: 종료일 (YYYYMMDD).
            mode: 실행 모드.
            run_id: 백테스트 실행 ID.

        Returns:
            스냅샷 딕셔너리 리스트 (날짜순).
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT * FROM snapshots
                WHERE date BETWEEN ? AND ? AND mode=? AND run_id=?
                ORDER BY date
                """,
                (start, end, mode, run_id),
            ).fetchall()
        return [dict(r) for r in rows]

    # ── Orders ─────────────────────────────────────��──────────────

    def save_order(
        self,
        order_id: str,
        mode: str,
        date: str,
        stock_code: str,
        stock_name: str,
        side: str,
        order_type: str,
        quantity: int,
        price: float,
        strategy_id: str,
        reason: str,
        status: str,
        filled_quantity: int,
        filled_price: float,
        commission: float,
        tax: float,
        run_id: str = "",
    ) -> None:
        """주문을 저장한다."""
        now = time.time()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO orders
                    (order_id, mode, run_id, date, stock_code, stock_name,
                     side, order_type, quantity, price, strategy_id, reason,
                     status, filled_quantity, filled_price, commission, tax,
                     created_at, filled_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    order_id, mode, run_id, date, stock_code, stock_name,
                    side, order_type, quantity, price, strategy_id, reason,
                    status, filled_quantity, filled_price, commission, tax,
                    now, now if status == "filled" else None,
                ),
            )

    def get_orders(
        self, date: str, mode: str, run_id: str = ""
    ) -> list[dict]:
        """특정 날짜 주문을 조회한다."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM orders WHERE date=? AND mode=? AND run_id=?",
                (date, mode, run_id),
            ).fetchall()
        return [dict(r) for r in rows]

    # ── Trades ────────────────────────────────────────────────���───

    def save_trade(
        self,
        trade_id: str,
        order_id: str,
        mode: str,
        date: str,
        stock_code: str,
        side: str,
        quantity: int,
        price: float,
        commission: float,
        tax: float,
        strategy_id: str,
        realized_pnl: float,
        run_id: str = "",
    ) -> None:
        """거래를 저장한다."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO trades
                    (trade_id, order_id, mode, run_id, date, stock_code,
                     side, quantity, price, commission, tax,
                     strategy_id, realized_pnl)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    trade_id, order_id, mode, run_id, date, stock_code,
                    side, quantity, price, commission, tax,
                    strategy_id, realized_pnl,
                ),
            )

    def get_trades(
        self, date: str, mode: str, run_id: str = ""
    ) -> list[dict]:
        """특정 날짜 거래를 조회한다."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM trades WHERE date=? AND mode=? AND run_id=?",
                (date, mode, run_id),
            ).fetchall()
        return [dict(r) for r in rows]

    # ── Attribution ──────��────────────────────────────────────────

    def save_attribution(
        self,
        date: str,
        mode: str,
        strategy_returns: dict,
        factor_returns: dict,
        sector_returns: dict,
        run_id: str = "",
    ) -> None:
        """성과 귀속을 저장한다."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO attribution
                    (date, mode, run_id, strategy_returns,
                     factor_returns, sector_returns)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    date, mode, run_id,
                    json.dumps(strategy_returns, ensure_ascii=False),
                    json.dumps(factor_returns, ensure_ascii=False),
                    json.dumps(sector_returns, ensure_ascii=False),
                ),
            )

    def get_attribution(
        self, date: str, mode: str, run_id: str = ""
    ) -> dict | None:
        """성과 귀속을 조��한다."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM attribution WHERE date=? AND mode=? AND run_id=?",
                (date, mode, run_id),
            ).fetchone()
        return dict(row) if row else None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/trading/portfolio/test_store.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add alphapulse/trading/portfolio/store.py tests/trading/portfolio/test_store.py
git commit -m "feat(trading): add PortfolioStore (snapshots, orders, trades, attribution)"
```

---

### Task 13: PerformanceAttribution

**Files:**
- Create: `alphapulse/trading/portfolio/attribution.py`
- Test: `tests/trading/portfolio/test_attribution.py`

- [ ] **Step 1: Write failing test**

`tests/trading/portfolio/test_attribution.py`:
```python
"""PerformanceAttribution 테스트."""

import pytest

from alphapulse.trading.core.models import PortfolioSnapshot, Position, Stock
from alphapulse.trading.portfolio.attribution import PerformanceAttribution


@pytest.fixture
def samsung():
    return Stock(code="005930", name="삼성전자", market="KOSPI", sector="반도체")


@pytest.fixture
def kakao():
    return Stock(code="035720", name="카카��", market="KOSPI", sector="IT")


@pytest.fixture
def attribution():
    return PerformanceAttribution()


class TestStrategyAttribution:
    def test_single_strategy(self, attribution, samsung):
        """단일 전략 수익 기여도."""
        pos1 = Position(
            stock=samsung, quantity=100, avg_price=72000,
            current_price=73000, unrealized_pnl=100000,
            weight=0.50, strategy_id="momentum",
        )
        snap_prev = PortfolioSnapshot(
            date="20260408", cash=5_000_000,
            positions=[
                Position(stock=samsung, quantity=100, avg_price=72000,
                         current_price=72000, unrealized_pnl=0,
                         weight=0.50, strategy_id="momentum"),
            ],
            total_value=12_200_000, daily_return=0.0,
            cumulative_return=0.0, drawdown=0.0,
        )
        snap_curr = PortfolioSnapshot(
            date="20260409", cash=5_000_000,
            positions=[pos1], total_value=12_300_000,
            daily_return=0.82, cumulative_return=0.82, drawdown=0.0,
        )

        result = attribution.strategy_attribution(snap_prev, snap_curr)
        assert "momentum" in result
        assert result["momentum"] > 0

    def test_multi_strategy(self, attribution, samsung, kakao):
        """멀티 전략 수익 기여도 분리."""
        snap_prev = PortfolioSnapshot(
            date="20260408", cash=2_000_000,
            positions=[
                Position(stock=samsung, quantity=100, avg_price=72000,
                         current_price=72000, unrealized_pnl=0,
                         weight=0.40, strategy_id="momentum"),
                Position(stock=kakao, quantity=50, avg_price=50000,
                         current_price=50000, unrealized_pnl=0,
                         weight=0.25, strategy_id="value"),
            ],
            total_value=10_000_000, daily_return=0.0,
            cumulative_return=0.0, drawdown=0.0,
        )
        snap_curr = PortfolioSnapshot(
            date="20260409", cash=2_000_000,
            positions=[
                Position(stock=samsung, quantity=100, avg_price=72000,
                         current_price=73000, unrealized_pnl=100000,
                         weight=0.41, strategy_id="momentum"),
                Position(stock=kakao, quantity=50, avg_price=50000,
                         current_price=49000, unrealized_pnl=-50000,
                         weight=0.24, strategy_id="value"),
            ],
            total_value=10_050_000, daily_return=0.5,
            cumulative_return=0.5, drawdown=0.0,
        )

        result = attribution.strategy_attribution(snap_prev, snap_curr)
        assert result["momentum"] > 0  # 삼성전자 상승
        assert result["value"] < 0     # 카카오 하락


class TestSectorAttribution:
    def test_sector_returns(self, attribution, samsung, kakao):
        """섹터별 수익 기여도."""
        snap_prev = PortfolioSnapshot(
            date="20260408", cash=2_000_000,
            positions=[
                Position(stock=samsung, quantity=100, avg_price=72000,
                         current_price=72000, unrealized_pnl=0,
                         weight=0.50, strategy_id="momentum"),
                Position(stock=kakao, quantity=50, avg_price=50000,
                         current_price=50000, unrealized_pnl=0,
                         weight=0.25, strategy_id="value"),
            ],
            total_value=10_000_000, daily_return=0.0,
            cumulative_return=0.0, drawdown=0.0,
        )
        snap_curr = PortfolioSnapshot(
            date="20260409", cash=2_000_000,
            positions=[
                Position(stock=samsung, quantity=100, avg_price=72000,
                         current_price=73000, unrealized_pnl=100000,
                         weight=0.51, strategy_id="momentum"),
                Position(stock=kakao, quantity=50, avg_price=50000,
                         current_price=49000, unrealized_pnl=-50000,
                         weight=0.24, strategy_id="value"),
            ],
            total_value=10_050_000, daily_return=0.5,
            cumulative_return=0.5, drawdown=0.0,
        )

        result = attribution.sector_attribution(snap_prev, snap_curr)
        assert "반도체" in result
        assert "IT" in result
        assert result["반도체"] > 0
        assert result["IT"] < 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/trading/portfolio/test_attribution.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement**

`alphapulse/trading/portfolio/attribution.py`:
```python
"""성과 귀속 분석.

전략별, 섹터별 수익 기여도를 분석한다.
"""

import logging

from alphapulse.trading.core.models import PortfolioSnapshot

logger = logging.getLogger(__name__)


class PerformanceAttribution:
    """수익률 원천 분석.

    전략별, 섹터별 수익 기여도를 산출한다.
    """

    def strategy_attribution(
        self,
        prev_snapshot: PortfolioSnapshot,
        curr_snapshot: PortfolioSnapshot,
    ) -> dict[str, float]:
        """전략별 수익 기여도를 산출한다.

        Args:
            prev_snapshot: 전일 스냅샷.
            curr_snapshot: 금일 스냅샷.

        Returns:
            전략ID → 수익 기여도(%) 매핑.
        """
        prev_total = prev_snapshot.total_value
        if prev_total <= 0:
            return {}

        # 전일 포지션 매핑: code → (price, weight, strategy)
        prev_map: dict[str, dict] = {}
        for pos in prev_snapshot.positions:
            prev_map[pos.stock.code] = {
                "price": pos.current_price,
                "weight": pos.weight,
                "strategy_id": pos.strategy_id,
            }

        # 전략별 수익 기여도 집계
        strategy_returns: dict[str, float] = {}
        for pos in curr_snapshot.positions:
            code = pos.stock.code
            strategy = pos.strategy_id
            prev = prev_map.get(code)
            if prev is None or prev["price"] <= 0:
                continue

            stock_return = (pos.current_price - prev["price"]) / prev["price"]
            contribution = prev["weight"] * stock_return * 100  # %

            strategy_returns[strategy] = (
                strategy_returns.get(strategy, 0.0) + contribution
            )

        return strategy_returns

    def sector_attribution(
        self,
        prev_snapshot: PortfolioSnapshot,
        curr_snapshot: PortfolioSnapshot,
    ) -> dict[str, float]:
        """섹터별 수��� 기여도를 산출��다.

        Args:
            prev_snapshot: 전일 스냅샷.
            curr_snapshot: 금일 스냅샷.

        Returns:
            섹터명 → 수익 기여���(%) 매핑.
        """
        prev_total = prev_snapshot.total_value
        if prev_total <= 0:
            return {}

        prev_map: dict[str, dict] = {}
        for pos in prev_snapshot.positions:
            prev_map[pos.stock.code] = {
                "price": pos.current_price,
                "weight": pos.weight,
                "sector": pos.stock.sector,
            }

        sector_returns: dict[str, float] = {}
        for pos in curr_snapshot.positions:
            code = pos.stock.code
            prev = prev_map.get(code)
            if prev is None or prev["price"] <= 0:
                continue

            sector = prev["sector"] or "기타"
            stock_return = (pos.current_price - prev["price"]) / prev["price"]
            contribution = prev["weight"] * stock_return * 100

            sector_returns[sector] = (
                sector_returns.get(sector, 0.0) + contribution
            )

        return sector_returns
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/trading/portfolio/test_attribution.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add alphapulse/trading/portfolio/attribution.py tests/trading/portfolio/test_attribution.py
git commit -m "feat(trading): add PerformanceAttribution (strategy, sector)"
```

---

### Task 14: PortfolioManager (통합)

**Files:**
- Create: `alphapulse/trading/portfolio/manager.py`
- Test: `tests/trading/portfolio/test_manager.py`

- [ ] **Step 1: Write failing test**

`tests/trading/portfolio/test_manager.py`:
```python
"""PortfolioManager 통합 테스트."""

from unittest.mock import MagicMock

import pytest

from alphapulse.trading.core.enums import Side
from alphapulse.trading.core.models import (
    Order,
    PortfolioSnapshot,
    Position,
    Signal,
    Stock,
    StrategySynthesis,
)
from alphapulse.trading.portfolio.manager import PortfolioManager


@pytest.fixture
def samsung():
    return Stock(code="005930", name="삼성전자", market="KOSPI")


@pytest.fixture
def manager():
    position_sizer = MagicMock()
    optimizer = MagicMock()
    rebalancer = MagicMock()
    cost_model = MagicMock()

    return PortfolioManager(
        position_sizer=position_sizer,
        optimizer=optimizer,
        rebalancer=rebalancer,
        cost_model=cost_model,
    )


class TestUpdateTarget:
    def test_generates_target_weights(self, manager, samsung):
        """전략 시그널로부터 목표 비중을 산출한다."""
        signals = {
            "momentum": [
                Signal(stock=samsung, score=80.0,
                       factors={"momentum": 0.8},
                       strategy_id="momentum"),
            ],
        }
        allocations = {"momentum": 1.0}
        current = PortfolioSnapshot(
            date="20260409", cash=10_000_000, positions=[],
            total_value=10_000_000, daily_return=0.0,
            cumulative_return=0.0, drawdown=0.0,
        )
        manager.position_sizer.equal_weight.return_value = 1.0

        target = manager.update_target(
            strategy_signals=signals,
            allocations=allocations,
            current=current,
            prices={"005930": 72000},
        )

        assert isinstance(target, dict)
        assert "005930" in target
        assert 0 < target["005930"] <= 1.0

    def test_applies_allocation_ratio(self, manager, samsung):
        """전략 배분 비율을 적용한다."""
        signals = {
            "momentum": [
                Signal(stock=samsung, score=80.0,
                       factors={"momentum": 0.8},
                       strategy_id="momentum"),
            ],
        }
        allocations = {"momentum": 0.50}  # 50%만 배분
        current = PortfolioSnapshot(
            date="20260409", cash=10_000_000, positions=[],
            total_value=10_000_000, daily_return=0.0,
            cumulative_return=0.0, drawdown=0.0,
        )
        manager.position_sizer.equal_weight.return_value = 1.0

        target = manager.update_target(
            strategy_signals=signals,
            allocations=allocations,
            current=current,
            prices={"005930": 72000},
        )

        # 50% 배분 * 100% 종목 비중 = 50%
        assert target["005930"] <= 0.50 + 0.01


class TestGenerateOrders:
    def test_delegates_to_rebalancer(self, manager, samsung):
        """Rebalancer에 위임한다."""
        target = {"005930": 0.50}
        current = PortfolioSnapshot(
            date="20260409", cash=10_000_000, positions=[],
            total_value=10_000_000, daily_return=0.0,
            cumulative_return=0.0, drawdown=0.0,
        )
        prices = {"005930": 72000}

        expected_orders = [
            Order(stock=samsung, side=Side.BUY, order_type="MARKET",
                  quantity=69, price=None, strategy_id="momentum"),
        ]
        manager.rebalancer.generate_orders.return_value = expected_orders

        orders = manager.generate_orders(
            target_weights=target,
            current=current,
            prices=prices,
            strategy_id="momentum",
        )

        assert orders == expected_orders
        manager.rebalancer.generate_orders.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/trading/portfolio/test_manager.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement**

`alphapulse/trading/portfolio/manager.py`:
```python
"""포트폴리오 매니저.

전략 시그널을 목표 포트폴리오로 변환하고 리밸런싱 주문을 생성한다.
PositionSizer, PortfolioOptimizer, Rebalancer를 통합한다.
"""

import logging

from alphapulse.trading.core.cost_model import CostModel
from alphapulse.trading.core.models import Order, PortfolioSnapshot, Signal
from alphapulse.trading.portfolio.optimizer import PortfolioOptimizer
from alphapulse.trading.portfolio.position_sizer import PositionSizer
from alphapulse.trading.portfolio.rebalancer import Rebalancer

logger = logging.getLogger(__name__)


class PortfolioManager:
    """목표 포트폴리오 산출 및 리밸런싱 주문 생성 통합 관리자.

    Attributes:
        position_sizer: 포지션 사이징 도구.
        optimizer: 포트폴리오 최적화기.
        rebalancer: 리밸런서.
        cost_model: 거래 비용 모델.
    """

    def __init__(
        self,
        position_sizer: PositionSizer,
        optimizer: PortfolioOptimizer,
        rebalancer: Rebalancer,
        cost_model: CostModel,
    ) -> None:
        """PortfolioManager를 초기화한다.

        Args:
            position_sizer: 포지션 사이징 도구.
            optimizer: 포트폴리오 최적화기.
            rebalancer: 리밸런서.
            cost_model: 거래 비용 모델.
        """
        self.position_sizer = position_sizer
        self.optimizer = optimizer
        self.rebalancer = rebalancer
        self.cost_model = cost_model

    def update_target(
        self,
        strategy_signals: dict[str, list[Signal]],
        allocations: dict[str, float],
        current: PortfolioSnapshot,
        prices: dict[str, float],
    ) -> dict[str, float]:
        """목표 포트폴리오 비중을 산출한다.

        Args:
            strategy_signals: 전략ID → Signal 리스트.
            allocations: 전략ID → 배분 비율.
            current: 현재 포트폴리오 스냅샷.
            prices: 종목코드 → 현재가.

        Returns:
            종목코드 → 목표 비중 딕셔너리.
        """
        target_weights: dict[str, float] = {}

        for strategy_id, signals in strategy_signals.items():
            alloc_ratio = allocations.get(strategy_id, 0.0)
            if alloc_ratio <= 0 or not signals:
                continue

            # 전략 내 종목별 균등 배분
            n_stocks = len(signals)
            per_stock_weight = self.position_sizer.equal_weight(n_stocks)

            for sig in signals:
                code = sig.stock.code
                # 전략 배분 비율 * 종목 내 비중
                weight = alloc_ratio * per_stock_weight
                # 기존 비중과 합산 (다수 전략이 동일 종목 보유 가능)
                target_weights[code] = target_weights.get(code, 0.0) + weight

        return target_weights

    def generate_orders(
        self,
        target_weights: dict[str, float],
        current: PortfolioSnapshot,
        prices: dict[str, float],
        strategy_id: str,
    ) -> list[Order]:
        """현재 → 목표 차이를 주문으로 변환한다.

        Args:
            target_weights: 종목코드 → 목표 비중.
            current: 현재 포트폴리오 스냅샷.
            prices: 종목코드 → 현재가.
            strategy_id: 전략 ID.

        Returns:
            Order 리스트.
        """
        return self.rebalancer.generate_orders(
            target_weights=target_weights,
            current=current,
            prices=prices,
            strategy_id=strategy_id,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/trading/portfolio/test_manager.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add alphapulse/trading/portfolio/manager.py tests/trading/portfolio/test_manager.py
git commit -m "feat(trading): add PortfolioManager integrating sizer, optimizer, rebalancer"
```

---

## Phase ⑥: Risk Engine

---

### Task 15: RiskLimits + RiskDecision + RiskAlert

**Files:**
- Create: `alphapulse/trading/risk/__init__.py`
- Create: `alphapulse/trading/risk/limits.py`
- Test: `tests/trading/risk/__init__.py`
- Test: `tests/trading/risk/test_limits.py`

- [ ] **Step 1: Create package directories**

```bash
mkdir -p alphapulse/trading/risk
mkdir -p tests/trading/risk
```

Create `tests/trading/risk/__init__.py` (빈 파일).

`alphapulse/trading/risk/__init__.py`:
```python
"""리스크 관리 엔진."""
```

- [ ] **Step 2: Write failing test**

`tests/trading/risk/test_limits.py`:
```python
"""RiskLimits, RiskDecision, RiskAlert 테스트."""

from alphapulse.trading.core.enums import RiskAction
from alphapulse.trading.risk.limits import RiskAlert, RiskDecision, RiskLimits


class TestRiskLimits:
    def test_defaults(self):
        """기본값 확인."""
        limits = RiskLimits()
        assert limits.max_position_weight == 0.10
        assert limits.max_sector_weight == 0.30
        assert limits.max_etf_leverage == 0.20
        assert limits.max_total_exposure == 1.0
        assert limits.max_drawdown_soft == 0.10
        assert limits.max_drawdown_hard == 0.15
        assert limits.max_daily_loss == 0.03
        assert limits.min_cash_ratio == 0.05
        assert limits.max_single_order_pct == 0.05
        assert limits.max_order_to_volume == 0.10
        assert limits.max_portfolio_var_95 == 0.03

    def test_custom_values(self):
        """커스텀 값 지정."""
        limits = RiskLimits(
            max_position_weight=0.05,
            max_drawdown_hard=0.20,
        )
        assert limits.max_position_weight == 0.05
        assert limits.max_drawdown_hard == 0.20
        # 나머지는 기본값
        assert limits.max_sector_weight == 0.30


class TestRiskDecision:
    def test_approve(self):
        """승인 결정."""
        d = RiskDecision(
            action=RiskAction.APPROVE,
            reason="모든 한도 이내",
            adjusted_quantity=None,
        )
        assert d.action == RiskAction.APPROVE
        assert d.adjusted_quantity is None

    def test_reduce_size(self):
        """수량 축소."""
        d = RiskDecision(
            action=RiskAction.REDUCE_SIZE,
            reason="종목 비중 한도 초과",
            adjusted_quantity=50,
        )
        assert d.action == RiskAction.REDUCE_SIZE
        assert d.adjusted_quantity == 50

    def test_reject(self):
        """거부."""
        d = RiskDecision(
            action=RiskAction.REJECT,
            reason="일간 손실 한도 초과",
            adjusted_quantity=None,
        )
        assert d.action == RiskAction.REJECT


class TestRiskAlert:
    def test_creation(self):
        alert = RiskAlert(
            level="WARNING",
            category="drawdown",
            message="드로다운 -8% 접근",
            current_value=0.08,
            limit_value=0.10,
        )
        assert alert.level == "WARNING"
        assert alert.category == "drawdown"
        assert alert.current_value == 0.08
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/trading/risk/test_limits.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 4: Implement**

`alphapulse/trading/risk/limits.py`:
```python
"""리스크 한도 정의.

절대 위반 불가 제약 조건과 리스크 판정 결과 데이터 클래스.
"""

from dataclasses import dataclass

from alphapulse.trading.core.enums import RiskAction


@dataclass
class RiskLimits:
    """��대 위반 불가 리스크 제약 조건.

    AI, 전략, 사용자 모두 오버라이드 불가.
    Config(.env)에서 로드하여 코드 수정 없이 튜닝 가능하다.

    Attributes:
        max_position_weight: 종목당 최대 비중.
        max_sector_weight: 섹터당 최대 비중.
        max_etf_leverage: 레버리지/인버스 ETF 최대 비중.
        max_total_exposure: 총 노출도 상한.
        max_drawdown_soft: 소프트 드로다운 한도 (경고).
        max_drawdown_hard: 하드 드로다운 한도 (강제 축소).
        max_daily_loss: 일간 최대 손실 한도.
        min_cash_ratio: 최소 현금 비율.
        max_single_order_pct: 단일 주문 총자산 비율 상한.
        max_order_to_volume: 주문량/일평균 거래량 비율 상한.
        max_portfolio_var_95: 95% VaR 상한.
    """

    max_position_weight: float = 0.10
    max_sector_weight: float = 0.30
    max_etf_leverage: float = 0.20
    max_total_exposure: float = 1.0
    max_drawdown_soft: float = 0.10
    max_drawdown_hard: float = 0.15
    max_daily_loss: float = 0.03
    min_cash_ratio: float = 0.05
    max_single_order_pct: float = 0.05
    max_order_to_volume: float = 0.10
    max_portfolio_var_95: float = 0.03


@dataclass
class RiskDecision:
    """리스크 검증 결과.

    Attributes:
        action: 검증 결과 (APPROVE | REDUCE_SIZE | REJECT).
        reason: 사유.
        adjusted_quantity: REDUCE_SIZE일 때 조정된 ��량.
    """

    action: RiskAction
    reason: str
    adjusted_quantity: int | None


@dataclass
class RiskAlert:
    """리스크 경고.

    Attributes:
        level: 경고 수준 ("INFO" | "WARNING" | "CRITICAL").
        category: 카테고리 ("drawdown" | "concentration" | "var" | "liquidity").
        message: 경고 메시지.
        current_value: 현재값.
        limit_value: 한도값.
    """

    level: str
    category: str
    message: str
    current_value: float
    limit_value: float
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/trading/risk/test_limits.py -v`
Expected: 6 passed

- [ ] **Step 6: Commit**

```bash
git add alphapulse/trading/risk/ tests/trading/risk/
git commit -m "feat(trading): add RiskLimits, RiskDecision, RiskAlert dataclasses"
```

---

### Task 16: VaRCalculator

**Files:**
- Create: `alphapulse/trading/risk/var.py`
- Test: `tests/trading/risk/test_var.py`

- [ ] **Step 1: Write failing test**

`tests/trading/risk/test_var.py`:
```python
"""VaRCalculator 테스트."""

import numpy as np
import pytest

from alphapulse.trading.risk.var import VaRCalculator


@pytest.fixture
def calc():
    return VaRCalculator()


@pytest.fixture
def normal_returns():
    """정규분포 유사 수익률 시계열 (평균 0, 표준편차 ~2%)."""
    np.random.seed(42)
    return np.random.normal(0.0, 0.02, 250)


class TestHistoricalVaR:
    def test_95_confidence(self, calc, normal_returns):
        """95% 신뢰수준 Historical VaR."""
        var = calc.historical_var(normal_returns, confidence=0.95)
        assert var > 0
        assert 0.01 < var < 0.10  # 합리적 범위

    def test_99_confidence_higher(self, calc, normal_returns):
        """99% VaR > 95% VaR."""
        var_95 = calc.historical_var(normal_returns, confidence=0.95)
        var_99 = calc.historical_var(normal_returns, confidence=0.99)
        assert var_99 > var_95


class TestParametricVaR:
    def test_single_asset(self, calc):
        """단일 자산 파라메트릭 VaR."""
        weights = np.array([1.0])
        cov = np.array([[0.04]])  # 변동성 20%
        var = calc.parametric_var(weights, cov, confidence=0.95)
        assert var > 0

    def test_two_assets(self, calc):
        """2종목 파라메트릭 VaR."""
        weights = np.array([0.5, 0.5])
        cov = np.array([[0.04, 0.01], [0.01, 0.09]])
        var = calc.parametric_var(weights, cov, confidence=0.95)
        assert var > 0

    def test_diversification_reduces_var(self, calc):
        """분산 투자 시 VaR 감소."""
        cov = np.array([[0.04, 0.01], [0.01, 0.09]])
        # 집중 투자
        var_conc = calc.parametric_var(np.array([1.0, 0.0]), cov)
        # 분산 투자
        var_div = calc.parametric_var(np.array([0.5, 0.5]), cov)
        assert var_div < var_conc


class TestCVaR:
    def test_cvar_greater_than_var(self, calc, normal_returns):
        """CVaR >= VaR (꼬리 리스크 반영)."""
        var = calc.historical_var(normal_returns, confidence=0.95)
        cvar = calc.cvar(normal_returns, confidence=0.95)
        assert cvar >= var

    def test_cvar_positive(self, calc, normal_returns):
        """CVaR는 양수."""
        cvar = calc.cvar(normal_returns, confidence=0.95)
        assert cvar > 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/trading/risk/test_var.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement**

`alphapulse/trading/risk/var.py`:
```python
"""VaR(Value at Risk) / CVaR 계산기.

포트폴리오 손실 위험을 측정한다.
Historical, Parametric(분산-공분산), CVaR(Expected Shortfall)을 지원한다.
"""

import numpy as np
from scipy.stats import norm


class VaRCalculator:
    """포트폴리오 VaR/CVaR 계산기."""

    def historical_var(
        self,
        returns: np.ndarray,
        confidence: float = 0.95,
    ) -> float:
        """과거 수익률 분포 기반 Historical VaR.

        Args:
            returns: 일간 수익률 배열.
            confidence: 신뢰수준 (0~1, 기본 0.95).

        Returns:
            VaR 값 (양수, 손실 크기).
        """
        percentile = (1 - confidence) * 100
        return float(-np.percentile(returns, percentile))

    def parametric_var(
        self,
        weights: np.ndarray,
        cov_matrix: np.ndarray,
        confidence: float = 0.95,
    ) -> float:
        """분산-공분산 기반 파라메트릭 VaR (정규분포 가정).

        Args:
            weights: 종목별 비중 벡터.
            cov_matrix: 공분산 행렬.
            confidence: 신뢰수준.

        Returns:
            VaR 값 (양수).
        """
        portfolio_vol = float(np.sqrt(weights @ cov_matrix @ weights))
        z_score = norm.ppf(confidence)
        return portfolio_vol * z_score

    def cvar(
        self,
        returns: np.ndarray,
        confidence: float = 0.95,
    ) -> float:
        """Conditional VaR (Expected Shortfall).

        VaR를 초과하는 손실의 평균 — 꼬리 리스크를 반영한다.

        Args:
            returns: 일간 수익률 배��.
            confidence: 신뢰���준.

        Returns:
            CVaR 값 (양수, 손실 크기).
        """
        var = self.historical_var(returns, confidence)
        tail_losses = returns[returns <= -var]
        if len(tail_losses) == 0:
            return var
        return float(-tail_losses.mean())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/trading/risk/test_var.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add alphapulse/trading/risk/var.py tests/trading/risk/test_var.py
git commit -m "feat(trading): add VaRCalculator (historical, parametric, CVaR)"
```

---

### Task 17: DrawdownManager

**Files:**
- Create: `alphapulse/trading/risk/drawdown.py`
- Test: `tests/trading/risk/test_drawdown.py`

- [ ] **Step 1: Write failing test**

`tests/trading/risk/test_drawdown.py`:
```python
"""DrawdownManager 테스트."""

import pytest

from alphapulse.trading.core.enums import DrawdownAction, Side
from alphapulse.trading.core.models import PortfolioSnapshot, Position, Stock
from alphapulse.trading.risk.drawdown import DrawdownManager
from alphapulse.trading.risk.limits import RiskLimits


@pytest.fixture
def samsung():
    return Stock(code="005930", name="삼성전자", market="KOSPI")


@pytest.fixture
def limits():
    return RiskLimits(max_drawdown_soft=0.10, max_drawdown_hard=0.15)


@pytest.fixture
def manager(limits):
    return DrawdownManager(limits=limits)


class TestCheckDrawdown:
    def test_normal_state(self, manager):
        """드로다운 미발생 → NORMAL."""
        snap = PortfolioSnapshot(
            date="20260409", cash=5_000_000, positions=[],
            total_value=10_000_000, daily_return=0.5,
            cumulative_return=5.0, drawdown=-2.0,
        )
        manager.update_peak(10_000_000)
        action = manager.check(snap)
        assert action == DrawdownAction.NORMAL

    def test_warn_state(self, manager):
        """소프트 한도 초과 → WARN."""
        manager.update_peak(10_000_000)
        # 10% 하락 → 9,000,000
        snap = PortfolioSnapshot(
            date="20260409", cash=4_000_000, positions=[],
            total_value=8_900_000, daily_return=-1.1,
            cumulative_return=-5.0, drawdown=-11.0,
        )
        action = manager.check(snap)
        assert action == DrawdownAction.WARN

    def test_deleverage_state(self, manager):
        """하드 한도 초과 → DELEVERAGE."""
        manager.update_peak(10_000_000)
        # 16% 하락 → 8,400,000
        snap = PortfolioSnapshot(
            date="20260409", cash=3_000_000, positions=[],
            total_value=8_400_000, daily_return=-2.0,
            cumulative_return=-10.0, drawdown=-16.0,
        )
        action = manager.check(snap)
        assert action == DrawdownAction.DELEVERAGE

    def test_peak_updates(self, manager):
        """고점이 자동 갱신된다."""
        manager.update_peak(10_000_000)
        manager.update_peak(11_000_000)
        assert manager.peak_value == 11_000_000

    def test_peak_does_not_decrease(self, manager):
        """고점은 감소하지 않는다."""
        manager.update_peak(10_000_000)
        manager.update_peak(9_000_000)
        assert manager.peak_value == 10_000_000


class TestGenerateDeleverageOrders:
    def test_deleverage_orders(self, manager, samsung):
        """전 포지션 50% 축소 주문 생성."""
        pos = Position(
            stock=samsung, quantity=100, avg_price=72000,
            current_price=60000, unrealized_pnl=-1200000,
            weight=0.70, strategy_id="momentum",
        )
        snap = PortfolioSnapshot(
            date="20260409", cash=2_000_000,
            positions=[pos], total_value=8_000_000,
            daily_return=-3.0, cumulative_return=-20.0, drawdown=-20.0,
        )

        orders = manager.generate_deleverage_orders(snap)

        assert len(orders) == 1
        assert orders[0].side == Side.SELL
        assert orders[0].quantity == 50  # 100의 50%
        assert "디레버리지" in orders[0].reason or "축소" in orders[0].reason

    def test_no_positions_no_orders(self, manager):
        """포지션 없으면 주문 없음."""
        snap = PortfolioSnapshot(
            date="20260409", cash=8_000_000, positions=[],
            total_value=8_000_000, daily_return=-3.0,
            cumulative_return=-20.0, drawdown=-20.0,
        )

        orders = manager.generate_deleverage_orders(snap)
        assert len(orders) == 0

    def test_orders_sorted_by_loss(self, manager, samsung):
        """손실 큰 포지션부터 매도."""
        kakao = Stock(code="035720", name="카카오", market="KOSPI")
        pos1 = Position(
            stock=samsung, quantity=100, avg_price=72000,
            current_price=60000, unrealized_pnl=-1200000,
            weight=0.40, strategy_id="momentum",
        )
        pos2 = Position(
            stock=kakao, quantity=50, avg_price=50000,
            current_price=48000, unrealized_pnl=-100000,
            weight=0.30, strategy_id="value",
        )
        snap = PortfolioSnapshot(
            date="20260409", cash=2_000_000,
            positions=[pos2, pos1],  # 의도적으로 카카오 먼저
            total_value=8_000_000, daily_return=-3.0,
            cumulative_return=-20.0, drawdown=-20.0,
        )

        orders = manager.generate_deleverage_orders(snap)
        # 삼성전자 (-1,200,000)가 카카오 (-100,000)보다 먼저
        assert orders[0].stock.code == "005930"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/trading/risk/test_drawdown.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement**

`alphapulse/trading/risk/drawdown.py`:
```python
"""드로다운 관리자.

포트폴리오 고점 대비 하락률을 모니터링하고,
한도 초과 시 자동 디레버리징 주문을 생성한다.
"""

import logging

from alphapulse.trading.core.enums import DrawdownAction, OrderType, Side
from alphapulse.trading.core.models import Order, PortfolioSnapshot
from alphapulse.trading.risk.limits import RiskLimits

logger = logging.getLogger(__name__)


class DrawdownManager:
    """드로다운 모니터링 + 자동 디레버리징.

    Attributes:
        limits: 리스크 한도.
        peak_value: 포트폴리오 역대 최고 가치.
    """

    def __init__(self, limits: RiskLimits) -> None:
        """DrawdownManager를 초기��한다.

        Args:
            limits: 리스크 한도 설정.
        """
        self.limits = limits
        self.peak_value: float = 0.0

    def update_peak(self, current_value: float) -> None:
        """포트폴리오 고점을 갱신한다.

        Args:
            current_value: 현재 포트폴리오 총 가치.
        """
        self.peak_value = max(self.peak_value, current_value)

    def check(self, portfolio: PortfolioSnapshot) -> DrawdownAction:
        """드로다운 상태를 확인한다.

        Args:
            portfolio: 현재 포트폴리오 스냅샷.

        Returns:
            DrawdownAction (NORMAL | WARN | DELEVERAGE).
        """
        self.update_peak(portfolio.total_value)

        if self.peak_value <= 0:
            return DrawdownAction.NORMAL

        drawdown = (self.peak_value - portfolio.total_value) / self.peak_value

        if drawdown < self.limits.max_drawdown_soft:
            return DrawdownAction.NORMAL
        elif drawdown < self.limits.max_drawdown_hard:
            logger.warning(
                "드로다운 경고: %.1f%% (소프트 한도: %.1f%%)",
                drawdown * 100,
                self.limits.max_drawdown_soft * 100,
            )
            return DrawdownAction.WARN
        else:
            logger.error(
                "드로다운 한도 초과: %.1f%% (하드 한도: %.1f%%) → 디레버리징",
                drawdown * 100,
                self.limits.max_drawdown_hard * 100,
            )
            return DrawdownAction.DELEVERAGE

    def generate_deleverage_orders(
        self,
        portfolio: PortfolioSnapshot,
    ) -> list[Order]:
        """전 포지션 50% 축소 주문을 생성한다.

        손실이 큰 포지션부터 우선 매도한다.

        Args:
            portfolio: 현재 포트폴리오 스냅샷.

        Returns:
            디레버리징 매도 주문 리스트.
        """
        if not portfolio.positions:
            return []

        # 손실 큰 순서로 정렬
        sorted_positions = sorted(
            portfolio.positions,
            key=lambda p: p.unrealized_pnl,
        )

        orders: list[Order] = []
        for pos in sorted_positions:
            sell_qty = pos.quantity // 2  # 50% 축소
            if sell_qty <= 0:
                continue
            orders.append(
                Order(
                    stock=pos.stock,
                    side=Side.SELL,
                    order_type=OrderType.MARKET,
                    quantity=sell_qty,
                    price=None,
                    strategy_id=pos.strategy_id,
                    reason=f"디레버리징: 드로다운 한도 초과 — 50% 축소",
                )
            )

        return orders
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/trading/risk/test_drawdown.py -v`
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add alphapulse/trading/risk/drawdown.py tests/trading/risk/test_drawdown.py
git commit -m "feat(trading): add DrawdownManager with auto-deleverage orders"
```

---

### Task 18: StressTest

**Files:**
- Create: `alphapulse/trading/risk/stress_test.py`
- Test: `tests/trading/risk/test_stress_test.py`

- [ ] **Step 1: Write failing test**

`tests/trading/risk/test_stress_test.py`:
```python
"""StressTest ���스트."""

import pytest

from alphapulse.trading.core.models import PortfolioSnapshot, Position, Stock
from alphapulse.trading.risk.stress_test import StressResult, StressTest


@pytest.fixture
def samsung():
    return Stock(code="005930", name="삼성전자", market="KOSPI", sector="반도체")


@pytest.fixture
def kodex():
    return Stock(code="069500", name="KODEX 200", market="ETF")


@pytest.fixture
def stress():
    return StressTest()


@pytest.fixture
def portfolio(samsung, kodex):
    pos1 = Position(
        stock=samsung, quantity=100, avg_price=72000,
        current_price=72000, unrealized_pnl=0,
        weight=0.50, strategy_id="momentum",
    )
    pos2 = Position(
        stock=kodex, quantity=200, avg_price=35000,
        current_price=35000, unrealized_pnl=0,
        weight=0.50, strategy_id="topdown_etf",
    )
    return PortfolioSnapshot(
        date="20260409", cash=0,
        positions=[pos1, pos2],
        total_value=14_200_000,
        daily_return=0.0, cumulative_return=0.0, drawdown=0.0,
    )


class TestPredefinedScenarios:
    def test_scenarios_exist(self, stress):
        """사전 정의 시나리오가 존재한다."""
        assert "2020_covid" in stress.SCENARIOS
        assert "2022_rate_hike" in stress.SCENARIOS
        assert "flash_crash" in stress.SCENARIOS
        assert "won_crisis" in stress.SCENARIOS

    def test_covid_scenario(self, stress, portfolio):
        """COVID-19 시나리오 실행."""
        result = stress.run(portfolio, "2020_covid")
        assert isinstance(result, StressResult)
        assert result.scenario_name == "2020_covid"
        assert result.estimated_loss < 0  # 손실 발생
        assert result.loss_pct < 0

    def test_flash_crash_scenario(self, stress, portfolio):
        """일간 급락 시나리오."""
        result = stress.run(portfolio, "flash_crash")
        assert result.estimated_loss < 0

    def test_result_has_contributions(self, stress, portfolio):
        """종목별 손실 기여도 포���."""
        result = stress.run(portfolio, "2020_covid")
        assert len(result.contributions) > 0

    def test_unknown_scenario_raises(self, stress, portfolio):
        """미정의 시나리오 → KeyError."""
        with pytest.raises(KeyError):
            stress.run(portfolio, "unknown_scenario")


class TestRunAll:
    def test_runs_all_scenarios(self, stress, portfolio):
        """전 시나리오 일괄 실행."""
        results = stress.run_all(portfolio)
        assert len(results) == len(stress.SCENARIOS)
        assert all(isinstance(r, StressResult) for r in results.values())


class TestCustomScenario:
    def test_add_custom(self, stress, portfolio):
        """사용자 정의 시나리오 추가."""
        stress.add_custom_scenario(
            "china_crisis",
            {"kospi": -0.30, "kosdaq": -0.40, "desc": "중국 경제 위기"},
        )
        assert "china_crisis" in stress.SCENARIOS

        result = stress.run(portfolio, "china_crisis")
        assert result.estimated_loss < 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/trading/risk/test_stress_test.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement**

`alphapulse/trading/risk/stress_test.py`:
```python
"""시나리오 스트레스 테스트.

사전 정의된 위기 시나리오를 포트폴리오에 적용하여
예상 손실을 시뮬레이션한다.
"""

import logging
from dataclasses import dataclass, field

from alphapulse.trading.core.models import PortfolioSnapshot

logger = logging.getLogger(__name__)


@dataclass
class StressResult:
    """스트레스 테스트 결과.

    Attributes:
        scenario_name: 시나리오 이름.
        description: 시나리오 설명.
        estimated_loss: 예상 손실 금액 (원, 음수).
        loss_pct: 예상 손실률 (%, 음수).
        contributions: 종목별 손실 기여 딕셔너리.
    """

    scenario_name: str
    description: str
    estimated_loss: float
    loss_pct: float
    contributions: dict[str, float] = field(default_factory=dict)


class StressTest:
    """시나리오별 포트폴리오 손실 시뮬레이션.

    사전 정의 시나리오 + 사용자 정의 시나리오를 지원한다.
    """

    SCENARIOS: dict[str, dict] = {
        "2020_covid": {
            "kospi": -0.35,
            "kosdaq": -0.40,
            "etf": -0.35,
            "desc": "COVID-19 급락 (2020.03)",
        },
        "2022_rate_hike": {
            "kospi": -0.25,
            "kosdaq": -0.35,
            "etf": -0.25,
            "desc": "금리 인상기 하락 (2022)",
        },
        "flash_crash": {
            "kospi": -0.10,
            "kosdaq": -0.15,
            "etf": -0.10,
            "desc": "일간 급락 (Flash Crash)",
        },
        "won_crisis": {
            "kospi": -0.20,
            "kosdaq": -0.25,
            "etf": -0.20,
            "desc": "원화 위기 + 외국인 이탈",
        },
    }

    def run(
        self,
        portfolio: PortfolioSnapshot,
        scenario: str,
    ) -> StressResult:
        """시나리오를 포트폴리오에 적용한��.

        Args:
            portfolio: 현재 포트폴리오 스냅샷.
            scenario: 시나리오 이름.

        Returns:
            StressResult.

        Raises:
            KeyError: 미정의 시나리오.
        """
        if scenario not in self.SCENARIOS:
            raise KeyError(f"미정의 시나리오: {scenario}")

        shocks = self.SCENARIOS[scenario]
        desc = shocks.get("desc", scenario)

        total_loss = 0.0
        contributions: dict[str, float] = {}

        for pos in portfolio.positions:
            # 시장 유형에 따라 충격 적용
            market = pos.stock.market
            if market == "ETF":
                shock = shocks.get("etf", shocks.get("kospi", -0.10))
            elif market == "KOSDAQ":
                shock = shocks.get("kosdaq", shocks.get("kospi", -0.10))
            else:
                shock = shocks.get("kospi", -0.10)

            position_value = pos.quantity * pos.current_price
            position_loss = position_value * shock
            total_loss += position_loss
            contributions[pos.stock.code] = position_loss

        total_value = portfolio.total_value
        loss_pct = (total_loss / total_value * 100) if total_value > 0 else 0.0

        return StressResult(
            scenario_name=scenario,
            description=desc,
            estimated_loss=total_loss,
            loss_pct=loss_pct,
            contributions=contributions,
        )

    def run_all(
        self,
        portfolio: PortfolioSnapshot,
    ) -> dict[str, StressResult]:
        """전 시나리오를 일괄 실행한다.

        Args:
            portfolio: 현재 포트폴리오 스냅샷.

        Returns:
            시나리오명 → StressResult 매핑.
        """
        results = {}
        for name in self.SCENARIOS:
            results[name] = self.run(portfolio, name)
        return results

    def add_custom_scenario(self, name: str, shocks: dict) -> None:
        """사용자 정의 시나리오를 추가한다.

        Args:
            name: 시나리오 이름.
            shocks: 충격 파라미터 (kospi, kosdaq, etf, desc).
        """
        self.SCENARIOS[name] = shocks
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/trading/risk/test_stress_test.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add alphapulse/trading/risk/stress_test.py tests/trading/risk/test_stress_test.py
git commit -m "feat(trading): add StressTest with 4 predefined scenarios + custom support"
```

---

### Task 19: RiskReport

**Files:**
- Create: `alphapulse/trading/risk/report.py`
- Test: `tests/trading/risk/test_report.py`

- [ ] **Step 1: Write failing test**

`tests/trading/risk/test_report.py`:
```python
"""RiskReport 테스트."""

import pytest

from alphapulse.trading.core.models import PortfolioSnapshot, Position, Stock
from alphapulse.trading.risk.limits import RiskAlert
from alphapulse.trading.risk.report import RiskReport, RiskReportGenerator
from alphapulse.trading.risk.stress_test import StressResult


@pytest.fixture
def samsung():
    return Stock(code="005930", name="삼성전자", market="KOSPI", sector="반도체")


@pytest.fixture
def generator():
    return RiskReportGenerator()


@pytest.fixture
def portfolio(samsung):
    pos = Position(
        stock=samsung, quantity=100, avg_price=72000,
        current_price=73000, unrealized_pnl=100000,
        weight=0.50, strategy_id="momentum",
    )
    return PortfolioSnapshot(
        date="20260409", cash=5_000_000,
        positions=[pos], total_value=12_300_000,
        daily_return=0.82, cumulative_return=8.3, drawdown=-2.1,
    )


class TestRiskReport:
    def test_creation(self):
        report = RiskReport(
            date="20260409",
            drawdown_pct=2.1,
            drawdown_status="NORMAL",
            var_95=0.018,
            cvar_95=0.025,
            alerts=[],
            stress_results={},
            sector_concentration={"반도체": 0.50},
        )
        assert report.date == "20260409"
        assert report.var_95 == 0.018

    def test_has_alerts(self):
        alert = RiskAlert(
            level="WARNING", category="concentration",
            message="반도체 섹터 50%", current_value=0.50,
            limit_value=0.30,
        )
        report = RiskReport(
            date="20260409", drawdown_pct=2.1,
            drawdown_status="NORMAL", var_95=0.018,
            cvar_95=0.025, alerts=[alert],
            stress_results={}, sector_concentration={},
        )
        assert len(report.alerts) == 1
        assert report.alerts[0].level == "WARNING"


class TestRiskReportGenerator:
    def test_generate_sector_concentration(self, generator, portfolio):
        """섹터 집중도 계산."""
        concentration = generator.calculate_sector_concentration(portfolio)
        assert "반도체" in concentration
        assert concentration["반도체"] == pytest.approx(0.50, abs=0.01)

    def test_generate_report(self, generator, portfolio):
        """리포트 생성."""
        report = generator.generate(
            portfolio=portfolio,
            drawdown_status="NORMAL",
            var_95=0.018,
            cvar_95=0.025,
            stress_results={},
        )
        assert isinstance(report, RiskReport)
        assert report.date == "20260409"

    def test_concentration_alert(self, generator, portfolio):
        """섹터 집중도 경고 생성."""
        alerts = generator.check_concentration_alerts(
            portfolio, max_sector_weight=0.30,
        )
        # 반도체 50% > 30% 한도
        assert len(alerts) >= 1
        assert alerts[0].category == "concentration"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/trading/risk/test_report.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement**

`alphapulse/trading/risk/report.py`:
```python
"""리스크 리포트 생성.

일일 리스크 현황을 요약하는 리포트를 생성한다.
"""

import logging
from dataclasses import dataclass, field

from alphapulse.trading.core.models import PortfolioSnapshot
from alphapulse.trading.risk.limits import RiskAlert
from alphapulse.trading.risk.stress_test import StressResult

logger = logging.getLogger(__name__)


@dataclass
class RiskReport:
    """일일 리스크 리포트.

    Attributes:
        date: 기준 날짜 (YYYYMMDD).
        drawdown_pct: 현재 드로다운 (%).
        drawdown_status: 드로다운 상태 ("NORMAL" | "WARN" | "DELEVERAGE").
        var_95: 95% VaR.
        cvar_95: 95% CVaR.
        alerts: 리스크 경고 목록.
        stress_results: 스트레스 테스트 결과.
        sector_concentration: 섹터별 집중도.
    """

    date: str
    drawdown_pct: float
    drawdown_status: str
    var_95: float
    cvar_95: float
    alerts: list[RiskAlert] = field(default_factory=list)
    stress_results: dict[str, StressResult] = field(default_factory=dict)
    sector_concentration: dict[str, float] = field(default_factory=dict)


class RiskReportGenerator:
    """리스크 리포트 생성기."""

    def generate(
        self,
        portfolio: PortfolioSnapshot,
        drawdown_status: str,
        var_95: float,
        cvar_95: float,
        stress_results: dict[str, StressResult],
        max_sector_weight: float = 0.30,
    ) -> RiskReport:
        """���일 리스크 리포트를 생성한다.

        Args:
            portfolio: 현재 포트폴리오 스냅샷.
            drawdown_status: 드로다운 상태 문자열.
            var_95: 95% VaR.
            cvar_95: 95% CVaR.
            stress_results: 스트레스 테스트 결과.
            max_sector_weight: 섹터 집중도 경고 한도.

        Returns:
            RiskReport 인스턴스.
        """
        sector_conc = self.calculate_sector_concentration(portfolio)
        alerts = self.check_concentration_alerts(
            portfolio, max_sector_weight,
        )

        return RiskReport(
            date=portfolio.date,
            drawdown_pct=abs(portfolio.drawdown),
            drawdown_status=drawdown_status,
            var_95=var_95,
            cvar_95=cvar_95,
            alerts=alerts,
            stress_results=stress_results,
            sector_concentration=sector_conc,
        )

    def calculate_sector_concentration(
        self,
        portfolio: PortfolioSnapshot,
    ) -> dict[str, float]:
        """섹터별 집중도를 계산한다.

        Args:
            portfolio: 포트폴리오 스냅샷.

        Returns:
            섹터명 → 비중 매핑.
        """
        sector_weights: dict[str, float] = {}
        for pos in portfolio.positions:
            sector = pos.stock.sector or "기타"
            sector_weights[sector] = (
                sector_weights.get(sector, 0.0) + pos.weight
            )
        return sector_weights

    def check_concentration_alerts(
        self,
        portfolio: PortfolioSnapshot,
        max_sector_weight: float = 0.30,
    ) -> list[RiskAlert]:
        """섹터 집중도 경고를 생성한다.

        Args:
            portfolio: 포트폴리오 스냅샷.
            max_sector_weight: 섹터당 최대 비중.

        Returns:
            RiskAlert 리스트.
        """
        sector_conc = self.calculate_sector_concentration(portfolio)
        alerts = []

        for sector, weight in sector_conc.items():
            if weight > max_sector_weight:
                alerts.append(
                    RiskAlert(
                        level="WARNING",
                        category="concentration",
                        message=f"{sector} 섹터 집중도 {weight:.0%} > 한도 {max_sector_weight:.0%}",
                        current_value=weight,
                        limit_value=max_sector_weight,
                    )
                )

        return alerts
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/trading/risk/test_report.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add alphapulse/trading/risk/report.py tests/trading/risk/test_report.py
git commit -m "feat(trading): add RiskReport + RiskReportGenerator"
```

---

### Task 20: RiskManager (통합)

**Files:**
- Create: `alphapulse/trading/risk/manager.py`
- Test: `tests/trading/risk/test_manager.py`

- [ ] **Step 1: Write failing test**

`tests/trading/risk/test_manager.py`:
```python
"""RiskManager 통합 테스트."""

from unittest.mock import MagicMock

import pytest

from alphapulse.trading.core.enums import DrawdownAction, RiskAction, Side
from alphapulse.trading.core.models import Order, PortfolioSnapshot, Position, Stock
from alphapulse.trading.risk.drawdown import DrawdownManager
from alphapulse.trading.risk.limits import RiskDecision, RiskLimits
from alphapulse.trading.risk.manager import RiskManager
from alphapulse.trading.risk.var import VaRCalculator


@pytest.fixture
def samsung():
    return Stock(code="005930", name="삼성전자", market="KOSPI", sector="반도체")


@pytest.fixture
def limits():
    return RiskLimits()


@pytest.fixture
def manager(limits):
    var_calc = VaRCalculator()
    drawdown_mgr = DrawdownManager(limits=limits)
    drawdown_mgr.update_peak(10_000_000)
    return RiskManager(
        limits=limits,
        var_calc=var_calc,
        drawdown_mgr=drawdown_mgr,
    )


class TestCheckOrder:
    def test_approve_normal_order(self, manager, samsung):
        """정상 주문 → APPROVE."""
        order = Order(
            stock=samsung, side=Side.BUY, order_type="MARKET",
            quantity=10, price=None, strategy_id="momentum",
        )
        portfolio = PortfolioSnapshot(
            date="20260409", cash=5_000_000,
            positions=[], total_value=10_000_000,
            daily_return=0.0, cumulative_return=0.0, drawdown=0.0,
        )
        prices = {"005930": 72000}

        decision = manager.check_order(order, portfolio, prices)
        assert decision.action == RiskAction.APPROVE

    def test_reject_position_weight_exceeded(self, manager, samsung):
        """종목 비중 한도 초과 → REDUCE_SIZE."""
        order = Order(
            stock=samsung, side=Side.BUY, order_type="MARKET",
            quantity=200, price=None, strategy_id="momentum",
        )
        portfolio = PortfolioSnapshot(
            date="20260409", cash=5_000_000,
            positions=[], total_value=10_000_000,
            daily_return=0.0, cumulative_return=0.0, drawdown=0.0,
        )
        prices = {"005930": 72000}
        # 200 * 72000 = 14,400,000 > 10,000,000 * 10% = 1,000,000

        decision = manager.check_order(order, portfolio, prices)
        assert decision.action in (RiskAction.REDUCE_SIZE, RiskAction.REJECT)

    def test_reject_during_warn_drawdown(self, manager, samsung):
        """WARN 드로다운 상태에서 매수 → REJECT."""
        manager.drawdown_mgr.update_peak(10_000_000)
        order = Order(
            stock=samsung, side=Side.BUY, order_type="MARKET",
            quantity=5, price=None, strategy_id="momentum",
        )
        portfolio = PortfolioSnapshot(
            date="20260409", cash=4_000_000,
            positions=[], total_value=8_900_000,
            daily_return=-1.0, cumulative_return=-5.0, drawdown=-11.0,
        )
        prices = {"005930": 72000}

        decision = manager.check_order(order, portfolio, prices)
        assert decision.action == RiskAction.REJECT
        assert "드로다운" in decision.reason

    def test_allow_sell_during_warn(self, manager, samsung):
        """WARN 드로다운 상태에서 매도는 허용."""
        manager.drawdown_mgr.update_peak(10_000_000)
        pos = Position(
            stock=samsung, quantity=100, avg_price=72000,
            current_price=72000, unrealized_pnl=0,
            weight=0.50, strategy_id="momentum",
        )
        order = Order(
            stock=samsung, side=Side.SELL, order_type="MARKET",
            quantity=50, price=None, strategy_id="momentum",
        )
        portfolio = PortfolioSnapshot(
            date="20260409", cash=4_000_000,
            positions=[pos], total_value=8_900_000,
            daily_return=-1.0, cumulative_return=-5.0, drawdown=-11.0,
        )
        prices = {"005930": 72000}

        decision = manager.check_order(order, portfolio, prices)
        assert decision.action == RiskAction.APPROVE

    def test_reject_daily_loss_exceeded(self, manager, samsung):
        """일간 손실 한도 초과 → REJECT."""
        order = Order(
            stock=samsung, side=Side.BUY, order_type="MARKET",
            quantity=5, price=None, strategy_id="momentum",
        )
        portfolio = PortfolioSnapshot(
            date="20260409", cash=5_000_000,
            positions=[], total_value=10_000_000,
            daily_return=-3.5, cumulative_return=-5.0, drawdown=-5.0,
        )
        prices = {"005930": 72000}

        decision = manager.check_order(order, portfolio, prices)
        assert decision.action == RiskAction.REJECT
        assert "일간" in decision.reason or "손실" in decision.reason

    def test_reject_min_cash_violation(self, manager, samsung):
        """최소 현금 비율 위반 → REJECT."""
        order = Order(
            stock=samsung, side=Side.BUY, order_type="MARKET",
            quantity=10, price=None, strategy_id="momentum",
        )
        # 현금 300,000 / 총자산 10,000,000 = 3% < 5%
        portfolio = PortfolioSnapshot(
            date="20260409", cash=300_000,
            positions=[], total_value=10_000_000,
            daily_return=0.0, cumulative_return=0.0, drawdown=0.0,
        )
        prices = {"005930": 72000}

        decision = manager.check_order(order, portfolio, prices)
        assert decision.action == RiskAction.REJECT


class TestCheckPortfolio:
    def test_returns_alerts(self, manager, samsung):
        """포트폴리오 전체 리스크 점검."""
        pos = Position(
            stock=samsung, quantity=100, avg_price=72000,
            current_price=72000, unrealized_pnl=0,
            weight=0.80, strategy_id="momentum",  # 80% 집중
        )
        portfolio = PortfolioSnapshot(
            date="20260409", cash=2_000_000,
            positions=[pos], total_value=9_200_000,
            daily_return=-1.0, cumulative_return=-3.0, drawdown=-8.0,
        )

        alerts = manager.check_portfolio(portfolio)
        assert len(alerts) >= 1  # 집중도 경고
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/trading/risk/test_manager.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement**

`alphapulse/trading/risk/manager.py`:
```python
"""리스크 매니저.

모든 리스크 체크를 통합하는 중앙 관리자.
주문 실행 전 검증, 포트폴리오 전체 점검, 일일 리포트를 담당한다.
"""

import logging

from alphapulse.trading.core.enums import DrawdownAction, RiskAction, Side
from alphapulse.trading.core.models import Order, PortfolioSnapshot
from alphapulse.trading.risk.drawdown import DrawdownManager
from alphapulse.trading.risk.limits import RiskAlert, RiskDecision, RiskLimits
from alphapulse.trading.risk.report import RiskReport, RiskReportGenerator
from alphapulse.trading.risk.stress_test import StressTest
from alphapulse.trading.risk.var import VaRCalculator

logger = logging.getLogger(__name__)


class RiskManager:
    """모든 리스크 체크 통합 관리자.

    Attributes:
        limits: 리스크 한도.
        var_calc: VaR 계산기.
        drawdown_mgr: 드로다운 관리자.
        stress_test: 스트레스 테스트.
        report_gen: 리포트 생성기.
    """

    def __init__(
        self,
        limits: RiskLimits,
        var_calc: VaRCalculator,
        drawdown_mgr: DrawdownManager,
    ) -> None:
        """RiskManager를 초기화한다.

        Args:
            limits: 리스크 한도 설정.
            var_calc: VaR 계산기.
            drawdown_mgr: 드로다운 관리자.
        """
        self.limits = limits
        self.var_calc = var_calc
        self.drawdown_mgr = drawdown_mgr
        self.stress_test = StressTest()
        self.report_gen = RiskReportGenerator()

    def check_order(
        self,
        order: Order,
        portfolio: PortfolioSnapshot,
        prices: dict[str, float],
    ) -> RiskDecision:
        """주문 실행 전 리스크를 검증한다.

        검증 순서:
        1. 일간 손실 한도
        2. 드로다운 상태 (WARN이면 매수 거부)
        3. 최소 현금 비율
        4. 종목 비중 한도
        5. 단일 주문 금액 한도

        Args:
            order: 검증할 주문.
            portfolio: 현재 포트폴리오.
            prices: 종목코드 → 현재가.

        Returns:
            RiskDecision (APPROVE | REDUCE_SIZE | REJECT).
        """
        # 1. 일간 손실 한도 체크
        if abs(portfolio.daily_return) >= self.limits.max_daily_loss * 100:
            return RiskDecision(
                action=RiskAction.REJECT,
                reason=f"일��� 손실 한도 초과: {portfolio.daily_return:.1f}% "
                       f"(한도: {self.limits.max_daily_loss * 100:.1f}%)",
                adjusted_quantity=None,
            )

        # 2. 드로다운 상태 체크
        dd_action = self.drawdown_mgr.check(portfolio)
        if dd_action == DrawdownAction.WARN and order.side == Side.BUY:
            return RiskDecision(
                action=RiskAction.REJECT,
                reason="드로다운 경고 상태 — 신규 매수 중단",
                adjusted_quantity=None,
            )
        if dd_action == DrawdownAction.DELEVERAGE and order.side == Side.BUY:
            return RiskDecision(
                action=RiskAction.REJECT,
                reason="드로다운 한도 초과 — 디레버리징 모드",
                adjusted_quantity=None,
            )

        # 매도 주문은 추가 검증 없이 승인
        if order.side == Side.SELL:
            return RiskDecision(
                action=RiskAction.APPROVE,
                reason="매도 주문 승인",
                adjusted_quantity=None,
            )

        # 3. 최소 현금 비율 체크
        if portfolio.total_value > 0:
            cash_ratio = portfolio.cash / portfolio.total_value
            if cash_ratio < self.limits.min_cash_ratio:
                return RiskDecision(
                    action=RiskAction.REJECT,
                    reason=f"최소 현금 비율 미달: {cash_ratio:.1%} "
                           f"(한도: {self.limits.min_cash_ratio:.1%})",
                    adjusted_quantity=None,
                )

        # 4. 종목 비중 한도 체크
        price = prices.get(order.stock.code, 0)
        if price > 0 and portfolio.total_value > 0:
            # 현재 보유량 + 주문량
            current_qty = 0
            for pos in portfolio.positions:
                if pos.stock.code == order.stock.code:
                    current_qty = pos.quantity
                    break
            new_value = (current_qty + order.quantity) * price
            new_weight = new_value / portfolio.total_value

            if new_weight > self.limits.max_position_weight:
                # 비중 한도 내로 수량 축소
                max_value = portfolio.total_value * self.limits.max_position_weight
                max_qty = int(max_value / price) - current_qty
                if max_qty <= 0:
                    return RiskDecision(
                        action=RiskAction.REJECT,
                        reason=f"종목 비중 한도 초과: {new_weight:.1%} "
                               f"(한도: {self.limits.max_position_weight:.1%})",
                        adjusted_quantity=None,
                    )
                return RiskDecision(
                    action=RiskAction.REDUCE_SIZE,
                    reason=f"종목 비중 한도 → 수량 축소: {order.quantity} → {max_qty}",
                    adjusted_quantity=max_qty,
                )

        # 5. 단일 주문 금액 한도
        if price > 0 and portfolio.total_value > 0:
            order_amount = order.quantity * price
            order_pct = order_amount / portfolio.total_value
            if order_pct > self.limits.max_single_order_pct:
                max_amount = portfolio.total_value * self.limits.max_single_order_pct
                max_qty = int(max_amount / price)
                if max_qty <= 0:
                    return RiskDecision(
                        action=RiskAction.REJECT,
                        reason=f"단일 주문 한도 초과: {order_pct:.1%}",
                        adjusted_quantity=None,
                    )
                return RiskDecision(
                    action=RiskAction.REDUCE_SIZE,
                    reason=f"단일 주문 한도 → 수량 축소: {order.quantity} → {max_qty}",
                    adjusted_quantity=max_qty,
                )

        return RiskDecision(
            action=RiskAction.APPROVE,
            reason="모든 한도 이내",
            adjusted_quantity=None,
        )

    def check_portfolio(
        self,
        portfolio: PortfolioSnapshot,
    ) -> list[RiskAlert]:
        """포트폴리오 전체 리스크를 점검한다.

        Args:
            portfolio: 현재 포트폴리오 스냅샷.

        Returns:
            RiskAlert 리스트.
        """
        alerts: list[RiskAlert] = []

        # 섹터 집중도
        alerts.extend(
            self.report_gen.check_concentration_alerts(
                portfolio,
                max_sector_weight=self.limits.max_sector_weight,
            )
        )

        # 종목 집중도
        for pos in portfolio.positions:
            if pos.weight > self.limits.max_position_weight:
                alerts.append(
                    RiskAlert(
                        level="WARNING",
                        category="concentration",
                        message=f"{pos.stock.name} 비중 {pos.weight:.0%} > "
                                f"한도 {self.limits.max_position_weight:.0%}",
                        current_value=pos.weight,
                        limit_value=self.limits.max_position_weight,
                    )
                )

        # 드로다운 경고
        dd_action = self.drawdown_mgr.check(portfolio)
        if dd_action != DrawdownAction.NORMAL:
            alerts.append(
                RiskAlert(
                    level="CRITICAL" if dd_action == DrawdownAction.DELEVERAGE else "WARNING",
                    category="drawdown",
                    message=f"드로다운 상태: {dd_action.value}",
                    current_value=abs(portfolio.drawdown) / 100,
                    limit_value=self.limits.max_drawdown_soft,
                )
            )

        return alerts

    def daily_report(
        self,
        portfolio: PortfolioSnapshot,
        returns_history: list[float] | None = None,
    ) -> RiskReport:
        """일일 리스크 리포트를 생성한다.

        Args:
            portfolio: 현재 포트폴리오 스냅샷.
            returns_history: 일간 수익률 이력 (VaR 계산용).

        Returns:
            RiskReport.
        """
        import numpy as np

        dd_action = self.drawdown_mgr.check(portfolio)

        var_95 = 0.0
        cvar_95 = 0.0
        if returns_history and len(returns_history) >= 20:
            arr = np.array(returns_history)
            var_95 = self.var_calc.historical_var(arr, confidence=0.95)
            cvar_95 = self.var_calc.cvar(arr, confidence=0.95)

        stress_results = self.stress_test.run_all(portfolio)

        return self.report_gen.generate(
            portfolio=portfolio,
            drawdown_status=dd_action.value,
            var_95=var_95,
            cvar_95=cvar_95,
            stress_results=stress_results,
            max_sector_weight=self.limits.max_sector_weight,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/trading/risk/test_manager.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add alphapulse/trading/risk/manager.py tests/trading/risk/test_manager.py
git commit -m "feat(trading): add RiskManager with integrated order/portfolio checks"
```

---

## Task 21: 전체 통합 테스트 + __init__.py 갱신

**Files:**
- Create: `tests/trading/test_phase2_integration.py`
- Update: `alphapulse/trading/strategy/__init__.py`
- Update: `alphapulse/trading/portfolio/__init__.py`
- Update: `alphapulse/trading/risk/__init__.py`

- [ ] **Step 1: Update __init__.py exports**

`alphapulse/trading/strategy/__init__.py`:
```python
"""전략 프레임워크."""

from .allocator import StrategyAllocator
from .base import BaseStrategy
from .momentum import MomentumStrategy
from .quality_momentum import QualityMomentumStrategy
from .registry import StrategyRegistry
from .topdown_etf import TopDownETFStrategy
from .value import ValueStrategy

__all__ = [
    "BaseStrategy",
    "TopDownETFStrategy",
    "MomentumStrategy",
    "ValueStrategy",
    "QualityMomentumStrategy",
    "StrategyRegistry",
    "StrategyAllocator",
]
```

`alphapulse/trading/portfolio/__init__.py`:
```python
"""포트폴리오 관리."""

from .attribution import PerformanceAttribution
from .manager import PortfolioManager
from .optimizer import PortfolioOptimizer
from .position_sizer import PositionSizer
from .rebalancer import Rebalancer
from .store import PortfolioStore

__all__ = [
    "PositionSizer",
    "PortfolioOptimizer",
    "Rebalancer",
    "PortfolioStore",
    "PerformanceAttribution",
    "PortfolioManager",
]
```

`alphapulse/trading/risk/__init__.py`:
```python
"""리스크 관리 엔진."""

from .drawdown import DrawdownManager
from .limits import RiskAlert, RiskDecision, RiskLimits
from .manager import RiskManager
from .report import RiskReport, RiskReportGenerator
from .stress_test import StressResult, StressTest
from .var import VaRCalculator

__all__ = [
    "RiskLimits",
    "RiskDecision",
    "RiskAlert",
    "VaRCalculator",
    "DrawdownManager",
    "StressTest",
    "StressResult",
    "RiskReport",
    "RiskReportGenerator",
    "RiskManager",
]
```

- [ ] **Step 2: Write integration test**

`tests/trading/test_phase2_integration.py`:
```python
"""Trading Phase 2 통합 테스트.

Strategy → Portfolio → Risk 전체 파이프라인을 검증한다.
"""

from unittest.mock import MagicMock

from alphapulse.trading.core.enums import RiskAction, Side
from alphapulse.trading.core.models import (
    Order,
    PortfolioSnapshot,
    Position,
    Signal,
    Stock,
    StrategySynthesis,
)
from alphapulse.trading.portfolio.manager import PortfolioManager
from alphapulse.trading.portfolio.optimizer import PortfolioOptimizer
from alphapulse.trading.portfolio.position_sizer import PositionSizer
from alphapulse.trading.portfolio.rebalancer import Rebalancer
from alphapulse.trading.risk.drawdown import DrawdownManager
from alphapulse.trading.risk.limits import RiskLimits
from alphapulse.trading.risk.manager import RiskManager
from alphapulse.trading.risk.var import VaRCalculator
from alphapulse.trading.strategy.allocator import StrategyAllocator
from alphapulse.trading.strategy.registry import StrategyRegistry
from alphapulse.trading.strategy.topdown_etf import TopDownETFStrategy


def test_strategy_to_portfolio_to_risk():
    """전략 시그널 → 목표 비중 → 주문 → 리스크 검증 흐름."""
    # 1. 전략 설정
    registry = StrategyRegistry()
    etf_strategy = TopDownETFStrategy(config={})
    registry.register(etf_strategy)

    # 2. 시그널 생성
    etf_universe = [
        Stock(code="069500", name="KODEX 200", market="ETF"),
        Stock(code="153130", name="KODEX 단기채권", market="ETF"),
    ]
    ctx = {"pulse_signal": "moderately_bullish", "pulse_score": 40}
    signals = etf_strategy.generate_signals(etf_universe, ctx)
    assert len(signals) > 0

    # 3. 배분
    allocator = StrategyAllocator(
        base_allocations={"topdown_etf": 1.0}
    )
    allocations = allocator.get_allocations()

    # 4. 포트폴리오 목표 산출
    sizer = PositionSizer()
    optimizer = PortfolioOptimizer()
    rebalancer = Rebalancer(min_trade_amount=50_000)
    cost_model = MagicMock()

    pm = PortfolioManager(
        position_sizer=sizer,
        optimizer=optimizer,
        rebalancer=rebalancer,
        cost_model=cost_model,
    )

    current = PortfolioSnapshot(
        date="20260409", cash=10_000_000, positions=[],
        total_value=10_000_000, daily_return=0.0,
        cumulative_return=0.0, drawdown=0.0,
    )

    target = pm.update_target(
        strategy_signals={"topdown_etf": signals},
        allocations=allocations,
        current=current,
        prices={"069500": 35000, "153130": 100000},
    )
    assert len(target) > 0

    # 5. 주문 생성
    orders = pm.generate_orders(
        target_weights=target,
        current=current,
        prices={"069500": 35000, "153130": 100000},
        strategy_id="topdown_etf",
    )

    # 6. 리스크 검증
    limits = RiskLimits()
    var_calc = VaRCalculator()
    dd_mgr = DrawdownManager(limits=limits)
    dd_mgr.update_peak(10_000_000)
    risk_mgr = RiskManager(
        limits=limits, var_calc=var_calc, drawdown_mgr=dd_mgr,
    )

    for order in orders:
        decision = risk_mgr.check_order(
            order, current,
            prices={"069500": 35000, "153130": 100000},
        )
        assert decision.action in (
            RiskAction.APPROVE, RiskAction.REDUCE_SIZE,
        )


def test_allocator_with_ai_synthesis():
    """AI 종합 판단이 배분에 반영된다."""
    allocator = StrategyAllocator(
        base_allocations={"topdown_etf": 0.30, "momentum": 0.40, "value": 0.30}
    )

    synthesis = StrategySynthesis(
        market_view="매수 우위",
        conviction_level=0.8,
        allocation_adjustment={"topdown_etf": 0.20, "momentum": 0.50, "value": 0.30},
        stock_opinions=[],
        risk_warnings=[],
        reasoning="외국인 순매수 지속",
    )

    adjusted = allocator.adjust_by_market_regime(
        pulse_score=40, ai_synthesis=synthesis,
    )

    assert abs(sum(adjusted.values()) - 1.0) < 1e-6
    assert adjusted["momentum"] > 0.40  # AI가 momentum 증가 제안


def test_drawdown_triggers_deleverage():
    """드로다운 한도 초과 시 디레버리징 주문 생성."""
    samsung = Stock(code="005930", name="삼성전자", market="KOSPI")
    limits = RiskLimits(max_drawdown_hard=0.15)
    dd_mgr = DrawdownManager(limits=limits)
    dd_mgr.update_peak(10_000_000)

    pos = Position(
        stock=samsung, quantity=100, avg_price=72000,
        current_price=60000, unrealized_pnl=-1200000,
        weight=0.70, strategy_id="momentum",
    )
    portfolio = PortfolioSnapshot(
        date="20260409", cash=2_000_000,
        positions=[pos], total_value=8_000_000,
        daily_return=-3.0, cumulative_return=-20.0, drawdown=-20.0,
    )

    action = dd_mgr.check(portfolio)
    assert action.value == "DELEVERAGE"

    orders = dd_mgr.generate_deleverage_orders(portfolio)
    assert len(orders) == 1
    assert orders[0].side == Side.SELL
    assert orders[0].quantity == 50
```

- [ ] **Step 3: Run integration test**

Run: `pytest tests/trading/test_phase2_integration.py -v`
Expected: 3 passed

- [ ] **Step 4: Run full Phase 2 test suite**

Run: `pytest tests/trading/strategy/ tests/trading/portfolio/ tests/trading/risk/ tests/trading/test_phase2_integration.py -v`
Expected: All tests pass (approximately 110+ tests)

- [ ] **Step 5: Run all tests to verify no regressions**

Run: `pytest tests/ -v --tb=short`
Expected: All existing tests + new Phase 2 tests pass. No failures.

- [ ] **Step 6: Commit**

```bash
git add alphapulse/trading/strategy/__init__.py alphapulse/trading/portfolio/__init__.py alphapulse/trading/risk/__init__.py tests/trading/test_phase2_integration.py
git commit -m "feat(trading): Phase 2 integration tests + package exports"
```

---

## Verification Checklist

After completing all tasks, verify:

- [ ] `pytest tests/trading/strategy/ -v` — 전체 전략 테스트 통과
- [ ] `pytest tests/trading/portfolio/ -v` — 전체 포트폴리오 테스트 통과
- [ ] `pytest tests/trading/risk/ -v` — 전체 리스크 테스트 ��과
- [ ] `pytest tests/trading/test_phase2_integration.py -v` — 통합 테스트 통과
- [ ] `pytest tests/ -v` — 기존 275+ 테스트 회귀 없음
- [ ] `ruff check alphapulse/trading/strategy/ alphapulse/trading/portfolio/ alphapulse/trading/risk/` — 린트 에러 없음
- [ ] 모든 파일이 200줄 이내 (분리 검토 불필요)
- [ ] 모든 docstring이 한국어
- [ ] async는 `ai_synthesizer.py`만 사용 (`asyncio.to_thread()`)
- [ ] `scipy.optimize`가 `optimizer.py`에서 사용됨
- [ ] `RiskManager.check_order()`가 `RiskDecision` 반환
- [ ] `DrawdownManager`가 `peak_value` 추적 + `generate_deleverage_orders()` 구현
- [ ] `StressTest`에 4개 사전 정의 시나리오 포함 (2020_covid, 2022_rate_hike, flash_crash, won_crisis)
- [ ] `StrategyAllocator`가 `StrategySynthesis.allocation_adjustment` 반영

---

## Next Plans

After Phase 2 completion, the following plans will be created:

| Plan | Phases | Description |
|------|--------|-------------|
| **Plan 3** | ⑦⑧ | Backtest engine (SimBroker, DataFeed, metrics) + KIS broker integration |
| **Plan 4** | ⑨⑩ | Trading orchestrator + scheduler + Telegram alerts + CLI commands |

Each plan depends on the previous one. Start Plan 3 only after Plan 2 is fully verified.
