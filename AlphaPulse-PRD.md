# AlphaPulse PRD -- AI 기반 투자 인텔리전스 플랫폼

> **버전:** 0.2
> **작성일:** 2026-03-23
> **상태:** 구현 전 설계

---

## 1. Executive Summary

AlphaPulse는 **정량 분석(Market Pulse)**과 **정성 분석(Content Intelligence)**을 **독립적으로 실행**하고, AI 멀티에이전트가 두 결과를 종합 판단하여 투자 인텔리전스를 제공하는 플랫폼이다.

두 파이프라인은 무조건 매핑되지 않는다. 정량 데이터(직전 거래일 기준)와 정성 콘텐츠(블로그/텔레그램 피드)는 시점과 맥락이 다를 수 있으므로, 각각 독립 리포트를 발행하고 AI 종합 에이전트가 맥락에 따라 연결 여부를 판단한다.

**리포트 3종 체계:**
1. **📊 정량 리포트** — Market Pulse Score + 10개 지표 (텔레그램 자동 발송)
2. **📝 정성 리포트** — AI 멀티에이전트 콘텐츠 분석 (블로그/채널 감지 시 발송)
3. **📋 종합 리포트** — Senior Synthesis Agent가 두 리포트를 소스로 종합 판단 (매일 장 전 발송)

**멀티에이전트 구조:**
- **분야별 전문가 에이전트** — 한국주식, 미국주식, 환율, 채권, 원자재 (각 분야 독립 분석)
- **Senior Synthesis Agent** — 전문가 분석 + 정량 데이터를 종합하여 최종 판단

**현재 범위:** 정량 분석은 한국시장(KOSPI/KOSDAQ)에 한정. 미국시장 정량 분석은 v2.0에서 추가.

v1.0은 CLI + Telegram 자동 브리핑에 집중하고, v2.0에서 AI 투자 에이전트로 확장한다.

---

## 2. Problem Statement

### 현재 상황

개인 투자자가 장 시작 전에 시장 상황을 파악하려면 다음을 수동으로 확인해야 한다:

1. **수급 데이터** -- 외국인/기관 매매동향, 프로그램 매매, 예탁금 (증권사 HTS, KRX)
2. **매크로 환경** -- 환율, 금리, 글로벌 지수, V-KOSPI (여러 웹사이트)
3. **전문가 분석** -- 경제 블로그, 텔레그램 채널, 리서치 리포트 (분산된 소스)

이 과정에 매일 30분 이상이 소요되며, 데이터와 해석이 분리되어 있어 종합 판단이 어렵다.

### 기존 프로젝트의 한계

| 프로젝트 | 강점 | 한계 |
|---------|------|------|
| **K-Market Pulse** | 10개 지표 자동 수집, 객관적 점수 산출 | 숫자만 제공. "왜 외국인이 매도하는가?"에 답할 수 없음 |
| **BlogPulse** | AI가 전문가 콘텐츠를 분석하여 맥락 제공 | 실제 시장 데이터와 연결되지 않음. 블로그 글이 없으면 분석 불가 |

### AlphaPulse의 해결책

두 프로젝트를 통합하여 **데이터 기반 점수 + AI 콘텐츠 분석 + AI 종합 해설**을 하나의 자동화된 일일 브리핑으로 제공한다.

---

## 3. Product Vision

| 버전 | 목표 | 핵심 기능 |
|------|------|----------|
| **v1.0** | 일일 자동 브리핑 | KMP 지표 수집 + BlogPulse 콘텐츠 분석 + AI 종합 브리핑 -> Telegram 전송 (08:30) |
| **v1.5** | AI가 데이터를 읽고 설명 | AI 에이전트가 Market Pulse 데이터를 tool/function으로 직접 조회하여 해설 생성 |
| **v2.0** | AI 투자 에이전트 | 전략 추천, 포트폴리오 관점 제안, 과거 데이터 기반 백테스팅 |
| **v3.0** | 웹 대시보드 + 실시간 | Streamlit/Gradio UI, 실시간 데이터 갱신, 사용자 맞춤 설정 |

---

## 4. System Architecture

### 4.1 High-Level Architecture — 독립 파이프라인 + 종합 판단

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           AlphaPulse Platform                               │
│                                                                             │
│  ┌─── 정량 파이프라인 (독립 실행) ──────────┐  ┌─── 정성 파이프라인 (독립 실행) ──┐  │
│  │                                          │  │                                │  │
│  │  [수집] KR Market Collectors             │  │  [수집] Blog/Channel Collectors  │  │
│  │    PykrxCollector (투자자 수급)           │  │    PostDetector (RSS)            │  │
│  │    KrxScraper (프로그램, 업종, 예탁금)    │  │    BlogCrawler (Crawl4AI)        │  │
│  │    FdrCollector (환율, 글로벌 지수)       │  │    TelegramChannelMonitor        │  │
│  │    FredCollector (미국/한국 금리)         │  │    MessageAggregator             │  │
│  │    InvestingScraper (선물, V-KOSPI)       │  │                                │  │
│  │            ↓                              │  │            ↓                    │  │
│  │  [분석] 10개 지표 Analyzers              │  │  [분석] AI 멀티에이전트          │  │
│  │    InvestorFlowAnalyzer (20%)            │  │    TopicClassifier               │  │
│  │    MacroMonitorAnalyzer (10%+10%+5%)     │  │    ┌─ 분야별 전문가 에이전트 ──┐ │  │
│  │    MarketBreadthAnalyzer (10%+10%)       │  │    │ KRStockAnalyst (한국주식) │ │  │
│  │    ProgramTradeAnalyzer (10%)            │  │    │ USStockAnalyst (미국주식) │ │  │
│  │    FundFlowAnalyzer (5%)                 │  │    │ ForexAnalyst (환율)       │ │  │
│  │    ScoringEngine (가중합산)               │  │    │ BondAnalyst (채권/금리)   │ │  │
│  │            ↓                              │  │    │ CommodityAnalyst (원자재) │ │  │
│  │  [산출] Market Pulse Score               │  │    └──────────────────────────┘ │  │
│  │            ↓                              │  │    SeniorAnalyst (전문가 종합)   │  │
│  │  📊 정량 리포트 → Telegram 발송          │  │            ↓                    │  │
│  │                                          │  │  📝 정성 리포트 → Telegram 발송 │  │
│  └─────────────┬────────────────────────────┘  └──────────┬─────────────────────┘  │
│                 │                                          │                        │
│                 └──────────────┐  ┌────────────────────────┘                        │
│                                ↓  ↓                                                 │
│                 ┌──────────────────────────────────┐                                │
│                 │  🤖 Senior Synthesis Agent (NEW)  │                                │
│                 │                                    │                                │
│                 │  두 리포트를 "소스"로 참조하여      │                                │
│                 │  맥락에 따라 연결/종합 판단         │                                │
│                 │  (무조건 매핑 아님)                 │                                │
│                 │            ↓                        │                                │
│                 │  📋 종합 리포트 → Telegram 발송    │                                │
│                 └──────────────────────────────────┘                                │
│                                                                                     │
│  ┌── Storage ──────────────────┐  ┌── Output ─────────────────────────┐            │
│  │  DataCache (SQLite)          │  │  TerminalReporter (rich CLI)      │            │
│  │  PulseHistory (SQLite)       │  │  HtmlReporter (jinja2+matplotlib) │            │
│  │  MonitorState (JSON)         │  │  TelegramNotifier (httpx)         │            │
│  │  Reports (Markdown files)    │  │  ReportWriter (markdown)          │            │
│  └──────────────────────────────┘  └───────────────────────────────────┘            │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

**핵심 원칙:**
1. **정량/정성은 독립 파이프라인** — 각각 별도로 실행되고 별도 리포트 발송
2. **종합 에이전트는 두 결과를 "소스"로 참조** — 맥락 판단에 의해 연결 (무조건 매핑 아님)
3. **리포트 3종** — 정량 리포트, 정성 리포트, 종합 리포트 (각각 텔레그램 발송)
4. **멀티에이전트 구조 유지** — 분야별 전문가(5명) + 시니어 분석가 + 종합 에이전트

**정량 분석 범위:** 현재 한국시장(KOSPI/KOSDAQ)에 한정. 미국시장 정량 분석은 TODO (§13 참조).

### 4.2 Module Mapping

#### KMP에서 그대로 마이그레이션하는 모듈

| KMP 원본 경로 | AlphaPulse 대상 경로 | 변경 사항 |
|--------------|---------------------|----------|
| `kmp/collectors/*.py` | `alphapulse/market/collectors/` | import 경로만 변경 |
| `kmp/analyzers/*.py` | `alphapulse/market/analyzers/` | import 경로만 변경 |
| `kmp/engine/*.py` | `alphapulse/market/engine/` | import 경로만 변경 |
| `kmp/reporters/terminal.py` | `alphapulse/market/reporters/terminal.py` | import 경로만 변경 |
| `kmp/reporters/html_report.py` | `alphapulse/market/reporters/html_report.py` | import 경로만 변경 |
| `kmp/reporters/templates/` | `alphapulse/market/reporters/templates/` | 그대로 |
| `kmp/storage/*.py` | `alphapulse/core/storage/` | 공유 모듈로 승격 |
| `kmp/config.py` | `alphapulse/core/config.py`에 병합 | 가중치/임계값 유지, 경로 변경 |

#### BlogPulse에서 그대로 마이그레이션하는 모듈

| BlogPulse 원본 경로 | AlphaPulse 대상 경로 | 변경 사항 |
|--------------------|---------------------|----------|
| `naver_blog_monitor/agents/*.py` | `alphapulse/content/agents/` | import 경로 변경, config 통합 |
| `naver_blog_monitor/detector.py` | `alphapulse/content/detector.py` | import 경로만 변경 |
| `naver_blog_monitor/crawler.py` | `alphapulse/content/crawler.py` | import 경로만 변경 |
| `naver_blog_monitor/category_filter.py` | `alphapulse/content/category_filter.py` | import 경로만 변경 |
| `naver_blog_monitor/monitor.py` | `alphapulse/content/monitor.py` | CLI 로직 분리, 핵심 로직 유지 |
| `naver_blog_monitor/aggregator.py` | `alphapulse/content/aggregator.py` | import 경로만 변경 |
| `naver_blog_monitor/channel_monitor.py` | `alphapulse/content/channel_monitor.py` | import 경로만 변경 |
| `naver_blog_monitor/notifier.py` | `alphapulse/core/notifier.py` | 공유 모듈로 승격 |
| `naver_blog_monitor/reporter.py` | `alphapulse/content/reporter.py` | import 경로만 변경 |

#### 새로 작성해야 하는 모듈 (Integration Glue)

| 모듈 | 경로 | 역할 | 예상 규모 |
|------|------|------|----------|
| **통합 Config** | `alphapulse/core/config.py` | 양쪽 config 병합, 환경변수 통합 관리 | ~80 라인 |
| **통합 CLI** | `alphapulse/cli.py` | click 그룹: market/content/briefing 서브커맨드 | ~200 라인 |
| **BriefingOrchestrator** | `alphapulse/briefing/orchestrator.py` | 일일 브리핑 파이프라인 조율 | ~150 라인 |
| **BriefingFormatter** | `alphapulse/briefing/formatter.py` | 브리핑 메시지 포맷팅 (Telegram HTML) | ~100 라인 |
| **MarketCommentaryAgent** | `alphapulse/agents/commentary.py` | AI가 시장 데이터를 읽고 해설 생성 | ~120 라인 |
| **MarketDataTool** | `alphapulse/agents/tools.py` | AI 에이전트용 market data 접근 인터페이스 | ~80 라인 |
| **Scheduler** | `alphapulse/briefing/scheduler.py` | cron 스타일 일일 실행 스케줄러 | ~60 라인 |

### 4.3 Key Design Decisions

**Monorepo 구조.** 두 프로젝트를 단일 레포지토리(`alphapulse/`)로 통합한다. 이유: 공유 config, 공유 storage, 공유 notifier를 별도 패키지로 관리하는 오버헤드를 피하고, 단일 `pip install -e .`로 전체 시스템을 설치한다.

**Sync-first, Async adapter.** KMP는 동기(requests/pykrx), BlogPulse는 비동기(httpx/crawl4ai/telethon)이다. v1.0에서는 각 모듈의 실행 모델을 유지하되, BriefingOrchestrator에서 `asyncio.run()`으로 비동기 모듈을 호출한다. v2.0에서 KMP 수집기를 비동기로 전환하여 병렬 수집을 구현한다.

**AI 프레임워크: Google ADK 유지.** BlogPulse의 멀티에이전트 파이프라인이 Google ADK 기반이므로 이를 유지한다. MarketCommentaryAgent도 ADK로 구현하여 일관성을 확보한다. 단, AI 에이전트 레이어는 인터페이스를 추상화하여 향후 Anthropic Claude 또는 OpenAI로 교체 가능하게 설계한다.

**Storage 통합.** KMP의 SQLite cache/history와 BlogPulse의 JSON state를 공존시킨다. v1.0에서는 각자의 저장소를 유지하되 경로를 `alphapulse/data/` 아래로 통일한다. v2.0에서 PostgreSQL 마이그레이션을 검토한다.

**AI 에이전트의 시장 데이터 접근.** MarketCommentaryAgent는 SignalEngine의 결과 dict를 직접 context로 받는다 (v1.0). v1.5에서 ADK의 tool/function calling을 통해 에이전트가 필요한 데이터를 능동적으로 조회하도록 확장한다.

---

## 5. Core Features (v1.0)

### 5.1 Market Pulse Engine (from KMP)

KMP의 전체 파이프라인을 `alphapulse/market/` 아래로 마이그레이션한다. 기능 변경 없이 import 경로만 업데이트한다.

**포함 항목:**
- 5개 수집기 (PykrxCollector, KrxScraper, FdrCollector, FredCollector, InvestingScraper)
- 5개 분석기 (InvestorFlow, ProgramTrade, MarketBreadth, FundFlow, MacroMonitor)
- ScoringEngine (10개 지표 가중합산, N/A 재배분)
- SignalEngine (전체 파이프라인 오케스트레이션)
- 터미널/HTML 리포터
- SQLite 캐시/이력 저장소

**CLI 매핑:**

| KMP 명령어 | AlphaPulse 명령어 |
|-----------|------------------|
| `kmp pulse` | `ap market pulse` |
| `kmp investor` | `ap market investor` |
| `kmp program` | `ap market program` |
| `kmp sector` | `ap market sector` |
| `kmp macro` | `ap market macro` |
| `kmp fund` | `ap market fund` |
| `kmp report` | `ap market report` |
| `kmp history` | `ap market history` |
| `kmp cache clear` | `ap cache clear` |

### 5.2 Content Intelligence Engine (from BlogPulse)

BlogPulse의 전체 파이프라인을 `alphapulse/content/` 아래로 마이그레이션한다.

**포함 항목:**
- PostDetector (RSS 새 글 감지)
- CategoryFilter (카테고리 필터링)
- BlogCrawler (Crawl4AI 크롤링)
- AnalysisOrchestrator + 멀티에이전트 (TopicClassifier, 5개 Specialist, SeniorAnalyst)
- TelegramChannelMonitor + MessageAggregator
- ReportWriter (마크다운 보고서)

**CLI 매핑:**

| BlogPulse 명령어 | AlphaPulse 명령어 |
|-----------------|------------------|
| `python monitor.py` | `ap content monitor` |
| `python monitor.py --daemon` | `ap content monitor --daemon` |
| `python monitor.py --channel-only` | `ap content monitor --channel-only` |
| `python monitor.py --force-latest N` | `ap content monitor --force-latest N` |
| `python monitor.py --test-telegram` | `ap content test-telegram` |
| `python monitor.py --list-channels` | `ap content list-channels` |

### 5.3 리포트 3종 체계 (NEW — 핵심 통합 설계)

정량과 정성은 **독립적으로 실행/발송**되고, 종합 에이전트가 맥락에 따라 연결한다.

#### 📊 리포트 1: 정량 리포트 (Market Pulse Report)

**트리거:** 매일 장 전 자동 실행 (08:00)
**내용:** Market Pulse Score + 10개 지표 점수표 + **분야별 전문가 코멘트**
**발송:** Telegram 자동 전송

정량 데이터만 보여주는 것이 아니라, AI 전문가 에이전트가 숫자에 대한 해석/코멘트를 추가한다. 예: "외국인 -3.7조 매도는 최근 5일 중 최대 규모이며 매도 전환 신호"

```
📊 AlphaPulse 정량 리포트 — 2026-03-23 (월)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Market Pulse Score: -63 (강한 매도)
대상: KOSPI/KOSDAQ (한국시장)

외국인+기관 수급  -100  외국인 -36,755억 | 기관 -38,162억 | 5일: 매도전환
글로벌 시장        -47  SP500 -1.51% | NASDAQ -2.01% | 선물 -0.77%
업종 모멘텀       -100  평균 -4.67% | 상승 업종 1%
프로그램 비차익   -100  비차익 순매도 29,784억
환율 (USD/KRW)     -22  1,489.8원 (+0.06%) | 변동성 1.23% 급등
V-KOSPI            -10  63.19 (패닉) — 역사적 매수 기회 가능성
ADR + 거래량       -93  ADR 0.07 (상승 31 / 하락 453)
선물 베이시스     -100  -5.70% 디스카운트
한미 금리차        -19  미국 4.25% / 한국 3.61%
증시 자금          +50  예탁금 +12.4% | 신용/시총 0.06% 정상

[전문가 코멘트]
🇰🇷 한국주식: 외국인 5일 연속 순매도로 전환. 수급 바닥 확인 필요.
    V-KOSPI 63은 2020년 3월 이후 최고치, 역투자 관찰 구간 진입.
💱 환율: 원/달러 변동성 급등(1.23%)은 단순 약세가 아닌 불확실성 반영.
📈 채권: 한미 금리차 0.64%p로 외국인 자금 이탈 압력은 제한적.
```

#### 📝 리포트 2: 정성 리포트 (Content Intelligence Report)

**트리거:** 블로그 새 글 감지 또는 텔레그램 채널 메시지 수신 시 (비동기, 실시간)
**내용:** 멀티에이전트 분석 결과 (분야별 전문가 → 시니어 종합)
**발송:** 분석 완료 즉시 Telegram 전송

```
📝 AlphaPulse 정성 리포트 — 2026-03-23 15:30
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
출처: [메르의 블로그] "트럼프 관세 3차 확대 시나리오"

[전문가 분석]
🇰🇷 한국주식: IT/반도체 수출 직격탄, 삼성전자 목표가 하향 가능성
🇺🇸 미국주식: 관세 회피 수혜주(멕시코 생산 기업) vs 피해주(중국 의존)
💱 환율: 원화 약세 압력 지속, 1,500원 돌파 가능성 30%
📈 채권: 안전자산 선호로 한국 국채 수요 증가
🛢️ 원자재: 공급망 재편으로 구리/알루미늄 단기 상승

[시니어 종합]
4월 관세 확대 시 한국 수출 의존도 감안하면 KOSPI 추가 하락 가능.
방어적 포지션 유지 권고.
```

#### 📋 리포트 3: 종합 리포트 (Synthesis Report)

**트리거:** 매일 장 전 자동 실행 (08:30), 정량 리포트 이후
**내용:** Senior Synthesis Agent가 정량 리포트 + 최근 정성 리포트를 소스로 종합 판단
**핵심:** 정성 데이터가 없으면 정량 데이터만으로 판단. 있으면 맥락 연결.
**발송:** Telegram 자동 전송

```
📋 AlphaPulse 종합 리포트 — 2026-03-23 (월) 08:30
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[종합 판단: 강한 매도 / 방어적 전략]

정량 분석(Market Pulse -63)에서 외국인 3.7조 순매도와 프로그램 비차익
3조 매도가 동시에 나타나며 수급이 극도로 악화되었습니다.

이와 관련하여 메르의 블로그(3/22)에서 분석한 트럼프 관세 3차 확대
시나리오가 외국인 매도의 주요 원인으로 판단됩니다. 환율 변동성이
1.23%로 급등한 점도 관세 불확실성을 반영합니다.

다만 V-KOSPI 63.19는 역사적 패닉 수준으로, 역발상 매수 관점에서
관찰 구간에 진입했습니다. 예탁금이 12.4% 증가하며 대기자금이
유입되고 있어, 관세 불확실성 해소 시 반등 가능성이 있습니다.

💡 관세 이슈 해소 전까지 방어적 포지션 유지. V-KOSPI 하락 반전 시
   선별적 매수 검토.
```

**CLI:**

```bash
ap briefing                     # 정량 + 종합 리포트 생성 + Telegram
ap briefing --no-telegram       # 터미널 출력만
ap briefing --daemon            # 매일 08:00 정량, 08:30 종합 자동 실행
ap briefing --time 08:00        # 종합 리포트 발송 시간 변경
ap commentary --date 2026-03-20 # 과거 날짜 종합 해설
```

### 5.4 멀티에이전트 구조 상세

#### 정성 파이프라인 에이전트 (BlogPulse 계승)

```
Stage 1: TopicClassifier
  → 콘텐츠에서 관련 분야 태깅: ["kr_stock", "us_stock", "forex", "bond", "commodity"]

Stage 2: 분야별 전문가 에이전트 (해당 분야만 병렬 실행)
  ├─ KRStockAnalyst  — 한국 주식/경제 전문가
  ├─ USStockAnalyst  — 미국 주식/경제 전문가
  ├─ ForexAnalyst    — 외환/환율 전문가
  ├─ BondAnalyst     — 채권/금리 전문가
  └─ CommodityAnalyst — 원자재/에너지 전문가

Stage 3: SeniorAnalyst
  → 전문가 분석 종합 → 정성 리포트 생성
```

#### 종합 판단 에이전트 (NEW)

```
SeniorSynthesisAgent
  입력:
    - 📊 정량 리포트 (Market Pulse Score + 10개 지표 상세)
    - 📝 정성 리포트 (최근 24시간 내, 0~N개)
  판단:
    - 정성 리포트가 있으면: 정량 데이터와 정성 분석의 맥락 연결 시도
    - 정성 리포트가 없으면: 정량 데이터만으로 시장 해설
    - 정량/정성이 상충하면: 상충 사실을 명시하고 양쪽 근거 제시
  출력:
    - 📋 종합 리포트
```

**KRStockAnalyst와 정량 데이터 연결 (v1.5):**
한국주식 전문가 에이전트는 v1.5에서 Market Pulse 데이터를 tool로 직접 조회하여, 정성 분석에 정량 근거를 포함시킬 수 있다. 예: "외국인 매도(-3.7조)가 관세 우려를 반영"

---

## 6. Architecture Details

### 6.1 Directory Structure

```
alphapulse/
├── pyproject.toml                        # 통합 패키지 정의
├── .env.example                          # 환경변수 템플릿
├── alphapulse/
│   ├── __init__.py                       # __version__ = "1.0.0"
│   ├── cli.py                            # click 그룹: ap {market,content,briefing,commentary,cache}
│   │
│   ├── core/                             # 공유 인프라
│   │   ├── __init__.py
│   │   ├── config.py                     # 통합 설정 (KMP 가중치 + BlogPulse 설정 + 브리핑 설정)
│   │   ├── notifier.py                   # TelegramNotifier (BlogPulse에서 승격, 양쪽 공유)
│   │   └── storage/
│   │       ├── __init__.py
│   │       ├── cache.py                  # DataCache (from KMP)
│   │       └── history.py               # PulseHistory (from KMP)
│   │
│   ├── market/                           # KMP 전체 마이그레이션
│   │   ├── __init__.py
│   │   ├── collectors/
│   │   │   ├── __init__.py
│   │   │   ├── base.py                   # BaseCollector + @retry
│   │   │   ├── pykrx_collector.py
│   │   │   ├── krx_scraper.py
│   │   │   ├── fdr_collector.py
│   │   │   ├── fred_collector.py
│   │   │   └── investing_scraper.py
│   │   ├── analyzers/
│   │   │   ├── __init__.py
│   │   │   ├── investor_flow.py
│   │   │   ├── program_trade.py
│   │   │   ├── market_breadth.py
│   │   │   ├── fund_flow.py
│   │   │   └── macro_monitor.py
│   │   ├── engine/
│   │   │   ├── __init__.py
│   │   │   ├── scoring.py
│   │   │   └── signal_engine.py
│   │   └── reporters/
│   │       ├── __init__.py
│   │       ├── terminal.py
│   │       ├── html_report.py
│   │       └── templates/
│   │           └── report.html
│   │
│   ├── content/                          # BlogPulse 전체 마이그레이션
│   │   ├── __init__.py
│   │   ├── monitor.py                    # BlogMonitor 오케스트레이터
│   │   ├── detector.py                   # PostDetector (RSS)
│   │   ├── category_filter.py
│   │   ├── crawler.py                    # BlogCrawler (Crawl4AI)
│   │   ├── reporter.py                   # ReportWriter (마크다운)
│   │   ├── aggregator.py                 # MessageAggregator
│   │   ├── channel_monitor.py            # TelegramChannelMonitor
│   │   └── agents/
│   │       ├── __init__.py
│   │       ├── orchestrator.py           # AnalysisOrchestrator
│   │       ├── topic_classifier.py
│   │       ├── specialists.py
│   │       └── senior_analyst.py
│   │
│   ├── briefing/                         # NEW: 일일 브리핑
│   │   ├── __init__.py
│   │   ├── orchestrator.py               # BriefingOrchestrator
│   │   ├── formatter.py                  # 브리핑 메시지 포맷팅
│   │   └── scheduler.py                  # 데몬 모드 스케줄러
│   │
│   └── agents/                           # NEW: AI 에이전트
│       ├── __init__.py
│       ├── commentary.py                 # MarketCommentaryAgent
│       └── tools.py                      # AI 에이전트용 market data tools (v1.5)
│
├── tests/
│   ├── market/                           # KMP 테스트 마이그레이션 (101개)
│   ├── content/                          # BlogPulse 테스트 마이그레이션 (94개)
│   ├── briefing/                         # 브리핑 테스트 (신규)
│   └── agents/                           # 에이전트 테스트 (신규)
│
├── data/                                 # 런타임 생성
│   ├── cache.db
│   ├── history.db
│   └── .monitor_state.json
│
├── reports/                              # BlogPulse 보고서 저장
└── docs/
```

### 6.2 Data Flow: Daily Briefing

```
[08:00 KST - Scheduler triggers]
         |
         v
BriefingOrchestrator.run()
         |
         +--[1]-- SignalEngine.run(date=today)  ---------> pulse_result dict
         |          |                                       {score: 35, signal: "매수 우위",
         |          +-- 5 Collectors (sync, sequential)     indicator_scores: {...},
         |          +-- 5 Analyzers                         details: {...}}
         |          +-- ScoringEngine
         |
         +--[2]-- ContentSummaryCollector.collect()  ----> content_summaries list
         |          |                                       ["[메르] 트럼프 관세...",
         |          +-- reports/ 디렉토리에서                "[채널] 글로벌 매크로..."]
         |              최근 24시간 내 .md 파일 검색
         |          +-- 각 파일에서 핵심 요약 섹션 추출
         |
         +--[3]-- MarketCommentaryAgent.generate()  ----> commentary str
         |          |                                       "오늘 시장은 매수 우위..."
         |          +-- pulse_result + content_summaries
         |              -> Gemini API 호출
         |
         +--[4]-- BriefingFormatter.format()  ----------> telegram_html str
         |          |
         |          +-- pulse_result -> 점수 카드 + 지표 테이블
         |          +-- content_summaries -> 콘텐츠 요약 섹션
         |          +-- commentary -> AI 해설 섹션
         |
         +--[5]-- TelegramNotifier.send()
         |
         +--[6]-- PulseHistory.save()
```

### 6.3 AI Agent - Market Data Interface (v1.5)

v1.5에서 AI 에이전트가 tool/function calling으로 시장 데이터를 능동적으로 조회한다.

```python
# alphapulse/agents/tools.py (v1.5)

# ADK FunctionTool 정의
def get_market_pulse_score(date: str = "today") -> dict:
    """오늘의 Market Pulse Score와 10개 지표 점수를 반환합니다."""
    engine = SignalEngine()
    result = engine.run(date)
    return {
        "score": result["score"],
        "signal": result["signal"],
        "indicators": result["indicator_scores"],
    }

def get_investor_flow_detail(date: str = "today") -> dict:
    """외국인/기관 매매동향 상세를 반환합니다."""
    # ... SignalEngine 결과에서 investor_flow details 추출

def get_recent_content_analysis(hours: int = 24) -> list[dict]:
    """최근 N시간 내 블로그/채널 분석 보고서를 반환합니다."""
    # ... reports/ 디렉토리에서 최근 파일 검색

def get_pulse_history(days: int = 7) -> list[dict]:
    """최근 N일간 Market Pulse Score 이력을 반환합니다."""
    # ... PulseHistory.get_recent(days)
```

---

## 7. Technical Stack

### 통합 의존성

| 범주 | 패키지 | 출처 | 비고 |
|------|--------|------|------|
| **Runtime** | Python 3.11+ | 공통 | |
| **CLI** | click >= 8.1 | KMP | |
| **한국 시장** | pykrx >= 1.0.45 | KMP | |
| **글로벌 데이터** | finance-datareader >= 0.9.90 | KMP | |
| **미국 경제** | fredapi >= 0.5 | KMP | 선택 |
| **수치 연산** | pandas >= 2.0, numpy >= 1.24 | KMP | |
| **HTTP (sync)** | requests >= 2.31 | KMP | |
| **HTTP (async)** | httpx >= 0.27 | BlogPulse | |
| **HTML 파싱** | beautifulsoup4 >= 4.12 | KMP | |
| **웹 크롤링** | crawl4ai >= 0.4.0 | BlogPulse | 브라우저 크롤링 |
| **RSS** | feedparser >= 6.0 | BlogPulse | |
| **텔레그램 사용자 API** | telethon >= 1.36 | BlogPulse | 채널 모니터 |
| **AI 에이전트** | google-adk ~= 1.27.2 | BlogPulse | 멀티에이전트 (1.27.0 yanked 주의) |
| **터미널 UI** | rich >= 13.0 | KMP | |
| **HTML 리포트** | jinja2 >= 3.1, matplotlib >= 3.7 | KMP | |
| **환경 변수** | python-dotenv >= 1.0 | 공통 | |
| **SSL 인증서** | certifi >= 2024.0 | BlogPulse | |
| **테스트** | pytest >= 8.0, pytest-cov >= 4.1, pytest-asyncio >= 0.24 | 공통 | |

### Sync/Async 공존 전략

```
BriefingOrchestrator (sync entry point)
  |
  +-- SignalEngine.run()           # sync (requests, pykrx)
  |
  +-- asyncio.run(                 # async wrapper
  |     ContentSummaryCollector()  # async (파일 I/O는 실제로 sync 가능)
  |   )
  |
  +-- asyncio.run(                 # async wrapper
  |     MarketCommentaryAgent()    # async (google-adk는 async)
  |   )
  |
  +-- TelegramNotifier.send()     # async -> asyncio.run() 래핑
```

BlogPulse의 `BlogMonitor.run_daemon()`은 자체 asyncio event loop를 가지며, BriefingOrchestrator와 독립적으로 실행된다.

---

## 8. CLI Command Reference

```
ap -- AlphaPulse CLI

COMMANDS:
  ap market pulse [--date DATE] [--period {daily,weekly,monthly}]
      종합 시황 분석 (Market Pulse Score)

  ap market investor [--date DATE]
      투자자 수급 상세

  ap market program [--date DATE]
      프로그램 매매 동향

  ap market sector [--date DATE]
      업종별 동향

  ap market macro [--date DATE]
      매크로 환경

  ap market fund [--date DATE]
      증시 자금 동향

  ap market report [--date DATE] [--output FILE]
      HTML 리포트 생성

  ap market history [--days N]
      과거 시황 이력

  ap content monitor [--daemon] [--interval SECS] [--force-latest N]
                     [--no-telegram] [--blog-only] [--channel-only]
      블로그/채널 콘텐츠 모니터링

  ap content test-telegram
      텔레그램 연결 테스트

  ap content list-channels
      구독 텔레그램 채널 목록

  ap briefing [--no-telegram] [--daemon] [--time HH:MM]
      일일 종합 브리핑 생성 + 전송

  ap commentary [--date DATE]
      AI 시장 해설 생성

  ap cache clear
      캐시 초기화

GLOBAL OPTIONS:
  --debug / --no-debug    디버그 로깅
  --version               버전 출력
```

---

## 9. Environment Variables

### 필수

| 변수 | 용도 | 출처 |
|------|------|------|
| `GEMINI_API_KEY` | Google AI API (멀티에이전트 + 시장 해설) | BlogPulse |
| `TELEGRAM_BOT_TOKEN` | 텔레그램 봇 토큰 | BlogPulse |
| `TELEGRAM_CHAT_ID` | 브리핑/알림 수신 채팅 ID | BlogPulse |

### 선택

| 변수 | 기본값 | 용도 | 출처 |
|------|--------|------|------|
| `FRED_API_KEY` | (없음) | FRED API (미국 경제 지표) | KMP |
| `APP_ENV` | `development` | AI 모델 선택 (dev/prod) | BlogPulse |
| `BLOG_ID` | `ranto28` | 모니터링 블로그 | BlogPulse |
| `TARGET_CATEGORIES` | `경제,주식,국제정세,사회` | 블로그 카테고리 필터 | BlogPulse |
| `SKIP_UNKNOWN_CATEGORY` | `true` | 미분류 글 처리 | BlogPulse |
| `GEMINI_MODEL_DEV` | `gemini-3-flash-preview` | 개발 모델 | BlogPulse |
| `GEMINI_MODEL_PROD` | `gemini-3.1-pro-preview` | 운영 모델 | BlogPulse |
| `TELEGRAM_API_ID` | (없음) | 텔레그램 사용자 API | BlogPulse |
| `TELEGRAM_API_HASH` | (없음) | 텔레그램 사용자 API | BlogPulse |
| `TELEGRAM_PHONE` | (없음) | 텔레그램 전화번호 | BlogPulse |
| `CHANNEL_IDS` | (없음) | 텔레그램 채널 ID 목록 | BlogPulse |
| `TELEGRAM_SEND_FILE` | `false` | 보고서 파일 전송 여부 | BlogPulse |
| `CHECK_INTERVAL` | `600` | 콘텐츠 모니터 주기 (초) | BlogPulse |
| `BRIEFING_TIME` | `08:30` | 일일 브리핑 시간 (HH:MM) | NEW |
| `BRIEFING_ENABLED` | `true` | 브리핑 자동 전송 on/off | NEW |
| `AGGREGATION_WINDOW` | `300` | 채널 글타래 윈도우 (초) | BlogPulse |
| `REPORTS_DIR` | `./reports` | 보고서 저장 경로 | BlogPulse |
| `STATE_FILE` | `./data/.monitor_state.json` | 블로그 상태 파일 | BlogPulse (경로 변경) |
| `LOG_FILE` | `./alphapulse.log` | 로그 파일 | 공통 |
| `MAX_RETRIES` | `3` | 크롤링/API 재시도 | 공통 |

---

## 10. Migration Plan

### Phase 1: 프로젝트 Scaffold + 공유 인프라 (1일)

**목표:** 빈 프로젝트 구조 생성, 공유 모듈 설정

**작업:**
1. `alphapulse/` 레포지토리 생성, `pyproject.toml` 작성 (통합 의존성)
2. `alphapulse/core/config.py` -- 양쪽 설정 병합, `.env` 로드
3. `alphapulse/core/notifier.py` -- BlogPulse의 TelegramNotifier 이동
4. `alphapulse/core/storage/` -- KMP의 cache.py, history.py 이동
5. `alphapulse/cli.py` -- click 그룹 스켈레톤 (`ap market`, `ap content`, `ap briefing`)
6. 기본 테스트 인프라 (`pytest.ini`, `conftest.py`)

**완료 조건:** `pip install -e ".[dev]"` 성공, `ap --version` 동작

### Phase 2: KMP 마이그레이션 (1일)

**목표:** KMP 전체 코드를 `alphapulse/market/`으로 이동, 테스트 통과

**작업:**
1. `kmp/collectors/` -> `alphapulse/market/collectors/` 복사
2. `kmp/analyzers/` -> `alphapulse/market/analyzers/` 복사
3. `kmp/engine/` -> `alphapulse/market/engine/` 복사
4. `kmp/reporters/` -> `alphapulse/market/reporters/` 복사
5. 모든 파일의 `from kmp.` -> `from alphapulse.market.` 또는 `from alphapulse.core.` import 변경
6. `config.py`, `storage/` 참조를 `alphapulse.core`로 변경
7. CLI에 `ap market` 서브커맨드 연결
8. KMP 테스트 101개 마이그레이션 + 통과 확인

**완료 조건:** `ap market pulse` 실행 시 KMP와 동일한 출력, 101개 테스트 통과

### Phase 3: BlogPulse 마이그레이션 (1일)

**목표:** BlogPulse 전체 코드를 `alphapulse/content/`로 이동, 테스트 통과

**작업:**
1. `naver_blog_monitor/agents/` -> `alphapulse/content/agents/` 복사
2. `naver_blog_monitor/*.py` -> `alphapulse/content/` 복사 (monitor, detector, crawler, category_filter, reporter, aggregator, channel_monitor)
3. `naver_blog_monitor/config.py` 참조를 `alphapulse.core.config`로 변경
4. `naver_blog_monitor/notifier.py` 참조를 `alphapulse.core.notifier`로 변경
5. 모든 import 경로 업데이트
6. CLI에 `ap content` 서브커맨드 연결
7. BlogPulse 테스트 94개 마이그레이션 + 통과 확인

**완료 조건:** `ap content monitor --force-latest 1 --no-telegram` 동작, 94개 테스트 통과

### Phase 4: Daily Briefing 구현 (2일)

**목표:** `ap briefing` 명령어로 종합 브리핑 생성 + Telegram 전송

**작업 (Day 1):**
1. `alphapulse/briefing/orchestrator.py` -- BriefingOrchestrator 구현
   - SignalEngine.run() 호출
   - reports/ 디렉토리에서 최근 콘텐츠 분석 수집
   - 결과 조합
2. `alphapulse/briefing/formatter.py` -- BriefingFormatter 구현
   - 점수 카드 + 지표 테이블 + 콘텐츠 요약을 Telegram HTML로 변환
3. CLI `ap briefing` 명령어 연결

**작업 (Day 2):**
4. `alphapulse/briefing/scheduler.py` -- 데몬 모드 구현
   - `--daemon` 플래그: 매일 지정 시간에 briefing 실행
   - Python `schedule` 라이브러리 또는 `asyncio` 기반 타이머
5. Telegram 전송 테스트
6. 브리핑 단위 테스트 작성 (20개 이상)

**완료 조건:** `ap briefing` 실행 시 Market Pulse + 콘텐츠 요약이 포함된 Telegram 메시지 수신

### Phase 5: AI Commentary 구현 (2일)

**목표:** AI가 시장 데이터를 기반으로 자연어 해설 생성

**작업 (Day 1):**
1. `alphapulse/agents/commentary.py` -- MarketCommentaryAgent 구현
   - Google ADK 기반 에이전트
   - pulse_result를 구조화된 프롬프트로 변환
   - 3~5문장 시장 해설 생성
2. CLI `ap commentary` 명령어 연결
3. Gemini API 호출 테스트

**작업 (Day 2):**
4. Commentary를 BriefingOrchestrator에 통합
   - briefing의 [3] AI Commentary 섹션 연결
5. 프롬프트 최적화 (실제 데이터로 반복 테스트)
6. 에이전트 단위 테스트 작성 (10개 이상)

**완료 조건:** `ap briefing`에 AI Commentary 섹션이 포함되어 전송됨

### Phase 6: 테스트 + Polish (1일)

**목표:** 전체 통합 테스트, 문서화, 안정화

**작업:**
1. 통합 테스트 작성 (briefing E2E, CLI 전체 명령어)
2. 커버리지 확인 (목표: 85% 이상)
3. `.env.example` 작성 (전체 환경변수)
4. README.md 작성 (설치, 설정, 사용법)
5. 에러 핸들링 검증 (API 실패, 네트워크 오류 시나리오)
6. 실제 운영 환경에서 `ap briefing --daemon` 24시간 테스트

**완료 조건:** 전체 테스트 통과 (220개 이상), `ap briefing --daemon` 안정 동작

### 전체 타임라인

```
Day 1: Phase 1 (Scaffold) + Phase 2 시작
Day 2: Phase 2 완료 + Phase 3
Day 3: Phase 4 (Briefing Day 1)
Day 4: Phase 4 완료 + Phase 5 시작
Day 5: Phase 5 완료
Day 6: Phase 6 (Test + Polish)
---
총 6일 (1주)
```

---

## 11. v2.0 Roadmap

| 기능 | 설명 | 우선순위 |
|------|------|---------|
| **AI 투자 에이전트 (Tool Use)** | 에이전트가 `get_market_pulse_score()`, `get_investor_flow_detail()` 등을 tool로 사용하여 능동적으로 데이터 조회 + 분석 | 높음 |
| **병렬 데이터 수집** | KMP 수집기를 asyncio/concurrent.futures로 병렬화 (현재 순차 실행 약 60초 -> 목표 20초) | 높음 |
| **한국 공휴일 캘린더** | `exchange_calendars` 연동으로 공휴일 자동 건너뛰기 | 높음 |
| **백테스팅 프레임워크** | PulseHistory 축적 데이터로 "Score +40 이상일 때 다음날 KOSPI 수익률" 분석 | 중간 |
| **웹 대시보드** | Streamlit 또는 Gradio 기반 UI. 실시간 점수, 차트, AI 해설 표시 | 중간 |
| **멀티 블로그 모니터링** | 복수 블로그 ID + 블로그별 카테고리 설정 | 중간 |
| **Slack 연동** | Telegram 외 Slack 웹훅 지원 | 낮음 |
| **REST API** | FastAPI 래핑으로 외부 시스템 연동 가능 | 낮음 |
| **가중치 자동 보정** | 백테스팅 결과 기반 10개 지표 가중치 최적화 | 낮음 |
| **PostgreSQL 마이그레이션** | SQLite -> PostgreSQL로 전환 (멀티 프로세스 안정성) | 낮음 |

---

## 12. TODO — 미국시장 정량 분석 확장

현재 정량 파이프라인(Market Pulse)은 **한국시장(KOSPI/KOSDAQ)에 한정**되어 있다. 미국시장 정량 분석은 아래 계획으로 추가한다.

### 구현 시 추가될 항목

| 항목 | 내용 | 데이터 소스 후보 |
|------|------|----------------|
| **US Market Pulse Score** | 미국시장 종합 점수 (-100~+100) | — |
| 기관 수급 (13F/Flow) | ETF 자금흐름, 기관 포지션 변화 | FRED, ETF.com API |
| 섹터 로테이션 | S&P 11개 섹터 등락률 | FDR (Yahoo Finance) |
| 변동성 (VIX) | CBOE VIX 수준 | FDR, investing.com |
| 금리/채권 | 미국 10Y/2Y 스프레드, 장단기 금리차 | FRED (DGS10, DGS2) |
| 고용/경제 | 실업률, 비농업고용, PMI | FRED |
| Put/Call Ratio | 옵션 시장 심리 | CBOE |
| Fear & Greed Index | CNN 공포탐욕지수 | 크롤링 |
| 기술적 지표 | S&P500 이동평균 돌파 여부 | FDR |
| 연준 정책 | FOMC 결정, 금리 전망 | FRED, FedWatch |

### 구현 시 아키텍처 영향

- `alphapulse/market/` 하위에 `kr/` (한국), `us/` (미국) 서브 패키지로 분리
- 각 시장별 독립 Score 산출 → 통합 Global Score 가능
- USStockAnalyst 전문가 에이전트가 미국 정량 데이터를 tool로 조회
- 리포트에 한국/미국 섹션 병렬 표시

### 우선순위

v2.0 이후 — 한국시장 정량+정성 통합이 안정화된 후 추가

---

## 12. Success Metrics

### 기능 지표

| 항목 | 목표 |
|------|------|
| 일일 브리핑 전송 | 거래일 08:30 이전 100% 전송 |
| Market Pulse 지표 | 10개 중 8개 이상 정상 수집 (N/A 2개 이하) |
| AI Commentary | 시장 데이터 수치를 1개 이상 정확히 인용 |
| Content Intelligence | 24시간 내 블로그 분석이 있으면 브리핑에 포함 |
| 파이프라인 실행 시간 | 브리핑 전체 파이프라인 3분 이내 완료 |

### 품질 지표

| 항목 | 목표 |
|------|------|
| 테스트 커버리지 | 85% 이상 |
| 테스트 수 | 220개 이상 (KMP 101 + BlogPulse 94 + 신규 25+) |
| 데몬 안정성 | 7일 연속 무중단 운영 |
| 에러 복구 | API 실패 시 3회 재시도 + 캐시 폴백 + 가중치 재배분 |

### 비즈니스 지표

| 항목 | 목표 |
|------|------|
| 수동 확인 시간 절감 | 30분/일 -> 5분/일 (브리핑 읽기) |
| 정보 커버리지 | 수급 + 매크로 + 전문가 분석 = 3개 영역 단일 소스 |
| 의사결정 지원 | Score + AI 해설로 장 시작 전 시장 방향 판단 가능 |

-추가 사항-

AlphaPulse 통합 시 주의사항

  1. Sync/Async 충돌

  KMP는 동기(requests), BlogPulse는 **비동기(httpx, asyncio)**입니다. asyncio.run() 안에서 또 asyncio.run()을 호출하면 에러납니다. BlogPulse의 async 함수를
  호출할 때 이벤트 루프 중첩에 주의하세요.

  2. import 경로 일괄 변경

  마이그레이션 시 from kmp. → from alphapulse.market.으로 바꿔야 할 파일이 30개 이상입니다. 수동으로 하지 말고 한 모듈씩 옮기고 바로 테스트 돌리세요. 한꺼번에
   옮기면 어디서 깨졌는지 찾기 어렵습니다.

  3. config 병합 시 키 충돌

  두 프로젝트 모두 MAX_RETRIES, LOG_FILE 같은 변수를 쓰는데 기본값이 다릅니다. 네임스페이스를 구분하거나(MARKET_MAX_RETRIES, CONTENT_MAX_RETRIES) 공통 값으로
  통일하는 결정을 먼저 하세요.

  4. 네이버 크롤링 rate limit

  KMP와 BlogPulse가 동시에 네이버를 크롤링합니다. 두 파이프라인이 같은 시간에 실행되면 IP 차단 위험이 있으니, 정량(08:00) → 종합(08:30) 순서로 시차를 두세요.

  5. Google ADK 의존성

  BlogPulse의 google-adk는 아직 초기 라이브러리라 버전 변경이 잦습니다. pyproject.toml에 버전을 고정하고, 새 버전 올라올 때마다 테스트 돌려서 확인하세요.

  6. 테스트 격리

  두 프로젝트의 테스트가 합쳐지면 195개입니다. BlogPulse 테스트 중 네트워크를 타는 것이 있으면 KMP 테스트까지 느려집니다. tests/market/, tests/content/로
  분리하고 pytest tests/market/ -v처럼 개별 실행할 수 있게 하세요.

  7. 가장 중요한 것

  Phase 2(KMP 마이그레이션) 완료 후 ap market pulse가 기존과 동일하게 동작하는지 반드시 확인하고 나서 Phase 3으로 넘어가세요. 두 프로젝트가 각각 독립적으로
  돌아가는 걸 확인한 뒤에 통합 기능을 붙여야 합니다.
