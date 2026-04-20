"""Jobs 라우트 — 진행률 polling 전용 GET 엔드포인트."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from alphapulse.webapp.auth.deps import get_current_user
from alphapulse.webapp.store.jobs import JobRepository
from alphapulse.webapp.store.users import User


class JobResponse(BaseModel):
    id: str
    kind: str
    status: str
    progress: float
    progress_text: str
    result_ref: str | None
    error: str | None
    created_at: float
    started_at: float | None
    finished_at: float | None


def get_jobs(request: Request) -> JobRepository:
    return request.app.state.jobs


router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: str,
    user: User = Depends(get_current_user),
    jobs: JobRepository = Depends(get_jobs),
):
    j = jobs.get(job_id)
    if j is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if j.user_id != user.id and user.role != "admin":
        raise HTTPException(status_code=403, detail="Forbidden")
    return JobResponse(
        id=j.id,
        kind=j.kind,
        status=j.status,
        progress=j.progress,
        progress_text=j.progress_text,
        result_ref=j.result_ref,
        error=j.error,
        created_at=j.created_at,
        started_at=j.started_at,
        finished_at=j.finished_at,
    )
