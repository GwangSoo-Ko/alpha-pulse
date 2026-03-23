# AlphaPulse

AI 기반 투자 인텔리전스 플랫폼.

## Quick Start

pip install -e ".[dev]"
ap --version
ap market pulse
ap briefing --no-telegram

## Architecture

- `alphapulse/market/` — 정량 분석 (KMP 마이그레이션). Sync.
- `alphapulse/content/` — 정성 분석 (BlogPulse 마이그레이션). Async.
- `alphapulse/briefing/` — 일일 브리핑 통합. Sync entry, async AI calls.
- `alphapulse/agents/` — AI 에이전트 (MarketCommentaryAgent, SeniorSynthesisAgent).
- `alphapulse/core/` — 공유 인프라 (config, notifier, storage, constants).

## Testing

pytest tests/ -v                    # 전체
pytest tests/market/ -v             # 정량 분석만
pytest tests/content/ -v            # 정성 분석만
pytest tests/briefing/ -v           # 브리핑만

## Key Rules

- Market pipeline is SYNC (requests, pykrx). Content pipeline is ASYNC (httpx, crawl4ai).
- Never nest asyncio.run() calls. Use await inside async functions.
- BriefingOrchestrator.run_async() is the single async entry point.
- Config via environment variables (.env file). See .env.example.
- AI uses Google Gemini API (google-adk ~= 1.27.2).
- INDICATOR_NAMES shared constant in core/constants.py (DRY).
