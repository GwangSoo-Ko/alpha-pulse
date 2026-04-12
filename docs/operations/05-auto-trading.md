# 자동 매매 시스템 운영 가이드

AlphaPulse 자동 매매 시스템의 운영 참조 문서이다. 모의투자(Paper)와 실전매매(Live) 모드 모두를 다룬다.

---

## 목차

1. [개요](#1-개요)
2. [5단계 파이프라인](#2-5단계-파이프라인)
3. [DI 팩토리](#3-di-팩토리)
4. [한국투자증권 API](#4-한국투자증권-api)
5. [PaperBroker vs KISBroker](#5-paperbroker-vs-kisbroker)
6. [안전장치 (Safeguard)](#6-안전장치-safeguard)
7. [스케줄러](#7-스케줄러)
8. [알림 시스템](#8-알림-시스템)
9. [잔고 대사](#9-잔고-대사)
10. [감사 추적](#10-감사-추적)
11. [CLI 명령어](#11-cli-명령어)
12. [환경 설정](#12-환경-설정)

---

## 1. 개요

자동 매매 시스템은 **5단계 파이프라인**을 통해 데이터 수집부터 주문 실행, 사후 관리까지 일일 매매 사이클을 자동화한다.

### 아키텍처

```
┌─────────────────────────────────────────────────────────────┐
│                     TradingEngine                           │
│  (orchestrator/engine.py — run_daily 5-phase pipeline)      │
├──────────┬──────────┬──────────┬──────────┬─────────────────┤
│ Phase 1  │ Phase 2  │ Phase 3  │ Phase 4  │    Phase 5      │
│ 데이터   │ 분석     │ 포트폴리오│ 실행     │    사후 관리    │
│ 수집     │          │          │          │                 │
└──────────┴──────────┴──────────┴──────────┴─────────────────┘
       │          │          │          │            │
       ▼          ▼          ▼          ▼            ▼
  DataProvider  Strategy   Portfolio   Broker    PortfolioStore
  Universe     AI Synth   RiskMgr    KIS API    DrawdownMgr
  Screener     Allocator  Sizer      Safeguard  AuditLogger
```

### 실행 모드 (`TradingMode`)

| 모드 | 값 | 설명 | 브로커 |
|------|-----|------|--------|
| **PAPER** | `"paper"` | 모의투자. 한투 모의투자 서버 사용. | `PaperBroker` |
| **LIVE** | `"live"` | 실전매매. 한투 실전 서버 사용. 안전장치 필수. | `KISBroker` |
| **BACKTEST** | `"backtest"` | 과거 데이터 기반 시뮬레이션. | `PaperBroker` |

### 동기/비동기 정책

- **Sync**: 데이터 수집, 스크리닝, 전략, 포트폴리오, 리스크, 백테스트, 브로커 (requests 라이브러리).
- **Async**: AI 종합 판단(`StrategyAISynthesizer.synthesize`), 알림(`TradingAlert`), 오케스트레이터(`TradingEngine.run_daily`).
- `asyncio.run()`은 CLI entry에서만 호출한다. 내부에서 중첩 호출은 금지이다.

---

## 2. 5단계 파이프라인

`TradingEngine.run_daily(date)` 메서드가 전체 파이프라인을 실행한다. `date` 인자가 `None`이면 오늘 날짜(`datetime.now().strftime("%Y%m%d")`)를 사용한다.

### Phase 1: 데이터 수집

```python
# DataProvider.refresh()를 호출한다.
# async이면 await, sync이면 직접 호출.
refresh_fn = getattr(self.data_provider, "refresh", None)
```

- `TradingDataProvider`가 OHLCV, 재무, 수급, 공매도 데이터를 갱신한다.
- 데이터 수집 실패 시 `audit.log_error("data_provider", e, {"date": date})`로 기록하고 다음 단계로 진행한다.
- 실패가 전체 파이프라인을 중단하지 않는다.

### Phase 2: 분석

세 가지 하위 단계로 구성된다.

**2-1. 투자 유니버스 필터링**

```python
filtered_universe = self._get_filtered_universe()
```

`Universe`에 `get_filtered()` 또는 `get_all()` 메서드가 있으면 호출하여 투자 대상 종목 리스트를 반환한다.

**2-2. 전략별 시그널 생성**

각 전략(`MomentumStrategy`, `ValueStrategy`, `TopDownETFStrategy`)에 대해:

1. `PortfolioStore`에서 마지막 리밸런싱 날짜를 조회한다.
2. `strategy.should_rebalance(last_rebalance, date, market_context)`로 리밸런싱 여부를 판단한다.
3. 리밸런싱 대상이면 `strategy.generate_signals(filtered_universe, market_context)`를 호출한다.
4. 리밸런싱 날짜를 갱신한다.

```python
strategy_signals: dict[str, list] = {}
for strategy in self.strategies:
    last_rebalance = self._get_last_rebalance(strategy.strategy_id)
    if strategy.should_rebalance(last_rebalance, date, market_context):
        signals = strategy.generate_signals(filtered_universe, market_context)
        strategy_signals[strategy.strategy_id] = signals
```

**2-3. AI 종합 판단**

```python
ai_synthesis = await self._run_ai_synthesis(market_context, strategy_signals, date)
```

`StrategyAISynthesizer.synthesize()`를 호출하여 `StrategySynthesis` 객체를 반환한다. 실패 시 `None`을 반환하고 fallback으로 진행한다.

반환값에는 `conviction_level`(확신도, 0.0~1.0)과 `risk_warnings`(리스크 경고 목록)이 포함된다.

### Phase 3: 포트폴리오

다섯 가지 하위 단계로 구성된다.

**3-1. 배분 조정**

```python
allocations = self.allocator.adjust_by_market_regime(
    market_context.get("pulse_score", 0),
    ai_synthesis,
)
```

`StrategyAllocator`가 Market Pulse 점수와 AI 판단을 기반으로 전략별 배분 비중을 동적 조정한다.

**3-2. 목표 포트폴리오 산출**

```python
target = self.portfolio_manager.update_target(
    strategy_signals, allocations, current_snapshot, prices,
)
```

**3-3. 주문 생성**

```python
orders = self.portfolio_manager.generate_orders(
    target, current_snapshot, prices, primary_strategy_id
)
```

현재 스냅샷과 목표 포트폴리오의 차이를 계산하여 매수/매도 주문 목록을 생성한다.

**3-4. 리스크 체크**

모든 주문에 대해 `RiskManager.check_order()`를 실행한다.

```python
for order in orders:
    decision = self.risk_manager.check_order(order, current_snapshot)
    self.audit.log_risk_decision(order, decision)

    if decision.action == RiskAction.APPROVE:
        approved_orders.append(order)
    elif decision.action == RiskAction.REDUCE_SIZE:
        order.quantity = decision.adjusted_quantity
        approved_orders.append(order)
    else:
        # RiskAction.REJECT — 주문 거부
        logger.info("주문 거부: %s %s", order.stock.code, order.side)
```

`RiskAction` 결과:

| 결과 | 설명 |
|------|------|
| `APPROVE` | 승인. 원래 수량 유지. |
| `REDUCE_SIZE` | 수량 축소. `decision.adjusted_quantity`로 변경. |
| `REJECT` | 거부. 주문 제외. |

**3-5. 장전 알림**

```python
await self.alert.pre_market(market_context, approved_orders, ai_synthesis)
```

### Phase 4: 실행

승인된 주문을 브로커에 제출한다.

```python
for order in approved_orders:
    result = self.broker.submit_order(order)
    self.audit.log_order(order, result)
    await self.alert.execution(order, result)
```

- 주문 성공/실패 모두 감사 로그에 기록된다.
- 체결 알림이 각 주문마다 전송된다.
- 알림 실패가 주문 실행을 중단하지 않는다.

### Phase 5: 사후 관리

세 가지 하위 단계로 구성된다.

**5-1. 스냅샷 저장**

```python
snapshot = self._take_snapshot(date)
```

브로커에서 `get_positions()`와 `get_balance()`를 호출하여 현재 포트폴리오 스냅샷을 생성한다. 이전 스냅샷 대비 일간 수익률과 누적 수익률을 계산한다. `PortfolioStore`에 저장한다.

**5-2. 드로다운 체크**

```python
dd_action = self.risk_manager.drawdown_mgr.check(snapshot)
```

| 드로다운 상태 | 설명 |
|--------------|------|
| `NORMAL` | 정상 범위. 조치 없음. |
| `WARN` | Soft 리밋 도달 (-10% 기본값). 경고. |
| `DELEVERAGE` | Hard 리밋 도달 (-15% 기본값). 포지션 50% 강제 축소. |

Hard 리밋 도달 시:
1. `generate_deleverage_orders(snapshot)`로 포지션 축소 주문을 생성한다.
2. 축소 주문을 브로커에 제출한다.
3. 긴급 리스크 알림을 전송한다: `"드로다운 하드 리밋 도달. 포지션 50% 축소 실행."`

**5-3. 일일 리포트**

```python
risk_report = self.risk_manager.daily_report(snapshot)
await self.alert.post_market(snapshot, risk_report)
```

### 반환값

`run_daily()`는 다음 딕셔너리를 반환한다:

```python
{
    "date": "20260411",
    "mode": TradingMode.PAPER,
    "signals": 3,             # 시그널을 생성한 전략 수
    "orders_submitted": 5,    # 실제 제출된 주문 수
    "drawdown_action": "NORMAL",
}
```

---

## 3. DI 팩토리

`build_trading_engine(mode, cfg)` 함수가 모든 컴포넌트를 조립하여 완성된 `TradingEngine`을 반환한다.

### 조립 순서

```
1. 데이터 레이어    → TradingStore, Universe, TradingDataProvider
2. 브로커           → KISClient → PaperBroker 또는 KISBroker
3. 전략             → MultiFactorRanker, MomentumStrategy, ValueStrategy, TopDownETFStrategy
4. 포트폴리오+리스크 → CostModel, PortfolioManager, RiskLimits, RiskManager
5. 배분+AI          → StrategyAllocator, StrategyAISynthesizer
6. 인프라            → TelegramNotifier, TradingAlert, AuditLogger, PortfolioStore
7. 안전장치 (LIVE)   → TradingSafeguard
```

### 컴포넌트 상세

**1. 데이터 레이어**

| 컴포넌트 | 클래스 | 설정 |
|----------|--------|------|
| store | `TradingStore` | `db_path=cfg.TRADING_DB_PATH` |
| universe | `Universe` | `store=store` |
| data_provider | `TradingDataProvider` | `db_path=cfg.TRADING_DB_PATH` |

**2. 브로커**

`_build_broker(mode, cfg)` 함수가 모드에 따라 브로커를 선택한다:

- `KIS_APP_KEY`가 없으면 `RuntimeError`를 발생시킨다.
- `KISClient`를 `is_paper=cfg.KIS_IS_PAPER`로 생성한다.
- LIVE 모드: `KISBroker(client, audit)` 반환.
- 그 외: `PaperBroker(client, audit)` 반환.

**3. 전략**

| 전략 | 클래스 | 설정 |
|------|--------|------|
| momentum | `MomentumStrategy` | `top_n=20` |
| value | `ValueStrategy` | `top_n=20` |
| topdown_etf | `TopDownETFStrategy` | `{}` |

`MultiFactorRanker`의 기본 팩터 가중치:

| 팩터 | 가중치 |
|------|--------|
| `momentum_3m` | 0.10 |
| `momentum_6m` | 0.15 |
| `volume_trend` | 0.05 |
| `pbr` | 0.10 |
| `per` | 0.10 |
| `roe` | 0.10 |
| `debt_ratio` | 0.05 |
| `foreign_net` | 0.15 |
| `institutional_net` | 0.10 |
| `revenue_growth_yoy` | 0.05 |
| `operating_profit_growth_yoy` | 0.05 |

**4. 포트폴리오 + 리스크**

```python
PortfolioManager(
    position_sizer=PositionSizer(),
    optimizer=PortfolioOptimizer(),
    rebalancer=Rebalancer(),
    cost_model=CostModel(
        commission_rate=cfg.BACKTEST_COMMISSION,
        tax_rate_stock=cfg.BACKTEST_TAX,
    ),
)

RiskManager(
    limits=RiskLimits(
        max_position_weight=cfg.MAX_POSITION_WEIGHT,
        max_drawdown_soft=cfg.MAX_DRAWDOWN_SOFT,
        max_drawdown_hard=cfg.MAX_DRAWDOWN_HARD,
    ),
    var_calc=VaRCalculator(),
    drawdown_mgr=DrawdownManager(limits=limits),
)
```

**5. 배분 + AI**

```python
StrategyAllocator(base_allocations=cfg.STRATEGY_ALLOCATIONS)
# 기본값: {"topdown_etf": 0.3, "momentum": 0.4, "value": 0.3}

StrategyAISynthesizer()
```

**6. 인프라**

| 컴포넌트 | 클래스 | 설정 |
|----------|--------|------|
| notifier | `TelegramNotifier` | `bot_token=cfg.TELEGRAM_BOT_TOKEN`, `chat_id=cfg.TELEGRAM_CHAT_ID` |
| alert | `TradingAlert` | `notifier=notifier` |
| audit | `AuditLogger` | `db_path=cfg.DATA_DIR / "audit.db"` |
| portfolio_store | `PortfolioStore` | `db_path=cfg.PORTFOLIO_DB_PATH` |

**7. 안전장치 (LIVE 모드 한정)**

```python
TradingSafeguard(config={
    "LIVE_TRADING_ENABLED": cfg.LIVE_TRADING_ENABLED,
    "MAX_DAILY_ORDERS": cfg.MAX_DAILY_ORDERS,
    "MAX_DAILY_AMOUNT": cfg.MAX_DAILY_AMOUNT,
})
```

---

## 4. 한국투자증권 API

`KISClient`는 한국투자증권 Open API의 REST 클라이언트이다. 모든 메서드는 Sync(`requests` 라이브러리)로 동작한다.

### 서버 URL

| 모드 | URL | 비고 |
|------|-----|------|
| 모의투자 | `https://openapivts.koreainvestment.com:29443` | `is_paper=True` |
| 실전 | `https://openapi.koreainvestment.com:9443` | `is_paper=False` |

### 인증 (OAuth 토큰)

```python
client.get_access_token()
```

- 엔드포인트: `POST {base_url}/oauth2/tokenP`
- 요청 본문: `{"grant_type": "client_credentials", "appkey": ..., "appsecret": ...}`
- 토큰은 내부에 캐시되며, 만료 1시간 전에 자동 재발급한다.
- 기본 만료 시간: `expires_in` 응답값 (기본 86400초 = 24시간).

### 주요 엔드포인트

**주문 제출**

- 경로: `/uapi/domestic-stock/v1/trading/order-cash`
- 메서드: `POST`
- `tr_id` (모의/실전):

| 구분 | 모의투자 | 실전 |
|------|---------|------|
| 매수 | `VTTC0802U` | `TTTC0802U` |
| 매도 | `VTTC0801U` | `TTTC0801U` |

- 요청 본문:

| 필드 | 설명 | 예시 |
|------|------|------|
| `CANO` | 계좌번호 앞 8자리 | `"12345678"` |
| `ACNT_PRDT_CD` | 계좌번호 뒤 2자리 | `"01"` |
| `PDNO` | 종목코드 | `"005930"` |
| `ORD_DVSN` | 주문 유형 코드 | `"00"`(지정가), `"01"`(시장가) |
| `ORD_QTY` | 주문 수량 (문자열) | `"10"` |
| `ORD_UNPR` | 주문 가격 (문자열, 시장가면 `"0"`) | `"70000"` |

**주문 취소**

- 경로: `/uapi/domestic-stock/v1/trading/order-rvsecncl`
- 메서드: `POST`
- `tr_id`: 모의 `VTTC0803U` / 실전 `TTTC0803U`
- 요청 본문:

| 필드 | 설명 | 값 |
|------|------|----|
| `ORGN_ODNO` | 원래 주문번호 | |
| `RVSE_CNCL_DVSN_CD` | 취소 구분 | `"02"` (취소) |
| `QTY_ALL_ORD_YN` | 전량 여부 | `"Y"` |

**잔고 조회**

- 경로: `/uapi/domestic-stock/v1/trading/inquire-balance`
- 메서드: `GET`
- `tr_id`: 모의 `VTTC8434R` / 실전 `TTTC8434R`
- 주요 파라미터: `CANO`, `ACNT_PRDT_CD`, `INQR_DVSN="02"`, `UNPR_DVSN="01"`
- 응답의 `output1`에 보유 종목 정보, `output`에 예수금 정보가 포함된다.

**주문 체결 내역**

- 경로: `/uapi/domestic-stock/v1/trading/inquire-daily-ccld`
- 메서드: `GET`
- `tr_id`: 모의 `VTTC8001R` / 실전 `TTTC8001R`

**현재가 조회**

- 경로: `/uapi/domestic-stock/v1/quotations/inquire-price`
- 메서드: `GET`
- `tr_id`: `FHKST01010100`
- 파라미터: `FID_COND_MRKT_DIV_CODE="J"`, `FID_INPUT_ISCD={종목코드}`

**일별 시세**

- 경로: `/uapi/domestic-stock/v1/quotations/inquire-daily-price`
- 메서드: `GET`

### 공통 헤더

모든 API 호출에 다음 헤더가 포함된다:

```
Content-Type: application/json; charset=utf-8
authorization: Bearer {access_token}
appkey: {app_key}
appsecret: {app_secret}
tr_id: {거래 ID}
```

### 주문 구분 코드

| 구분 | 코드 |
|------|------|
| 매도 (`SELL`) | `"01"` |
| 매수 (`BUY`) | `"02"` |
| 지정가 (`LIMIT`) | `"00"` |
| 시장가 (`MARKET`) | `"01"` |

---

## 5. PaperBroker vs KISBroker

두 브로커 모두 동일한 Broker Protocol을 구현한다. 핵심 차이는 접속하는 KIS 서버와 안전 검증이다.

### 비교표

| 항목 | `PaperBroker` | `KISBroker` |
|------|--------------|-------------|
| 클라이언트 요구 | `is_paper=True` 필수 | `is_paper=False` 필수 |
| 서버 URL | `openapivts:29443` | `openapi:9443` |
| 실자금 이동 | 없음 | 있음 |
| 안전장치 | 불필요 | `TradingSafeguard` 필수 |
| 초기화 검증 | 실전 클라이언트 전달 시 `ValueError` | 모의 클라이언트 전달 시 `ValueError` |
| 용도 | 전략 검증, 개발, 테스트 | 실전 매매 |

### 공통 메서드

**`submit_order(order: Order) -> OrderResult`**

1. `client.place_order()`를 호출하여 KIS 서버에 주문을 제출한다.
2. 응답의 `rt_cd`가 `"0"`이면 `status="pending"`, 주문번호는 `output.ORNO`에서 추출한다.
3. `rt_cd`가 `"0"`이 아니면 `status="rejected"`.
4. 예외 발생 시에도 `status="rejected"`로 `OrderResult`를 생성한다.
5. 모든 결과를 `audit.log_order()`로 기록한다.

**`cancel_order(order_id: str) -> bool`**

`client.cancel_order()`를 호출한다. `rt_cd == "0"`이면 `True` 반환.

**`get_balance() -> dict`**

`client.get_balance()`를 그대로 반환한다.

**`get_positions() -> list[Position]`**

1. `client.get_positions()`로 원시 데이터를 조회한다.
2. 각 항목을 `Position` 데이터 모델로 변환한다:

| KIS 필드 | Position 필드 | 설명 |
|----------|--------------|------|
| `pdno` | `stock.code` | 종목코드 |
| `prdt_name` | `stock.name` | 종목명 |
| `hldg_qty` | `quantity` | 보유 수량 |
| `pchs_avg_pric` | `avg_price` | 평균 매수가 |
| `prpr` | `current_price` | 현재가 |
| `evlu_pfls_amt` | `unrealized_pnl` | 미실현 손익 |

- `weight`는 `0.0`으로 초기화된다 (PortfolioManager에서 별도 계산).
- `strategy_id`는 빈 문자열이다 (RecoveryManager에서 별도 매핑).

**`get_order_status(order_id: str) -> OrderResult`**

당일 주문 내역(`get_order_history`)에서 해당 주문번호를 찾아 체결 상태를 반환한다.

| 상태 | 조건 |
|------|------|
| `"pending"` | `tot_ccld_qty == 0` |
| `"filled"` | `tot_ccld_qty >= ord_qty` |
| `"partial"` | `0 < tot_ccld_qty < ord_qty` |

---

## 6. 안전장치 (Safeguard)

`TradingSafeguard`는 LIVE 모드 전용 이중 안전장치이다. LIVE 모드에서 `safeguard`가 `None`이면 `TradingEngine` 초기화 시 `ValueError`가 발생한다.

### 세 가지 보호 계층

**계층 1: 환경변수 스위치**

```python
safeguard.check_live_allowed()
```

- `LIVE_TRADING_ENABLED=true`가 설정되어 있어야 한다.
- 미설정 또는 `false`이면 `RuntimeError` 발생: `"실매매가 비활성화 상태입니다."`

**계층 2: 터미널 수동 확인**

```python
safeguard.confirm_live_start(broker.client.account_no)
```

- 터미널에 계좌번호를 표시하고 `yes/no` 입력을 요구한다.
- `TradingEngine.__init__`에서 LIVE 모드일 때 자동 호출된다.

표시 메시지:
```
실매매를 시작합니다.
계좌: 12345678-01
확인하시겠습니까? (yes/no):
```

**계층 3: 일일 주문 한도**

```python
safeguard.check_daily_limit(today_orders, today_amount)
```

| 한도 | 기본값 | 환경변수 |
|------|--------|----------|
| 일일 최대 주문 횟수 | 50회 | `MAX_DAILY_ORDERS` |
| 일일 최대 주문 금액 | 50,000,000원 | `MAX_DAILY_AMOUNT` |

- 한도 초과 시 `RuntimeError` 발생.
- `record_order(amount)`로 누적 카운터를 증가시킨다.
- `reset_daily()`로 새 거래일 시작 시 카운터를 초기화한다.

### TradingEngine 초기화 흐름 (LIVE)

```
TradingEngine.__init__(mode=LIVE, safeguard=safeguard)
  ├── safeguard가 None이면 ValueError 발생
  ├── safeguard.check_live_allowed()   # LIVE_TRADING_ENABLED 확인
  └── safeguard.confirm_live_start()   # 터미널 yes/no 확인
```

---

## 7. 스케줄러

`TradingScheduler`는 KRX 거래일 기반으로 매매 파이프라인을 스케줄링한다.

### 일일 시간표

| 단계 | 시각 | 설명 |
|------|------|------|
| `data_update` | 08:00 | 데이터 갱신 |
| `analysis` | 08:15 | 분석 (시그널 생성) |
| `portfolio` | 08:40 | 포트폴리오 목표 산출 |
| `pre_market_alert` | 08:50 | 장전 매매 계획 알림 |
| `market_open` | 09:00 | 장 시작 (주문 실행) |
| `midday_check` | 12:30 | 중간 점검 |
| `market_close` | 15:30 | 장 마감 |
| `post_market` | 16:00 | 사후 관리 (리포트) |

### 실행 모드

**1회 실행 (`run_once`)**

```python
result = await scheduler.run_once(date="20260411")
```

- 지정 날짜가 거래일이 아니면 `None`을 반환한다.
- 거래일이면 `engine.run_daily(date)`를 호출한다.

**데몬 모드 (`run_daemon`)**

```python
await scheduler.run_daemon()
```

- 무한 루프로 동작한다.
- `KRXCalendar.is_trading_day()`로 거래일 여부를 확인한다.
- 비거래일이면 `calendar.next_trading_day()`로 다음 거래일을 계산하고 07:50까지 `asyncio.sleep`한다.
- 거래일이면 `run_once()`를 실행하고, 완료 후 다음 거래일 07:50까지 대기한다.

### 헬퍼 메서드

| 메서드 | 설명 |
|--------|------|
| `is_active_day(date)` | `KRXCalendar`를 이용해 거래일 여부 반환 |
| `should_run_phase(phase, current_time)` | 현재 시각이 해당 단계 시각 이후인지 판단 |
| `get_next_phase(current_time)` | 다음 실행할 단계와 시각을 반환. 모두 완료면 `(None, None)` |

---

## 8. 알림 시스템

`TradingAlert`는 `TelegramNotifier`를 래핑하여 매매 전용 메시지를 포맷팅한다. 모든 알림 메서드는 async이며, 전송 실패가 매매 로직을 중단하지 않는다.

### 알림 유형

**장전 알림 (`pre_market`)**

- 시점: Phase 3 완료 후, Phase 4 실행 전.
- 타이틀: `"장전 매매 계획"`
- 카테고리: `"trading"`
- 내용:
  - 날짜, Market Pulse 점수, AI 확신도
  - 매수 예정 종목 (상위 5건), 매도 예정 종목 (상위 5건)
  - 리스크 경고 (최대 3건)
  - 주문이 없으면: `"오늘 매매 없음"`

**체결 알림 (`execution`)**

- 시점: Phase 4에서 각 주문 제출 직후.
- 타이틀: `"체결 알림 -- {종목명}"`
- 내용:
  - 매수/매도 방향, 종목명(코드)
  - 상태: `체결 완료` / `부분 체결` / `주문 거부` / `주문 접수`
  - 체결 수량, 체결 가격, 금액
  - 전략 ID

**사후 알림 (`post_market`)**

- 시점: Phase 5 일일 리포트.
- 타이틀: `"일일 성과 리포트"`
- 내용:
  - 날짜, 총 자산, 일간 수익률, 누적 수익률
  - MDD, 보유 종목 수, 현금
  - 리스크 요약 (있는 경우)

**리스크 알림 (`risk_alert`)**

- 시점: 드로다운 Hard 리밋 도달 등 긴급 상황.
- 타이틀: `"긴급 리스크 알림"`
- 카테고리: `"risk"`

**주간 리포트 (`weekly_report`)**

- 타이틀: `"주간 성과 리포트"`
- 내용: 전략별 수익률 귀속 분석.

---

## 9. 잔고 대사

`RecoveryManager`는 DB 포트폴리오 스냅샷과 브로커 실제 잔고를 대사(reconcile)한다.

### reconcile() 로직

1. `PortfolioStore`에서 최신 스냅샷을 로드한다.
2. `Broker.get_positions()`로 실제 보유 종목을 조회한다.
3. 종목코드 기준으로 비교한다 (비중과 전략 ID는 무시).

비교 항목:

| 불일치 유형 | 메시지 형식 |
|------------|-------------|
| DB에만 존재 | `"DB에만 존재: {code} ({name}) DB수량={qty}"` |
| 브로커에만 존재 | `"브로커에만 존재: {code} ({name}) 브로커수량={qty}"` |
| 수량 불일치 | `"수량 불일치: {code} ({name}) DB={qty} vs 브로커={qty}"` |

### 핵심 원칙

- **자동 수정 금지**: 불일치 발견 시 경고만 하고 자동으로 수정하지 않는다.
- 사람이 확인한 후 수동으로 처리해야 한다.

### on_crash_recovery()

시스템 재시작 시 복구 흐름:

1. 마지막 스냅샷 로드.
2. 브로커 실제 잔고 조회.
3. `reconcile()` 수행.
4. 불일치 발견 시 경고.

반환값:
```python
{
    "recovered": True,
    "warnings": ["불일치 메시지 1", ...],
    "snapshot_date": "20260411" | None,
}
```

---

## 10. 감사 추적

`AuditLogger`는 모든 매매 의사결정을 SQLite에 기록한다.

### audit_log 테이블 스키마

```sql
CREATE TABLE IF NOT EXISTS audit_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp       REAL NOT NULL,      -- Unix timestamp (time.time())
    event_type      TEXT NOT NULL,       -- 이벤트 유형
    component       TEXT NOT NULL,       -- 발생 컴포넌트
    data            TEXT NOT NULL,       -- JSON 직렬화된 상세 데이터
    mode            TEXT NOT NULL        -- 실행 모드 (backtest/paper/live)
)
```

### 기록 대상 이벤트

| event_type | component | 발생 시점 | 기록 데이터 |
|-----------|-----------|----------|-------------|
| `order` | `broker` | 주문 제출 결과 | 주문 정보 + 체결 결과 |
| `risk_decision` | `risk_manager` | 리스크 체크 결과 | 주문 + 결정(APPROVE/REDUCE/REJECT) |
| `error` | `data_provider`, `broker`, `ai_synthesizer` | 오류 발생 | 예외 메시지 + 컨텍스트 |

### 데이터베이스 경로

- 기본 경로: `{DATA_DIR}/audit.db` (예: `data/audit.db`)

### 조회 API

```python
audit = AuditLogger(db_path="data/audit.db")

# 전체 조회 (최신순)
events = audit.query()

# 이벤트 유형으로 필터링
orders = audit.query(event_type="order")

# 기간 필터링 (YYYYMMDD)
events = audit.query(event_type="error", start="20260401", end="20260411")
```

---

## 11. CLI 명령어

모든 명령어는 `ap trading` 하위 명령이다.

### ap trading run

매매 파이프라인을 실행한다.

```bash
# 모의투자 1회 실행 (기본)
ap trading run

# 모의투자 1회 실행 (명시적)
ap trading run --mode paper

# 실전매매 1회 실행
ap trading run --mode live

# 모의투자 데몬 모드 (스케줄 기반)
ap trading run --daemon

# 실전매매 데몬 모드
ap trading run --mode live --daemon
```

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `--mode` | `paper` | 실행 모드. `paper` 또는 `live`. |
| `--daemon` | 플래그 | 데몬 모드로 실행 (스케줄 기반). |

### ap trading status

시스템 상태를 확인한다.

```bash
ap trading status
```

출력 항목:
- 모드 (모의투자/실전)
- 실매매 활성화 여부
- 일일 한도 (횟수/금액)
- 전략 배분
- 초기 자본
- 리스크 한도 (종목당 비중, DD soft/hard)
- 최신 포트폴리오 스냅샷 (총자산, 현금, 일간/누적 수익률, 드로다운)

### ap trading reconcile

DB와 증권사 잔고를 대사한다.

```bash
ap trading reconcile
```

- `KIS_APP_KEY`가 설정되어 있어야 한다.
- `KIS_IS_PAPER` 설정에 따라 모의/실전 브로커를 선택한다.
- 불일치 발견 시 경고 메시지를 출력한다.

### ap trading portfolio show

현재 포트폴리오 상태를 표시한다.

```bash
# 모의투자 포트폴리오 (기본)
ap trading portfolio show

# 실전 포트폴리오
ap trading portfolio show --mode live

# 백테스트 포트폴리오
ap trading portfolio show --mode backtest
```

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `--mode` | `paper` | `paper`, `live`, `backtest` 중 선택. |

출력 항목: 날짜, 총자산, 현금, 일간/누적 수익률, 드로다운, 보유 종목 목록 (최대 20개).

### ap trading portfolio history

포트폴리오 성과 이력을 조회한다.

```bash
# 최근 30일 (기본)
ap trading portfolio history

# 최근 90일, 실전
ap trading portfolio history --days 90 --mode live
```

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `--days` | `30` | 조회 기간 (일). |
| `--mode` | `paper` | `paper`, `live`, `backtest` 중 선택. |

### ap trading portfolio attribution

성과 귀속 분석을 실행한다.

```bash
ap trading portfolio attribution
ap trading portfolio attribution --days 30 --mode live
```

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `--days` | `30` | 분석 기간 (일). |
| `--mode` | `paper` | `paper`, `live`, `backtest` 중 선택. |

출력 항목: `strategy_returns`, `factor_returns`, `sector_returns`.

### ap trading risk report

리스크 리포트를 생성한다.

```bash
ap trading risk report
ap trading risk report --mode live
```

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `--mode` | `paper` | `paper`, `live`, `backtest` 중 선택. |

출력 항목: 드로다운 상태, VaR(95%), CVaR(95%), 리스크 경보.

### ap trading risk stress

스트레스 테스트를 실행한다.

```bash
ap trading risk stress
ap trading risk stress --mode live
```

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `--mode` | `paper` | `paper`, `live`, `backtest` 중 선택. |

### ap trading risk limits

현재 리스크 리밋 설정을 표시한다.

```bash
ap trading risk limits
```

출력 항목: 종목당 최대 비중, 드로다운 soft/hard, 일일 주문 한도(횟수/금액).

---

## 12. 환경 설정

`.env` 파일에 설정한다. 모든 변수는 `Config` 클래스를 통해 로드된다.

### KIS API (필수)

| 변수 | 설명 | 기본값 | 예시 |
|------|------|--------|------|
| `KIS_APP_KEY` | 한투 앱 키 | `""` (필수) | `"PSqC3b5W..."` |
| `KIS_APP_SECRET` | 한투 앱 시크릿 | `""` (필수) | `"xR7pN2..."` |
| `KIS_ACCOUNT_NO` | 계좌번호 (형식: `앞8-뒤2`) | `""` (필수) | `"12345678-01"` |
| `KIS_IS_PAPER` | 모의투자 여부 | `"true"` | `"true"` / `"false"` |

### 안전장치

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `LIVE_TRADING_ENABLED` | 실매매 활성화 스위치 | `"false"` |
| `MAX_DAILY_ORDERS` | 일일 최대 주문 횟수 | `"50"` |
| `MAX_DAILY_AMOUNT` | 일일 최대 주문 금액 (원) | `"50000000"` |

### 전략 설정

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `STRATEGY_ALLOCATIONS` | 전략별 배분 (JSON) | `'{"topdown_etf":0.3,"momentum":0.4,"value":0.3}'` |
| `MOMENTUM_TOP_N` | 모멘텀 전략 상위 N종목 | `"20"` |
| `VALUE_TOP_N` | 가치 전략 상위 N종목 | `"15"` |

### 리스크 리밋

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `MAX_POSITION_WEIGHT` | 종목당 최대 비중 | `"0.10"` (10%) |
| `MAX_SECTOR_WEIGHT` | 섹터당 최대 비중 | `"0.30"` (30%) |
| `MAX_DRAWDOWN_SOFT` | 드로다운 경고 임계 | `"0.10"` (-10%) |
| `MAX_DRAWDOWN_HARD` | 드로다운 강제 축소 임계 | `"0.15"` (-15%) |
| `MAX_DAILY_LOSS` | 일간 최대 손실 | `"0.03"` (-3%) |
| `MIN_CASH_RATIO` | 최소 현금 비율 | `"0.05"` (5%) |

### 백테스트/거래 비용

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `BACKTEST_INITIAL_CAPITAL` | 백테스트 초기 자본 (원) | `"100000000"` (1억) |
| `BACKTEST_COMMISSION` | 수수료율 | `"0.00015"` (0.015%) |
| `BACKTEST_TAX` | 세금율 | `"0.0018"` (0.18%) |
| `PAPER_INITIAL_CAPITAL` | 모의투자 초기 자본 (원) | `"100000000"` (1억) |

### 텔레그램 알림

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `TELEGRAM_BOT_TOKEN` | 텔레그램 봇 토큰 | `""` (필수) |
| `TELEGRAM_CHAT_ID` | 텔레그램 채팅 ID | `""` (필수) |

### 데이터베이스 경로 (자동 설정)

다음 경로들은 `Config.DATA_DIR` 기준으로 자동 설정된다. 환경변수가 아닌 코드 내부 상수이다.

| 경로 | 설명 |
|------|------|
| `{DATA_DIR}/trading.db` | 종목 데이터 (OHLCV, 재무, 수급) |
| `{DATA_DIR}/portfolio.db` | 포트폴리오 스냅샷 |
| `{DATA_DIR}/backtest.db` | 백테스트 결과 |
| `{DATA_DIR}/audit.db` | 감사 추적 로그 |

### .env 예시

```bash
# KIS API
KIS_APP_KEY=PSqC3b5W...
KIS_APP_SECRET=xR7pN2...
KIS_ACCOUNT_NO=12345678-01
KIS_IS_PAPER=true

# 안전장치
LIVE_TRADING_ENABLED=false
MAX_DAILY_ORDERS=50
MAX_DAILY_AMOUNT=50000000

# 전략
STRATEGY_ALLOCATIONS={"topdown_etf":0.3,"momentum":0.4,"value":0.3}

# 리스크
MAX_POSITION_WEIGHT=0.10
MAX_DRAWDOWN_SOFT=0.10
MAX_DRAWDOWN_HARD=0.15

# 텔레그램
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGhIjKlmNopQrsTuvWxyz
TELEGRAM_CHAT_ID=-1001234567890
```

---

## 부록: 시스템 모니터링

`SystemMonitor`는 등록된 컴포넌트의 헬스체크를 수행한다.

### 점검 방식

| 컴포넌트 | 점검 방법 |
|----------|----------|
| `broker` | `get_balance()` 호출 |
| 그 외 | `ping()` 또는 `check_health()` 호출 |

### 반환값

```python
{
    "timestamp": "2026-04-11T08:00:00",
    "healthy": True,
    "broker": {"status": "ok", "message": ""},
    "data_provider": {"status": "ok", "message": ""},
}
```

하나라도 실패하면 `healthy`가 `False`가 된다.
