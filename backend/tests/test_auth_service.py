import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import User
from app.exceptions import AuthenticationError
from app.services import auth_service
from app.utils.auth import create_access_token, create_refresh_token


def _user(is_active: bool = True) -> User:
    uid = uuid.uuid4().hex[:8]
    return User(
        id=f"as-user-{uid}",
        username=f"asuser_{uid}",
        email=f"as_{uid}@test.local",
        password_hash="x" * 60,
        is_active=is_active,
    )


@pytest.mark.asyncio
async def test_get_user_from_token_success(db_session: AsyncSession):
    u = _user(is_active=True)
    db_session.add(u)
    await db_session.commit()

    token = create_access_token({"sub": u.id, "username": u.username})
    fetched_user = await auth_service.get_user_from_token(db_session, token)
    assert fetched_user.id == u.id


@pytest.mark.asyncio
async def test_get_user_from_token_rejects_refresh_token(db_session: AsyncSession):
    u = _user(is_active=True)
    db_session.add(u)
    await db_session.commit()

    # Refresh token used where access token is expected
    refresh_token = create_refresh_token({"sub": u.id, "username": u.username})
    with pytest.raises(AuthenticationError, match="无效的访问令牌类型"):
        await auth_service.get_user_from_token(db_session, refresh_token)


@pytest.mark.asyncio
async def test_get_user_from_token_rejects_inactive_user(db_session: AsyncSession):
    u = _user(is_active=False)
    db_session.add(u)
    await db_session.commit()

    token = create_access_token({"sub": u.id, "username": u.username})
    with pytest.raises(AuthenticationError, match="账户已被禁用"):
        await auth_service.get_user_from_token(db_session, token)


@pytest.mark.asyncio
async def test_refresh_token_success(db_session: AsyncSession):
    u = _user(is_active=True)
    db_session.add(u)
    await db_session.commit()

    refresh_token = create_refresh_token({"sub": u.id, "username": u.username})
    new_tokens = await auth_service.refresh_user_token(db_session, refresh_token)
    assert "access_token" in new_tokens
    assert "refresh_token" in new_tokens


@pytest.mark.asyncio
async def test_refresh_token_rejects_access_token(db_session: AsyncSession):
    u = _user(is_active=True)
    db_session.add(u)
    await db_session.commit()

    # Access token passed to refresh endpoint
    access_token = create_access_token({"sub": u.id, "username": u.username})
    with pytest.raises(AuthenticationError, match="无效的刷新令牌"):
        await auth_service.refresh_user_token(db_session, access_token)


@pytest.mark.asyncio
async def test_refresh_token_rejects_inactive_user(db_session: AsyncSession):
    u = _user(is_active=False)
    db_session.add(u)
    await db_session.commit()

    refresh_token = create_refresh_token({"sub": u.id, "username": u.username})
    with pytest.raises(AuthenticationError, match="账户已被禁用"):
        await auth_service.refresh_user_token(db_session, refresh_token)
