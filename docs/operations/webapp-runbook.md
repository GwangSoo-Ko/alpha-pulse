# Webapp Runbook — 장애 대응

## 증상: FastAPI 5xx 급증
1. 로그 확인: `journalctl -u alphapulse-fastapi -n 200 --no-pager`
2. 잘못된 DB 경로/권한 여부: `ls -la /opt/alphapulse/data/`
3. 재시작: `sudo systemctl restart alphapulse-fastapi`
4. 해결 안 됨 → 최근 배포 롤백: `git checkout <prev> && uv sync && restart`

## 증상: Next.js UI 로딩 실패
1. `journalctl -u alphapulse-webapp-ui -n 100`
2. Node 버전: `node --version` (22 LTS)
3. 빌드 재실행: `sudo -u alphapulse bash -c "cd webapp-ui && pnpm build"`
4. 재시작: `sudo systemctl restart alphapulse-webapp-ui`

## 증상: Cloudflare Tunnel 단절
1. `sudo systemctl status cloudflared`
2. 토큰 유효성: `sudo cloudflared tunnel list`
3. 재연결: `sudo systemctl restart cloudflared`

## 증상: 로그인 불가
1. 계정 잠금 여부: `/opt/alphapulse/.venv/bin/ap webapp unlock-account --email <>`
2. DB 무결성: `sqlite3 /opt/alphapulse/data/webapp.db "PRAGMA integrity_check"`
3. 세션 DB 리셋 (극단적 경우): 모든 사용자 로그아웃됨
   ```bash
   sqlite3 /opt/alphapulse/data/webapp.db "DELETE FROM sessions;"
   ```

## 증상: 백테스트 실행 안 끝남 / 멈춤
1. Job 상태: `sqlite3 /opt/alphapulse/data/webapp.db "SELECT id, status, progress FROM jobs ORDER BY created_at DESC LIMIT 5"`
2. 오래된 `running` 정리: FastAPI 재시작하면 orphan 복구 자동 수행
3. 기존 결과 삭제:
   ```bash
   # CLI 또는 UI에서 DELETE /api/v1/backtest/runs/<id>
   ```

## 긴급 전체 중지
```bash
sudo systemctl stop alphapulse-webapp-ui alphapulse-fastapi cloudflared
```
복구: `sudo systemctl start ...` 역순 또는 `systemctl start` 한 번에.

## 로그 수집 범위
- `journalctl -u alphapulse-* -u cloudflared --since "1 hour ago"`
- `/opt/alphapulse/logs/*.log`
- `/opt/alphapulse/data/audit.db` (최근 이벤트)
