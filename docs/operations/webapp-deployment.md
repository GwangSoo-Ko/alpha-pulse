# AlphaPulse Webapp 배포 가이드 (홈서버 + Cloudflare Tunnel)

## 요구사항
- Ubuntu 24.04 LTS (또는 Debian계 Linux)
- Python 3.12+, Node.js 22 LTS, pnpm (corepack)
- Cloudflare 계정 + 도메인

## 1. 사전 준비

### 사용자/디렉토리
```bash
sudo useradd --system --create-home --home-dir /opt/alphapulse --shell /bin/false alphapulse
sudo chown -R alphapulse:alphapulse /opt/alphapulse
```

### 소스 배포
```bash
sudo -u alphapulse git clone https://<repo> /opt/alphapulse
cd /opt/alphapulse
sudo -u alphapulse uv sync
sudo -u alphapulse bash -c "cd webapp-ui && pnpm install && pnpm build"
```

### `.env` 설정
```bash
sudo -u alphapulse cp .env.example /opt/alphapulse/.env
sudo chmod 600 /opt/alphapulse/.env
sudo nano /opt/alphapulse/.env
```
필수:
- `WEBAPP_SESSION_SECRET` (최소 32자, `openssl rand -hex 32`)
- `KIS_APP_KEY`, `KIS_APP_SECRET`, `KIS_ACCOUNT_NO`
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHANNEL_ID` (콘텐츠)
- `TELEGRAM_MONITOR_BOT_TOKEN`, `TELEGRAM_MONITOR_CHANNEL_ID` (모니터링)

### 관리자 계정 생성
```bash
cd /opt/alphapulse
sudo -u alphapulse .venv/bin/ap webapp create-admin --email admin@example.com
```

## 2. systemd 설치

```bash
sudo cp /opt/alphapulse/systemd/alphapulse-fastapi.service /etc/systemd/system/
sudo cp /opt/alphapulse/systemd/alphapulse-webapp-ui.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now alphapulse-fastapi alphapulse-webapp-ui
sudo systemctl status alphapulse-fastapi alphapulse-webapp-ui
```

## 3. Cloudflare Tunnel

### 설치
```bash
# 패키지 설치 (Cloudflare 공식 지침 따름)
curl -L https://pkg.cloudflare.com/install.sh | sudo bash
sudo apt install -y cloudflared
```

### 터널 생성 & 인증
```bash
sudo cloudflared tunnel login
sudo cloudflared tunnel create alphapulse
# → /etc/cloudflared/<uuid>.json 생성
```

### 설정
`/etc/cloudflared/config.yml`:
```yaml
tunnel: <uuid-from-above>
credentials-file: /etc/cloudflared/<uuid>.json
ingress:
  - hostname: app.example.com
    service: http://127.0.0.1:3000
  - hostname: api.example.com
    service: http://127.0.0.1:8000
  - service: http_status:404
```

### DNS 라우팅
```bash
sudo cloudflared tunnel route dns alphapulse app.example.com
sudo cloudflared tunnel route dns alphapulse api.example.com
```

### 서비스 등록
```bash
sudo cp /opt/alphapulse/systemd/cloudflared.service.example /etc/systemd/system/cloudflared.service
sudo systemctl daemon-reload
sudo systemctl enable --now cloudflared
```

## 4. Cloudflare 추가 보안 설정

1. **Transform Rules** → Modify Request Header
   - Remove `x-middleware-subrequest`
   - Remove `x-middleware-prefetch`
2. **SSL/TLS** → Full (strict)
3. **WAF** → Managed Rules 활성 (OWASP Core Rule Set)
4. (선택) **Zero Trust Access** → 이메일 OTP 정책으로 `app.example.com` 보호

## 5. 동작 확인

```bash
curl https://api.example.com/api/v1/health
# 예상: {"status":"ok"}

# 브라우저에서 https://app.example.com 접속 → 로그인
```

## 6. 업데이트 절차

```bash
cd /opt/alphapulse
sudo -u alphapulse git pull
sudo -u alphapulse uv sync
sudo -u alphapulse bash -c "cd webapp-ui && pnpm install && pnpm build"
sudo systemctl restart alphapulse-fastapi alphapulse-webapp-ui
```
