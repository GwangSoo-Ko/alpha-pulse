#!/bin/bash
# PreToolUse hook (matcher: Bash)
# git push --force, git reset --hard, rm -rf 등 위험 명령 차단

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // ""')

# 위험 명령 패턴 검사
if echo "$COMMAND" | grep -qE 'git\s+push\s+.*--force|git\s+push\s+-f\b'; then
  echo '{"decision":"block","reason":"git push --force는 차단됩니다. 일반 git push를 사용하세요."}'
  exit 0
fi

if echo "$COMMAND" | grep -qE 'git\s+reset\s+--hard'; then
  echo '{"decision":"block","reason":"git reset --hard는 차단됩니다. 변경사항이 손실될 수 있습니다."}'
  exit 0
fi

if echo "$COMMAND" | grep -qE 'rm\s+-rf\s+/|rm\s+-rf\s+\.\s|rm\s+-rf\s+\.\.|rm\s+-rf\s+\*'; then
  echo '{"decision":"block","reason":"rm -rf 광범위 삭제는 차단됩니다. 구체적인 경로를 지정하세요."}'
  exit 0
fi

if echo "$COMMAND" | grep -qE 'git\s+clean\s+-f'; then
  echo '{"decision":"block","reason":"git clean -f는 차단됩니다. 추적되지 않는 파일이 삭제됩니다."}'
  exit 0
fi

exit 0
