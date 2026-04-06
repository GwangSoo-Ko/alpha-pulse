---
description: 테스트 실행 (전체 또는 특정 모듈)
argument-hint: "[module] e.g. market, content, briefing, agents, feedback"
---

Run the test suite. If an argument is provided, run only that module's tests.

```bash
# If argument provided:
pytest tests/$ARGUMENTS/ -v --tb=short

# If no argument:
pytest tests/ -v --tb=short
```

Report: total passed/failed count and any failures.
