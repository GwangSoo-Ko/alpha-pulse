---
paths:
  - "alphapulse/market/**/*.py"
---

# Market 모듈: SYNC ONLY

이 디렉토리는 **동기(sync) 코드만** 허용합니다.

- `async def`, `await`, `asyncio` 사용 **금지**
- HTTP: `requests` 라이브러리만 사용 (httpx 금지)
- 주가: `pykrx` 라이브러리 사용
- `asyncio.run()`, `asyncio.to_thread()` 호출 금지
- 이 디렉토리에서 async 관련 import를 보면 즉시 제거할 것
