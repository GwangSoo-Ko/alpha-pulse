---
description: 코드 품질 점검 (가비지 컬렉션)
---

Run a code quality sweep. Check for common issues that accumulate over time.

## Checks to perform:

1. **Lint sweep**: `ruff check alphapulse/ --statistics` — 린트 위반 현황. 있으면 `ruff check --fix alphapulse/`로 자동 수정.

2. **Unused imports/variables**: ruff 결과 중 F401 (unused import), F841 (unused variable) 집중 확인.

3. **Test health**: `pytest tests/ -q --tb=no` — 깨진 테스트 유무 확인.

4. **File size check**: 200줄 초과 파일 탐지.
   ```bash
   find alphapulse/ -name "*.py" -exec awk 'END{if(NR>200) print FILENAME": "NR" lines"}' {} \;
   ```

5. **CLAUDE.md sync**: CLAUDE.md의 Known Failures 섹션이 최신인지 확인. 새로운 반복 실수가 있으면 추가 제안.

## Output:
- 발견된 이슈 수 요약
- 자동 수정 가능한 것은 즉시 수정
- 수동 검토 필요한 항목은 목록으로 제시
