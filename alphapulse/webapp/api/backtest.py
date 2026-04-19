"""Backtest API — Phase 1. 조회(Task 14) + 실행(Task 15)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from alphapulse.webapp.auth.deps import get_current_user, require_role
from alphapulse.webapp.store.readers.backtest import BacktestReader
from alphapulse.webapp.store.users import User

router = APIRouter(prefix="/api/v1/backtest", tags=["backtest"])


def get_reader(request: Request) -> BacktestReader:
    return request.app.state.backtest_reader


class RunSummaryResponse(BaseModel):
    run_id: str
    name: str
    strategies: list[str]
    start_date: str
    end_date: str
    initial_capital: float
    final_value: float
    benchmark: str
    metrics: dict
    created_at: float


class RunListResponse(BaseModel):
    items: list[RunSummaryResponse]
    page: int
    size: int
    total: int


class RunDetailResponse(BaseModel):
    run_id: str
    name: str
    strategies: list[str]
    start_date: str
    end_date: str
    initial_capital: float
    final_value: float
    benchmark: str
    params: dict
    metrics: dict
    created_at: float


@router.get("/runs", response_model=RunListResponse)
async def list_runs(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    name: str | None = None,
    _: User = Depends(get_current_user),
    reader: BacktestReader = Depends(get_reader),
):
    p = reader.list_runs(page=page, size=size, name_contains=name)
    return RunListResponse(
        items=[RunSummaryResponse(**s.__dict__) for s in p.items],
        page=p.page,
        size=p.size,
        total=p.total,
    )


@router.get("/runs/{run_id}", response_model=RunDetailResponse)
async def get_run(
    run_id: str,
    _: User = Depends(get_current_user),
    reader: BacktestReader = Depends(get_reader),
):
    full = reader.get_run_full(run_id)
    if not full:
        raise HTTPException(status_code=404, detail="Run not found")
    return RunDetailResponse(**full.__dict__)


@router.get("/runs/{run_id}/snapshots")
async def get_snapshots(
    run_id: str,
    _: User = Depends(get_current_user),
    reader: BacktestReader = Depends(get_reader),
):
    s = reader.resolve_run(run_id)
    if not s:
        raise HTTPException(status_code=404, detail="Run not found")
    return {"items": reader.get_snapshots(s.run_id)}


@router.get("/runs/{run_id}/trades")
async def get_trades(
    run_id: str,
    code: str | None = None,
    winner: bool | None = None,
    _: User = Depends(get_current_user),
    reader: BacktestReader = Depends(get_reader),
):
    s = reader.resolve_run(run_id)
    if not s:
        raise HTTPException(status_code=404, detail="Run not found")
    return {"items": reader.get_trades(s.run_id, code=code, winner=winner)}


@router.get("/runs/{run_id}/positions")
async def get_positions(
    run_id: str,
    date: str | None = None,
    code: str | None = None,
    _: User = Depends(get_current_user),
    reader: BacktestReader = Depends(get_reader),
):
    s = reader.resolve_run(run_id)
    if not s:
        raise HTTPException(status_code=404, detail="Run not found")
    return {"items": reader.get_positions(s.run_id, date=date, code=code)}


@router.get("/compare")
async def compare_runs(
    ids: str = Query(..., description="comma-separated run ids/prefixes"),
    _: User = Depends(get_current_user),
    reader: BacktestReader = Depends(get_reader),
):
    parts = [p.strip() for p in ids.split(",") if p.strip()]
    if len(parts) != 2:
        raise HTTPException(
            status_code=400, detail="ids must have exactly 2 values",
        )
    a = reader.get_run_full(parts[0])
    b = reader.get_run_full(parts[1])
    if not a or not b:
        raise HTTPException(status_code=404, detail="One or both not found")
    return {"a": a.__dict__, "b": b.__dict__}


@router.delete("/runs/{run_id}")
async def delete_run(
    run_id: str,
    _: User = Depends(require_role("admin")),
    reader: BacktestReader = Depends(get_reader),
):
    s = reader.resolve_run(run_id)
    if not s:
        raise HTTPException(status_code=404, detail="Run not found")
    reader.delete_run(s.run_id)
    return {"ok": True}
