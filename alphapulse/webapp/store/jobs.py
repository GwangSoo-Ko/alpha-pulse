"""JobRepository — data/webapp.db jobs 테이블."""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

from alphapulse.webapp.jobs.models import Job, JobKind, JobStatus


def _row_to_job(row: sqlite3.Row) -> Job:
    return Job(
        id=row["id"],
        kind=row["kind"],
        status=row["status"],
        progress=row["progress"],
        progress_text=row["progress_text"] or "",
        params=json.loads(row["params"]) if row["params"] else {},
        result_ref=row["result_ref"],
        error=row["error"],
        user_id=row["user_id"],
        tenant_id=row["tenant_id"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        started_at=row["started_at"],
        finished_at=row["finished_at"],
    )


class JobRepository:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)

    def create(
        self,
        job_id: str,
        kind: JobKind,
        params: dict,
        user_id: int,
        tenant_id: int | None = None,
    ) -> None:
        now = time.time()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO jobs (id, kind, status, progress, "
                "progress_text, params, user_id, tenant_id, "
                "created_at, updated_at) "
                "VALUES (?, ?, 'pending', 0.0, '', ?, ?, ?, ?, ?)",
                (
                    job_id, kind,
                    json.dumps(params, ensure_ascii=False),
                    user_id, tenant_id, now, now,
                ),
            )

    def get(self, job_id: str) -> Job | None:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM jobs WHERE id = ?", (job_id,)
            ).fetchone()
        return _row_to_job(row) if row else None

    def update_progress(
        self, job_id: str, progress: float, text: str,
    ) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE jobs SET progress = ?, progress_text = ?, "
                "updated_at = ? WHERE id = ?",
                (progress, text, time.time(), job_id),
            )

    def update_status(
        self,
        job_id: str,
        status: JobStatus,
        *,
        started_at: float | None = None,
        finished_at: float | None = None,
        result_ref: str | None = None,
        error: str | None = None,
    ) -> None:
        fields = ["status = ?", "updated_at = ?"]
        values: list = [status, time.time()]
        if started_at is not None:
            fields.append("started_at = ?")
            values.append(started_at)
        if finished_at is not None:
            fields.append("finished_at = ?")
            values.append(finished_at)
        if result_ref is not None:
            fields.append("result_ref = ?")
            values.append(result_ref)
        if error is not None:
            fields.append("error = ?")
            values.append(error)
        values.append(job_id)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                f"UPDATE jobs SET {', '.join(fields)} WHERE id = ?",
                values,
            )

    def list_by_status(self, status: JobStatus) -> list[Job]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM jobs WHERE status = ? ORDER BY created_at",
                (status,),
            ).fetchall()
        return [_row_to_job(r) for r in rows]

    def find_running_by_kind_and_date(
        self, kind: JobKind, date: str,
    ) -> Job | None:
        """kind 와 params.date 가 일치하는 pending/running Job 을 1건 반환.

        중복 실행 요청 방지용. 동일 날짜의 다른 Job 이 진행 중이면 그걸 재사용.
        동시 호출 시 이 메서드 → create 사이에 race window 가 존재하므로
        호출부(API 레이어)에서 추가 보호가 필요할 수 있다.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM jobs WHERE kind = ? "
                "AND status IN ('pending', 'running') "
                "AND json_extract(params, '$.date') = ? "
                "ORDER BY created_at DESC LIMIT 1",
                (kind, date),
            ).fetchone()
        return _row_to_job(row) if row else None

    def find_running_by_kind(self, kind: JobKind) -> Job | None:
        """kind 가 일치하는 pending/running Job 을 1건 반환.

        date 무관 중복 실행 방지용 (날짜 개념 없는 연속 스트림 Job).
        동시 호출 시 이 메서드 → create 사이에 race window 가 존재하므로
        호출부(API 레이어)에서 추가 보호가 필요할 수 있다.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM jobs WHERE kind = ? "
                "AND status IN ('pending', 'running') "
                "ORDER BY created_at DESC LIMIT 1",
                (kind,),
            ).fetchone()
        return _row_to_job(row) if row else None
