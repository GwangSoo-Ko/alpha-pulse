# AlphaPulse

AI 기반 투자 인텔리전스 플랫폼. 정량(Market Pulse) + 정성(Content Intelligence) + AI 종합 판단 + 피드백 학습.

## Architecture

- `alphapulse/market/` — 정량 분석. **Sync** (requests, pykrx). 11개 지표.
- `alphapulse/content/` — 정성 분석 (BlogPulse). **Async** (httpx, crawl4ai).
- `alphapulse/briefing/` — 일일 브리핑. 피드백 수집 → 정량+정성+AI → 포맷 → 전송.
- `alphapulse/agents/` — MarketCommentaryAgent, SeniorSynthesisAgent.
- `alphapulse/feedback/` — 피드백 시스템. 시장 결과 수집, 적중률, 사후 분석 멀티에이전트.
- `alphapulse/core/` — 공유 인프라 (config, notifier, storage, constants).

## Key Rules

- Market = **SYNC** (requests, pykrx). Content/Feedback agents = **ASYNC** (httpx, google-adk).
- `asyncio.run()`은 CLI entry에서만. 내부에서는 `await`. 중첩 호출 **금지**.
- LLM 호출: `asyncio.to_thread()`로 sync genai API를 non-blocking 래핑.
- Config: `Config()` 인스턴스 사용. 모듈 레벨 상수 대신.
- AI: Google Gemini API (`google-adk ~= 1.27.2`).
- 피드백 코드는 항상 try/except. 피드백 실패가 메인 브리핑을 중단하면 안 됨.
- `INDICATOR_NAMES`는 `core/constants.py`에 공유 정의 (DRY).

## File Conventions

- 새 모듈: TDD (test first → red → implement → green → commit)
- 한 파일에 한 클래스/한 책임. 200줄 넘으면 분리 검토.
- Commit: 기능 단위 incremental commit. `/push`로 CI 게이트 포함 푸시.

## Testing

```bash
pytest tests/ -v                     # 전체 (275개)
pytest tests/{market,content,briefing,agents,feedback}/ -v  # 모듈별
pytest tests/ --cov=alphapulse       # 커버리지
```

## Quality Gates (자동 강제)

- **Ruff 린터**: Write/Edit 후 PostToolUse hook이 자동 실행. 린트 에러 시 수정 필요.
- **`/push` CI 게이트**: ruff check + pytest 통과해야만 커밋/푸시 진행.
- 설정: `pyproject.toml [tool.ruff]`, `.claude/hooks/ruff-check.sh`

## Known Failures (실수 기록 — 에이전트가 반복한 실수)

- `asyncio.run()`을 async 함수 내부에서 호출하여 RuntimeError 발생한 적 있음.
- import 정렬 미준수 (isort). ruff I001 규칙으로 자동 강제 중.
- 미사용 import를 남겨두어 F401 경고 발생. ruff가 자동 감지.

## Detailed Docs

- CLI 명령어: `.claude/docs/cli-commands.md`
- AI Agent/Storage/Feedback 컨벤션: `.claude/docs/conventions.md`

## Custom Commands

- `/test [module]` — 테스트 실행
- `/coverage` — 커버리지 리포트
- `/push [message]` — CI 게이트 + 커밋 + 푸시
- `/status` — 프로젝트 현황
