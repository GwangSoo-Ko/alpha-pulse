# 스크리닝 및 랭킹 시스템 운영 가이드

> AlphaPulse Trading 모듈의 종목 스크리닝, 팩터 계산, 멀티팩터 랭킹 파이프라인에 대한 운영 참고 문서.

---

## 목차

1. [개요](#1-개요)
2. [투자 유니버스](#2-투자-유니버스)
3. [팩터 계산기 (FactorCalculator)](#3-팩터-계산기-factorcalculator)
4. [멀티팩터 랭커 (MultiFactorRanker)](#4-멀티팩터-랭커-multifactorranker)
5. [가중치 프리셋](#5-가중치-프리셋)
6. [필터 조건 (StockFilter)](#6-필터-조건-stockfilter)
7. [CLI 명령어](#7-cli-명령어)

---

## 1. 개요

### 1.1 목적

스크리닝/랭킹 시스템은 전체 투자 유니버스에서 **투자 매력도가 높은 종목을 정량적으로 선별**하는 모듈이다. 모멘텀, 밸류, 퀄리티, 성장, 수급, 변동성 등 다양한 팩터를 계산하고 멀티팩터 랭킹을 통해 종합 점수를 산출한다.

### 1.2 처리 흐름

```
유니버스 조회         팩터 계산          필터링          랭킹             시그널 출력
   (Universe)    (FactorCalculator)  (StockFilter)  (MultiFactorRanker)   (Signal)
      |                |                 |                |                  |
      v                v                 v                v                  v
 시장별 종목 --> 종목별 원시값 --> 조건 미달 제외 --> percentile --> 가중 합산 점수
   목록 조회       계산 (20+종)       (시총/거래량)      정규화       (-100 ~ +100)
```

**핵심 원칙:**

- 팩터 계산은 **원시값**을 반환한다. 정규화는 랭커가 담당한다.
- 모든 스크리닝 로직은 **Sync**(동기)로 동작한다.
- 데이터 소스는 `TradingStore` (SQLite) 기반이다.

### 1.3 모듈 구조

| 파일 | 클래스 | 역할 |
|------|--------|------|
| `screening/factors.py` | `FactorCalculator` | 개별 팩터 원시값 계산 |
| `screening/ranker.py` | `MultiFactorRanker` | percentile 정규화 + 가중 합산 |
| `screening/filter.py` | `StockFilter` | 시총/거래량/섹터 필터 |
| `screening/universe_selector.py` | `UniverseSelector` | 전략별 유니버스 선택 |
| `data/universe.py` | `Universe` | 유니버스 관리 및 Stock 변환 |

---

## 2. 투자 유니버스

### 2.1 Universe 클래스

`alphapulse/trading/data/universe.py`에 정의된 `Universe` 클래스가 투자 유니버스를 관리한다.

**주요 메서드:**

| 메서드 | 설명 |
|--------|------|
| `get_all()` | 전체 종목을 `Stock` 리스트로 반환 |
| `get_by_market(market)` | 특정 시장 종목만 조회. `market`: `"KOSPI"`, `"KOSDAQ"`, `"ETF"` |
| `filter_stocks(stocks, min_market_cap, min_avg_volume)` | 시가총액/거래대금 기준 필터링 |

**Stock 데이터 모델:**

```python
@dataclass(frozen=True)
class Stock:
    code: str      # 종목코드 (6자리)
    name: str      # 종목명
    market: str    # "KOSPI" | "KOSDAQ" | "ETF"
    sector: str    # 업종 (기본값: "")
```

### 2.2 시장별 유니버스 조회

`get_by_market()` 메서드로 시장을 지정하여 조회한다. 내부적으로 `TradingStore.get_all_stocks(market=...)` 를 호출한다.

### 2.3 유니버스 필터링

`filter_stocks()` 메서드는 다음 조건을 적용한다:

- **최소 시가총액** (`min_market_cap`): 원 단위. 조건 미달 종목 제외.
- **최소 일평균 거래대금** (`min_avg_volume`): 원 단위. 최근 20영업일 평균.

평균 거래대금 계산 공식:

```
avg_trading_value = sum(close * volume for 최근 20일) / 20
```

### 2.4 UniverseSelector (전략별 유니버스)

`UniverseSelector`는 전략 ID에 따라 서로 다른 유니버스를 적용한다. 예를 들어 ETF 전략은 ETF만, 종목 전략은 주식만 포함할 수 있다.

**선택 기준:**

| 설정 항목 | 설명 |
|-----------|------|
| `include_markets` | 포함할 시장 목록 (예: `["KOSPI"]`) |
| `min_market_cap` | 전략별 최소 시가총액 |
| `min_avg_volume` | 전략별 최소 거래대금 |

---

## 3. 팩터 계산기 (FactorCalculator)

`alphapulse/trading/screening/factors.py`에 정의된 `FactorCalculator`는 종목별 팩터 원시값을 계산한다. spec 5.1 기준 20개 팩터 + 시계열 기반 확장 팩터를 지원한다.

### 3.1 편의 메서드 (기존 호환)

CLI 명령에서 주로 사용하는 대표 편의 메서드:

| 편의 메서드 | 내부 호출 | 설명 |
|-------------|-----------|------|
| `momentum(code, lookback=60)` | `_momentum_by_days(code, 60)` | lookback 기간 수익률 (%) |
| `value(code)` | `value_per(code)` | PER 역수 (E/P) |
| `quality(code)` | `quality_roe(code)` | ROE (%) |
| `growth(code)` | `quality_revenue_growth(code)` | 매출 YoY 성장률 (%) |
| `flow(code, days=20)` | `flow_foreign(code, days=20)` | 외국인 순매수 누적 (원) |

### 3.2 모멘텀 팩터 (5종)

| 팩터 | 메서드 | 계산 공식 | Lookback |
|------|--------|-----------|----------|
| 1개월 모멘텀 | `momentum_1m(code)` | `(종가[-1] - 종가[-20]) / 종가[-20] * 100` | 20영업일 |
| 3개월 모멘텀 | `momentum_3m(code)` | `(종가[-1] - 종가[-60]) / 종가[-60] * 100` | 60영업일 |
| 6개월 모멘텀 | `momentum_6m(code)` | `(종가[-1] - 종가[-120]) / 종가[-120] * 100` | 120영업일 |
| 12-1 모멘텀 | `momentum_12m(code)` | `(종가[-21] - 종가[-261]) / 종가[-261] * 100` | 240영업일 (최근 20일 제외) |
| 52주 신고가 근접도 | `high_52w_proximity(code)` | `현재가 / 52주 고가 * 100` | 252영업일 |

**12-1 모멘텀 상세:**

전통적인 12개월 모멘텀에서 최근 1개월(20영업일)을 제외한다. 이는 단기 반전 효과(short-term reversal)를 배제하기 위함이다.

- 최소 데이터 요건: 22일 이상
- 계산 구간: `rows[start_idx]` ~ `rows[end_idx - 1]` (end_idx = len - 20)

**52주 신고가 근접도:**

100에 가까울수록 현재가가 52주 고가에 근접한 것이다. 데이터가 252일 미만이면 보유한 전체 데이터에서 고가를 구한다.

### 3.3 밸류 팩터 (4종 + Forward 1종)

| 팩터 | 메서드 | 계산 공식 | 데이터 소스 |
|------|--------|-----------|-------------|
| PER 역수 (E/P) | `value_per(code)` | `(1 / PER) * 100` | `fundamentals.per` |
| PBR 역수 (B/P) | `value_pbr(code)` | `(1 / PBR) * 100` | `fundamentals.pbr` |
| PSR 역수 (S/P) | `value_psr(code)` | `(1 / (시가총액 / 매출액)) * 100` | `fundamentals.revenue` + `ohlcv.market_cap` |
| 배당수익률 | `dividend_yield(code)` | 원시 배당수익률 (%) | `fundamentals.dividend_yield` |
| Forward PER 역수 | `forward_per(code)` | `(1 / 추정PER) * 100` | 연간 추정치 (is_estimate=True) |

**밸류 팩터 공통 원칙:**

- PER, PBR, PSR은 **역수**로 변환하여 반환한다. 즉 낮은 PER = 높은 팩터값 = 저평가.
- PER, PBR이 0 이하인 경우 `None`을 반환한다 (적자 기업 등).
- PSR은 시가총액과 매출액을 별도로 조회하여 직접 계산한다.

### 3.4 퀄리티 팩터 (6종)

| 팩터 | 메서드 | 계산 공식 | 데이터 소스 |
|------|--------|-----------|-------------|
| ROE | `quality_roe(code)` | 원시 ROE (%) | `fundamentals.roe` |
| TTM ROE | `quality_roe_ttm(code)` | 최근 4분기 ROE 평균 | 분기 시계열 (`quarterly`) |
| 영업이익 성장률 | `quality_profit_growth(code)` | `(최근분기 - 4분기전) / abs(4분기전) * 100` | 분기 시계열 `operating_profit` |
| 매출 성장률 | `quality_revenue_growth(code)` | `(최근분기 - 4분기전) / abs(4분기전) * 100` | 분기 시계열 `revenue` |
| 순이익 성장률 | `quality_net_income_growth(code)` | `(최근분기 - 4분기전) / abs(4분기전) * 100` | 분기 시계열 `net_income` |
| 부채비율 역수 | `quality_debt_ratio(code)` | `(1 / 부채비율) * 100` | `fundamentals.debt_ratio` |

**YoY 성장률 공식 (공통):**

```
yoy_growth = (current - prior) / abs(prior) * 100
```

- `current`: 최근 분기 값 (`quarters[-1]`)
- `prior`: 4분기 전 값 (`quarters[-5]`), 동일 분기 비교 (YoY)
- 최소 데이터 요건: 5개 분기 이상
- `prior`가 0이면 `None` 반환

**TTM ROE:**

최근 4분기 실적(추정 제외) ROE의 산술 평균. 분기 결산 직후 변동성을 줄이는 용도.

**추가 확장 팩터:**

| 팩터 | 메서드 | 계산 공식 | 최소 데이터 |
|------|--------|-----------|-------------|
| 영업이익률 추세 | `quality_margin_trend(code)` | 최근 4분기 영업이익률 평균 - 직전 4분기 영업이익률 평균 | 8개 분기 |
| 어닝 서프라이즈 | `earnings_surprise(code)` | 최근 실적 영업이익 vs 직전 분기 영업이익 (YoY 성장률 근사) | 2개 분기 (실적) |

### 3.5 수급 팩터 (3종)

| 팩터 | 메서드 | 계산 공식 | 기본 기간 |
|------|--------|-----------|-----------|
| 외국인 순매수 | `flow_foreign(code, days=20)` | N일간 `foreign_net` 합계 (원) | 20영업일 |
| 기관 순매수 | `flow_institutional(code, days=20)` | N일간 `institutional_net` 합계 (원) | 20영업일 |
| 수급 추세 | `flow_trend(code)` | 5일 외국인 순매수 평균 - 20일 외국인 순매수 평균 | 20영업일 |

**수급 추세 상세:**

```
avg_5d  = sum(foreign_net[:5]) / 5
avg_20d = sum(foreign_net[:20]) / 20
flow_trend = avg_5d - avg_20d
```

- 양수: 단기 수급이 장기 대비 개선
- 음수: 단기 수급이 장기 대비 악화
- `avg_20d`가 0이면 `avg_5d` 값을 그대로 반환

### 3.6 역발상 팩터 (2종)

| 팩터 | 메서드 | 계산 공식 | 기본 기간 |
|------|--------|-----------|-----------|
| 공매도 감소율 | `short_decrease(code, days=20)` | `(oldest - recent) / oldest * 100` | 20영업일 |
| 신용잔고 변화율 | `credit_change(code, days=20)` | `(recent - oldest) / oldest * 100` | 20영업일 |

**공매도 감소율:**

- 양수: 공매도 잔고가 감소 (긍정적 신호)
- 음수: 공매도 잔고가 증가 (부정적 신호)
- 데이터는 최신순(DESC) 정렬. `rows[0]`이 최근, `rows[-1]`이 가장 오래된 값.

**신용잔고 변화율:**

- 양수: 신용잔고 증가 (과열 신호)
- 음수: 신용잔고 감소

### 3.7 변동성 팩터 (3종)

| 팩터 | 메서드 | 계산 공식 | 기본 기간 |
|------|--------|-----------|-----------|
| 일간 변동성 | `volatility(code, days=60)` | 일간 수익률 표준편차 x sqrt(252) x 100 | 60영업일 |
| 시장 베타 | `beta(code, benchmark="KOSPI")` | `Cov(stock, market) / Var(market)` | 60영업일 |
| 하방 변동성 | `downside_vol(code, days=60)` | 음수 수익률만의 표준편차 x sqrt(252) x 100 | 60영업일 |

**일간 변동성 (연환산):**

```
daily_return[i] = (close[i] - close[i-1]) / close[i-1]
mean = avg(daily_return)
variance = sum((r - mean)^2) / (N - 1)     # 표본분산 (N-1)
annualized_vol = sqrt(variance) * sqrt(252) * 100
```

- 최소 데이터 요건: 일간 수익률 3개 이상

**시장 베타:**

현재 Phase 1에서는 KOSPI 지수 데이터 대신 **유니버스 내 전 종목의 평균 수익률**을 벤치마크로 근사한다.

```
beta = Cov(stock_returns, market_returns) / Var(market_returns)
```

- 공분산과 분산 모두 표본 통계 (N-1 분모) 사용
- 최소 5일 이상의 수익률 필요
- 종목의 수익률 길이가 시장 수익률과 다르면 제외

**하방 변동성:**

일간 수익률 중 **음수만** 추출하여 표준편차를 계산하고 연환산한다. 하락 리스크만 측정하므로 낮을수록 양호하다. 음수 수익률이 3개 미만이면 `None` 반환.

### 3.8 팩터 반환값 정리

모든 팩터 메서드는 다음 규칙을 따른다:

- 정상 계산 시: `float` 값 반환 (원시값, 정규화 전)
- 데이터 부족/오류 시: `None` 반환
- `None`인 팩터는 랭킹에서 해당 종목의 가중치 계산에서 제외된다

---

## 4. 멀티팩터 랭커 (MultiFactorRanker)

`alphapulse/trading/screening/ranker.py`에 정의된 `MultiFactorRanker`가 팩터 원시값을 정규화하고 종합 점수를 산출한다.

### 4.1 처리 단계

```
팩터 원시값 --> percentile 정규화 (0~100) --> 가중 합산 --> 스케일 변환 (-100~+100)
```

### 4.2 Percentile 정규화

각 팩터에 대해 전체 종목을 순위 기반 percentile로 변환한다.

**정규화 과정:**

1. 해당 팩터의 값이 있는 종목만 추출
2. 값 기준으로 정렬 (일반 팩터: 내림차순, inverse 팩터: 오름차순)
3. 순위 기반 percentile 할당

**Percentile 공식:**

```
percentile = (1 - rank_idx / (N - 1)) * 100
```

- `rank_idx`: 정렬 후 순위 (0부터 시작, 0이 최우수)
- `N`: 해당 팩터 값이 있는 종목 수
- `N = 1`인 경우: 50.0 고정
- 결과 범위: 0 ~ 100

**예시 (5개 종목):**

| 순위 (rank_idx) | percentile |
|:---:|:---:|
| 0 (최우수) | 100.0 |
| 1 | 75.0 |
| 2 | 50.0 |
| 3 | 25.0 |
| 4 (최하위) | 0.0 |

### 4.3 Inverse 팩터

아래 팩터는 **낮을수록 좋은 값**이므로 정렬 방향이 반대이다 (오름차순 정렬 후 percentile 할당):

| Inverse 팩터 | 설명 |
|--------------|------|
| `volatility` | 변동성이 낮을수록 우수 |
| `downside_vol` | 하방 변동성이 낮을수록 우수 |
| `debt_ratio_raw` | 원시 부채비율이 낮을수록 우수 (명시적 raw 사용 시) |

> **참고:** `quality_debt_ratio()` 메서드는 이미 역수로 반환하므로 inverse 처리 대상이 아니다. `debt_ratio_raw`는 원시 부채비율을 직접 사용할 때만 해당한다.

### 4.4 종합 점수 계산

Percentile 값에 가중치를 곱하여 합산한 뒤 -100 ~ +100 스케일로 변환한다.

**공식:**

```
raw_score = sum(percentile[i] * weight[i]) / sum(weight[i])    (값이 있는 팩터만)
score = (raw_score - 50) * 2
score = clamp(score, -100, +100)                               (소수점 1자리 반올림)
```

**변환 예시:**

| raw_score (0~100) | 최종 score (-100~+100) | 의미 |
|:---:|:---:|:---:|
| 100.0 | +100.0 | 전 팩터 최상위 |
| 75.0 | +50.0 | 상위권 |
| 50.0 | 0.0 | 중위 |
| 25.0 | -50.0 | 하위권 |
| 0.0 | -100.0 | 전 팩터 최하위 |

### 4.5 출력: Signal 객체

랭킹 결과는 `Signal` 데이터 클래스 리스트로 반환된다 (점수 내림차순 정렬).

```python
@dataclass
class Signal:
    stock: Stock              # 종목 정보
    score: float              # 종합 점수 (-100 ~ +100)
    factors: dict[str, float] # 팩터별 percentile (소수점 1자리)
    strategy_id: str          # 전략 ID
    timestamp: datetime       # 생성 시각
```

---

## 5. 가중치 프리셋

CLI의 `screen` 및 `signals` 명령에서 사용하는 팩터 가중치 프리셋이다. 모든 값은 소스코드에서 추출한 실제 값이다.

### 5.1 프리셋 목록

#### momentum (모멘텀)

| 팩터 | 가중치 |
|------|:------:|
| momentum | 0.50 |
| flow | 0.30 |
| volatility | 0.20 |
| **합계** | **1.00** |

특징: 가격 추세와 수급에 집중. 변동성은 리스크 조절 용도.

#### value (밸류)

| 팩터 | 가중치 |
|------|:------:|
| value | 0.40 |
| quality | 0.20 |
| momentum | 0.20 |
| flow | 0.15 |
| volatility | 0.05 |
| **합계** | **1.00** |

특징: 저평가 종목 중심. 퀄리티와 모멘텀으로 밸류 트랩 회피.

#### quality (퀄리티)

| 팩터 | 가중치 |
|------|:------:|
| quality | 0.35 |
| growth | 0.20 |
| momentum | 0.20 |
| value | 0.15 |
| flow | 0.10 |
| **합계** | **1.00** |

특징: 높은 ROE/성장성 중심. 밸류와 모멘텀 보조.

#### growth (성장)

| 팩터 | 가중치 |
|------|:------:|
| growth | 0.40 |
| momentum | 0.25 |
| quality | 0.15 |
| flow | 0.15 |
| volatility | 0.05 |
| **합계** | **1.00** |

특징: 매출 성장 중심. 모멘텀과 수급으로 시장 반영 확인.

#### balanced (균형)

| 팩터 | 가중치 |
|------|:------:|
| momentum | 0.25 |
| flow | 0.25 |
| value | 0.20 |
| quality | 0.15 |
| growth | 0.10 |
| volatility | 0.05 |
| **합계** | **1.00** |

특징: 한국 시장 특화. 외국인 수급(flow)과 모멘텀이 합산 50%로 가장 높은 비중. `screen` 명령에서 인식되지 않는 팩터명을 지정하면 이 프리셋이 기본 적용된다.

#### topdown_etf (탑다운 ETF)

| 팩터 | 가중치 |
|------|:------:|
| momentum | 0.50 |
| flow | 0.30 |
| volatility | 0.20 |
| **합계** | **1.00** |

특징: ETF 전용 전략. 가중치 구조는 momentum 프리셋과 동일. `signals` 명령에서만 사용 가능.

### 5.2 프리셋 비교 (시각화)

```
팩터         momentum  value  quality  growth  balanced  topdown_etf
─────────────────────────────────────────────────────────────────────
momentum       0.50    0.20    0.20     0.25     0.25       0.50
value            -     0.40    0.15      -       0.20         -
quality          -     0.20    0.35     0.15     0.15         -
growth           -       -     0.20     0.40     0.10         -
flow           0.30    0.15    0.10     0.15     0.25       0.30
volatility     0.20    0.05      -      0.05     0.05       0.20
```

### 5.3 사용되는 편의 메서드 매핑

CLI 명령에서 팩터 데이터를 계산할 때 다음 편의 메서드가 호출된다:

| 프리셋 팩터명 | 호출 메서드 | 실제 계산 |
|---------------|-------------|-----------|
| `momentum` | `calc.momentum(code)` | 60영업일 수익률 (%) |
| `value` | `calc.value(code)` | PER 역수 (E/P, %) |
| `quality` | `calc.quality(code)` | ROE (%) |
| `growth` | `calc.growth(code)` | 매출 YoY 성장률 (%) |
| `flow` | `calc.flow(code)` | 외국인 20일 순매수 누적 (원) |
| `volatility` | `calc.volatility(code)` | 연환산 변동성 (%) |

> `screen` 명령은 추가로 `profit_growth` (`quality_profit_growth`)와 `debt_ratio` (`quality_debt_ratio`)도 계산하지만, 현재 기본 프리셋에서는 가중치에 포함되지 않는다.

---

## 6. 필터 조건 (StockFilter)

`alphapulse/trading/screening/filter.py`에 정의된 `StockFilter`는 투자 부적격 종목을 제외한다.

### 6.1 필터 기준

| 필터 항목 | 설정 키 | 설명 | 비교 방식 |
|-----------|---------|------|-----------|
| 최소 시가총액 | `min_market_cap` | 원 단위. `None`이면 필터 미적용. | `stock_data["market_cap"] < min_market_cap` 이면 제외 |
| 최소 평균 거래량 | `min_avg_volume` | 원 단위. `None`이면 필터 미적용. | `stock_data["avg_volume"] < min_avg_volume` 이면 제외 |
| 제외 섹터 | `exclude_sectors` | 섹터명 리스트. 빈 리스트가 기본값. | `stock.sector in exclude_sectors` 이면 제외 |

### 6.2 사용 방법

```python
filter_config = {
    "min_market_cap": 100_000_000_000,   # 1,000억 원
    "min_avg_volume": 1_000_000_000,     # 10억 원
    "exclude_sectors": ["금융", "유틸리티"],
}

stock_filter = StockFilter(filter_config)
filtered = stock_filter.apply(stocks, stock_data)
```

### 6.3 설계 특징

- `stock_data`는 **외부에서 주입**한다 (테스트 용이성을 위한 의도적 설계).
- 필터 기준이 `None`이면 해당 조건을 건너뛴다 (선택적 적용).
- 모든 조건은 AND 로직: 하나라도 미달하면 제외.

---

## 7. CLI 명령어

### 7.1 `ap trading screen` -- 팩터 기반 종목 스크리닝

**문법:**

```bash
ap trading screen [OPTIONS]
```

**옵션:**

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `--market` | `KOSPI` | 시장 (`KOSPI` / `KOSDAQ`) |
| `--top` | `20` | 출력할 상위 종목 수 |
| `--factor` | `momentum` | 가중치 프리셋 (`momentum`, `value`, `quality`, `growth`, `balanced`) |

**사용 예시:**

```bash
# KOSPI 모멘텀 상위 20종목
ap trading screen

# KOSDAQ 밸류 상위 10종목
ap trading screen --market KOSDAQ --factor value --top 10

# KOSPI 균형 전략 상위 30종목
ap trading screen --factor balanced --top 30
```

**출력 포맷:**

```
============================================================
 KOSPI 종목 스크리닝 (팩터: momentum, 상위 20)
============================================================
 순위  종목코드  종목명          점수  주요팩터
 --------------------------------------------------------
    1  005930  삼성전자         +72.3  momentum
    2  000660  SK하이닉스       +68.1  flow
    3  035720  카카오           +55.9  momentum
   ...
```

- **순위**: 종합 점수 내림차순
- **점수**: -100 ~ +100 스케일
- **주요팩터**: percentile이 가장 높은 팩터명

**동작 흐름:**

1. 지정 시장의 전체 종목 조회 (`Universe.get_by_market`)
2. 6개 팩터 + 2개 추가 팩터 계산 (momentum, value, quality, growth, profit_growth, debt_ratio, flow, volatility)
3. 프리셋 가중치 적용하여 `MultiFactorRanker.rank()` 호출
4. 상위 N종목 출력

### 7.2 `ap trading signals` -- 전략 시그널 생성

**문법:**

```bash
ap trading signals [OPTIONS]
```

**옵션:**

| 옵션 | 기본값 | 선택지 | 설명 |
|------|--------|--------|------|
| `--strategy` | `momentum` | `momentum`, `value`, `quality`, `growth`, `balanced`, `topdown_etf` | 전략 프리셋 |
| `--market` | `KOSPI` | - | 시장 |
| `--top` | `20` | - | 상위 종목 수 |

**사용 예시:**

```bash
# KOSPI 모멘텀 전략 시그널
ap trading signals

# KOSDAQ 밸류 전략 상위 15종목
ap trading signals --strategy value --market KOSDAQ --top 15

# ETF 탑다운 전략
ap trading signals --strategy topdown_etf --market ETF

# 균형 전략
ap trading signals --strategy balanced
```

**출력 포맷:**

```
[시장 상황] Pulse Score: +23.5 (매수 우위)

======================================================================
 KOSPI momentum 전략 시그널 (상위 20)
======================================================================
 순위  종목코드  종목명             점수  주요 팩터
 --------------------------------------------------------------------
    1  005930  삼성전자           +72.3  momentum(95)
    2  000660  SK하이닉스         +68.1  flow(88)
    3  035720  카카오             +55.9  momentum(82)
   ...

  권장 액션: 매수
```

### 7.3 `screen` vs `signals` 차이점

| 항목 | `screen` | `signals` |
|------|----------|-----------|
| 목적 | 팩터 기반 단순 랭킹 | 전략 시그널 생성 |
| Market Pulse 연동 | 없음 | 있음 (시장 상황 조회) |
| 매도 시장 보정 | 없음 | momentum 전략 시 점수 0.5배 축소 |
| 권장 액션 표시 | 없음 | 매수 / 관망/축소 표시 |
| 프리셋 | 5종 (momentum, value, quality, growth, balanced) | 6종 (+ topdown_etf) |
| 팩터 지정 방식 | `--factor` (자유 입력, 미인식 시 balanced) | `--strategy` (click.Choice 제한) |
| 팩터 출력 형식 | 팩터명만 | 팩터명 + percentile 값 |

**시장 매도 우위 보정 (signals 전용):**

Market Pulse의 신호가 "bearish" 또는 "매도"를 포함하고, 전략이 `momentum`인 경우:

```python
for sig in ranked:
    sig.score *= 0.5   # 점수 50% 축소
```

권장 액션도 "관망/축소"로 변경된다.

---

## 부록

### A. 데이터 의존성 요약

| 팩터 카테고리 | 필요 데이터 | TradingStore 메서드 |
|--------------|-------------|---------------------|
| 모멘텀 | OHLCV | `get_ohlcv()` |
| 밸류 | 재무제표, OHLCV (시가총액) | `get_fundamentals()`, `get_ohlcv()` |
| 퀄리티 | 재무제표, 분기 시계열 | `get_fundamentals()`, `get_fundamentals_timeseries()` |
| 수급 | 투자자 거래 | `get_investor_flow()` |
| 역발상 | 공매도/신용 잔고 | `get_short_interest()` |
| 변동성 | OHLCV | `get_ohlcv()` |

### B. 전체 팩터 목록 (24종)

| 번호 | 카테고리 | 팩터명 | 메서드 | 높을수록 좋음 |
|:----:|----------|--------|--------|:---:|
| 1 | 모멘텀 | 1개월 수익률 | `momentum_1m` | O |
| 2 | 모멘텀 | 3개월 수익률 | `momentum_3m` | O |
| 3 | 모멘텀 | 6개월 수익률 | `momentum_6m` | O |
| 4 | 모멘텀 | 12-1 모멘텀 | `momentum_12m` | O |
| 5 | 모멘텀 | 52주 신고가 근접도 | `high_52w_proximity` | O |
| 6 | 밸류 | PER 역수 (E/P) | `value_per` | O |
| 7 | 밸류 | PBR 역수 (B/P) | `value_pbr` | O |
| 8 | 밸류 | PSR 역수 (S/P) | `value_psr` | O |
| 9 | 밸류 | 배당수익률 | `dividend_yield` | O |
| 10 | 밸류 | Forward PER 역수 | `forward_per` | O |
| 11 | 퀄리티 | ROE | `quality_roe` | O |
| 12 | 퀄리티 | TTM ROE | `quality_roe_ttm` | O |
| 13 | 퀄리티 | 영업이익 성장률 | `quality_profit_growth` | O |
| 14 | 퀄리티 | 매출 성장률 | `quality_revenue_growth` | O |
| 15 | 퀄리티 | 순이익 성장률 | `quality_net_income_growth` | O |
| 16 | 퀄리티 | 부채비율 역수 | `quality_debt_ratio` | O |
| 17 | 퀄리티 | 영업이익률 추세 | `quality_margin_trend` | O |
| 18 | 퀄리티 | 어닝 서프라이즈 | `earnings_surprise` | O |
| 19 | 수급 | 외국인 순매수 | `flow_foreign` | O |
| 20 | 수급 | 기관 순매수 | `flow_institutional` | O |
| 21 | 수급 | 수급 추세 | `flow_trend` | O |
| 22 | 역발상 | 공매도 감소율 | `short_decrease` | O |
| 23 | 역발상 | 신용잔고 변화율 | `credit_change` | O |
| 24 | 변동성 | 일간 변동성 | `volatility` | X (inverse) |
| 25 | 변동성 | 시장 베타 | `beta` | - (전략 의존) |
| 26 | 변동성 | 하방 변동성 | `downside_vol` | X (inverse) |

> 편의 메서드 `momentum()`, `value()`, `quality()`, `growth()`, `flow()`는 위 개별 팩터의 래퍼이므로 별도 카운트하지 않는다.

### C. 파이프라인 코드 경로

```
alphapulse/
  trading/
    data/
      universe.py           # Universe 클래스
      store.py              # TradingStore (SQLite)
    screening/
      __init__.py
      factors.py            # FactorCalculator (24+ 팩터)
      ranker.py             # MultiFactorRanker
      filter.py             # StockFilter
      universe_selector.py  # UniverseSelector
    core/
      models.py             # Stock, Signal 데이터 모델
  cli.py                    # screen, signals CLI 명령
```
