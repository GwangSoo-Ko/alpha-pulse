# 알림 시스템 — Design Spec

**작성일**: 2026-04-24
**대상 페이지**: 전역 상단바 (벨 아이콘 + 드롭다운)
**목표**: 4개 핵심 이벤트(Job 완료/실패, 브리핑 저장, Risk alert, Pulse 극단값) 를 인앱 알림 센터로 표시. 사용자가 페이지 열어둔 동안 30초 폴링으로 업데이트.

---

## 1. 원칙

- **Push 모델**: 이벤트 발생 지점에서 `NotificationStore.add()` 호출.
- **이벤트 소스 4종**: Job, Briefing, Risk, Pulse — 범위 명확.
- **글로벌 읽음 상태**: `is_read` 단일 컬럼 (단일 관리자 운영 가정, YAGNI).
- **폴링 30초**: WebSocket/SSE 오버엔지니어링 회피.
- **`MonitorNotifier`(Telegram) 와 분리**: 중복 가능하나 우선 독립.
- **보관 정책**: 조회 시 `created_at > NOW - 30일` 필터. cron 삭제 없음.
- **호출 전반 try/except 격리**: 알림 실패가 원래 기능 중단시키지 않음.

## 2. 데이터 모델

### 2.1 신규 테이블 (기존 `webapp.db` 확장)

```sql
CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,            -- 'job' | 'briefing' | 'risk' | 'pulse'
    level TEXT NOT NULL,           -- 'info' | 'warn' | 'error'
    title TEXT NOT NULL,
    body TEXT,
    link TEXT,
    created_at REAL NOT NULL,
    is_read INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_notifications_created_at
    ON notifications(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_notifications_unread
    ON notifications(is_read, created_at DESC)
    WHERE is_read = 0;
```

partial index 로 `unread-count` 쿼리 성능 확보.

### 2.2 Notification 예시

| kind | level | title | body | link |
|---|---|---|---|---|
| `briefing` | info | 브리핑 생성 완료 | 2026-04-24 · +62.5 긍정 | `/briefings/20260424` |
| `job` | error | 백테스트 Job 실패 | `momentum_20260424` · 타임아웃 | `/backtest/jobs/{job_id}` |
| `risk` | warn | Risk 경고 | 집중 리스크 25% 초과 | `/risk` |
| `pulse` | info | Pulse 극단값 감지 | +85.2 강한 강세 | `/market/pulse` |

### 2.3 제약

- `kind` 화이트리스트: `{"job", "briefing", "risk", "pulse"}`
- `level` 화이트리스트: `{"info", "warn", "error"}`
- 중복 억제: 동일 `(kind, link)` 가 1분 이내 반복 시 삽입 skip
- 보관: 조회 시 `WHERE created_at >= NOW - 30 days`

## 3. Backend

### 3.1 `NotificationStore` 신규

**파일**: `alphapulse/webapp/store/notifications.py`

```python
"""알림 저장소 — 이벤트별 push 기록, 조회, 읽음 관리."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Literal

NotificationKind = Literal["job", "briefing", "risk", "pulse"]
NotificationLevel = Literal["info", "warn", "error"]

ALLOWED_KINDS = {"job", "briefing", "risk", "pulse"}
ALLOWED_LEVELS = {"info", "warn", "error"}

DEDUP_WINDOW_SECONDS = 60
RETENTION_DAYS = 30


class NotificationStore:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)

    def add(
        self,
        *,
        kind: NotificationKind,
        level: NotificationLevel,
        title: str,
        body: str | None = None,
        link: str | None = None,
    ) -> int | None:
        """알림을 추가한다. 1분 내 동일 (kind, link) 중복은 skip."""
        if kind not in ALLOWED_KINDS or level not in ALLOWED_LEVELS:
            return None
        now = time.time()
        dedup_after = now - DEDUP_WINDOW_SECONDS
        with sqlite3.connect(self.db_path) as conn:
            if link is not None:
                dup = conn.execute(
                    "SELECT id FROM notifications "
                    "WHERE kind = ? AND link = ? AND created_at >= ? "
                    "LIMIT 1",
                    (kind, link, dedup_after),
                ).fetchone()
                if dup is not None:
                    return None
            cur = conn.execute(
                "INSERT INTO notifications (kind, level, title, body, link, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (kind, level, title, body, link, now),
            )
            return cur.lastrowid

    def list_recent(self, limit: int = 20) -> list[dict]:
        cutoff = time.time() - RETENTION_DAYS * 86400
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM notifications "
                "WHERE created_at >= ? "
                "ORDER BY created_at DESC LIMIT ?",
                (cutoff, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def unread_count(self) -> int:
        cutoff = time.time() - RETENTION_DAYS * 86400
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM notifications "
                "WHERE is_read = 0 AND created_at >= ?",
                (cutoff,),
            ).fetchone()
        return row[0]

    def mark_read(self, notification_id: int) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                "UPDATE notifications SET is_read = 1 WHERE id = ?",
                (notification_id,),
            )
            return cur.rowcount > 0

    def mark_all_read(self) -> int:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                "UPDATE notifications SET is_read = 1 WHERE is_read = 0",
            )
            return cur.rowcount
```

### 3.2 API `alphapulse/webapp/api/notifications.py` (신규)

```python
@router.get("/notifications", response_model=NotificationListResponse)
async def list_notifications(
    limit: int = Query(20, ge=1, le=100),
    _: User = Depends(get_current_user),
    store: NotificationStore = Depends(get_notification_store),
):
    return NotificationListResponse(
        items=[Notification(**n) for n in store.list_recent(limit=limit)],
    )


@router.get("/notifications/unread-count")
async def get_unread_count(
    _: User = Depends(get_current_user),
    store: NotificationStore = Depends(get_notification_store),
):
    return {"count": store.unread_count()}


@router.post("/notifications/{notification_id}/read")
async def mark_read(
    notification_id: int,
    _: User = Depends(get_current_user),
    store: NotificationStore = Depends(get_notification_store),
):
    if not store.mark_read(notification_id):
        raise HTTPException(404)
    return {"ok": True}


@router.post("/notifications/read-all")
async def mark_all_read(
    _: User = Depends(get_current_user),
    store: NotificationStore = Depends(get_notification_store),
):
    return {"count": store.mark_all_read()}
```

Pydantic 모델:

```python
class Notification(BaseModel):
    id: int
    kind: str
    level: str
    title: str
    body: str | None = None
    link: str | None = None
    created_at: float
    is_read: int

class NotificationListResponse(BaseModel):
    items: list[Notification]
```

### 3.3 이벤트 발행 지점 (4곳)

**원칙**: 모든 호출을 `try/except` 로 격리.

**① Job 완료/실패** — `alphapulse/webapp/jobs/runner.py` 의 `JobRunner.run()` finally

```python
# status == "done" 분기:
try:
    self.notification_store.add(
        kind="job", level="info",
        title=f"{kind_label} Job 완료",
        body=params_summary,
        link=f"/{kind_to_path[kind]}/jobs/{job_id}",
    )
except Exception as e:
    logger.warning("notification add failed: %s", e)

# status == "failed" 분기:
try:
    self.notification_store.add(
        kind="job", level="error",
        title=f"{kind_label} Job 실패",
        body=error_msg[:200],
        link=f"/{kind_to_path[kind]}/jobs/{job_id}",
    )
except Exception as e:
    logger.warning(...)
```

**② 브리핑 저장** — `alphapulse/briefing/orchestrator.py` save 성공 직후

```python
if notification_store is not None:
    try:
        notification_store.add(
            kind="briefing", level="info",
            title="브리핑 생성 완료",
            body=f"{date} · {signal_label}",
            link=f"/briefings/{date}",
        )
    except Exception as e:
        logger.warning(...)
```

**③ Risk alert** — `alphapulse/webapp/store/readers/risk.py` `get_report()` alerts 반환 시

```python
if report_dict["alerts"]:
    for alert in report_dict["alerts"]:
        try:
            self.notification_store.add(
                kind="risk", level="warn",
                title="Risk 경고",
                body=alert["message"],
                link="/risk",
            )
        except Exception as e:
            logger.warning(...)
```

**④ Pulse 극단값** — `alphapulse/core/storage/history.py` `save()` 에서 `abs(score) >= 80`

```python
if self.notification_store is not None and abs(score) >= 80:
    try:
        self.notification_store.add(
            kind="pulse", level="info",
            title=f"Pulse {'강세' if score > 0 else '약세'} 극단값",
            body=f"{date} · {'+' if score > 0 else ''}{score:.1f}",
            link="/market/pulse",
        )
    except Exception as e:
        logger.warning(...)
```

### 3.4 Dependency Injection

- `app.state.notification_store = NotificationStore(db_path=webapp_db)` (`webapp/main.py`)
- `JobRunner`, `BriefingOrchestrator`, `RiskReader`, `PulseHistory` 각각 생성자에 `notification_store: NotificationStore | None = None` 선택적 파라미터 추가
- webapp `create_app` 에서 인스턴스 주입, CLI entry 는 None (알림 기록 skip)

### 3.5 스키마 통합

`alphapulse/webapp/store/webapp_db.py` 의 `SCHEMA` 상수에 `CREATE TABLE notifications` + 2개 인덱스 DDL 추가.

## 4. Frontend

### 4.1 `NotificationBell` 컴포넌트

**파일**: `webapp-ui/components/layout/notification-bell.tsx`

- `"use client"`, polling 30초 간격으로 `/api/v1/notifications/unread-count`
- 벨 클릭 → 드롭다운 open + `/api/v1/notifications?limit=20` 조회
- 각 row: 제목(level 색상), body, 상대 시각 ("3분 전")
- 안 읽음 표시: 왼쪽에 초록 점
- link 존재 시 `<Link>` wrapping (클릭 시 read 상태로)
- "모두 읽음" 버튼: `POST /notifications/read-all` 후 로컬 상태 업데이트
- 개별 row 클릭: `POST /notifications/{id}/read`

상세 코드는 spec §4.1 참고.

### 4.2 상단바 통합

**파일**: `webapp-ui/components/layout/topbar.tsx` (또는 실제 상단바)

기존 상단바 우측 (로그아웃 버튼 좌측) 에 `<NotificationBell />` 삽입.

### 4.3 파일 구조

```
신규:
  alphapulse/webapp/store/notifications.py
  alphapulse/webapp/api/notifications.py
  webapp-ui/components/layout/notification-bell.tsx

수정:
  alphapulse/webapp/store/webapp_db.py             (스키마)
  alphapulse/webapp/main.py                        (app.state.notification_store)
  alphapulse/webapp/jobs/runner.py                 (Job 발행)
  alphapulse/briefing/orchestrator.py              (Briefing 발행)
  alphapulse/webapp/store/readers/risk.py          (Risk 발행)
  alphapulse/core/storage/history.py               (Pulse 발행)
  webapp-ui/components/layout/topbar.tsx           (Bell 통합)
```

## 5. 에러 처리

| 상황 | 동작 |
|---|---|
| `kind`/`level` 화이트리스트 밖 | silent None |
| 1분 내 동일 `(kind, link)` | dedup skip, None |
| `add()` DB 예외 | 호출부 try/except warning, 원 기능 계속 |
| `list_recent` DB 락 | SQLite 기본 5초 재시도 |
| 폴링 API 401 | FE apiFetch 가 /login redirect |
| `mark_read` missing id | 404 |
| FE 네트워크 에러 | 무시, 다음 폴링에서 복구 |
| 30일 이전 알림 | 조회 cutoff 로 숨김 (실제 삭제는 별도) |
| 드롭다운 열린 채 새 알림 | 다음 열림 시 refresh (폴링 제약) |

## 6. 테스트

### 6.1 Backend 단위 — `tests/webapp/store/test_notifications.py`

- `test_add_inserts_row`
- `test_add_rejects_invalid_kind`
- `test_add_rejects_invalid_level`
- `test_add_dedups_same_kind_link_within_1min`
- `test_add_allows_same_kind_different_link`
- `test_list_recent_orders_desc`
- `test_list_recent_respects_limit`
- `test_list_recent_filters_retention_cutoff`
- `test_unread_count_counts_only_is_read_zero`
- `test_mark_read_returns_true_on_success`
- `test_mark_read_returns_false_on_missing_id`
- `test_mark_all_read_returns_affected_count`

### 6.2 Backend API — `tests/webapp/api/test_notifications.py`

- `test_list_notifications_returns_items`
- `test_unread_count_endpoint`
- `test_mark_read_endpoint`
- `test_mark_read_404_on_missing`
- `test_mark_all_read_endpoint`
- `test_all_endpoints_require_auth`

### 6.3 이벤트 발행 회귀

- `tests/webapp/jobs/test_runner.py`: `test_job_done_emits_notification`, `test_job_failed_emits_notification`
- `tests/briefing/test_orchestrator.py`: `test_briefing_save_emits_notification`
- `tests/webapp/store/readers/test_risk.py` 또는 `test_risk_reader.py`: `test_risk_alerts_emit_notification`
- `tests/core/storage/test_history.py` 또는 유사: `test_pulse_score_above_80_emits`, `test_pulse_score_below_minus_80_emits`, `test_pulse_score_40_no_emit`

### 6.4 스키마 회귀

- `tests/webapp/store/test_webapp_db.py`: `test_notifications_table_exists`, `test_notifications_indexes_exist`

### 6.5 FE E2E — `webapp-ui/e2e/notifications.spec.ts`

- 벨 아이콘 상단바 가시성
- 클릭 시 드롭다운 노출
- 빈 상태 "알림 없음" 문구

## 7. 성공 기준

- pytest 1355 + 신규 (~25) 통과
- ruff clean
- pnpm lint / pnpm build 성공
- 수동 검증:
  - 백테스트 Job 실행 → 완료 시 벨 뱃지 증가
  - 브리핑 실행 → 완료 후 알림 노출
  - Risk 경고 상태에서 /risk 접속 → 알림 도착
  - Pulse score ±80 이상 → 극단값 알림

## 8. 범위 밖

- Telegram 통합 발사 (기존 `MonitorNotifier` 와 중복 가능)
- 사용자별 읽음 상태 (단일 관리자 가정)
- WebSocket/SSE 실시간
- 알림 카테고리 on/off 설정
- 이메일/Slack 전달
- 알림 검색/필터, 전체 목록 페이지
- 자동 TTL 삭제 cron
- 대량 알림 시 pagination
