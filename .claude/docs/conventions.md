# Detailed Conventions

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
