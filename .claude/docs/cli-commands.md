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

# Trading
ap trading screen [--market] [--top] [--factor]        # 팩터 스크리닝
ap trading signals [--strategy] [--market] [--top]     # 전략 시그널
ap trading backtest run [--strategy] [--start] [--end] [--capital] [--html] # 백테스트 실행
ap trading backtest list [--limit]                     # 과거 결과 목록
ap trading backtest report <run_id> [--html]           # 상세 리포트
ap trading backtest trades <run_id> [--code] [--winner/--loser] # 거래 이력
ap trading backtest compare <id1> <id2>                # 두 결과 비교
ap trading run [--mode paper|live] [--daemon]          # 매매 실행
ap trading status                                      # 시스템 상태
ap trading reconcile                                   # DB/증권사 대사
ap trading portfolio show [--mode]                     # 포트폴리오
ap trading portfolio history [--days] [--mode]         # 성과 이력
ap trading portfolio attribution [--days] [--mode]     # 성과 귀속
ap trading risk report [--mode]                        # 리스크 리포트
ap trading risk stress [--mode]                        # 스트레스 테스트
ap trading risk limits                                 # 리밋 설정
ap trading data collect [--market] [--years]           # 전종목 수집
ap trading data update [--market]                      # 증분 업데이트
ap trading data status                                 # 수집 현황
ap trading data schedule [--market] [--top-n] [--force] # 자율 수집
```
