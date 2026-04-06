# AlphaPulse

AI 기반 투자 인텔리전스 플랫폼. 정량(Market Pulse) + 정성(Content Intelligence) + AI 종합 판단.

## Quick Start

```bash
pip install -e ".[dev]"
ap --version
ap market pulse
ap briefing --no-telegram
```

## Architecture

- `alphapulse/market/` — 정량 분석 (KMP 마이그레이션). **Sync** (requests, pykrx).
- `alphapulse/content/` — 정성 분석 (BlogPulse 마이그레이션). **Async** (httpx, crawl4ai).
- `alphapulse/briefing/` — 일일 브리핑 통합. Sync entry → `run_async()` → await AI calls.
- `alphapulse/agents/` — MarketCommentaryAgent (정량 해설), SeniorSynthesisAgent (종합 판단).
- `alphapulse/core/` — 공유 인프라 (config, notifier, storage, constants).

## Testing

```bash
pytest tests/ -v                     # 전체 (235개)
pytest tests/market/ -v              # 정량 분석만
pytest tests/content/ -v             # 정성 분석만
pytest tests/briefing/ -v            # 브리핑만
pytest tests/agents/ -v              # AI 에이전트만
pytest tests/ --cov=alphapulse       # 커버리지
```

## Key Rules

- Market pipeline은 **SYNC** (requests, pykrx). Content pipeline은 **ASYNC** (httpx, crawl4ai).
- `asyncio.run()` 중첩 호출 금지. `run_async()` 내에서는 반드시 `await` 사용.
- `BriefingOrchestrator.run()` (sync) → `run_async()` (async) 패턴. CLI entry에서만 `asyncio.run()`.
- LLM 호출은 `asyncio.to_thread()`로 sync genai API를 non-blocking 래핑.
- Config은 환경변수 기반 (.env). 모든 설정은 `Config` 클래스 인스턴스로 접근.
- `INDICATOR_NAMES`는 `core/constants.py`에 공유 정의 (DRY).
- AI는 Google Gemini API (`google-adk ~= 1.27.2`). 버전 호환성 주의 (1.27.0 yanked).

## CLI Commands

```
ap market pulse [--date] [--period]          # 종합 시황
ap market {investor,program,sector,macro,fund} [--date]  # 상세 분석
ap market report [--date] [--output]         # HTML 리포트
ap market history [--days]                   # 과거 이력
ap content monitor [--daemon] [--force-latest N] [--no-telegram]
ap content test-telegram                     # 연결 테스트
ap briefing [--no-telegram] [--daemon] [--time HH:MM]
ap commentary [--date]                       # AI 시장 해설
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
- 프롬프트: 모듈 상단에 `PROMPT_TEMPLATE` 상수로 정의.
- 실패 시: `_fallback()` 메서드로 graceful degradation. 예외 전파하지 않음.
- 테스트: `@patch("module.Class._call_llm")` 으로 LLM mock.

## Storage Conventions

- SQLite 기반. `__init__(self, db_path)` 패턴.
- 테이블 생성: `__init__`에서 `CREATE TABLE IF NOT EXISTS`.
- 테스트: `tmp_path` fixture 사용, 실제 DB 파일 생성하지 않음.

## Custom Commands

- `/test [module]` — 테스트 실행 (전체 또는 특정 모듈)
- `/coverage` — 커버리지 리포트
- `/push [message]` — 커밋 + 푸시
- `/status` — 프로젝트 현황 (git + 테스트)
