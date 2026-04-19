# AlphaPulse Web Frontend Design

AlphaPulse 트레이딩 플랫폼의 웹 기반 프론트엔드 서비스 설계 문서.
기존 CLI 도구로만 운영되던 시스템에 웹 UI 레이어를 추가하여 조회/운영 편의성을 확보하고,
궁극적으로는 SaaS 형태로 확장 가능한 아키텍처를 갖춘다.

## 1. 요구사항 요약

| 항목 | 결정 |
|------|------|
| 배포 형태 | 홈서버 + Cloudflare Tunnel (HTTPS 자동, 포트 노출 없음) |
| 데이터베이스 | SQLite 유지 (기존 `data/*.db` 재사용 + 신규 `data/webapp.db`) |
| 사용자 범위 | Phase 1-2: 단일 관리자. Phase 3: 멀티테넌트 SaaS로 확장 |
| 실시간성 | 장중 10~30초 polling (WebSocket 불필요) |
| 스택 | Next.js 15+ (App Router) + FastAPI + TypeScript + Python |
| 액션 범위 | Phase 1-2: 조회 + 백테스트/스크리닝/수집 실행. 실매매는 CLI 유지. Phase 3: 실매매 UI 확장 |
| 디자인 | 도메인별 하이브리드 (Backtest 거래 이력은 밀도↑, 리포트는 여백↑) |
| 보안 | Defense in Depth. CVE 스캔 자동화, 프레임워크별 취약점 대응 |
| 모니터링 | 운영/장애 전용 Telegram 채널 분리 (콘텐츠 채널과 별도) |

## 2. 아키텍처

### 2.1 시스템 전체 구조

```
  [User Browser]
        │ HTTPS
        ▼
  [Cloudflare Tunnel]          ← 외부 노출, TLS 자동, WAF/Managed Rules
        │
  ┌─────┴──────────────────────────────────────────┐
  │ Home Server (Linux)                             │
  │                                                  │
  │  ┌──────────────────┐   ┌─────────────────────┐ │
  │  │ Next.js (3000)   │──▶│ FastAPI (8000)      │ │
  │  │ - App Router SSR │HTTP│ - 도메인 API         │ │
  │  │ - shadcn/ui      │   │ - 인증/세션          │ │
  │  │ - 인증 미들웨어  │   │ - 백그라운드 태스크  │ │
  │  └──────────────────┘   └──────────┬──────────┘ │
  │                                     │            │
  │                          ┌──────────▼─────────┐ │
  │                          │ alphapulse 패키지  │ │
  │                          │ (기존 코드, 불변)   │ │
  │                          │ market/content/    │ │
  │                          │ trading/ 등         │ │
  │                          └──────────┬─────────┘ │
  │                                     │            │
  │                          ┌──────────▼─────────┐ │
  │                          │ SQLite 다수         │ │
  │                          │ data/*.db +         │ │
  │                          │ data/webapp.db      │ │
  │                          └────────────────────┘ │
  └──────────────────────────────────────────────────┘
```

**핵심 설계 원칙:**
- 기존 `alphapulse/` 패키지는 **무변경**. 웹 서버는 `alphapulse/webapp/` 신규 모듈
- 기존 DB 스키마 **무변경** (인덱스만 추가 허용)
- 사용자 대상 알림(브리핑)과 운영/장애 알림은 **별도 Telegram 채널**로 분리

### 2.2 Phase 분할

| Phase | 범위 | 기간 | 핵심 가치 |
|-------|------|------|-----------|
| **Phase 1** | Auth 인프라 + Backtest 도메인 (조회 + 실행) | 2~3주 | CLI에서 가장 불편한 백테스트 관리 해소 |
| **Phase 2** | Portfolio/Risk/Screening/Data 도메인 + Settings | 3~4주 | 일일 트레이딩 운영 UI |
| **Phase 3** | Market/Briefing/Feedback 도메인 + SaaS 전환 + 실매매 UI | 4~6주 | 전체 서비스 완성 + 멀티테넌시 |

### 2.3 도메인 카탈로그

아래 모든 도메인이 설계에 포함되며 Phase별로 단계적 구현된다.

| 도메인 | 주요 화면 | Phase |
|---|---|---|
| Auth | 로그인, 세션 관리 | 1 |
| Backtest | 결과 목록 / 상세 / 거래 이력 / 포지션 / 비교 / 실행 폼 / 진행률 | 1 |
| Portfolio | 현재 상태 / 성과 이력 차트 / 성과 귀속 | 2 |
| Risk | 리스크 리포트 / VaR / 드로다운 / 스트레스 테스트 / 리밋 | 2 |
| Screening | 팩터 스크리닝 / 전략별 시그널 / 유니버스 관리 | 2 |
| Data | 수집 현황 / 스케줄 상태 / 갭 감지 / 수동 트리거 | 2 |
| Settings | API 키 관리, 리스크 리밋, 알림 설정 | 2 |
| Market Pulse | 11개 지표 카드 / Pulse Score 차트 / 히스토리 | 3 |
| Briefing | 일일 브리핑 이력 / AI 해설 / 성과 추적 | 3 |
| Feedback | 적중률 / 지표별 성과 / 사후 분석 보고서 | 3 |
| Trading Run | 오케스트레이터 실행 상태 (조회 전용) / 실매매 UI (Phase 3b) | 3 |

## 3. 백엔드 설계 (FastAPI)

### 3.1 디렉토리 구조

```
alphapulse/
├── market/, content/, trading/, ...     # 기존 — 무변경
└── webapp/                              # 신규
    ├── __init__.py
    ├── main.py                          # FastAPI 앱 엔트리
    ├── config.py                        # 웹 설정 (CORS, 세션 시크릿 등)
    ├── auth/
    │   ├── models.py                    # User, Session Pydantic 모델
    │   ├── routes.py                    # POST /login, /logout, GET /me
    │   ├── deps.py                      # get_current_user, require_role
    │   └── security.py                  # bcrypt, 세션 쿠키
    ├── jobs/
    │   ├── models.py                    # Job dataclass
    │   ├── runner.py                    # asyncio 기반 백그라운드 실행기
    │   └── routes.py                    # GET /jobs/{id}
    ├── api/                             # 도메인별 라우터 (Phase별 추가)
    │   ├── backtest.py                  # Phase 1
    │   ├── portfolio.py                 # Phase 2
    │   ├── risk.py                      # Phase 2
    │   ├── screening.py                 # Phase 2
    │   ├── data.py                      # Phase 2
    │   ├── market.py                    # Phase 3
    │   ├── briefing.py                  # Phase 3
    │   └── feedback.py                  # Phase 3
    ├── store/
    │   ├── webapp_db.py                 # data/webapp.db 초기화
    │   ├── users.py                     # UserRepository
    │   ├── sessions.py                  # SessionRepository
    │   ├── jobs.py                      # JobRepository
    │   └── readers/                     # 기존 DB 조회 어댑터
    │       ├── backtest.py
    │       ├── portfolio.py
    │       ├── trading_data.py
    │       └── market.py
    ├── middleware/
    │   ├── rate_limit.py
    │   ├── audit.py                     # 기존 AuditLogger 재사용
    │   ├── csrf.py
    │   └── security_headers.py
    └── notifier.py                      # MonitorNotifier (운영 채널 전용)
```

### 3.2 API 라우트 (Phase 1)

모든 경로 `/api/v1/` 접두사. 응답은 JSON (Pydantic 모델).

| Method | Path | 설명 |
|---|---|---|
| POST | `/api/v1/auth/login` | 이메일/비번 → 세션 쿠키 발급 |
| POST | `/api/v1/auth/logout` | 세션 무효화 |
| GET | `/api/v1/auth/me` | 현재 사용자 정보 |
| GET | `/api/v1/csrf-token` | CSRF 토큰 발급 |
| GET | `/api/v1/backtest/runs` | 결과 목록 (페이지네이션, 정렬, 필터) |
| GET | `/api/v1/backtest/runs/{run_id}` | 상세 (metadata + metrics) |
| GET | `/api/v1/backtest/runs/{run_id}/snapshots` | 일별 자산 곡선 |
| GET | `/api/v1/backtest/runs/{run_id}/trades` | 거래 이력 (filter: code, winner) |
| GET | `/api/v1/backtest/runs/{run_id}/positions` | 포지션 (filter: date, code) |
| GET | `/api/v1/backtest/compare?ids=a,b` | 두 결과 비교 |
| DELETE | `/api/v1/backtest/runs/{run_id}` | 결과 삭제 |
| POST | `/api/v1/backtest/run` | 백테스트 실행 → `{job_id}` 반환 |
| GET | `/api/v1/jobs/{job_id}` | job 상태/진행률/결과 run_id |

### 3.3 API 계약 원칙

- 페이지네이션: `?page=1&size=50`
- 필터: query string
- 에러: RFC 7807 problem+json
  ```json
  {
    "type": "https://alphapulse/errors/invalid-request",
    "title": "Invalid backtest parameters",
    "status": 400,
    "detail": "end date must be after start date",
    "instance": "/api/v1/backtest/run"
  }
  ```
- 시간: UTC ISO8601, 날짜는 `YYYYMMDD` 문자열 (기존 컨벤션 유지)
- API 버전: `/api/v1/` (v2 신설 시 v1 당분간 병행)

### 3.4 인증 — 세션 쿠키

**선택 이유:** JWT 대비 즉시 무효화 가능, XSS 영향 최소, SaaS 전환 시 그대로 사용 가능.

**쿠키 설정:**
- 이름: `ap_session`
- 속성: `HttpOnly; Secure; SameSite=Strict; Path=/`
- 값: 서버 사이드 세션 ID (`secrets.token_urlsafe(32)`)
- 만료: 24시간 기본, 15분마다 사용 시 슬라이딩 갱신, 절대 만료 30일

**FastAPI 의존성:**
```python
async def get_current_user(
    session_cookie: str = Cookie(None, alias="ap_session"),
) -> User:
    if not session_cookie:
        raise HTTPException(401, "Not authenticated")
    sess = await session_repo.get(session_cookie)
    if not sess or sess.is_expired or sess.revoked_at:
        raise HTTPException(401, "Session invalid")
    await session_repo.touch(sess.id)  # 슬라이딩 갱신
    return await user_repo.get(sess.user_id)

def require_role(*allowed: str):
    async def _check(user: User = Depends(get_current_user)):
        if user.role not in allowed:
            raise HTTPException(403, "Forbidden")
        return user
    return _check
```

### 3.5 백그라운드 태스크 패턴

**설계 선택:** 인프로세스 asyncio 태스크 + SQLite 진행률 저장 (Approach A).
Phase 3에서 Redis + ARQ로 교체 가능하도록 시그니처 호환.

```python
# alphapulse/webapp/jobs/runner.py
@dataclass
class Job:
    id: str                # UUID
    kind: str              # "backtest" | "screening" | "data_update"
    status: str            # "pending" | "running" | "done" | "failed" | "cancelled"
    progress: float        # 0.0 ~ 1.0
    progress_text: str
    params: dict           # JSON
    result_ref: str
    error: str
    user_id: int
    tenant_id: int | None  # Phase 3 대비
    created_at, updated_at, started_at, finished_at: float

async def run_job(job_id: str, func, *args, **kwargs):
    """백그라운드로 job 실행. 진행률을 jobs 테이블에 write."""
    job_repo.update_status(job_id, "running", started_at=time.time())
    def _on_progress(current: int, total: int, text: str = ""):
        job_repo.update_progress(job_id, current / total, text)
    try:
        result = await asyncio.to_thread(
            func, *args, progress_callback=_on_progress, **kwargs
        )
        job_repo.update_status(
            job_id, "done", result_ref=str(result), finished_at=time.time()
        )
    except Exception as e:
        job_repo.update_status(
            job_id, "failed", error=str(e), finished_at=time.time()
        )
```

**Orphan 복구:**
FastAPI startup 훅에서 `status='running'`인 job을 `failed`로 정리 (프로세스 재시작 가정).

**ARQ 호환성 확보:**
`run_job` 시그니처는 `async def <task>(ctx, *args, **kwargs)` 형태를 흉내내어
Phase 3에서 ARQ worker로 옮기더라도 실제 실행 함수(`func`)는 무변경.

## 4. 프론트엔드 설계 (Next.js)

### 4.1 디렉토리 구조 (Next.js 15+ App Router)

```
webapp-ui/                              # alphapulse 레포 내 monorepo
├── app/
│   ├── layout.tsx                      # 루트 레이아웃 (theme provider)
│   ├── (auth)/
│   │   └── login/page.tsx
│   ├── (dashboard)/                    # 로그인 필요 구간
│   │   ├── layout.tsx                  # 사이드바 + 상단바 + 세션 재검증
│   │   ├── page.tsx                    # 홈 대시보드
│   │   ├── backtest/                   # Phase 1
│   │   │   ├── page.tsx                # 리스트
│   │   │   ├── [runId]/
│   │   │   │   ├── page.tsx            # 상세
│   │   │   │   ├── trades/page.tsx
│   │   │   │   └── positions/page.tsx
│   │   │   ├── new/page.tsx            # 실행 폼
│   │   │   ├── jobs/[jobId]/page.tsx   # 진행률
│   │   │   └── compare/page.tsx
│   │   ├── portfolio/, risk/, screening/, data/    # Phase 2
│   │   └── market/, briefing/, feedback/           # Phase 3
│   └── api/                            # Next.js API 라우트 (BFF, 선택)
├── components/
│   ├── ui/                             # shadcn/ui
│   ├── charts/                         # 도메인별 차트 래퍼
│   │   ├── equity-curve.tsx            # TradingView Lightweight
│   │   ├── drawdown.tsx
│   │   ├── monthly-heatmap.tsx
│   │   └── ...
│   ├── layout/
│   │   ├── sidebar.tsx
│   │   ├── topbar.tsx
│   │   └── breadcrumb.tsx
│   └── domain/
│       ├── backtest/
│       ├── portfolio/
│       └── ...
├── lib/
│   ├── api-client.ts                   # FastAPI 호출 래퍼
│   ├── auth.ts                         # 세션 확인
│   └── utils.ts
├── hooks/
│   ├── use-job-status.ts               # 진행률 polling
│   ├── use-portfolio.ts                # 10~30s polling
│   └── ...
├── middleware.ts                       # 로그인 미들웨어 (추가 보호 레이어)
├── next.config.js
├── tailwind.config.ts
└── package.json
```

### 4.2 데이터 패칭 전략

| 유형 | 방식 | 예시 |
|---|---|---|
| 정적 데이터 (백테스트 상세, 거래 이력) | Server Component + fetch → FastAPI | 최초 렌더 빠름 |
| 실시간 갱신 (포트폴리오, Job 진행률) | Client Component + TanStack Query polling | `refreshInterval: 2_000` (job) / `30_000` (포트폴리오) |
| 사용자 액션 (백테스트 트리거) | Server Action → FastAPI POST | 폼 제출 직후 job_id로 리다이렉트 |

### 4.3 상태 관리

- 서버 상태: **TanStack Query** (`@tanstack/react-query`)
- 클라이언트 상태: React state + `useContext` (테마, 사이드바 토글)
- 폼: `react-hook-form` + `zod` (FastAPI OpenAPI에서 `zod` 스키마 자동 생성)

### 4.4 UI 컴포넌트 & 차트

**컴포넌트:** `shadcn/ui` + Tailwind CSS
- 복사식 컴포넌트 → 의존성 최소
- 주요: Button, Card, Dialog, Table, Tabs, Command, Select, Toast, Skeleton

**차트:**
- 일반 지표/곡선: `Recharts` (shadcn/ui 궁합 좋음)
- 자산 곡선/대형 시계열: `TradingView Lightweight Charts` (무료, 성능 우수)
- 히트맵 (월별 수익률): `@nivo/heatmap` 또는 Recharts 커스텀

### 4.5 레이아웃 — 도메인별 하이브리드

공통 셸(사이드바 + 상단바) 안에서 도메인별 밀도를 다르게.

| 도메인 | 밀도 | 스타일 |
|---|---|---|
| Backtest 거래 이력, 포지션 | 높음 | 어두운 배경, 촘촘한 표 (shadcn Table + 가상 스크롤) |
| Backtest 상세, Portfolio 대시보드 | 중간 | 카드형 지표 + 큰 차트 |
| Risk 리포트, Briefing, Feedback | 낮음 | 문서형, 타이포 중심, 여백 풍부 |

**테마:** 다크 기본 + 라이트 토글. 시스템 선호 감지.

### 4.6 Phase 1 페이지 상세

1. **`/backtest`** — 결과 목록: 필터 바 + 테이블 + 정렬, `[새 백테스트]` `[비교 선택]`
2. **`/backtest/[runId]`** — 상세: 메타 + 6개 지표 카드 + 차트 탭 (자산 곡선, 드로다운, 월별 히트맵, 벤치마크 대비)
3. **`/backtest/[runId]/trades`** — 거래 이력: 밀도 높은 표, 필터 (종목/승패/기간), 요약
4. **`/backtest/[runId]/positions`** — 포지션: 날짜 슬라이더 + 종목 선택, 보유 수량 변화 차트
5. **`/backtest/new`** — 실행 폼: 전략/기간/자본/시장/Top N, `POST /api/v1/backtest/run` → job_id로 이동
6. **`/backtest/jobs/[jobId]`** — 진행률: 2초 polling, 완료 시 결과 redirect, 실패 시 재시도 옵션
7. **`/backtest/compare`** — 비교: 나란히 지표 카드 + 자산 곡선 오버레이

## 5. 데이터 모델

### 5.1 DB 파일 구성

| DB | 소유자 | 용도 | 웹앱 접근 |
|---|---|---|---|
| `data/trading.db` | `alphapulse/trading/data/` | OHLCV, 재무, 수급 | 읽기만 |
| `data/backtest.db` | `alphapulse/trading/backtest/` | runs, snapshots, trades, round_trips, positions | 읽기 + 삭제 |
| `data/portfolio.db` | `alphapulse/trading/portfolio/` | 포트폴리오 스냅샷/귀속/주문 | 읽기만 (Phase 2) |
| `data/audit.db` | `alphapulse/trading/core/audit.py` | 감사 추적 | 읽기 + append |
| `data/history.db`, `feedback.db`, `cache.db` | 기존 모듈들 | 각 도메인 | 읽기만 (Phase 3) |
| `data/webapp.db` | `alphapulse/webapp/store/` | **신규** — users, sessions, jobs | 쓰기 |

**원칙:** 기존 DB 스키마는 절대 변경하지 않는다. 인덱스만 추가 허용.

### 5.2 `data/webapp.db` 스키마

```sql
-- 사용자
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,            -- bcrypt cost 12
    role TEXT NOT NULL DEFAULT 'admin',     -- 'admin', 'user', 'readonly'
    tenant_id INTEGER,                      -- Phase 3 대비, 현재 NULL
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at REAL NOT NULL,
    last_login_at REAL
);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_tenant ON users(tenant_id);

-- 세션 (서버 사이드)
CREATE TABLE sessions (
    id TEXT PRIMARY KEY,                    -- secrets.token_urlsafe(32)
    user_id INTEGER NOT NULL,
    created_at REAL NOT NULL,
    expires_at REAL NOT NULL,
    ip TEXT,
    user_agent TEXT,
    revoked_at REAL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
CREATE INDEX idx_sessions_user ON sessions(user_id);
CREATE INDEX idx_sessions_expires ON sessions(expires_at);

-- 백그라운드 작업
CREATE TABLE jobs (
    id TEXT PRIMARY KEY,                    -- UUID
    kind TEXT NOT NULL,                     -- 'backtest', 'screening', 'data_update'
    status TEXT NOT NULL,                   -- 'pending', 'running', 'done', 'failed', 'cancelled'
    progress REAL DEFAULT 0.0,              -- 0.0 ~ 1.0
    progress_text TEXT DEFAULT '',
    params TEXT NOT NULL,                   -- JSON 입력
    result_ref TEXT,
    error TEXT,
    user_id INTEGER NOT NULL,
    tenant_id INTEGER,                      -- Phase 3 대비
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    started_at REAL,
    finished_at REAL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
CREATE INDEX idx_jobs_user ON jobs(user_id);
CREATE INDEX idx_jobs_status ON jobs(status);
CREATE INDEX idx_jobs_kind ON jobs(kind);
CREATE INDEX idx_jobs_created ON jobs(created_at DESC);

-- 로그인 잠금 (브루트포스 방어)
CREATE TABLE login_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL,
    ip TEXT NOT NULL,
    success INTEGER NOT NULL,
    attempted_at REAL NOT NULL
);
CREATE INDEX idx_login_attempts_email ON login_attempts(email, attempted_at);
CREATE INDEX idx_login_attempts_ip ON login_attempts(ip, attempted_at);

-- 알림 제한 추적 (운영 Telegram 채널 rate limit)
CREATE TABLE alert_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    level TEXT NOT NULL,
    first_sent_at REAL NOT NULL,
    last_sent_at REAL NOT NULL,
    count INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX idx_alert_log_title ON alert_log(title, last_sent_at);
```

### 5.3 기존 DB 인덱스 추가 (Phase 1)

```sql
-- backtest.db
CREATE INDEX IF NOT EXISTS idx_runs_created ON runs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_positions_date_lookup ON positions(run_id, date);
CREATE INDEX IF NOT EXISTS idx_positions_code_lookup ON positions(run_id, code);
```

### 5.4 DB 접근 레이어

기존 `BacktestStore` 등은 직접 호출하지 않고 얇은 어댑터로 감싼다:

```
alphapulse/webapp/store/readers/
├── backtest.py          # BacktestStore를 래핑, 페이지네이션·DTO 변환 추가
├── portfolio.py         # PortfolioStore 래핑
├── trading_data.py      # TradingStore 래핑
└── market.py            # history.db 등 조회
```

이로써 기존 스토어는 불변, 웹앱이 요구하는 형태(페이지네이션, 필터, 응답 DTO)는 어댑터에서만 처리.

### 5.5 동시성

- `PRAGMA journal_mode=WAL` 활성화 (reader-writer 병행)
- 쓰기 경로는 `webapp.db`(sessions/jobs) 중심 — 빈번한 write
- 기존 DB는 웹앱 프로세스에서 SELECT만 (백테스트 실행은 기존 `BacktestStore.save_run()` 그대로 호출)

## 6. 보안

### 6.1 전송 계층

| 요소 | 조치 |
|---|---|
| HTTPS | Cloudflare Tunnel TLS 자동 처리, 홈서버는 HTTP 내부 통신 |
| 포트 노출 | 홈서버에서 80/443 포트포워딩 **안 함** (Tunnel은 아웃바운드) |
| DNS | Cloudflare Proxy 활성 (오리진 IP 은닉) |
| Cloudflare WAF | OWASP Core Rule Set, Managed Rules 활성 |
| Cloudflare Access (선택) | Phase 3에서 이메일 OTP + SSO 엣지 인증 레이어 추가 권장 |

### 6.2 인증

#### 비밀번호
- `bcrypt` cost 12
- 최소 12자 + 영문/숫자/특수 조합 강제
- 비밀번호 리셋은 CLI (`ap webapp reset-password`)로만 — 원격 리셋 폼 없음

#### 세션 쿠키
- `HttpOnly; Secure; SameSite=Strict`
- 서버 사이드 세션 ID (`secrets.token_urlsafe(32)`)
- 만료 24시간 기본, 15분마다 슬라이딩 갱신, 절대 만료 30일
- 로그아웃 시 `revoked_at` 설정 → 즉시 무효화

#### 브루트포스 방어
- 로그인 시도: IP당 10회/분, 계정당 5회/15분
- 연속 5회 실패 시 계정 15분 잠금
- 잠금 해제: `ap webapp unlock-account <email>` (관리자 CLI)

#### 2FA (Phase 3)
- TOTP (Google Authenticator) 또는 Cloudflare Access 위임
- 실매매 액션은 2FA 재확인 강제

### 6.3 인가 (RBAC)

```
admin    : 모든 액션 + 사용자 관리
user     : 자신의 테넌트 데이터 조회/실행 (Phase 3)
readonly : 조회만, 액션 불가
```

테넌트 격리 (Phase 3): 모든 repository 함수 `tenant_id` 인자 강제, query에 자동 주입. 타입 시스템으로 강제.

### 6.4 요청/응답 보안

#### CSRF
- `SameSite=Strict` 기본 방어
- Double Submit Cookie 패턴: `GET /api/v1/csrf-token` → 쿠키 + body, 변경 요청 시 `X-CSRF-Token` 헤더 재제출
- Next.js Server Action은 자동 처리

#### XSS
- React 기본 escape 의존, 임의 HTML 주입 API 사용 금지 (ESLint 룰로 강제)
- CSP 헤더:
  ```
  Content-Security-Policy: default-src 'self';
    script-src 'self' 'nonce-{random}';
    style-src 'self' 'unsafe-inline';
    connect-src 'self' https://<fastapi-host>;
    frame-ancestors 'none';
  X-Frame-Options: DENY
  X-Content-Type-Options: nosniff
  Referrer-Policy: strict-origin-when-cross-origin
  ```

#### CORS
- Next.js와 FastAPI가 같은 도메인(Cloudflare Tunnel) → CORS 불필요
- 분리 시 `allow_origins=[<ui-origin>]`, `allow_credentials=True`

#### Rate Limiting
- 기본: IP당 60 req/분, 사용자당 300 req/분
- 백테스트 실행: 사용자당 5 req/시간
- 로그인: `6.2 브루트포스 방어` 참조
- 구현: `slowapi` 또는 자체

### 6.5 입력 검증

- FastAPI: Pydantic 모델로 모든 입력 타입/범위 검증 (자동)
- Next.js: `zod` 스키마, OpenAPI에서 자동 생성
- 파라미터화 쿼리 (기존 코드 `?` placeholder 사용 중, SQL injection 방어됨)

### 6.6 시크릿 관리

#### 환경 변수
- 기존: `KIS_APP_KEY`, `KIS_APP_SECRET`, `TELEGRAM_BOT_TOKEN`, `GEMINI_API_KEY`, `CLOUDFLARE_TUNNEL_TOKEN`
- 신규: `WEBAPP_SESSION_SECRET`, `WEBAPP_ENCRYPT_KEY`, `TELEGRAM_MONITOR_BOT_TOKEN`, `TELEGRAM_MONITOR_CHANNEL_ID`

#### 저장/로딩
- `.env` 파일 (`.gitignore`), 권한 600, 소유자 webapp user
- 프로덕션: systemd `EnvironmentFile` 또는 Docker secrets
- 로그/에러 응답에 출력 금지, `Config.__repr__` 마스킹

#### 회전
- API 키 정기 교체 절차: `docs/operations/secrets-rotation.md`
- Phase 3: 테넌트별 KIS 키는 Fernet 암호화로 `tenants.kis_app_key_encrypted` 저장

### 6.7 감사 로그

기존 `alphapulse/trading/core/audit.py` 확장:
- 로그인 성공/실패, 로그아웃, 세션 취소
- 백테스트 실행, 결과 삭제
- 리스크 리밋 변경, API 키 변경 (Phase 2)
- 실매매 관련 (Phase 3, 2FA 챌린지 포함)
- 레코드: `(timestamp, user_id, ip, action, target, details_json)`
- 보관: 최소 1년

### 6.8 에러 응답

- 내부 정보 노출 금지 (스택트레이스, DB 쿼리, 파일 경로)
- RFC 7807 problem+json (`3.3 API 계약 원칙` 참조)
- 500 에러: `detail`에 사유 미노출, `instance`에 trace ID만

### 6.9 프레임워크 CVE 대응

#### Next.js 주요 CVE

| CVE | 요약 | 대응 |
|---|---|---|
| CVE-2025-29927 (Critical) | `x-middleware-subrequest` 헤더로 미들웨어 우회 | Next.js ≥15.2.3 / ≥14.2.25 고정. Cloudflare Transform Rule로 위험 헤더 제거 |
| CVE-2024-51479 (High) | 미들웨어 없는 페이지 인증 우회 | 보호 라우트는 `layout.tsx`에서도 세션 재검증 |
| CVE-2024-46982 (High) | SSR 캐시 포이즈닝 | App Router만 사용, 사용자별 데이터는 `dynamic = 'force-dynamic'` |
| CVE-2024-34351 (Medium) | Server Actions SSRF | 외부 URL fetch 금지, 내부 FastAPI 호출도 allowlist |

**방어 원칙 — "미들웨어에만 의존하지 않는다":**

```tsx
// app/(dashboard)/layout.tsx
import { redirect } from "next/navigation"
import { getSession } from "@/lib/auth"
export default async function DashboardLayout({ children }) {
  const session = await getSession()
  if (!session) redirect("/login")  // 미들웨어 우회되어도 여기서 차단
  return <>{children}</>
}
```

**Cloudflare Transform Rule:**
```
Remove request header: x-middleware-subrequest
Remove request header: x-middleware-prefetch
```

#### 기타 프레임워크

| 항목 | 대응 |
|---|---|
| Starlette CVE-2024-47874 (DoS 멀티파트) | Starlette ≥0.40.0, 파일 업로드 없음으로 위험도 낮음 |
| Pydantic | v2 이상 (v1 EOL) |
| python-jose / PyJWT | **사용 안 함** (세션 쿠키 방식으로 JWT CVE 전체 회피) |
| uvicorn | `--proxy-headers --forwarded-allow-ips=127.0.0.1` |
| Node.js | LTS만 (22.x). `corepack + pnpm` 사용 |
| `next-auth` | **사용 안 함** (자체 세션 구현) |
| `react-hook-form`, `zod` | 최신 |
| `@tanstack/react-query` | 최신 |
| `recharts` / `d3-*` | prototype pollution 이력, 최신 고정 |
| `tailwindcss`, `postcss` | postcss ≥8.4.31 |
| `lightweight-charts` (TradingView) | 라이선스 확인, 최신 |
| `bcrypt` | ≥4.0 (C 바인딩) |
| `cryptography` | 정기 업데이트 (OpenSSL 영향) |

### 6.10 자동화된 취약점 스캔

#### 주간 파이프라인 (GitHub Actions or 로컬 cron)

```yaml
on:
  schedule: [{cron: "0 3 * * 1"}]  # 매주 월요일 03:00 UTC
jobs:
  python:
    - uv sync
    - uv run pip-audit --strict
    - uv run bandit -r alphapulse/
  node:
    - corepack enable && pnpm install --frozen-lockfile
    - pnpm audit --audit-level=high
    - npx osv-scanner --lockfile=pnpm-lock.yaml
  secrets:
    - gitleaks detect --source . --verbose
  docker:
    - trivy image alphapulse-webapp:latest
```

**결과 처리:**
- Critical/High → 모니터링 채널 즉시 알림
- Medium → 주간 리포트
- Low → 월간 리포트

#### 배포 전 (Pre-deploy Gate)
- `pip-audit --strict` → High 이상이면 배포 차단
- `pnpm audit --audit-level=high` → 차단
- `trivy image` → Critical 차단

### 6.11 의존성 버전 관리 정책

| 변경 | 정책 |
|---|---|
| Patch (1.2.3 → 1.2.4) | Dependabot/Renovate 자동 PR → CI 통과 시 자동 머지 |
| Minor (1.2 → 1.3) | 자동 PR → 수동 리뷰 |
| Major (1.x → 2.x) | 수동, 마이그레이션 검토 |
| 보안 픽스 | 메이저여도 긴급 적용 (CVSS ≥ 7.0) |

- `pnpm-lock.yaml`, `uv.lock` 반드시 커밋
- lockfile 무결성 CI 체크

### 6.12 SBOM

- **CycloneDX** 포맷 생성:
  ```bash
  uv run cyclonedx-py --format json -o sbom-python.json
  pnpm cyclonedx-npm --output sbom-node.json
  ```
- 배포마다 재생성, CVE 공지 시 즉시 영향 범위 파악

### 6.13 배포 보안 체크리스트

- [ ] Cloudflare Tunnel 토큰은 systemd 유닛에서만 읽기 (권한 600)
- [ ] 홈서버 SSH는 키 기반 + LAN 한정
- [ ] 서버 OS 자동 업데이트 활성화
- [ ] 일일 백업 + 외부 원격 동기화
- [ ] `.env` 권한 600, 소유자 webapp user
- [ ] FastAPI `--reload` 금지 (프로덕션)
- [ ] Next.js `next build` 후 `start`, `dev` 금지

### 6.14 Phase 3 실매매 UI 추가 보안

- 모든 매매 액션에 2FA 재확인
- IP 화이트리스트
- 주문 한도 (웹 UI에서는 주문당 최대 1,000만원 등)
- 확인 다이얼로그 + 타이핑 확인 ("SELL 005930 100주" 수동 타이핑)
- 이상 거래 탐지 (평소 대비 급격한 금액·빈도 → 자동 잠금)
- 취소/긴급정지만 허용 모드 (읽기만, 신규 주문 제한 옵션)

## 7. 에러 처리 & 복구

### 7.1 웹앱 레이어 에러

| 유형 | 처리 |
|---|---|
| FastAPI 호출 실패 (network) | TanStack Query 자동 재시도 3회, Toast 알림 |
| FastAPI 5xx | trace ID 표시 + 모니터링 채널 즉시 알림 |
| Job 실패 | `jobs.error` 기록, 프론트에 에러 + `[다시 시도]` |
| 세션 만료 (401) | 현재 경로 유지, 로그인 후 복귀 |
| Rate limit (429) | "잠시 후 다시 시도" Toast, 재시도 시간 표시 |

### 7.2 장애 복구

| 장애 | 복구 |
|---|---|
| FastAPI 재시작 중 Job 진행 | 시작 훅에서 `status='running'` → `failed, error='process restarted'` |
| Cloudflare Tunnel 단절 | cloudflared systemd `Restart=always` |
| SQLite 손상 | 일일 백업에서 복구, `PRAGMA integrity_check` 주기 실행 |
| 홈서버 전원 꺼짐 | UPS 권장, 복구 후 systemd 자동 기동 |

### 7.3 그레이스풀 셧다운
- SIGTERM 수신 시 FastAPI는 현재 요청 완료 후 종료
- 실행 중 Job은 cleanup 로직에서 `cancelled`로 표시

## 8. 테스트 전략

### 8.1 레이어별

| 레이어 | 도구 | 범위 |
|---|---|---|
| FastAPI 단위 | `pytest` + `httpx.AsyncClient` | 라우트, mock DB |
| FastAPI 통합 | `pytest` + tmp SQLite | 실제 DB, 기존 스토어와 조립 |
| 프론트 단위 | `vitest` + React Testing Library | 컴포넌트, 훅 |
| 프론트 E2E | `Playwright` | 로그인 → 백테스트 실행 → 결과 조회 |
| 보안 테스트 | `pytest` | CSRF 누락 거부, 잠금 동작, rate limit |

### 8.2 기존 테스트 보존
- `alphapulse/` 무변경 → 기존 863개 테스트 전부 유지
- `alphapulse/webapp/` 신규 테스트는 `tests/webapp/`
- 프론트 테스트는 `webapp-ui/__tests__/`

### 8.3 커버리지 목표
- 백엔드: 신규 코드 80% 이상
- 프론트: 컴포넌트 70%, 핵심 플로우 E2E 100%

## 9. 배포 & 운영

### 9.1 홈서버 구성

```
Linux (Ubuntu 24.04 LTS)
├── systemd units
│   ├── alphapulse-fastapi.service       # uvicorn
│   ├── alphapulse-webapp-ui.service     # next start
│   └── cloudflared.service              # Cloudflare Tunnel
├── /opt/alphapulse/                     # 프로젝트 루트
│   ├── alphapulse/                      # Python 패키지
│   ├── webapp-ui/                       # Next.js
│   ├── data/*.db                        # SQLite
│   ├── .env                             # 600 권한
│   └── logs/
└── /opt/alphapulse/backups/             # 일일 SQLite 백업
```

### 9.2 systemd 유닛 예시

```ini
# /etc/systemd/system/alphapulse-fastapi.service
[Unit]
Description=AlphaPulse FastAPI
After=network-online.target
[Service]
User=alphapulse
WorkingDirectory=/opt/alphapulse
EnvironmentFile=/opt/alphapulse/.env
ExecStart=/opt/alphapulse/.venv/bin/uvicorn alphapulse.webapp.main:app \
    --host 127.0.0.1 --port 8000 \
    --proxy-headers --forwarded-allow-ips=127.0.0.1
Restart=always
RestartSec=5
# 샌드박싱
ProtectSystem=strict
ReadWritePaths=/opt/alphapulse/data /opt/alphapulse/logs
PrivateTmp=true
NoNewPrivileges=true
[Install]
WantedBy=multi-user.target
```

### 9.3 Cloudflare Tunnel

```yaml
# /etc/cloudflared/config.yml
tunnel: <uuid>
credentials-file: /etc/cloudflared/<uuid>.json
ingress:
  - hostname: app.example.com
    service: http://127.0.0.1:3000   # Next.js
  - hostname: api.example.com
    service: http://127.0.0.1:8000   # FastAPI
  - service: http_status:404
```

### 9.4 백업

```bash
# /opt/alphapulse/scripts/backup.sh (매일 03:00 cron)
DATE=$(date +%Y%m%d)
mkdir -p /opt/alphapulse/backups/$DATE
for db in trading backtest portfolio audit feedback cache history webapp; do
    sqlite3 /opt/alphapulse/data/$db.db \
        ".backup /opt/alphapulse/backups/$DATE/$db.db"
done
# 원격 동기화 (Backblaze B2 등)
rclone sync /opt/alphapulse/backups/$DATE b2:alphapulse-backups/$DATE
# 7일 이전 로컬 백업 삭제
find /opt/alphapulse/backups -mindepth 1 -maxdepth 1 -type d -mtime +7 -exec rm -rf {} +
```

### 9.5 모니터링 — Telegram 채널 분리

**채널 이원화:**

| 채널 | 용도 | 환경변수 |
|---|---|---|
| 기존 — 콘텐츠 채널 | 일일 브리핑, 시장 해설, 거래 시그널 (사용자 대상) | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHANNEL_ID` |
| **신규 — 모니터링 채널** | **시스템 장애/경고/보안 이벤트 (운영자 대상)** | `TELEGRAM_MONITOR_BOT_TOKEN`, `TELEGRAM_MONITOR_CHANNEL_ID` |

**권장:** 별도 봇 + 별도 채널. 콘텐츠 봇이 탈취·스팸 당해도 운영 알림 보존.

**MonitorNotifier 구현 (`alphapulse/webapp/notifier.py`):**

```python
class MonitorNotifier:
    """운영/장애 전용 Telegram 알림."""
    def __init__(self, cfg: Config):
        self.token = cfg.TELEGRAM_MONITOR_BOT_TOKEN
        self.chat_id = cfg.TELEGRAM_MONITOR_CHANNEL_ID
        self.enabled = bool(self.token and self.chat_id)
    
    async def send(self, level: str, title: str, detail: str = "") -> None:
        if not self.enabled:
            return
        emoji = {"INFO": "ℹ️", "WARN": "⚠️", "ERROR": "🚨", "CRITICAL": "🔥"}[level]
        text = f"{emoji} [{level}] {title}"
        if detail:
            text += f"\n\n{detail[:3500]}"
        # Telegram API 호출
```

**이벤트 분류:**

| 모니터링 채널 (신규) | 콘텐츠 채널 (기존) |
|---|---|
| 서비스 기동/정지 | 일일 브리핑 발행 |
| FastAPI 5xx 급증 | 시장 해설 |
| 로그인 실패 과다 | 거래 시그널 |
| Rate limit 초과 | 실매매 체결 알림 (Phase 3) |
| Job 실패 | 사후 분석 리포트 |
| 백업 성공/실패 | |
| Cloudflare Tunnel 단절/복구 | |
| CVE 공지 (사용 중 라이브러리 해당 시) | |
| 보안 스캔 결과 (주간/긴급) | |
| 디스크/메모리 임계치 초과 | |

**원칙:** 이벤트 유형을 반드시 한 쪽으로만 보냄 (혼동 방지).

**알림 Rate Limiting:**

| 이벤트 | 제한 |
|---|---|
| 동일 에러 반복 | 5분 윈도우 내 같은 title은 1회만, 이후 `(N회 더 발생)` 요약 |
| 보안 스캔 결과 | 주간 1회, 긴급 Critical CVE만 즉시 |
| 백업 성공 | 요약만 (실패 시만 즉시) |
| Job 실패 | 즉시, 같은 job type 반복은 묶음 |

구현: `alert_log` 테이블 (`5.2` 참조) + in-memory sliding window.

**자가 점검:**
```bash
ap webapp verify-monitoring
# → 모니터 봇/채널로 테스트 메시지 발송
```

**선택적 확장 (Phase 3):** Grafana Cloud free tier + `node_exporter` Prometheus. 디스크/메모리/프로세스 상세 대시보드.

## 10. SaaS 확장 로드맵 (Phase 3)

### 10.1 전환 시 변경 범위

| 영역 | Phase 1-2 (현재) | Phase 3 (SaaS) | 마이그레이션 |
|---|---|---|---|
| DB | SQLite 단일 파일 | PostgreSQL | 중 (SQL 방언 거의 호환) |
| 세션 저장 | `webapp.db` sessions | Redis 또는 Postgres | 소 (repository 교체) |
| Job 큐 | asyncio + `webapp.db` | **ARQ + Redis** | 소 (시그니처 호환) |
| 인증 | 세션 쿠키 단일 관리자 | 동일 + 멀티유저 + 2FA | 소 (`tenant_id` nullable 이미 존재) |
| 데이터 격리 | 단일 테넌트 | `WHERE tenant_id = ?` 강제 주입 | 중 (repository 계층) |
| KIS API 키 | `.env` 파일 | `tenants.kis_app_key_encrypted` (Fernet) | 중 |
| 배포 | 홈서버 + Cloudflare Tunnel | 클라우드 (Fly/Railway/AWS) + Redis + Postgres | 대 |

### 10.2 전환 순서

1. SQLite → Postgres (`alembic` 도입, 스키마 이관)
2. Sessions → Redis (기존 세션 폐기)
3. Jobs → ARQ + Redis (인터페이스 호환)
4. `tenants` 테이블 신설 + 기존 데이터 `tenant_id=1` 일괄 UPDATE
5. KIS 키 암호화 이관
6. 2FA 온보딩
7. 실매매 UI (6.14 추가 보안 적용)

각 단계 rollback 가능, feature flag로 점진 활성화.

### 10.3 Phase 3 스키마 마이그레이션 예시

```sql
-- Phase 3
CREATE TABLE tenants (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    kis_app_key_encrypted TEXT,
    kis_app_secret_encrypted TEXT,
    created_at REAL NOT NULL
);

-- 기존 테이블에 tenant_id 추가
ALTER TABLE portfolio_snapshots ADD COLUMN tenant_id INTEGER;
ALTER TABLE backtest_runs ADD COLUMN tenant_id INTEGER;
-- ... 동일 패턴

-- 이관: 기존 단일사용자 데이터는 tenant_id=1로
UPDATE portfolio_snapshots SET tenant_id = 1 WHERE tenant_id IS NULL;
```

## 11. 문서화

### 11.1 설계 문서 (본 spec)
- `docs/superpowers/specs/2026-04-19-webapp-design.md`

### 11.2 운영 문서 (구현 중/후 작성)
- `docs/operations/webapp-deployment.md` — 초기 설치 가이드
- `docs/operations/webapp-runbook.md` — 장애 대응 절차
- `docs/operations/security-checklist.md` — 분기 점검 체크리스트
- `docs/operations/secrets-rotation.md` — 시크릿 로테이션 절차
- `docs/operations/backup-restore.md` — 백업/복구 절차
- `docs/operations/saas-migration.md` — Phase 3 전환 절차 (Phase 3 시작 시 작성)

### 11.3 API 문서
- FastAPI 자동 생성 `/docs` (개발 환경만, 프로덕션 비활성)
- OpenAPI JSON → Next.js `zod` 스키마 자동 생성 (`openapi-zod-client`)

## 12. Phase별 작업 분해 (씨앗)

상세 태스크는 별도 implementation plan 문서에서 확장.

### Phase 1 (MVP, 약 2~3주)

1. 레포 구조 생성 (`alphapulse/webapp/`, `webapp-ui/`)
2. `data/webapp.db` 초기화 + users/sessions/jobs/login_attempts/alert_log 스키마
3. FastAPI 앱 기본 + 세션 쿠키 인증 + CSRF 미들웨어 + security headers
4. Next.js 앱 기본 + shadcn/ui 초기 설정 + 로그인 페이지 + 세션 재검증
5. Backtest API (runs/trades/positions 조회 + 삭제)
6. Backtest UI (리스트/상세/거래/포지션/비교)
7. Backtest 실행 + Job 인프라 (진행률 polling)
8. 보안: Rate limit, CSRF, CSP/보안 헤더, Next.js CVE 패치 확인, Cloudflare Transform Rule
9. MonitorNotifier + 모니터링 Telegram 채널 연결 + 이벤트 wiring
10. 배포: systemd + Cloudflare Tunnel + 일일 백업 스크립트
11. 주간 취약점 스캔 파이프라인
12. 운영 문서 초안 작성 (deployment/runbook/security-checklist)

### Phase 2 (약 3~4주)

13. Portfolio 도메인 API·UI
14. Risk 도메인 API·UI
15. Screening 도메인 API·UI (실행 포함)
16. Data 도메인 API·UI (수집 현황, 수동 트리거)
17. Settings 페이지 (API 키 관리, 알림 설정)
18. 감사 로그 뷰

### Phase 3 (약 4~6주)

19. Market Pulse / Briefing / Feedback 도메인
20. SaaS 전환 — SQLite → Postgres
21. Sessions/Jobs → Redis + ARQ
22. Tenants 모델, 2FA (TOTP)
23. KIS API 키 암호화 (Fernet)
24. 실매매 UI (6.14 추가 보안 전체 적용)

## 13. 신규 의존성

### Python (`pyproject.toml` 추가)
```
fastapi>=0.115
uvicorn[standard]>=0.32
pydantic>=2.9
bcrypt>=4.0
cryptography>=43
slowapi>=0.1.9
pip-audit>=2.7
bandit>=1.7
cyclonedx-py>=6.0
```

### Node (`webapp-ui/package.json`)
```
next@^15
react@^19
typescript@^5
tailwindcss@^3.4
@tanstack/react-query@^5
react-hook-form@^7
zod@^3
recharts@^2
lightweight-charts@^4
```

## 14. 테스트 전략 (요약)

```bash
pytest tests/ -v                      # 기존 + webapp 포함 (신규 webapp 테스트 +α)
pytest tests/webapp/ -v               # 웹앱 단위/통합
cd webapp-ui && pnpm test             # 프론트 단위
cd webapp-ui && pnpm playwright test  # E2E
```

**테스트 원칙:**
- 기존 TDD 원칙 유지 (test first → red → implement → green)
- 외부 API (Cloudflare, Telegram) → mock
- 세션/CSRF 등 보안 테스트는 경계값 (정상/우회 시도)

## 15. 설계 원칙 요약

1. **기존 코드 무변경** — `alphapulse/`는 읽기만. 스키마 변경 없음 (인덱스만 추가)
2. **Phase별 점진 구현** — Phase 1 → 2 → 3 각각 독립 릴리스 가능
3. **SaaS 확장성** — `tenant_id` 컬럼 선반영, repository 시그니처 호환
4. **Defense in Depth** — 다층 방어 (엣지 + 앱 + DB 접근)
5. **미들웨어에만 의존하지 않기** — Next.js CVE 대응, 레이아웃에서도 세션 재검증
6. **세션 쿠키 방식** — JWT CVE 전체 회피
7. **모니터링 분리** — 사용자 콘텐츠 채널과 운영/장애 채널 분리
8. **자동 취약점 스캔** — 주간 + 배포 전 게이트
9. **SBOM 관리** — 배포마다 재생성, CVE 영향 추적
10. **실매매 UI는 Phase 3** — 추가 보안 장치(2FA, IP 화이트리스트, 확인 타이핑) 적용 후
