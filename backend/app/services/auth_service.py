"""
Authentication service — user registration, login, token refresh, user lookup,
profile update and password change.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import User
from app.exceptions import (
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    NotFoundError,
    ValidationError,
)
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


async def update_profile(
    db: AsyncSession,
    user: User,
    username: str | None = None,
    email: str | None = None,
) -> User:
    """Update current user's profile fields (username/email).

    None means "keep unchanged". Raises ConflictError on duplicates,
    ValidationError on empty values.
    """
    if username is not None:
        username = username.strip()
        if not username:
            raise ValidationError("用户名不能为空")
        if username != user.username:
            result = await db.execute(select(User).where(User.username == username))
            if result.scalar_one_or_none():
                raise ConflictError("用户名已存在")
            user.username = username

    if email is not None:
        email = email.strip()
        if not email:
            raise ValidationError("邮箱不能为空")
        if email != user.email:
            result = await db.execute(select(User).where(User.email == email))
            if result.scalar_one_or_none():
                raise ConflictError("邮箱已存在")
            user.email = email

    await db.commit()
    await db.refresh(user)
    return user


async def change_password(
    db: AsyncSession,
    user: User,
    old_password: str,
    new_password: str,
) -> None:
    """Change current user's password after verifying the old one.

    Raises AuthenticationError when the old password doesn't match,
    ValidationError when the new password is too weak.
    """
    if not verify_password(old_password, user.password_hash):
        raise AuthenticationError("原密码不正确")

    if len(new_password) < 6:
        raise ValidationError("新密码至少需要 6 位")

    user.password_hash = get_password_hash(new_password)
    await db.commit()
