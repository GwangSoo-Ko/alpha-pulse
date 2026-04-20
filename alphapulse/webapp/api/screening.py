"""Screening API — 조회 / 실행 (Job) / 삭제."""

from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from alphapulse.webapp.auth.deps import get_current_user, require_role
from alphapulse.webapp.jobs.runner import JobRunner
from alphapulse.webapp.services.screening_runner import run_screening_sync
from alphapulse.webapp.store.jobs import JobRepository
from alphapulse.webapp.store.screening import ScreeningRepository
from alphapulse.webapp.store.users import User

router = APIRouter(prefix="/api/v1/screening", tags=["screening"])


class ScreeningRunRequest(BaseModel):
    market: Literal["KOSPI", "KOSDAQ", "ALL"] = "KOSPI"
    strategy: str = Field(default="momentum", max_length=40)
    factor_weights: dict[str, float] = Field(
        default_factory=lambda: {
            "momentum": 0.5, "value": 0.0, "quality": 0.0,
            "growth": 0.0, "flow": 0.3, "volatility": 0.2,
        },
    )
    top_n: int = Field(default=20, ge=1, le=100)
    name: str = Field(default="", max_length=100)


class ScreeningRunResponse(BaseModel):
    job_id: str


class RunSummary(BaseModel):
    run_id: str
    name: str
    market: str
    strategy: str
    top_n: int
    created_at: float


class RunListResponse(BaseModel):
    items: list[RunSummary]
    page: int
    size: int
    total: int


class RunDetailResponse(BaseModel):
    run_id: str
    name: str
    market: str
    strategy: str
    factor_weights: dict
    top_n: int
    market_context: dict
    results: list
    created_at: float


def get_repo(request: Request) -> ScreeningRepository:
    return request.app.state.screening_repo


def get_jobs(request: Request) -> JobRepository:
    return request.app.state.jobs


def get_runner(request: Request) -> JobRunner:
    return request.app.state.job_runner


@router.get("/runs", response_model=RunListResponse)
async def list_runs(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    repo: ScreeningRepository = Depends(get_repo),
):
    p = repo.list_for_user(user_id=user.id, page=page, size=size)
    return RunListResponse(
        items=[
            RunSummary(
                run_id=r.run_id, name=r.name,
                market=r.market, strategy=r.strategy,
                top_n=r.top_n, created_at=r.created_at,
            )
            for r in p.items
        ],
        page=p.page, size=p.size, total=p.total,
    )


@router.get("/runs/{run_id}", response_model=RunDetailResponse)
async def get_run(
    run_id: str,
    user: User = Depends(get_current_user),
    repo: ScreeningRepository = Depends(get_repo),
):
    run = repo.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    if run.user_id != user.id and user.role != "admin":
        raise HTTPException(status_code=403, detail="Forbidden")
    return RunDetailResponse(
        run_id=run.run_id, name=run.name,
        market=run.market, strategy=run.strategy,
        factor_weights=run.factor_weights, top_n=run.top_n,
        market_context=run.market_context,
        results=run.results, created_at=run.created_at,
    )


@router.post("/run", response_model=ScreeningRunResponse)
async def run_screening(
    body: ScreeningRunRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    repo: ScreeningRepository = Depends(get_repo),
    job_repo: JobRepository = Depends(get_jobs),
    runner: JobRunner = Depends(get_runner),
):
    job_id = str(uuid.uuid4())
    job_repo.create(
        job_id=job_id, kind="screening",
        params=body.model_dump(),
        user_id=user.id,
    )
    try:
        request.app.state.audit.log(
            "webapp.screening.run",
            component="webapp",
            data={
                "user_id": user.id, "job_id": job_id,
                "market": body.market, "strategy": body.strategy,
            },
            mode="live",
        )
    except AttributeError:
        pass

    async def _run():
        await runner.run(
            job_id,
            run_screening_sync,
            market=body.market, strategy=body.strategy,
            factor_weights=body.factor_weights,
            top_n=body.top_n, name=body.name,
            screening_repo=repo, user_id=user.id,
        )

    background_tasks.add_task(_run)
    return ScreeningRunResponse(job_id=job_id)


@router.delete("/runs/{run_id}")
async def delete_run(
    run_id: str,
    request: Request,
    user: User = Depends(require_role("admin")),
    repo: ScreeningRepository = Depends(get_repo),
):
    run = repo.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    repo.delete(run_id)
    try:
        request.app.state.audit.log(
            "webapp.screening.delete",
            component="webapp",
            data={"user_id": user.id, "run_id": run_id},
            mode="live",
        )
    except AttributeError:
        pass
    return {"ok": True}
