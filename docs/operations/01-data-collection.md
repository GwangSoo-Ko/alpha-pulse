# AlphaPulse 데이터 수집 시스템 운영 레퍼런스

## 1. 개요

AlphaPulse 데이터 수집 시스템은 한국 주식시장(KOSPI/KOSDAQ) 종목의 가격, 재무, 수급, 공매도, 기업분석 데이터를 자동으로 수집하여 SQLite 데이터베이스(`trading.db`)에 저장한다.

### 1.1 아키텍처

```
┌──────────────────────────────────────────────────────────────┐
│                     CLI (ap trading data)                     │
├──────────────────────────────────────────────────────────────┤
│                    DataScheduler (2단계)                       │
│  ┌────────────────────────┐  ┌────────────────────────────┐  │
│  │ Stage 1: 전종목 기본    │  │ Stage 2: 후보 N종목 상세    │  │
│  │ (sync, 빠름)           │  │ (crawl4ai, 느림)           │  │
│  └────────────────────────┘  └────────────────────────────┘  │
├──────────────────────────────────────────────────────────────┤
│                       BulkCollector                            │
│  ┌───────────┐ ┌────────────────┐ ┌────────────────────────┐ │
│  │ Stock      │ │ Fundamental    │ │ Flow      │ Wisereport │ │
│  │ Collector  │ │ Collector      │ │ Collector │ Collector  │ │
│  └───────────┘ └────────────────┘ └────────────────────────┘ │
│  ┌──────────────────┐                                         │
│  │ ShortCollector    │                                         │
│  │ (crawl4ai, async) │                                         │
│  └──────────────────┘                                         │
├──────────────────────────────────────────────────────────────┤
│        RateLimiter / RateBucket / ProgressTracker             │
├──────────────────────────────────────────────────────────────┤
│           TradingStore (SQLite) + CollectionMetadata           │
└──────────────────────────────────────────────────────────────┘
```

### 1.2 동기/비동기 구분

| 구분 | 방식 | 수집기 |
|------|------|--------|
| **Sync** (requests + BeautifulSoup) | `requests.get()` | StockCollector, FundamentalCollector, FlowCollector, WisereportCollector(정적) |
| **Sync** (pykrx) | `pykrx.stock.get_market_ohlcv()` | StockCollector (OHLCV 1차 시도) |
| **Async** (crawl4ai) | `AsyncWebCrawler` | ShortCollector, WisereportCollector(동적: 투자지표, 컨센서스, 업종분석) |

### 1.3 데이터베이스 위치

기본 경로: `{DATA_DIR}/trading.db` (Config 설정에 따름)

---

## 2. 데이터베이스 스키마

### 2.1 stocks -- 종목 마스터

| 컬럼명 | 타입 | 설명 | 비고 |
|--------|------|------|------|
| `code` | TEXT | 종목코드 (예: "005930") | **PK** |
| `name` | TEXT NOT NULL | 종목명 | |
| `market` | TEXT NOT NULL | 시장 ("KOSPI", "KOSDAQ", "ETF") | |
| `sector` | TEXT | 업종 | 기본값: '' |
| `market_cap` | REAL | 시가총액 | 기본값: 0 |
| `is_tradable` | INTEGER | 거래 가능 여부 (1=가능) | 기본값: 1 |
| `updated_at` | REAL | 갱신 시각 (Unix timestamp) | |

### 2.2 ohlcv -- 일봉 데이터

| 컬럼명 | 타입 | 설명 | 비고 |
|--------|------|------|------|
| `code` | TEXT NOT NULL | 종목코드 | **PK (code, date)** |
| `date` | TEXT NOT NULL | 날짜 (YYYYMMDD) | **PK** |
| `open` | REAL | 시가 | |
| `high` | REAL | 고가 | |
| `low` | REAL | 저가 | |
| `close` | REAL | 종가 | |
| `volume` | INTEGER | 거래량 | |
| `market_cap` | REAL | 시가총액 | 기본값: 0 |

### 2.3 fundamentals -- 재무제표 스냅샷

| 컬럼명 | 타입 | 설명 | 비고 |
|--------|------|------|------|
| `code` | TEXT NOT NULL | 종목코드 | **PK (code, date)** |
| `date` | TEXT NOT NULL | 기준일 (YYYYMMDD) | **PK** |
| `per` | REAL | 주가수익비율 | |
| `pbr` | REAL | 주가순자산비율 | |
| `roe` | REAL | 자기자본이익률 (%) | |
| `revenue` | REAL | 매출액 | |
| `operating_profit` | REAL | 영업이익 | |
| `net_income` | REAL | 당기순이익 | |
| `debt_ratio` | REAL | 부채비율 (%) | |
| `dividend_yield` | REAL | 배당수익률 (%) | |

### 2.4 fundamentals_timeseries -- 재무 시계열 (연간/분기)

| 컬럼명 | 타입 | 설명 | 비고 |
|--------|------|------|------|
| `code` | TEXT NOT NULL | 종목코드 | **PK (code, period, period_type)** |
| `period` | TEXT NOT NULL | 기간 (예: "2024.12") | **PK** |
| `period_type` | TEXT NOT NULL | "annual" 또는 "quarterly" | **PK** |
| `is_estimate` | INTEGER | 추정치 여부 (0=실적, 1=추정) | 기본값: 0 |
| `revenue` | REAL | 매출액 | |
| `operating_profit` | REAL | 영업이익 | |
| `net_income` | REAL | 당기순이익 | |
| `operating_margin` | REAL | 영업이익률 (%) | |
| `net_margin` | REAL | 순이익률 (%) | |
| `roe` | REAL | 자기자본이익률 (%) | |
| `debt_ratio` | REAL | 부채비율 (%) | |
| `quick_ratio` | REAL | 당좌비율 (%) | |
| `reserve_ratio` | REAL | 유보율 (%) | |
| `eps` | REAL | 주당순이익 | |
| `per` | REAL | 주가수익비율 | |
| `bps` | REAL | 주당순자산 | |
| `pbr` | REAL | 주가순자산비율 | |
| `dps` | REAL | 주당배당금 | |
| `div_yield` | REAL | 시가배당률 (%) | |
| `div_payout` | REAL | 배당성향 (%) | |
| `updated_at` | REAL | 갱신 시각 (Unix timestamp) | |

### 2.5 stock_investor_flow -- 투자자별 수급

| 컬럼명 | 타입 | 설명 | 비고 |
|--------|------|------|------|
| `code` | TEXT NOT NULL | 종목코드 | **PK (code, date)** |
| `date` | TEXT NOT NULL | 날짜 (YYYYMMDD) | **PK** |
| `foreign_net` | REAL | 외국인 순매매량 | |
| `institutional_net` | REAL | 기관 순매매량 | |
| `individual_net` | REAL | 개인 순매매량 | = -(외국인+기관) |
| `foreign_holding_pct` | REAL | 외국인 보유비율 (%) | |

### 2.6 short_interest -- 공매도/신용

| 컬럼명 | 타입 | 설명 | 비고 |
|--------|------|------|------|
| `code` | TEXT NOT NULL | 종목코드 | **PK (code, date)** |
| `date` | TEXT NOT NULL | 날짜 (YYYYMMDD) | **PK** |
| `short_volume` | INTEGER | 공매도 수량 | |
| `short_balance` | INTEGER | 공매도 잔고 수량 | |
| `short_ratio` | REAL | 공매도 비율 | |
| `credit_balance` | REAL | 신용잔고 | |
| `lending_balance` | REAL | 대차잔고 | |

### 2.7 wisereport_data -- 기업현황 종합

| 컬럼명 | 타입 | 설명 | 비고 |
|--------|------|------|------|
| `code` | TEXT NOT NULL | 종목코드 | **PK (code, date)** |
| `date` | TEXT NOT NULL | 기준일 (YYYYMMDD) | **PK** |
| `market_cap` | REAL | 시가총액 | |
| `beta` | REAL | 52주 베타 | |
| `foreign_pct` | REAL | 외국인지분율 (%) | |
| `high_52w` | REAL | 52주 최고가 | |
| `low_52w` | REAL | 52주 최저가 | |
| `return_1m` | REAL | 1개월 수익률 (%) | |
| `return_3m` | REAL | 3개월 수익률 (%) | |
| `return_6m` | REAL | 6개월 수익률 (%) | |
| `return_1y` | REAL | 1년 수익률 (%) | |
| `per` | REAL | PER (실적) | |
| `pbr` | REAL | PBR | |
| `pcr` | REAL | PCR | |
| `ev_ebitda` | REAL | EV/EBITDA | |
| `eps` | REAL | EPS (실적) | |
| `bps` | REAL | BPS | |
| `dividend_yield` | REAL | 배당수익률 (%) | |
| `est_per` | REAL | PER (추정) | |
| `est_eps` | REAL | EPS (추정) | |
| `target_price` | REAL | 컨센서스 목표주가 | |
| `analyst_count` | INTEGER | 추정기관수 | |
| `consensus_opinion` | REAL | 투자의견 (점수) | |
| `revenue` | REAL | 매출액 (최근 연간) | |
| `operating_profit` | REAL | 영업이익 | |
| `net_income` | REAL | 당기순이익 | |
| `roe` | REAL | ROE (%) | |
| `roa` | REAL | ROA (%) | |
| `debt_ratio` | REAL | 부채비율 (%) | |
| `operating_margin` | REAL | 영업이익률 (%) | |
| `net_margin` | REAL | 순이익률 (%) | |

### 2.8 company_overview -- 기업개요 (c1020001)

| 컬럼명 | 타입 | 설명 | 비고 |
|--------|------|------|------|
| `code` | TEXT NOT NULL | 종목코드 | **PK (code, date)** |
| `date` | TEXT NOT NULL | 기준일 (YYYYMMDD) | **PK** |
| `products` | TEXT | 매출구성 (JSON) | 예: [{"name":"반도체","ratio":45.2}] |
| `rd_expense` | REAL | 연구개발비 | |
| `rd_ratio` | REAL | 매출 대비 R&D 비율 (%) | |
| `established` | TEXT | 설립일 | |
| `listed` | TEXT | 상장일 | |
| `employees` | INTEGER | 종업원 수 | |
| `subsidiary_count` | INTEGER | 관계사 수 | |

### 2.9 investment_indicators -- 투자지표 시계열 (c1040001)

| 컬럼명 | 타입 | 설명 | 비고 |
|--------|------|------|------|
| `code` | TEXT NOT NULL | 종목코드 | **PK (code, date, period, indicator)** |
| `date` | TEXT NOT NULL | 기준일 (YYYYMMDD) | **PK** |
| `period` | TEXT NOT NULL | 기간 (예: "2024") | **PK** |
| `indicator` | TEXT NOT NULL | 지표명 (예: "ROE", "부채비율") | **PK** |
| `value` | REAL | 지표 값 | |

### 2.10 consensus_estimates -- 컨센서스 추정실적 (c1050001)

| 컬럼명 | 타입 | 설명 | 비고 |
|--------|------|------|------|
| `code` | TEXT NOT NULL | 종목코드 | **PK (code, date, period)** |
| `date` | TEXT NOT NULL | 기준일 (YYYYMMDD) | **PK** |
| `period` | TEXT NOT NULL | 기간 (예: "2025E") | **PK** |
| `revenue` | REAL | 추정 매출액 | |
| `operating_profit` | REAL | 추정 영업이익 | |
| `net_income` | REAL | 추정 당기순이익 | |
| `eps` | REAL | 추정 EPS | |
| `per` | REAL | 추정 PER | |
| `analyst_count` | INTEGER | 추정기관수 | |

### 2.11 sector_comparison -- 업종 비교 (c1060001)

| 컬럼명 | 타입 | 설명 | 비고 |
|--------|------|------|------|
| `code` | TEXT NOT NULL | 종목코드 | **PK (code, date)** |
| `date` | TEXT NOT NULL | 기준일 (YYYYMMDD) | **PK** |
| `sector` | TEXT | 업종명 | |
| `rank_in_sector` | INTEGER | 업종 내 순위 | |
| `sector_per` | REAL | 업종 PER | |
| `sector_pbr` | REAL | 업종 PBR | |
| `comparison_data` | TEXT | 비교 데이터 (JSON) | |

### 2.12 shareholder_data -- 지분 현황 (c1070001)

| 컬럼명 | 타입 | 설명 | 비고 |
|--------|------|------|------|
| `code` | TEXT NOT NULL | 종목코드 | **PK (code, date)** |
| `date` | TEXT NOT NULL | 기준일 (YYYYMMDD) | **PK** |
| `largest_holder` | TEXT | 최대주주명 | |
| `largest_pct` | REAL | 최대주주 지분율 (%) | |
| `foreign_pct` | REAL | 외국인 지분율 (%) | |
| `institutional_pct` | REAL | 기관 지분율 (%) | |
| `float_pct` | REAL | 유동주식 비율 (%) | |
| `float_shares` | INTEGER | 유동주식 수 | |
| `changes` | TEXT | 지분 변동 내역 (JSON) | |

### 2.13 analyst_reports -- 증권사 리포트 (c1080001)

| 컬럼명 | 타입 | 설명 | 비고 |
|--------|------|------|------|
| `code` | TEXT NOT NULL | 종목코드 | **PK (code, report_date, provider)** |
| `report_date` | TEXT NOT NULL | 리포트 발행일 | **PK** |
| `analyst` | TEXT | 애널리스트명 | |
| `provider` | TEXT | 증권사명 | **PK** |
| `title` | TEXT | 리포트 제목 | |
| `opinion` | TEXT | 투자의견 (매수/보유 등) | |
| `target_price` | REAL | 목표주가 | |

### 2.14 etf_info -- ETF 정보

| 컬럼명 | 타입 | 설명 | 비고 |
|--------|------|------|------|
| `code` | TEXT | ETF 종목코드 | **PK** |
| `name` | TEXT | ETF 명칭 | |
| `category` | TEXT | 분류 | |
| `underlying` | TEXT | 기초자산 | |
| `expense_ratio` | REAL | 총보수 (%) | |
| `nav` | REAL | 기준가 (NAV) | |
| `updated_at` | REAL | 갱신 시각 (Unix timestamp) | |

### 2.15 collection_metadata -- 수집 메타데이터

| 컬럼명 | 타입 | 설명 | 비고 |
|--------|------|------|------|
| `market` | TEXT NOT NULL | 시장/스코프 ("KOSPI", "KOSDAQ", "ALL", "TOP") | **PK (market, data_type)** |
| `data_type` | TEXT NOT NULL | 데이터 유형 ("ohlcv", "fundamentals", "flow", "wisereport", "short" 등) | **PK** |
| `last_date` | TEXT NOT NULL | 마지막 수집일 (YYYYMMDD) | |
| `updated_at` | REAL | 갱신 시각 (Unix timestamp) | |

---

## 3. 데이터 소스별 수집기

### 3.1 StockCollector -- 종목 목록 및 OHLCV

**소스 파일**: `alphapulse/trading/data/stock_collector.py`

#### 종목 목록 수집

| 항목 | 내용 |
|------|------|
| **데이터 소스** | `https://finance.naver.com/sise/sise_market_sum.naver` |
| **수집 방식** | requests + BeautifulSoup (sync) |
| **수집 항목** | 종목코드(`code`), 종목명(`name`), 시장(`market`) |
| **저장 테이블** | `stocks` |
| **파라미터** | `sosok=0` (KOSPI), `sosok=1` (KOSDAQ), 최대 50페이지 |
| **요청 딜레이** | 페이지당 0.3초 |

#### OHLCV 수집 (1차: pykrx)

| 항목 | 내용 |
|------|------|
| **데이터 소스** | KRX (pykrx 라이브러리 경유) |
| **수집 방식** | pykrx (sync) -- `stock.get_market_ohlcv(start, end, code)` |
| **수집 항목** | 시가, 고가, 저가, 종가, 거래량 |
| **저장 테이블** | `ohlcv` |
| **특징** | 1회 호출로 전체 기간 반환 (빠름), KRX 로그인 불필요 |

#### OHLCV 수집 (2차 폴백: 네이버 금융)

| 항목 | 내용 |
|------|------|
| **데이터 소스** | `https://finance.naver.com/item/sise_day.naver` |
| **수집 방식** | requests + BeautifulSoup (sync) |
| **수집 항목** | 시가, 고가, 저가, 종가, 거래량 |
| **저장 테이블** | `ohlcv` |
| **파라미터** | `code={종목코드}`, `page={페이지번호}`, 최대 100페이지 |
| **요청 딜레이** | 페이지당 0.3초 |

### 3.2 FundamentalCollector -- 기본 재무제표

**소스 파일**: `alphapulse/trading/data/fundamental_collector.py`

| 항목 | 내용 |
|------|------|
| **데이터 소스** | `https://finance.naver.com/item/main.naver` |
| **수집 방식** | requests + BeautifulSoup (sync), 병렬 (`ThreadPoolExecutor`) |
| **수집 항목** | PER, PBR, 배당수익률 (per_table), 연간/분기 재무 시계열 (tb_type1_ifrs) |
| **저장 테이블** | `fundamentals`, `fundamentals_timeseries` |
| **병렬 워커** | 기본 `max_workers=5` |
| **시계열 필드** | revenue, operating_profit, net_income, operating_margin, net_margin, roe, debt_ratio, quick_ratio, reserve_ratio, eps, per, bps, pbr, dps, div_yield, div_payout |
| **전역 Rate Limiter** | `RateBucket(rate=8.0, capacity=8)` |

### 3.3 FlowCollector -- 투자자 수급

**소스 파일**: `alphapulse/trading/data/flow_collector.py`

| 항목 | 내용 |
|------|------|
| **데이터 소스** | `https://finance.naver.com/item/frgn.naver` |
| **수집 방식** | requests + BeautifulSoup (sync) |
| **수집 항목** | 기관 순매매(tds[5]), 외국인 순매매(tds[6]), 외국인 보유비율(tds[8]) |
| **저장 테이블** | `stock_investor_flow` |
| **파라미터** | `code={종목코드}`, `page={페이지번호}`, 최대 100페이지 |
| **요청 딜레이** | 페이지당 0.3초 |
| **개인 순매매** | `-(기관 + 외국인)` 근사 계산 |

BulkCollector에서는 수급을 병렬 수집하며, 별도의 RateBucket(rate=8.0)과 429 백오프 로직이 적용된다.

### 3.4 ShortCollector -- 공매도

**소스 파일**: `alphapulse/trading/data/short_collector.py`

| 항목 | 내용 |
|------|------|
| **데이터 소스** | `https://data.krx.co.kr/comm/srt/srtLoader/index.cmd?screenId=MDCSTAT300&isuCd={code}` |
| **수집 방식** | crawl4ai (`AsyncWebCrawler`, headless 브라우저) |
| **수집 항목** | 공매도 수량(`short_volume`), 공매도 잔고(`short_balance`) |
| **저장 테이블** | `short_interest` |
| **브라우저 설정** | `headless=True`, `wait_until="domcontentloaded"`, `delay_before_return_html=5.0` |
| **비고** | credit_balance는 이 소스에서 미제공 (0으로 저장), lending_balance는 short_balance로 매핑 |

### 3.5 WisereportCollector -- 기업분석 종합

**소스 파일**: `alphapulse/trading/data/wisereport_collector.py`

베이스 URL: `https://navercomp.wisereport.co.kr/v2/company`

#### 3.5.1 기업현황 (c1010001) -- 정적

| 항목 | 내용 |
|------|------|
| **URL** | `{WISEREPORT_BASE}/c1010001.aspx?cmp_cd={code}` |
| **수집 방식** | requests + BeautifulSoup (sync) |
| **수집 항목** | 시장정보 (시가총액, 베타, 외국인지분율, 52주 고/저, 수익률), 주요지표 (PER/PBR/PCR/EV_EBITDA/EPS/BPS/배당수익률, 추정 PER/EPS), 컨센서스 (목표주가, 투자의견, 추정기관수) |
| **저장 테이블** | `wisereport_data` |
| **전역 Rate Limiter** | `RateBucket(rate=8.0, capacity=8)` |
| **429 대응** | 3회 재시도, 지수 백오프 `(2^attempt) + random(0,1)초` |

#### 3.5.2 기업개요 (c1020001) -- 정적

| 항목 | 내용 |
|------|------|
| **URL** | `{WISEREPORT_BASE}/c1020001.aspx?cmp_cd={code}` |
| **수집 방식** | requests + BeautifulSoup (sync) |
| **수집 항목** | 매출구성(제품명/구성비), R&D비/비율, 종업원 수, 관계사 수 |
| **저장 테이블** | `company_overview` |

#### 3.5.3 투자지표 (c1040001) -- 동적 (crawl4ai)

| 항목 | 내용 |
|------|------|
| **URL** | `{WISEREPORT_BASE}/c1040001.aspx?cmp_cd={code}` |
| **수집 방식** | crawl4ai (`AsyncWebCrawler`, headless 브라우저) |
| **수집 항목** | 53개 투자지표 시계열 (수익성, 성장성, 안정성, 활동성) |
| **저장 테이블** | `investment_indicators` |
| **브라우저 설정** | `headless=True`, `wait_until="networkidle"`, `delay_before_return_html=3.0` |

#### 3.5.4 컨센서스 추정실적 (c1050001) -- 동적 (crawl4ai)

| 항목 | 내용 |
|------|------|
| **URL** | `{WISEREPORT_BASE}/c1050001.aspx?cmp_cd={code}` |
| **수집 방식** | crawl4ai (`AsyncWebCrawler`, headless 브라우저) |
| **수집 항목** | 추정 매출액, 영업이익, 순이익, EPS, PER |
| **저장 테이블** | `consensus_estimates` |
| **브라우저 설정** | `headless=True`, `wait_until="networkidle"`, `delay_before_return_html=3.0` |

#### 3.5.5 업종분석 (c1060001) -- 동적 (crawl4ai)

| 항목 | 내용 |
|------|------|
| **URL** | `{WISEREPORT_BASE}/c1060001.aspx?cmp_cd={code}` |
| **수집 방식** | crawl4ai (`AsyncWebCrawler`, headless 브라우저) |
| **수집 항목** | 업종 PER, 업종 PBR, 동종 비교 데이터 |
| **저장 테이블** | `sector_comparison` |
| **브라우저 설정** | `headless=True`, `wait_until="networkidle"`, `delay_before_return_html=3.0` |

#### 3.5.6 지분 현황 (c1070001) -- 정적

| 항목 | 내용 |
|------|------|
| **URL** | `{WISEREPORT_BASE}/c1070001.aspx?cmp_cd={code}` |
| **수집 방식** | requests + BeautifulSoup (sync) |
| **수집 항목** | 최대주주/지분율, 유동주식 비율, 지분 변동 이력 |
| **저장 테이블** | `shareholder_data` |

#### 3.5.7 증권사 리포트 (c1080001) -- 정적

| 항목 | 내용 |
|------|------|
| **URL** | `{WISEREPORT_BASE}/c1080001.aspx?cmp_cd={code}` |
| **수집 방식** | requests + BeautifulSoup (sync) |
| **수집 항목** | 리포트 일자, 제목, 애널리스트, 증권사, 투자의견, 목표주가 |
| **저장 테이블** | `analyst_reports` |

---

## 4. Rate Limiting 및 차단 방지

### 4.1 RateLimiter -- 순차 요청 제한

**소스 파일**: `alphapulse/trading/data/rate_limiter.py`

| 설정값 | 기본값 | 설명 |
|--------|--------|------|
| `delay` | 0.5초 | 요청 간 기본 딜레이 |
| `max_retries` | 3 | 최대 재시도 횟수 |
| `backoff_base` | 2.0 | 지수 백오프 기저 |

**재시도 대기 시간 계산식**:

```
wait = delay * (backoff_base ^ attempt) + random(0, 0.2)
```

- 1차 재시도: `0.5 * 2^0 + jitter` = 약 0.5~0.7초
- 2차 재시도: `0.5 * 2^1 + jitter` = 약 1.0~1.2초
- 3차 재시도: `0.5 * 2^2 + jitter` = 약 2.0~2.2초

두 가지 호출 모드 제공:
- `call(fn)`: 실패 시 예외 전파
- `call_safe(fn)`: 실패 시 `None` 반환 (수집 중단 방지)

### 4.2 RateBucket -- 전역 토큰 버킷

**소스 파일**: `alphapulse/trading/data/rate_bucket.py`

| 설정값 | 기본값 | 설명 |
|--------|--------|------|
| `rate` | 8.0 | 초당 토큰 보충 속도 (= 초당 최대 요청 수) |
| `capacity` | 8 (= rate) | 버킷 최대 용량 (버스트 허용량) |

**동작 원리**: 토큰 버킷 알고리즘
1. `acquire()` 호출 시 토큰 1개 소비
2. 토큰 부족 시 `(필요량 - 현재 토큰) / rate` 만큼 대기
3. `threading.Lock`으로 스레드 안전 보장

**적용 위치**:
- `FundamentalCollector`: 전역 `_RATE_BUCKET = RateBucket(rate=8.0, capacity=8)`
- `WisereportCollector`: 전역 `_WISEREPORT_BUCKET = RateBucket(rate=8.0, capacity=8)`
- `BulkCollector._collect_flow_parallel()`: 로컬 `RateBucket(rate=8.0, capacity=8)`

### 4.3 429 응답 지수 백오프

네이버 금융/wisereport의 HTTP 429 응답 시 다음 로직이 적용된다:

```
재시도 3회:
  attempt 0: 대기 = 2^0 + random(0,1) = 1~2초
  attempt 1: 대기 = 2^1 + random(0,1) = 2~3초
  attempt 2: 대기 = 2^2 + random(0,1) = 4~5초
```

적용 위치: `FundamentalCollector._safe_get()`, `wisereport_collector._safe_get()`, `BulkCollector._fetch_with_retry()`

### 4.4 병렬 수집 안전 설정

| 항목 | 설정값 | 설명 |
|------|--------|------|
| `max_workers` | 5 | 기본 동시 스레드 수 (안전) |
| 전역 rate bucket | 초당 8회 | 전 스레드 합산 요청 수 제한 |
| 페이지 간 jitter | `random(0.1, 0.3)초` | 수급 병렬 수집 시 페이지 간 랜덤 딜레이 |
| SQLite 쓰기 직렬화 | `threading.Lock` | 병렬 수집 시 DB 쓰기 충돌 방지 |

---

## 5. 체크포인트 및 재개

### 5.1 CollectionMetadata 기반 재개

**소스 파일**: `alphapulse/trading/data/collection_metadata.py`

`collection_metadata` 테이블에 시장/데이터 유형별 마지막 수집일을 기록한다.

**증분 업데이트 흐름**:

```
1. get_last_date(market, data_type) → 마지막 수집일 조회
2. 마지막 수집일 + 1일 ~ 오늘까지 데이터 수집
3. set_last_date(market, data_type, today) → 수집일 갱신
```

**스코프 구분**:
- `"KOSPI"`, `"KOSDAQ"`: BulkCollector가 시장별로 기록
- `"ALL"`: DataScheduler Stage 1 (전종목)
- `"TOP"`: DataScheduler Stage 2 (후보 종목)

### 5.2 ProgressTracker 체크포인트

**소스 파일**: `alphapulse/trading/data/progress_tracker.py`

대량 수집 중 중단 시 마지막 완료 종목부터 재개할 수 있다.

**체크포인트 파일**: `{checkpoint_dir}/.collection_checkpoint_{label}` (라벨은 소문자+언더스코어 변환)

**동작 흐름**:

```
1. get_resume_point(codes) → 체크포인트 이후 남은 종목 리스트 반환
2. 종목 수집 완료마다 checkpoint(code) → 파일에 마지막 종목코드 기록
3. 전체 완료 후 cleanup() → 체크포인트 파일 삭제
```

**파일 쓰기**: 원자적 교체 (`.tmp` 작성 후 `rename`) -- 중단 시 파일 손상 방지

**재개 비활성화**: CLI에서 `--no-resume` 플래그 사용

### 5.3 OHLCV/수급 최신 데이터 확인

BulkCollector는 수집 전에 이미 최신 데이터가 있는 종목을 일괄 조회하여 건너뛴다:

- `_get_ohlcv_up_to_date_codes()`: `SELECT code, MAX(date) FROM ohlcv GROUP BY code`
- `_get_flow_up_to_date_codes()`: `SELECT code, MAX(date) FROM stock_investor_flow GROUP BY code`

이미 오늘 날짜 데이터가 있는 종목은 수집을 건너뛰어 불필요한 네트워크 요청을 제거한다.

---

## 6. 자율 수집 스케줄러

### 6.1 2단계 수집 전략

**소스 파일**: `alphapulse/trading/data/scheduler.py`

DataScheduler는 수집을 2단계로 나누어 효율성과 깊이를 동시에 달성한다.

#### Stage 1: 전종목 기본 데이터 (sync, 빠름)

전종목을 대상으로 스크리닝에 필요한 기본 데이터를 수집한다.

| 데이터 유형 | 수집 주기 | 설명 | 수집기 |
|-------------|-----------|------|--------|
| `ohlcv` | 매일 (daily) | 일봉 + 수급 + 기본 재무 | BulkCollector.update() |
| `wisereport` | 매일 (daily) | 시가총액, 베타, 컨센서스 | WisereportCollector.collect_static_batch() |
| `reports` | 주간 (weekly, 7일) | 증권사 리포트 | WisereportCollector.collect_analyst_reports() |
| `shareholders` | 주간 (weekly, 7일) | 주주 지분 변동 | WisereportCollector.collect_shareholders() |
| `overview` | 분기 (quarterly, 90일) | 기업개요 (매출구성, R&D) | WisereportCollector.collect_overview() |

주간/분기 수집은 `_parallel_per_code(max_workers=5)`로 병렬 처리한다.

#### 스크리닝 -> 후보 종목 선정

Stage 1 완료 후 멀티팩터 스크리닝으로 투자 후보를 선정한다.

**가중치 (한국 시장 특화)**:
| 팩터 | 가중치 | 설명 |
|------|--------|------|
| `momentum` | 0.25 | 단기-중기 모멘텀 |
| `flow` | 0.25 | 외국인/기관 수급 |
| `value` | 0.20 | 가치 (PER/PBR) |
| `quality` | 0.15 | 재무 건전성 |
| `growth` | 0.10 | 성장성 |
| `volatility` | 0.05 | 변동성 |

**폴백**: 스크리닝 실패 시 또는 팩터 데이터 부족 시 (10종목 미만) 시가총액 상위 N종목으로 대체한다.

#### Stage 2: 후보 종목 상세 데이터 (crawl4ai, 느림)

스크리닝 상위 N종목에 대해 심층 데이터를 수집한다.

| 데이터 유형 | 수집 주기 | 설명 | 수집기 |
|-------------|-----------|------|--------|
| `short` | 매일 (daily) | 공매도 수량/잔고 (최근 30일) | ShortCollector.collect_async() |
| `financials` | 월간 (monthly, 30일) | 재무 시계열 (매출, ROE) | WisereportCollector.collect_financials() |
| `indicators` | 월간 (monthly, 30일) | 53개 투자지표 | WisereportCollector.collect_investment_indicators() |
| `consensus_est` | 월간 (monthly, 30일) | 추정실적 컨센서스 | WisereportCollector.collect_consensus() |
| `sector` | 월간 (monthly, 30일) | 업종분석 (동종비교) | WisereportCollector.collect_sector_analysis() |

### 6.2 수집 주기 판단 로직

`_should_collect(data_type, today, frequency)` 메서드로 판단한다:

```python
# 마지막 수집일로부터 경과일 계산
days_since = (today - last_collected).days

# 주기별 기준
daily:     days_since >= 1
weekly:    days_since >= 7
monthly:   days_since >= 30
quarterly: days_since >= 90
```

ALL 스코프와 TOP 스코프 모두 확인하여, 이미 오늘 수집했으면 건너뛴다.

### 6.3 기본 설정

| 파라미터 | 기본값 | 설명 |
|----------|--------|------|
| `top_n` | 100 | Stage 2 대상 종목 수 |
| `delay` | 0.3초 | wisereport 정적 수집 딜레이 |
| `markets` | ["KOSPI", "KOSDAQ"] | 대상 시장 |

---

## 7. CLI 명령어 레퍼런스

모든 데이터 수집 명령은 `ap trading data` 그룹 하위에 있다.

### 7.1 ap trading data collect

**전종목 초기 데이터 수집** (OHLCV + 재무 + 수급 + wisereport)

```bash
ap trading data collect [OPTIONS]
```

| 옵션 | 타입 | 기본값 | 설명 |
|------|------|--------|------|
| `--market` | TEXT | `ALL` | 시장 (KOSPI / KOSDAQ / ALL) |
| `--years` | INT | `3` | 수집 기간 (년) |
| `--delay` | FLOAT | `0.5` | 요청 간 딜레이 (초) |
| `--no-resume` | FLAG | - | 체크포인트 무시 (처음부터 재수집) |

**수집 순서** (5단계):
1. 종목 목록 수집 (네이버 금융)
2. OHLCV 수집 (pykrx 우선, 네이버 폴백)
3. 재무제표 수집 (네이버 금융, 병렬 5워커)
4. 수급 수집 (네이버 금융, 병렬 5워커)
5. wisereport 정적 수집 (병렬 5워커)

**사용 예시**:

```bash
# KOSPI + KOSDAQ 전종목 3년치 수집
ap trading data collect

# KOSPI만 5년치 수집, 딜레이 1초
ap trading data collect --market KOSPI --years 5 --delay 1.0

# 체크포인트 무시하고 처음부터
ap trading data collect --no-resume
```

### 7.2 ap trading data update

**증분 업데이트** (마지막 수집 이후 신규 데이터만)

```bash
ap trading data update [OPTIONS]
```

| 옵션 | 타입 | 기본값 | 설명 |
|------|------|--------|------|
| `--market` | TEXT | `ALL` | 시장 (KOSPI / KOSDAQ / ALL) |

**동작**: `collection_metadata`에서 마지막 수집일을 조회하고, 그 다음 날부터 오늘까지의 데이터만 수집한다. 미수집 상태면 자동으로 `collect_all`을 실행한다.

**사용 예시**:

```bash
# 전시장 증분 업데이트
ap trading data update

# KOSDAQ만 업데이트
ap trading data update --market KOSDAQ
```

### 7.3 ap trading data status

**데이터 수집 현황 조회**

```bash
ap trading data status
```

옵션 없음. 종목 수 (KOSPI/KOSDAQ/ETF 구분) 및 시장별/데이터 유형별 최종 수집일을 표시한다.

### 7.4 ap trading data schedule

**자율 데이터 수집** (2단계: 전종목 기본 -> 후보 상세)

```bash
ap trading data schedule [OPTIONS]
```

| 옵션 | 타입 | 기본값 | 설명 |
|------|------|--------|------|
| `--market` | TEXT | `ALL` | 시장 (KOSPI / KOSDAQ / ALL) |
| `--top-n` | INT | `100` | Stage 2 대상 종목 수 |
| `--force` | FLAG | - | 주기 무시하고 전체 실행 |

**사용 예시**:

```bash
# 자율 수집 (주기 자동 판단)
ap trading data schedule

# 상위 50종목만 상세 수집
ap trading data schedule --top-n 50

# 주기 무시하고 전체 재수집
ap trading data schedule --force
```

### 7.5 ap trading data schedule-status

**수집 스케줄 현황 조회**

```bash
ap trading data schedule-status
```

옵션 없음. 각 데이터 유형의 수집 주기, 단계(Stage 1/2), 마지막 수집일, 업데이트 필요 여부를 표시한다.

### 7.6 ap trading data collect-financials

**wisereport 정적 재무 데이터 수집** (시장정보, 주요지표, 컨센서스)

```bash
ap trading data collect-financials [OPTIONS]
```

| 옵션 | 타입 | 기본값 | 설명 |
|------|------|--------|------|
| `--code` | TEXT | - | 종목코드 (단일 종목) |
| `--market` | TEXT | - | 시장 (KOSPI / KOSDAQ) |
| `--top` | INT | `50` | 상위 N종목 (시가총액 기준, `--market` 사용 시) |

**사용 예시**:

```bash
# 삼성전자 단일 수집
ap trading data collect-financials --code 005930

# KOSPI 시총 상위 100종목
ap trading data collect-financials --market KOSPI --top 100
```

### 7.7 ap trading data collect-wisereport

**wisereport 전체 탭 데이터 수집** (정적 4탭 + 선택적 crawl4ai 4탭)

```bash
ap trading data collect-wisereport [OPTIONS]
```

| 옵션 | 타입 | 기본값 | 설명 |
|------|------|--------|------|
| `--code` | TEXT | - | 종목코드 (단일 종목) |
| `--market` | TEXT | - | 시장 (KOSPI / KOSDAQ) |
| `--top` | INT | `50` | 상위 N종목 |
| `--full` | FLAG | - | crawl4ai 포함 전체 수집 (느림) |

**수집 범위**:
- **정적** (기본): 기업현황 + 기업개요 + 주주현황 + 증권사 리포트 (4탭)
- **동적** (`--full`): 투자지표 + 컨센서스 + 업종분석 + 재무 시계열 (4탭 추가)

**사용 예시**:

```bash
# 삼성전자 정적 수집
ap trading data collect-wisereport --code 005930

# 삼성전자 전체 수집 (crawl4ai 포함)
ap trading data collect-wisereport --code 005930 --full

# KOSPI 상위 30종목 정적 수집
ap trading data collect-wisereport --market KOSPI --top 30

# KOSPI 상위 30종목 전체 수집 (시간 소요 큼)
ap trading data collect-wisereport --market KOSPI --top 30 --full
```

### 7.8 ap trading data collect-short

**공매도 데이터 수집** (KRX crawl4ai 기반, 최근 30일)

```bash
ap trading data collect-short [OPTIONS]
```

| 옵션 | 타입 | 기본값 | 설명 |
|------|------|--------|------|
| `--code` | TEXT | - | 종목코드 (단일 종목) |
| `--market` | TEXT | - | 시장 (KOSPI / KOSDAQ) |
| `--top` | INT | `50` | 상위 N종목 |

**수집 기간**: 현재일 기준 30일 전 ~ 오늘

**사용 예시**:

```bash
# 삼성전자 공매도 수집
ap trading data collect-short --code 005930

# KOSDAQ 시총 상위 50종목
ap trading data collect-short --market KOSDAQ --top 50
```

---

## 8. 운영 팁

### 8.1 초기 수집 소요 시간

전종목 초기 수집(`ap trading data collect`)의 예상 소요 시간:

| 단계 | 종목 수 | 예상 시간 | 비고 |
|------|---------|-----------|------|
| 종목 목록 | - | 약 1분 | 네이버 금융 50페이지 x 2시장 |
| OHLCV (3년) | 약 2,500종목 | 약 30~60분 | pykrx 1회 호출/종목, 이미 최신이면 skip |
| 재무제표 | 약 2,500종목 | 약 10~20분 | 병렬 5워커, rate=8/s |
| 수급 | 약 2,500종목 | 약 30~60분 | 병렬 5워커, rate=8/s |
| wisereport | 약 2,500종목 | 약 10~20분 | 병렬 5워커, rate=8/s |
| **전체** | - | **약 1.5~3시간** | 네트워크 상태에 따라 변동 |

### 8.2 일일 업데이트 권장 사항

- **매일**: `ap trading data schedule` 실행 (주기 자동 판단)
- **수동 업데이트**: `ap trading data update` (OHLCV/재무/수급만 증분)
- **업데이트 소요 시간**: Stage 1 약 15~30분, Stage 2 (100종목) 약 30~60분
- **권장 실행 시점**: 장 마감 후 (15:30 이후) 또는 야간

### 8.3 장애 대응

#### 네이버 금융 차단 (429)

**증상**: 로그에 `429 수신. X.X초 대기` 반복

**대응**:
1. 자동 복구: 지수 백오프 재시도 (최대 3회)가 내장되어 있다
2. 수동 조치: `--delay` 값을 높인다 (예: `--delay 1.0`)
3. 과도한 차단 시: 30분~1시간 후 재시도

#### 수집 중단 후 재개

**증상**: 네트워크 오류 또는 프로세스 종료로 수집 중단

**대응**:
1. 동일 명령 재실행 -- ProgressTracker 체크포인트에서 자동 재개
2. 체크포인트 무시: `--no-resume` 플래그 사용
3. 체크포인트 파일 위치: `{DB_DIR}/.collection_checkpoint_*`

#### crawl4ai 수집 실패

**증상**: 공매도/투자지표/컨센서스/업종분석 수집 0건

**대응**:
1. crawl4ai 설치 확인: `pip install crawl4ai`
2. Chrome/Chromium 설치 확인 (headless 브라우저 필요)
3. KRX/wisereport 사이트 접속 가능 여부 확인
4. `--debug` 플래그로 상세 로그 확인: `ap --debug trading data collect-short --code 005930`

#### SQLite 잠금 오류

**증상**: `database is locked` 오류

**대응**:
1. 동시 실행 중인 다른 수집 프로세스 확인 및 종료
2. 병렬 수집에서 SQLite 쓰기는 `threading.Lock`으로 직렬화되지만, 별도 프로세스 간에는 충돌 가능
3. 한 번에 하나의 수집 프로세스만 실행 권장

### 8.4 데이터 검증

수집 후 상태 확인:

```bash
# 전체 현황 조회
ap trading data status

# 스케줄 현황 조회 (주기별 업데이트 필요 여부)
ap trading data schedule-status

# 디버그 모드로 단일 종목 확인
ap --debug trading data collect-financials --code 005930
```

### 8.5 디스크 사용량

SQLite 데이터베이스 예상 크기 (전종목 기준):

| 데이터 | 대략적 크기 |
|--------|------------|
| OHLCV (3년, 약 2,500종목) | 약 200~400MB |
| 재무/수급/wisereport | 약 50~100MB |
| 공매도/투자지표 (100종목) | 약 10~30MB |
| **합계** | **약 300~500MB** |

### 8.6 최근 거래일 판단

BulkCollector는 삼성전자(005930) 일별 시세 페이지에서 최근 거래일을 자동 감지한다. 감지 실패 시 어제 날짜로 폴백한다.

```
소스: https://finance.naver.com/item/sise_day.naver?code=005930&page=1
폴백: datetime.now() - timedelta(days=1)
```
