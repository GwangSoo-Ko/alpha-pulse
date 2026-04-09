---
description: 변경사항 커밋 + 푸시 (CI 게이트 포함)
argument-hint: "commit message"
---

Push changes with quality gates. Tests and lint must pass before commit.

## CI Gate (반드시 통과해야 진행)

1. Run `ruff check alphapulse/` — lint 검사. 실패 시 `ruff check --fix alphapulse/`로 자동 수정 후 재확인.
2. Run `pytest tests/ -x -q --tb=short` — 테스트. 실패 시 중단하고 사용자에게 알림.

## Commit & Push (CI Gate 통과 후)

3. `git add -A`
4. `git status --short` to show what will be committed
5. `git commit -m "$ARGUMENTS"` (if no argument, generate a descriptive message)
6. `git push`

**IMPORTANT**: 1-2단계가 모두 통과해야만 3-6단계를 진행합니다. 테스트 실패 시 절대 커밋하지 마세요.
