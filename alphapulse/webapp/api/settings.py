"""Settings API — category 조회 / 개별 수정 (비밀번호 재확인)."""

from __future__ import annotations

import hashlib
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from alphapulse.webapp.auth.deps import get_current_user, require_role
from alphapulse.webapp.auth.security import verify_password
from alphapulse.webapp.services.settings_service import SettingsService
from alphapulse.webapp.store.settings import SettingsRepository
from alphapulse.webapp.store.users import User, UserRepository


router = APIRouter(prefix="/api/v1/settings", tags=["settings"])


Category = Literal["api_key", "risk_limit", "notification", "backtest"]


class SettingView(BaseModel):
    key: str
    value: str            # 마스킹된 표시용
    is_secret: bool
    category: str
    updated_at: float
    updated_by: int | None


class SettingsListResponse(BaseModel):
    items: list[SettingView]


class UpdateSettingRequest(BaseModel):
    value: str = Field(min_length=1, max_length=10000)
    current_password: str = Field(min_length=1, max_length=256)


def get_repo(request: Request) -> SettingsRepository:
    return request.app.state.settings_repo


def get_service(request: Request) -> SettingsService:
    return request.app.state.settings_service


def get_users(request: Request) -> UserRepository:
    return request.app.state.users


@router.get("", response_model=SettingsListResponse)
async def list_settings(
    category: Category,
    user: User = Depends(require_role("admin")),
    repo: SettingsRepository = Depends(get_repo),
    svc: SettingsService = Depends(get_service),
):
    entries = repo.list_by_category(category)
    items: list[SettingView] = []
    for e in entries:
        raw = repo.get(e.key) or ""
        display = SettingsService.mask(raw) if e.is_secret else raw
        items.append(SettingView(
            key=e.key, value=display,
            is_secret=e.is_secret, category=e.category,
            updated_at=e.updated_at, updated_by=e.updated_by,
        ))
    return SettingsListResponse(items=items)


@router.put("/{key}")
async def update_setting(
    key: str,
    body: UpdateSettingRequest,
    request: Request,
    user: User = Depends(require_role("admin")),
    repo: SettingsRepository = Depends(get_repo),
    users: UserRepository = Depends(get_users),
):
    # 비밀번호 재확인
    current = users.get_by_id(user.id)
    if current is None or not verify_password(
        body.current_password, current.password_hash,
    ):
        raise HTTPException(
            status_code=401, detail="Current password incorrect",
        )
    existing = repo.list_all()
    match = next((e for e in existing if e.key == key), None)
    if match is None:
        raise HTTPException(status_code=404, detail="Setting not found")
    old_val = repo.get(key) or ""
    repo.set(
        key=key, value=body.value,
        is_secret=match.is_secret, category=match.category,
        user_id=user.id,
    )
    try:
        request.app.state.audit.log(
            "webapp.settings.update",
            component="webapp",
            data={
                "key": key, "category": match.category,
                "user_id": user.id,
                "old_hash": hashlib.sha256(
                    old_val.encode("utf-8"),
                ).hexdigest()[:8],
                "new_hash": hashlib.sha256(
                    body.value.encode("utf-8"),
                ).hexdigest()[:8],
            },
            mode="live",
        )
    except AttributeError:
        pass
    return {"ok": True}
