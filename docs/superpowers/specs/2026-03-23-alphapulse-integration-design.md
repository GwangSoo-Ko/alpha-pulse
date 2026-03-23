# AlphaPulse Integration Design Spec

> **Date:** 2026-03-23
> **Status:** Approved
> **Source PRD:** `AlphaPulse-PRD.md` (v0.2)

## Summary

Two independent Korean market analysis projects are merged into a single monorepo platform:

- **K-Market Pulse** (quantitative: 10 indicators, scoring) → `alphapulse/market/`
- **BlogPulse** (qualitative: multi-agent AI blog/channel analysis) → `alphapulse/content/`
- **New integration layer** (daily briefing, AI commentary, synthesis) → `alphapulse/briefing/` + `alphapulse/agents/`

## Design Decision: PRD as Spec

The PRD (`AlphaPulse-PRD.md`) contains complete architectural specification including:
- Module mapping tables (§4.2)
- Directory structure (§6.1)
- Data flow diagrams (§6.2)
- CLI command reference (§8)
- Environment variables (§9)
- Migration phases (§10)

This document adopts the PRD as the authoritative design specification.

## Key Constraints (from PRD Addendum)

1. **Sync/Async isolation** — KMP is sync (requests), BlogPulse is async (httpx). No nested `asyncio.run()`.
2. **Incremental migration** — Move one module at a time, test immediately. No bulk moves.
3. **Config namespace** — Resolve key collisions (MAX_RETRIES, LOG_FILE) with shared defaults.
4. **Crawling rate limit** — Stagger quantitative (08:00) and synthesis (08:30) pipelines.
5. **Google ADK version pinning** — Pin in pyproject.toml, test on updates.
6. **Test isolation** — `tests/market/` and `tests/content/` run independently.
7. **Phase gate** — Each phase must be verified independently before proceeding.

## Implementation Phases

See PRD §10 for detailed phase breakdown (Phase 1-6, ~6 days).
