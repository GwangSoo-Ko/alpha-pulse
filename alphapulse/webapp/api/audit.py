"""Audit API — 감사 로그 조회."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel

from alphapulse.webapp.auth.deps import require_role
from alphapulse.webapp.store.readers.audit import AuditReader
from alphapulse.webapp.store.users import User

router = APIRouter(prefix="/api/v1/audit", tags=["audit"])


class AuditEventResponse(BaseModel):
    id: int
    timestamp: float
    event_type: str
    component: str
    data: dict
    mode: str


class AuditListResponse(BaseModel):
    items: list[AuditEventResponse]
    page: int
    size: int
    total: int


def get_reader(request: Request) -> AuditReader:
    return request.app.state.audit_reader


@router.get("/events", response_model=AuditListResponse)
async def list_events(
    from_ts: float | None = None,
    to_ts: float | None = None,
    actor: str | None = None,
    action_prefix: str | None = None,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    _: User = Depends(require_role("admin")),
    reader: AuditReader = Depends(get_reader),
):
    result = reader.query(
        from_ts=from_ts, to_ts=to_ts,
        actor_email=actor, action_prefix=action_prefix,
        page=page, size=size,
    )
    items = [
        AuditEventResponse(
            id=e.id, timestamp=e.timestamp, event_type=e.event_type,
            component=e.component, data=e.data, mode=e.mode,
        )
        for e in result["items"]
    ]
    return AuditListResponse(
        items=items, page=result["page"],
        size=result["size"], total=result["total"],
    )
