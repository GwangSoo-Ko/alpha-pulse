# 백업 / 복구

## 자동 백업 설정

```bash
sudo -u alphapulse crontab -e
```
```
0 3 * * * /opt/alphapulse/scripts/backup.sh >> /opt/alphapulse/logs/backup.log 2>&1
```

## 복구 절차

### 1. 서비스 중지
```bash
sudo systemctl stop alphapulse-fastapi alphapulse-webapp-ui
```

### 2. 백업 추출
```bash
cd /tmp
tar xzf /opt/alphapulse/backups/<DATE>.tar.gz
```

### 3. DB 복원
```bash
sudo -u alphapulse cp /tmp/<DATE>/<db>.db /opt/alphapulse/data/<db>.db
```

### 4. 무결성 확인
```bash
for db in /opt/alphapulse/data/*.db; do
    sqlite3 "$db" "PRAGMA integrity_check;"
done
```

### 5. 서비스 기동
```bash
sudo systemctl start alphapulse-fastapi alphapulse-webapp-ui
curl https://api.example.com/api/v1/health
```

## 원격 저장소 연결 (선택)

Backblaze B2 예시:
```bash
sudo -u alphapulse rclone config
# Remote name: b2
# Storage: Backblaze B2
# (B2 application key 입력)
```
