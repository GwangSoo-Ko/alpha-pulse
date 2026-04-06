# AlphaPulse

AI 기반 투자 인텔리전스 플랫폼. 정량(Market Pulse) + 정성(Content Intelligence) + AI 종합 판단 + 피드백 학습.

## Quick Start

```bash
pip install -e ".[dev]"
ap --version
ap market pulse
ap briefing --no-telegram
ap feedback report
```

## Architecture

- `alphapulse/market/` — 정량 분석. **Sync** (requests, pykrx). 11개 지표.
- `alphapulse/content/` — 정성 분석 (BlogPulse). **Async** (httpx, crawl4ai).
- `alphapulse/briefing/` — 일일 브리핑. 피드백 수집 → 정량+정성+AI → 포맷 → 전송.
- `alphapulse/agents/` — MarketCommentaryAgent, SeniorSynthesisAgent (feedback_context 지원).
- `alphapulse/feedback/` — 피드백 시스템. 시장 결과 수집, 적중률, 사후 분석 멀티에이전트.
- `alphapulse/core/` — 공유 인프라 (config, notifier, storage, constants).

## Testing

```bash
pytest tests/ -v                     # 전체 (275개)
pytest tests/market/ -v              # 정량 분석
pytest tests/content/ -v             # 정성 분석
pytest tests/briefing/ -v            # 브리핑
pytest tests/agents/ -v              # 브리핑 AI 에이전트
pytest tests/feedback/ -v            # 피드백 시스템
pytest tests/ --cov=alphapulse       # 커버리지
```

## Key Rules

- Market pipeline은 **SYNC** (requests, pykrx). Content/Feedback agents는 **ASYNC** (httpx, google-adk).
- `asyncio.run()` 중첩 호출 금지. `run_async()` 내에서는 반드시 `await` 사용.
- `BriefingOrchestrator.run()` (sync) → `run_async()` (async) 패턴. CLI entry에서만 `asyncio.run()`.
- LLM 호출은 `asyncio.to_thread()`로 sync genai API를 non-blocking 래핑.
- Config은 환경변수 기반 (.env). 모든 설정은 `Config` 클래스 인스턴스로 접근.
- `INDICATOR_NAMES`는 `core/constants.py`에 공유 정의 (DRY).
- AI는 Google Gemini API (`google-adk ~= 1.27.2`). 버전 호환성 주의 (1.27.0 yanked).
- 피드백 코드는 항상 try/except 래핑. 피드백 실패가 메인 브리핑을 중단하면 안 됨.

## CLI Commands

```
ap market pulse [--date] [--period]          # 종합 시황 (11개 지표)
ap market {investor,program,sector,macro,fund} [--date]  # 상세 분석
ap market report [--date] [--output]         # HTML 리포트
ap market history [--days]                   # 과거 이력
ap content monitor [--daemon] [--force-latest N] [--no-telegram]
ap content test-telegram                     # 연결 테스트
ap briefing [--no-telegram] [--daemon] [--time HH:MM]
ap commentary [--date]                       # AI 시장 해설
ap feedback evaluate                         # 시그널 평가 (시장 결과 수집)
ap feedback report [--days]                  # 적중률 리포트
ap feedback indicators [--days]              # 지표별 적중률
ap feedback history [--days]                 # 시그널 vs 결과 테이블
ap feedback analyze [--date]                 # 사후 분석
ap cache clear                               # 캐시 초기화
```

## File Conventions

- 새 모듈: TDD (test first → red → implement → green → commit)
- Config 접근: `Config()` 인스턴스 사용, 모듈 레벨 상수 대신
- Commit: 기능 단위 incremental commit
- 한 파일에 한 클래스/한 책임. 파일이 200줄 넘으면 분리 검토.

## Async/Sync Rules

- `alphapulse/market/` — SYNC only (requests, pykrx). 절대 async 사용 안 함.
- `alphapulse/content/`, `alphapulse/feedback/agents/` — ASYNC (httpx, google-adk).
- `asyncio.run()`은 CLI entry point에서만 호출. 내부에서는 `await` 사용.
- sync API를 async에서 호출할 때: `await asyncio.to_thread(sync_func, args)`.
- LLM 호출 패턴: `async def _call_llm()` → `asyncio.to_thread(client.generate_content)`.

## AI Agent Conventions

- 모든 에이전트: `__init__(self)` → `Config()` 인스턴스 생성.
- LLM 호출: `google.genai.Client` 사용, `asyncio.to_thread()`로 래핑.
- 프롬프트: 모듈 상단에 `PROMPT` 또는 `PROMPT_TEMPLATE` 상수로 정의.
- 실패 시: `_fallback()` 메서드로 graceful degradation. 예외 전파하지 않음.
- 테스트: `@patch("module.Class._call_llm")` 으로 LLM mock.
- 피드백 지원: `feedback_context: str | None = None` 파라미터로 프롬프트 주입.

## Storage Conventions

- SQLite 기반. `__init__(self, db_path)` 패턴.
- 테이블 생성: `__init__`에서 `CREATE TABLE IF NOT EXISTS`.
- 테스트: `tmp_path` fixture 사용, 실제 DB 파일 생성하지 않음.
- DB 파일 위치: `data/` 디렉토리 (cache.db, history.db, feedback.db).

## Feedback System

- 브리핑 파이프라인 시작 시 자동 실행 (FEEDBACK_ENABLED=true).
- 수집: FeedbackCollector → pykrx로 KOSPI/KOSDAQ 종가 + 1d/3d/5d 수익률.
- 평가: FeedbackEvaluator → 적중률, 상관계수, 지표별 극단값 정확도.
- AI 주입: FeedbackSummarizer → 적중률/신뢰도 텍스트를 AI 프롬프트에 삽입.
- 사후 분석: 4개 에이전트 병렬 실행 (BlindSpot, PredictionReview, ExternalFactor → SeniorFeedback).
- 텔레그램: 매일 전일 결과 한 줄, 월요일 주간 요약.

## Custom Commands

- `/test [module]` — 테스트 실행 (전체 또는 market/content/briefing/agents/feedback)
- `/coverage` — 커버리지 리포트
- `/push [message]` — 커밋 + 푸시
- `/status` — 프로젝트 현황 (git + 테스트)
