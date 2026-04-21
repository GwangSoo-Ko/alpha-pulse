"""Content API — BlogPulse 리포트 조회 + Job 실행."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from pydantic import BaseModel

from alphapulse.webapp.auth.deps import get_current_user
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


def _validate_filename(name: str) -> str:
    """경로 조작 차단 — .md 확장자, 슬래시/점점/숨김 금지."""
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
        items=[ReportSummary(**i) for i in result["items"]],
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
