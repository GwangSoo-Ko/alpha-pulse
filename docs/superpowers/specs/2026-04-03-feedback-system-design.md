# AlphaPulse ���드백 시스템 설계 스펙

> **Date:** 2026-04-03
> **Status:** Approved
> **Version:** 1.0

---

## 1. 목표

AlphaPulse의 정량/정성 분석 시그널에 대해 **장 마감 후 실제 결과를 검증**하고, **왜 맞았는지/틀렸는지를 AI가 분석**하여, **다음 분석에 자동 반영**하는 피드백 루프를 구축한다.

투자 에이전트가 매일 스스로 학습하고 발전하는 시스템.

---

## 2. 핵심 결정 사항

| 항목 | 결정 |
|------|------|
| 정답 기준 | **복합**: 1일/3일/5일 수익률 모두 추적 |
| 반영 방식 | **AI 프롬프트 주입** + 가중치는 수동 리밸런싱 참고 데이터로 제공 |
| 실행 시점 | **다음날 브리핑 직전** (08:00) + CLI 수동 실행 보조 |
| 텔레그램 발송 | **매일 한 줄 결과** + **월요일 주간 요약** |
| 적중 판단 | **방향 일치**(hit rate) + **시그널 강도-수익률 상관계수**(correlation) 분리 추적 |
| 뉴스 소스 | **기존 정성(블로그/채널)** = 장 전 예측 근거, **네이버 뉴스** = 장 후 사후 분석 소스 |
| 사후 분석 | **멀티에이전트**: 사각지대 + 예측 복기 + 외부 변수 → 종합 피드백 |

---

## 3. 아키텍처

### 3.1 전체 흐름

```
[매일 08:00 브리핑 파이프라인 — 수정된 흐름]

 ┌─── 피드백 단계 (신규) ─────────────────────────────────────────┐
 │                                                                │
 │  [0-1] FeedbackCollector                                       │
 │         전일 KOSPI/KOSDAQ 종가 수집 (pykrx/FDR)                │
 │         과거 시그널의 1일/3일/5일 수익률 계산                    │
 │                                                                │
 │  [0-2] NewsCollector                                           │
 │         네이버 금융 뉴스 크롤링 (전일 장 마감 후 시황 기사)      │
 ���                                                                │
 │  [0-3] PostMarketOrchestrator (멀티에이전트 사후 분석)          │
 │         ├── BlindSpotAgent: 현 시스템 사각지대 식별             ��
 │         ├── PredictionReviewAgent: 예측 복기 (어떤 지표가 왜)   │
 │         ├── ExternalFactorAgent: 외부 변수 식별                 │
 │         └── SeniorFeedbackAgent: 종합 피드백 + 개선 제안        │
 ���                                                                │
 │  [0-4] FeedbackSummarizer                                      │
 │         AI 프롬프트용 요약 + 텔레그램 메시지 생성               │
 │                                                                │
 └────────────────────────────────────────────────────────────────┘
         │
         ▼ feedback_context
 ┌─── 기존 브리핑 단계 (피드백 반영) ─────────────────────────────┐
 │                                                                │
 │  [1] SignalEngine.run() → 정량 분석                            │
 │  [2] collect_recent_content() → 정성 분석 수집                 │
 │  [3] MarketCommentaryAgent.generate(feedback_context=...)      │
 │  [4] SeniorSynthesisAgent.synthesize(feedback_context=...)     │
 │  [5] BriefingFormatter (전일 결과 한 줄 + 월요일 주간 요약)    │
 │  [6] TelegramNotifier.send()                                   │
 │  [7] 오늘 시그널을 FeedbackStore에 기록 (결과는 내일 채움)     │
 │                                                                │
 └─────────────────────────────────────────────────────────��──────┘
```

### 3.2 사후 분석 멀티에이전트 상세

```
PostMarketOrchestrator
  │
  │  입력:
  │    - 장 전 시그널 (score, signal, 11개 지표 상세)
  │    - 장 전 정성 분석 (블로그/채널 요약)
  │    - 실제 결과 (KOSPI 등락률, 수익률)
  │    - 장 후 뉴스 (네이버 금융 시황 기사)
  │
  ├── BlindSpotAgent (사각지대 분석)
  │   역할: 현재 11개 지표가 커버하지 못하는 요인 식별
  │   질문: "정치 이벤트, 규제 변화, 실적 발표, 수급 외 이슈 중
  │          오늘 시장에 영향을 준 것이 무엇인가?"
  │   출력: 놓친 변수 목록 + 시스템 개선 제안
  │
  ├── PredictionReviewAgent (예측 복기)
  │   역할: 어떤 지표가 맞고 틀렸는지, 왜 그런지 분석
  │   질문: "외국인 수급 +68점이었는데 실제로 맞았나?
  │          V-KOSPI -10점은 적절했나? 각 지표의 기여도는?"
  │   출력: 지표별 적중/미적중 원인 분석
  │
  ├── ExternalFactorAgent (외부 변수 분석)
  │   역할: 현 시스템 범위 밖의 시장 영향 요인 식별
  │   질문: "미국 정책, 지정학, 경제 이벤트 캘린더, 실적 시즌,
  │          글로벌 유동성 등 어떤 외부 요인이 작용했나?"
  │   출력: 외부 변수 목록 + 향후 모니터링 포인트
  │
  └── SeniorFeedbackAgent (종합 피드백)
      입력: 위 3개 에이전트 분석 결과 전체
      출력:
        - 예측 성공/실패 핵심 원인 (1~2문장)
        - 놓친 변수 (blind spots) 요약
        - 시스템 개선 제안 (새 지표 후보, 가중치 조정 힌트)
        - 내일 주의할 포인트
        - 지표별 신뢰도 코멘트 (AI 프롬프트 주입용)
```

---

## 4. 데이터 모델

### 4.1 signal_feedback 테이블 (신규)

```sql
CREATE TABLE signal_feedback (
    date TEXT PRIMARY KEY,           -- 시그널 발행일 YYYYMMDD
    -- 예측 데이터
    score REAL,                      -- Market Pulse Score
    signal TEXT,                     -- "매수 우위" 등
    indicator_scores TEXT,           -- JSON {11개 지표 점수}
    -- 시장 결과
    kospi_close REAL,                -- 당일 KOSPI 종가
    kospi_change_pct REAL,           -- 당일 KOSPI 등락률 (%)
    kosdaq_close REAL,               -- 당일 KOSDAQ 종가
    kosdaq_change_pct REAL,          -- 당�� KOSDAQ 등락률 (%)
    -- 수익률 (시그널 발행일 기준)
    return_1d REAL,                  -- 1일 수익률 (%)
    return_3d REAL,                  -- 3일 누적 수익률 (%)
    return_5d REAL,                  -- 5일 누적 수익률 (%)
    -- 적중 판정 (1=적중, 0=미적중, NULL=미확정)
    hit_1d INTEGER,
    hit_3d INTEGER,
    hit_5d INTEGER,
    -- 사후 분석
    post_analysis TEXT,              -- JSON: SeniorFeedbackAgent 출력
    news_summary TEXT,               -- 장 후 주요 뉴스 요약
    blind_spots TEXT,                -- JSON: 놓친 변수 목록
    -- 메타
    evaluated_at REAL,               -- 마지막 평가 Unix timestamp
    created_at REAL                  -- 생성 시간
);
```

### 4.2 부분 평가 전략

시그널 발행 후 시간이 지나면서 점진적으로 결과가 채워진다:

| 시점 | 채워지는 필드 |
|------|--------------|
| 시그널 발행 시 (D+0) | score, signal, indicator_scores |
| 다음날 브리핑 (D+1) | kospi_close, kospi_change_pct, return_1d, hit_1d, post_analysis, news_summary, blind_spots |
| D+3 브리핑 | return_3d, hit_3d |
| D+5 브리핑 | return_5d, hit_5d |

---

## 5. 적중 판단 로직

### 5.1 방향 적중률 (Hit Rate)

```python
# 시그널 방향 판단
signal_direction = "bullish" if score > 0 else "bearish" if score < 0 else "neutral"

# 적중 판정
if signal_direction == "bullish":
    hit = 1 if return_nd > 0 else 0
elif signal_direction == "bearish":
    hit = 1 if return_nd < 0 else 0
else:  # neutral
    hit = 1 if abs(return_nd) < 0.5 else 0  # ±0.5% 이내면 적중
```

### 5.2 시그널 강도-수익률 상관계수 (Correlation)

최근 30일 데이터로 Pearson 상관계수 계산:
- `correlation(score_series, return_1d_series)`
- 0.5 이상: 시그널 강도가 실제 수익률과 잘 대응
- 0.3 미만: 시그널 강도 신뢰도 낮음

### 5.3 지표별 적중률

각 지표가 **극단값(±80 이상)**일 때의 시장 방향 예측 정확도:
```python
# 예: 외국인 수급이 +80 이상이었던 날들 중 KOSPI 양수 비율
investor_flow_extreme_days = [d for d in history if d.indicator_scores["investor_flow"] >= 80]
investor_flow_hit_rate = mean([1 if d.return_1d > 0 else 0 for d in investor_flow_extreme_days])
```

---

## 6. 뉴스 수집 (NewsCollector)

### 6.1 소스

네이버 금융 뉴스 (`https://finance.naver.com/news/`)에서 장 마감 후 시황 기사 수집.

### 6.2 수집 대상

- 검색 키워드: "코스피", "증시", "주식시장"
- 시간 범위: 전일 15:00 ~ 당일 08:00 (장 마감 후 ~ 브리핑 전)
- 수집 건수: 상위 5~10건
- 수집 방법: httpx + BeautifulSoup (기존 크롤링 패턴 활용)

### 6.3 출력

```python
{
    "collected_at": "2026-04-03T07:50:00",
    "articles": [
        {
            "title": "코스피 1.2% 상승…외국인 8천억 순매수",
            "source": "한국경제",
            "published": "2026-04-03 16:30",
            "summary": "외국인 매수 전환에 코스피 반등...",  # 본문 요약 또는 첫 200자
            "url": "https://..."
        },
        ...
    ]
}
```

---

## 7. AI 프롬프트 주입

### 7.1 FeedbackSummarizer 출력 형식

MarketCommentaryAgent와 SeniorSynthesisAgent의 프롬프트에 다음 블록을 주입:

```
=== 피드백 컨텍스트 (최근 30일 기준) ===

[적중률]
전체: 1일 72% | 3일 65% | 5일 68%
상관계수: 0.58 (시그널 강도↔1일 수익률)

[지표별 신뢰도] (극단값 기준)
높음: 외국인 수급 85%, 프로그램 비차익 78%
보통: 업종 모멘텀 62%, 글로벌 시장 60%
낮음: V-KOSPI 38%, 환율 45%
→ V-KOSPI, 환율 기반 판단은 보수적으로 해석하세요.

[어제 복기]
시그널: 매수 우위(+36) → 실제: KOSPI -0.5% ❌
원인: 장중 미국 반도체 수출규제 발표 (시스템 미반영 외부 변수)
놓친 변수: 지정학 리스크, 정책 이벤트 캘린더
교훈: 글로벌 정책 이벤트 사전 모니터링 필요

[오늘 주의 포인트]
- 미국 고용지표(NFP) 발표 예정 (21:30 KST)
- 외국인 선물 매수 5일 연속 → 방향 전환 가능성 모니터링
```

### 7.2 주입 방식

기존 AI 에이전트의 generate()/synthesize() 메서드에 `feedback_context: str | None` 파라미터 추가:

```python
# commentary.py
COMMENTARY_PROMPT = """...
{feedback_context}
=== Market Pulse 데이터 ===
...
"""

async def generate(self, pulse_result, content_summaries, feedback_context=None):
    prompt = self._build_prompt(pulse_result, content_summaries, feedback_context)
    ...
```

---

## 8. 텔레그램 출��

### 8.1 매일 — 종합 리포트 하단 추가

```html
<b>📊 어제 시그널 결과</b>
매수 우위(+36) → KOSPI -0.5% ❌
💡 미국 반도체 수출규제 발표(장중) — 시스템 미반영 외부 변수
```

### 8.2 월요일 — 주간 피드백 요약 섹션

```html
<b>📈 주간 피드백 (3/31~4/4)</b>
적중률: 1일 3/5(60%) | 3일 3/5(60%) | 5일 4/4(100%)
최고 지표: 외국인 수급 (5/5) | 최저: V-KOSPI (1/5)
상관계수: 0.58

<b>🔍 주간 사각지대 분석</b>
• 2회 미적중 원인: 장중 돌발 정책 이벤트
• 놓친 변수: 정책 이벤트 캘린더, 실적 시즌 효과
• 개선 후보: 경제 이벤트 캘린더 지표 추가 검토
• 다음주 주의: 4/7 한국은행 금통위, 4/10 미국 CPI
```

---

## 9. 파일 구조

```
alphapulse/
├── feedback/                          # 신규 패키지
│   ���── __init__.py
│   ├── collector.py                   # FeedbackCollector
│   │   - collect_market_result(date)  # KOSPI/KOSDAQ 종가 수집
│   │   - calculate_returns(date)      # 1d/3d/5d 수익률 계산
│   │   - evaluate_hits(date)          # 방향 적중 판정
│   │
│   ├���─ evaluator.py                   # FeedbackEvaluator
│   │   - evaluate_pending()           # 미확정 시그널 일괄 평가
│   │   - get_hit_rates(days=30)       # 기간별 적중률
│   │   - get_indicator_accuracy(days=30)  # 지표별 적중률
│   │   - get_correlation(days=30)     # 강도-수익률 상관계수
│   │
│   ├── summarizer.py                  # FeedbackSummarizer
│   │   - generate_ai_context(days=30) # AI 프롬프트 주입용 텍스트
│   │   - format_daily_result()        # 텔레그램 매일 한 줄
│   │   - format_weekly_summary()      # 텔레그램 주간 ��약
│   │
│   ├── news_collector.py              # NewsCollector
│   │   - collect_market_news(date)    # 네이버 금융 뉴스 크롤링
│   │   - summarize_news(articles)     # 뉴스 요약
│   │
│   └── agents/                        # 사후 분석 멀티에이전트
│       ├── __init__.py
│       ├── orchestrator.py            # PostMarketOrchestrator
│       │   - analyze(signal, result, news, content_summaries)
│       │
│       ├── blind_spot.py              # BlindSpotAgent
│       │   "현 시스템 사각지대 식별"
│       │
│       ├── prediction_review.py       # PredictionReviewAgent
│       │   "예측 복기 — 어떤 지표가 왜 맞고 틀렸나"
│       │
│       ├── external_factor.py         # ExternalFactorAgent
│       │   "외부 변수 식별 — 정책, 지정학, 이벤트"
│       │
│       ��── senior_feedback.py         # SeniorFeedbackAgent
│           "종합 피드백 + 개선 제안 + 내일 주의 포인트"
│
├── core/storage/
│   └── feedback.py                    # FeedbackStore (신규)
│       - save_signal(date, score, signal, indicators)
│       - update_result(date, close, change, returns, hits)
│       - update_analysis(date, post_analysis, news, blind_spots)
│       - get_recent(days=30)
│       - get_pending_evaluation()
│
├── briefing/
│   └── orchestrator.py                # 수정: 피드백 단계 추가
│
├── agents/
│   ├── commentary.py                  # 수정: feedback_context 파라미터 추가
│   └── synthesis.py                   # 수정: feedback_context 파라미터 추가
│
└��─ cli.py                             # 수정: feedback 서브커맨드 추가

tests/
├── feedback/
│   ├── test_collector.py
│   ├���─ test_evaluator.py
│   ├── test_summarizer.py
│   ├── test_news_collector.py
│   └── test_agents.py
└── ...
```

---

## 10. CLI 명령어

```bash
# 피드백 서브커맨드 그룹
ap feedback evaluate                    # 수동으로 미확정 시그널 평가 실행
ap feedback report [--days 30]          # 적중률 리포트 (터미널 출력)
ap feedback indicators [--days 30]      # 지표별 적중률 순위
ap feedback history [--days 7]          # 최근 시그널 vs 실제 결과 테이블
ap feedback analyze [--date YYYY-MM-DD] # 특정 날짜 사후 분석 실행
```

---

## 11. 브리핑 파이프라인 변경

### 11.1 BriefingOrchestrator.run_async() 수정

```python
async def run_async(self, date=None, send_telegram=True):
    # === 피드백 단계 (신규) ===

    # [0-1] 시장 결과 수집 + 과거 시그널 평가
    feedback_collector = FeedbackCollector()
    feedback_collector.collect_and_evaluate()

    # [0-2] 뉴스 수집
    news = await NewsCollector().collect_market_news()

    # [0-3] 사후 분석 (전일 시그널이 있을 때만)
    yesterday_signal = feedback_store.get_yesterday()
    post_analysis = None
    if yesterday_signal and yesterday_signal.return_1d is not None:
        post_analysis = await PostMarketOrchestrator().analyze(
            signal=yesterday_signal,
            news=news,
            content_summaries=self.collect_recent_content(hours=48),
        )
        feedback_store.update_analysis(yesterday_signal.date, post_analysis)

    # [0-4] 피드백 요약 생성
    feedback_context = FeedbackSummarizer().generate_ai_context(days=30)
    daily_result_msg = FeedbackSummarizer().format_daily_result(yesterday_signal)
    weekly_msg = FeedbackSummarizer().format_weekly_summary()  # 월요일만

    # === 기존 브리핑 단계 (피드백 반영) ===

    # [1] 정량 분석
    pulse_result = await asyncio.to_thread(self.run_quantitative, date)

    # [2] 정성 분석
    content_summaries = self.collect_recent_content(hours=24)

    # [3] AI Commentary (피드백 컨텍스트 주입)
    commentary = await MarketCommentaryAgent().generate(
        pulse_result, content_summaries,
        feedback_context=feedback_context
    )

    # [4] Synthesis (피드백 컨텍스트 주입)
    synthesis = await SeniorSynthesisAgent().synthesize(
        pulse_result, content_summaries, commentary,
        feedback_context=feedback_context
    )

    # [5] 포맷 (전일 결과 + 월요일 주간 요약 포함)
    # [6] 텔레그램 전송
    # [7] 오늘 시그널을 feedback DB에 기록
    feedback_store.save_signal(
        date=pulse_result["date"],
        score=pulse_result["score"],
        signal=pulse_result["signal"],
        indicator_scores=pulse_result["indicator_scores"],
    )
```

---

## 12. 기존 모듈 변경 사항

### 12.1 MarketCommentaryAgent (commentary.py)

- `generate()` 메서드에 `feedback_context: str | None = None` 파라미터 추가
- `_build_prompt()`에서 feedback_context를 프롬프트 상단에 삽입
- 프롬프트 규칙에 "피드백 컨텍스트가 있으면 지표별 신뢰도를 고려하여 판단" 추가

### 12.2 SeniorSynthesisAgent (synthesis.py)

- `synthesize()` 메서드에 `feedback_context: str | None = None` 파라미터 추가
- 동일한 프롬프트 주입 방식

### 12.3 BriefingFormatter (formatter.py)

- `format_quantitative()`에 전일 결과 한 줄 추가 (daily_result_msg)
- `format_synthesis()`에 월요일이면 주간 요약 섹션 추가 (weekly_msg)

### 12.4 Config (config.py)

- 신규 환경변수: `FEEDBACK_LOOKBACK_DAYS=30` (피드백 분석 기간)
- 신규 환경변수: `FEEDBACK_ENABLED=true` (피드백 시스템 on/off)

---

## 13. 구현 우선순위

### Phase A: 기반 (정량 피드백)
1. FeedbackStore (signal_feedback 테이블)
2. FeedbackCollector (시장 결과 수집 + 수익률 계산 + 적중 판정)
3. FeedbackEvaluator (적중률, 상관계수, 지표별 정확도)
4. FeedbackSummarizer (AI 프롬프트 텍스트 + 텔레그램 메시지)
5. CLI `ap feedback` 서브커맨드
6. BriefingOrchestrator 연동 (피드백 단계 추가)

### Phase B: 사후 분석 (정성 피드백)
7. NewsCollector (네이버 금융 뉴스 크롤링)
8. PostMarketOrchestrator + 4개 에이전트
9. 사후 분석 결과를 AI 프롬프트에 주입
10. 텔레그램 주간 사각지대 분석

### Phase C: 기존 에이전트 연동
11. MarketCommentaryAgent — feedback_context 주입
12. SeniorSynthesisAgent — feedback_context 주입
13. BriefingFormatter — 매일 결과 + 주간 요약 추가
14. 통합 테스트

---

## 14. 성공 지표

| 항목 | 목표 |
|------|------|
| 피드백 데이터 수집 | 거래일 100% 자동 수집 |
| 적중률 추적 | 1일/3일/5일 분리 추적 + 30일 롤링 |
| 지표별 정확도 | 11개 지표 각각 극단값 적중률 산출 |
| 사후 분석 | 미적중 시그널에 대해 원인 분석 생성 |
| AI 반영 | 다음 브리핑 AI가 피드백을 인지하고 있음을 텍스트에서 확인 |
| 텔레그램 | 매일 결과 한 줄 + 월요일 주간 요약 발송 |

---

## 15. 환경변수 추가

| 변수 | 기본값 | 용도 |
|------|--------|------|
| `FEEDBACK_ENABLED` | `true` | 피드백 시스템 on/off |
| `FEEDBACK_LOOKBACK_DAYS` | `30` | 적중률 계산 기간 |
| `FEEDBACK_NEWS_ENABLED` | `true` | 뉴스 수집 on/off |
| `FEEDBACK_NEWS_COUNT` | `10` | 수집할 뉴스 기사 수 |
