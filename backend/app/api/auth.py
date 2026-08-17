from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import User, get_db
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["认证"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login")


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


# ── Dependency ─────────────────────────────────────────────────────────────


async def get_current_user(
    token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)
) -> User:
    return await auth_service.get_user_from_token(db, token)


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
