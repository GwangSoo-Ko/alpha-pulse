"""Dashboard home — 여러 도메인 aggregate 1회 호출."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from alphapulse.webapp.auth.deps import get_current_user
from alphapulse.webapp.store.readers.audit import AuditReader
from alphapulse.webapp.store.readers.data_status import DataStatusReader
from alphapulse.webapp.store.readers.portfolio import PortfolioReader
from alphapulse.webapp.store.readers.risk import RiskReader
from alphapulse.webapp.store.users import User

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


class HomeResponse(BaseModel):
    portfolio: dict | None
    portfolio_history: list
    risk: dict | None
    data_status: dict
    recent_backtests: list
    recent_audits: list


def get_portfolio(request: Request) -> PortfolioReader:
    return request.app.state.portfolio_reader


def get_risk(request: Request) -> RiskReader:
    return request.app.state.risk_reader


def get_data(request: Request) -> DataStatusReader:
    return request.app.state.data_status_reader


def get_audit(request: Request) -> AuditReader:
    return request.app.state.audit_reader


@router.get("/home", response_model=HomeResponse)
async def home(
    request: Request,
    _: User = Depends(get_current_user),
    portfolio: PortfolioReader = Depends(get_portfolio),
    risk: RiskReader = Depends(get_risk),
    data: DataStatusReader = Depends(get_data),
    audit: AuditReader = Depends(get_audit),
):
    mode = "paper"
    snap = portfolio.get_latest(mode=mode)
    history = portfolio.get_history(mode=mode, days=30)
    risk_data = risk.get_report(mode=mode) if snap else None
    bt_store = request.app.state.backtest_reader
    recent_bt = bt_store.list_runs(page=1, size=3)
    audit_result = audit.query(page=1, size=10)

    return HomeResponse(
        portfolio=snap.__dict__ if snap else None,
        portfolio_history=[s.__dict__ for s in history],
        risk=risk_data,
        data_status={
            "tables": [t.__dict__ for t in data.get_status()],
            "gaps_count": len(data.detect_gaps(days=5)),
        },
        recent_backtests=[s.__dict__ for s in recent_bt.items],
        recent_audits=[e.__dict__ for e in audit_result["items"]],
    )
