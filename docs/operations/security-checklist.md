# 분기 보안 체크리스트 (3개월 1회)

**실시일:** ____________________  
**실시자:** ____________________

## 의존성
- [ ] `uv run pip-audit --strict` Pass
- [ ] `pnpm audit --audit-level=high` Pass
- [ ] Next.js / FastAPI 메이저 업데이트 여부 확인
- [ ] 최근 CVE 공지 전수 확인 (cvedetails, GHSA)

## 인증/세션
- [ ] 활성 세션 수 검토 (`SELECT COUNT(*) FROM sessions WHERE expires_at > strftime('%s','now')`)
- [ ] 장기 미사용 계정 비활성화 여부
- [ ] 관리자 비밀번호 로테이션 (연 1회 이상)

## 감사 로그
- [ ] 비정상 로그인 시도 로그 확인 (로그인 실패 IP 집중 여부)
- [ ] 감사 로그 1년 이상 보관 중인지

## 시크릿
- [ ] `.env` 권한 `600` 확인
- [ ] `WEBAPP_SESSION_SECRET` / `KIS_*` 로테이션 여부 (연 1회)
- [ ] Git history에 시크릿 누출 없음 (`git log -p | grep -iE "(api[_-]?key|secret|password)"`)

## 인프라
- [ ] 서버 OS 보안 업데이트 최신 (`apt list --upgradable | grep -i security`)
- [ ] Cloudflare WAF Managed Rules 활성
- [ ] SSL 인증서 만료일 > 30일
- [ ] 백업 실행/복구 테스트 (실제 복구 해보기)

## 네트워크
- [ ] 홈서버 포트 80/443 포워딩 없음 재확인
- [ ] SSH는 키 기반 + LAN 한정
- [ ] fail2ban / SSH 로그인 실패 로그 검토

## 서명
- [ ] 모든 항목 OK 시 이 문서 커밋 (`docs/operations/security-log-YYYYQn.md` 로 복사)
