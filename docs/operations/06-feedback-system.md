# 06. 피드백 시스템 운영 레퍼런스

> AlphaPulse 피드백 시스템의 아키텍처, 데이터 흐름, 운영 절차를 기술한다.
> 모든 클래스명, 메서드명, DB 스키마, 수치는 소스코드 기준이다.

---

## 1. 개요

피드백 시스템은 AlphaPulse의 **예측 -> 결과 -> 학습** 순환 루프를 담당한다.

매일 아침 브리핑에서 발행하는 Market Pulse 시그널(종합 점수 + 11개 지표 점수)이 실제 시장 결과와 얼마나 일치하는지를 정량적으로 추적하고, 멀티에이전트 사후 분석을 통해 시스템 개선 포인트를 도출한다.

**핵심 목적:**

- 시그널 방향 적중률(1일/3일/5일) 추적
- 지표별 신뢰도 평가 (어떤 지표가 잘 맞고, 어떤 지표가 안 맞는지)
- 시그널 강도와 실제 수익률 간 상관계수 모니터링
- AI 에이전트 사후 분석을 통한 정성적 피드백 생성
- 피드백 데이터를 다음 브리핑의 AI 프롬프트에 주입하여 판단 품질 향상

**관련 모듈:**

| 모듈 경로 | 역할 |
|---|---|
| `alphapulse/feedback/collector.py` | 시장 결과 수집 + 수익률 계산 + 적중 판정 |
| `alphapulse/feedback/evaluator.py` | 적중률, 상관계수, 지표별 정확도 계산 |
| `alphapulse/feedback/summarizer.py` | AI 프롬프트용 컨텍스트 + 텔레그램 메시지 포맷 |
| `alphapulse/feedback/news_collector.py` | 네이버 금융 뉴스 수집 (장 마감 후 시황) |
| `alphapulse/feedback/agents/` | 사후 분석 멀티에이전트 (4개 에이전트) |
| `alphapulse/core/storage/feedback.py` | `FeedbackStore` -- SQLite 기반 피드백 저장소 |
| `alphapulse/core/config.py` | 피드백 관련 설정 4개 |

---

## 2. 피드백 수집

### 2.1 수집 클래스

**클래스:** `FeedbackCollector` (`alphapulse/feedback/collector.py`)

```
FeedbackCollector(db_path=None)
```

- `db_path` 미지정 시 `Config().DATA_DIR / "feedback.db"` 사용
- 내부에서 `FeedbackStore` 인스턴스를 생성하여 DB 접근

### 2.2 KOSPI/KOSDAQ 데이터 수집

| 메서드 | 데이터 소스 | 반환값 |
|---|---|---|
| `_get_kospi_data(date)` | pykrx `get_index_ohlcv_by_date(date, date, "1001")` | `{"close": float, "change_pct": float}` |
| `_get_kosdaq_data(date)` | pykrx `get_index_ohlcv_by_date(date, date, "2001")` | `{"close": float, "change_pct": float}` |
| `_get_kospi_close_series(start, end)` | pykrx `get_index_ohlcv_by_date(start, end, "1001")` | `dict[str, float]` (YYYYMMDD -> 종가) |

`collect_market_result(date)` 메서드가 위 두 메서드를 결합하여 아래 형태의 결과를 반환한다:

```python
{
    "kospi_close": float | None,
    "kospi_change_pct": float | None,
    "kosdaq_close": float | None,
    "kosdaq_change_pct": float | None,
}
```

### 2.3 수익률 계산

**메서드:** `calculate_returns(signal_date, base_close)`

시그널 발행일 기준으로 1일/3일/5일 실현 수익률을 계산한다.

- 시그널 발행일 이후 15일 캘린더 기간의 KOSPI 종가 시계열을 가져온다
- 발행일 이후 **거래일 기준**으로 정렬하여 D+1, D+3, D+5 종가를 추출한다
- 수익률 공식: `(future_close / base_close - 1) * 100` (%, 소수점 2자리 반올림)

반환값:

```python
{
    "return_1d": float | None,
    "return_3d": float | None,
    "return_5d": float | None,
}
```

데이터 부족(거래일 미도래, 종가 미확인) 시 해당 필드는 `None`을 반환한다.

### 2.4 전체 수집/평가 파이프라인

**메서드:** `collect_and_evaluate()`

1. `store.get_pending_evaluation()`으로 **미평가 시그널** (`return_1d IS NULL`) 목록 조회
2. 각 시그널에 대해:
   - `collect_market_result(date)`로 당일 시장 결과 수집
   - 시장 데이터가 `None`이면 스킵 (아직 거래일이 아닌 경우)
   - 1일 수익률 = 당일 KOSPI 등락률 (`kospi_change_pct`)
   - `calculate_hit(score, return_1d)`로 적중 판정
   - `store.update_result(...)`로 DB 업데이트
   - `calculate_returns(date, kospi_close)`로 3일/5일 수익률 계산 (가능한 경우)
   - 3일/5일 결과가 있으면 `store.update_returns(...)`로 부분 업데이트

---

## 3. 적중률 평가

### 3.1 적중 판정 함수

**함수:** `calculate_hit(score, return_pct)` (`alphapulse/feedback/collector.py`)

시그널 점수와 실제 수익률의 **방향 일치 여부**를 판정한다.

| 조건 | 시그널 방향 | 적중 기준 | 반환값 |
|---|---|---|---|
| `score >= 20` | Bullish (매수) | `return_pct > 0` | 1 (적중) 또는 0 (미적중) |
| `score <= -20` | Bearish (매도) | `return_pct < 0` | 1 (적중) 또는 0 (미적중) |
| `-19 < score < 20` | Neutral (중립) | `abs(return_pct) < 0.5` | 1 (적중) 또는 0 (미적중) |

**판정 기준 수치:**

- Bullish 임계값: `score >= 20`
- Bearish 임계값: `score <= -20`
- Neutral 범위: `-19 < score < 20`
- Neutral 적중 허용 변동폭: 0.5% 이내

### 3.2 적중률 계산 클래스

**클래스:** `FeedbackEvaluator` (`alphapulse/feedback/evaluator.py`)

```
FeedbackEvaluator(store: FeedbackStore | None = None, db_path=None)
```

#### `get_hit_rates(days=30)`

최근 `days`건의 레코드에서 1일/3일/5일 적중률을 계산한다.

반환값:

```python
{
    "hit_rate_1d": float,   # 0.0 ~ 1.0 (소수점 2자리)
    "hit_rate_3d": float,
    "hit_rate_5d": float,
    "total_evaluated": int, # hit_1d가 NOT NULL인 레코드 수
    "count_1d": int,        # 1일 적중률 계산에 사용된 건수
    "count_3d": int,
    "count_5d": int,
}
```

적중률 공식: `sum(hits) / len(hits)` (소수점 2자리 반올림)

평가된 시그널이 없으면 모든 적중률은 `0.0`, `total_evaluated`는 `0`을 반환한다.

#### `get_indicator_accuracy(days=30, threshold=50.0)`

지표별 **극단값 적중률**을 계산한다. 각 지표가 `threshold` (기본값 50) 이상의 절대값을 가질 때, 해당 시그널의 시장 방향 적중 여부를 집계한다.

반환값 (지표별):

```python
{
    "investor_flow": {
        "hits": int,
        "total": int,
        "accuracy": float,  # 0.0 ~ 1.0 (소수점 2자리)
    },
    ...
}
```

`indicator_scores` 필드가 JSON 문자열이면 `json.loads()`로 파싱한다.

#### `get_correlation(days=30)`

시그널 강도(score)와 1일 수익률(return_1d) 간 **Pearson 상관계수**를 계산한다.

- `numpy.corrcoef(scores, returns)`를 사용한다
- 유효 쌍이 5건 미만이면 `None`을 반환한다 (의미 있는 상관계수 산출 불가)
- 반환값: `float` (소수점 3자리) 또는 `None`

---

## 4. 사후 분석 (Post-Mortem)

### 4.1 멀티에이전트 아키텍처

사후 분석은 **2단계 파이프라인**으로 구성된다.

```
Stage 1 (병렬):
  PredictionReviewAgent  ──┐
  BlindSpotAgent         ──┼──> Stage 2: SeniorFeedbackAgent -> 종합 피드백
  ExternalFactorAgent    ──┘
```

**오케스트레이터:** `PostMarketOrchestrator` (`alphapulse/feedback/agents/orchestrator.py`)

```python
async def analyze(self, signal: dict, news: dict, content_summaries: list[str]) -> dict
```

**Stage 1:** `asyncio.gather()`를 사용하여 3개 전문 에이전트를 **병렬** 실행한다.
**Stage 2:** 3개 결과를 종합하는 시니어 에이전트를 **순차** 실행한다.

반환값:

```python
{
    "blind_spots": str,         # BlindSpotAgent 결과
    "prediction_review": str,   # PredictionReviewAgent 결과
    "external_factors": str,    # ExternalFactorAgent 결과
    "senior_synthesis": str,    # SeniorFeedbackAgent 종합 결과
}
```

### 4.2 에이전트 상세

모든 에이전트는 아래의 공통 패턴을 따른다:

- `__init__()` -> `Config()` 인스턴스 생성
- LLM 호출: `asyncio.to_thread()`로 sync `google.genai.Client` API를 non-blocking 래핑
- 모듈 상단에 `PROMPT` 상수로 프롬프트 정의
- 실패 시 `_fallback()` 메서드로 graceful degradation (예외 전파 금지)
- LLM 설정: `max_output_tokens`, `temperature=0.3`

#### 4.2.1 PredictionReviewAgent (예측 복기)

**파일:** `alphapulse/feedback/agents/prediction_review.py`

**역할:** 퀀트 전략 검증 전문가. 지표별 적중/미적중 분석.

**프롬프트 페르소나:** "퀀트 전략 검증 전문가"

**분석 항목:**

1. 지표별 점수와 실제 시장 결과를 비교하여 적중/미적중 판단
2. 적중한 지표의 성공 요인과 미적중 지표의 실패 원인 분석
3. 지표 간 상충 신호가 있었는지 확인
4. 향후 지표 가중치 조정에 대한 제안

**입력 데이터:** 시그널 점수, 지표별 점수, KOSPI 변동률, 장 후 뉴스, 정성 분석

**LLM 설정:** `max_output_tokens=1024`, `temperature=0.3`

**Fallback:** `"예측 복기 분석 실패 (점수: {score}). 지표별 적중률을 수동으로 확인하세요."`

#### 4.2.2 BlindSpotAgent (사각지대 분석)

**파일:** `alphapulse/feedback/agents/blind_spot.py`

**역할:** 투자 시스템 감사관. 현 시스템이 놓친 요인 식별.

**프롬프트 페르소나:** "투자 시스템 감사관"

**분석 항목:**

1. 11개 지표가 커버하지 못하는 요인에 집중
2. 정치 이벤트, 규제 변화, 실적 발표, 지정학 등 비정량 요인
3. 구체적으로 어떤 이벤트/변수가 시장에 영향을 줬는지 명시
4. 시스템 개선을 위한 새 지표 후보 제안

**LLM 설정:** `max_output_tokens=1024`, `temperature=0.3`

**Fallback:** `"사각지대 분석 실패 (점수: {score}). 비정량 요인을 수동으로 확인하세요."`

#### 4.2.3 ExternalFactorAgent (외부 변수 분석)

**파일:** `alphapulse/feedback/agents/external_factor.py`

**역할:** 글로벌 매크로 전략가. 외부 요인 식별.

**프롬프트 페르소나:** "글로벌 매크로 전략가"

**분석 항목:**

1. 미국 정책, 지정학, 경제 이벤트, 실적 시즌, 글로벌 유동성 등 외부 요인에 집중
2. 해당 외부 요인이 KOSPI에 미친 구체적 영향 경로 설명
3. 현 시스템이 이 요인을 포착할 수 있었는지 평가
4. 향후 모니터링 포인트 제안

**LLM 설정:** `max_output_tokens=1024`, `temperature=0.3`

**Fallback:** `"외부 변수 분석 실패 (점수: {score}). 글로벌 매크로 요인을 수동으로 확인하세요."`

#### 4.2.4 SeniorFeedbackAgent (시니어 종합 피드백)

**파일:** `alphapulse/feedback/agents/senior_feedback.py`

**역할:** CIO(최고투자책임자). 3개 분석 결과를 종합하여 구조화된 피드백 생성.

**프롬프트 페르소나:** "CIO(최고투자책임자)"

**메서드:** `synthesize(signal, blind_spot, prediction_review, external_factor)`

**출력 구조 (5개 섹션 필수):**

1. `[예측 성공/실패 핵심 원인]`
2. `[놓친 변수 요약]`
3. `[시스템 개선 제안]`
4. `[내일 주의 포인트]`
5. `[지표별 신뢰도 코멘트]`

**LLM 설정:** `max_output_tokens=1536`, `temperature=0.3`

**Fallback:** `"종합 피드백 생성 실패 (점수: {score}, {signal_label}). 개별 분석 결과를 직접 확인하세요."`

### 4.3 뉴스 수집기

**클래스:** `NewsCollector` (`alphapulse/feedback/news_collector.py`)

**데이터 소스:** 네이버 금융 메인뉴스 (`https://finance.naver.com/news/mainnews.naver`)

- HTTP 클라이언트: `httpx.AsyncClient` (timeout=15초)
- 최대 수집 건수: `Config().FEEDBACK_NEWS_COUNT` (기본값 10)
- HTML 파싱: `BeautifulSoup` (html.parser)

**수집 필드 (기사별):**

```python
{
    "title": str,      # 기사 제목
    "source": str,     # 언론사
    "published": str,  # 발행 시간
    "summary": str,    # 요약 (최대 200자)
    "url": str,        # 기사 URL
}
```

**메서드:** `async collect_market_news(date=None)` -> `{"collected_at": str, "articles": list[dict]}`

실패 시 빈 `articles` 리스트를 반환한다 (예외를 전파하지 않음).

---

## 5. 피드백 저장소

### 5.1 FeedbackStore

**클래스:** `FeedbackStore` (`alphapulse/core/storage/feedback.py`)

**DB 엔진:** SQLite (`sqlite3`)

**DB 파일 경로:** `Config().DATA_DIR / "feedback.db"` (기본값: `data/feedback.db`)

생성자에서 `Path(db_path).parent.mkdir(parents=True, exist_ok=True)`로 상위 디렉토리를 자동 생성한다.

### 5.2 테이블 스키마

**테이블명:** `signal_feedback`

| 컬럼 | 타입 | 설명 | 비고 |
|---|---|---|---|
| `date` | `TEXT` | 날짜 (YYYYMMDD) | **PRIMARY KEY** |
| `score` | `REAL` | 종합 Market Pulse 점수 | |
| `signal` | `TEXT` | 시황 시그널 라벨 | 예: "매수 우위 (Moderately Bullish)" |
| `indicator_scores` | `TEXT` | 11개 지표별 점수 (JSON) | `json.dumps()` |
| `kospi_close` | `REAL` | KOSPI 종가 | |
| `kospi_change_pct` | `REAL` | KOSPI 등락률 (%) | |
| `kosdaq_close` | `REAL` | KOSDAQ 종가 | |
| `kosdaq_change_pct` | `REAL` | KOSDAQ 등락률 (%) | |
| `return_1d` | `REAL` | 1일 수익률 (%) | |
| `return_3d` | `REAL` | 3일 수익률 (%) | |
| `return_5d` | `REAL` | 5일 수익률 (%) | |
| `hit_1d` | `INTEGER` | 1일 적중 (1/0) | |
| `hit_3d` | `INTEGER` | 3일 적중 (1/0) | |
| `hit_5d` | `INTEGER` | 5일 적중 (1/0) | |
| `post_analysis` | `TEXT` | 사후 분석 결과 (JSON) | |
| `news_summary` | `TEXT` | 뉴스 요약 | |
| `blind_spots` | `TEXT` | 발견된 사각지대 (JSON) | |
| `evaluated_at` | `REAL` | 평가 완료 시각 (Unix timestamp) | |
| `created_at` | `REAL` | 생성 시각 (Unix timestamp) | |

### 5.3 주요 메서드

| 메서드 | 설명 | SQL 패턴 |
|---|---|---|
| `save_signal(date, score, signal, indicator_scores)` | 시그널 저장 (UPSERT) | `INSERT ... ON CONFLICT(date) DO UPDATE` |
| `get(date)` | 특정 날짜 레코드 조회 | `SELECT * WHERE date = ?` |
| `update_result(date, kospi_close, ...)` | 시장 결과 업데이트 + `evaluated_at` 기록 | `UPDATE ... WHERE date = ?` |
| `update_analysis(date, post_analysis, news_summary, blind_spots)` | 사후 분석 결과 저장 | `UPDATE ... WHERE date = ?` |
| `update_returns(date, return_3d, hit_3d, return_5d, hit_5d)` | 3일/5일 수익률 부분 업데이트 | 동적 `SET` 절 구성 |
| `get_recent(days=30)` | 최근 N건 조회 (날짜 내림차순) | `ORDER BY date DESC LIMIT ?` |
| `get_pending_evaluation()` | 미평가 레코드 조회 | `WHERE return_1d IS NULL ORDER BY date ASC` |
| `get_yesterday()` | 전일(두 번째로 최근) 레코드 | `ORDER BY date DESC LIMIT 1 OFFSET 1` |

**주의사항:**

- `save_signal()`은 UPSERT 패턴을 사용한다. 같은 날짜에 중복 호출해도 최신 값으로 갱신된다.
- `update_returns()`는 지정된 필드만 부분 업데이트한다. `None`인 파라미터는 SQL에 포함되지 않는다.
- `get_recent(days)`의 `days` 파라미터는 날짜 기간이 아니라 **레코드 건수 상한**이다 (`LIMIT ?`).

---

## 6. 피드백 -> AI 종합 판단 연결

### 6.1 피드백 요약 생성

**클래스:** `FeedbackSummarizer` (`alphapulse/feedback/summarizer.py`)

#### `generate_ai_context(days=30)`

AI 에이전트 프롬프트에 주입할 피드백 요약 텍스트를 생성한다.

**데이터 없을 때:**

```
=== 피드백 컨텍스트 ===
피드백 데이터 부족 (평가된 시그널 없음)
```

**데이터 있을 때 출력 형식:**

```
=== 피드백 컨텍스트 (최근 30일 기준) ===

[적중률]
전체: 1일 70% (10건) | 3일 65% (8건) | 5일 60% (6건)
상관계수: 0.45 (시그널 강도<->1일 수익률)

[지표별 신뢰도] (극단값 기준)
  높음: investor_flow 80% (5건)
  보통: global_market 60% (3건)
  낮음: vkospi 30% (4건)
```

**신뢰도 수준 분류:**

| 정확도 범위 | 라벨 |
|---|---|
| >= 0.7 | "높음" |
| >= 0.5 | "보통" |
| < 0.5 | "낮음" |

지표별 정확도는 내림차순 정렬된다.

### 6.2 AI 에이전트에서의 활용

**MarketCommentaryAgent** (`alphapulse/agents/commentary.py`)와 **SeniorSynthesisAgent** (`alphapulse/agents/synthesis.py`)는 `feedback_context: str | None = None` 파라미터를 받는다.

```python
# MarketCommentaryAgent
async def generate(self, pulse_result, content_summaries, feedback_context=None)

# SeniorSynthesisAgent
async def synthesize(self, pulse_result, content_summaries, commentary, feedback_context=None)
```

`feedback_context`가 제공되면, AI 프롬프트 내에 해당 텍스트가 삽입된다.

**MarketCommentaryAgent 프롬프트 구조:**

```
당신은 20년 경력의 시니어 투자 전략가입니다.
...
{content_context}
{feedback_context}        <-- 피드백 컨텍스트 삽입 위치
=== Market Pulse 데이터 ===
...
```

**SeniorSynthesisAgent 프롬프트 구조:**

```
당신은 20년 경력의 수석 투자 전략가(Senior Synthesis Agent)입니다.
...
{feedback_context}        <-- 피드백 컨텍스트 삽입 위치
=== 정량 분석 (Market Pulse) ===
...
```

이를 통해 AI는 과거 적중률과 지표 신뢰도를 참고하여 판단의 확신도(conviction)를 조정할 수 있다. 예를 들어, 적중률이 높은 지표가 강한 시그널을 보이면 확신도를 높이고, 적중률이 낮은 지표에 과도하게 의존하지 않는다.

---

## 7. 브리핑 연동

### 7.1 브리핑 파이프라인 내 피드백 위치

`BriefingOrchestrator.run_async()` (`alphapulse/briefing/orchestrator.py`) 메서드에서 피드백은 **총 4개 단계**에 걸쳐 통합된다.

```
[0-1] 피드백 수집/평가 ............. FeedbackCollector.collect_and_evaluate()
                                     FeedbackSummarizer.generate_ai_context()
                                     FeedbackSummarizer.format_daily_result()
[0-2] 뉴스 수집 ................... NewsCollector.collect_market_news()
[0-3] 사후 분석 ................... PostMarketOrchestrator.analyze()
                                     FeedbackStore.update_analysis()
[1]   정량 분석 ................... SignalEngine.run()
[2]   정성 분석 수집 .............. collect_recent_content()
[3]   AI Commentary + Synthesis ... feedback_context를 프롬프트에 주입
[4]   Format ...................... daily_result_msg를 정량 리포트에 추가
                                     weekly_summary를 종합 리포트에 추가 (월요일)
[5]   Telegram 전송
[6]   이력 저장
[7]   오늘 시그널 피드백 DB 기록 ... FeedbackStore.save_signal()
```

### 7.2 단계별 상세

#### [0-1] 피드백 수집/평가

`Config().FEEDBACK_ENABLED`가 `true`일 때만 실행된다.

1. `FeedbackStore` 인스턴스 생성
2. `FeedbackCollector.collect_and_evaluate()` 호출 (`asyncio.to_thread()`로 sync 함수를 async 컨텍스트에서 실행)
3. `FeedbackSummarizer.generate_ai_context(Config().FEEDBACK_LOOKBACK_DAYS)`로 AI 프롬프트용 피드백 컨텍스트 생성
4. `FeedbackStore.get_yesterday()`로 전일 시그널 조회
5. `FeedbackSummarizer.format_daily_result(yesterday)`로 전일 결과 한 줄 메시지 생성

#### [0-2] 뉴스 수집

`FEEDBACK_ENABLED` **and** `FEEDBACK_NEWS_ENABLED`가 모두 `true`일 때만 실행된다.

`NewsCollector.collect_market_news()`를 async 호출하여 네이버 금융 뉴스를 수집한다.

#### [0-3] 사후 분석

전일 시그널이 존재하고 `return_1d`가 `None`이 아닌 경우에만 실행된다.

1. `PostMarketOrchestrator.analyze(yesterday, news, content_summaries)` 호출
2. 분석 결과를 `FeedbackStore.update_analysis()`로 DB에 저장
   - `post_analysis`: `senior_synthesis` 값
   - `news_summary`: 뉴스 제목 5건 (줄바꿈 결합)
   - `blind_spots`: `blind_spots` 값

#### [4] 포맷

- **정량 리포트:** `BriefingFormatter.format_quantitative(pulse_result, daily_result_msg=daily_result_msg)` -- 전일 결과 한 줄이 리포트 하단에 추가된다
- **종합 리포트 (월요일):** `FeedbackSummarizer.format_weekly_summary()`를 호출하여 주간 피드백 요약을 종합 리포트에 추가한다

#### [7] 오늘 시그널 기록

정량 분석 완료 후 `FeedbackStore.save_signal()`을 호출하여 오늘 시그널을 피드백 DB에 기록한다. 이 레코드는 다음 날 `collect_and_evaluate()` 실행 시 미평가 대상으로 조회된다.

### 7.3 텔레그램 메시지 포맷

#### 전일 결과 한 줄 (`format_daily_result`)

```
(적중) 어제 시그널 결과: 매수 우위(+36) -> KOSPI +1.2% (체크)
(미적중) 어제 시그널 결과: 매수 우위(+36) -> KOSPI -0.5% (엑스)
```

전일 시그널이 없거나 `return_1d`가 `None`이면 빈 문자열을 반환한다.

#### 주간 피드백 요약 (`format_weekly_summary`)

월요일에만 생성되며, 종합 리포트 하단에 추가된다.

```
<b>주간 피드백</b>
적중률: 1일 70% (5건) | 3일 60% (4건) | 5일 55% (3건)
최고 지표: investor_flow (80%) | 최저: vkospi (30%)
상관계수: 0.45
```

평가된 시그널이 없으면 빈 문자열을 반환한다.

---

## 8. 에러 처리 원칙

### 8.1 핵심 원칙

> **피드백 실패가 메인 브리핑 파이프라인을 중단시키면 안 된다.**

이 원칙은 `CLAUDE.md` 및 `.claude/rules/testing.md`에 명시되어 있으며, 코드 전반에 `try/except` 패턴으로 구현되어 있다.

### 8.2 브리핑 파이프라인의 try/except 패턴

`BriefingOrchestrator.run_async()`에서 피드백 관련 코드는 **4개의 독립적인 try/except 블록**으로 감싸져 있다:

```python
# [0-1] 피드백 수집/평가
if self.config.FEEDBACK_ENABLED:
    try:
        ...  # 피드백 수집 로직
    except Exception as e:
        logger.warning(f"피드백 수집 실패, 스킵: {e}")

# [0-2] 뉴스 수집
if self.config.FEEDBACK_ENABLED and self.config.FEEDBACK_NEWS_ENABLED:
    try:
        ...  # 뉴스 수집 로직
    except Exception as e:
        logger.warning(f"뉴스 수집 실패, 스킵: {e}")

# [0-3] 사후 분석
if self.config.FEEDBACK_ENABLED and yesterday is not None and ...:
    try:
        ...  # 사후 분석 로직
    except Exception as e:
        logger.warning(f"사후 분석 실패, 스킵: {e}")

# [7] 오늘 시그널 기록
if self.config.FEEDBACK_ENABLED:
    try:
        ...  # 시그널 기록 로직
    except Exception as e:
        logger.warning(f"시그널 피드백 기록 실패: {e}")
```

**각 블록의 독립성:** 한 블록이 실패해도 다른 블록과 메인 파이프라인([1]~[6])은 정상 실행된다. 피드백 컨텍스트 변수(`feedback_context`, `daily_result_msg` 등)는 초기값(`None`, `""`)이 설정되어 있어, 피드백 실패 시 해당 값이 그대로 유지된다.

### 8.3 에이전트 수준의 에러 처리

모든 피드백 에이전트는 `_fallback()` 메서드를 제공한다:

| 에이전트 | Fallback 동작 |
|---|---|
| `PredictionReviewAgent` | 분석 실패 안내 문자열 반환 |
| `BlindSpotAgent` | 분석 실패 안내 문자열 반환 |
| `ExternalFactorAgent` | 분석 실패 안내 문자열 반환 |
| `SeniorFeedbackAgent` | 종합 실패 안내 문자열 반환 |

LLM 호출(`_call_llm`)에서 예외가 발생하면 에이전트 내부에서 `_fallback()`을 호출하여 기본 메시지를 반환한다. 예외를 상위로 전파하지 않는다.

### 8.4 뉴스 수집기의 에러 처리

`NewsCollector.collect_market_news()`는 HTTP 실패 또는 파싱 실패 시 빈 결과를 반환한다:

```python
return {"collected_at": datetime.now().isoformat(), "articles": []}
```

---

## 9. 운영 주기

### 9.1 일일 실행 흐름

피드백 시스템은 독립 실행이 아니라 **브리핑 파이프라인의 일부**로 매일 자동 실행된다.

| 시점 | 동작 | 실행 조건 |
|---|---|---|
| 매일 아침 (기본 08:30) | 미평가 시그널 수집/평가 | `FEEDBACK_ENABLED=true` |
| 매일 아침 (기본 08:30) | 뉴스 수집 | `FEEDBACK_ENABLED=true` **and** `FEEDBACK_NEWS_ENABLED=true` |
| 매일 아침 (기본 08:30) | 사후 분석 실행 | 전일 시그널 존재 **and** `return_1d` 확정 |
| 매일 아침 (기본 08:30) | 오늘 시그널 피드백 DB 기록 | `FEEDBACK_ENABLED=true` |
| 월요일 아침 | 주간 피드백 요약 생성 | `FEEDBACK_ENABLED=true` |

**스케줄링:** `run_scheduler()` (`alphapulse/briefing/scheduler.py`)가 매일 지정 시간(`BRIEFING_TIME`, 기본 `08:30`)에 `BriefingOrchestrator.run()`을 호출한다. tolerance는 1분이다.

### 9.2 CLI 수동 실행

**명령어 그룹:** `alphapulse feedback`

| 명령어 | 설명 |
|---|---|
| `alphapulse feedback evaluate` | 미확정 시그널에 대해 시장 결과 수집 + 적중 판정 |
| `alphapulse feedback report --days 30` | 적중률 리포트 (1일/3일/5일 적중률 + 상관계수) |
| `alphapulse feedback indicators --days 30` | 지표별 적중률 순위 (극단값 기준, 막대 그래프) |
| `alphapulse feedback history --days 7` | 최근 시그널 vs 실제 결과 테이블 |
| `alphapulse feedback analyze --date YYYY-MM-DD` | 특정 날짜 사후 분석 (현재 "Phase B에서 구현 예정" 메시지 출력) |

### 9.3 설정값 (환경 변수)

| 환경 변수 | 기본값 | 설명 |
|---|---|---|
| `FEEDBACK_ENABLED` | `true` | 피드백 시스템 전체 활성화 |
| `FEEDBACK_LOOKBACK_DAYS` | `30` | AI 프롬프트에 주입할 피드백 분석 기간 (일) |
| `FEEDBACK_NEWS_ENABLED` | `true` | 장 후 뉴스 수집 활성화 |
| `FEEDBACK_NEWS_COUNT` | `10` | 뉴스 최대 수집 건수 |

### 9.4 데이터 흐름 요약

```
[D일 08:30]
  1. 정량 분석 실행 -> score, signal, indicator_scores 산출
  2. FeedbackStore.save_signal(D일) -- 오늘 시그널 기록
     (이 레코드의 return_1d는 NULL)

[D+1일 08:30]
  1. FeedbackCollector.collect_and_evaluate()
     -> get_pending_evaluation() -- D일 레코드 조회 (return_1d IS NULL)
     -> collect_market_result(D일) -- D일 KOSPI/KOSDAQ 결과 수집
     -> calculate_hit(D일 score, D일 return) -- 적중 판정
     -> update_result(D일, ...) -- 1일 수익률 + 적중 저장
     -> calculate_returns(D일, ...) -- 3일/5일 수익률 (가능한 경우)
  2. FeedbackSummarizer.generate_ai_context(30)
     -> FeedbackEvaluator.get_hit_rates(30) -- 적중률 계산
     -> FeedbackEvaluator.get_correlation(30) -- 상관계수
     -> FeedbackEvaluator.get_indicator_accuracy(30) -- 지표별 정확도
  3. PostMarketOrchestrator.analyze(D일 signal, news, content)
     -> PredictionReviewAgent / BlindSpotAgent / ExternalFactorAgent (병렬)
     -> SeniorFeedbackAgent (종합)
     -> FeedbackStore.update_analysis(D일, ...)
  4. AI Commentary + Synthesis에 feedback_context 주입
  5. FeedbackStore.save_signal(D+1일) -- 오늘 시그널 기록
```

---

## 10. 테스트 구조

피드백 시스템의 테스트는 `tests/feedback/` 디렉토리에 위치한다.

| 테스트 파일 | 대상 모듈 | 주요 검증 항목 |
|---|---|---|
| `test_store.py` | `FeedbackStore` | save_signal, update_result, update_analysis, get_recent, get_pending_evaluation, get_yesterday, update_returns |
| `test_collector.py` | `FeedbackCollector`, `calculate_hit` | Bullish/Bearish/Neutral 적중 판정, 시장 결과 수집(mock), 수익률 계산, collect_and_evaluate 파이프라인 |
| `test_evaluator.py` | `FeedbackEvaluator` | 적중률 계산, 빈 데이터 처리, 지표별 정확도, 상관계수 (5건 미만 시 None) |
| `test_summarizer.py` | `FeedbackSummarizer` | AI 컨텍스트 생성, 빈 데이터 처리, 전일 결과 포맷, 적중/미적중 이모지, 주간 요약 |
| `test_agents.py` | 4개 에이전트 + `PostMarketOrchestrator` | LLM mock으로 분석 실행, 오케스트레이터 병렬/순차 파이프라인 |
| `test_news_collector.py` | `NewsCollector` | HTML 파싱, HTTP mock, 빈 결과 처리 |

**테스트 실행:**

```bash
pytest tests/feedback/ -v
```

**테스트 규칙:**

- DB 테스트: `tmp_path` fixture 사용 (실제 DB 파일 생성하지 않음)
- LLM 테스트: `@patch("...._call_llm")` 으로 mock
- async 테스트: `@pytest.mark.asyncio` 사용 (`asyncio_mode = "auto"`)
