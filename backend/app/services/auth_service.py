"""
Authentication service — user registration, login, token refresh, user lookup.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import User
from app.exceptions import AuthenticationError, AuthorizationError, ConflictError, NotFoundError
from app.utils.auth import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    verify_password,
)


async def register_user(
    db: AsyncSession,
    username: str,
    email: str,
    password: str,
) -> User:
    """Register a new user. Raises ConflictError if username or email exists."""
    result = await db.execute(select(User).where(User.username == username))
    if result.scalar_one_or_none():
        raise ConflictError("用户名已存在")

    result = await db.execute(select(User).where(User.email == email))
    if result.scalar_one_or_none():
        raise ConflictError("邮箱已存在")

    user_id = str(uuid.uuid4())
    new_user = User(
        id=user_id,
        username=username,
        email=email,
        password_hash=get_password_hash(password),
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user


async def authenticate_user(
    db: AsyncSession,
    username: str,
    password: str,
) -> dict:
    """Authenticate by username/password. Returns {access_token, refresh_token}."""
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()

    if not user or not verify_password(password, user.password_hash):
        raise AuthenticationError("用户名或密码错误")

    if not user.is_active:
        raise AuthorizationError("用户已被禁用")

    token_data = {"sub": user.id, "username": user.username}
    return {
        "access_token": create_access_token(data=token_data),
        "refresh_token": create_refresh_token(data=token_data),
    }


async def refresh_user_token(
    db: AsyncSession,
    token: str,
) -> dict:
    """Validate a refresh token and issue new token pair."""
    payload = decode_token(token)
    if not payload or payload.get("type") != "refresh":
        raise AuthenticationError("无效的刷新令牌")

    user_id = payload.get("sub")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise NotFoundError("用户不存在")

    token_data = {"sub": user.id, "username": user.username}
    return {
        "access_token": create_access_token(data=token_data),
        "refresh_token": create_refresh_token(data=token_data),
    }


async def get_user_from_token(
    db: AsyncSession,
    token: str,
) -> User:
    """Decode JWT token and return the matching User. Raises AuthenticationError on failure."""
    payload = decode_token(token)
    if payload is None:
        raise AuthenticationError("无法验证凭据")

    user_id = payload.get("sub")
    if user_id is None:
        raise AuthenticationError("无法验证凭据")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise AuthenticationError("无法验证凭据")

    return user
