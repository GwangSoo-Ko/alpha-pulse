"""Portfolio API — summary / history / attribution."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel

from alphapulse.webapp.auth.deps import get_current_user
from alphapulse.webapp.store.readers.portfolio import PortfolioReader
from alphapulse.webapp.store.users import User

router = APIRouter(prefix="/api/v1/portfolio", tags=["portfolio"])

Mode = Literal["paper", "live", "backtest"]


class SnapshotResponse(BaseModel):
    date: str
    cash: float
    total_value: float
    daily_return: float
    cumulative_return: float
    drawdown: float
    positions: list


class HistoryResponse(BaseModel):
    items: list[SnapshotResponse]


class AttributionResponse(BaseModel):
    date: str
    strategy_returns: dict
    factor_returns: dict
    sector_returns: dict


def get_reader(request: Request) -> PortfolioReader:
    return request.app.state.portfolio_reader


@router.get("", response_model=SnapshotResponse | None)
async def get_portfolio(
    mode: Mode = "paper",
    _: User = Depends(get_current_user),
    reader: PortfolioReader = Depends(get_reader),
):
    dto = reader.get_latest(mode=mode)
    if dto is None:
        return None
    return SnapshotResponse(**dto.__dict__)


@router.get("/history", response_model=HistoryResponse)
async def get_history(
    mode: Mode = "paper",
    days: int = Query(30, ge=1, le=365),
    _: User = Depends(get_current_user),
    reader: PortfolioReader = Depends(get_reader),
):
    items = reader.get_history(mode=mode, days=days)
    return HistoryResponse(
        items=[SnapshotResponse(**d.__dict__) for d in items],
    )


@router.get("/attribution", response_model=AttributionResponse | None)
async def get_attribution(
    mode: Mode = "paper",
    date: str | None = None,
    _: User = Depends(get_current_user),
    reader: PortfolioReader = Depends(get_reader),
):
    if not date:
        date = datetime.now().strftime("%Y%m%d")
    dto = reader.get_attribution(mode=mode, date=date)
    if dto is None:
        return None
    return AttributionResponse(**dto.__dict__)
