---
paths:
  - "alphapulse/content/**/*.py"
  - "alphapulse/feedback/agents/**/*.py"
---

# Content/Feedback Agents: ASYNC 모듈

이 디렉토리는 **비동기(async) 코드**를 사용합니다.

- HTTP: `httpx` 사용 (requests 대신)
- LLM 호출: `asyncio.to_thread(client.generate_content)` 패턴
- `asyncio.run()`은 **절대 사용 금지** — 이미 async 컨텍스트 안이므로 `await` 사용
- sync 함수 호출 시: `await asyncio.to_thread(sync_func, args)`
