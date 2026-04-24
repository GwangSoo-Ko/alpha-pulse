"""Notification API — 인앱 알림 조회, 읽음 처리."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from alphapulse.webapp.auth.deps import get_current_user
from alphapulse.webapp.store.notifications import NotificationStore
from alphapulse.webapp.store.users import User

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


class Notification(BaseModel):
    id: int
    kind: str
    level: str
    title: str
    body: str | None = None
    link: str | None = None
    created_at: float
    is_read: int


class NotificationListResponse(BaseModel):
    items: list[Notification]


class UnreadCountResponse(BaseModel):
    count: int


class MarkReadResponse(BaseModel):
    ok: bool


class MarkAllReadResponse(BaseModel):
    count: int


def get_notification_store(request: Request) -> NotificationStore:
    return request.app.state.notification_store


@router.get("", response_model=NotificationListResponse)
async def list_notifications(
    limit: int = Query(20, ge=1, le=100),
    _: User = Depends(get_current_user),
    store: NotificationStore = Depends(get_notification_store),
):
    return NotificationListResponse(
        items=[Notification(**n) for n in store.list_recent(limit=limit)],
    )


@router.get("/unread-count", response_model=UnreadCountResponse)
async def unread_count(
    _: User = Depends(get_current_user),
    store: NotificationStore = Depends(get_notification_store),
):
    return UnreadCountResponse(count=store.unread_count())


@router.post("/read-all", response_model=MarkAllReadResponse)
async def mark_all_read(
    _: User = Depends(get_current_user),
    store: NotificationStore = Depends(get_notification_store),
):
    return MarkAllReadResponse(count=store.mark_all_read())


@router.post("/{notification_id}/read", response_model=MarkReadResponse)
async def mark_read(
    notification_id: int,
    _: User = Depends(get_current_user),
    store: NotificationStore = Depends(get_notification_store),
):
    if not store.mark_read(notification_id):
        raise HTTPException(status_code=404, detail="Notification not found")
    return MarkReadResponse(ok=True)
