# CLI Commands Reference

```
ap market pulse [--date] [--period]          # 종합 시황 (11개 지표)
ap market {investor,program,sector,macro,fund} [--date]  # 상세 분석
ap market report [--date] [--output]         # HTML 리포트
ap market history [--days]                   # 과거 이력
ap content monitor [--daemon] [--force-latest N] [--no-telegram]
ap content test-telegram                     # 연결 테스트
ap briefing [--no-telegram] [--daemon] [--time HH:MM]
ap commentary [--date]                       # AI 시장 해설
ap feedback evaluate                         # 시그널 평가 (시장 결과 수집)
ap feedback report [--days]                  # 적중률 리포트
ap feedback indicators [--days]              # 지표별 적중률
ap feedback history [--days]                 # 시그널 vs 결과 테이블
ap feedback analyze [--date]                 # 사후 분석
ap cache clear                               # 캐시 초기화
```
