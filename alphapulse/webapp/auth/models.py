"""Auth Pydantic 모델 — 요청/응답 DTO."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class UserResponse(BaseModel):
    id: int
    email: str
    role: str


class LoginResponse(BaseModel):
    user: UserResponse
