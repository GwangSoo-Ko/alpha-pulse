"""Risk API — report / stress / limits / custom stress."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from alphapulse.webapp.auth.deps import get_current_user
from alphapulse.webapp.store.readers.risk import RiskReader
from alphapulse.webapp.store.users import User

router = APIRouter(prefix="/api/v1/risk", tags=["risk"])

Mode = Literal["paper", "live", "backtest"]


class RiskReport(BaseModel):
    report: dict
    stress: dict
    cached: bool = False
    computed_at: float | None = None


class LimitsResponse(BaseModel):
    max_position_weight: float
    max_drawdown_soft: float
    max_drawdown_hard: float
    max_daily_orders: int
    max_daily_amount: int


class CustomStressRequest(BaseModel):
    mode: Mode = "paper"
    shocks: dict[str, float] = Field(
        description="시장별 충격 (예: {'KOSPI': -0.1, 'KOSDAQ': -0.15})",
    )


def get_reader(request: Request) -> RiskReader:
    return request.app.state.risk_reader


@router.get("/report", response_model=RiskReport | None)
async def get_report(
    mode: Mode = "paper",
    _: User = Depends(get_current_user),
    reader: RiskReader = Depends(get_reader),
):
    data = reader.get_report(mode=mode)
    return data


@router.get("/stress", response_model=RiskReport | None)
async def get_stress(
    mode: Mode = "paper",
    _: User = Depends(get_current_user),
    reader: RiskReader = Depends(get_reader),
):
    # 동일 API — 캐시된 stress 부분 포함
    return reader.get_report(mode=mode)


@router.post("/stress/custom")
async def run_custom_stress(
    body: CustomStressRequest,
    request: Request,
    _: User = Depends(get_current_user),
    reader: RiskReader = Depends(get_reader),
):
    result = reader.run_custom_stress(mode=body.mode, shocks=body.shocks)
    try:
        request.app.state.audit.log(
            "webapp.risk.custom_stress",
            component="webapp",
            data={"mode": body.mode, "shocks": body.shocks},
            mode="live",
        )
    except AttributeError:
        pass
    return {"results": result}


@router.get("/limits", response_model=LimitsResponse)
async def get_limits(
    _: User = Depends(get_current_user),
    reader: RiskReader = Depends(get_reader),
):
    return LimitsResponse(**reader.get_limits())
