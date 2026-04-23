"""Content API — BlogPulse 리포트 조회 + Job 실행."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Path, Query, Request
from pydantic import BaseModel

from alphapulse.webapp.auth.deps import get_current_user
from alphapulse.webapp.jobs.runner import JobRunner
from alphapulse.webapp.services.content_runner import run_content_monitor_async
from alphapulse.webapp.store.jobs import JobRepository
from alphapulse.webapp.store.readers.content import ContentReader
from alphapulse.webapp.store.users import User

router = APIRouter(prefix="/api/v1/content", tags=["content"])


class ReportSummary(BaseModel):
    filename: str
    title: str
    category: str
    published: str
    analyzed_at: str
    source: str
    source_tag: str = ""
    highlight: str | None = None


class ReportListResponse(BaseModel):
    items: list[ReportSummary]
    page: int
    size: int
    total: int
    categories: list[str]


class ReportDetail(BaseModel):
    filename: str
    title: str
    category: str
    published: str
    analyzed_at: str
    source: str
    source_tag: str = ""
    body: str


class MonitorRunRequest(BaseModel):
    pass


class MonitorRunResponse(BaseModel):
    job_id: str
    reused: bool


def get_content_reader(request: Request) -> ContentReader:
    return request.app.state.content_reader


def get_jobs(request: Request) -> JobRepository:
    return request.app.state.jobs


def get_runner(request: Request) -> JobRunner:
    return request.app.state.job_runner


def _validate_filename(name: str) -> str:
    """경로 조작 차단 — .md 확장자, 슬래시/점점/숨김/null byte 금지."""
    if "\x00" in name:
        raise HTTPException(400, "Invalid filename — null byte not allowed")
    if not name.endswith(".md"):
        raise HTTPException(400, "Invalid filename — must end with .md")
    if "/" in name or "\\" in name or ".." in name or name.startswith("."):
        raise HTTPException(400, "Invalid filename — path traversal not allowed")
    return name


@router.get("/reports", response_model=ReportListResponse)
async def list_reports(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    category: list[str] | None = Query(None),
    date_from: str | None = Query(None, alias="from", max_length=8),
    date_to: str | None = Query(None, alias="to", max_length=8),
    q: str | None = Query(None, max_length=200),
    sort: str = Query("newest", pattern="^(newest|oldest)$"),
    user: User = Depends(get_current_user),
    reader: ContentReader = Depends(get_content_reader),
):
    result = reader.list_reports(
        categories=category,
        date_from=date_from,
        date_to=date_to,
        query=q,
        sort=sort,  # type: ignore[arg-type]
        page=page,
        size=size,
    )
    return ReportListResponse(
        items=[
            ReportSummary(
                filename=i["filename"],
                title=i["title"],
                category=i["category"],
                published=i["published"],
                analyzed_at=i["analyzed_at"],
                source=i["source"],
                source_tag=i.get("source_tag", ""),
                highlight=i.get("highlight"),
            )
            for i in result["items"]
        ],
        page=result["page"],
        size=result["size"],
        total=result["total"],
        categories=result["categories"],
    )


@router.get("/reports/{filename:path}", response_model=ReportDetail)
async def get_report(
    filename: str = Path(...),
    user: User = Depends(get_current_user),
    reader: ContentReader = Depends(get_content_reader),
):
    _validate_filename(filename)
    detail = reader.get_report(filename)
    if detail is None:
        raise HTTPException(404, "Report not found")
    return ReportDetail(**detail)


@router.post("/monitor/run", response_model=MonitorRunResponse)
async def run_monitor(
    body: MonitorRunRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    jobs: JobRepository = Depends(get_jobs),
    runner: JobRunner = Depends(get_runner),
):
    # 원자적 중복 감지 + 생성 (TOCTOU race 제거)
    job_id = str(uuid.uuid4())
    job, created = jobs.create_or_return_running_by_kind(
        kind="content_monitor",
        job_id=job_id, params={}, user_id=user.id,
    )
    if not created:
        return MonitorRunResponse(job_id=job.id, reused=True)
    try:
        request.app.state.audit.log(
            "webapp.content.monitor.run",
            component="webapp",
            data={"user_id": user.id, "job_id": job_id},
            mode="live",
        )
    except AttributeError:
        pass

    async def _run():
        await runner.run(
            job_id,
            run_content_monitor_async,
        )

    background_tasks.add_task(_run)
    return MonitorRunResponse(job_id=job_id, reused=False)
