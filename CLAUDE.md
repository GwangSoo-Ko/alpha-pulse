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

- 마이그레이션 모듈: import 경로만 변경, 로직 유지
- 새 모듈: TDD (test first → red → implement → green → commit)
- Config 접근: `Config()` 인스턴스 사용, 모듈 레벨 상수 대신
- Commit: 기능 단위 incremental commit
