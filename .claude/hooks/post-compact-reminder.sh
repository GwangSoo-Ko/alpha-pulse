#!/bin/bash
# SessionStart hook (matcher: compact)
# 컨텍스트 압축 후 핵심 규칙을 재주입하여 "기억 상실" 방지

cat <<'REMINDER'
## AlphaPulse 핵심 규칙 (압축 후 재주입)

1. **Sync/Async 경계**: market/ = SYNC only, content/ + feedback/agents/ = ASYNC only
2. **asyncio.run()은 CLI entry에서만**. 내부에서는 await. 중첩 호출 금지.
3. **LLM 호출**: asyncio.to_thread(client.generate_content) 패턴
4. **피드백 코드**: 항상 try/except. 피드백 실패가 메인 브리핑 중단하면 안 됨.
5. **파일 수정 후**: ruff 린트 훅이 자동 실행됨. 에러 시 수정 필요.
6. **커밋 전**: /push 사용 — ruff + pytest 통과해야만 커밋 가능.
7. **Known Failures**: asyncio.run() 중첩, import 정렬 미준수, 미사용 import 방치
REMINDER
