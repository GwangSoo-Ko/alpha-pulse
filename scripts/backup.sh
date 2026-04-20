#!/usr/bin/env bash
# AlphaPulse 일일 백업 — cron 03:00 실행
# Usage: /opt/alphapulse/scripts/backup.sh

set -euo pipefail

BASE="${BASE:-/opt/alphapulse}"
DATA="$BASE/data"
BACKUPS="$BASE/backups"
DATE=$(date +%Y%m%d_%H%M%S)
TARGET="$BACKUPS/$DATE"

mkdir -p "$TARGET"
for db in trading backtest portfolio audit feedback cache history webapp; do
    SRC="$DATA/$db.db"
    if [ -f "$SRC" ]; then
        sqlite3 "$SRC" ".backup '$TARGET/$db.db'"
    fi
done

# 압축
tar czf "$TARGET.tar.gz" -C "$BACKUPS" "$DATE"
rm -rf "$TARGET"

# 원격 동기화 (rclone 설정 선택)
if command -v rclone >/dev/null 2>&1 && rclone listremotes | grep -q "^b2:"; then
    rclone copy "$TARGET.tar.gz" "b2:alphapulse-backups/" --quiet
fi

# 7일 이전 로컬 백업 삭제
find "$BACKUPS" -maxdepth 1 -name "*.tar.gz" -mtime +7 -delete

echo "backup ok: $TARGET.tar.gz"
