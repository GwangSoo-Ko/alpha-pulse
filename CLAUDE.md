# AlphaPulse

AI 기반 투자 인텔리전스 플랫폼. 정량(Market Pulse) + 정성(Content Intelligence) + AI 종합 판단 + 피드백 학습.

## Architecture

- `alphapulse/market/` — 정량 분석. **Sync** (requests, pykrx). 11개 지표.
- `alphapulse/content/` — 정성 분석 (BlogPulse). **Async** (httpx, crawl4ai).
- `alphapulse/briefing/` — 일일 브리핑. 피드백 수집 → 정량+정성+AI → 포맷 → 전송.
- `alphapulse/agents/` — MarketCommentaryAgent, SeniorSynthesisAgent.
- `alphapulse/feedback/` — 피드백 시스템. 시장 결과 수집, 적중률, 사후 분석 멀티에이전트.
- `alphapulse/core/` — 공유 인프라 (config, notifier, storage, constants).
- `alphapulse/trading/` — **자동 매매 시스템**. 9개 서브모듈:
  - `core/` — 데이터 모델, Protocol 인터페이스, 캘린더, 비용 모델, 감사 추적.
  - `data/` — 종목 데이터 수집 (OHLCV, 재무, 수급, 공매도). **Sync**.
  - `screening/` — 20개 팩터, 필터, 멀티팩터 랭킹. **Sync**.
  - `strategy/` — 4개 전략(momentum/value/quality_momentum/topdown_etf) + AI 종합 판단. **Sync** (AI만 Async).
  - `portfolio/` — 포트폴리오 최적화, 리밸런싱. **Sync**.
  - `risk/` — VaR, 드로다운, 스트레스 테스트. **Sync**.
  - `backtest/` — 백테스트 엔진, SimBroker, 결과 저장/리포트. **Sync**.
  - `broker/` — 한투 API (KISBroker/PaperBroker). **Sync** (requests).
  - `orchestrator/` — 5-phase 파이프라인, 스케줄러. **Async** (CLI entry만 asyncio.run).

## Key Rules

- Market = **SYNC** (requests, pykrx). Content/Feedback agents = **ASYNC** (httpx, google-adk).
- Trading = **SYNC** (data, screening, strategy, portfolio, risk, backtest, broker). **Async**: AI synthesizer + orchestrator.
- `asyncio.run()`은 CLI entry에서만. 내부에서는 `await`. 중첩 호출 **금지**.
- LLM 호출: `asyncio.to_thread()`로 sync genai API를 non-blocking 래핑.
- Config: `Config()` 인스턴스 사용. 모듈 레벨 상수 대신.
- AI: Google Gemini API (`google-adk ~= 1.27.2`).
- 피드백 코드는 항상 try/except. 피드백 실패가 메인 브리핑을 중단하면 안 됨.
- `INDICATOR_NAMES`는 `core/constants.py`에 공유 정의 (DRY).
- Trading Protocol 기반: `Broker`, `StrategyProtocol`, `RiskChecker`, `DataProvider` 인터페이스.
- 리스크 리밋은 AI/전략/사용자 모두 오버라이드 불가.

## File Conventions

- 새 모듈: TDD (test first → red → implement → green → commit)
- 한 파일에 한 클래스/한 책임. 200줄 넘으면 분리 검토.
- Commit: 기능 단위 incremental commit. `/push`로 CI 게이트 포함 푸시.

## Testing

```bash
pytest tests/ -v                     # 전체 (843개)
pytest tests/{market,content,briefing,agents,feedback}/ -v  # 기존 모듈별
pytest tests/trading/ -v             # 자동 매매 시스템 (471개)
pytest tests/ --cov=alphapulse       # 커버리지
```

## Quality Gates (자동 강제)

- **Ruff 린터**: Write/Edit 후 PostToolUse hook이 자동 실행. 린트 에러 시 수정 필요.
- **asyncio.run() 검사**: Write/Edit 후 CLI entry 외 asyncio.run() 사용 차단.
- **위험 명령 차단**: PreToolUse hook이 force push, reset --hard, rm -rf 등 차단.
- **컨텍스트 압축 복구**: SessionStart hook이 compact 후 핵심 규칙 재주입.
- **작업 완료 검증 (Stop hook)**: 코드 변경 시 → 1) 테스트 실행 2) 문서 최신화 3) 커밋 확인. **푸시는 사용자가 `/push`로 명시적 요청 시에만.**
- 설정: `pyproject.toml [tool.ruff]`, `.claude/hooks/`, `.claude/settings.json`

## Known Failures (실수 기록 — 에이전트가 반복한 실수)

- `asyncio.run()`을 async 함수 내부에서 호출하여 RuntimeError 발생한 적 있음.
- import 정렬 미준수 (isort). ruff I001 규칙으로 자동 강제 중.
- 미사용 import를 남겨두어 F401 경고 발생. ruff가 자동 감지.

## Detailed Docs

- CLI 명령어: `.claude/docs/cli-commands.md`
- AI Agent/Storage/Feedback 컨벤션: `.claude/docs/conventions.md`
- Trading System 가이드: `docs/trading-system-guide.md`
- Trading System 설계: `docs/superpowers/specs/2026-04-09-trading-system-design.md`

## Custom Commands

- `/test [module]` — 테스트 실행
- `/coverage` — 커버리지 리포트
- `/push [message]` — CI 게이트 + 커밋 + 푸시
- `/status` — 프로젝트 현황
