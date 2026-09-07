from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import User, get_db
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["认证"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login")
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="api/auth/login", auto_error=False)


# ── Schemas ────────────────────────────────────────────────────────────────


class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str


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
    new_password: str


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


@router.post("/register", response_model=UserResponse)
async def register(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
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
    form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)
):
    tokens = await auth_service.authenticate_user(db, form_data.username, form_data.password)
    return Token(**tokens)


@router.post("/refresh", response_model=Token)
async def refresh_token(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)):
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
