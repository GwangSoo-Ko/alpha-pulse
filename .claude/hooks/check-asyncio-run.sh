#!/bin/bash
# PostToolUse hook (matcher: Write|Edit)
# asyncio.run()이 CLI entry 외부에서 사용되면 에러 반환
# OpenAI 패턴: "에러 메시지가 곧 교육"

FILE=$(jq -r '.tool_response.filePath // .tool_input.file_path' 2>/dev/null)

# Python 파일만 검사
if ! echo "$FILE" | grep -qE '\.py$'; then
  exit 0
fi

if [ ! -f "$FILE" ]; then
  exit 0
fi

# CLI entry point 및 sync→async 브릿지 파일은 검사 제외
# orchestrator.py의 run() → asyncio.run(run_async())는 의도된 패턴
if echo "$FILE" | grep -qE '(cli\.py|__main__\.py|orchestrator\.py)$'; then
  exit 0
fi

# tests/ 디렉토리도 제외 (테스트에서는 asyncio.run 허용)
if echo "$FILE" | grep -qE '/tests/'; then
  exit 0
fi

# asyncio.run() 사용 검사
VIOLATIONS=$(grep -n 'asyncio\.run(' "$FILE" 2>/dev/null)

if [ -n "$VIOLATIONS" ]; then
  ESCAPED=$(echo "$VIOLATIONS" | jq -Rs .)
  cat <<EOF
{"hookSpecificOutput":{"hookEventName":"PostToolUse","additionalContext":"RULE VIOLATION: asyncio.run()은 CLI entry point(cli.py)에서만 허용됩니다.\n\nFile: $FILE\nViolations:\n$(echo "$VIOLATIONS")\n\nFIX: async 함수 내부에서는 await를 사용하세요. sync→async 브릿지가 필요하면 BriefingOrchestrator.run() → run_async() 패턴을 참고하세요."}}
EOF
  exit 2
fi

exit 0
