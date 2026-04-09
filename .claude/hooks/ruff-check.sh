#!/bin/bash
# PostToolUse hook: ruff lint check on Python files after Write/Edit
# Returns lint errors as additionalContext so the agent self-corrects

FILE=$(jq -r '.tool_response.filePath // .tool_input.file_path' 2>/dev/null)

# Skip non-Python files
if ! echo "$FILE" | grep -qE '\.py$'; then
  exit 0
fi

# Skip if file doesn't exist (deleted)
if [ ! -f "$FILE" ]; then
  exit 0
fi

OUTPUT=$(ruff check "$FILE" 2>&1)
EXIT=$?

if [ $EXIT -ne 0 ]; then
  # Escape for JSON
  ESCAPED=$(echo "$OUTPUT" | jq -Rs .)
  echo "{\"hookSpecificOutput\":{\"hookEventName\":\"PostToolUse\",\"additionalContext\":\"Ruff lint errors found. Fix before proceeding:\\n\"${ESCAPED}\"\"}}"
  exit 2
fi

# Success is quiet - no output
exit 0
