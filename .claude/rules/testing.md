---
paths:
  - "tests/**/*.py"
---

# 테스트 규칙

- 새 모듈은 TDD: test first → red → implement → green → commit
- DB 테스트: `tmp_path` fixture 사용, 실제 DB 파일 생성하지 않음
- LLM 테스트: `@patch("module.Class._call_llm")` 으로 mock
- async 테스트: `pytest-asyncio` 사용, `asyncio_mode = "auto"` 설정됨
- 피드백 테스트: 피드백 실패가 메인 파이프라인을 중단하지 않는지 반드시 검증
