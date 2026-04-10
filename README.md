# AlphaPulse

**AI 기반 투자 인텔리전스 + 자동 매매 플랫폼**

한국 주식 시장을 위한 엔드투엔드 투자 시스템입니다. 정량/정성 시황 분석, AI 종합 판단, 피드백 학습, 팩터 기반 스크리닝, 백테스트, 모의투자/실매매까지 **한 파이프라인**으로 통합합니다.

---

## 주요 기능

### 1. 시황 분석 (Market Intelligence)

- **Market Pulse Score** — 11개 정량 지표 가중합산 (-100 ~ +100)
- **Content Intelligence** — 블로그/채널 실시간 멀티에이전트 분석
- **AI 종합 판단** — 정량 + 정성 + 피드백 컨텍스트를 LLM이 통합 해석
- **피드백 학습** — 시그널 적중률 추적 + 사후 분석 → 다음 판단에 반영
- **일일 브리핑** — 매일 08:30 텔레그램 자동 발송

### 2. 자동 매매 시스템 (Trading System)

- **20개 팩터 스크리닝** — 모멘텀/밸류/퀄리티/수급/역발상/변동성 멀티팩터 랭킹
- **4개 전략** — TopDownETF, Momentum, Value, QualityMomentum + AI 종합 판단
- **포트폴리오 최적화** — mean-variance, risk parity, min variance (scipy)
- **리스크 엔진** — VaR/CVaR, 드로다운 자동 디레버리징, 스트레스 테스트, 상관관계 분석
- **백테스트** — 22개 성과 지표, look-ahead bias 방지, 실매매와 동일 코드 경로
- **한국투자증권 API** — 모의투자 + 실매매 (이중 안전장치)
- **자율 수집 스케줄러** — 2단계 전략 (전종목 기본 → 후보 상세)

### 3. 데이터 수집 (Data Infrastructure)

- **네이버 금융 스크래핑** + **pykrx** (개별 OHLCV) + **crawl4ai** (JS 렌더링 페이지)
- **공매도 데이터** — KRX 페이지 crawl4ai 렌더링
- **wisereport 심층 재무** — 기업현황/기업개요/재무/투자지표/컨센서스/업종분석/주주현황/증권사 리포트
- **차단 방지** — 전역 rate bucket (8 req/s), 429 지수 백오프, 랜덤 jitter
- **병렬 수집** — ThreadPoolExecutor 5 workers + 스레드 안전 SQLite

---

## 설치

### 전제 조건

- Python 3.11+
- Chromium (crawl4ai용): `crawl4ai-setup` 실행 후 한 번 세팅
- Google Gemini API 키 ([AI Studio](https://aistudio.google.com))
- Telegram Bot 토큰 ([@BotFather](https://t.me/BotFather))
- 한국투자증권 Open API (매매 기능 사용 시)

### 설치 방법

```bash
git clone https://github.com/GwangSoo-Ko/alpha-pulse.git && cd alpha-pulse
cp .env.example .env
# .env 파일에 API 키 입력

pip install -e ".[dev]"
ap --version
```

---

## 빠른 시작

### 최초 실행 (시황 분석)

```bash
ap market pulse           # Market Pulse Score + 11개 지표
ap briefing --no-telegram  # 정량+정성 종합 브리핑 (터미널)
```

### 최초 실행 (자동 매매)

```bash
# 1. 전종목 데이터 수집 (3년치, 약 4시간)
ap trading data collect --market ALL --years 3

# 2. 팩터 스크리닝 확인
ap trading screen --market KOSPI --factor momentum --top 20

# 3. 백테스트
ap trading backtest --strategy momentum --start 20220101 --end 20251231

# 4. 모의투자 (한투 Open API 키 필요)
ap trading run --mode paper
```

---

## 사용법

### 정량 분석 (Market Pulse)

```bash
ap market pulse                          # 종합 시황 (Market Pulse Score)
ap market pulse --period weekly          # 주간 분석
ap market investor                       # 투자자 수급 상세 (KOSPI/KOSDAQ)
ap market program                        # 프로그램 매매
ap market sector                         # 업종별 동향
ap market macro                          # 환율/금리/글로벌
ap market fund                           # 증시 자금
ap market report --output report.html    # HTML 리포트
ap market history --days 30              # 과거 이력
```

### 정성 분석 (Content Intelligence)

```bash
ap content monitor                       # 블로그 + 채널 감지
ap content monitor --daemon              # 데몬 모드 (10분 간격)
ap content monitor --force-latest 3      # 최근 3개 강제 처리
ap content test-telegram                 # 텔레그램 연결 테스트
```

### 일일 브리핑

```bash
ap briefing                              # 피드백 + 정량 + 정성 → 텔레그램
ap briefing --no-telegram                # 터미널 출력만
ap briefing --daemon --time 08:00        # 매일 08:00 자동 실행
ap commentary                            # AI 시장 해설만 생성
```

### 피드백 시스템

```bash
ap feedback evaluate                     # 미확정 시그널 평가
ap feedback report --days 30             # 적중률 리포트
ap feedback indicators --days 30         # 지표별 적중률 순위
ap feedback history --days 7             # 시그널 vs 실제 결과
ap feedback analyze --date 20260403      # 특정 날짜 사후 분석
```

### 자동 매매 시스템

#### 데이터 수집

```bash
# 전종목 기본 데이터 (최초 1회, 3년치)
ap trading data collect --market ALL --years 3

# 증분 업데이트 (매일)
ap trading data update

# 현황 조회
ap trading data status

# 자율 수집 (2단계 전략, 주기 기반 자동 판단)
ap trading data schedule                 # 정기 실행
ap trading data schedule --force         # 전체 강제 수집
ap trading data schedule-status          # 스케줄 현황

# wisereport 심층 수집
ap trading data collect-wisereport --code 005930        # 단일 종목
ap trading data collect-wisereport --market KOSPI --top 50
ap trading data collect-wisereport --code 005930 --full # crawl4ai 포함

# 공매도 수집 (KRX crawl4ai)
ap trading data collect-short --code 005930
ap trading data collect-short --market KOSPI --top 50
```

#### 스크리닝 및 분석

```bash
# 팩터 스크리닝
ap trading screen --market KOSPI --factor momentum --top 20
ap trading screen --market KOSPI --factor value --top 20
ap trading screen --factor balanced --top 30

# 백테스트
ap trading backtest --strategy momentum --start 20200101 --end 20251231
```

#### 매매 실행

```bash
# 모의투자
ap trading run --mode paper
ap trading run --mode paper --daemon

# 실매매 (이중 안전장치 필요)
ap trading run --mode live

# 포트폴리오
ap trading portfolio show
ap trading portfolio history --days 30
ap trading portfolio attribution --days 30

# 리스크
ap trading risk report
ap trading risk stress
ap trading risk limits

# 시스템
ap trading status
ap trading reconcile                     # DB ↔ 증권사 대사
```

> 상세 가이드: [docs/trading-system-guide.md](docs/trading-system-guide.md)

### 캐시 관리

```bash
ap cache clear                           # 시장 데이터 캐시 초기화
```

---

## 환경 변수

`.env` 파일에 설정합니다. 자세한 내용은 `.env.example` 참조.

### 필수

| 변수 | 용도 |
|------|------|
| `GEMINI_API_KEY` | Google AI API (멀티에이전트 + 시장 해설) |
| `TELEGRAM_BOT_TOKEN` | 텔레그램 봇 토큰 |
| `TELEGRAM_CHAT_ID` | 브리핑 수신 채팅 ID |

### 선택

| 변수 | 기본값 | 용도 |
|------|--------|------|
| `FRED_API_KEY` | — | FRED API (미국 경제 지표) |
| `APP_ENV` | `development` | `production`이면 고성능 AI 모델 사용 |
| `BRIEFING_TIME` | `08:30` | 일일 브리핑 발송 시간 |
| `CHECK_INTERVAL` | `600` | 콘텐츠 모니터링 주기 (초) |
| `FEEDBACK_ENABLED` | `true` | 피드백 시스템 on/off |
| `FEEDBACK_LOOKBACK_DAYS` | `30` | 적중률 계산 기간 |

### Trading System

| 변수 | 기본값 | 용도 |
|------|--------|------|
| `KIS_APP_KEY` | — | 한국투자증권 앱 키 |
| `KIS_APP_SECRET` | — | 한국투자증권 앱 시크릿 |
| `KIS_ACCOUNT_NO` | — | 계좌번호 |
| `KIS_IS_PAPER` | `true` | `true`: 모의투자, `false`: 실전 |
| `LIVE_TRADING_ENABLED` | `false` | 실매매 최종 스위치 (이중 안전장치) |
| `MAX_DAILY_ORDERS` | `50` | 일일 주문 한도 |
| `MAX_DAILY_AMOUNT` | `50000000` | 일일 금액 한도 (원) |
| `STRATEGY_ALLOCATIONS` | `{"topdown_etf":0.3,"momentum":0.4,"value":0.3}` | 전략별 자금 배분 (JSON) |

---

## 아키텍처

```
alphapulse/
├── core/              # 공유 인프라 (config, storage, notifier, constants)
├── market/            # 정량 분석 (11개 지표 → Market Pulse Score)
│   ├── collectors/    # pykrx, FDR, KRX, FRED, investing.com
│   ├── analyzers/     # 수급, 프로그램, 업종, 자금, 매크로
│   ├── engine/        # SignalEngine (가중합산 → -100~+100)
│   └── reporters/     # 터미널 + HTML 리포트
├── content/           # 정성 분석 (블로그 + 채널 멀티에이전트 AI)
│   └── agents/        # TopicClassifier → 5 Specialists → SeniorAnalyst
├── briefing/          # 일일 브리핑 통합
├── agents/            # 브리핑 AI 에이전트 (Commentary + Synthesis)
├── feedback/          # 피드백 시스템 (적중률 + 사후 분석)
│   └── agents/        # 사후 분석 멀티에이전트 (4종)
└── trading/           # 자동 매매 시스템
    ├── core/          # 데이터 모델, Protocol, 캘린더, 비용 모델, 감사 추적
    ├── data/          # 데이터 수집 + 저장 + 스케줄러 + rate bucket
    │   ├── stock_collector.py       # pykrx OHLCV
    │   ├── flow_collector.py        # 네이버 frgn.naver 수급
    │   ├── fundamental_collector.py # 네이버 item/main.naver PER/PBR
    │   ├── wisereport_collector.py  # wisereport 8탭 전체
    │   ├── short_collector.py       # KRX 공매도 (crawl4ai)
    │   ├── bulk_collector.py        # 전종목 병렬 수집
    │   ├── scheduler.py             # 2단계 자율 수집
    │   └── rate_bucket.py           # 토큰 버킷 rate limiter
    ├── screening/     # 20개 팩터 계산, 필터, 멀티팩터 랭킹
    ├── strategy/      # 4개 전략 + AI Synthesizer
    ├── portfolio/     # 포지션 사이징, 최적화, 리밸런싱, 성과 귀속
    ├── risk/          # VaR/CVaR, 드로다운, 스트레스 테스트, 상관관계
    ├── backtest/      # 백테스트 엔진 (22개 지표, look-ahead 방지)
    ├── broker/        # 한국투자증권 API + 안전장치
    └── orchestrator/  # 5-phase 파이프라인, 스케줄러, 알림, 복구
```

### 11개 Market Pulse 지표

| 지표 | 가중치 | 데이터 소스 |
|------|--------|-----------|
| 외국인+기관 수급 | 18% | pykrx, 네이버 금융 |
| 선물 베이시스 | 5% | investing.com |
| 선물 수급 | 7% | 네이버 금융 (현선물 교차검증) |
| 프로그램 비차익 | 8% | KRX |
| 업종 모멘텀 | 10% | pykrx |
| 환율 (USD/KRW) | 10% | FDR |
| V-KOSPI | 10% | KRX, investing.com |
| 한미 금리차 | 5% | FRED, FDR |
| 글로벌 시장 | 13% | FDR (S&P500, NASDAQ, N225, SSEC) |
| 증시 자금 | 5% | KRX (예탁금, 신용잔고) |
| ADR + 거래량 | 9% | 네이버 금융 |

### 20개 팩터 (Trading System)

| 카테고리 | 팩터 |
|---------|------|
| 모멘텀 (5) | momentum_1m, 3m, 6m, 12m, high_52w_proximity |
| 밸류 (4) | value_per, value_pbr, value_psr, dividend_yield |
| 퀄리티 (3) | quality_roe, profit_growth, debt_ratio |
| 수급 (3) | flow_foreign, flow_institutional, flow_trend |
| 역발상 (2) | short_decrease, credit_change |
| 변동성 (3) | volatility, beta, downside_vol |

### 데이터 흐름

```
[08:00] 피드백 수집 → 사후 분석 멀티에이전트 → feedback_context
[08:00] SignalEngine → 11개 지표 → Market Pulse Score
[실시간] BlogMonitor → 멀티에이전트 분석
[08:30] BriefingOrchestrator → Commentary + Synthesis → 텔레그램

[Trading System] (자율 스케줄러)
  Phase 1: 전종목 기본 데이터 수집 (OHLCV, 수급, 재무, wisereport)
  Phase 2: 스크리닝으로 투자 후보 선정 (팩터 랭킹)
  Phase 3: 후보 상세 수집 (공매도, 재무 시계열, 투자지표)
  Phase 4: 전략별 시그널 + AI 종합 판단
  Phase 5: 포트폴리오 목표 → 리스크 검증 → 주문 생성
  Phase 6: 브로커 제출 (Paper/Live)
  Phase 7: 스냅샷 + 리스크 리포트 + 텔레그램 알림
```

---

## 테스트

```bash
pytest tests/ -v                     # 전체 (824개)
pytest tests/market/ -v              # 정량 분석
pytest tests/content/ -v             # 정성 분석
pytest tests/briefing/ -v            # 브리핑
pytest tests/agents/ -v              # 브리핑 AI 에이전트
pytest tests/feedback/ -v            # 피드백 시스템
pytest tests/trading/ -v             # 자동 매매 시스템 (~470개)
pytest tests/ --cov=alphapulse       # 커버리지 리포트
```

---

## 기술 스택

| 범주 | 패키지 |
|------|--------|
| 한국 시장 데이터 | pykrx, finance-datareader, beautifulsoup4 |
| 미국 경제 데이터 | fredapi |
| 웹 크롤링 | crawl4ai, httpx, requests, feedparser |
| AI 멀티에이전트 | google-adk ~= 1.27.2 (Gemini API) |
| 텔레그램 | httpx (Bot API), telethon (채널 모니터) |
| CLI | click |
| 터미널 UI | rich |
| 리포트 | jinja2, matplotlib |
| 저장소 | SQLite (cache, history, feedback, trading) |
| 포트폴리오 최적화 | scipy, numpy |
| 증권사 API | 한국투자증권 Open API (requests) |
| 병렬 처리 | ThreadPoolExecutor, threading.Lock |

---

## 데이터베이스 구조

### 기존 (`core/storage/`)

| DB | 용도 |
|----|------|
| `cache.db` | API 캐시 (TTL 기반) |
| `history.db` | Market Pulse Score 이력 |
| `feedback.db` | 시그널 적중률 + 사후 분석 |

### Trading System (`trading/data/`)

| 테이블 | 용도 |
|-------|------|
| `stocks` | 종목 기본정보 |
| `ohlcv` | 일봉 데이터 |
| `fundamentals` | PER, PBR, ROE, 배당 |
| `stock_investor_flow` | 외국인/기관 순매매 |
| `short_interest` | 공매도/대차잔고 |
| `etf_info` | ETF 정보 |
| `wisereport_data` | wisereport 심층 재무 |
| `company_overview` | 매출구성, R&D, 관계사 |
| `investment_indicators` | 53개 투자지표 시계열 |
| `consensus_estimates` | 추정실적 컨센서스 |
| `sector_comparison` | 업종 내 PER/PBR 비교 |
| `shareholder_data` | 주주 구성, 지분 변동 |
| `analyst_reports` | 증권사 리포트 |
| `collection_metadata` | 수집일 추적 |

---

## 데이터 수집 최적화

### 병렬 수집 + 차단 방지

- **전역 rate bucket** (토큰 버킷 알고리즘): 초당 8회 제한
- **max_workers=5**: ThreadPoolExecutor 동시 요청 수 제한
- **429 지수 백오프**: 재시도 2s → 4s → 8s (jitter 포함)
- **랜덤 jitter**: 페이지 간 0.1-0.3초 랜덤

### 2단계 자율 수집 전략

Stage 1 (전종목, sync): OHLCV, 수급, 재무, wisereport 정적
Stage 2 (후보 N종목, crawl4ai): 공매도, 재무 시계열, 투자지표, 컨센서스, 업종

| 주기 | Stage | 데이터 | 소요 시간 |
|------|-------|--------|----------|
| 매일 | 1 | OHLCV + 수급 + 기본재무 + wisereport | ~3시간 (전종목) |
| 매일 | 2 | 공매도 | ~8분 (후보 100종목) |
| 주간 | 1 | 증권사 리포트, 주주 지분 | ~10분 |
| 월간 | 2 | 재무 시계열, 투자지표, 컨센서스, 업종 | ~10분 |
| 분기 | 1 | 기업개요 | ~5분 |

---

## 안전장치 (Trading System)

### 이중 잠금 (실매매)

```
KIS_IS_PAPER=false                # 한투 API 실전 모드
LIVE_TRADING_ENABLED=true         # 실매매 최종 스위치
→ KISBroker.__init__() → check_live_allowed() → 터미널 사용자 확인
```

### 일일 한도

- `MAX_DAILY_ORDERS`: 일일 주문 횟수
- `MAX_DAILY_AMOUNT`: 일일 거래 금액

### 리스크 하드 리밋 (AI/전략 오버라이드 불가)

- 종목당 최대 비중 10%
- 섹터당 최대 비중 30%
- 레버리지 ETF 최대 20%
- 드로다운 -10% (soft) → 신규 매수 중단
- 드로다운 -15% (hard) → 포지션 50% 자동 축소
- 일간 손실 -3% → 당일 매매 중단
- 최소 현금 5% 유지

### 장애 복구

- `ap trading reconcile`: DB ↔ 증권사 잔고 대사
- `ap trading status`: 시스템 헬스체크

---

## 로드맵

| 버전 | 내용 |
|------|------|
| **v1.0** | 일일 자동 브리핑 (정량+정성+AI 종합) |
| **v1.1** | 피드백 시스템 (적중률 + 사후 분석 + AI 자동 반영) |
| **v2.0** | 자동 매매 시스템 (백테스트 + 모의투자 + 실매매) |
| **v2.1 (현재)** | 심층 데이터 수집 (wisereport 8탭, 공매도, 자율 스케줄러) |
| v2.5 | 실매매 최적화, 실시간 시세, 웹소켓 모니터링 |
| v3.0 | 웹 대시보드 (Streamlit/Gradio), 실시간 갱신 |

---

## 문서

- **[docs/trading-system-guide.md](docs/trading-system-guide.md)** — Trading System 전체 가이드
- **[CLAUDE.md](CLAUDE.md)** — 개발 컨벤션 (Claude Code 작업 규칙)
- **[AlphaPulse-PRD.md](AlphaPulse-PRD.md)** — 초기 제품 요구사항

---

## 라이선스

MIT License
