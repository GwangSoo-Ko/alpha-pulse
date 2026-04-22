"""Briefing API — 저장된 브리핑 조회 + Job 실행."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from pydantic import BaseModel

from alphapulse.core.storage.briefings import BriefingStore
from alphapulse.webapp.auth.deps import get_current_user
from alphapulse.webapp.store.jobs import JobRepository
from alphapulse.webapp.store.users import User

router = APIRouter(prefix="/api/v1/briefings", tags=["briefings"])


class BriefingSummary(BaseModel):
    date: str
    score: float
    signal: str
    has_synthesis: bool
    has_commentary: bool
    created_at: float


class BriefingListResponse(BaseModel):
    items: list[BriefingSummary]
    page: int
    size: int
    total: int


class BriefingDetail(BaseModel):
    date: str
    created_at: float
    pulse_result: dict
    content_summaries: list[str]
    commentary: str | None
    synthesis: str | None
    quant_msg: str
    synth_msg: str
    feedback_context: dict | None
    daily_result_msg: str
    news: dict
    post_analysis: dict | None
    generated_at: str


class RunBriefingRequest(BaseModel):
    date: str | None = None


class RunBriefingResponse(BaseModel):
    job_id: str
    reused: bool


def get_briefing_store(request: Request) -> BriefingStore:
    return request.app.state.briefing_store


def get_jobs(request: Request) -> JobRepository:
    return request.app.state.jobs


def _row_to_summary(row: dict) -> BriefingSummary:
    payload = row["payload"] or {}
    pulse = payload.get("pulse_result") or {}
    return BriefingSummary(
        date=row["date"],
        score=float(pulse.get("score") or 0.0),
        signal=str(pulse.get("signal") or ""),
        has_synthesis=bool(payload.get("synthesis")),
        has_commentary=bool(payload.get("commentary")),
        created_at=row["created_at"],
    )


def _row_to_detail(row: dict) -> BriefingDetail:
    payload = row["payload"] or {}
    return BriefingDetail(
        date=row["date"],
        created_at=row["created_at"],
        pulse_result=payload.get("pulse_result") or {},
        content_summaries=payload.get("content_summaries") or [],
        commentary=payload.get("commentary"),
        synthesis=payload.get("synthesis"),
        quant_msg=payload.get("quant_msg") or "",
        synth_msg=payload.get("synth_msg") or "",
        feedback_context=payload.get("feedback_context"),
        daily_result_msg=payload.get("daily_result_msg") or "",
        news=payload.get("news") or {"articles": []},
        post_analysis=payload.get("post_analysis"),
        generated_at=payload.get("generated_at") or "",
    )


@router.get("/latest", response_model=BriefingDetail | None)
async def get_latest(
    user: User = Depends(get_current_user),
    store: BriefingStore = Depends(get_briefing_store),
):
    rows = store.get_recent(days=1)
    if not rows:
        return None
    return _row_to_detail(rows[0])


@router.get("", response_model=BriefingListResponse)
async def list_briefings(
    days: int = Query(30, ge=1, le=365),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    store: BriefingStore = Depends(get_briefing_store),
):
    rows = store.get_recent(days=days)
    total = len(rows)
    start = (page - 1) * size
    sliced = rows[start:start + size]
    return BriefingListResponse(
        items=[_row_to_summary(r) for r in sliced],
        page=page,
        size=size,
        total=total,
    )


@router.get("/{date}", response_model=BriefingDetail)
async def get_briefing(
    date: str = Path(..., pattern=r"^\d{8}$", description="YYYYMMDD"),
    user: User = Depends(get_current_user),
    store: BriefingStore = Depends(get_briefing_store),
):
    row = store.get(date)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Briefing not found for {date}")
    return _row_to_detail(row)
