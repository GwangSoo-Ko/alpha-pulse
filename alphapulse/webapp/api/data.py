"""Data API — status / scheduler / update / collect-*."""

from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request
from pydantic import BaseModel, Field

from alphapulse.webapp.auth.deps import get_current_user
from alphapulse.webapp.jobs.runner import JobRunner
from alphapulse.webapp.services.data_jobs import (
    run_data_collect_financials,
    run_data_collect_short,
    run_data_collect_wisereport,
    run_data_update,
)
from alphapulse.webapp.store.jobs import JobRepository
from alphapulse.webapp.store.readers.data_status import DataStatusReader
from alphapulse.webapp.store.users import User

router = APIRouter(prefix="/api/v1/data", tags=["data"])


class UpdateRequest(BaseModel):
    markets: list[Literal["KOSPI", "KOSDAQ"]] = Field(
        default_factory=lambda: ["KOSPI"],
    )


class CollectRequest(BaseModel):
    market: Literal["KOSPI", "KOSDAQ"] = "KOSPI"
    top: int = Field(default=100, ge=1, le=500)


class JobCreatedResponse(BaseModel):
    job_id: str


def get_reader(request: Request) -> DataStatusReader:
    return request.app.state.data_status_reader


def get_jobs(request: Request) -> JobRepository:
    return request.app.state.jobs


def get_runner(request: Request) -> JobRunner:
    return request.app.state.job_runner


def _audit(request: Request, action: str, data: dict) -> None:
    try:
        request.app.state.audit.log(
            action, component="webapp", data=data, mode="live",
        )
    except AttributeError:
        pass


@router.get("/status")
async def get_status(
    gap_days: int = Query(5, ge=1, le=30),
    _: User = Depends(get_current_user),
    reader: DataStatusReader = Depends(get_reader),
):
    return {
        "tables": [t.__dict__ for t in reader.get_status()],
        "gaps": reader.detect_gaps(days=gap_days),
    }


@router.post("/update", response_model=JobCreatedResponse)
async def update(
    body: UpdateRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    job_repo: JobRepository = Depends(get_jobs),
    runner: JobRunner = Depends(get_runner),
):
    job_id = str(uuid.uuid4())
    job_repo.create(
        job_id=job_id, kind="data_update",
        params=body.model_dump(), user_id=user.id,
    )
    _audit(request, "webapp.data.job_started",
           {"kind": "update", "markets": body.markets, "job_id": job_id})

    async def _run():
        await runner.run(job_id, run_data_update, markets=body.markets)

    background_tasks.add_task(_run)
    return JobCreatedResponse(job_id=job_id)


@router.post("/collect-financials", response_model=JobCreatedResponse)
async def collect_financials(
    body: CollectRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    job_repo: JobRepository = Depends(get_jobs),
    runner: JobRunner = Depends(get_runner),
):
    job_id = str(uuid.uuid4())
    job_repo.create(
        job_id=job_id, kind="data_update",
        params=body.model_dump(), user_id=user.id,
    )
    _audit(request, "webapp.data.job_started",
           {"kind": "collect_financials", "market": body.market,
            "top": body.top, "job_id": job_id})

    async def _run():
        await runner.run(
            job_id, run_data_collect_financials,
            market=body.market, top=body.top,
        )

    background_tasks.add_task(_run)
    return JobCreatedResponse(job_id=job_id)


@router.post("/collect-wisereport", response_model=JobCreatedResponse)
async def collect_wisereport(
    body: CollectRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    job_repo: JobRepository = Depends(get_jobs),
    runner: JobRunner = Depends(get_runner),
):
    job_id = str(uuid.uuid4())
    job_repo.create(
        job_id=job_id, kind="data_update",
        params=body.model_dump(), user_id=user.id,
    )
    _audit(request, "webapp.data.job_started",
           {"kind": "collect_wisereport", "market": body.market,
            "top": body.top, "job_id": job_id})

    async def _run():
        await runner.run(
            job_id, run_data_collect_wisereport,
            market=body.market, top=body.top,
        )

    background_tasks.add_task(_run)
    return JobCreatedResponse(job_id=job_id)


@router.post("/collect-short", response_model=JobCreatedResponse)
async def collect_short(
    body: CollectRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    job_repo: JobRepository = Depends(get_jobs),
    runner: JobRunner = Depends(get_runner),
):
    job_id = str(uuid.uuid4())
    job_repo.create(
        job_id=job_id, kind="data_update",
        params=body.model_dump(), user_id=user.id,
    )
    _audit(request, "webapp.data.job_started",
           {"kind": "collect_short", "market": body.market,
            "top": body.top, "job_id": job_id})

    async def _run():
        await runner.run(
            job_id, run_data_collect_short,
            market=body.market, top=body.top,
        )

    background_tasks.add_task(_run)
    return JobCreatedResponse(job_id=job_id)
