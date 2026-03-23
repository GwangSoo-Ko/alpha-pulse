# AlphaPulse

**AI 기반 투자 인텔리전스 플랫폼** — 정량 분석(Market Pulse)과 정성 분석(Content Intelligence)을 통합하여 일일 투자 브리핑을 자동 생성합니다.

## 리포트 3종 체계

| 리포트 | 트리거 | 내용 |
|--------|--------|------|
| **정량 리포트** | 매일 장 전 (08:00) | Market Pulse Score + 10개 지표 + AI 코멘트 |
| **정성 리포트** | 블로그/채널 감지 시 | 멀티에이전트 AI 분석 (5개 분야 전문가 → 시니어 종합) |
| **종합 리포트** | 매일 장 전 (08:30) | 정량+정성을 AI가 맥락 기반 종합 판단 |

## 설치

### 전제 조건

- Python 3.11+
- Chromium (Crawl4AI용): `crawl4ai-setup`
- Google Gemini API 키 ([AI Studio](https://aistudio.google.com))
- Telegram Bot 토큰 ([@BotFather](https://t.me/BotFather))

### 설치 방법

```bash
git clone <repo-url> && cd alpha-pulse
cp .env.example .env
# .env 파일에 API 키 입력

pip install -e ".[dev]"
ap --version
```

## 사용법

### 정량 분석 (Market Pulse)

```bash
ap market pulse                      # 종합 시황 (Market Pulse Score)
ap market pulse --date 2026-03-21    # 특정 날짜
ap market pulse --period weekly      # 주간 분석
ap market investor                   # 투자자 수급 상세
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
ap briefing                          # 정량 + AI 종합 → 텔레그램 전송
ap briefing --no-telegram            # 터미널 출력만
ap briefing --daemon --time 08:00    # 매일 08:00 자동 실행
ap commentary                        # AI 시장 해설만 생성
ap commentary --date 2026-03-20      # 과거 날짜 해설
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

## 아키텍처

```
alphapulse/
├── core/           # 공유 인프라 (config, storage, notifier, constants)
├── market/         # 정량 분석 파이프라인 (sync)
│   ├── collectors/ #   5개 데이터 수집기 (pykrx, FDR, KRX, FRED, investing)
│   ├── analyzers/  #   5개 분석기 (수급, 프로그램, 업종, 자금, 매크로)
│   ├── engine/     #   SignalEngine (10개 지표 가중합산 → -100~+100 점수)
│   └── reporters/  #   터미널 + HTML 리포트
├── content/        # 정성 분석 파이프라인 (async)
│   ├── agents/     #   멀티에이전트 (TopicClassifier → 5 Specialists → SeniorAnalyst)
│   ├── detector.py #   RSS 새 글 감지
│   ├── crawler.py  #   Crawl4AI 크롤링
│   └── monitor.py  #   BlogMonitor 오케스트레이터
├── briefing/       # 일일 브리핑 통합
│   ├── orchestrator.py  # 정량+정성+AI 조합
│   ├── formatter.py     # 텔레그램 HTML 포맷
│   └── scheduler.py     # 데몬 모드 스케줄러
└── agents/         # AI 에이전트
    ├── commentary.py    # MarketCommentaryAgent (정량 해설)
    └── synthesis.py     # SeniorSynthesisAgent (종합 판단)
```

### 데이터 흐름

```
[08:00] SignalEngine → 10개 지표 수집/분석 → Market Pulse Score
                                                    ↓
[실시간] BlogMonitor → RSS/채널 감지 → AI 멀티에이전트 분석
                                                    ↓
[08:30] BriefingOrchestrator
          ├── 정량 데이터 (SignalEngine 결과)
          ├── 정성 요약 (최근 24시간 reports/)
          ├── MarketCommentaryAgent (정량 해설)
          └── SeniorSynthesisAgent (종합 판단)
                    ↓
          텔레그램 자동 전송
```

## 테스트

```bash
pytest tests/ -v                     # 전체 (235개)
pytest tests/market/ -v              # 정량 분석만
pytest tests/content/ -v             # 정성 분석만
pytest tests/briefing/ -v            # 브리핑만
pytest tests/agents/ -v              # AI 에이전트만
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
| 저장소 | SQLite (캐시 + 이력) |

## 로드맵

| 버전 | 목표 |
|------|------|
| **v1.0** (현재) | 일일 자동 브리핑 (정량+정성+AI 종합) |
| v1.5 | AI 에이전트가 tool/function calling으로 시장 데이터 능동 조회 |
| v2.0 | AI 투자 에이전트, 병렬 수집, 백테스팅 |
| v3.0 | 웹 대시보드 (Streamlit/Gradio), 실시간 갱신 |
