# AlphaPulse Web Frontend — Phase 2 Design

Phase 1(Auth + Backtest)의 웹 프론트엔드 위에, 일일 트레이딩 운영 도메인을 추가하는 설계 문서.
Portfolio / Risk / Screening / Data / Settings / Audit 6개 도메인을 구현하고, 통합 홈 대시보드를 새로 추가한다.

**Phase 1 참조:** `docs/superpowers/specs/2026-04-19-webapp-design.md`, `docs/superpowers/plans/2026-04-19-webapp-phase1.md`

## 1. 요구사항 요약

| 항목 | 결정 |
|------|------|
| 홈 대시보드 | **추가** — 좌측 포트폴리오(2/3) + 우측 위젯 4종 (Layout A) |
| Settings 수정 범위 | **전체** — KIS/Telegram/Gemini 키 + 리스크 리밋 + 알림 + 백테스트 기본값 |
| Settings 저장 방식 | Fernet 암호화 DB 저장 + `.env` fallback (hybrid) |
| Data 액션 범위 | `update` + 개별 재수집 (재무/wisereport/공매도). **`collect_all`은 CLI 전용** (UI 비활성 + 사유 표시) |
| Screening 실행 | **Job 기반 + 영속 저장** (screening_runs 테이블) |
| Portfolio/Risk 모드 | URL `?mode=` 기반 전역 모드 셀렉터 |
| Risk 계산 | **스냅샷 해시 캐싱** — 동일 스냅샷이면 캐시 반환 |
| Phase 3 대비 | 신규 테이블 모두 `tenant_id` nullable 선반영 |

## 2. 아키텍처

### 2.1 Phase 1 위에 쌓는 구조

기존 FastAPI/Next.js 프레임워크·미들웨어·인증은 모두 재사용.
- 도메인별 FastAPI 라우터 추가: `alphapulse/webapp/api/*.py`
- 기존 repository + 신규 어댑터(`readers/`)
- Next.js App Router 도메인별 페이지 (Phase 1 패턴 동일)
- 공통 `useMode` hook으로 URL 모드 상태 관리

### 2.2 도메인 & 라우트 카탈로그

| 도메인 | 백엔드 라우터 | 프론트 페이지 |
|---|---|---|
| **Home Dashboard** | `api/dashboard.py` | `/` (Phase 1 redirect 교체) |
| **Portfolio** | `api/portfolio.py` | `/portfolio`, `/portfolio/history`, `/portfolio/attribution` |
| **Risk** | `api/risk.py` | `/risk`, `/risk/stress`, `/risk/limits` |
| **Screening** | `api/screening.py` | `/screening`, `/screening/new`, `/screening/[runId]`, `/screening/jobs/[id]` |
| **Data** | `api/data.py` | `/data`, `/data/jobs/[id]` |
| **Settings** | `api/settings.py` | `/settings/[tab]` (4 탭) |
| **Audit** | `api/audit.py` | `/audit` |

### 2.3 신규 DB 테이블 (webapp.db)

```sql
-- 설정 (Fernet 암호화 저장, hybrid with .env)
CREATE TABLE settings (
    key TEXT PRIMARY KEY,
    value_encrypted TEXT NOT NULL,
    is_secret INTEGER NOT NULL DEFAULT 0,
    category TEXT NOT NULL,          -- 'api_key' | 'risk_limit' | 'notification' | 'backtest'
    tenant_id INTEGER,               -- Phase 3 대비
    updated_at REAL NOT NULL,
    updated_by INTEGER,
    FOREIGN KEY (updated_by) REFERENCES users(id)
);
CREATE INDEX idx_settings_category ON settings(category);

-- 스크리닝 결과 영속 저장
CREATE TABLE screening_runs (
    run_id TEXT PRIMARY KEY,
    name TEXT DEFAULT '',
    market TEXT NOT NULL,
    strategy TEXT NOT NULL,
    factor_weights TEXT NOT NULL,    -- JSON
    top_n INTEGER NOT NULL,
    market_context TEXT DEFAULT '{}',
    results TEXT NOT NULL,           -- JSON list
    user_id INTEGER NOT NULL,
    tenant_id INTEGER,
    created_at REAL NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
CREATE INDEX idx_screening_user ON screening_runs(user_id, created_at DESC);

-- 리스크 리포트 캐시 (스냅샷 해시 기반)
CREATE TABLE risk_report_cache (
    snapshot_key TEXT PRIMARY KEY,   -- "{date}|{mode}|{total_value_int}"
    report_json TEXT NOT NULL,
    stress_json TEXT,
    computed_at REAL NOT NULL,
    tenant_id INTEGER
);
```

**기존 테이블 무변경 원칙 유지.** Phase 1과 동일.

## 3. 백엔드 상세

### 3.1 파일 구조 (Phase 2 추가분)

```
alphapulse/webapp/
├── api/
│   ├── dashboard.py
│   ├── portfolio.py
│   ├── risk.py
│   ├── screening.py
│   ├── data.py
│   ├── settings.py
│   └── audit.py
├── store/
│   ├── settings.py            # SettingsRepository (Fernet)
│   ├── risk_cache.py
│   ├── screening.py
│   └── readers/
│       ├── portfolio.py
│       ├── risk.py
│       ├── data_status.py
│       └── audit.py
└── services/
    ├── settings_service.py    # DB → .env fallback
    ├── screening_runner.py
    └── data_jobs.py
```

### 3.2 Settings 서비스 (핵심)

**SettingsRepository:** webapp.db의 settings 테이블에 Fernet 암호화 저장/조회.

**SettingsService:** 런타임 설정 중앙 접근점. 우선순위:
1. DB에 암호화된 값 있으면 Fernet 복호화 후 반환
2. 없으면 `os.environ.get(key)` fallback
3. 둘 다 없으면 None 또는 기본값

```python
class SettingsService:
    def get(self, key: str) -> str | None: ...
    def get_int(self, key: str, default: int) -> int: ...
    def get_float(self, key: str, default: float) -> float: ...
    def get_bool(self, key: str, default: bool) -> bool: ...
    def set(self, key: str, value: str, is_secret: bool,
            category: str, user_id: int) -> None: ...
    def list_by_category(self, category: str) -> list[SettingEntry]: ...

    def load_env_overrides(self) -> None:
        """FastAPI startup 훅에서 호출. DB 값으로 os.environ 덮어쓰기.
        기존 코드가 os.environ을 직접 읽어도 DB 값이 반영되게 함.
        Phase 3에서 DI 패턴으로 교체 예정."""
        for entry in self.repo.list_all():
            os.environ[entry.key] = self.get(entry.key)
```

### 3.3 Risk Report 캐싱

키: `f"{snapshot.date}|{mode}|{int(snapshot.total_value)}"`

```python
def get_risk_report(snapshot, mode) -> dict:
    key = f"{snapshot.date}|{mode}|{int(snapshot.total_value)}"
    cached = risk_cache.get(key)
    if cached:
        return cached
    report = risk_manager.daily_report(snapshot)
    stress = stress_test.run_all(snapshot)
    data = {"report": report.__dict__, "stress": stress,
            "computed_at": time.time()}
    risk_cache.put(key, data)
    return data
```

스냅샷은 하루 1회 변경되므로 실제 계산은 모드별 1일 1회 수준.

### 3.4 Screening Runner (Job 용)

Phase 1 `run_backtest_sync` 패턴 재사용. 기존 `ap trading screen` CLI 로직을 서비스 함수로 추출:

```python
def run_screening_sync(*, market, strategy, factor_weights, top_n,
                      user_id, progress_callback) -> str:  # run_id 반환
    universe = load_universe(market)
    progress_callback(0, 3, "데이터 로드")

    calc = FactorCalculator(trading_store)
    factor_data = compute_factors(calc, universe)
    progress_callback(1, 3, "팩터 계산")

    ranker = MultiFactorRanker(weights=factor_weights)
    signals = ranker.rank(universe, factor_data, strategy_id=strategy)[:top_n]
    progress_callback(2, 3, "랭킹")

    market_context = _get_market_pulse()
    run_id = screening_repo.save(
        market=market, strategy=strategy,
        factor_weights=factor_weights, top_n=top_n,
        market_context=market_context,
        results=[signal_to_dict(s) for s in signals],
        user_id=user_id,
    )
    progress_callback(3, 3, "저장")
    return run_id
```

### 3.5 Data Jobs

기존 `BulkCollector`와 개별 collector 메서드를 Job wrapper로 감싼다.

```python
def run_data_update(*, markets, user_id, progress_callback) -> str:
    collector = BulkCollector(db_path=TRADING_DB_PATH)
    # BulkCollector.update()는 이미 progress_callback 지원
    results = collector.update(markets=markets,
                               progress_callback=progress_callback)
    return json.dumps([r.__dict__ for r in results])

def run_data_collect_financials(*, market, top, user_id,
                                progress_callback): ...
def run_data_collect_wisereport(*, market, top, user_id,
                                progress_callback): ...
def run_data_collect_short(*, market, top, user_id,
                           progress_callback): ...

# collect_all 은 서비스 함수 자체를 제공하지 않음 → API 자체 없음
```

### 3.6 API 라우트 (Phase 2)

| Method | Path | 설명 |
|---|---|---|
| GET | `/api/v1/dashboard/home` | 홈 통합 (portfolio summary + risk status + data status + recent backtests + recent audits) |
| GET | `/api/v1/portfolio?mode=` | 현재 스냅샷 |
| GET | `/api/v1/portfolio/history?mode=&days=` | 성과 이력 |
| GET | `/api/v1/portfolio/attribution?mode=&days=` | 성과 귀속 |
| GET | `/api/v1/risk/report?mode=` | 리포트 (캐시 사용) |
| GET | `/api/v1/risk/stress?mode=` | 스트레스 5 시나리오 (캐시) |
| POST | `/api/v1/risk/stress/custom` | 사용자 정의 시나리오 (캐시 skip) |
| GET | `/api/v1/risk/limits` | 현재 리밋 |
| GET | `/api/v1/screening/runs` | 목록 (페이지네이션) |
| GET | `/api/v1/screening/runs/{id}` | 상세 |
| POST | `/api/v1/screening/run` | 실행 → job_id |
| DELETE | `/api/v1/screening/runs/{id}` | 삭제 (admin) |
| GET | `/api/v1/data/status` | 수집 현황 + 갭 감지 |
| GET | `/api/v1/data/scheduler` | 스케줄러 상태 |
| POST | `/api/v1/data/update` | update Job |
| POST | `/api/v1/data/collect-financials` | 재무 재수집 Job |
| POST | `/api/v1/data/collect-wisereport` | wisereport 재수집 Job |
| POST | `/api/v1/data/collect-short` | 공매도 재수집 Job |
| GET | `/api/v1/settings?category=` | 카테고리별 조회 (마스킹) |
| PUT | `/api/v1/settings/{key}` | 수정 (현재 비밀번호 재입력 필요) |
| GET | `/api/v1/audit/events?from=&to=&actor=&action_prefix=` | 감사 로그 조회 |

## 4. 프론트엔드 상세

### 4.1 파일 구조 (Phase 2 추가분)

```
webapp-ui/
├── app/(dashboard)/
│   ├── page.tsx               # 홈 대시보드 (redirect 교체)
│   ├── portfolio/             # summary/history/attribution
│   ├── risk/                  # overview/stress/limits
│   ├── screening/             # list/new/[runId]/jobs
│   ├── data/                  # status/jobs
│   ├── settings/              # 4 탭
│   └── audit/
├── components/
│   ├── layout/
│   │   ├── mode-selector.tsx  # NEW 상단바 드롭다운
│   │   └── sidebar.tsx        # 활성 항목 업데이트
│   └── domain/
│       ├── home/              # 5 위젯
│       ├── portfolio/
│       ├── risk/
│       ├── screening/
│       ├── data/
│       ├── settings/
│       └── audit/
├── hooks/
│   ├── use-mode.ts
│   ├── use-portfolio.ts       # 장중 polling
│   ├── use-data-status.ts
│   └── use-job-status.ts      # (기존 재사용)
└── lib/
    ├── market-hours.ts        # 장중 여부
    └── format.ts              # 숫자/금액 포맷 유틸
```

### 4.2 Mode Selector

Topbar 중앙에 `[Paper ▾]` 드롭다운 추가. Phase 1 topbar.tsx 확장.

**동작:**
- URL `?mode=paper|live|backtest` 자동 동기화
- 선택 변경 → `router.replace`
- Portfolio/Risk 도메인에서 TanStack Query queryKey에 mode 포함 → 자동 리페치

**노출 규칙:**
- Portfolio / Risk 계열: 활성
- Backtest / Data / Settings / Audit / Home: 숨김 또는 비활성 (홈은 paper 고정)

### 4.3 홈 대시보드 (Layout A)

```
+---------------------------------+----------------------+
|  포트폴리오 (2/3)                 |  리스크 상태 위젯      |
|  - 총 자산 KPI                   +----------------------+
|  - 30일 자산 곡선 미니            |  데이터 수집 위젯      |
|  - 상위 5 보유 종목               +----------------------+
|                                 |  최근 백테스트 3건     |
|                                 +----------------------+
|                                 |  최근 감사 이벤트 10건 |
+---------------------------------+----------------------+
```

- 서버 컴포넌트: `/api/v1/dashboard/home` 단일 호출로 모든 위젯 데이터 확보
- Portfolio 위젯만 client component로 장중 30초 polling
- 나머지는 정적

### 4.4 페이지별 핵심 UI

#### Portfolio
- `/portfolio`: KPI 카드 4개(총자산/현금/일간/누적) + Holdings 테이블 (Phase 1 position-viewer 스타일 재사용)
- `/portfolio/history`: Recharts 자산 곡선 + 일별 수익률 바. 기간 버튼(7/30/90/YTD/전체)
- `/portfolio/attribution`: 전략별 + 섹터별 가로 막대

#### Risk
- `/risk`: 카드 그리드 (드로다운 상태/VaR95/CVaR95/경고 수) + 경고 리스트
- `/risk/stress`: 5 시나리오 표 + 커스텀 시나리오 실행 폼
- `/risk/limits`: 현재 리밋 읽기 전용 + `[Settings에서 수정]` 링크

#### Screening
- `/screening`: 과거 실행 목록 (이름/전략/top_n/실행일/시장)
- `/screening/new`: 폼 — 시장, 전략 preset 또는 커스텀 팩터 가중치 슬라이더, top N, 이름
- `/screening/[runId]`: 결과 표 (순위/종목/점수/주요 팩터) + 시장 컨텍스트 카드
- `/screening/jobs/[id]`: 진행률 (Phase 1 job-progress 재사용)

#### Data
- `/data`:
  - 상단: 수집 스케줄러 상태 카드
  - 중앙: 테이블별 현황 (trading/fundamentals/wisereport/flow/short)
  - 갭 감지: 최근 5일 데이터 누락 경고
  - 액션: `[증분 업데이트]`, `[재무 재수집]`, `[Wisereport 재수집]`, `[공매도 재수집]`
  - `[전종목 수집]` 버튼: 회색 비활성 + 툴팁: "초기 1회 전종목 수집은 리소스 큼. CLI(`ap trading data collect`)에서만 실행 가능. 웹에서는 안전상 차단."
- `/data/jobs/[id]`: 진행률

#### Settings (탭)
- API 키 / 리스크 리밋 / 알림 / 백테스트 기본값
- `SecretInput` 컴포넌트: 기존 값 `sk-****...abc` 마스킹, 편집 진입 시 새 값
- 변경 시 **현재 비밀번호 재입력 확인**

#### Audit
- 필터 바 (날짜 / 이메일 / action prefix) + 페이지네이션
- 행 클릭 → 상세 JSON 팝오버

### 4.5 Polling 정책

| 페이지 | 간격 | 조건 |
|---|---|---|
| Home | 30초 | 장중 (09:00~15:30 KST) |
| Portfolio summary | 30초 | 장중 |
| Portfolio history/attribution | 없음 | - |
| Risk | 없음 | 캐시 |
| Screening list/detail | 없음 | - |
| Data status | 수동 새로고침 | - |
| Data jobs | 2초 | 실행 중 (Phase 1 재사용) |
| Settings / Audit | 없음 | - |

`useMarketHours()` hook으로 장중 여부 판단, polling 자동 on/off.

## 5. 보안 & 마이그레이션

### 5.1 Fernet 키 관리

**생성 & 배포:**
```bash
ap webapp init-encrypt-key
# → 32바이트 URL-safe 키 생성 → stdout
# → .env에 WEBAPP_ENCRYPT_KEY=... 추가하라고 안내
# → 키 분실 시 복호화 불가 경고 표시
```

**원칙:**
- 키는 절대 DB에 저장하지 않음
- 키는 절대 git에 커밋하지 않음 (`.env` is gitignored)
- 프로덕션: systemd `EnvironmentFile=/opt/alphapulse/.env` (권한 600)

**키 교체 (Phase 2 포함):**
```bash
ap webapp rotate-encrypt-key --old OLD_KEY --new NEW_KEY
# → DB 전체 재암호화
```

**키 유실 복구:** DB의 암호화 값 복구 불가. `.env` 값으로 재설정 필요. Runbook에 명시.

### 5.2 Settings 변경 보안

**흐름:**
1. CSRF 토큰 검증 (기본)
2. 세션 유효 + role == "admin"
3. 요청 본문의 `current_password` bcrypt 검증 (재확인)
4. 값 검증 (형식, 범위)
5. `SettingsRepository.set()` → Fernet 암호화 저장
6. `AuditLogger.log("webapp.settings.update", ...)` — 키/카테고리/user_id/old_hash(prefix)/new_hash(prefix). **값 자체는 기록 안 함**.

**마스킹 규칙:**
- Secret (`is_secret=1`): `value_masked = f"{val[:4]}****{val[-4:]}"` (8자 미만은 `****`)
- Non-secret (리스크 리밋 등): 평문 노출

**Rate limit:** 사용자당 PUT 10회/10분

### 5.3 `.env` → DB 이관

```bash
ap webapp import-env [--dry-run]
```

**동작:**
1. `.env` 읽기
2. 화이트리스트 키 각각:
   - 이미 DB에 있으면 skip (덮어쓰기 안 함)
   - 없으면 DB에 삽입 (Fernet 암호화)
3. dry-run: 변경 리스트만 출력
4. 감사: `webapp.settings.imported_from_env` 이벤트

**화이트리스트:**
- `api_key` 카테고리: `KIS_APP_KEY`, `KIS_APP_SECRET`, `KIS_ACCOUNT_NO`, `GEMINI_API_KEY`
- `notification` 카테고리: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHANNEL_ID`, `TELEGRAM_MONITOR_BOT_TOKEN`, `TELEGRAM_MONITOR_CHANNEL_ID`
- `risk_limit`: `MAX_POSITION_WEIGHT`, `MAX_DRAWDOWN_SOFT/HARD`, `MAX_DAILY_ORDERS`, `MAX_DAILY_AMOUNT`
- `backtest`: `BACKTEST_COMMISSION`, `BACKTEST_TAX`, `BACKTEST_INITIAL_CAPITAL`, `STRATEGY_ALLOCATIONS`

이관 후 `.env`는 그대로 두거나 제거 — hybrid 구조로 둘 다 지원.

### 5.4 기존 코드 호환 (Phase 2)

**방안 A (Phase 2 채택):** FastAPI startup 훅에서 `SettingsService.load_env_overrides()` 호출 → DB 값으로 `os.environ` 덮어쓰기. 기존 코드 무변경. FastAPI 프로세스 재시작 후에만 반영.

**방안 B (Phase 3 예정):** 기존 코드를 `SettingsService` 의존성 주입으로 점진 교체. 런타임 즉시 반영.

방안 A의 제약:
- 전역 state 수정 — 단일 프로세스 가정에서 안전
- 멀티 workers 시 각 worker마다 호출 필요
- Phase 2에서는 충분. Phase 3에서 B로 전환.

### 5.5 Audit 이벤트 확장 (Phase 2 신규)

- `webapp.settings.update` — 설정 변경 (마스킹된 diff)
- `webapp.settings.imported_from_env` — 최초 이관
- `webapp.settings.encrypt_key_rotated` — 키 교체
- `webapp.data.job_started` — 데이터 수집 Job 시작 (kind + params)
- `webapp.data.job_finished` — Job 완료/실패
- `webapp.screening.run` — 스크리닝 실행
- `webapp.screening.delete` — 결과 삭제
- `webapp.risk.custom_stress` — 사용자 정의 스트레스 계산

## 6. 테스트 전략

### 6.1 Security 테스트 (필수)
- 비밀번호 재입력 없이 설정 수정 거부 (401)
- 일반 user 역할이 settings 수정 거부 (403)
- Rate limit 경계 (10회/10분)
- Fernet 암호화/복호화 라운드트립
- 키 불일치 시 복호화 실패 → 명시적 에러

### 6.2 Import 테스트
- `.env`에 키 있고 DB 비어있음 → import 후 DB에 있음
- `.env`와 DB 동일 키 → skip, DB 값 유지
- dry-run: DB 변경 없음

### 6.3 도메인 테스트
- Portfolio: 모드별 데이터 반환 (paper/live/backtest), 없는 모드는 빈 응답
- Risk: 캐시 hit/miss 동작, 동일 스냅샷은 캐시 반환
- Screening: Job 생성 → 실행 → 결과 저장 → 조회
- Data: update Job 트리거 → 진행률 전파
- Settings: CRUD 라운드트립, 마스킹, 감사 로그

### 6.4 E2E (Playwright 확장)
- 모드 전환 (Paper → Backtest → 다시 Paper)
- Settings → API 키 변경 → 감사 로그 확인
- Data update Job 실행 → 완료까지 관찰
- Screening 실행 → Job 완료 → 상세 페이지 이동

### 6.5 회귀 방지
- Phase 1 기존 976개 테스트 유지
- Phase 2 신규 ~50+ 테스트 추가

## 7. 태스크 분해 (Phase 2)

### Part A — Backend Foundation (Tasks 1-6)
1. `SettingsRepository` (webapp.db settings 테이블 + Fernet 암호화)
2. `SettingsService` (DB → .env fallback, `load_env_overrides`)
3. `RiskReportCacheRepository`
4. `ScreeningRepository`
5. `ScreeningRunner` 서비스
6. Data Jobs 서비스 (update / collect-financials / wisereport / short)

### Part B — Backend API (Tasks 7-14)
7. Portfolio API (summary / history / attribution, mode param)
8. Risk API (report / stress / limits, 캐시 연동)
9. Custom stress API (캐시 skip)
10. Screening API (조회/실행/삭제, Job 연동)
11. Data API (status / scheduler / 4종 Job 실행)
12. Settings API (category별 조회/수정, 비밀번호 재확인)
13. Audit API (event 조회, 필터)
14. Dashboard home API (aggregate)

### Part C — Backend CLI & Migration (Tasks 15-16)
15. `ap webapp init-encrypt-key` / `rotate-encrypt-key` / `set` / `list`
16. `ap webapp import-env` + 감사 wiring

### Part D — Frontend Common (Tasks 17-18)
17. `useMode` hook + `ModeSelector` 컴포넌트 + topbar 통합
18. `useMarketHours` + `lib/format.ts`

### Part E — Frontend Home + Portfolio (Tasks 19-22)
19. 홈 대시보드 (Layout A, 5 위젯 통합)
20. Portfolio summary
21. Portfolio history
22. Portfolio attribution

### Part F — Frontend Risk + Screening (Tasks 23-29)
23. Risk overview
24. Risk stress (기본 시나리오 표)
25. Custom stress form
26. Risk limits
27. Screening list + form
28. Screening detail
29. Screening job progress 연결

### Part G — Frontend Data + Settings + Audit (Tasks 30-36)
30. Data dashboard (status + scheduler)
31. Data action buttons + disabled collect_all + 툴팁
32. Data job progress
33. Settings 탭 쉘 + API keys 탭
34. Settings 리스크 리밋 탭
35. Settings 알림 + 백테스트 기본값 탭
36. Audit viewer

### Part H — Integration (Tasks 37-38)
37. Sidebar 업데이트 (disabled 해제, 아이콘 개선)
38. Playwright E2E 확장

## 8. Phase 2 완료 기준

- [ ] 38개 태스크 전부 commit
- [ ] `pytest tests/webapp/` 통과 (신규 ~50+ 테스트)
- [ ] 기존 `pytest tests/` 통과 (Phase 1 976개 회귀 없음)
- [ ] `ruff check alphapulse/` 클린
- [ ] `cd webapp-ui && pnpm build` 성공
- [ ] Playwright E2E 통과 (서비스 기동 환경)
- [ ] 수동 검증:
  - [ ] 홈 대시보드 표시
  - [ ] 모드 전환 (Paper → Backtest)
  - [ ] Portfolio/Risk/Screening/Data 각 페이지 정상 동작
  - [ ] Settings → API 키 변경 → 감사 로그 기록 확인
  - [ ] Data update Job 실행 → 진행률 표시
- [ ] 운영 문서 업데이트

## 9. 롤아웃 순서

**단계 1:** Part A+B+C (백엔드 + CLI) 완료 → API 존재, UI는 Phase 1 상태
**단계 2:** Part D+E (프론트 공통 + Home/Portfolio) → 홈 + Portfolio 사용 가능
**단계 3:** Part F (Risk + Screening) → 분석 기능 사용 가능
**단계 4:** Part G+H (Data + Settings + Audit + E2E) → Phase 2 릴리스

각 단계 PR 분리 가능. Phase 1 수준의 subagent-driven 실행.

## 10. 스코프 제외 (Phase 3로 이월)

- 실매매 UI (주문 생성/취소)
- Market Pulse 대시보드 / Briefing 이력 / Feedback 적중률
- Postgres / Redis 전환 + Tenants 모델
- Settings Service 방안 B (DI 교체) — Phase 2는 방안 A (env override) 사용

## 11. 설계 원칙 요약

1. **기존 코드 무변경** — `alphapulse/trading/*` 읽기만. Phase 1과 동일
2. **Phase 1 패턴 재사용** — Job 인프라, 인증, 미들웨어, shadcn/ui 모두 동일
3. **Settings hybrid** — DB Fernet + .env fallback. 후방 호환 + 웹 편집 가능
4. **안전 우선** — collect_all은 웹 차단, 비밀번호 재입력, Rate limit, 감사 로그
5. **모드 분리** — URL searchParam 기반, 전역 셀렉터
6. **캐싱으로 성능** — Risk 리포트는 스냅샷 해시 캐싱
7. **Phase 3 대비** — 신규 테이블 `tenant_id` 선반영
