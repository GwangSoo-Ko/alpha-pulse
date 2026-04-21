"""Market Pulse API — 이력 조회 + Job 실행."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from pydantic import BaseModel

from alphapulse.core.storage import PulseHistory
from alphapulse.webapp.auth.deps import get_current_user
from alphapulse.webapp.store.jobs import JobRepository
from alphapulse.webapp.store.users import User

router = APIRouter(prefix="/api/v1/market", tags=["market"])


class PulseSnapshot(BaseModel):
    date: str
    score: float
    signal: str
    indicator_scores: dict[str, float | None]
    indicator_descriptions: dict[str, str | None]
    period: str
    created_at: float


class HistoryItem(BaseModel):
    date: str
    score: float
    signal: str


class HistoryResponse(BaseModel):
    items: list[HistoryItem]


class RunPulseRequest(BaseModel):
    date: str | None = None


class RunPulseResponse(BaseModel):
    job_id: str
    reused: bool


def get_pulse_history(request: Request) -> PulseHistory:
    return request.app.state.pulse_history


def get_jobs(request: Request) -> JobRepository:
    return request.app.state.jobs


def _row_to_snapshot(row: dict) -> PulseSnapshot:
    """PulseHistory.get 결과 dict 를 API 응답 모델로 변환.

    과거 저장분은 indicator_descriptions 키가 없을 수 있고,
    반대로 description 만 있고 score 가 없는 키도 있을 수 있다.
    두 키 집합의 합집합을 사용하고, 한쪽에만 있는 키는 다른 쪽을 None 으로 채운다.
    """
    details = row.get("details") or {}
    scores = details.get("indicator_scores") or {}
    descriptions_raw = details.get("indicator_descriptions") or {}
    # 키 집합: scores 와 descriptions 중 아무 쪽에 있는 모든 키.
    # 한쪽에만 있으면 다른 쪽은 None 으로 채움.
    all_keys = set(scores.keys()) | set(descriptions_raw.keys())
    scores_full = {k: scores.get(k) for k in all_keys}
    descriptions = {k: descriptions_raw.get(k) for k in all_keys}
    return PulseSnapshot(
        date=row["date"],
        score=row["score"],
        signal=row["signal"],
        indicator_scores=scores_full,
        indicator_descriptions=descriptions,
        period=details.get("period", "daily"),
        created_at=row["created_at"],
    )


@router.get("/pulse/latest", response_model=PulseSnapshot | None)
async def get_latest(
    user: User = Depends(get_current_user),
    history: PulseHistory = Depends(get_pulse_history),
):
    rows = history.get_recent(days=1)
    if not rows:
        return None
    return _row_to_snapshot(rows[0])


@router.get("/pulse/history", response_model=HistoryResponse)
async def get_history(
    days: int = Query(30, ge=1, le=365),
    user: User = Depends(get_current_user),
    history: PulseHistory = Depends(get_pulse_history),
):
    rows = history.get_recent(days=days)
    rows_asc = sorted(rows, key=lambda r: r["date"])
    return HistoryResponse(
        items=[
            HistoryItem(date=r["date"], score=r["score"], signal=r["signal"])
            for r in rows_asc
        ]
    )


@router.get("/pulse/{date}", response_model=PulseSnapshot)
async def get_pulse(
    date: str = Path(..., pattern=r"^\d{8}$", description="YYYYMMDD"),
    user: User = Depends(get_current_user),
    history: PulseHistory = Depends(get_pulse_history),
):
    row = history.get(date)
    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"Pulse history not found for {date}",
        )
    return _row_to_snapshot(row)
