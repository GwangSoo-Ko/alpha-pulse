# AlphaPulse

**AI 기반 투자 인텔리전스 플랫폼** — 정량 분석(Market Pulse)과 정성 분석(Content Intelligence)을 통합하여 일일 투자 브리핑을 자동 생성하고, 피드백 시스템으로 매일 스스로 학습합니다.

## 리포트 3종 체계

| 리포트 | 트리거 | 내용 |
|--------|--------|------|
| **정량 리포트** | 매일 장 전 (08:00) | Market Pulse Score + 11개 지표 + AI 코멘트 + 전일 시그널 결과 |
| **정성 리포트** | 블로그/채널 감지 시 | 멀티에이전트 AI 분석 (5개 분야 전문가 → 시니어 종합) |
| **종합 리포트** | 매일 장 전 (08:30) | 정량+정성을 AI가 맥락 기반 종합 판단 (피드백 컨텍스트 반영) |

## 설치

### 전제 조건

- Python 3.11+
- Chromium (Crawl4AI용): `crawl4ai-setup`
- Google Gemini API 키 ([AI Studio](https://aistudio.google.com))
- Telegram Bot 토큰 ([@BotFather](https://t.me/BotFather))

### 설치 방법

```bash
git clone https://github.com/GwangSoo-Ko/alpha-pulse.git && cd alpha-pulse
cp .env.example .env
# .env 파일에 API 키 입력

pip install -e ".[dev]"
ap --version
```

## 사용법

### 정량 분석 (Market Pulse)

```bash
ap market pulse                      # 종합 시황 (Market Pulse Score, 11개 지표)
ap market pulse --date 2026-04-03    # 특정 날짜
ap market pulse --period weekly      # 주간 분석
ap market investor                   # 투자자 수급 상세 (KOSPI/KOSDAQ 분리)
ap market program                    # 프로그램 매매
ap market sector                     # 업종별 동향
ap market macro                      # 매크로 환경 (환율/금리/글로벌)
ap market fund                       # 증시 자금
ap market report --output report.html  # HTML 리포트
ap market history --days 30          # 과거 이력
```

### 정성 분석 (Content Intelligence)

```bash
ap content monitor                   # 블로그 새 글 감지 + AI 분석
ap content monitor --daemon          # 데몬 모드 (10분 간격)
ap content monitor --force-latest 3  # 최근 3개 강제 처리
ap content monitor --no-telegram     # 텔레그램 미전송
ap content monitor --channel-only    # 채널만 모니터링
ap content test-telegram             # 텔레그램 연결 테스트
ap content list-channels             # 구독 채널 목록
```

### 일일 브리핑

```bash
ap briefing                          # 피드백 수집 + 정량 + AI 종합 → 텔레그램
ap briefing --no-telegram            # 터미널 출력만
ap briefing --daemon --time 08:00    # 매일 08:00 자동 실행
ap commentary                        # AI 시장 해설만 생성
ap commentary --date 2026-04-03      # 과거 날짜 해설
```

### 피드백 시스템

```bash
ap feedback evaluate                 # 미확정 시그널 평가 (시장 결과 수집 + 적중 판정)
ap feedback report --days 30         # 적중률 리포트 (1일/3일/5일)
ap feedback indicators --days 30     # 지표별 적중률 순위
ap feedback history --days 7         # 시그널 vs 실제 결과 테이블
ap feedback analyze --date 2026-04-03  # 특정 날짜 사후 분석
```

### 캐시 관리

```bash
ap cache clear                       # 시장 데이터 캐시 초기화
```

## 환경 변수

`.env` 파일에 설정합니다. 자세한 내용은 [.env.example](.env.example) 참조.

### 필수

| 변수 | 용도 |
|------|------|
| `GEMINI_API_KEY` | Google AI API (멀티에이전트 + 시장 해설) |
| `TELEGRAM_BOT_TOKEN` | 텔레그램 봇 토큰 |
| `TELEGRAM_CHAT_ID` | 브리핑 수신 채팅 ID |

### 주요 선택

| 변수 | 기본값 | 용도 |
|------|--------|------|
| `FRED_API_KEY` | — | FRED API (미국 경제 지표) |
| `APP_ENV` | `development` | `production`이면 고성능 AI 모델 사용 |
| `BRIEFING_TIME` | `08:30` | 일일 브리핑 발송 시간 |
| `CHECK_INTERVAL` | `600` | 콘텐츠 모니터링 주기 (초) |
| `FEEDBACK_ENABLED` | `true` | 피드백 시스템 on/off |
| `FEEDBACK_LOOKBACK_DAYS` | `30` | 적중률 계산 기간 |
| `FEEDBACK_NEWS_ENABLED` | `true` | 장 후 뉴스 수집 on/off |
| `FEEDBACK_NEWS_COUNT` | `10` | 수집할 뉴스 기사 수 |

## 아키텍처

```
alphapulse/
├── core/           # 공유 인프라 (config, storage, notifier, constants)
│   └── storage/    #   DataCache, PulseHistory, FeedbackStore (SQLite)
├── market/         # 정량 분석 파이프라인 (sync)
│   ├── collectors/ #   5개 데이터 수집기 (pykrx, FDR, KRX, FRED, investing)
│   ├── analyzers/  #   5개 분석기 (수급, 프로그램, 업종, 자금, 매크로)
│   ├── engine/     #   SignalEngine (11개 지표 가중합산 → -100~+100 점수)
│   └── reporters/  #   터미널 + HTML 리포트
├── content/        # 정성 분석 파이프라인 (async)
│   ├── agents/     #   멀티에이전트 (TopicClassifier → 5 Specialists → SeniorAnalyst)
│   ├── detector.py #   RSS 새 글 감지
│   ├── crawler.py  #   Crawl4AI 크롤링
│   └── monitor.py  #   BlogMonitor 오케스트레이터
├── briefing/       # 일일 브리핑 통합
│   ├── orchestrator.py  # 피드백 수집 → 정량+정성+AI → 포맷 → 전송
│   ├── formatter.py     # 텔레그램 HTML 포맷 (매일 결과 + 주간 요약)
│   └── scheduler.py     # 데몬 모드 스케줄러
├── agents/         # 브리핑 AI 에이전트
│   ├── commentary.py    # MarketCommentaryAgent (정량 해설, 피드백 인지)
│   └── synthesis.py     # SeniorSynthesisAgent (종합 판단, 피드백 인지)
└── feedback/       # 피드백 시스템 (장 후 검증 + 학습)
    ├── collector.py      # 시장 결과 수집 + 수익률 계산 + 적중 판정
    ├── evaluator.py      # 적중률, 상관계수, 지표별 정확도
    ├── summarizer.py     # AI 프롬프트 주입용 요약 + 텔레그램 메시지
    ├── news_collector.py # 네이버 금융 뉴스 크롤링 (장 후 시황)
    └── agents/           # 사후 분석 멀티에이전트
        ├── blind_spot.py         # 시스템 사각지대 식별
        ├── prediction_review.py  # 예측 복기 (지표별 적중/미적중 원인)
        ├── external_factor.py    # 외부 변수 식별 (정책/지정학/이벤트)
        └── senior_feedback.py    # 종합 피드백 + 시스템 개선 제안
```

### 11개 지표 (Market Pulse Score)

| 지표 | 가중치 | 데이터 소스 |
|------|--------|------------|
| 외국인+기관 수급 | 18% | pykrx, 네이버 금융 (KOSPI/KOSDAQ 분리) |
| 선물 베이시스 | 5% | investing.com |
| 선물 수급 | 7% | 네이버 금융 (sosok=03, 현선물 교차검증) |
| 프로그램 비차익 | 8% | KRX |
| 업종 모멘텀 | 10% | pykrx |
| 환율 (USD/KRW) | 10% | FDR |
| V-KOSPI | 10% | KRX, investing.com |
| 한미 금리차 | 5% | FRED, FDR |
| 글로벌 시장 | 13% | FDR (S&P500, NASDAQ, N225, SSEC) |
| 증시 자금 | 5% | KRX (예탁금, 신용잔고) |
| ADR + 거래량 | 9% | 네이버 금융 |

### 데이터 흐름

```
[08:00] 피드백 수집
          ├── 전일 KOSPI/KOSDAQ 결과 수집 (FeedbackCollector)
          ├── 과거 시그널 1d/3d/5d 적중 판정
          ├── 네이버 뉴스 크롤링 (NewsCollector)
          └── 사후 분석 멀티에이전트 (BlindSpot + PredictionReview + ExternalFactor → Senior)
                    ↓ feedback_context
[08:00] SignalEngine → 11개 지표 수집/분석 → Market Pulse Score
                    ↓
[실시간] BlogMonitor → RSS/채널 감지 → AI 멀티에이전트 분석
                    ↓
[08:30] BriefingOrchestrator
          ├── 정량 데이터 + 전일 시그널 결과 한 줄
          ├── 정성 요약 (최근 24시간 reports/)
          ├── MarketCommentaryAgent (피드백 인지 정량 해설)
          ├── SeniorSynthesisAgent (피드백 인지 종합 판단)
          └── 월요일: 주간 적중률 요약
                    ↓
          텔레그램 자동 전송
```

### 피드백 루프

```
브리핑 발행 (D+0) → 시그널 DB 기록
                          ↓
다음날 (D+1) → 전일 KOSPI 결과 수집 → 1일 적중 판정 → 뉴스 수집 → 사후 분석
                          ↓
D+3 → 3일 수익률 평가
D+5 → 5일 수익률 평가
                          ↓
다음 브리핑 → AI가 피드백 컨텍스트 참조하여 분석
             (적중률, 지표별 신뢰도, 놓친 변수, 주의 포인트)
```

## 테스트

```bash
pytest tests/ -v                     # 전체 (275개)
pytest tests/market/ -v              # 정량 분석
pytest tests/content/ -v             # 정성 분석
pytest tests/briefing/ -v            # 브리핑
pytest tests/agents/ -v              # 브리핑 AI 에이전트
pytest tests/feedback/ -v            # 피드백 시스템
pytest tests/ --cov=alphapulse       # 커버리지 리포트
```

## 기술 스택

| 범주 | 패키지 |
|------|--------|
| 한국 시장 데이터 | pykrx, finance-datareader, beautifulsoup4 |
| 미국 경제 데이터 | fredapi |
| 웹 크롤링 | crawl4ai, httpx, feedparser |
| AI 멀티에이전트 | google-adk ~= 1.27.2 (Gemini API) |
| 텔레그램 | httpx (Bot API), telethon (채널 모니터) |
| CLI | click |
| 터미널 UI | rich |
| 리포트 | jinja2, matplotlib |
| 저장소 | SQLite (캐시 + 이력 + 피드백) |

## 로드맵

| 버전 | 목표 |
|------|------|
| **v1.0** | 일일 자동 브리핑 (정량+정성+AI 종합) |
| **v1.1** (현재) | 피드백 시스템 (적중률 추적 + 사후 분석 + AI 프롬프트 자동 반영) |
| v1.5 | AI 에이전트가 tool/function calling으로 시장 데이터 능동 조회 |
| v2.0 | AI 투자 에이전트, 병렬 수집, 백테스팅 |
| v3.0 | 웹 대시보드 (Streamlit/Gradio), 실시간 갱신 |
