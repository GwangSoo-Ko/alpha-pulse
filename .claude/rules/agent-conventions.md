---
paths:
  - "alphapulse/agents/**/*.py"
  - "alphapulse/feedback/agents/**/*.py"
---

# AI Agent 컨벤션

- `__init__(self)` → `Config()` 인스턴스 생성
- LLM: `google.genai.Client`, `asyncio.to_thread()`로 래핑
- 프롬프트: 모듈 상단에 `PROMPT` 또는 `PROMPT_TEMPLATE` 상수 정의
- 실패 시: `_fallback()` 메서드로 graceful degradation. 예외 전파 금지.
- 테스트: `@patch("module.Class._call_llm")`으로 LLM mock
- 피드백: `feedback_context: str | None = None` 파라미터로 프롬프트 주입
