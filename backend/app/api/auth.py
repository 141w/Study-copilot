from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core import password_policy, turnstile
from app.core.rate_limit import IPRateLimiter, resolve_client_ip
from app.db import User, get_db
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["认证"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login")
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="api/auth/login", auto_error=False)

# Stricter than chat/upload: brute-force protection on credential endpoints.
_auth_limiter = IPRateLimiter(requests_per_minute=20)


def _enforce_auth_rate_limit(request: Request) -> None:
    if not _auth_limiter.check(request):
        raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试")


# ── Schemas ────────────────────────────────────────────────────────────────


class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    # Turnstile token；服务端配置了 SECRET 时必填
    turnstile_token: str | None = None


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    created_at: str


class ProfileUpdate(BaseModel):
    """部分更新：未提供的字段（None）保持不变。"""

    username: str | None = None
    email: EmailStr | None = None


class PasswordChange(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=8, max_length=128)


# ── Dependency ─────────────────────────────────────────────────────────────


async def get_current_user(
    token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)
) -> User:
    return await auth_service.get_user_from_token(db, token)


async def get_optional_user(
    token: str | None = Depends(oauth2_scheme_optional),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    if not token:
        return None
    try:
        return await auth_service.get_user_from_token(db, token)
    except Exception:
        return None


# ── Endpoints ──────────────────────────────────────────────────────────────


@router.get("/register-meta")
async def register_meta() -> dict:
    """注册页公开元数据（无需登录）：开关、Turnstile site key、密码策略。"""
    return {
        "allow_registration": settings.allow_registration,
        "turnstile_site_key": turnstile.site_key(),
        "password": password_policy.POLICY,
    }


@router.post("/register", response_model=UserResponse)
async def register(
    request: Request, user_data: UserCreate, db: AsyncSession = Depends(get_db)
):
    _enforce_auth_rate_limit(request)
    if not settings.allow_registration:
        raise HTTPException(status_code=403, detail="当前未开放注册，请联系管理员")
    await turnstile.verify_turnstile_token(
        user_data.turnstile_token, remote_ip=resolve_client_ip(request)
    )
    new_user = await auth_service.register_user(
        db, user_data.username, user_data.email, user_data.password
    )
    return UserResponse(
        id=new_user.id,
        username=new_user.username,
        email=new_user.email,
        created_at=str(new_user.created_at),
    )


@router.post("/login", response_model=Token)
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    _enforce_auth_rate_limit(request)
    tokens = await auth_service.authenticate_user(db, form_data.username, form_data.password)
    return Token(**tokens)


@router.post("/refresh", response_model=Token)
async def refresh_token(
    request: Request, token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)
):
    _enforce_auth_rate_limit(request)
    tokens = await auth_service.refresh_user_token(db, token)
    return Token(**tokens)


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return UserResponse(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        created_at=str(current_user.created_at),
    )


@router.put("/me", response_model=UserResponse)
async def update_me(
    profile: ProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新当前用户资料（用户名/邮箱，未提交的字段不变）。"""
    updated = await auth_service.update_profile(
        db,
        current_user,
        username=profile.username,
        email=profile.email,
    )
    return UserResponse(
        id=updated.id,
        username=updated.username,
        email=updated.email,
        created_at=str(updated.created_at),
    )


@router.put("/password")
async def change_my_password(
    payload: PasswordChange,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """校验原密码后修改密码。"""
    await auth_service.change_password(db, current_user, payload.old_password, payload.new_password)
    return {"detail": "密码已更新"}
