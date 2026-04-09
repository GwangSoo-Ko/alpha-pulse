# AlphaPulse Trading System Design

자동 투자 및 포트폴리오 운용 에이전트 설계 문서.
기존 AlphaPulse 분석 플랫폼(정량 11개 지표 + 정성 + AI 종합 + 피드백)에 **매매 실행 레이어**를 추가한다.

## 1. 요구사항 요약

| 항목 | 결정 |
|------|------|
| 매매 모드 | 백테스트 + Paper Trading + 실매매 (3가지 모두) |
| 매매 대상 | 한국 주식 (KOSPI/KOSDAQ) + ETF |
| 전략 유형 | 탑다운 ETF + 개별 종목(팩터) + 멀티전략 배분 |
| 증권사 | 한국투자증권 Open API |
| 리밸런싱 | 혼합 — 전략별 다른 주기 (ETF: 시그널 드리븐, 종목: 주간) |
| 리스크 관리 | 고급 — VaR, 드로다운 자동 디레버리징, 상관관계 최적화, 스트레스 테스트 |
| 데이터 소스 | 가격 + 재무제표 + 수급 + 공매도/신용 (대안 데이터 포함) |
| AI 연동 | 정량(스크리닝+전략) + 정성(콘텐츠) → LLM 종합 판단 → 최종 전략 수립 |

## 2. 아키텍처

### 2.1 접근법: 모듈형 플러그인 아키텍처

기존 `alphapulse/` 패키지에 `trading/` 모듈을 추가한다. Protocol 기반 인터페이스로 서브시스템 간 경계를 분리한다.

```
alphapulse/
├── market/            # 기존 — 시장 레벨 정량 분석 (SYNC)
├── content/           # 기존 — 정성 분석 (ASYNC)
├── briefing/          # 기존 — 일일 브리핑
├── agents/            # 기존 — AI 에이전트
├── feedback/          # 기존 — 피드백 시스템
├── core/              # 기존 — 공유 인프라
└── trading/           # 새로 추가
    ├── core/          # 공유 인터페이스, 데이터 모델 (①)
    ├── data/          # 종목 데이터 수집기 (②)
    ├── screening/     # 팩터 스크리닝/랭킹 (③)
    ├── strategy/      # 전략 프레임워크 + AI 종합 (④)
    ├── portfolio/     # 포트폴리오 관리 (⑤)
    ├── risk/          # 리스크 엔진 (⑥)
    ├── backtest/      # 백테스트 엔진 (⑦)
    ├── broker/        # 증권사 API 연동 (⑧)
    └── orchestrator/  # 트레이딩 오케스트레이터 (⑨)
```

### 2.2 기존 시스템과의 관계

```
기존 AlphaPulse (읽기 전용 소비)          새 Trading 시스템
────────────────────────────            ──────────────────
SignalEngine.run() ─────────────────→  TradingEngine (Market Pulse Score)
Content Analysis ───────────────────→  AI Synthesizer (정성 입력)
FeedbackEvaluator.get_hit_rates() ──→  AI Synthesizer (적중률 → 확신도)
Notifier (Telegram) ────────────────→  TradingAlert (알림 채널 재사용)
DataCache (cache.db) ───────────────→  trading/data/ 캐싱 패턴 재사용
Config ─────────────────────────────→  trading 설정 확장
```

- 기존 모듈은 **변경하지 않는다**. trading/은 읽기 전용으로 소비.
- 데이터 변환이 필요한 경우 `trading/core/adapters.py`에서 처리.

### 2.3 Sync/Async 규칙

기존 규칙을 그대로 따른다:

| 모듈 | 방식 | 이유 |
|------|------|------|
| `trading/data/` | Sync | pykrx, requests 기반 수집 |
| `trading/screening/` | Sync | 데이터 계산, I/O 없음 |
| `trading/strategy/` | Sync (기본) + Async (AI) | AI 종합만 async |
| `trading/strategy/ai_synthesizer.py` | Async | LLM 호출 (`asyncio.to_thread()`) |
| `trading/portfolio/` | Sync | 계산 로직 |
| `trading/risk/` | Sync | 계산 로직 |
| `trading/backtest/` | Sync | 시뮬레이션 루프 |
| `trading/broker/` | Sync | REST API (requests) |
| `trading/orchestrator/` | Async | 전체 통합 (`asyncio.run()`은 CLI entry만) |

## 3. 핵심 데이터 모델 (`trading/core/`)

```
trading/core/
├── __init__.py
├── models.py          # 공유 데이터 클래스
├── interfaces.py      # Protocol 기반 인터페이스
├── adapters.py        # 기존 AlphaPulse dict → dataclass 변환
├── enums.py           # 열거형 (Side, OrderType, Mode 등)
├── calendar.py        # 한국 마켓 캘린더
├── cost_model.py      # 거래 비용 모델 (수수료, 세금, 슬리피지)
└── audit.py           # 감사 추적 로거
```

### 3.1 데이터 클래스 (`models.py`)

```python
from dataclasses import dataclass, field
from datetime import datetime

@dataclass(frozen=True)
class Stock:
    """종목 식별자"""
    code: str              # "005930"
    name: str              # "삼성전자"
    market: str            # "KOSPI" | "KOSDAQ" | "ETF"
    sector: str = ""       # "반도체" (ETF는 빈 문자열)

@dataclass
class OHLCV:
    """일봉 데이터"""
    date: str              # YYYYMMDD
    open: float
    high: float
    low: float
    close: float
    volume: int
    market_cap: float = 0  # 시가총액 (원)

@dataclass
class Position:
    """보유 포지션"""
    stock: Stock
    quantity: int
    avg_price: float       # 평균 매수가
    current_price: float   # 현재가 (최종 종가)
    unrealized_pnl: float  # 미실현 손익 (원)
    weight: float          # 포트폴리오 내 비중 (0~1)
    strategy_id: str       # 어떤 전략이 보유 중인지

@dataclass
class Order:
    """매매 주문"""
    stock: Stock
    side: str              # "BUY" | "SELL" (enums.Side)
    order_type: str        # "MARKET" | "LIMIT" (enums.OrderType)
    quantity: int
    price: float | None    # LIMIT일 때만
    strategy_id: str       # 발생 전략
    reason: str = ""       # 주문 사유 (감사 추적용)

@dataclass
class OrderResult:
    """주문 체결 결과"""
    order_id: str
    order: Order
    status: str            # "filled" | "partial" | "rejected" | "pending"
    filled_quantity: int
    filled_price: float
    commission: float      # 수수료
    tax: float             # 세금
    filled_at: datetime | None

@dataclass
class Signal:
    """종목 매매 시그널"""
    stock: Stock
    score: float           # -100 ~ +100
    factors: dict          # {"momentum": 0.8, "value": 0.3, ...}
    strategy_id: str
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class PortfolioSnapshot:
    """특정 시점의 포트폴리오 상태"""
    date: str
    cash: float
    positions: list[Position]
    total_value: float         # cash + 포지션 평가액 합
    daily_return: float        # 일간 수익률 (%)
    cumulative_return: float   # 누적 수익률 (%)
    drawdown: float            # 고점 대비 하락률 (%)

@dataclass
class StrategySynthesis:
    """AI 종합 판단 결과"""
    market_view: str               # 시장 전체 판단 요약
    conviction_level: float        # 확신도 (0~1)
    allocation_adjustment: dict    # {"topdown_etf": 0.35, ...}
    stock_opinions: list           # list[StockOpinion]
    risk_warnings: list[str]       # 리스크 경고 목록
    reasoning: str                 # 판단 근거 (투명성)

@dataclass
class StockOpinion:
    """AI 종목별 의견"""
    stock: Stock
    action: str           # "강력매수" | "매수" | "유지" | "축소" | "매도"
    reason: str           # 근거
    confidence: float     # 0~1
```

### 3.2 인터페이스 (`interfaces.py`)

모든 서브시스템은 Protocol 기반 인터페이스를 통해 소통한다. 구현체 교체가 자유롭다.

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class DataProvider(Protocol):
    """종목 데이터 소스"""
    def get_ohlcv(self, code: str, start: str, end: str) -> list[OHLCV]: ...
    def get_financials(self, code: str) -> dict: ...
    def get_investor_flow(self, code: str, days: int) -> dict: ...
    def get_short_interest(self, code: str, days: int) -> dict: ...

@runtime_checkable
class Strategy(Protocol):
    """매매 전략"""
    strategy_id: str
    rebalance_freq: str       # "daily" | "weekly" | "signal_driven"
    def generate_signals(self, universe: list[Stock],
                          market_context: dict) -> list[Signal]: ...

@runtime_checkable
class Broker(Protocol):
    """주문 집행"""
    def submit_order(self, order: Order) -> OrderResult: ...
    def cancel_order(self, order_id: str) -> bool: ...
    def get_balance(self) -> dict: ...
    def get_positions(self) -> list[Position]: ...
    def get_order_status(self, order_id: str) -> OrderResult: ...

@runtime_checkable
class RiskChecker(Protocol):
    """리스크 검증"""
    def check_order(self, order: Order,
                     portfolio: PortfolioSnapshot) -> RiskDecision: ...
    def check_portfolio(self, portfolio: PortfolioSnapshot) -> list[RiskAlert]: ...
```

### 3.3 열거형 (`enums.py`)

```python
from enum import StrEnum

class Side(StrEnum):
    BUY = "BUY"
    SELL = "SELL"

class OrderType(StrEnum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"

class TradingMode(StrEnum):
    BACKTEST = "backtest"
    PAPER = "paper"
    LIVE = "live"

class RebalanceFreq(StrEnum):
    DAILY = "daily"
    WEEKLY = "weekly"
    SIGNAL_DRIVEN = "signal_driven"

class RiskAction(StrEnum):
    APPROVE = "APPROVE"
    REDUCE_SIZE = "REDUCE_SIZE"
    REJECT = "REJECT"

class DrawdownAction(StrEnum):
    NORMAL = "NORMAL"
    WARN = "WARN"              # soft limit — 신규 매수 중단
    DELEVERAGE = "DELEVERAGE"  # hard limit — 강제 축소
```

### 3.4 마켓 캘린더 (`calendar.py`)

```python
class KRXCalendar:
    """한국거래소 영업일 관리"""

    # 고정 공휴일 + 매년 변동 공휴일 (설날, 추석 등)
    # 데이터 소스: KRX 공시 또는 pykrx 내장 캘린더

    def is_trading_day(self, date: str) -> bool: ...
    def next_trading_day(self, date: str) -> str: ...
    def prev_trading_day(self, date: str) -> str: ...
    def trading_days_between(self, start: str, end: str) -> list[str]: ...
    def is_half_day(self, date: str) -> bool: ...  # 반일장 (거의 없음)
```

- 기존 `Config.get_prev_trading_day()`는 주말만 스킵함. 공휴일 처리 강화.
- 백테스트 루프, 스케줄러, 피드백 수집 모두 이 캘린더를 사용.

### 3.5 거래 비용 모델 (`cost_model.py`)

```python
@dataclass
class CostModel:
    """전 모드 공통 거래 비용 모델"""

    # 수수료 (매수+매도 양방향)
    commission_rate: float = 0.00015   # 0.015% (한투 온라인 기준)

    # 세금 (매도 시에만)
    tax_rate_stock: float = 0.0018     # 주식 0.18% (2025년 기준)
    tax_rate_etf: float = 0.0          # ETF 매도세 면제

    # 슬리피지 모델
    slippage_model: str = "volume_based"
    # volume_based: 주문량/거래대금 비율로 추정
    # fixed: 고정 0.1%
    # none: 슬리피지 없음 (보수적 테스트용)

    def calculate_commission(self, amount: float) -> float:
        return amount * self.commission_rate

    def calculate_tax(self, amount: float, is_etf: bool) -> float:
        rate = self.tax_rate_etf if is_etf else self.tax_rate_stock
        return amount * rate

    def estimate_slippage(self, order: Order, avg_volume: int) -> float:
        """체결가 대비 예상 슬리피지 (%)"""
        if self.slippage_model == "none":
            return 0.0
        order_amount = order.quantity * (order.price or 0)
        avg_daily_amount = avg_volume * (order.price or 0)
        if avg_daily_amount == 0:
            return 0.003  # 거래량 없으면 0.3%
        impact_ratio = order_amount / avg_daily_amount
        if impact_ratio < 0.01:
            return 0.0
        elif impact_ratio < 0.05:
            return 0.001  # 0.1%
        else:
            return 0.003  # 0.3%

    def total_cost(self, order: Order, filled_price: float,
                   is_etf: bool, avg_volume: int) -> dict:
        """주문 총 비용 계산"""
        amount = order.quantity * filled_price
        return {
            "commission": self.calculate_commission(amount),
            "tax": self.calculate_tax(amount, is_etf) if order.side == "SELL" else 0,
            "slippage": self.estimate_slippage(order, avg_volume),
        }
```

- 백테스트, Paper, 실매매 모두 동일한 CostModel 사용.
- 파라미터는 Config에서 오버라이드 가능.

### 3.6 감사 추적 (`audit.py`)

```python
class AuditLogger:
    """모든 의사결정을 기록하는 감사 추적 시스템"""

    # 저장소: trading.db의 audit_log 테이블
    # 모든 주요 이벤트를 기록:
    #   - 시그널 생성 (전략 ID, 종목, 점수, 팩터)
    #   - AI 종합 판단 (입력 요약, 출력, 확신도)
    #   - 리스크 결정 (주문, APPROVE/REJECT, 사유)
    #   - 주문 제출/체결 (상세)
    #   - 드로다운 이벤트 (WARN/DELEVERAGE)
    #   - 포트폴리오 변경 (스냅샷 차이)

    def log_signal(self, signal: Signal, context: dict) -> None: ...
    def log_ai_synthesis(self, synthesis: StrategySynthesis,
                          inputs_summary: dict) -> None: ...
    def log_risk_decision(self, order: Order,
                           decision: RiskDecision) -> None: ...
    def log_order(self, order: Order, result: OrderResult) -> None: ...
    def log_drawdown_event(self, action: DrawdownAction,
                            drawdown_pct: float) -> None: ...
    def log_error(self, component: str, error: Exception,
                   context: dict) -> None: ...

    def query(self, event_type: str = None, start: str = None,
              end: str = None) -> list[dict]: ...
```

- 사후 분석, 디버깅, 규제 대응에 활용.
- `trading.db`의 `audit_log` 테이블에 JSON 직렬화하여 저장.

### 3.7 어댑터 (`adapters.py`)

```python
class PulseResultAdapter:
    """기존 SignalEngine dict → trading 데이터 모델 변환"""

    @staticmethod
    def to_market_context(pulse_result: dict) -> dict:
        """SignalEngine.run() 결과를 전략이 소비할 수 있는 형태로 변환"""
        return {
            "date": pulse_result["date"],
            "pulse_score": pulse_result["score"],
            "pulse_signal": pulse_result["signal"],
            "indicator_scores": pulse_result["indicator_scores"],
            "details": pulse_result["details"],
        }

    @staticmethod
    def to_feedback_context(hit_rates: dict, correlation: float) -> str:
        """FeedbackEvaluator 결과 → AI 종합 판단 입력 문자열"""
        ...
```

## 4. 종목 데이터 수집기 (`trading/data/`)

```
trading/data/
├── __init__.py
├── stock_collector.py       # OHLCV, 시가총액, 거래대금
├── fundamental_collector.py # 재무제표 (PER, PBR, ROE, 매출, 영업이익)
├── flow_collector.py        # 종목별 외국인/기관 수급
├── short_collector.py       # 공매도, 대차잔고, 신용잔고
├── universe.py              # 투자 유니버스 관리
└── store.py                 # 종목 데이터 SQLite 저장 (trading.db)
```

### 4.1 데이터 소스 매핑

각 데이터 항목에 1순위/2순위 소스를 지정한다. 구현 단계에서 1순위 소스의 실제 가용성을 검증하고, 불가 시 2순위 또는 대안 리서치를 진행한다.

| 데이터 | 1순위 소스 | 2순위 소스 (폴백) | 비고 |
|--------|-----------|-------------------|------|
| OHLCV (일봉) | pykrx `stock.get_market_ohlcv_by_ticker()` | FinanceDataReader | pykrx 검증됨 |
| 시가총액 | pykrx `stock.get_market_cap_by_ticker()` | KRX 정보데이터시스템 | pykrx 검증됨 |
| PER/PBR/배당수익률 | pykrx `stock.get_market_fundamental_by_ticker()` | 네이버 금융 스크래핑 | pykrx 검증 필요 |
| ROE/매출/영업이익 | pykrx 또는 KRX DART | 네이버 금융 스크래핑 | 구현 시 검증 |
| 종목별 외국인 보유 | pykrx `stock.get_exhaustion_rates_of_foreign_investment()` | 네이버 금융 | pykrx 검증 필요 |
| 종목별 기관 수급 | pykrx `stock.get_market_trading_value_by_date()` | KRX 스크래핑 | 구현 시 검증 |
| 공매도 잔고 | KRX 정보데이터시스템 스크래핑 | 네이버 금융 | 별도 스크래퍼 필요 |
| 신용/대차잔고 | 네이버 금융 스크래핑 | 한투 API (실시간) | 별도 스크래퍼 필요 |
| ETF 목록/구성종목 | pykrx ETF API | KRX ETF 정보 | 구현 시 검증 |
| ETF NAV/괴리율 | KRX 정보데이터시스템 | 한투 API | 구현 시 검증 |

**데이터 소스 검증 프로토콜:**
1. 구현 단계에서 각 소스에 실제 API 호출 테스트
2. 반환 데이터 형식, 필드 유무, 데이터 품질 확인
3. 실패 시 2순위 시도 → 모두 실패 시 대안 리서치 (증권사 API, 유료 데이터 등)
4. 각 소스의 호출 제한(rate limit), 가용 기간, 지연시간 문서화

### 4.2 유니버스 관리 (`universe.py`)

```python
class Universe:
    """투자 가능 종목 풀 관리"""

    def __init__(self, data_provider: DataProvider):
        self.provider = data_provider

    def get_kospi200(self) -> list[Stock]: ...
    def get_kosdaq150(self) -> list[Stock]: ...
    def get_etf_list(self, category: str = None) -> list[Stock]:
        """category: "index" | "leverage" | "inverse" | "sector" | "bond" | None(전체)"""
        ...
    def get_all_tradable(self) -> list[Stock]:
        """KOSPI + KOSDAQ + ETF 전체 (관리종목, 거래정지 제외)"""
        ...
    def filter(self, stocks: list[Stock],
               min_market_cap: float = None,
               min_avg_volume: float = None,
               min_listing_days: int = None) -> list[Stock]:
        """유동성/시총 기준 필터링"""
        ...
```

### 4.3 저장소 스키마 (`trading.db`)

```sql
-- 종목 기본정보 (일 1회 갱신)
CREATE TABLE stocks (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    market TEXT NOT NULL,         -- "KOSPI" | "KOSDAQ" | "ETF"
    sector TEXT DEFAULT "",
    market_cap REAL DEFAULT 0,
    is_tradable INTEGER DEFAULT 1,  -- 0: 거래정지/관리종목
    updated_at REAL
);

-- 일봉 데이터 (누적)
CREATE TABLE ohlcv (
    code TEXT NOT NULL,
    date TEXT NOT NULL,
    open REAL, high REAL, low REAL, close REAL,
    volume INTEGER,
    market_cap REAL DEFAULT 0,
    PRIMARY KEY (code, date)
);

-- 재무제표 (분기별)
CREATE TABLE fundamentals (
    code TEXT NOT NULL,
    date TEXT NOT NULL,           -- 분기 기준일 YYYYMMDD
    per REAL, pbr REAL, roe REAL,
    revenue REAL,                 -- 매출액 (원)
    operating_profit REAL,        -- 영업이익 (원)
    net_income REAL,              -- 순이익 (원)
    debt_ratio REAL,              -- 부채비율 (%)
    dividend_yield REAL,          -- 배당수익률 (%)
    PRIMARY KEY (code, date)
);

-- 종목별 수급 (일별)
CREATE TABLE stock_investor_flow (
    code TEXT NOT NULL,
    date TEXT NOT NULL,
    foreign_net REAL,             -- 외국인 순매수 (원)
    institutional_net REAL,       -- 기관 순매수 (원)
    individual_net REAL,          -- 개인 순매수 (원)
    foreign_holding_pct REAL,     -- 외국인 보유 비중 (%)
    PRIMARY KEY (code, date)
);

-- 공매도/신용 (일별)
CREATE TABLE short_interest (
    code TEXT NOT NULL,
    date TEXT NOT NULL,
    short_volume INTEGER,         -- 공매도 수량
    short_balance INTEGER,        -- 공매도 잔고
    short_ratio REAL,             -- 공매도 비율 (%)
    credit_balance REAL,          -- 신용잔고 (원)
    lending_balance REAL,         -- 대차잔고 (주)
    PRIMARY KEY (code, date)
);

-- ETF 정보
CREATE TABLE etf_info (
    code TEXT PRIMARY KEY,
    name TEXT,
    category TEXT,                -- "index" | "leverage" | "inverse" | "sector" | "bond"
    underlying TEXT,              -- 추적 지수/자산
    expense_ratio REAL,           -- 총보수 (%)
    nav REAL,                     -- 순자산가치
    updated_at REAL
);

-- 감사 추적 로그
CREATE TABLE audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp REAL NOT NULL,
    event_type TEXT NOT NULL,     -- "signal" | "ai_synthesis" | "risk_decision" | "order" | "drawdown" | "error"
    component TEXT NOT NULL,      -- "momentum_strategy" | "risk_manager" | "kis_broker" 등
    data TEXT NOT NULL,           -- JSON 직렬화
    mode TEXT NOT NULL            -- "backtest" | "paper" | "live"
);
```

## 5. 종목 스크리닝/랭킹 엔진 (`trading/screening/`)

```
trading/screening/
├── __init__.py
├── factors.py            # 개별 팩터 계산
├── ranker.py             # 멀티팩터 종합 랭킹
├── filter.py             # 투자 제외 조건
└── universe_selector.py  # 전략별 유니버스 → 최종 후보
```

### 5.1 팩터 정의

```python
class FactorCalculator:
    """개별 팩터 점수 계산 — 유니버스 내 percentile(0~100)로 정규화"""

    def __init__(self, data_provider: DataProvider):
        self.provider = data_provider

    # 모멘텀 팩터
    def momentum_1m(self, code: str) -> float: ...   # 1개월 수익률
    def momentum_3m(self, code: str) -> float: ...   # 3개월 수익률
    def momentum_6m(self, code: str) -> float: ...   # 6개월 수익률
    def momentum_12m(self, code: str) -> float: ...  # 12개월 수익률 (최근 1개월 제외)
    def high_52w_proximity(self, code: str) -> float: ...  # 52주 신고가 근접도

    # 밸류 팩터
    def value_per(self, code: str) -> float: ...      # PER 역수 (E/P)
    def value_pbr(self, code: str) -> float: ...      # PBR 역수 (B/P)
    def value_psr(self, code: str) -> float: ...      # PSR 역수 (S/P)
    def dividend_yield(self, code: str) -> float: ... # 배당수익률

    # 퀄리티 팩터
    def quality_roe(self, code: str) -> float: ...              # ROE
    def quality_profit_growth(self, code: str) -> float: ...    # 영업이익 성장률 (YoY)
    def quality_debt_ratio(self, code: str) -> float: ...       # 부채비율 역수 (낮을수록 좋음)

    # 수급 팩터
    def flow_foreign(self, code: str, days: int = 20) -> float: ...        # 외국인 N일 순매수 비율
    def flow_institutional(self, code: str, days: int = 20) -> float: ...  # 기관 N일 순매수 비율
    def flow_trend(self, code: str) -> float: ...                          # 수급 추세 (5/20일 이평 교차)

    # 역발상 팩터
    def short_decrease(self, code: str) -> float: ...    # 공매도 잔고 감소율
    def credit_change(self, code: str) -> float: ...     # 신용잔고 변화율

    # 변동성 팩터
    def volatility(self, code: str, days: int = 60) -> float: ...        # 일간 변동성
    def beta(self, code: str, benchmark: str = "KOSPI") -> float: ...    # 시장 베타
    def downside_vol(self, code: str, days: int = 60) -> float: ...      # 하방 변동성
```

각 팩터는 유니버스 전체에서 percentile로 변환된다. 높을수록 해당 팩터에서 우수.

### 5.2 멀티팩터 랭킹

```python
class MultiFactorRanker:
    """멀티팩터 종합 점수 → 종목 랭킹"""

    def __init__(self, factor_calculator: FactorCalculator,
                 weights: dict[str, float]):
        # weights 예시:
        # {"momentum": 0.3, "value": 0.25, "quality": 0.2,
        #  "flow": 0.15, "volatility": 0.1}
        self.weights = weights

    def rank(self, universe: list[Stock]) -> list[Signal]:
        """
        1. 유니버스 전 종목에 대해 모든 팩터 계산
        2. 각 팩터를 percentile(0~100)로 정규화
        3. 카테고리별 평균 → 카테고리 점수
        4. 가중 합산 → 종합 점수 (-100~+100 스케일 변환)
        5. 점수순 정렬 → list[Signal] 반환
        """
        ...
```

- 팩터 가중치는 Config에서 로드. 전략별로 다른 가중치 사용 가능.
- 결측 팩터(데이터 없음)는 해당 팩터 제외 후 나머지로 재정규화.

### 5.3 투자 제외 필터

```python
class StockFilter:
    """투자 부적격 종목 제외"""

    def __init__(self, config: dict):
        self.min_market_cap = config.get("min_market_cap", 100_000_000_000)  # 1000억
        self.min_avg_volume = config.get("min_avg_volume", 1_000_000_000)    # 10억 (일평균 거래대금)
        self.min_listing_days = config.get("min_listing_days", 180)          # 상장 후 6개월
        self.exclude_sectors = config.get("exclude_sectors", [])             # 제외 섹터

    def apply(self, stocks: list[Stock]) -> list[Stock]:
        """
        제외 조건:
        - 관리종목, 거래정지, 정리매매
        - 시가총액 min_market_cap 미만
        - 일평균 거래대금 min_avg_volume 미만 (유동성 부족)
        - 상장 후 min_listing_days 미만 (IPO 직후 변동성)
        - 제외 섹터 목록에 해당
        - ETF: 일평균 거래대금 + 괴리율 과대 종목 제외
        """
        ...
```

## 6. 전략 프레임워크 (`trading/strategy/`)

```
trading/strategy/
├── __init__.py
├── base.py                # Strategy ABC (공통 로직)
├── topdown_etf.py         # 탑다운 ETF 전략
├── momentum.py            # 모멘텀 전략
├── value.py               # 밸류 전략
├── quality_momentum.py    # 퀄리티+모멘텀 복합
├── registry.py            # 전략 등록/관리
├── allocator.py           # 멀티전략 간 자금 배분
└── ai_synthesizer.py      # LLM 기반 최종 전략 종합
```

### 6.1 기본 전략 클래스

```python
class BaseStrategy(ABC):
    """모든 전략의 기본 클래스"""

    strategy_id: str
    rebalance_freq: RebalanceFreq

    def __init__(self, screener: MultiFactorRanker,
                 config: dict):
        self.screener = screener
        self.config = config  # 전략별 파라미터 (Config에서 로드)

    @abstractmethod
    def generate_signals(self, universe: list[Stock],
                          market_context: dict) -> list[Signal]:
        """종목별 매매 시그널 생성"""
        ...

    def should_rebalance(self, last_rebalance: str,
                          current_date: str,
                          market_context: dict) -> bool:
        """리밸런싱 시점 판단"""
        if self.rebalance_freq == RebalanceFreq.DAILY:
            return True
        elif self.rebalance_freq == RebalanceFreq.WEEKLY:
            # 매주 월요일 (또는 월요일이 공휴일이면 그 다음 거래일)
            return is_week_start(current_date)
        elif self.rebalance_freq == RebalanceFreq.SIGNAL_DRIVEN:
            # 점수 급변 시에만 (전일 대비 변화량 임계값 초과)
            return self._signal_changed_enough(market_context)
```

### 6.2 탑다운 ETF 전략

```python
class TopDownETFStrategy(BaseStrategy):
    """Market Pulse Score → ETF 포지션 결정"""

    strategy_id = "topdown_etf"
    rebalance_freq = RebalanceFreq.SIGNAL_DRIVEN

    # Score → ETF 매핑 (Config에서 오버라이드 가능)
    ETF_MAP = {
        "strong_bullish":      {"KODEX 레버리지": 0.7, "KODEX 200": 0.3},
        "moderately_bullish":  {"KODEX 200": 0.8, "KODEX 단기채권": 0.2},
        "neutral":             {"KODEX 단기채권": 0.5, "KODEX 200": 0.3, "현금": 0.2},
        "moderately_bearish":  {"KODEX 인버스": 0.5, "KODEX 단기채권": 0.3, "현금": 0.2},
        "strong_bearish":      {"KODEX 200선물인버스2X": 0.4, "KODEX 단기채권": 0.3, "현금": 0.3},
    }

    def generate_signals(self, universe, market_context):
        pulse_signal = market_context["pulse_signal"]
        # 현재 시장 시그널에 해당하는 ETF 매핑 조회
        # 각 ETF에 대해 목표 비중을 Signal로 변환
        ...

    def _signal_changed_enough(self, market_context) -> bool:
        """Market Pulse 시그널 레벨이 변경되었을 때만 리밸런싱"""
        # 예: "매수 우위" → "중립" 변경 시 True
        ...
```

### 6.3 개별 종목 전략

```python
class MomentumStrategy(BaseStrategy):
    """상위 모멘텀 종목 롱 — 주간 리밸런싱"""

    strategy_id = "momentum"
    rebalance_freq = RebalanceFreq.WEEKLY

    def __init__(self, screener, config):
        super().__init__(screener, config)
        self.top_n = config.get("top_n", 20)
        self.factor_weights = {
            "momentum": 0.6, "flow": 0.3, "volatility": 0.1
        }

    def generate_signals(self, universe, market_context):
        # 1. Market Pulse가 매도 우위 이하면 시그널 강도 축소 (0.5배)
        # 2. screener.rank(universe) with momentum factor_weights
        # 3. 상위 top_n 종목 → 매수 시그널
        # 4. 기존 보유 중 탈락 종목 → 매도 시그널
        ...

class ValueStrategy(BaseStrategy):
    """저평가 + 퀄리티 복합 — 주간 리밸런싱"""

    strategy_id = "value"
    rebalance_freq = RebalanceFreq.WEEKLY

    def __init__(self, screener, config):
        super().__init__(screener, config)
        self.top_n = config.get("top_n", 15)
        self.factor_weights = {
            "value": 0.4, "quality": 0.3, "momentum": 0.2, "flow": 0.1
        }

class QualityMomentumStrategy(BaseStrategy):
    """퀄리티 + 모멘텀 복합 — 주간 리밸런싱"""

    strategy_id = "quality_momentum"
    rebalance_freq = RebalanceFreq.WEEKLY

    def __init__(self, screener, config):
        super().__init__(screener, config)
        self.top_n = config.get("top_n", 15)
        self.factor_weights = {
            "quality": 0.35, "momentum": 0.35, "flow": 0.2, "volatility": 0.1
        }
```

### 6.4 전략 Registry & Allocator

```python
class StrategyRegistry:
    """전략 등록/조회"""

    def __init__(self):
        self._strategies: dict[str, Strategy] = {}

    def register(self, strategy: Strategy) -> None:
        self._strategies[strategy.strategy_id] = strategy

    def get(self, strategy_id: str) -> Strategy:
        return self._strategies[strategy_id]

    def list_all(self) -> list[str]:
        return list(self._strategies.keys())


class StrategyAllocator:
    """멀티전략 간 자금 배분"""

    def __init__(self, base_allocations: dict[str, float]):
        # {"topdown_etf": 0.30, "momentum": 0.40, "value": 0.30}
        # 합계 = 1.0
        self.base_allocations = base_allocations

    def adjust_by_market_regime(self, pulse_score: float,
                                 ai_synthesis: StrategySynthesis | None
                                 ) -> dict[str, float]:
        """
        Market Pulse + AI 판단에 따라 동적 배분 조정:
        - 강한 매수 → 종목 전략 비중↑, ETF 비중↓
        - 강한 매도 → ETF 인버스 비중↑, 종목 전략 비중↓
        - 중립 → 밸류 전략 비중↑
        - AI synthesis의 allocation_adjustment가 있으면 반영 (가중 평균)
        """
        ...

    def get_capital(self, strategy_id: str,
                     total_capital: float) -> float:
        """전략별 할당 가능 자금"""
        return total_capital * self.current_allocations[strategy_id]
```

### 6.5 AI 전략 종합 (`ai_synthesizer.py`)

```python
class StrategyAISynthesizer:
    """정량 + 정성 분석을 LLM으로 종합하여 최종 전략 판단"""

    def __init__(self):
        self.config = Config()
        # google.genai.Client (기존 에이전트 패턴)

    async def synthesize(
        self,
        pulse_result: dict,                    # Market Pulse 11개 지표
        ranked_stocks: list[Signal],           # 팩터 스크리닝 상위 종목
        strategy_signals: dict[str, list[Signal]],  # 전략별 시그널
        content_summaries: list[str],          # 콘텐츠 분석 결과
        feedback_context: str | None,          # 적중률/피드백
        current_portfolio: PortfolioSnapshot,  # 현재 포트폴리오
    ) -> StrategySynthesis:
        """
        LLM에 전달하는 프롬프트 구성:
        1. 시장 상황 (pulse_score, 각 지표 상세)
        2. 팩터 분석 요약 (상위 종목, 팩터별 특징)
        3. 전략별 시그널 요약
        4. 정성 분석 (블로그/뉴스 인사이트)
        5. 과거 성과 피드백 (적중률, 편향)
        6. 현재 포트폴리오 상태

        출력: StrategySynthesis (structured output)
        - 전략 배분 조정 제안
        - 종목별 AI 의견 (StockOpinion)
        - 리스크 경고
        - 판단 근거
        """
        ...

    async def _call_llm(self, prompt: str) -> str:
        """asyncio.to_thread()로 sync genai API 호출"""
        return await asyncio.to_thread(
            self.client.models.generate_content,
            model=self.model_name,
            contents=prompt,
        )

    def _fallback(self, strategy_signals: dict) -> StrategySynthesis:
        """LLM 실패 시 — 규칙 기반 기본 판단 (정량만)"""
        return StrategySynthesis(
            market_view="AI 분석 불가 — 정량 시그널 기반 실행",
            conviction_level=0.5,
            allocation_adjustment=self.allocator.base_allocations,
            stock_opinions=[],
            risk_warnings=["AI 종합 판단 실패. 규칙 기반으로 실행됨."],
            reasoning="LLM 호출 실패로 정량 시그널만 사용",
        )
```

**핵심 원칙:**
- AI는 **조언자** 역할. LLM 실패 시 규칙 기반 `_fallback()`으로 안전 실행.
- `conviction_level`이 낮으면(< 0.3) allocator가 현금 비중을 높임.
- `reasoning` 필드로 모든 판단 근거를 기록 → audit_log에 저장.
- 기존 에이전트 패턴 동일: `asyncio.to_thread()`, try/except, fallback.

## 7. 포트폴리오 관리자 (`trading/portfolio/`)

```
trading/portfolio/
├── __init__.py
├── manager.py           # 포트폴리오 매니저 (핵심)
├── position_sizer.py    # 포지션 사이징
├── rebalancer.py        # 리밸런싱 (목표 vs 현재 → 주문)
├── optimizer.py         # 포트폴리오 최적화 (mean-variance, risk parity)
├── attribution.py       # 성과 귀속 분석
└── store.py             # 포트폴리오 이력 저장 (portfolio.db)
```

### 7.1 포트폴리오 매니저

```python
class PortfolioManager:
    """목표 포트폴리오 산출 → 리밸런싱 주문 생성"""

    def __init__(self, position_sizer: PositionSizer,
                 optimizer: PortfolioOptimizer,
                 risk_manager: RiskManager,
                 cost_model: CostModel):
        ...

    def update_target(
        self,
        strategy_signals: dict[str, list[Signal]],
        ai_synthesis: StrategySynthesis | None,
        allocator: StrategyAllocator,
        current: PortfolioSnapshot,
    ) -> TargetPortfolio:
        """
        목표 포트폴리오 산출:
        1. 전략별 배분 비율 적용 (AI 조정 반영)
        2. 전략별 종목 시그널 → 목표 비중 산출
        3. 포지션 사이징 (변동성 조정 or Kelly)
        4. 포트폴리오 최적화 (상관관계 반영)
        5. 리스크 제약 적용 (종목 한도, 섹터 한도)
        6. 거래 비용 고려 (비중 변화 < 최소 거래 임계값이면 무시)
        """
        ...

    def generate_orders(
        self,
        target: TargetPortfolio,
        current: PortfolioSnapshot,
    ) -> list[Order]:
        """
        현재 → 목표 차이를 주문으로 변환:
        1. 매도 먼저 (자금 확보)
        2. 매수 다음
        3. 최소 거래금액 미만 차이는 무시 (수수료 효율)
        4. 동일 종목 다수 전략 보유 시 net 주문 생성
        """
        ...
```

### 7.2 포지션 사이징

```python
class PositionSizer:
    """종목당 투자 비중 결정"""

    def equal_weight(self, n_stocks: int) -> float:
        """균등 배분 — 1/N"""
        return 1.0 / n_stocks

    def volatility_adjusted(self, volatilities: dict[str, float],
                             target_vol: float = 0.15) -> dict[str, float]:
        """
        변동성 역수 비중:
        - 변동성 낮을수록 비중↑ (안정적 종목 더 많이)
        - target_vol: 포트폴리오 목표 변동성 (연 15%)
        """
        ...

    def kelly(self, win_rate: float, avg_win: float,
              avg_loss: float) -> float:
        """
        켈리 기준 최적 비중:
        - half-kelly 적용 (과도한 집중 방지)
        - 피드백 시스템의 적중률 기반
        """
        kelly_fraction = win_rate - (1 - win_rate) / (avg_win / avg_loss)
        return max(0, kelly_fraction * 0.5)  # half-kelly

    def ai_adjusted(self, base_weight: float,
                     opinion: StockOpinion) -> float:
        """
        AI 확신도 반영:
        - confidence > 0.7 → 비중 1.2배 (상한: max_position_weight)
        - confidence < 0.3 → 비중 0.7배
        - "매도" 의견 → 비중 0
        """
        ...
```

### 7.3 포트폴리오 최적화

```python
class PortfolioOptimizer:
    """수학적 포트폴리오 최적화"""

    def mean_variance(self, expected_returns: pd.Series,
                       cov_matrix: pd.DataFrame,
                       constraints: dict) -> dict[str, float]:
        """
        마코위츠 평균-분산 최적화 (scipy.optimize.minimize):
        - 목적함수: 샤프 비율 최대화
        - 제약: 비중 합 = 1, 종목당 최대 비중, 섹터 최대 비중
        """
        ...

    def risk_parity(self, cov_matrix: pd.DataFrame) -> dict[str, float]:
        """
        리스크 패리티:
        - 각 종목의 리스크 기여도(Risk Contribution)를 균등화
        - 수익 예측 불필요, 공분산만으로 산출
        """
        ...

    def min_variance(self, cov_matrix: pd.DataFrame) -> dict[str, float]:
        """
        최소 분산 포트폴리오:
        - 포트폴리오 전체 변동성 최소화
        - 방어적 시장에서 사용
        """
        ...

    def select_method(self, market_context: dict) -> str:
        """
        시장 상황에 따라 최적화 방법 자동 선택:
        - 강한 매수/매도 → mean_variance (방향성 활용)
        - 중립 → risk_parity (불확실 시 균등 리스크)
        - 강한 매도 → min_variance (방어적)
        """
        ...
```

### 7.4 성과 귀속 분석 (`attribution.py`)

```python
class PerformanceAttribution:
    """수익률 원천 분석"""

    def strategy_attribution(self, snapshots: list[PortfolioSnapshot],
                              trades: list) -> dict:
        """
        전략별 수익 기여도:
        - topdown_etf: +1.2%
        - momentum: +0.8%
        - value: -0.3%
        """
        ...

    def factor_attribution(self, snapshots: list[PortfolioSnapshot],
                            factor_returns: dict) -> dict:
        """
        팩터별 수익 기여도:
        - 모멘텀 팩터: +0.9%
        - 밸류 팩터: +0.2%
        - 수급 팩터: +0.5%
        - 잔여(알파): +0.1%
        """
        ...

    def sector_attribution(self, snapshots: list[PortfolioSnapshot]) -> dict:
        """섹터별 수익 기여도"""
        ...
```

### 7.5 저장소 (`portfolio.db`)

```sql
-- 일별 포트폴리오 스냅샷
CREATE TABLE snapshots (
    date TEXT NOT NULL,
    mode TEXT NOT NULL,             -- "backtest" | "paper" | "live"
    run_id TEXT DEFAULT "",         -- 백테스트 run_id (live/paper는 빈 문자열)
    cash REAL,
    total_value REAL,
    positions TEXT,                 -- JSON: [{code, quantity, avg_price, weight, strategy_id}]
    daily_return REAL,
    cumulative_return REAL,
    drawdown REAL,
    PRIMARY KEY (date, mode, run_id)
);

-- 주문 이력
CREATE TABLE orders (
    order_id TEXT PRIMARY KEY,
    mode TEXT NOT NULL,
    run_id TEXT DEFAULT "",
    date TEXT, stock_code TEXT, stock_name TEXT,
    side TEXT, order_type TEXT,
    quantity INTEGER, price REAL,
    strategy_id TEXT, reason TEXT,
    status TEXT,                    -- "filled" | "partial" | "rejected" | "cancelled"
    filled_quantity INTEGER,
    filled_price REAL,
    commission REAL, tax REAL,
    created_at REAL, filled_at REAL
);

-- 거래 이력 (체결 기준)
CREATE TABLE trades (
    trade_id TEXT PRIMARY KEY,
    order_id TEXT,
    mode TEXT NOT NULL,
    run_id TEXT DEFAULT "",
    date TEXT, stock_code TEXT,
    side TEXT, quantity INTEGER, price REAL,
    commission REAL, tax REAL,
    strategy_id TEXT,
    realized_pnl REAL              -- 매도 시 실현 손익
);

-- 성과 귀속 (일별)
CREATE TABLE attribution (
    date TEXT NOT NULL,
    mode TEXT NOT NULL,
    run_id TEXT DEFAULT "",
    strategy_returns TEXT,          -- JSON: {"topdown_etf": 0.012, ...}
    factor_returns TEXT,            -- JSON: {"momentum": 0.009, ...}
    sector_returns TEXT,            -- JSON: {"반도체": 0.005, ...}
    PRIMARY KEY (date, mode, run_id)
);
```

## 8. 리스크 엔진 (`trading/risk/`)

```
trading/risk/
├── __init__.py
├── manager.py          # 리스크 매니저 (통합)
├── limits.py           # 하드 리밋 정의
├── var.py              # VaR / CVaR 계산
├── correlation.py      # 상관관계 분석 + 집중도
├── stress_test.py      # 시나리오 스트레스 테스트
├── drawdown.py         # 드로다운 모니터링 + 자동 디레버리징
└── report.py           # 리스크 리포트 생성
```

### 8.1 하드 리밋

```python
@dataclass
class RiskLimits:
    """
    절대 위반 불가 제약 조건.
    AI, 전략, 사용자 모두 오버라이드 불가.
    Config(.env)에서 로드, 코드 수정 없이 튜닝 가능.
    """
    # 집중도
    max_position_weight: float = 0.10      # 종목당 최대 10%
    max_sector_weight: float = 0.30        # 섹터당 최대 30%
    max_etf_leverage: float = 0.20         # 레버리지/인버스 ETF 최대 20%
    max_total_exposure: float = 1.0        # 총 노출도 100% (레버리지 없음)

    # 손실 제한
    max_drawdown_soft: float = 0.10        # -10% → 경고 + 신규 매수 중단
    max_drawdown_hard: float = 0.15        # -15% → 전 포지션 50% 자동 축소
    max_daily_loss: float = 0.03           # 일간 -3% → 당일 매매 중단

    # 유동성
    min_cash_ratio: float = 0.05           # 최소 현금 5% 유지
    max_single_order_pct: float = 0.05     # 단일 주문 총자산의 5% 이하
    max_order_to_volume: float = 0.10      # 주문량 ≤ 일평균 거래량의 10%

    # VaR
    max_portfolio_var_95: float = 0.03     # 95% VaR ≤ 3%
```

### 8.2 VaR/CVaR

```python
class VaRCalculator:
    """포트폴리오 손실 위험 측정"""

    def historical_var(self, returns: pd.Series,
                        confidence: float = 0.95) -> float:
        """과거 수익률 분포 기반 VaR"""
        return -np.percentile(returns, (1 - confidence) * 100)

    def parametric_var(self, weights: np.ndarray,
                        cov_matrix: np.ndarray,
                        confidence: float = 0.95) -> float:
        """분산-공분산 기반 VaR (정규분포 가정)"""
        portfolio_vol = np.sqrt(weights @ cov_matrix @ weights)
        z_score = norm.ppf(confidence)
        return portfolio_vol * z_score

    def cvar(self, returns: pd.Series,
              confidence: float = 0.95) -> float:
        """Conditional VaR (Expected Shortfall) — 꼬리 리스크"""
        var = self.historical_var(returns, confidence)
        return -returns[returns <= -var].mean()
```

### 8.3 드로다운 자동 대응

```python
class DrawdownManager:
    """드로다운 모니터링 + 자동 디레버리징"""

    def __init__(self, limits: RiskLimits, audit: AuditLogger):
        self.limits = limits
        self.audit = audit
        self.peak_value: float = 0

    def update_peak(self, current_value: float) -> None:
        self.peak_value = max(self.peak_value, current_value)

    def check(self, portfolio: PortfolioSnapshot) -> DrawdownAction:
        self.update_peak(portfolio.total_value)
        drawdown = (self.peak_value - portfolio.total_value) / self.peak_value

        if drawdown < self.limits.max_drawdown_soft:
            return DrawdownAction.NORMAL
        elif drawdown < self.limits.max_drawdown_hard:
            self.audit.log_drawdown_event(DrawdownAction.WARN, drawdown)
            return DrawdownAction.WARN      # 신규 매수 중단
        else:
            self.audit.log_drawdown_event(DrawdownAction.DELEVERAGE, drawdown)
            return DrawdownAction.DELEVERAGE  # 강제 축소

    def generate_deleverage_orders(self,
                                    portfolio: PortfolioSnapshot) -> list[Order]:
        """
        전 포지션 50% 축소:
        - 손실 큰 포지션부터 우선
        - 최소 거래 단위 고려
        """
        ...
```

### 8.4 스트레스 테스트

```python
class StressTest:
    """시나리오별 포트폴리오 손실 시뮬레이션"""

    SCENARIOS = {
        "2020_covid":      {"kospi": -0.35, "kosdaq": -0.40, "desc": "COVID-19 급락"},
        "2022_rate_hike":  {"kospi": -0.25, "kosdaq": -0.35, "desc": "금리 인상기"},
        "flash_crash":     {"kospi": -0.10, "kosdaq": -0.15, "desc": "일간 급락"},
        "won_crisis":      {"kospi": -0.20, "fx_usdkrw": +0.15, "desc": "원화 위기"},
        "sector_collapse": {"specific_sector": -0.50, "desc": "특정 섹터 붕괴"},
    }

    def run(self, portfolio: PortfolioSnapshot,
            scenario: str) -> StressResult:
        """
        시나리오 적용:
        1. 포트폴리오 내 종목별 시장/섹터 민감도(베타) 계산
        2. 시나리오 충격 적용
        3. 예상 손실 + 종목별 기여도 산출
        """
        ...

    def run_all(self, portfolio: PortfolioSnapshot) -> dict[str, StressResult]:
        """전 시나리오 일괄 실행"""
        ...

    def add_custom_scenario(self, name: str, shocks: dict) -> None:
        """사용자 정의 시나리오 추가"""
        self.SCENARIOS[name] = shocks
```

### 8.5 리스크 매니저 (통합)

```python
class RiskManager:
    """모든 리스크 체크 통합"""

    def __init__(self, limits: RiskLimits, var_calc: VaRCalculator,
                 drawdown_mgr: DrawdownManager, audit: AuditLogger):
        ...

    def check_order(self, order: Order,
                     portfolio: PortfolioSnapshot) -> RiskDecision:
        """
        주문 실행 전 검증 (순서대로):
        1. 일간 손실 한도 체크 → 초과 시 REJECT
        2. 드로다운 상태 체크 → WARN이면 매수 REJECT
        3. 종목 비중 한도 체크 → 초과 시 REDUCE_SIZE
        4. 섹터 집중도 체크 → 초과 시 REDUCE_SIZE
        5. 레버리지 ETF 한도 체크
        6. 최소 현금 비율 체크
        7. 주문량/거래량 비율 체크
        8. VaR 한도 체크 → 초과 시 REDUCE_SIZE
        → APPROVE / REDUCE_SIZE / REJECT + 사유
        """
        ...

    def check_portfolio(self, portfolio: PortfolioSnapshot) -> list[RiskAlert]:
        """
        포트폴리오 전체 리스크 점검 (일일 리포트용):
        - 드로다운 상태
        - VaR / CVaR
        - 섹터 집중도
        - 상관관계 집중도
        - 스트레스 테스트 요약
        """
        ...

    def daily_report(self, portfolio: PortfolioSnapshot) -> RiskReport:
        """일일 리스크 리포트 생성"""
        ...


@dataclass
class RiskDecision:
    action: RiskAction           # APPROVE | REDUCE_SIZE | REJECT
    reason: str                  # 사유
    adjusted_quantity: int | None  # REDUCE_SIZE일 때 조정된 수량


@dataclass
class RiskAlert:
    level: str                   # "INFO" | "WARNING" | "CRITICAL"
    category: str                # "drawdown" | "concentration" | "var" | "liquidity"
    message: str
    current_value: float
    limit_value: float
```

## 9. 백테스트 엔진 (`trading/backtest/`)

```
trading/backtest/
├── __init__.py
├── engine.py            # 백테스트 엔진 (시간 루프)
├── data_feed.py         # 히스토리 데이터 피드 (look-ahead bias 방지)
├── sim_broker.py        # 시뮬레이션 브로커
├── metrics.py           # 성과 지표
├── report.py            # 리포트 (HTML + 터미널)
└── store.py             # 결과 저장 (backtest.db)
```

### 9.1 핵심 설계: 실매매와 동일 코드 경로

```
                     ┌─── SimBroker (백테스트)     — 네트워크 없음, 로컬 시뮬레이션
Strategy → Portfolio → Risk → Broker ──┤
                     ├─── PaperBroker (모의투자)   — 한투 모의 서버
                     └─── KISBroker (실매매)       — 한투 실전 서버
```

전략, 포트폴리오, 리스크 코드는 **하나도 바꾸지 않고** 브로커만 교체.

### 9.2 백테스트 엔진

```python
class BacktestEngine:
    """시간 순서대로 전략 파이프라인 시뮬레이션"""

    def __init__(self, config: BacktestConfig):
        """
        config:
            strategies: list[str]           # 전략 ID 목록
            allocations: dict[str, float]   # 전략별 배분
            initial_capital: float          # 초기 자본
            start_date: str                 # YYYYMMDD
            end_date: str                   # YYYYMMDD
            cost_model: CostModel           # 거래 비용
            risk_limits: RiskLimits         # 리스크 제약
            use_ai: bool = False            # AI 종합 사용 여부 (느림)
            benchmark: str = "KOSPI"        # 벤치마크
        """
        self.sim_broker = SimBroker(config.cost_model)
        self.portfolio_manager = PortfolioManager(...)
        self.risk_manager = RiskManager(config.risk_limits, ...)

    def run(self) -> BacktestResult:
        """
        메인 루프:
        for date in trading_days(start, end):
            1. data_feed.advance_to(date)    # 미래 데이터 차단
            2. 전략별 시그널 생성
            3. (선택) AI 종합 판단
            4. 포트폴리오 목표 산출
            5. 리스크 체크
            6. 주문 생성 → SimBroker 체결
            7. 일별 스냅샷 저장
            8. 드로다운 체크 (디레버리징 트리거)
        """
        ...

    def _save_result(self, result: BacktestResult) -> str:
        """backtest.db에 저장, run_id 반환"""
        ...
```

### 9.3 시뮬레이션 브로커

```python
class SimBroker:
    """가상 체결 엔진"""

    def __init__(self, cost_model: CostModel):
        self.cost_model = cost_model
        self.cash: float = 0
        self.positions: dict[str, Position] = {}

    def submit_order(self, order: Order) -> OrderResult:
        """
        체결 시뮬레이션:
        - MARKET: 당일 종가로 체결 (보수적 가정)
        - LIMIT:
            매수: 저가 ≤ 지정가 → 체결
            매도: 고가 ≥ 지정가 → 체결
        - 슬리피지: cost_model.estimate_slippage() 적용
        - 수수료 + 세금: cost_model에서 계산
        """
        ...
```

### 9.4 Look-Ahead Bias 방지

```python
class HistoricalDataFeed:
    """DataProvider 구현 — 미래 데이터 접근 차단"""

    def __init__(self, all_data: dict[str, pd.DataFrame]):
        self._all_data = all_data
        self._current_date: str = ""

    def advance_to(self, date: str) -> None:
        """현재 날짜를 전진 — 이 날짜 이후 데이터 접근 불가"""
        self._current_date = date

    def get_ohlcv(self, code: str, start: str, end: str) -> list[OHLCV]:
        assert end <= self._current_date, \
            f"Look-ahead bias! Requested {end} but current date is {self._current_date}"
        return self._filter(code, start, end)

    def get_financials(self, code: str) -> dict:
        """발표일 기준으로 필터 — 미발표 재무제표 접근 차단"""
        ...
```

### 9.5 성과 지표

```python
class BacktestMetrics:
    """백테스트 결과 분석"""

    def calculate(self, snapshots: list[PortfolioSnapshot],
                   benchmark_returns: pd.Series,
                   risk_free_rate: float = 0.035) -> dict:
        return {
            # 수익률
            "total_return": float,             # 총 수익률 (%)
            "cagr": float,                     # 연환산 수익률 (%)
            "monthly_returns": list[float],    # 월별 수익률

            # 리스크
            "volatility": float,               # 연 변동성 (%)
            "max_drawdown": float,             # 최대 낙폭 (%)
            "max_drawdown_duration": int,      # MDD 지속 기간 (영업일)
            "downside_deviation": float,       # 하방 변동성

            # 리스크 조정 수익
            "sharpe_ratio": float,             # 샤프 비율
            "sortino_ratio": float,            # 소르티노 비율
            "calmar_ratio": float,             # CAGR / MDD

            # 거래
            "total_trades": int,               # 총 거래 횟수
            "win_rate": float,                 # 승률 (%)
            "profit_factor": float,            # 총이익 / 총손실
            "avg_win": float,                  # 평균 수익 거래 (%)
            "avg_loss": float,                 # 평균 손실 거래 (%)
            "turnover": float,                 # 연간 회전율

            # 벤치마크 비교
            "benchmark_return": float,         # 벤치마크 수익률
            "excess_return": float,            # 초과 수익 (알파)
            "beta": float,                     # 시장 베타
            "alpha": float,                    # 젠센 알파
            "information_ratio": float,        # 정보 비율
            "tracking_error": float,           # 추적 오차
        }
```

### 9.6 저장소 (`backtest.db`)

```sql
-- 백테스트 실행 이력
CREATE TABLE runs (
    run_id TEXT PRIMARY KEY,
    name TEXT,                      -- 사용자 지정 이름
    strategies TEXT,                -- JSON: ["momentum", "value"]
    allocations TEXT,               -- JSON: {"momentum": 0.5, "value": 0.5}
    params TEXT,                    -- JSON: 전체 파라미터
    start_date TEXT, end_date TEXT,
    initial_capital REAL,
    final_value REAL,
    metrics TEXT,                   -- JSON: 성과 지표 전체
    created_at REAL
);

-- 일별 스냅샷은 portfolio.db의 snapshots 테이블 공유 (run_id로 구분)
-- 거래 이력도 portfolio.db의 trades 테이블 공유
```

## 10. 증권사 API 연동 (`trading/broker/`)

```
trading/broker/
├── __init__.py
├── base.py              # Broker Protocol + 공통 유틸
├── kis_client.py        # 한투 API 클라이언트 (인증, REST)
├── kis_broker.py        # 실매매 브로커
├── paper_broker.py      # 모의투자 브로커
├── safeguard.py         # 실매매 안전장치
└── monitor.py           # 주문 모니터링 + 체결 알림
```

### 10.1 한투 API 클라이언트

```python
class KISClient:
    """한국투자증권 Open API REST 클라이언트"""

    # 모의투자: https://openapivts.koreainvestment.com
    # 실전:     https://openapi.koreainvestment.com

    def __init__(self, app_key: str, app_secret: str,
                 account_no: str, is_paper: bool = True):
        self.base_url = (
            "https://openapivts.koreainvestment.com"
            if is_paper else
            "https://openapi.koreainvestment.com"
        )
        self._access_token: str = ""
        self._token_expires: datetime | None = None

    # 인증
    def get_access_token(self) -> str: ...
    def _refresh_token_if_needed(self) -> None: ...
    def _headers(self) -> dict: ...

    # 주문
    def place_order(self, code: str, side: str, qty: int,
                     price: int, order_type: str) -> dict: ...
    def cancel_order(self, order_no: str) -> dict: ...
    def modify_order(self, order_no: str, qty: int, price: int) -> dict: ...

    # 조회
    def get_balance(self) -> dict: ...
    def get_positions(self) -> list[dict]: ...
    def get_order_history(self, date: str) -> list[dict]: ...
    def get_execution_history(self, date: str) -> list[dict]: ...

    # 시세
    def get_current_price(self, code: str) -> dict: ...
    def get_daily_prices(self, code: str, days: int) -> list[dict]: ...
```

### 10.2 실매매 / 모의투자 브로커

```python
class KISBroker:
    """한투 실전 API — Broker Protocol 구현"""

    def __init__(self, client: KISClient, audit: AuditLogger):
        assert not client.is_paper, "실매매 브로커에 모의투자 클라이언트 사용 불가"
        self.client = client
        self.audit = audit

    def submit_order(self, order: Order) -> OrderResult:
        result = self.client.place_order(...)
        self.audit.log_order(order, result)
        return self._to_order_result(result)

    def get_positions(self) -> list[Position]:
        raw = self.client.get_positions()
        return [self._to_position(r) for r in raw]


class PaperBroker:
    """한투 모의투자 API — KISBroker와 동일, 서버만 다름"""

    def __init__(self, client: KISClient, audit: AuditLogger):
        assert client.is_paper, "모의투자 브로커에 실전 클라이언트 사용 불가"
        # ... KISBroker와 동일한 구현
```

### 10.3 안전장치

```python
class TradingSafeguard:
    """실매매 전용 안전장치"""

    def __init__(self, config: dict):
        self.live_enabled = config.get("LIVE_TRADING_ENABLED", False)
        self.max_daily_orders = config.get("MAX_DAILY_ORDERS", 50)
        self.max_daily_amount = config.get("MAX_DAILY_AMOUNT", 50_000_000)

    def check_live_allowed(self) -> bool:
        """LIVE_TRADING_ENABLED=true 여부 확인"""
        if not self.live_enabled:
            raise RuntimeError(
                "실매매가 비활성화 상태입니다. "
                "LIVE_TRADING_ENABLED=true 설정 후 재시작하세요."
            )
        return True

    def confirm_live_start(self, account_no: str) -> bool:
        """터미널에서 사용자 수동 확인"""
        response = input(
            f"실매매를 시작합니다.\n"
            f"계좌: {account_no}\n"
            f"확인하시겠습니까? (yes/no): "
        )
        return response.strip().lower() == "yes"

    def check_daily_limit(self, today_orders: int,
                           today_amount: float) -> bool:
        """일일 주문 한도 체크"""
        if today_orders >= self.max_daily_orders:
            raise RuntimeError(f"일일 주문 한도 초과: {today_orders}/{self.max_daily_orders}")
        if today_amount >= self.max_daily_amount:
            raise RuntimeError(f"일일 금액 한도 초과: {today_amount:,.0f}/{self.max_daily_amount:,.0f}")
        return True
```

### 10.4 Config 추가

```python
# .env 추가 항목
KIS_APP_KEY=...                    # 한투 앱 키
KIS_APP_SECRET=...                 # 한투 앱 시크릿
KIS_ACCOUNT_NO=...                 # 계좌번호
KIS_IS_PAPER=true                  # true: 모의투자, false: 실전

LIVE_TRADING_ENABLED=false         # 실매매 최종 스위치 (이중 안전장치)
MAX_DAILY_ORDERS=50                # 일일 주문 한도
MAX_DAILY_AMOUNT=50000000          # 일일 금액 한도 (5천만원)

# 전략 설정
STRATEGY_ALLOCATIONS={"topdown_etf":0.3,"momentum":0.4,"value":0.3}
MOMENTUM_TOP_N=20
VALUE_TOP_N=15
```

## 11. 트레이딩 오케스트레이터 (`trading/orchestrator/`)

```
trading/orchestrator/
├── __init__.py
├── engine.py            # 트레이딩 엔진 (메인 루프)
├── scheduler.py         # 스케줄링 (시간대별 실행)
├── monitor.py           # 시스템 모니터링 + 헬스체크
└── alert.py             # 텔레그램 알림 통합
```

### 11.1 트레이딩 엔진 — 일일 파이프라인

```python
class TradingEngine:
    """전체 매매 파이프라인 오케스트레이션"""

    def __init__(self, mode: TradingMode):
        self.mode = mode
        self.broker = self._create_broker(mode)
        self.data_provider = StockDataProvider(...)
        self.screener = MultiFactorRanker(...)
        self.strategies = self._load_strategies()
        self.allocator = StrategyAllocator(...)
        self.portfolio_manager = PortfolioManager(...)
        self.risk_manager = RiskManager(...)
        self.ai_synthesizer = StrategyAISynthesizer()
        self.alert = TradingAlert(...)
        self.audit = AuditLogger(...)

    async def run_daily(self, date: str = None):
        """일일 매매 사이클 — 5 Phase"""

        # ── Phase 1: 데이터 수집 (08:00) ──
        market_context = self._collect_market_data(date)
        self._update_stock_data()

        # ── Phase 2: 분석 (08:00~08:30) ──
        universe = self._get_filtered_universe()
        strategy_signals = {}
        for strategy in self.strategies:
            if strategy.should_rebalance(last, date, market_context):
                signals = strategy.generate_signals(universe, market_context)
                strategy_signals[strategy.strategy_id] = signals

        # AI 종합 판단
        content_summaries = self._get_content_summaries()
        feedback_context = self._get_feedback_context()
        current_portfolio = self._get_current_portfolio()

        ai_synthesis = await self.ai_synthesizer.synthesize(
            pulse_result=market_context,
            ranked_stocks=self._get_top_ranked(universe),
            strategy_signals=strategy_signals,
            content_summaries=content_summaries,
            feedback_context=feedback_context,
            current_portfolio=current_portfolio,
        )

        # ── Phase 3: 포트폴리오 (08:30~08:50) ──
        adjusted_alloc = self.allocator.adjust_by_market_regime(
            market_context["pulse_score"], ai_synthesis
        )
        target = self.portfolio_manager.update_target(
            strategy_signals, ai_synthesis, self.allocator, current_portfolio
        )
        orders = self.portfolio_manager.generate_orders(target, current_portfolio)

        # 리스크 체크
        approved_orders = []
        for order in orders:
            decision = self.risk_manager.check_order(order, current_portfolio)
            self.audit.log_risk_decision(order, decision)
            if decision.action == RiskAction.APPROVE:
                approved_orders.append(order)
            elif decision.action == RiskAction.REDUCE_SIZE:
                order.quantity = decision.adjusted_quantity
                approved_orders.append(order)
            # REJECT → 건너뜀

        # 장전 알림
        await self.alert.pre_market(market_context, approved_orders, ai_synthesis)

        # ── Phase 4: 실행 (09:00) ──
        for order in approved_orders:
            result = self.broker.submit_order(order)
            self.audit.log_order(order, result)
            await self.alert.execution(order, result)

        # ── Phase 5: 사후 관리 (15:30~) ──
        snapshot = self._take_snapshot()
        self._save_snapshot(snapshot)

        # 드로다운 체크
        dd_action = self.risk_manager.drawdown_mgr.check(snapshot)
        if dd_action == DrawdownAction.DELEVERAGE:
            deleverage_orders = self.risk_manager.drawdown_mgr \
                .generate_deleverage_orders(snapshot)
            for order in deleverage_orders:
                self.broker.submit_order(order)
            await self.alert.risk_alert("드로다운 하드 리밋 도달. 포지션 50% 축소 실행.")

        # 일일 리포트
        risk_report = self.risk_manager.daily_report(snapshot)
        await self.alert.post_market(snapshot, risk_report)

    def _create_broker(self, mode: TradingMode) -> Broker:
        if mode == TradingMode.BACKTEST:
            return SimBroker(self.cost_model)
        elif mode == TradingMode.PAPER:
            client = KISClient(..., is_paper=True)
            return PaperBroker(client, self.audit)
        elif mode == TradingMode.LIVE:
            safeguard = TradingSafeguard(...)
            safeguard.check_live_allowed()
            safeguard.confirm_live_start(...)
            client = KISClient(..., is_paper=False)
            return KISBroker(client, self.audit)
```

### 11.2 스케줄링

```python
class TradingScheduler:
    """한국 시장 시간대 기반 스케줄링"""

    SCHEDULE = {
        "data_update":      "08:00",   # 데이터 수집
        "analysis":         "08:15",   # 분석 + 시그널
        "portfolio":        "08:40",   # 포트폴리오 산출
        "pre_market_alert": "08:50",   # 매매 계획 알림
        "market_open":      "09:00",   # 주문 제출
        "midday_check":     "12:30",   # signal_driven 전략 중간 체크
        "market_close":     "15:30",   # 장 마감 처리
        "post_market":      "16:00",   # 성과 + 리스크 리포트
    }

    def __init__(self, engine: TradingEngine, calendar: KRXCalendar):
        self.engine = engine
        self.calendar = calendar

    async def run_daemon(self):
        """스케줄 기반 데몬 모드"""
        while True:
            now = datetime.now()
            today = now.strftime("%Y%m%d")

            if not self.calendar.is_trading_day(today):
                # 공휴일 → 다음 거래일까지 대기
                next_day = self.calendar.next_trading_day(today)
                await self._sleep_until(next_day, "08:00")
                continue

            for phase, time_str in self.SCHEDULE.items():
                await self._wait_until(time_str)
                await self._run_phase(phase)

            # 다음 거래일까지 대기
            next_day = self.calendar.next_trading_day(today)
            await self._sleep_until(next_day, "07:50")
```

### 11.3 텔레그램 알림

```python
class TradingAlert:
    """기존 Notifier 재사용 — 매매 전용 메시지"""

    async def pre_market(self, context: dict, orders: list[Order],
                          synthesis: StrategySynthesis | None):
        """
        08:50 — 오늘 매매 계획:
        📊 Market Pulse: +35.2 (매수 우위)
        🤖 AI 확신도: 72%
        📋 매수 예정: 삼성전자 외 3종목
        📋 매도 예정: SK하이닉스 외 1종목
        ⚠️ 리스크: VaR -2.1%, MDD -5.3%
        """
        ...

    async def execution(self, order: Order, result: OrderResult):
        """체결 즉시 알림"""
        ...

    async def post_market(self, snapshot: PortfolioSnapshot,
                           risk_report: RiskReport):
        """
        16:00 — 일일 성과:
        💰 총 자산: 108,350,000원 (+0.42%)
        📈 일간 수익: +450,000원
        📉 MDD: -3.2% (한도 -15%)
        🏆 KOSPI 대비: +0.15%
        """
        ...

    async def risk_alert(self, message: str):
        """긴급 리스크 알림 (즉시)"""
        ...

    async def weekly_report(self, attribution: dict):
        """주간 성과 귀속 리포트 (월요일)"""
        ...
```

### 11.4 장애 복구

```python
class RecoveryManager:
    """장애 발생 시 복구 전략"""

    def on_crash_recovery(self):
        """
        시스템 재시작 시:
        1. 마지막 스냅샷 로드 → 포트폴리오 상태 복원
        2. 미체결 주문 확인 (broker.get_order_history)
        3. 실제 잔고와 DB 상태 비교 → 불일치 시 경고
        4. 불일치 해소 후 정상 운영 재개
        """
        ...

    def reconcile(self, db_positions: list[Position],
                   broker_positions: list[Position]) -> list[str]:
        """
        DB ↔ 증권사 잔고 대사:
        - 일치 → 정상
        - 불일치 → 경고 알림 + 수동 확인 요청
        - 자동 수정은 하지 않음 (안전 우선)
        """
        ...
```

### 11.5 CLI 확장

```bash
# 매매 실행
ap trading run --mode paper                    # 모의투자 1회 실행
ap trading run --mode paper --daemon           # 모의투자 데몬 모드
ap trading run --mode live                     # 실매매 (확인 프롬프트)

# 포트폴리오
ap trading portfolio                           # 현재 포트폴리오 상태
ap trading portfolio history --days 30         # 성과 이력
ap trading portfolio attribution --days 30     # 성과 귀속

# 리스크
ap trading risk report                         # 리스크 리포트
ap trading risk stress                         # 스트레스 테스트
ap trading risk limits                         # 현재 리밋 설정 확인

# 백테스트
ap trading backtest --strategy momentum --start 20200101 --end 20241231
ap trading backtest --strategy all --capital 100000000
ap trading backtest list                       # 과거 결과 목록
ap trading backtest report <run_id>            # 상세 리포트
ap trading backtest compare <run_id1> <run_id2>  # 비교

# 스크리닝
ap trading screen --factor momentum --top 30   # 팩터 스크리닝
ap trading screen --strategy value             # 전략 기반 스크리닝

# 시스템
ap trading status                              # 시스템 상태
ap trading reconcile                           # DB ↔ 증권사 대사
```

## 12. 구현 순서

각 서브시스템이 독립적으로 테스트 가능하며, 이전 단계 위에 쌓는 구조.

| 단계 | 서브시스템 | 의존성 | 예상 테스트 |
|------|-----------|--------|------------|
| **①** | `trading/core/` — 데이터 모델, 인터페이스, 캘린더, 비용 모델 | 없음 | 단위 테스트 |
| **②** | `trading/data/` — 종목 데이터 수집기 | ① | 데이터 소스 검증 + 단위 테스트 |
| **③** | `trading/screening/` — 팩터 스크리닝/랭킹 | ①② | 팩터 계산 정확성 |
| **④** | `trading/strategy/` — 전략 프레임워크 (AI 제외) | ①②③ + 기존 market/ | 시그널 생성 로직 |
| **⑤** | `trading/portfolio/` — 포트폴리오 관리 | ①④ | 최적화 + 주문 생성 |
| **⑥** | `trading/risk/` — 리스크 엔진 | ①⑤ | 리밋 검증 + VaR 계산 |
| **⑦** | `trading/backtest/` — 백테스트 엔진 | ①~⑥ | 히스토리 시뮬레이션 |
| **⑧** | `trading/strategy/ai_synthesizer.py` — AI 종합 | ④ + 기존 agents/ | LLM mock 테스트 |
| **⑨** | `trading/broker/` — 한투 API 연동 | ① | 모의투자 서버 테스트 |
| **⑩** | `trading/orchestrator/` — 통합 오케스트레이터 | 전체 | 통합 테스트 |

## 13. 신규 의존성

```toml
# pyproject.toml [project.dependencies] 추가
"scipy>=1.11",          # 포트폴리오 최적화 (mean-variance)
"scikit-learn>=1.3",    # 상관관계, 통계 분석
```

기존 의존성(pandas, numpy, pykrx, requests, google-adk, rich, click)은 그대로 사용.

## 14. 테스트 전략

```bash
# 전체
pytest tests/trading/ -v

# 서브시스템별
pytest tests/trading/core/ -v        # 데이터 모델, 캘린더, 비용
pytest tests/trading/data/ -v        # 수집기 (mock API)
pytest tests/trading/screening/ -v   # 팩터 계산
pytest tests/trading/strategy/ -v    # 전략 시그널
pytest tests/trading/portfolio/ -v   # 포트폴리오 최적화
pytest tests/trading/risk/ -v        # 리스크 리밋
pytest tests/trading/backtest/ -v    # 백테스트 엔진
pytest tests/trading/broker/ -v      # 브로커 (mock)
pytest tests/trading/orchestrator/ -v # 통합
```

**테스트 원칙:**
- 기존 프로젝트 TDD 원칙 유지 (test first → red → implement → green)
- 외부 API (pykrx, 한투) → mock/patch
- LLM (Gemini) → `@patch("...._call_llm")` (기존 패턴)
- 백테스트 → 알려진 기간의 예상 결과와 비교
- 리스크 → 경계값 테스트 (한도 정확히 도달, 초과 시 동작)

## 15. 설계 원칙 요약

1. **Protocol 기반 인터페이스** — 구현체 교체 자유 (브로커 3종, 데이터 소스 폴백)
2. **동일 코드 경로** — 백테스트/Paper/실매매가 브로커만 다르고 나머지 동일
3. **AI는 조언자** — LLM 실패해도 규칙 기반 fallback. 리스크 리밋은 AI 오버라이드 불가
4. **Config 외부화** — 팩터 가중치, 전략 파라미터, 리스크 리밋 모두 .env에서 튜닝
5. **감사 추적** — 모든 의사결정(시그널, AI 판단, 리스크 결정, 주문) 기록
6. **기존 시스템 무변경** — market/, content/, feedback/ 읽기 전용 소비
7. **단계적 구현** — ①~⑩ 순서대로, 각 단계 독립 테스트 후 다음 진행
8. **안전 우선** — 이중 안전장치(env 스위치 + 터미널 확인), 드로다운 자동 대응, 일일 한도
