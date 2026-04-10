# AlphaPulse Trading System 가이드

자동 투자 및 포트폴리오 운용 시스템 사용 가이드.

---

## 목차

1. [개요](#1-개요)
2. [아키텍처](#2-아키텍처)
3. [설치 및 설정](#3-설치-및-설정)
4. [빠른 시작 가이드](#4-빠른-시작-가이드)
5. [CLI 명령어 레퍼런스](#5-cli-명령어-레퍼런스)
6. [전략 가이드](#6-전략-가이드)
7. [팩터 레퍼런스](#7-팩터-레퍼런스)
8. [리스크 관리](#8-리스크-관리)
9. [백테스트 가이드](#9-백테스트-가이드)
10. [안전장치](#10-안전장치)
11. [개발자 가이드](#11-개발자-가이드)

---

## 1. 개요

AlphaPulse Trading System은 기존 AlphaPulse 분석 플랫폼 위에 구축된 **자동 매매 실행 레이어**다.

기존 시스템이 제공하는 정량 분석(Market Pulse Score, 11개 지표), 정성 분석(Content Intelligence), 피드백 학습을 **매매 결정의 입력**으로 활용하여 종목 스크리닝부터 주문 체결까지 전체 파이프라인을 자동화한다.

### 핵심 특징

| 항목 | 내용 |
|------|------|
| 매매 대상 | 한국 주식 (KOSPI/KOSDAQ) + ETF |
| 전략 유형 | 탑다운 ETF + 개별 종목(팩터) + 멀티전략 배분 |
| 매매 모드 | 백테스트, 모의투자(Paper), 실매매(Live) |
| 증권사 | 한국투자증권 Open API |
| 리스크 관리 | VaR/CVaR, 드로다운 자동 디레버리징, 스트레스 테스트, 하드 리밋 |
| AI 연동 | 정량 + 정성 + 피드백 -> LLM 종합 판단 -> 최종 전략 수립 |
| 팩터 | 20개 팩터 (모멘텀, 밸류, 퀄리티, 수급, 역발상, 변동성) |

### 기존 시스템과의 관계

```
기존 AlphaPulse (읽기 전용 소비)           Trading System
----------------------------------        -----------------------
SignalEngine.run() ──────────────────>  TradingEngine (Market Pulse Score 입력)
Content Analysis ────────────────────>  AI Synthesizer (정성 판단 입력)
FeedbackEvaluator.get_hit_rates() ──>  AI Synthesizer (적중률 -> 확신도 조정)
Notifier (Telegram) ─────────────────>  TradingAlert (알림 채널 재사용)
Config ──────────────────────────────>  trading 설정 확장
```

기존 모듈(`market/`, `content/`, `feedback/`)은 **변경하지 않는다**. Trading System은 읽기 전용으로 소비한다.

---

## 2. 아키텍처

### 2.1 모듈 구조

```
alphapulse/trading/
├── core/            # 공유 인터페이스, 데이터 모델, 캘린더, 비용 모델
│   ├── models.py          # Stock, OHLCV, Position, Order, Signal 등
│   ├── interfaces.py      # Protocol 기반 인터페이스 (DataProvider, Strategy, Broker)
│   ├── enums.py           # Side, OrderType, TradingMode, RebalanceFreq 등
│   ├── calendar.py        # KRXCalendar (한국 거래일 관리)
│   ├── cost_model.py      # CostModel (수수료, 세금, 슬리피지)
│   ├── audit.py           # AuditLogger (감사 추적)
│   └── adapters.py        # PulseResultAdapter (기존 시스템 데이터 변환)
│
├── data/            # 종목 데이터 수집기 (SYNC)
│   ├── stock_collector.py       # OHLCV, 시가총액
│   ├── fundamental_collector.py # 재무제표 (PER, PBR, ROE 등)
│   ├── flow_collector.py        # 외국인/기관 종목별 수급
│   ├── short_collector.py       # 공매도, 대차잔고, 신용잔고
│   ├── universe.py              # 투자 유니버스 관리
│   └── store.py                 # TradingStore (SQLite)
│
├── screening/       # 팩터 스크리닝/랭킹 (SYNC)
│   ├── factors.py            # 20개 팩터 계산기
│   ├── ranker.py             # 멀티팩터 종합 랭킹
│   ├── filter.py             # 투자 부적격 종목 필터
│   └── universe_selector.py  # 전략별 유니버스 선별
│
├── strategy/        # 전략 프레임워크 (SYNC + AI는 ASYNC)
│   ├── base.py               # BaseStrategy (ABC)
│   ├── topdown_etf.py        # TopDownETFStrategy (시그널 드리븐)
│   ├── momentum.py           # MomentumStrategy (주간 리밸런싱)
│   ├── value.py              # ValueStrategy (주간 리밸런싱)
│   ├── quality_momentum.py   # QualityMomentumStrategy (주간 리밸런싱)
│   ├── registry.py           # StrategyRegistry
│   ├── allocator.py          # StrategyAllocator (멀티전략 자금 배분)
│   └── ai_synthesizer.py     # StrategyAISynthesizer (LLM 종합 판단)
│
├── portfolio/       # 포트폴리오 관리 (SYNC)
│   ├── manager.py           # PortfolioManager (목표 포트폴리오 산출)
│   ├── position_sizer.py    # PositionSizer (equal, volatility, kelly)
│   ├── rebalancer.py        # Rebalancer (목표 vs 현재 -> 주문)
│   ├── optimizer.py         # PortfolioOptimizer (mean-variance, risk parity)
│   ├── attribution.py       # PerformanceAttribution (성과 귀속)
│   ├── models.py            # TargetPortfolio 등 포트폴리오 전용 모델
│   └── store.py             # PortfolioStore (SQLite)
│
├── risk/            # 리스크 엔진 (SYNC)
│   ├── manager.py           # RiskManager (통합)
│   ├── limits.py            # RiskLimits, RiskDecision, RiskAlert
│   ├── var.py               # VaRCalculator (Historical, Parametric, CVaR)
│   ├── correlation.py       # 상관관계 분석 + 집중도
│   ├── drawdown.py          # DrawdownManager (자동 디레버리징)
│   ├── stress_test.py       # StressTest (5개 시나리오)
│   └── report.py            # 리스크 리포트 생성
│
├── backtest/        # 백테스트 엔진 (SYNC)
│   ├── engine.py            # BacktestEngine (시간 루프)
│   ├── data_feed.py         # HistoricalDataFeed (look-ahead bias 방지)
│   ├── sim_broker.py        # SimBroker (가상 체결)
│   ├── metrics.py           # BacktestMetrics (22개 성과 지표)
│   ├── report.py            # 리포트 생성
│   └── store.py             # BacktestStore (결과 저장)
│
├── broker/          # 증권사 API 연동 (SYNC)
│   ├── kis_client.py        # KISClient (한투 REST API 클라이언트)
│   ├── kis_broker.py        # KISBroker (실매매)
│   ├── paper_broker.py      # PaperBroker (모의투자)
│   ├── safeguard.py         # TradingSafeguard (이중 안전장치)
│   └── monitor.py           # 주문 모니터링 + 체결 알림
│
└── orchestrator/    # 트레이딩 오케스트레이터 (ASYNC)
    ├── engine.py            # TradingEngine (5단계 일일 파이프라인)
    ├── scheduler.py         # TradingScheduler (시간대별 실행)
    ├── monitor.py           # 시스템 헬스체크
    ├── recovery.py          # RecoveryManager (장애 복구, 잔고 대사)
    └── alert.py             # TradingAlert (텔레그램 알림)
```

### 2.2 데이터 흐름

```
[08:00] 데이터 수집
          ├── Market Pulse Score (기존 SignalEngine)
          ├── 종목 데이터 갱신 (OHLCV, 재무, 수급)
          └── 콘텐츠 분석 결과 + 피드백 컨텍스트
                    |
                    v
[08:15] 분석 (Screening -> Strategy -> AI)
          ├── 팩터 계산 (20개 팩터)
          ├── 종목 랭킹 (멀티팩터 가중합)
          ├── 전략별 시그널 생성 (TopDown, Momentum, Value, QualityMomentum)
          └── AI 종합 판단 (LLM: 정량+정성+피드백 -> 최종 판단)
                    |
                    v
[08:40] 포트폴리오 산출
          ├── 멀티전략 배분 (시장 상황 반영)
          ├── 목표 포트폴리오 계산 (포지션 사이징, 최적화)
          ├── 리스크 검증 (주문별 APPROVE / REDUCE_SIZE / REJECT)
          └── 장전 알림 (텔레그램)
                    |
                    v
[09:00] 주문 실행
          ├── 승인된 주문 -> 증권사 API 전송
          └── 체결 알림 (텔레그램)
                    |
                    v
[15:30] 사후 관리
          ├── 포트폴리오 스냅샷 저장
          ├── 드로다운 체크 (자동 디레버리징 트리거)
          └── 일일 성과 + 리스크 리포트
```

### 2.3 동일 코드 경로 원칙

전략, 포트폴리오, 리스크 코드는 동일하며 **Broker 구현체만 교체**한다:

```
                     +--- SimBroker (백테스트)     -- 로컬 시뮬레이션
Strategy -> Portfolio -> Risk -> Broker ---+--- PaperBroker (모의투자) -- 한투 모의 서버
                     +--- KISBroker (실매매)    -- 한투 실전 서버
```

### 2.4 Sync/Async 규칙

| 모듈 | 방식 | 이유 |
|------|------|------|
| `trading/data/` | Sync | pykrx, requests 기반 |
| `trading/screening/` | Sync | 순수 계산 |
| `trading/strategy/` (기본) | Sync | 규칙 기반 로직 |
| `trading/strategy/ai_synthesizer.py` | Async | LLM 호출 (`asyncio.to_thread()`) |
| `trading/portfolio/` | Sync | 수학 계산 |
| `trading/risk/` | Sync | 수학 계산 |
| `trading/backtest/` | Sync | 시뮬레이션 루프 |
| `trading/broker/` | Sync | REST API (requests) |
| `trading/orchestrator/` | Async | 전체 통합 (`asyncio.run()`은 CLI entry만) |

---

## 3. 설치 및 설정

### 3.1 필수 의존성

기존 AlphaPulse 의존성 외에 Trading System이 추가로 필요로 하는 패키지:

```bash
pip install "scipy>=1.11" "scikit-learn>=1.3"
```

AlphaPulse를 개발 모드로 설치하면 자동으로 포함된다:

```bash
pip install -e ".[dev]"
```

### 3.2 환경 변수 설정

`.env` 파일에 다음 항목을 추가한다.

#### 한국투자증권 API (모의투자/실매매 공통)

```bash
# 한투 Open API 인증 정보
# https://apiportal.koreainvestment.com 에서 발급
KIS_APP_KEY=your_app_key_here
KIS_APP_SECRET=your_app_secret_here
KIS_ACCOUNT_NO=12345678-01        # 계좌번호

# 모의투자/실전 선택 (기본: 모의투자)
KIS_IS_PAPER=true
```

#### 안전장치

```bash
# 실매매 최종 스위치 (기본: false)
# true로 설정해도 터미널에서 추가 확인 필요
LIVE_TRADING_ENABLED=false

# 일일 주문 한도
MAX_DAILY_ORDERS=50                # 최대 주문 횟수
MAX_DAILY_AMOUNT=50000000          # 최대 주문 금액 (원, 기본 5천만)
```

#### 전략 설정

```bash
# 멀티전략 자금 배분 비율 (합계 = 1.0)
STRATEGY_ALLOCATIONS={"topdown_etf":0.3,"momentum":0.4,"value":0.3}

# 개별 전략 파라미터
MOMENTUM_TOP_N=20                  # 모멘텀 전략 선정 종목 수
VALUE_TOP_N=15                     # 밸류 전략 선정 종목 수
```

### 3.3 설정 예시: 모의투자 시작용

```bash
# .env 파일 (최소 설정)
GEMINI_API_KEY=your_gemini_key
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

KIS_APP_KEY=PSxxxxxxxxxxxxxxxxxxxxxx
KIS_APP_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
KIS_ACCOUNT_NO=12345678-01
KIS_IS_PAPER=true

LIVE_TRADING_ENABLED=false
STRATEGY_ALLOCATIONS={"topdown_etf":0.3,"momentum":0.4,"value":0.3}
```

### 3.4 설정 예시: 실매매 전환

```bash
# 실매매 전환 시 변경 사항
KIS_IS_PAPER=false
LIVE_TRADING_ENABLED=true
MAX_DAILY_ORDERS=30                # 보수적으로 시작
MAX_DAILY_AMOUNT=10000000          # 1천만원부터 시작
```

> **주의**: `LIVE_TRADING_ENABLED=true`로 설정해도 `ap trading run --mode live` 실행 시 터미널에서 계좌번호를 확인하는 2차 프롬프트가 표시된다. 두 단계를 모두 통과해야 실매매가 시작된다.

---

## 4. 빠른 시작 가이드

### 4.0 데이터 수집 (최초 1회)

스크리닝/백테스트/매매를 하기 전에 종목 데이터를 먼저 수집해야 한다.

```bash
# 초기 전종목 수집 (KOSPI + KOSDAQ, 3년치, 약 1-2시간 소요)
ap trading data collect --market ALL --years 3

# 특정 시장만 수집
ap trading data collect --market KOSPI --years 5

# 수집 현황 확인
ap trading data status

# 수집 중단 후 재개 (체크포인트 기반 자동 재개)
ap trading data collect   # 마지막 체크포인트에서 이어서 수집

# 일일 증분 업데이트 (마지막 수집일 이후만, 수분 소요)
ap trading data update
```

수집 데이터는 `data/trading.db` (SQLite)에 저장된다:
- `stocks`: 종목 기본정보 (~2,500 종목)
- `ohlcv`: 일봉 데이터 (~200만 rows / 3년)
- `fundamentals`: 재무제표 PER/PBR/배당수익률
- `stock_investor_flow`: 종목별 외국인/기관 수급
- `collection_metadata`: 마지막 수집일 추적

**데이터 소스 (네이버 금융 크롤링 통일):**
- 종목 목록: `sise_market_sum.naver` (KOSPI/KOSDAQ 시가총액 페이지)
- OHLCV: `sise_day.naver` (종목별 일별 시세)
- 수급: `frgn.naver` (외국인/기관 순매매량)
- 재무: `item/main.naver` (PER/PBR/배당수익률)
- 최근 거래일: 삼성전자(005930) 일별 시세 첫 행에서 자동 감지

> 이후 매일 `ap trading data update` 또는 TradingEngine이 자동으로 증분 업데이트를 수행한다.

### 4.1 종목 스크리닝

팩터 기반으로 종목을 랭킹하여 상위 종목을 확인한다.

```bash
# KOSPI 모멘텀 상위 20종목
ap trading screen --market KOSPI --top 20 --factor momentum

# KOSDAQ 밸류 상위 15종목
ap trading screen --market KOSDAQ --top 15 --factor value

# 퀄리티 기반 스크리닝
ap trading screen --factor quality --top 30

# 밸런스드 (모든 팩터 균등)
ap trading screen --factor balanced --top 20
```

출력 예시:

```
============================================================
 KOSPI 종목 스크리닝 (팩터: momentum, 상위 20)
============================================================
 순위  종목코드  종목명        점수  주요팩터
 --------------------------------------------------------
    1  005930    삼성전자      +72.3  momentum
    2  000660    SK하이닉스    +68.1  momentum
    3  035420    NAVER        +61.5  flow
   ...
```

### 4.2 모의투자 실행

한투 모의투자 서버로 전체 파이프라인을 1회 실행한다.

```bash
# 1회 실행
ap trading run --mode paper

# 데몬 모드 (한국 시장 시간대에 맞춰 자동 반복)
ap trading run --mode paper --daemon
```

데몬 모드의 일일 스케줄:

| 시간 | 단계 |
|------|------|
| 08:00 | 데이터 수집 |
| 08:15 | 분석 + 시그널 생성 |
| 08:40 | 포트폴리오 산출 |
| 08:50 | 장전 알림 (텔레그램) |
| 09:00 | 주문 제출 |
| 12:30 | signal_driven 전략 중간 체크 |
| 15:30 | 장 마감 처리 |
| 16:00 | 성과 + 리스크 리포트 |

### 4.3 실매매 실행

실매매는 이중 안전장치를 통과해야 한다.

```bash
# 1단계: .env 설정
# KIS_IS_PAPER=false
# LIVE_TRADING_ENABLED=true

# 2단계: CLI 실행 -> 터미널 확인 프롬프트 표시
ap trading run --mode live
```

실행 시 터미널 프롬프트:

```
매매 모드: live
데몬: 아니오 (1회 실행)
TradingEngine 초기화 중...
실매매를 시작합니다.
계좌: 12345678-01
확인하시겠습니까? (yes/no): yes
1회 실행 시작
```

### 4.4 시스템 상태 확인

```bash
ap trading status
```

출력 예시:

```
Trading System Status
========================================
모드: 모의투자
실매매: 비활성화
일일 한도: 50회 / 50,000,000원
전략 배분: {'topdown_etf': 0.3, 'momentum': 0.4, 'value': 0.3}
```

---

## 5. CLI 명령어 레퍼런스

모든 명령어는 `ap trading` 그룹 아래에 있다.

### 5.1 메인 명령어

| 명령어 | 설명 | 예시 |
|--------|------|------|
| `ap trading data collect` | 전종목 초기 데이터 수집 | `ap trading data collect --market ALL --years 3` |
| `ap trading data update` | 증분 데이터 업데이트 | `ap trading data update` |
| `ap trading data status` | 수집 현황 조회 | `ap trading data status` |
| `ap trading screen` | 팩터 기반 종목 스크리닝 | `ap trading screen --market KOSPI --top 20 --factor momentum` |
| `ap trading run` | 매매 파이프라인 실행 | `ap trading run --mode paper --daemon` |
| `ap trading status` | 시스템 상태 확인 | `ap trading status` |
| `ap trading reconcile` | DB/증권사 잔고 대사 | `ap trading reconcile` |

### 5.2 data 옵션

```bash
ap trading data collect [OPTIONS]
```

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `--market` | `ALL` | 시장 (KOSPI / KOSDAQ / ALL) |
| `--years` | `3` | 수집 기간 (년) |
| `--delay` | `0.5` | pykrx 요청 간 딜레이 (초) |
| `--no-resume` | - | 체크포인트 무시하고 처음부터 수집 |

```bash
ap trading data update [OPTIONS]
```

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `--market` | `ALL` | 시장 (KOSPI / KOSDAQ / ALL) |

```bash
ap trading data status    # 옵션 없음
```

### 5.3 screen 옵션

```bash
ap trading screen [OPTIONS]
```

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `--market` | `KOSPI` | 시장 (KOSPI / KOSDAQ) |
| `--top` | `20` | 상위 N종목 표시 |
| `--factor` | `momentum` | 주요 팩터 (momentum / value / quality / balanced) |

팩터별 가중치 프리셋:

| 프리셋 | momentum | value | quality | flow | volatility |
|--------|----------|-------|---------|------|------------|
| `momentum` | 0.6 | - | - | 0.3 | 0.1 |
| `value` | 0.2 | 0.4 | 0.3 | 0.1 | - |
| `quality` | 0.3 | 0.2 | 0.4 | 0.1 | - |
| `balanced` | 0.25 | 0.25 | 0.2 | 0.15 | 0.15 |

### 5.4 run 옵션

```bash
ap trading run [OPTIONS]
```

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `--mode` | `paper` | 실행 모드 (paper: 모의투자, live: 실매매) |
| `--daemon` | off | 데몬 모드 (스케줄 기반 자동 반복) |

### 5.5 포트폴리오 서브명령어

```bash
ap trading portfolio show                    # 현재 포트폴리오 현황
ap trading portfolio history --days 30       # 성과 이력 (기본 30일)
ap trading portfolio attribution --days 30   # 성과 귀속 분석
```

### 5.6 리스크 서브명령어

```bash
ap trading risk report                       # 리스크 리포트
ap trading risk stress                       # 스트레스 테스트 (5개 시나리오)
ap trading risk limits                       # 현재 리스크 리밋 설정
```

### 5.7 잔고 대사

```bash
ap trading reconcile                         # DB와 증권사 잔고 비교
```

DB와 증권사 실제 잔고를 대조하여 불일치 항목을 표시한다. 자동 수정은 하지 않으며 수동 확인을 요청한다.

---

## 6. 전략 가이드

### 6.1 기본 제공 전략 4종

#### TopDownETFStrategy

Market Pulse Score에 따라 ETF 포지션을 조절하는 매크로 전략.

| 항목 | 내용 |
|------|------|
| `strategy_id` | `topdown_etf` |
| 리밸런싱 | Signal-driven (시그널 레벨 변경 시) |
| 대상 | ETF (KODEX 200, 레버리지, 인버스, 단기채권) |

**Score -> ETF 매핑:**

| 시장 판단 | ETF 배분 |
|-----------|----------|
| 강한 매수 | KODEX 레버리지 70% + KODEX 200 30% |
| 매수 우위 | KODEX 200 80% + KODEX 단기채권 20% |
| 중립 | KODEX 단기채권 50% + KODEX 200 30% + 현금 20% |
| 매도 우위 | KODEX 인버스 50% + KODEX 단기채권 30% + 현금 20% |
| 강한 매도 | KODEX 200선물인버스2X 40% + KODEX 단기채권 30% + 현금 30% |

#### MomentumStrategy

상위 모멘텀 종목 롱 전략.

| 항목 | 내용 |
|------|------|
| `strategy_id` | `momentum` |
| 리밸런싱 | 주간 (매주 월요일) |
| 팩터 가중치 | momentum 0.6, flow 0.3, volatility 0.1 |
| 종목 수 | 상위 20종목 (`MOMENTUM_TOP_N`) |

Market Pulse가 매도 우위 이하이면 시그널 강도를 50%로 축소한다.

#### ValueStrategy

저평가 + 퀄리티 복합 전략.

| 항목 | 내용 |
|------|------|
| `strategy_id` | `value` |
| 리밸런싱 | 주간 (매주 월요일) |
| 팩터 가중치 | value 0.4, quality 0.3, momentum 0.2, flow 0.1 |
| 종목 수 | 상위 15종목 (`VALUE_TOP_N`) |

#### QualityMomentumStrategy

퀄리티와 모멘텀을 결합한 복합 전략.

| 항목 | 내용 |
|------|------|
| `strategy_id` | `quality_momentum` |
| 리밸런싱 | 주간 (매주 월요일) |
| 팩터 가중치 | quality 0.35, momentum 0.35, flow 0.2, volatility 0.1 |
| 종목 수 | 상위 15종목 |

### 6.2 전략 파라미터 튜닝

`.env`에서 전략 동작을 조정할 수 있다.

```bash
# 멀티전략 자금 배분 (합계 = 1.0)
STRATEGY_ALLOCATIONS={"topdown_etf":0.3,"momentum":0.4,"value":0.3}

# 개별 전략 상위 종목 수
MOMENTUM_TOP_N=20
VALUE_TOP_N=15
```

**배분 비율 예시 (시장 환경별):**

| 시장 환경 | topdown_etf | momentum | value | 설명 |
|-----------|-------------|----------|-------|------|
| 상승장 | 0.2 | 0.5 | 0.3 | 개별 종목 비중 확대 |
| 횡보장 | 0.3 | 0.3 | 0.4 | 밸류 전략 비중 확대 |
| 하락장 | 0.5 | 0.2 | 0.3 | ETF 방어 비중 확대 |

### 6.3 AI 종합 판단

StrategyAISynthesizer는 다음 입력을 LLM에 전달하여 최종 판단을 산출한다:

1. **시장 상황** -- Market Pulse Score, 11개 지표 상세
2. **팩터 분석** -- 스크리닝 상위 종목, 팩터별 특징
3. **전략별 시그널** -- 각 전략의 매수/매도 후보
4. **정성 분석** -- 블로그/뉴스 인사이트 (Content Intelligence)
5. **피드백 컨텍스트** -- 과거 적중률, 편향, 놓친 변수
6. **현재 포트폴리오** -- 보유 종목, 손익 현황

**출력 (StrategySynthesis):**

| 필드 | 설명 |
|------|------|
| `market_view` | 시장 전체 판단 요약 |
| `conviction_level` | 확신도 (0.0 ~ 1.0) |
| `allocation_adjustment` | 전략 배분 조정 제안 |
| `stock_opinions` | 종목별 AI 의견 (강력매수/매수/유지/축소/매도) |
| `risk_warnings` | 리스크 경고 목록 |
| `reasoning` | 판단 근거 (감사 추적에 기록) |

**안전 장치**: LLM 호출 실패 시 규칙 기반 `_fallback()`으로 전환한다. AI 판단이 리스크 하드 리밋을 오버라이드할 수 없다.

### 6.4 멀티전략 배분 (Allocator)

StrategyAllocator는 Market Pulse Score와 AI 확신도에 따라 전략 간 배분 비율을 동적으로 조정한다:

- **강한 매수** -> 종목 전략(momentum, value) 비중 확대, ETF 비중 축소
- **강한 매도** -> ETF 인버스 비중 확대, 종목 전략 비중 축소
- **중립** -> 밸류 전략 비중 확대
- AI `conviction_level < 0.3` -> 현금 비중 확대

---

## 7. 팩터 레퍼런스

20개 팩터가 6개 카테고리에 걸쳐 구현되어 있다. 각 팩터는 원시값을 반환하며, MultiFactorRanker에서 유니버스 내 percentile(0~100)로 정규화된다.

### 7.1 모멘텀 팩터 (5종)

| 팩터 | 메서드 | 설명 |
|------|--------|------|
| 1개월 수익률 | `momentum_1m()` | 최근 20영업일 수익률 (%) |
| 3개월 수익률 | `momentum_3m()` | 최근 60영업일 수익률 (%) |
| 6개월 수익률 | `momentum_6m()` | 최근 120영업일 수익률 (%) |
| 12개월 수익률 | `momentum_12m()` | 12개월 수익률, 최근 1개월 제외 (12-1 모멘텀) |
| 52주 신고가 근접도 | `high_52w_proximity()` | 현재가 / 52주 고가 x 100 (%) |

### 7.2 밸류 팩터 (4종)

| 팩터 | 메서드 | 설명 |
|------|--------|------|
| E/P (PER 역수) | `value_per()` | (1/PER) x 100. PER이 낮을수록 높은 값 |
| B/P (PBR 역수) | `value_pbr()` | (1/PBR) x 100. PBR이 낮을수록 높은 값 |
| S/P (PSR 역수) | `value_psr()` | (1/PSR) x 100. 매출 대비 저평가 측정 |
| 배당수익률 | `dividend_yield()` | 배당수익률 (%) |

### 7.3 퀄리티 팩터 (3종)

| 팩터 | 메서드 | 설명 |
|------|--------|------|
| ROE | `quality_roe()` | 자기자본이익률 (%). 높을수록 우수 |
| 영업이익 성장률 | `quality_profit_growth()` | YoY 영업이익 성장률 (%) |
| 부채비율 역수 | `quality_debt_ratio()` | (1/부채비율) x 100. 낮은 부채 = 높은 점수 |

### 7.4 수급 팩터 (3종)

| 팩터 | 메서드 | 설명 |
|------|--------|------|
| 외국인 순매수 | `flow_foreign()` | N일간 외국인 순매수 누적 (원) |
| 기관 순매수 | `flow_institutional()` | N일간 기관 순매수 누적 (원) |
| 수급 추세 | `flow_trend()` | 5일 이평 vs 20일 이평 교차 (양수 = 개선) |

### 7.5 역발상 팩터 (2종)

| 팩터 | 메서드 | 설명 |
|------|--------|------|
| 공매도 감소율 | `short_decrease()` | 양수 = 공매도 잔고 감소 (긍정적) |
| 신용잔고 변화 | `credit_change()` | 양수 = 신용 증가 (과열 신호) |

### 7.6 변동성 팩터 (3종)

| 팩터 | 메서드 | 설명 |
|------|--------|------|
| 변동성 | `volatility()` | 일간 수익률 표준편차 (연환산, %) |
| 베타 | `beta()` | 시장(KOSPI) 대비 민감도 |
| 하방 변동성 | `downside_vol()` | 음수 수익률만의 표준편차 (연환산, %) |

### 7.7 데이터 결측 처리

팩터 데이터가 없는 종목은 해당 팩터를 제외하고 나머지 팩터로 재정규화하여 랭킹에 포함한다.

---

## 8. 리스크 관리

### 8.1 하드 리밋

절대 위반 불가 제약 조건이다. AI, 전략, 사용자 모두 오버라이드할 수 없다.

#### 집중도 제한

| 리밋 | 기본값 | 설명 |
|------|--------|------|
| `max_position_weight` | 10% | 종목당 최대 비중 |
| `max_sector_weight` | 30% | 섹터당 최대 비중 |
| `max_etf_leverage` | 20% | 레버리지/인버스 ETF 최대 비중 |
| `max_total_exposure` | 100% | 총 노출도 상한 (레버리지 없음) |

#### 손실 제한

| 리밋 | 기본값 | 설명 |
|------|--------|------|
| `max_drawdown_soft` | -10% | 신규 매수 중단 (경고) |
| `max_drawdown_hard` | -15% | 전 포지션 50% 강제 축소 |
| `max_daily_loss` | -3% | 당일 매매 중단 |

#### 유동성 제한

| 리밋 | 기본값 | 설명 |
|------|--------|------|
| `min_cash_ratio` | 5% | 최소 현금 유지 비율 |
| `max_single_order_pct` | 5% | 단일 주문 총자산의 5% 이하 |
| `max_order_to_volume` | 10% | 주문량 <= 일평균 거래량의 10% |

#### VaR 제한

| 리밋 | 기본값 | 설명 |
|------|--------|------|
| `max_portfolio_var_95` | 3% | 95% VaR 상한 |

### 8.2 주문 리스크 검증 흐름

모든 주문은 실행 전에 다음 순서로 검증된다:

```
주문 발생
  |
  +-> 1. 일간 손실 한도 (-3%) 초과? --------> REJECT
  +-> 2. 드로다운 WARN 상태 + 매수? --------> REJECT
  +-> 3. 종목 비중 한도 (10%) 초과? ---------> REDUCE_SIZE
  +-> 4. 섹터 집중도 (30%) 초과? ------------> REDUCE_SIZE
  +-> 5. 레버리지 ETF 한도 (20%) 초과? ------> REDUCE_SIZE
  +-> 6. 최소 현금 비율 (5%) 위반? ----------> REJECT
  +-> 7. 주문량/거래량 비율 (10%) 초과? -----> REDUCE_SIZE
  +-> 8. VaR 한도 (3%) 초과? ----------------> REDUCE_SIZE
  |
  v
APPROVE (수량 조정 포함 가능)
```

RiskDecision의 action:

| 액션 | 의미 |
|------|------|
| `APPROVE` | 원래 수량으로 실행 |
| `REDUCE_SIZE` | 조정된 수량(`adjusted_quantity`)으로 실행 |
| `REJECT` | 주문 거부 (사유 기록) |

### 8.3 드로다운 자동 디레버리징

DrawdownManager가 포트폴리오 가치를 고점(peak) 대비 추적한다.

| 상태 | 조건 | 조치 |
|------|------|------|
| `NORMAL` | 낙폭 < 10% | 정상 운영 |
| `WARN` | 10% <= 낙폭 < 15% | 신규 매수 중단 (기존 보유 유지) |
| `DELEVERAGE` | 낙폭 >= 15% | 전 포지션 50% 강제 축소 (손실 큰 종목부터) |

디레버리징 실행 시 감사 로그에 기록되고 텔레그램으로 긴급 알림이 발송된다.

### 8.4 VaR/CVaR

VaRCalculator가 제공하는 3가지 방법:

| 방법 | 설명 |
|------|------|
| Historical VaR | 과거 수익률 분포의 하위 5% 분위수 |
| Parametric VaR | 분산-공분산 기반 (정규분포 가정) |
| CVaR (Expected Shortfall) | VaR를 초과하는 손실의 평균 (꼬리 리스크 측정) |

### 8.5 스트레스 테스트

5개 사전 정의 시나리오로 포트폴리오 충격을 시뮬레이션한다.

| 시나리오 | KOSPI | KOSDAQ | 설명 |
|----------|-------|--------|------|
| `2020_covid` | -35% | -40% | COVID-19 급락 (2020.03) |
| `2022_rate_hike` | -25% | -35% | 금리 인상기 하락 (2022) |
| `flash_crash` | -10% | -15% | 일간 급락 (Flash Crash) |
| `won_crisis` | -20% | -25% | 원화 위기 + 외국인 이탈 |
| `sector_collapse` | -10% | -15% | 특정 섹터 -50% 붕괴 |

사용자 정의 시나리오를 추가할 수 있다:

```python
from alphapulse.trading.risk.stress_test import StressTest

st = StressTest()
st.add_custom_scenario("china_shock", {
    "kospi": -0.15,
    "kosdaq": -0.20,
    "etf": -0.15,
    "desc": "중국발 충격",
})
result = st.run(portfolio, "china_shock")
```

---

## 9. 백테스트 가이드

### 9.1 핵심 설계 원칙

- **동일 코드 경로**: 전략, 포트폴리오, 리스크 코드가 실매매와 동일하며 SimBroker만 사용.
- **Look-ahead bias 방지**: HistoricalDataFeed가 미래 데이터 접근을 차단. assert로 검증.
- **현실적 비용 모델**: 수수료 0.015%, 매도세 0.18%, 슬리피지(거래량 기반) 적용.

### 9.2 거래 비용 모델

CostModel이 백테스트/모의투자/실매매 모두에서 동일하게 적용된다.

| 비용 항목 | 기본값 | 비고 |
|-----------|--------|------|
| 수수료 (매수+매도) | 0.015% | 한투 온라인 기준 |
| 매도세 (주식) | 0.18% | 2025년 기준 |
| 매도세 (ETF) | 0% | 면제 |
| 슬리피지 | 거래량 연동 | 주문량/거래대금 비율로 추정 |

슬리피지 모델:

| 주문/거래대금 비율 | 슬리피지 |
|--------------------|----------|
| < 1% | 0% |
| 1% ~ 5% | 0.1% |
| >= 5% | 0.3% |
| 거래량 없음 | 0.3% |

### 9.3 성과 지표 (22개)

BacktestMetrics가 계산하는 전체 지표 목록:

#### 수익률 지표

| 지표 | 필드명 | 설명 |
|------|--------|------|
| 총 수익률 | `total_return` | 전체 기간 수익률 (%) |
| CAGR | `cagr` | 연환산 수익률 (%) |
| 월별 수익률 | `monthly_returns` | 월별 복리 수익률 리스트 |

#### 리스크 지표

| 지표 | 필드명 | 설명 |
|------|--------|------|
| 변동성 | `volatility` | 연 변동성 (%) |
| 최대 낙폭 (MDD) | `max_drawdown` | 고점 대비 최대 하락률 (%) |
| MDD 지속 기간 | `max_drawdown_duration` | MDD 지속 기간 (영업일) |
| 하방 변동성 | `downside_deviation` | 음수 수익률만의 변동성 |

#### 리스크 조정 수익

| 지표 | 필드명 | 설명 |
|------|--------|------|
| Sharpe Ratio | `sharpe_ratio` | (수익률 - 무위험) / 변동성 |
| Sortino Ratio | `sortino_ratio` | (수익률 - 무위험) / 하방 변동성 |
| Calmar Ratio | `calmar_ratio` | CAGR / |MDD| |

#### 거래 분석

| 지표 | 필드명 | 설명 |
|------|--------|------|
| 총 거래 횟수 | `total_trades` | 라운드트립 기준 |
| 승률 | `win_rate` | 수익 거래 비율 (%) |
| Profit Factor | `profit_factor` | 총이익 / 총손실 |
| 평균 수익 | `avg_win` | 수익 거래의 평균 금액 |
| 평균 손실 | `avg_loss` | 손실 거래의 평균 금액 |
| 회전율 | `turnover` | 연간 거래대금 / 초기 자본 |

#### 벤치마크 비교

| 지표 | 필드명 | 설명 |
|------|--------|------|
| 벤치마크 수익률 | `benchmark_return` | KOSPI 수익률 (%) |
| 초과 수익 | `excess_return` | 전략 - 벤치마크 (%) |
| 베타 | `beta` | 시장 민감도 |
| 젠센 알파 | `alpha` | 체계적 위험 보상 초과 수익 |
| Information Ratio | `information_ratio` | 초과 수익 / 추적 오차 |
| Tracking Error | `tracking_error` | 벤치마크 대비 수익률 괴리 (%) |

### 9.4 리포트 해석 가이드

주요 지표 해석 기준:

| 지표 | 양호 | 보통 | 주의 |
|------|------|------|------|
| Sharpe Ratio | > 1.0 | 0.5 ~ 1.0 | < 0.5 |
| MDD | > -15% | -15% ~ -25% | < -25% |
| Win Rate | > 55% | 45% ~ 55% | < 45% |
| Profit Factor | > 1.5 | 1.0 ~ 1.5 | < 1.0 |
| Information Ratio | > 0.5 | 0.0 ~ 0.5 | < 0.0 |

---

## 10. 안전장치

### 10.1 실매매 이중 잠금 (Two-Lock System)

실매매 진입에는 두 단계 확인이 필요하다:

```
Lock 1: .env 설정
  LIVE_TRADING_ENABLED=true     <-- false(기본값)이면 실매매 자체가 불가
  KIS_IS_PAPER=false            <-- true이면 모의투자 서버만 연결

Lock 2: 터미널 확인
  "실매매를 시작합니다."
  "계좌: 12345678-01"
  "확인하시겠습니까? (yes/no):"  <-- 'yes' 입력 필수
```

두 잠금 모두 통과해야만 실전 서버에 주문이 전송된다.

### 10.2 일일 주문 한도

| 제한 | 기본값 | 환경 변수 |
|------|--------|-----------|
| 주문 횟수 | 50회/일 | `MAX_DAILY_ORDERS` |
| 주문 금액 | 5천만원/일 | `MAX_DAILY_AMOUNT` |

한도 초과 시 RuntimeError가 발생하며 이후 주문이 차단된다. 새 거래일이 시작되면 카운터가 초기화된다.

### 10.3 장애 복구 (RecoveryManager)

시스템 장애 후 재시작 시:

1. 마지막 포트폴리오 스냅샷을 DB에서 로드한다.
2. 증권사 API로 실제 잔고를 조회한다.
3. DB 포지션과 증권사 잔고를 대조한다.
4. 불일치 항목이 있으면 경고를 표시한다.
5. **자동 수정은 하지 않는다** (안전 우선). 수동 확인 후 조치한다.

```bash
# 수동 잔고 대사
ap trading reconcile
```

출력 예시:

```
DB/증권사 잔고 대사 실행
대사 진행 중...
불일치 1건 발견:
  - 005930 삼성전자: DB 100주 vs 증권사 95주
```

### 10.4 감사 추적 (Audit Log)

모든 의사결정이 `trading.db`의 `audit_log` 테이블에 기록된다:

| 이벤트 유형 | 기록 내용 |
|-------------|-----------|
| `signal` | 시그널 생성 (전략 ID, 종목, 점수, 팩터) |
| `ai_synthesis` | AI 종합 판단 (입력 요약, 출력, 확신도) |
| `risk_decision` | 리스크 결정 (APPROVE/REDUCE_SIZE/REJECT + 사유) |
| `order` | 주문 제출/체결 상세 |
| `drawdown` | 드로다운 이벤트 (WARN/DELEVERAGE) |
| `error` | 오류 발생 (컴포넌트, 예외 상세, 컨텍스트) |

---

## 11. 개발자 가이드

### 11.1 새 전략 추가 방법

1. `alphapulse/trading/strategy/` 아래에 새 파일을 생성한다.
2. `BaseStrategy`를 상속하고 `generate_signals()`를 구현한다.
3. StrategyRegistry에 등록한다.

```python
# alphapulse/trading/strategy/my_strategy.py

from alphapulse.trading.core.enums import RebalanceFreq
from alphapulse.trading.core.models import Signal, Stock
from alphapulse.trading.strategy.base import BaseStrategy


class MyStrategy(BaseStrategy):
    """커스텀 전략 예시."""

    strategy_id = "my_strategy"
    rebalance_freq = RebalanceFreq.WEEKLY

    def __init__(self, config: dict) -> None:
        super().__init__(config)
        self.top_n = config.get("top_n", 10)

    def generate_signals(
        self,
        universe: list[Stock],
        market_context: dict,
    ) -> list[Signal]:
        """종목별 매매 시그널을 생성한다."""
        signals = []
        # 전략 로직 구현
        # ...
        return sorted(signals, key=lambda s: s.score, reverse=True)[:self.top_n]
```

BaseStrategy가 제공하는 `should_rebalance()` 메서드는 `RebalanceFreq`에 따라 자동 동작한다:

| RebalanceFreq | 동작 |
|---------------|------|
| `DAILY` | 매 거래일 리밸런싱 |
| `WEEKLY` | 월요일에만 리밸런싱 |
| `SIGNAL_DRIVEN` | 서브클래스에서 오버라이드 필요 |

### 11.2 새 팩터 추가 방법

1. `alphapulse/trading/screening/factors.py`의 `FactorCalculator`에 메서드를 추가한다.
2. 원시값을 반환한다 (percentile 정규화는 Ranker가 수행).
3. 테스트를 작성한다.

```python
# factors.py에 추가

def my_custom_factor(self, code: str) -> float | None:
    """커스텀 팩터 설명.

    Args:
        code: 종목코드.

    Returns:
        팩터 원시값. 데이터 부족 시 None.
    """
    rows = self.store.get_ohlcv(code, "00000000", "99999999")
    if len(rows) < 10:
        return None
    # 계산 로직
    return result
```

### 11.3 테스트 실행

```bash
# Trading System 전체 테스트 (464개)
pytest tests/trading/ -v

# 서브시스템별 테스트
pytest tests/trading/core/ -v          # 데이터 모델, 캘린더, 비용 모델
pytest tests/trading/data/ -v          # 데이터 수집기
pytest tests/trading/screening/ -v     # 팩터 계산, 랭킹
pytest tests/trading/strategy/ -v      # 전략 시그널 생성
pytest tests/trading/portfolio/ -v     # 포트폴리오 최적화
pytest tests/trading/risk/ -v          # 리스크 리밋
pytest tests/trading/backtest/ -v      # 백테스트 엔진
pytest tests/trading/broker/ -v        # 브로커 (mock)
pytest tests/trading/orchestrator/ -v  # 통합 오케스트레이터

# 커버리지 리포트
pytest tests/trading/ --cov=alphapulse.trading
```

### 11.4 테스트 원칙

- **TDD 원칙 유지**: test first -> red -> implement -> green -> commit
- **외부 API 격리**: pykrx, 한투 API -> mock/patch
- **LLM 격리**: `@patch("...._call_llm")` (기존 패턴 동일)
- **경계값 테스트**: 리스크 리밋의 정확한 경계에서 동작 검증

### 11.5 데이터베이스 스키마

Trading System은 3개의 SQLite DB를 사용한다:

| DB | 용도 | 주요 테이블 |
|----|------|-------------|
| `trading.db` | 종목 데이터 | `stocks`, `ohlcv`, `fundamentals`, `stock_investor_flow`, `short_interest`, `etf_info`, `audit_log` |
| `portfolio.db` | 포트폴리오 | `snapshots`, `orders`, `trades`, `attribution` |
| `backtest.db` | 백테스트 | `runs` (일별 데이터는 portfolio.db 공유, `run_id`로 구분) |

### 11.6 Protocol 기반 확장

모든 서브시스템은 Protocol 기반 인터페이스로 연결된다. 구현체를 교체하여 확장할 수 있다.

```python
# 예시: 다른 증권사 브로커 구현

from alphapulse.trading.core.interfaces import Broker

class MyBroker:
    """Broker Protocol 구현 -- 커스텀 증권사."""

    def submit_order(self, order):
        # 구현
        ...

    def cancel_order(self, order_id):
        # 구현
        ...

    def get_balance(self):
        # 구현
        ...

    def get_positions(self):
        # 구현
        ...

    def get_order_status(self, order_id):
        # 구현
        ...
```

Protocol 인터페이스 목록:

| Protocol | 역할 | 구현체 |
|----------|------|--------|
| `DataProvider` | 종목 데이터 소스 | TradingStore, HistoricalDataFeed |
| `Strategy` | 매매 전략 | TopDownETF, Momentum, Value, QualityMomentum |
| `Broker` | 주문 집행 | SimBroker, PaperBroker, KISBroker |
| `RiskChecker` | 리스크 검증 | RiskManager |

---

## 부록: 환경 변수 전체 목록 (Trading 관련)

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `KIS_APP_KEY` | (없음) | 한투 앱 키 |
| `KIS_APP_SECRET` | (없음) | 한투 앱 시크릿 |
| `KIS_ACCOUNT_NO` | (없음) | 계좌번호 |
| `KIS_IS_PAPER` | `true` | 모의투자 여부 |
| `LIVE_TRADING_ENABLED` | `false` | 실매매 스위치 |
| `MAX_DAILY_ORDERS` | `50` | 일일 주문 횟수 한도 |
| `MAX_DAILY_AMOUNT` | `50000000` | 일일 주문 금액 한도 (원) |
| `STRATEGY_ALLOCATIONS` | `{"topdown_etf":0.3,"momentum":0.4,"value":0.3}` | 전략 배분 비율 (JSON) |
| `MOMENTUM_TOP_N` | `20` | 모멘텀 전략 상위 종목 수 |
| `VALUE_TOP_N` | `15` | 밸류 전략 상위 종목 수 |
